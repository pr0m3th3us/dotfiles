# ==============================================================================
# Dotfiles Modular Zsh Configuration
# Managed by GNU Stow: ~/projects/dotfiles
# ==============================================================================

# 1. Source modular configuration files in order
for file in ~/.zsh/[0-9]*.zsh; do
  [[ -f "$file" ]] && source "$file"
done

# 2. Platform-specific overrides (Darwin / WSL / Linux)
case "$(uname -s)" in
  Darwin)
    [[ -f ~/.zsh/os/mac.zsh ]] && source ~/.zsh/os/mac.zsh
    ;;
  Linux)
    if [[ -n "$WSL_DISTRO_NAME" ]] || grep -qi microsoft /proc/version 2>/dev/null; then
      [[ -f ~/.zsh/os/wsl.zsh ]] && source ~/.zsh/os/wsl.zsh
    else
      [[ -f ~/.zsh/os/linux.zsh ]] && source ~/.zsh/os/linux.zsh
    fi
    ;;
esac

# 3. Host-specific / untracked local overrides (secrets, API keys, tokens)
[[ -f ~/.zshrc.local ]] && source ~/.zshrc.local
