# --- History & Shell Options ----------------------------------
HISTFILE=~/.zsh_history
HISTSIZE=50000
SAVEHIST=50000
setopt SHARE_HISTORY HIST_IGNORE_ALL_DUPS HIST_REDUCE_BLANKS
setopt AUTO_CD INTERACTIVE_COMMENTS

# Use emacs keybindings even if EDITOR is set to vi
bindkey -e

# Disable unwanted terminal mouse tracking sequences in some shells
precmd() {
  print -n '\e[?1000l\e[?1002l\e[?1003l\e[?1006l'
}
