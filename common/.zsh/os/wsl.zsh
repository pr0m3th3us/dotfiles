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
