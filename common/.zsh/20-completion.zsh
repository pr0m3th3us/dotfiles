# Clean up dangling WSL Docker Desktop completion symlinks if Docker is stopped
if [ -L /usr/share/zsh/vendor-completions/_docker ] && [ ! -e /usr/share/zsh/vendor-completions/_docker ]; then
  rm -f /usr/share/zsh/vendor-completions/_docker 2>/dev/null || true
fi

autoload -Uz compinit
# Cache compdump check for faster startup
if [ -n "$(find ~/.zcompdump -mtime -1 2>/dev/null)" ]; then
  compinit -C -d ~/.zcompdump
else
  compinit -u -d ~/.zcompdump
fi

zstyle ':completion:*' auto-description 'specify: %d'
zstyle ':completion:*' completer _expand _complete _correct _approximate
zstyle ':completion:*' format 'Completing %d'
zstyle ':completion:*' group-name ''
zstyle ':completion:*' menu select=long

# Colorize completion lists
if command -v dircolors >/dev/null 2>&1; then
  eval "$(dircolors -b)"
  zstyle ':completion:*:default' list-colors ${(s.:.)LS_COLORS}
fi
zstyle ':completion:*' list-colors ''
zstyle ':completion:*' list-prompt %SAt %p: Hit TAB for more, or the character to insert%s
zstyle ':completion:*' matcher-list '' 'm:{a-z}={A-Za-z}' 'r:|[._-]=* r:|=* l:|=*'
zstyle ':completion:*' select-prompt %SScrolling active: current selection at %p%s
zstyle ':completion:*' use-compctl false
zstyle ':completion:*' verbose true

zstyle ':completion:*:*:kill:*:processes' list-colors '=(#b) #([0-9]#)*=0=01;31'
zstyle ':completion:*:kill:*' command 'ps -u $USER -o pid,%cpu,tty,cputime,cmd'

# fzf keybindings and completion
if command -v fzf >/dev/null 2>&1; then
  if fzf --zsh >/dev/null 2>&1; then
    eval "$(fzf --zsh)"
  else
    [ -f /usr/share/doc/fzf/examples/key-bindings.zsh ] && source /usr/share/doc/fzf/examples/key-bindings.zsh
    [ -f /usr/share/doc/fzf/examples/completion.zsh ] && source /usr/share/doc/fzf/examples/completion.zsh
  fi
fi
