#!/usr/bin/env bash
# ==============================================================================
# Seeds ~/.codex/config.toml with this repo's Codex CLI defaults.
#
#   codex-config.sh --check   print what would be added; exit 10 if anything, 0 if not
#   codex-config.sh --apply   add it (the old file is copied to $BACKUP_DIR first)
#
# Why a script and not a stowed file: Codex rewrites config.toml itself (project
# trust, model notices, /statusline choices), so a symlink into this repo would
# get dirty and a copy would clobber the machine's own settings.
#
# Seed-only: a key that is already set is never changed, so a /statusline choice
# made on one machine survives re-runs. A fresh machine gets everything.
# Codex has no status line command hook (unlike Claude Code and Antigravity), so
# oh-my-posh cannot draw it; the built-in item list below is the equivalent.
# Item names are not in OpenAI's docs. Checked against codex 0.164.0: an unknown
# name (token-counter, git-status) is ignored with a startup warning.
#
# Must stay bash 3.2 compatible (macOS /bin/bash).
# ==============================================================================
set -o pipefail

CONFIG="${CODEX_CONFIG:-$HOME/.codex/config.toml}"
PROJECTS_DIR="${CODEX_PROJECTS_DIR:-$HOME/projects}"
MODE="${1:---check}"

STATUS_LINE='["model-with-reasoning", "project-name", "git-branch", "branch-changes", "pull-request-number", "context-used", "total-input-tokens", "total-output-tokens", "five-hour-limit", "weekly-limit", "estimated-thread-cost", "run-state"]'

case "$MODE" in --check | --apply) ;; *) echo "usage: $0 --check | --apply" >&2; exit 2 ;; esac

WORK="$(mktemp)"
trap 'rm -f "$WORK" "$WORK.new"' EXIT
[ -f "$CONFIG" ] && cat "$CONFIG" >"$WORK"
ORIG="$(mktemp)"
trap 'rm -f "$WORK" "$WORK.new" "$ORIG"' EXIT
cat "$WORK" >"$ORIG"
ADDED=""

# Top-level keys must come before the first [table], so new ones go on top.
ensure_top() {
  local key="$1" line="$2"
  if awk -v k="$key" '/^\[/ { exit 1 } $0 ~ "^[[:space:]]*" k "[[:space:]]*=" { found = 1 } END { exit !found }' "$WORK"; then
    return 0
  fi
  { printf '%s\n' "$line"; cat "$WORK"; } >"$WORK.new" && cat "$WORK.new" >"$WORK"
  ADDED="$ADDED  + $line\n"
}

# Key inside [tui]: after the header if the table exists, else a new table at the end.
ensure_tui() {
  local key="$1" line="$2"
  if awk -v k="$key" '/^\[/ { in_tui = ($0 == "[tui]") } in_tui && $0 ~ "^[[:space:]]*" k "[[:space:]]*=" { found = 1 } END { exit !found }' "$WORK"; then
    return 0
  fi
  if grep -qx '\[tui\]' "$WORK"; then
    awk -v l="$line" '{ print } $0 == "[tui]" { print l }' "$WORK" >"$WORK.new"
  else
    { cat "$WORK"; [ -s "$WORK" ] && printf '\n'; printf '[tui]\n%s\n' "$line"; } >"$WORK.new"
  fi
  cat "$WORK.new" >"$WORK"
  ADDED="$ADDED  + [tui] $line\n"
}

ensure_trust() {
  local header="[projects.\"$1\"]"
  grep -qxF "$header" "$WORK" && return 0
  { cat "$WORK"; [ -s "$WORK" ] && printf '\n'; printf '%s\ntrust_level = "trusted"\n' "$header"; } >"$WORK.new" && cat "$WORK.new" >"$WORK"
  ADDED="$ADDED  + trust $1\n"
}

# CLAUDE.md is the fallback entry file for repos without an AGENTS.md (atpoure, sokal-home).
ensure_top project_doc_fallback_filenames 'project_doc_fallback_filenames = ["CLAUDE.md", "GEMINI.md"]'
ensure_top model_reasoning_effort 'model_reasoning_effort = "high"'
ensure_tui status_line "status_line = $STATUS_LINE"
ensure_tui status_line_use_colors 'status_line_use_colors = true'

# Trust each repo cloned here so the first run in it does not stop to ask.
if [ -d "$PROJECTS_DIR" ]; then
  for repo in "$PROJECTS_DIR"/*/; do
    [ -e "${repo%/}/.git" ] || continue
    ensure_trust "${repo%/}"
  done
fi

if cmp -s "$ORIG" "$WORK"; then
  [ "$MODE" = "--check" ] && echo "codex config is up to date"
  exit 0
fi

if [ "$MODE" = "--check" ]; then
  printf '%b' "$ADDED"
  exit 10
fi

mkdir -p "$(dirname "$CONFIG")"
if [ -f "$CONFIG" ] && [ -n "$BACKUP_DIR" ]; then
  mkdir -p "$BACKUP_DIR/.codex"
  cp -p "$CONFIG" "$BACKUP_DIR/.codex/config.toml"
fi
cat "$WORK" >"$CONFIG"
chmod 600 "$CONFIG"
printf '%b' "$ADDED"
