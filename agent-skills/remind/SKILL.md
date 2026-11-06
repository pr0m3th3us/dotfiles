---
name: remind
description: "Create, look up and close reminders for the user, built from repo context and mirrored to their Google Tasks and Google Calendar. Use when the user asks to be reminded of something, to set a reminder, or names a reminder ID (like MDO-3: pull it up, move it, mark it done). Also /remind list and /remind sync."
---

# remind

A reminder is a short file, `reminders/<ID>.md` at the root of the repo it belongs to, that carries
everything the user needs at the moment it fires. The helper mirrors it to the user's Google Tasks
(always) and Google Calendar (when it has a time), titled `[<ID>] <title> · <machine>`. The ID starts
with the repo's code (its initials), so IDs from every repo can share one Google Tasks list, and the
machine tag (`mac`, `wsl`) says where the file was when it was pushed. When the user names the ID in
any chat, the file is the full brief.

Helper: the `remind` command (or `node <this skill's folder>/scripts/remind.mjs`), run from inside the
repo. `remind help` lists the commands; `show` resolves an ID from any repo on the machine.

## Create a reminder

1. **Settle what and when.** The thing to do, the due date, and a time only if the user gave one (a
   time adds a Calendar event with alerts 30 minutes before and at the start; a date alone makes a Task
   only). A relative date ("Monday") becomes an absolute date; say it back in the reply.
2. **Gather the context.** Search the repo for what bears on it: pins, runbooks, cycles, ADRs, records,
   and this conversation. Done when you can name the source files and say what the user must do, bring
   or decide.
3. **Scaffold:** `remind.mjs new "<title>" --due YYYY-MM-DD [--time HH:MM] [--duration MIN] --source <path> ...`.
   The title is the action, short enough to read on a phone.
4. **Write the body.** `## Summary`: what to do, why now, what to have ready, in at most eight plain
   lines; this is the text Google shows, so it must stand alone. `## Details`: the fuller brief, linking
   each source file by its repo path. A reminder holds only what the user may store in Google and git:
   no passwords, account numbers, card details or student personal data.
5. **Push:** `remind.mjs push <ID>`. Done when it prints `task created` (and `event created` if timed).
   If it says the user is not connected, the file stays and the user runs the one sign-in under Setup;
   that sign-in pushes every waiting reminder itself.
6. Reply with the ID, the date and time, and where it landed. Agents other than Claude pass
   `--agent <name>` on every command, for `updated_by`.

## Use an ID the user names

- **Pull up:** `remind.mjs show <ID>`, then read the files under `sources` for anything the brief lacks.
- **Move or reword:** edit `due`, `time`, `title` or the Summary in the file, then `push <ID>` again;
  it updates the same Task and event.
- **Done or drop:** `done <ID>` or `cancel <ID>`, with `--reason` when the user gave one.
- **List / sync:** `list` shows this repo's open reminders; `sync` first pulls back what the user ticked
  off or deleted in Google Tasks.

## Setup and gotchas

- One-time sign-in per machine, by the user (it opens a browser): `! remind auth`.
  It uses the Desktop OAuth client at `~/.config/remind/client.json`; `auth --client <file>` installs
  another. Tokens live in `~/.config/remind/`, outside every repo.
- An OAuth app left in "Testing" status loses its login after 7 days; the app must be published
  ("In production") in Google Cloud for reminders to keep working.
- Google Keep has no API for personal Google accounts, so Tasks and Calendar are the targets.
- Each repo gets a fixed ID code on first use, kept in `reminders/config.json`; edit it there before the
  first reminder if the initials are unclear.
- Leave new and changed reminder files uncommitted unless the user asks for a commit.
