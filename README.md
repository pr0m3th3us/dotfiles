# Dotfiles (Symlink Farm)

A modular, cross-platform dotfile repository using **GNU Stow** for configuration management and shared cross-agent skills between macOS and Linux/WSL.

---

## 📂 Repository Structure

```text
~/projects/dotfiles/
├── install.sh                  # Consent-first bootstrap for macOS & Linux/WSL
├── deps.list                   # Single list of every dependency (read by install.sh)
├── AGENTS.md                   # Rules for AI agents (CLAUDE.md / GEMINI.md point here)
├── README.md                   # Documentation
├── agent-skills/               # Canonical source for AI Agent Skills
│   └── runbook/
│       └── SKILL.md
└── common/                     # Stowed package linked directly to $HOME
    ├── .config/
    │   └── oh-my-posh/         # OMP themes (system/claude/agy) + claude-statusline.sh
    ├── .zshrc                  # Modular Zsh entrypoint
    └── .zsh/
        ├── 00-env.zsh          # Homebrew, PATH, pnpm, mise, zoxide
        ├── 10-history.zsh      # History options & keybindings
        ├── 20-completion.zsh   # Compinit, zstyle rules, fzf
        ├── 30-plugins.zsh      # Autosuggestions & syntax highlighting
        ├── 40-aliases.zsh      # Common aliases & binary normalization
        ├── 45-functions.zsh    # Shell functions (restow)
        ├── 50-prompt.zsh       # Oh My Posh initialization
        └── os/
            ├── mac.zsh         # macOS-specific environment & aliases
            └── wsl.zsh         # WSL-specific clipboard & interop
```

---

## 🚀 Quick Setup

### On a new machine (macOS or WSL)

```bash
cd ~/projects
git clone <your-dotfiles-repo-url> dotfiles
cd dotfiles
./install.sh
```

Prerequisites: `bash`, `sudo` (Linux/WSL), and [Homebrew](https://brew.sh) on macOS.

The installer asks before every change and is safe to re-run:

1. **Dependency check (read-only).** Reads `deps.list`, checks each entry for this platform, and prints what is missing, who needs it, and the exact install command.
2. **Consent:** `[a]ll missing / [r]equired only / [N]o`. `N` with required dependencies missing exits with nothing changed.
3. **Install** via `apt`/`brew`, scripted installers, or the Nerd Font installer (on WSL the font goes onto the Windows host). Everything is re-checked; if a required dependency is still missing it stops before touching `$HOME`.
4. **Link check (read-only).** Shows each item as ✔ linked, `+` new link, or `!` existing and not ours. Cross-checked with `stow -n` (a dry run). If an existing shell rc (e.g. `~/.zshrc`) is marked `!`, its active settings are printed: nothing in it is carried over, so move what you need into the repo (every machine) or `~/.zshrc.local` (this machine only) first.
5. **Consent**, then any `!` items are **moved** to `~/.dotfiles_backup_<timestamp>/` (never deleted), `stow --restow common` links the package, and `agent-skills/` is linked to `~/.claude/skills` and `~/.gemini/config/skills`.
6. **Agent status lines.** With consent, sets only the `statusLine` key in `~/.claude/settings.json` and `~/.gemini/antigravity-cli/settings.json` (backed up first).

```bash
./install.sh --check   # read-only report; exit 1 if something required is missing
./install.sh --yes     # non-interactive: install all missing deps and accept every prompt
```

### Terminal font

The prompt and agent status lines need a Nerd Font. Either of these works; the installer installs CaskaydiaCove if neither is present:

* **CaskaydiaCove Nerd Font Mono** (`oh-my-posh font install CascadiaCode`)
* **GoogleSansCode Nerd Font Mono** (`oh-my-posh font install GoogleSansCode`)

Always pick the **Mono** variant (shown as `… NFM` in font pickers). The plain `NF` variant draws icons wider than one cell and `NFP` (Propo) is proportional; both make powerline caps and icons misalign, most visibly in macOS Terminal.app. Mono keeps icons small but aligned.

### What GNU Stow does with existing files

Stow never overwrites silently: a real file or a foreign symlink where it wants a link makes it abort everything. A real *directory* is different: stow quietly links our files *inside* it, mixing them with yours. That is why `install.sh` backs up the whole existing entry first. `~/.config` and `~/.local` are treated as shared containers: only the entries inside them are linked.

---

## 📦 Dependencies (`deps.list`)

One row per dependency: `id | tier | check | brew | apt | fallback | required_by`. The header of `deps.list` documents every field. **Whenever you add a config or script that needs a new tool, add its row in the same commit** (see `AGENTS.md`), then confirm with `./install.sh --check`.

---

## 🧠 AI Agent Skills (Antigravity & Claude Code)

All skills reside in `agent-skills/<skill-name>/SKILL.md`.

* **Claude Code** looks up: `~/.claude/skills` $\rightarrow$ `agent-skills/`
* **Antigravity / Gemini CLI** looks up: `~/.gemini/config/skills` $\rightarrow$ `agent-skills/`

**Benefit**: Any skill created, edited, or updated by either agent or yourself is instantly shared across all tools and tracked in Git.

---

## ⚙️ Adding New Configs to Dotfiles

### Adding an app inside `~/.config`

1. Move the configuration folder into `common/.config/<app>`:

   ```bash
   mkdir -p ~/projects/dotfiles/common/.config/git
   mv ~/.config/git/config ~/projects/dotfiles/common/.config/git/
   ```

2. Add any tools the config needs to `deps.list`.

3. Re-run the installer (it backs up the old path and links the new one):

   ```bash
   ./install.sh
   ```

   If nothing needs backing up, `restow` is the quick equivalent for the linking step (`stow -d ~/projects/dotfiles -t ~ --restow common`; `restow -d <dir>` for another clone). Editing an already-linked file needs neither.

### Runtimes (Python, Java, …)

Use `mise` (activated in `00-env.zsh`) rather than per-language managers like pyenv or SDKMAN, e.g. `mise use -g python@3.12 java@temurin-21`.

### Multiple users on one machine

Each user keeps their own clone at `~/projects/dotfiles` and runs `./install.sh` once; sync with `git pull` like any other environment. On macOS, Homebrew must have a single owner: other users run it as that owner rather than with their own account.

### Machine-Specific Untracked Secrets

Create `~/.zshrc.local` for machine-local tokens, API keys, or work-specific paths. It is automatically sourced at the end of `.zshrc` and ignored by Git.
