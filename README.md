# Dotfiles (Symlink Farm)

A modular, cross-platform dotfile repository using **GNU Stow** for configuration management and shared cross-agent skills between macOS and Linux/WSL.

---

## 📂 Repository Structure

```text
~/projects/dotfiles/
├── install.sh                  # Bootstrap script for macOS & Linux/WSL
├── README.md                   # Documentation
├── agent-skills/               # Canonical source for AI Agent Skills
│   └── runbook/
│       └── SKILL.md
├── common/                     # Stowed package linked directly to $HOME
│   ├── .config/
│   │   └── oh-my-posh/         # OMP themes (system-omp, claude-omp, agy-omp)
│   ├── .zshrc                  # Modular Zsh entrypoint
│   └── .zsh/
│       ├── 00-env.zsh          # PATH, pnpm, mise, zoxide
│       ├── 10-history.zsh      # History options & keybindings
│       ├── 20-completion.zsh   # Compinit, zstyle rules, fzf
│       ├── 30-plugins.zsh      # Autosuggestions & syntax highlighting
│       ├── 40-aliases.zsh      # Common aliases & binary normalization
│       ├── 50-prompt.zsh       # Oh My Posh initialization
│       └── os/
│           ├── mac.zsh         # macOS-specific environment & aliases
│           └── wsl.zsh         # WSL-specific clipboard & interop
└── os/                         # (Optional) OS-specific Stow packages
    ├── mac/
    └── wsl/
```

---

## 🚀 Quick Setup

### On a new machine (macOS or WSL):

```bash
cd ~/projects
git clone <your-dotfiles-repo-url> dotfiles
cd dotfiles
./install.sh
```

The installer will:
1. Automatically install `stow` (via `brew` or `apt`).
2. Back up any conflicting existing configuration files.
3. Link `common` package into `$HOME` via GNU Stow.
4. Fan out symlinks for `agent-skills/` to both `~/.claude/skills` and `~/.gemini/config/skills`.

---

## 🧠 AI Agent Skills (Antigravity & Claude Code)

All skills reside in `agent-skills/<skill-name>/SKILL.md`.

* **Claude Code** looks up: `~/.claude/skills` $\rightarrow$ `agent-skills/`
* **Antigravity / Gemini CLI** looks up: `~/.gemini/config/skills` $\rightarrow$ `agent-skills/`

**Benefit**: Any skill created, edited, or updated by either agent or yourself is instantly shared across all tools and tracked in Git.

---

## ⚙️ Adding New Configs to Dotfiles

### Adding an app inside `~/.config`:
1. Move the configuration folder into `common/.config/<app>`:
   ```bash
   mkdir -p ~/projects/dotfiles/common/.config/git
   mv ~/.config/git/config ~/projects/dotfiles/common/.config/git/
   ```
2. Re-stow:
   ```bash
   stow --dir=~/projects/dotfiles --target=$HOME --restow common
   ```

### Machine-Specific Untracked Secrets:
Create `~/.zshrc.local` for machine-local tokens, API keys, or work-specific paths. It is automatically sourced at the end of `.zshrc` and ignored by Git.
