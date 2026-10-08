# --- Common Aliases -------------------------------------------
alias ll='ls -AlFh --color=auto'
alias al='ls -Alhrt --color=auto'
alias lt='ls -Alhrt --color=auto'
alias gs='git status -sb'
alias gfs='git fetch 2>/dev/null; git status -sb'
alias gl='git log --oneline --graph --decorate -20'
alias c='code .'

# Command normalization across distributions
if command -v batcat >/dev/null 2>&1; then
  alias bat='batcat'
fi

if command -v fdfind >/dev/null 2>&1; then
  alias fd='fdfind'
fi

# Antigravity CLI: the Homebrew cask ships `agy`; other installs ship `antigravity`
if ! command -v agy >/dev/null 2>&1 && command -v antigravity >/dev/null 2>&1; then
  alias agy='antigravity'
fi
