#!/usr/bin/env bash
set -e

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="$HOME/.dotfiles_backup_$(date +%Y%m%d_%H%M%S)"

echo "=== Setting up Dotfiles from $DOTFILES_DIR ==="

# 1. Ensure GNU Stow is installed
if ! command -v stow &>/dev/null; then
  echo "GNU Stow not found. Attempting installation..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    if command -v brew &>/dev/null; then
      brew install stow
    else
      echo "Error: Homebrew not found. Please install brew and run this script again." >&2
      exit 1
    fi
  elif command -v apt-get &>/dev/null; then
    sudo apt-get update -qq && sudo apt-get install -y stow
  else
    echo "Error: Package manager not recognized. Please install GNU Stow manually." >&2
    exit 1
  fi
fi

# 2. Safely backup conflicting non-symlink files
backup_if_not_symlink() {
  local target="$1"
  if [ -e "$target" ] && [ ! -L "$target" ]; then
    mkdir -p "$BACKUP_DIR"
    echo "Backing up existing non-symlink $target -> $BACKUP_DIR/"
    mv "$target" "$BACKUP_DIR/"
  fi
}

backup_if_not_symlink "$HOME/.zshrc"
backup_if_not_symlink "$HOME/.zsh"
backup_if_not_symlink "$HOME/.config/oh-my-posh"

# 3. Stow common configs into $HOME
echo "Applying common dotfiles via GNU Stow..."
mkdir -p "$HOME/.config"
(cd "$HOME" && stow -d "$DOTFILES_DIR" -t "$HOME" --restow common)

# 4. Fan out Cross-Agent Skills symlinks
echo "Linking cross-agent skills..."
mkdir -p "$HOME/.gemini/config" "$HOME/.claude"

# Backup existing skills if they are real directories (not symlinks)
if [ -d "$HOME/.claude/skills" ] && [ ! -L "$HOME/.claude/skills" ]; then
  mkdir -p "$BACKUP_DIR"
  echo "Backing up existing ~/.claude/skills -> $BACKUP_DIR/"
  mv "$HOME/.claude/skills" "$BACKUP_DIR/"
fi

if [ -d "$HOME/.gemini/config/skills" ] && [ ! -L "$HOME/.gemini/config/skills" ]; then
  mkdir -p "$BACKUP_DIR"
  echo "Backing up existing ~/.gemini/config/skills -> $BACKUP_DIR/"
  mv "$HOME/.gemini/config/skills" "$BACKUP_DIR/"
fi

# Create canonical symlinks
ln -sfn "$DOTFILES_DIR/agent-skills" "$HOME/.claude/skills"
ln -sfn "$DOTFILES_DIR/agent-skills" "$HOME/.gemini/config/skills"

echo "=== Dotfiles setup completed successfully! ==="
if [ -d "$BACKUP_DIR" ]; then
  echo "Note: Replaced original files backed up to: $BACKUP_DIR"
fi
