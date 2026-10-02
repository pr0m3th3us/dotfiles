#!/usr/bin/env node
// runbook 0.1.0 · source: dotfiles/agent-skills/runbook
// Helper for the runbook skill: a board of a repo's runbooks, their ready steps, and recording ticks.
// Plain Node 22+, no dependencies. The board draws like `pin list` (kno-hub/kits/pin/scripts/pin.mjs).
//
// A runbook is a folder holding <name>-rb-data.json; in a stratadoc repo, every folder under the
// runbooks layer counts too, with or without a checklist. Its ticks are <name>-progress.json beside
// the data (the rb-state shape: {"done": {"p0.1": true}, "updatedAt": <ms>}); a runbook is in flight
// once that file exists.

import { readFileSync, writeFileSync, existsSync, readdirSync, realpathSync } from 'node:fs'
import { join, dirname, resolve, relative } from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

export const VERSION = '0.1.0'
export const STALE_DAYS = 3
const HERE = dirname(fileURLToPath(import.meta.url))
const SKIP_DIRS = new Set(['node_modules', '_archive', 'dist', 'build'])
const RETIRED_STATUSES = new Set(['DEPRECATED', 'SUPERSEDED', 'REJECTED'])
export const COLUMNS = ['IN FLIGHT', 'NOT STARTED', 'REFERENCE', 'DONE', 'RETIRED']
const HIDDEN = new Set(['RETIRED'])

const isoDate = (d) => d.toLocaleDateString('en-CA')
const readJson = (p) => (existsSync(p) ? JSON.parse(readFileSync(p, 'utf8')) : null)
const upper = (s) => String(s || '').toUpperCase()
const plain = (s) => String(s || '').replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim()

export function repoRoot(cwd = process.cwd()) {
  try {
    return execFileSync('git', ['rev-parse', '--show-toplevel'], { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
  } catch {
    return cwd
  }
}

function me(root) {
  if (process.env.RUNBOOK_ME) return process.env.RUNBOOK_ME
  try {
    return execFileSync('git', ['config', 'user.name'], { cwd: root, encoding: 'utf8' }).trim().split(/\s+/)[0]
  } catch {
    return ''
  }
}

function frontmatter(path) {
  if (!existsSync(path)) return {}
  const m = readFileSync(path, 'utf8').match(/^---\n([\s\S]*?)\n---/)
  const get = (k) => (m?.[1].match(new RegExp(`^${k}:\\s*(.*)$`, 'm')) || [])[1]?.trim().replace(/^(['"])(.*)\1$/, '$2')
  return { title: get('title'), status: get('status') }
}

function stratadocRunbookDir(root) {
  const cfg = join(root, 'stratadoc.yaml')
  if (!existsSync(cfg)) return null
  const docs = (readFileSync(cfg, 'utf8').match(/^docs_dir:\s*([^\s#]+)/m) || [])[1] || 'docs'
  const dir = join(root, docs, '30-runbooks')
  return existsSync(dir) ? dir : null
}

/** Every runbook in the repo: data files found by walking it, plus a stratadoc repo's runbook folders. */
export function findRunbooks(root) {
  const found = new Map()
  const walk = (dir) => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      if (e.name.startsWith('.') || SKIP_DIRS.has(e.name)) continue
      const p = join(dir, e.name)
      if (e.isDirectory()) walk(p)
      else if (e.name.endsWith('-rb-data.json')) found.set(p.slice(0, -'-rb-data.json'.length), true)
    }
  }
  walk(root)
  const layer = stratadocRunbookDir(root)
  if (layer) {
    for (const e of readdirSync(layer, { withFileTypes: true })) {
      if (e.isDirectory() && existsSync(join(layer, e.name, `${e.name}.md`))) found.set(join(layer, e.name, e.name), true)
    }
  }
  return [...found.keys()].map((base) => loadRunbook(base, root))
}

export function loadRunbook(base, root) {
  const name = base.split('/').pop()
  const data = readJson(`${base}-rb-data.json`)
  const progress = readJson(`${base}-progress.json`)
  const fm = frontmatter(`${base}.md`)
  const rb = { name, base, path: relative(root, dirname(base)), title: fm.title || data?.title || name, status: upper(fm.status), data, progress }
  return { ...rb, ...summarize(rb) }
}

function summarize({ data, progress, status }) {
  const done = progress?.done || {}
  const steps = data ? data.phases.flatMap((p) => p.steps.map((s) => ({ ...s, phase: p }))) : []
  const phaseDone = (id) => steps.filter((s) => s.phase.id === id).every((s) => done[s.id])
  const ready = steps.filter((s) => !done[s.id] && (s.phase.dependsOn || []).every(phaseDone) && (s.dependsOn || []).every((id) => done[id]))
  const doneCount = steps.filter((s) => done[s.id]).length
  const current = steps.find((s) => !done[s.id])?.phase
  const column = RETIRED_STATUSES.has(status) ? 'RETIRED'
    : status === 'DONE' || (steps.length && doneCount === steps.length) ? 'DONE'
    : !data ? 'REFERENCE'
    : progress ? 'IN FLIGHT'
    : 'NOT STARTED'
  const saved = progress?.updatedAt || 0
  const stale = column === 'IN FLIGHT' && Date.now() - saved > STALE_DAYS * 864e5
  return { steps, ready, doneCount, current, column, stale, saved }
}

const mine = (step, who) => Boolean(who) && new RegExp(`\\b${who}\\b`, 'i').test(step.where || '')

// ---------------------------------------------------------------------------
// The board: one column per state, one short card per runbook, in the same
// plain ASCII boxes, widths and colours as `pin list`.
// ---------------------------------------------------------------------------
const GAP = 1
const SLOTS = 4
export const VIEWS = {
  narrow: { min: 22, max: 28, lines: 2, meta: false },
  regular: { min: 34, max: 48, lines: 1, meta: false },
  wide: { min: 48, max: 64, lines: 1, meta: true },
}
export const viewFor = (width) => (width >= 200 ? 'wide' : width >= 140 ? 'regular' : 'narrow')
export const cardWidth = (width, view) => Math.max(VIEWS[view].min, Math.min(VIEWS[view].max, Math.floor((width + GAP) / SLOTS) - GAP))

const cut = (s, n) => (s.length <= n ? s : `${s.slice(0, n - 1)}~`)
const fit = (s, n) => cut(s, n).padEnd(n)

export function wrap(text, width, maxLines = 1) {
  const lines = []
  let cur = ''
  for (let w of String(text).split(' ').filter(Boolean)) {
    while (w.length > width) {
      if (cur) { lines.push(cur); cur = '' }
      lines.push(w.slice(0, width))
      w = w.slice(width)
    }
    if (cur && cur.length + 1 + w.length > width) { lines.push(cur); cur = w } else cur = cur ? `${cur} ${w}` : w
  }
  if (cur) lines.push(cur)
  if (lines.length <= maxLines) return lines.length ? lines : ['']
  return [...lines.slice(0, maxLines - 1), cut(lines.slice(maxLines - 1).join(' '), width)]
}

const SGR = { bold: '1', dim: '2', red: '31', green: '32', yellow: '33', blue: '34', magenta: '35', cyan: '36', grey: '90' }
const COLUMN_COLOR = { 'IN FLIGHT': 'yellow', 'NOT STARTED': 'cyan', REFERENCE: 'magenta', DONE: 'blue', RETIRED: 'grey' }
export const painter = (on) => (style, text) => (on && text ? `\x1b[${[].concat(style).map((k) => SGR[k]).join(';')}m${text}\x1b[0m` : text)

/** The card lines for a runbook: where it stands, what waits on others, your next ready step. */
export function cardFields(rb, who) {
  const step = (s) => `${s.id} ${plain(s.title)}`
  if (rb.column === 'REFERENCE') return { progress: `${rb.status || 'doc'} · no checklist`, waiting_on: '', next: '' }
  if (rb.column === 'DONE' || rb.column === 'RETIRED') return { progress: `${rb.doneCount}/${rb.steps.length} done`, waiting_on: '', next: '' }
  if (rb.column === 'NOT STARTED') {
    return { progress: `${rb.steps.length} steps · ${rb.data.phases.length} phases`, waiting_on: 'not started', next: rb.steps[0] ? `first: ${step(rb.steps[0])}` : '' }
  }
  const byWho = new Map()
  for (const s of rb.ready.filter((s) => !mine(s, who))) byWho.set(s.where || '?', [...(byWho.get(s.where || '?') || []), s.id])
  const phase = rb.current ? `${rb.current.num || rb.current.id} ${plain(rb.current.titleText || rb.current.title)}` : ''
  return {
    progress: `${rb.doneCount}/${rb.steps.length} done · ${phase}`,
    waiting_on: [...byWho].map(([w, ids]) => `${w} ${ids.join(' ')}`).join(' · '),
    next: (() => {
      const ss = rb.ready.filter((s) => mine(s, who))
      return ss.length ? `${ss.length > 1 ? `(+${ss.length - 1}) ` : ''}${step(ss[0])}` : ''
    })(),
  }
}

export function renderCard(rb, { who, color = false, width = 30, lines = 1, meta = false } = {}) {
  const paint = painter(color)
  const f = cardFields(rb, who)
  const frame = COLUMN_COLOR[rb.column]
  const text = width - 4
  const edge = paint(frame, `+${'-'.repeat(width - 2)}+`)
  const bar = paint(frame, '|')
  const row = (cells) => `${bar} ${cells}${' '.repeat(Math.max(0, text - cells.replace(/\x1b\[[\d;]*m/g, '').length))} ${bar}`
  const field = (mark, markStyle, value) => wrap(value || '-', text - 2, lines).map((l, i) =>
    row(`${i === 0 ? paint(markStyle, mark) : ' '} ${value ? l : paint('grey', l)}`))
  const tag = rb.stale ? ' STALE' : ''
  const saved = rb.saved ? `ticks saved ${isoDate(new Date(rb.saved))}` : rb.progress ? 'no ticks saved yet' : ''
  const hasSteps = rb.column === 'IN FLIGHT' || rb.column === 'NOT STARTED'
  return [
    edge,
    row(paint('bold', fit(rb.name, text - tag.length)) + paint(['bold', 'red'], tag)),
    ...wrap(rb.title, text, lines).map((l) => row(l)),
    row(paint('grey', fit(f.progress, text))),
    ...(hasSteps ? [...field('?', 'yellow', f.waiting_on), ...field('>', 'green', f.next)] : []),
    ...(meta ? [row(paint('grey', fit([rb.path, saved].filter(Boolean).join('  '), text)))] : []),
    edge,
  ]
}

export function renderBoard(rbs, { who, width = 80, color = false, view = viewFor(width) } = {}) {
  if (!rbs.length) return 'No runbooks to show.'
  const paint = painter(color)
  const { lines, meta } = VIEWS[view]
  const cw = cardWidth(width, view)
  const cols = COLUMNS.filter((c) => rbs.some((r) => r.column === c)).map((c) => {
    const rs = rbs.filter((r) => r.column === c)
    return { c, count: rs.length, rows: rs.flatMap((r) => renderCard(r, { who, color, width: cw, lines, meta })) }
  })
  const perBand = Math.max(1, Math.floor((width + GAP) / (cw + GAP)))
  const blank = ' '.repeat(cw)
  const out = []
  for (let i = 0; i < cols.length; i += perBand) {
    const band = cols.slice(i, i + perBand)
    const join = (cells) => cells.join(' '.repeat(GAP)).trimEnd()
    out.push(join(band.map(({ c, count }) => { const h = `${c} (${count})`; return paint(['bold', COLUMN_COLOR[c]], h) + ' '.repeat(Math.max(0, cw - h.length)) })))
    out.push(join(band.map(({ c }) => paint(COLUMN_COLOR[c], '='.repeat(cw)))))
    for (let r = 0; r < Math.max(...band.map((c) => c.rows.length)); r++) out.push(join(band.map((c) => c.rows[r] ?? blank)))
    out.push('')
  }
  out.push(`${paint('yellow', '?')} others' ready steps   ${paint('green', '>')} your next step${who ? ` (${who})` : ''}   ${paint(['bold', 'red'], 'STALE')} = no ticks saved in ${STALE_DAYS} days`)
  return out.join('\n')
}

/** Sort: stale first, then most steps ready for you, then name. */
export function listRunbooks(rbs, { all = false, columns = null, who } = {}) {
  const want = columns && columns.map(upper)
  return rbs
    .filter((r) => (want ? want.includes(r.column) : all || !HIDDEN.has(r.column)))
    .sort((a, b) => Number(b.stale) - Number(a.stale) || b.ready.filter((s) => mine(s, who)).length - a.ready.filter((s) => mine(s, who)).length || a.name.localeCompare(b.name))
}

// ---------------------------------------------------------------------------
// Ticks: written to <name>-progress.json, then the checklist HTML is rebuilt
// from it, so the file, the page and the board agree.
// ---------------------------------------------------------------------------
function writeProgress(rb, done, { build = true } = {}) {
  const ids = new Set(rb.steps.map((s) => s.id))
  const sorted = Object.fromEntries(rb.steps.filter((s) => done[s.id]).map((s) => [s.id, true]))
  for (const k of Object.keys(done)) if (!ids.has(k)) throw new Error(`${rb.name} has no step ${k}`)
  writeFileSync(`${rb.base}-progress.json`, `${JSON.stringify({ done: sorted, updatedAt: Date.now() }, null, 2)}\n`)
  if (build) {
    execFileSync('python3', [join(HERE, 'build_runbook.py'), '--data', `${rb.base}-rb-data.json`, '--state', `${rb.base}-progress.json`, '--out', `${rb.base}.html`], { stdio: 'inherit' })
  }
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------
function flags(argv) {
  const pos = []
  const opt = {}
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a.startsWith('--')) {
      const k = a.slice(2)
      if (['all', 'json', 'table', 'color', 'no-color', 'no-build', 'mine'].includes(k)) opt[k] = true
      else opt[k] = argv[++i]
    } else pos.push(a)
  }
  return { pos, opt }
}

function main(argv) {
  const [cmd, ...rest] = argv
  const { pos, opt } = flags(rest)
  const root = repoRoot()
  const who = opt.me || me(root)

  if (!cmd || cmd === 'help' || cmd === '--help') {
    console.log(`runbook ${VERSION}
  list [--all] [--column "IN FLIGHT,DONE"]         the board: a column per state (in flight, not started, reference, done),
       [--table] [--json] [--color | --no-color]   a card per runbook; RETIRED only with --all. Sized to the terminal like pin list.
  next <name> [--mine]                             every ready step of a runbook: id, who, title and what to do
  start <name>                                     create <name>-progress.json: the runbook moves to IN FLIGHT
  tick <name> <step-id>... [--no-build]            record steps as done, then rebuild <name>.html from the ticks
  untick <name> <step-id>... [--no-build]          take ticks back
  --me <name>                                      whose steps are "yours" (default: $RUNBOOK_ME, else the first word of git user.name)`)
    return 0
  }
  if (cmd === 'version') { console.log(`runbook ${VERSION}`); return 0 }

  const rbs = findRunbooks(root)
  const byName = (name) => {
    const rb = rbs.find((r) => r.name === name)
    if (!rb) throw new Error(`no runbook "${name}"; try: runbook list --all`)
    return rb
  }

  if (cmd === 'list') {
    const shown = listRunbooks(rbs, { all: opt.all, columns: opt.column ? opt.column.split(',') : null, who })
    if (opt.json) {
      console.log(JSON.stringify(shown.map((r) => ({ name: r.name, path: r.path, title: r.title, status: r.status, column: r.column, done: r.doneCount, steps: r.steps.length, stale: r.stale, ready: r.ready.map((s) => ({ id: s.id, where: s.where, title: plain(s.title) })) })), null, 2))
      return 0
    }
    if (opt.table) {
      console.log([['name', 'column', 'done', 'stale', 'title'], ...shown.map((r) => [r.name, r.column, r.steps.length ? `${r.doneCount}/${r.steps.length}` : '-', r.stale ? 'STALE' : '', r.title])].map((r) => r.join(' | ')).join('\n'))
      return 0
    }
    const color = opt.color ? true : opt['no-color'] ? false : Boolean(process.stdout.isTTY) && !process.env.NO_COLOR
    console.log(renderBoard(shown, { who, width: process.stdout.columns || 80, color }))
    return 0
  }

  if (cmd === 'next') {
    const rb = byName(pos[0])
    if (!rb.data) { console.log(`${rb.name} has no checklist.`); return 0 }
    const steps = rb.ready.filter((s) => !opt.mine || mine(s, who))
    console.log(`${rb.name} · ${rb.doneCount}/${rb.steps.length} done · ${steps.length} ready${rb.progress ? '' : ' (not started)'}\n`)
    for (const s of steps) console.log(`${s.id.padEnd(6)} [${s.where || '?'}] ${plain(s.title)}\n       ${plain(s.do)}\n`)
    return 0
  }

  if (cmd === 'start' || cmd === 'tick' || cmd === 'untick') {
    const [name, ...ids] = pos
    const rb = byName(name)
    if (!rb.data) throw new Error(`${rb.name} has no checklist to tick`)
    if (cmd !== 'start' && !ids.length) { console.error(`usage: ${cmd} <name> <step-id>...`); return 2 }
    if (cmd === 'start' && rb.progress) { console.log(`${rb.name} is already in flight.`); return 0 }
    const done = { ...(rb.progress?.done || {}) }
    for (const id of ids) cmd === 'tick' ? (done[id] = true) : delete done[id]
    writeProgress(rb, done, { build: !opt['no-build'] })
    const after = loadRunbook(rb.base, root)
    console.log(`${rb.name}: ${after.doneCount}/${after.steps.length} done · next ready: ${after.ready.map((s) => s.id).join(' ') || 'none'}`)
    return 0
  }

  console.error(`unknown command "${cmd}"; try: list, next, start, tick, untick`)
  return 2
}

function isDirectExecution() {
  if (!process.argv[1]) return false
  try {
    return realpathSync(resolve(process.argv[1])) === fileURLToPath(import.meta.url)
  } catch {
    return false
  }
}

if (isDirectExecution()) {
  try {
    process.exitCode = main(process.argv.slice(2))
  } catch (e) {
    console.error(`runbook: ${e.message}`)
    process.exitCode = 1
  }
}
