# --- Dynamic Terminal Tab Title --------------------------------
# Sets the tab title via OSC escape codes instead of relying on a static
# profile name. Compact format tailored for narrow tabs and rich prompts.
#
# Terminal requirements:
#
# Windows Terminal (WSL profiles):
#   - Clear the "Tab title" field (leave it blank / use reset arrow).
#   - Profile -> Additional settings -> Advanced -> "Suppress application
#     title changes" must be Off. WSL auto-registers a Fragments extension
#     (%LOCALAPPDATA%\Microsoft\Windows Terminal\Fragments\Microsoft.WSL\
#     <profile-guid>.json) that sets suppressApplicationTitle: true by
#     default for the distro's profile. That default isn't visible on the
#     main profile page (only the "Tab title" field is) and silently
#     swallows every OSC title write, so it must be overridden explicitly
#     per profile in settings.json with "suppressApplicationTitle": false.
#     Symptom when suppressed: title stays fixed on the profile name (e.g.
#     "Ubuntu-24.04") and a manually-sent, well-formed OSC 0 sequence
#     produces no visible change and no garbled output (WT parses it, then
#     discards it) -- that silent-discard behavior is the tell, as opposed
#     to a malformed escape (e.g. printf's "\e" isn't a real ESC byte in
#     zsh's builtin printf, only in bash/coreutils) which prints literal
#     garbage text instead.
#
# macOS Terminal.app:
#   - Preferences/Settings -> Profiles -> <profile> -> Window tab -> under
#     "Title", uncheck all boxes (Active Process Name, Shell, Working
#     Directory, TTY, Window Size, etc.). If any are checked, Terminal.app
#     composes its own title from those (e.g. "<path> - <folder> - zsh")
#     and ignores OSC title writes entirely.

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
