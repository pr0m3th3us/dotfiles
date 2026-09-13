# --- Common Aliases -------------------------------------------
alias ll='ls -AlFh --color=auto'
alias lt='ls -AlFhrt --color=auto'
alias gs='git status -sb'
alias gl='git log --oneline --graph --decorate -20'
alias dc='docker compose'
alias c='code .'
alias agy='antigravity'

# Command normalization across distributions
if command -v batcat >/dev/null 2>&1; then
  alias bat='batcat'
fi

if command -v fdfind >/dev/null 2>&1; then
  alias fd='fdfind'
fi
