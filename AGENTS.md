# Dotfiles: rules for AI agents

Shared rules for every agent working in this repo (Claude via `CLAUDE.md`, Gemini/Antigravity via `GEMINI.md`). Read this file before changing anything.

## What this repo is

- `common/` is a **GNU Stow package**. `install.sh` links its contents into `$HOME`, so `~/.zshrc`, `~/.zsh` and `~/.config/oh-my-posh` are symlinks back into this repo. Editing either path edits the same tracked file; there are no copies.
- `agent-skills/` is symlinked as a whole to `~/.claude/skills` and `~/.gemini/config/skills`.
- `deps.list` is the **single list** of binaries, packages and fonts the repo needs. `install.sh` reads it to check, install and report.
- `install.sh` is the only bootstrap: dependency preflight → consent → install → link preflight → consent → stow → agent statusLine wiring.

## Rule 1: every dependency is recorded in `deps.list`

Any change that makes the repo need something that isn't guaranteed to be on a fresh machine (a command, package, font, Python module or file path) **must add or update its row in `deps.list` in the same commit**.

- Applies to new dotfile *types* (a new app under `common/.config/`), new tools called from zsh modules or scripts, and new agent-skill scripts.
- Fill in `required_by` with the repo paths that use it. When you add another user of an existing dependency, append it to that row's `required_by`.
- Mark it `required` only if the config breaks without it. If the config already skips it when missing (`command -v … && …`), mark it `optional`.
- Give an install method for brew, apt, or a fallback (`sh:`, `nerdfont:`, `manual:`). Check `sh:` commands against the tool's official install docs; don't invent URLs.
- When you remove the last user of a dependency, remove its row or trim `required_by`.
- Before committing, run `./install.sh --check`. It is read-only. Confirm the list parses and your dependency shows up with the right status.

## Rule 2: installer safety

- `install.sh` must change nothing before the user consents. `--check` must stay fully read-only.
- Never use `stow --adopt`: it overwrites repo files with whatever is on the machine.
- Existing files are moved to `~/.dotfiles_backup_<timestamp>/`, never deleted.
- Keep `install.sh` compatible with macOS's bash 3.2: no associative arrays, no `mapfile`/`readarray`, no `${var,,}`.
- Installs must be idempotent: check first, skip what's present.

## Rule 3: configs fail soft

Shell modules and scripts must not break a shell when an optional tool is missing. Guard with `command -v` or file checks, as the existing `common/.zsh/*.zsh` files do.

## Housekeeping

- Glyph-heavy JSON (oh-my-posh themes) should be edited with a script that preserves Nerd Font code points, not by retyping glyphs.
- Update `README.md` when the layout, install flow or `deps.list` format changes.
