#!/usr/bin/env node
// remind 0.1.0
// Helper for the /remind skill: keeps a repo's reminders in reminders/<ID>.md and mirrors each one to
// the user's Google Tasks (always) and Google Calendar (when it has a time).
// Plain Node 22+, no dependencies. Procedures live in ../SKILL.md.
//
// Per-machine state, outside every repo (never commit it):
//   ~/.config/remind/client.json  OAuth client of type "installed" (Desktop app)
//   ~/.config/remind/token.json   refresh token, mode 600
//   ~/.config/remind/repos.json   repo code -> repo path, so an ID resolves from any repo
//   ~/.config/remind/config.json  optional {"host": "<name>"}: the machine tag on Google titles

import { readFileSync, writeFileSync, existsSync, readdirSync, mkdirSync, chmodSync, copyFileSync } from 'node:fs'
import { join, basename, relative } from 'node:path'
import { homedir, hostname } from 'node:os'
import { execFileSync } from 'node:child_process'
import { createServer } from 'node:http'
import { randomBytes, createHash } from 'node:crypto'

const CONF = join(homedir(), '.config', 'remind')
const CLIENT = join(CONF, 'client.json')
const TOKEN = join(CONF, 'token.json')
const REPOS = join(CONF, 'repos.json')
const CONFIG = join(CONF, 'config.json')
const SCOPES = ['openid', 'email', 'https://www.googleapis.com/auth/tasks', 'https://www.googleapis.com/auth/calendar.events']
const TASKS = 'https://tasks.googleapis.com/tasks/v1'
const CAL = 'https://www.googleapis.com/calendar/v3/calendars/primary/events'
const CODE_RE = /^[A-Z][A-Z0-9]{1,5}$/
const ID_RE = /^([A-Z][A-Z0-9]{1,5})-(\d+)$/
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const TIME_RE = /^\d{2}:\d{2}$/
// Folders searched for a repo whose code is not yet in repos.json on this machine.
const PROJECT_DIRS = [join(homedir(), 'projects'), join(homedir(), 'src'), join(homedir(), 'code')]
const NOTES_MAX = 1800

const today = () => new Date().toLocaleDateString('en-CA')

/** Which machine holds the files: "mac", "wsl", or the hostname; config.json "host" overrides. */
function hostTag() {
  const set = readJson(CONFIG, {}).host
  if (set) return set
  if (process.platform === 'darwin') return 'mac'
  if (process.env.WSL_DISTRO_NAME || (existsSync('/proc/version') && /microsoft/i.test(readFileSync('/proc/version', 'utf8')))) return 'wsl'
  return hostname().split('.')[0]
}
const tz = () => Intl.DateTimeFormat().resolvedOptions().timeZone
// Every failure throws; the CLI at the bottom prints it. `show` catches remote ones to print the brief anyway.
const die = (msg) => { throw new Error(msg) }
const readJson = (p, dflt) => (existsSync(p) ? JSON.parse(readFileSync(p, 'utf8')) : dflt)
function writeSecret(p, obj) {
  mkdirSync(CONF, { recursive: true, mode: 0o700 })
  writeFileSync(p, JSON.stringify(obj, null, 2) + '\n', { mode: 0o600 })
  chmodSync(p, 0o600)
}

// ---------------------------------------------------------------------------
// Repo, code and reminder files
// ---------------------------------------------------------------------------
function repoRoot(cwd = process.cwd()) {
  try { return execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim() } catch { return null }
}

/** The repo's reminder code (MDO for maac-digital-ops), fixed on first use in reminders/config.json. */
function repoCode(root) {
  const cfgPath = join(root, 'reminders', 'config.json')
  let code = readJson(cfgPath, {}).code
  if (!code) {
    const parts = basename(root).split(/[-_.\s]+/).filter(Boolean)
    code = (parts.length > 1 ? parts.map((p) => p[0]).join('') : parts[0].slice(0, 3)).toUpperCase().replace(/[^A-Z0-9]/g, '')
    if (!/^[A-Z]/.test(code)) code = `R${code}`
    code = code.padEnd(2, 'R').slice(0, 6)
    mkdirSync(join(root, 'reminders'), { recursive: true })
    writeFileSync(cfgPath, JSON.stringify({ code }, null, 2) + '\n')
  }
  if (!CODE_RE.test(code)) die(`code "${code}" in ${cfgPath} must be 2 to 6 capital letters or digits, starting with a letter`)
  const repos = readJson(REPOS, {})
  if (repos[code] && repos[code] !== root) die(`code ${code} already belongs to ${repos[code]}; set another "code" in ${cfgPath}`)
  if (repos[code] !== root) { repos[code] = root; mkdirSync(CONF, { recursive: true, mode: 0o700 }); writeFileSync(REPOS, JSON.stringify(repos, null, 2) + '\n') }
  return code
}

/** Finds a repo on this machine whose reminders/config.json has this code, and registers it. */
function discover(code) {
  const near = repoRoot()
  for (const dir of [...new Set([near && join(near, '..'), ...PROJECT_DIRS].filter(Boolean))]) {
    if (!existsSync(dir)) continue
    for (const name of readdirSync(dir)) {
      const root = join(dir, name)
      if (readJson(join(root, 'reminders', 'config.json'), {}).code === code) {
        const repos = readJson(REPOS, {})
        repos[code] = root
        mkdirSync(CONF, { recursive: true, mode: 0o700 })
        writeFileSync(REPOS, JSON.stringify(repos, null, 2) + '\n')
        return root
      }
    }
  }
  return null
}

/** Finds the file for an ID, from any repo registered in repos.json or found under the project folders. */
function locate(id) {
  const m = String(id).toUpperCase().match(ID_RE)
  if (!m) die(`"${id}" is not a reminder ID (like MDO-3)`)
  const root = readJson(REPOS, {})[m[1]] || discover(m[1]) || repoRoot()
  const file = root && join(root, 'reminders', `${m[1]}-${m[2]}.md`)
  if (!file || !existsSync(file)) die(`no reminder ${m[0]} (looked in ${root ? join(root, 'reminders') : 'no repo'})`)
  return { id: m[0], root, file }
}

function scalar(raw) {
  const s = raw.trim()
  if (s.startsWith('[') && s.endsWith(']')) return s.slice(1, -1).split(',').map(scalar).filter((x) => x !== '')
  if ((s.startsWith("'") && s.endsWith("'")) || (s.startsWith('"') && s.endsWith('"'))) return s.slice(1, -1).replace(/''/g, "'")
  return s
}
const quote = (v) => (v === '' || /[:#\[\]{}',]|^\s|\s$/.test(v) ? `'${v.replace(/'/g, "''")}'` : v)
const KEYS = ['id', 'title', 'status', 'due', 'time', 'duration', 'created', 'updated', 'updated_by', 'host', 'sources', 'google_task', 'google_event']

function parse(text) {
  const m = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/)
  if (!m) die('reminder file has no frontmatter')
  const fm = {}
  for (const line of m[1].split(/\r?\n/)) {
    const kv = line.match(/^([A-Za-z_][\w-]*):(.*)$/)
    if (kv) fm[kv[1]] = scalar(kv[2])
  }
  return { fm, body: m[2] }
}
function serialize({ fm, body }) {
  const keys = [...KEYS.filter((k) => k in fm), ...Object.keys(fm).filter((k) => !KEYS.includes(k))]
  const lines = keys.map((k) => `${k}: ${Array.isArray(fm[k]) ? `[${fm[k].map(quote).join(', ')}]` : quote(String(fm[k] ?? ''))}`)
  return `---\n${lines.join('\n')}\n---\n${body.startsWith('\n') ? '' : '\n'}${body}`
}
const load = (file) => parse(readFileSync(file, 'utf8'))
function save(file, doc, logLine, agent) {
  doc.fm.updated = today()
  if (agent) doc.fm.updated_by = agent
  if (logLine) doc.body = doc.body.replace(/\s*$/, `\n- ${today()} (${doc.fm.updated_by}): ${logLine}\n`)
  writeFileSync(file, serialize(doc))
}

/** Writes the file without a log line, so a remote ID survives a later failure in the same push. */
const persist = (file, doc) => writeFileSync(file, serialize(doc))

function section(body, name) {
  const m = body.match(new RegExp(`^## ${name}\\s*\\n([\\s\\S]*?)(?=^## |$(?![\\s\\S]))`, 'm'))
  return m ? m[1].trim() : ''
}

/** Text that goes into the Google Task notes and the event description. */
function googleNotes(doc, root) {
  const { fm, body } = doc
  let summary = section(body, 'Summary') || '(no summary written)'
  const tail = [
    fm.sources?.length ? `Sources: ${fm.sources.join(', ')}` : '',
    `Details on ${fm.host}: ask an agent "pull up ${fm.id}" (${basename(root)}/reminders/${fm.id}.md)`,
  ].filter(Boolean).join('\n')
  const room = NOTES_MAX - tail.length - 2
  if (summary.length > room) summary = summary.slice(0, room - 1).trimEnd() + '…'
  return `${summary}\n\n${tail}`
}

// ---------------------------------------------------------------------------
// Google OAuth (installed-app loopback flow with PKCE) and API calls
// ---------------------------------------------------------------------------
function client() {
  if (!existsSync(CLIENT)) die(`no OAuth client at ${CLIENT}; run: remind.mjs auth --client <path to a Desktop OAuth client JSON>`)
  const raw = readJson(CLIENT)
  const c = raw.installed || raw.web
  if (!c?.client_id) die(`${CLIENT} is not an OAuth client file`)
  return c
}

async function tokenRequest(params) {
  const c = client()
  const res = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_id: c.client_id, client_secret: c.client_secret, ...params }),
  })
  const json = await res.json()
  if (!res.ok) {
    if (json.error === 'invalid_grant') die('Google refused the saved login (expired or revoked; an app in "Testing" status expires it after 7 days). Run: remind.mjs auth')
    die(`token request failed: ${json.error} ${json.error_description || ''}`)
  }
  return json
}

async function accessToken() {
  const t = readJson(TOKEN, null)
  if (!t?.refresh_token) die('not connected to Google yet; run: remind.mjs auth')
  if (t.access_token && t.expiry > Date.now() + 60_000) return t.access_token
  const json = await tokenRequest({ grant_type: 'refresh_token', refresh_token: t.refresh_token })
  writeSecret(TOKEN, { ...t, access_token: json.access_token, expiry: Date.now() + json.expires_in * 1000 })
  return json.access_token
}

async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: { authorization: `Bearer ${await accessToken()}`, ...(body ? { 'content-type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 404 || res.status === 410) return null
  const text = await res.text()
  if (!res.ok) die(`${method} ${url.split('?')[0]} failed (${res.status}): ${text.slice(0, 300)}`)
  return text ? JSON.parse(text) : {}
}

async function auth(args) {
  if (args.client) {
    const raw = readJson(args.client)
    if (!(raw.installed || raw.web)?.client_id) die(`${args.client} is not an OAuth client file`)
    mkdirSync(CONF, { recursive: true, mode: 0o700 })
    copyFileSync(args.client, CLIENT)
    chmodSync(CLIENT, 0o600)
  }
  const c = client()
  const verifier = randomBytes(48).toString('base64url')
  const challenge = createHash('sha256').update(verifier).digest('base64url')
  const state = randomBytes(16).toString('hex')
  const server = createServer()
  await new Promise((r) => server.listen(0, '127.0.0.1', r))
  const redirect = `http://127.0.0.1:${server.address().port}`
  const url = 'https://accounts.google.com/o/oauth2/v2/auth?' + new URLSearchParams({
    client_id: c.client_id, redirect_uri: redirect, response_type: 'code', scope: SCOPES.join(' '),
    access_type: 'offline', prompt: 'consent', code_challenge: challenge, code_challenge_method: 'S256', state,
  })
  const code = await new Promise((resolve, reject) => {
    server.on('request', (req, res) => {
      const q = new URL(req.url, redirect).searchParams
      if (!q.get('code') && !q.get('error')) { res.writeHead(404).end(); return }
      res.writeHead(200, { 'content-type': 'text/plain' }).end('remind: done, you can close this tab.')
      server.close()
      if (q.get('state') !== state) reject(new Error('state mismatch'))
      else if (q.get('error')) reject(new Error(q.get('error')))
      else resolve(q.get('code'))
    })
    console.log(`Opening Google sign-in. If no browser opens, visit:\n${url}\n`)
    try { execFileSync(process.platform === 'darwin' ? 'open' : 'xdg-open', [url], { stdio: 'ignore' }) } catch {}
  }).catch((e) => die(`sign-in failed: ${e.message}`))
  const json = await tokenRequest({ grant_type: 'authorization_code', code, redirect_uri: redirect, code_verifier: verifier })
  if (!json.refresh_token) die('Google returned no refresh token; remove the app at myaccount.google.com/permissions and run auth again')
  const email = json.id_token ? JSON.parse(Buffer.from(json.id_token.split('.')[1], 'base64url')).email : 'unknown'
  writeSecret(TOKEN, { refresh_token: json.refresh_token, access_token: json.access_token, expiry: Date.now() + json.expires_in * 1000, email })
  console.log(`connected as ${email}`)
  // Push whatever this repo has waiting, so the first sign-in finishes the job it was started for.
  const root = repoRoot()
  if (root && existsSync(join(root, 'reminders'))) {
    for (const f of reminderFiles(root)) {
      const doc = load(f)
      if (doc.fm.status === 'OPEN' && !doc.fm.google_task) await push(doc.fm.id, {})
    }
  }
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------
function reminderFiles(root) {
  const dir = join(root, 'reminders')
  if (!existsSync(dir)) return []
  return readdirSync(dir).filter((f) => /^[A-Z][A-Z0-9]*-\d+\.md$/.test(f))
    .sort((a, b) => Number(a.match(/-(\d+)\./)[1]) - Number(b.match(/-(\d+)\./)[1]))
    .map((f) => join(dir, f))
}

function newReminder(title, args) {
  const root = repoRoot() || die('run inside a git repo')
  if (!title) die('usage: new "<title>" --due YYYY-MM-DD [--time HH:MM] [--duration MIN] [--source <path>]...')
  if (!DATE_RE.test(args.due || '')) die('--due YYYY-MM-DD is required')
  if (args.time && !TIME_RE.test(args.time)) die('--time must be HH:MM (24-hour, local time)')
  const code = repoCode(root)
  const n = reminderFiles(root).reduce((max, f) => Math.max(max, Number(f.match(/-(\d+)\.md$/)[1])), 0) + 1
  const id = `${code}-${n}`
  const fm = { id, title, status: 'OPEN', due: args.due, created: today(), updated: today(), updated_by: args.agent || 'claude', host: hostTag(), sources: args.source }
  if (args.time) { fm.time = args.time; fm.duration = args.duration || '15' }
  const body = `\n# ${id}: ${title}\n\n## Summary\n\n## Details\n\n## Log\n\n- ${today()} (${fm.updated_by}): Created.\n`
  const file = join(root, 'reminders', `${id}.md`)
  writeFileSync(file, serialize({ fm, body }))
  console.log(`${id}\t${relative(process.cwd(), file)}`)
}

async function push(id, args) {
  const { root, file } = locate(id)
  const doc = load(file)
  const { fm } = doc
  if (fm.status !== 'OPEN') die(`${fm.id} is ${fm.status}; only OPEN reminders are pushed`)
  if (!section(doc.body, 'Summary')) die(`${fm.id} has an empty "## Summary"; write it first, it is what Google shows`)
  fm.host = hostTag()
  const notes = googleNotes(doc, root)
  const title = `[${fm.id}] ${fm.title} · ${fm.host}`
  const done = []
  const task = { title, notes, due: `${fm.due}T00:00:00.000Z` }
  const existing = fm.google_task && (await api('GET', `${TASKS}/lists/@default/tasks/${fm.google_task}`))
  if (existing && !existing.deleted) { await api('PATCH', `${TASKS}/lists/@default/tasks/${fm.google_task}`, task); done.push('task updated') }
  else { fm.google_task = (await api('POST', `${TASKS}/lists/@default/tasks`, task)).id; persist(file, doc); done.push('task created') }

  if (fm.time && !args['no-calendar']) {
    const start = new Date(`${fm.due}T${fm.time}:00`)
    const end = new Date(start.getTime() + Number(fm.duration || 15) * 60_000)
    const local = (d) => `${d.toLocaleDateString('en-CA')}T${d.toTimeString().slice(0, 8)}`
    const event = {
      summary: title, description: notes,
      start: { dateTime: local(start), timeZone: tz() }, end: { dateTime: local(end), timeZone: tz() },
      reminders: { useDefault: false, overrides: [{ method: 'popup', minutes: 30 }, { method: 'popup', minutes: 0 }] },
    }
    const ev = fm.google_event && (await api('GET', `${CAL}/${fm.google_event}`))
    if (ev && ev.status !== 'cancelled') { await api('PATCH', `${CAL}/${fm.google_event}`, event); done.push('event updated') }
    else { fm.google_event = (await api('POST', CAL, event)).id; persist(file, doc); done.push('event created') }
  } else if (fm.google_event) {
    await api('DELETE', `${CAL}/${fm.google_event}`); delete fm.google_event; persist(file, doc); done.push('event removed (no time)')
  }
  save(file, doc, `Pushed to Google: ${done.join(', ')}.`, args.agent)
  console.log(`${fm.id}: ${done.join(', ')} · due ${fm.due}${fm.time ? ` ${fm.time}` : ''}`)
}

async function liveState(fm) {
  if (!fm.google_task) return 'not pushed'
  const t = await api('GET', `${TASKS}/lists/@default/tasks/${fm.google_task}`)
  if (!t || t.deleted) return 'deleted in Google'
  return t.status === 'completed' ? 'completed in Google' : 'open in Google'
}

async function show(id) {
  const { file } = locate(id)
  const doc = load(file)
  let state = 'not connected'
  if (existsSync(TOKEN)) { try { state = await liveState(doc.fm) } catch (e) { state = `unavailable (${e.message})` } }
  console.log(`${file}\nGoogle: ${state}\n`)
  console.log(readFileSync(file, 'utf8'))
}

async function sync(args) {
  const root = repoRoot() || die('run inside a git repo')
  for (const f of reminderFiles(root)) {
    const doc = load(f)
    if (doc.fm.status !== 'OPEN' || !doc.fm.google_task) continue
    const state = await liveState(doc.fm)
    if (state === 'completed in Google') { doc.fm.status = 'DONE'; save(f, doc, 'Marked done in Google; synced.', args.agent); console.log(`${doc.fm.id}: DONE`) }
    if (state === 'deleted in Google') {
      if (doc.fm.google_event) { await api('DELETE', `${CAL}/${doc.fm.google_event}`); delete doc.fm.google_event; persist(f, doc) }
      doc.fm.status = 'CANCELLED'; save(f, doc, 'Deleted in Google; synced as cancelled, Calendar event removed.', args.agent); console.log(`${doc.fm.id}: CANCELLED`)
    }
  }
  await list({})
}

async function close(id, status, args) {
  const { file } = locate(id)
  const doc = load(file)
  const { fm } = doc
  if (fm.google_task) {
    if (status === 'DONE') await api('PATCH', `${TASKS}/lists/@default/tasks/${fm.google_task}`, { status: 'completed' })
    else await api('DELETE', `${TASKS}/lists/@default/tasks/${fm.google_task}`)
  }
  if (fm.google_event && status === 'CANCELLED') await api('DELETE', `${CAL}/${fm.google_event}`)
  fm.status = status
  save(file, doc, status === 'DONE' ? `Done${args.reason ? `: ${args.reason}` : ''}.` : `Cancelled${args.reason ? `: ${args.reason}` : ''}.`, args.agent)
  console.log(`${fm.id}: ${status}`)
}

async function list(args) {
  const root = repoRoot() || die('run inside a git repo')
  const rows = reminderFiles(root).map(load).map((d) => d.fm).filter((fm) => args.all || fm.status === 'OPEN')
  if (!rows.length) { console.log(args.all ? 'no reminders' : 'no open reminders (--all shows closed ones)'); return }
  const now = today()
  for (const fm of rows.sort((a, b) => `${a.due}${a.time || ''}`.localeCompare(`${b.due}${b.time || ''}`))) {
    const flag = fm.status === 'OPEN' && fm.due < now ? ' OVERDUE' : ''
    console.log(`${fm.id.padEnd(8)} ${fm.status.padEnd(9)} ${fm.due} ${(fm.time || '').padEnd(5)}${flag} ${fm.title}${fm.google_task ? '' : '  [not pushed]'}`)
  }
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------
function parseArgs(argv) {
  const pos = []
  const args = { source: [] }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (!a.startsWith('--')) { pos.push(a); continue }
    const key = a.slice(2)
    const next = argv[i + 1]
    const val = next === undefined || next.startsWith('--') ? true : (i++, next)
    if (key === 'source') args.source.push(val)
    else args[key] = val
  }
  return { pos, args }
}

const USAGE = `remind <command>
  auth [--client <file>]        sign in to Google (once); pushes this repo's unpushed reminders
  new "<title>" --due YYYY-MM-DD [--time HH:MM] [--duration MIN] [--source <path>]...
                                create reminders/<ID>.md (not pushed yet)
  push <ID> [--no-calendar]     create or update the Google Task (and Calendar event if it has a time)
  show <ID>                     print the reminder and its Google state; works from any repo
  list [--all]                  this repo's reminders (open only unless --all)
  sync                          pull done or deleted state back from Google Tasks
  done <ID> [--reason <text>]   complete the task in Google and mark DONE
  cancel <ID> [--reason <text>] delete the task and event in Google and mark CANCELLED
  Any command takes --agent <name> for updated_by (default claude).`

const [cmd, ...rest] = process.argv.slice(2)
const { pos, args } = parseArgs(rest)
try {
  switch (cmd) {
    case 'auth': await auth(args); break
    case 'new': newReminder(pos[0], args); break
    case 'push': await push(pos[0], args); break
    case 'show': await show(pos[0]); break
    case 'list': await list(args); break
    case 'sync': await sync(args); break
    case 'done': await close(pos[0], 'DONE', args); break
    case 'cancel': await close(pos[0], 'CANCELLED', args); break
    default: console.log(USAGE); if (cmd && cmd !== 'help' && cmd !== '--help') process.exit(1)
  }
} catch (e) {
  console.error(`remind: ${e.message}`)
  process.exit(1)
}
