# --- Environment & Paths --------------------------------------

# Local binary directory
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac

# pnpm setup
export PNPM_HOME="$HOME/.local/share/pnpm"
case ":$PATH:" in
  *":$PNPM_HOME/bin:"*) ;;
  *) export PATH="$PNPM_HOME/bin:$PATH" ;;
esac

# mise version manager
if [ -x "$HOME/.local/bin/mise" ]; then
  eval "$($HOME/.local/bin/mise activate zsh)"
elif command -v mise >/dev/null 2>&1; then
  eval "$(mise activate zsh)"
fi

# zoxide directory jumper
if command -v zoxide >/dev/null 2>&1; then
  eval "$(zoxide init zsh)"
fi
