# --- macOS-Specific Configuration -----------------------------

# Homebrew environment
if [ -x "/opt/homebrew/bin/brew" ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x "/usr/local/bin/brew" ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

# Clipboard aliases native to macOS
alias copy='pbcopy'
alias paste='pbpaste'
