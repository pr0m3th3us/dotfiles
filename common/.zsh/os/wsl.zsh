# --- WSL / Linux-Specific Configuration -----------------------

# Windows Interop Aliases
alias e='explorer.exe .'
alias pbcopy='clip.exe'
alias pbpaste='powershell.exe -NoProfile -Command Get-Clipboard'

# Linux X11 Clipboard fallbacks if available
if command -v xclip >/dev/null 2>&1; then
  alias copy='xclip -selection clipboard'
  alias paste='xclip -selection clipboard -o'
fi

# Give WezTerm the Linux working directory for tabs and splits via OSC 7.
if [[ -o interactive && -t 1 && $TERM_PROGRAM == WezTerm && -z $TMUX ]]; then
  _wezterm_report_cwd() {
    local LC_ALL=C uri='' byte escaped
    for byte in ${(s::)PWD}; do
      case $byte in
        [a-zA-Z0-9/._~-]) uri+=$byte ;;
        *) printf -v escaped '%%%02X' "'$byte"; uri+=$escaped ;;
      esac
    done
    printf '\033]7;file://%s\033\\' "$uri"
  }

  autoload -Uz add-zsh-hook
  add-zsh-hook precmd _wezterm_report_cwd
fi
