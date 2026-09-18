# --- macOS-Specific Configuration -----------------------------

# Clipboard aliases native to macOS
alias copy='pbcopy'
alias paste='pbpaste'

# Keep the Mac awake for the life of an incoming SSH session so idle sleep
# doesn't drop the connection. caffeinate exits on its own when the login
# shell (SSH_CONNECTION's parent) exits, so it never lingers after logout.
if [[ -n "$SSH_CONNECTION" ]] && command -v caffeinate >/dev/null 2>&1; then
  caffeinate -s -w "$PPID" &>/dev/null &
fi
