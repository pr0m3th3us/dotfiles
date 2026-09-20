# --- Dynamic Terminal Tab Title --------------------------------
# Sets the tab title via OSC escape codes instead of relying on a static
# profile name. Compact format tailored for narrow tabs and rich prompts.
#
# Terminal requirements:
# In Windows Terminal Profile Settings -> WSL Ubuntu (or general profile):
#   - Clear the "Tab title" field (leave it blank / use reset arrow).
#   - Ensure "Suppress title changes" is Off.

# Guard: only run in interactive terminals that support OSC sequences
[[ -o interactive ]] && [[ -t 1 ]] && [[ "$TERM" != "dumb" ]] || return 0

_tab_title() {
  print -Pn "\e]0;$1\a"
}

# Idle: show only the current leaf directory or '~'
_tab_title_idle() {
  if [[ "$PWD" == "$HOME" ]]; then
    _tab_title "~"
  else
    _tab_title "${PWD:t}"
  fi
}

# Running: show the command, truncated for narrow tabs
_tab_title_running() {
  # Take the first line (in case of multiline commands)
  local cmd="${1%%$'\n'*}"
  # Truncate if too long (max 28 chars)
  if (( ${#cmd} > 28 )); then
    cmd="${cmd[1,25]}..."
  fi
  _tab_title "$cmd"
}

autoload -Uz add-zsh-hook
add-zsh-hook precmd _tab_title_idle
add-zsh-hook preexec _tab_title_running

# SSH wrapper: keep "ssh: <host>" visible for the entire duration of the session
ssh() {
  local target="${@[-1]}"
  _tab_title "ssh: ${target#*@}"
  command ssh "$@"
}
