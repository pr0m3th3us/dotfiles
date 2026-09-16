#!/usr/bin/env bash
# ==============================================================================
# Dotfiles installer (macOS, Linux, WSL)
#
#   ./install.sh           dependency check -> consent -> install ->
#                          link check -> consent -> stow -> agent wiring
#   ./install.sh --check   read-only report; exit 1 if a required dep is missing
#   ./install.sh --yes     answer yes to every prompt (installs all missing deps)
#
# Dependencies come from deps.list. Nothing changes before you consent, existing
# files are moved to ~/.dotfiles_backup_<timestamp>/ (never deleted), and every
# step is safe to re-run. Must stay bash 3.2 compatible (macOS /bin/bash).
# ==============================================================================
set -o pipefail

DOTFILES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPS_FILE="$DOTFILES_DIR/deps.list"
PACKAGE="common"
BACKUP_DIR="$HOME/.dotfiles_backup_$(date +%Y%m%d_%H%M%S)"

# Directories stow must never fold into a single symlink: they are shared with
# other programs, so we link the entries inside them instead.
STOW_CONTAINERS=".config .local .local/share .local/bin"

MODE="install"
ASSUME_YES=0

usage() {
  sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
  case "$arg" in
    --check) MODE="check" ;;
    -y | --yes) ASSUME_YES=1 ;;
    -h | --help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

# Installers such as oh-my-posh and mise drop binaries here.
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) export PATH="$HOME/.local/bin:$PATH" ;;
esac

# --- Output helpers -----------------------------------------------------------
if [ -t 1 ]; then
  C_BOLD=$'\033[1m' C_DIM=$'\033[2m' C_RED=$'\033[31m' C_GREEN=$'\033[32m'
  C_YELLOW=$'\033[33m' C_BLUE=$'\033[34m' C_RESET=$'\033[0m'
else
  C_BOLD="" C_DIM="" C_RED="" C_GREEN="" C_YELLOW="" C_BLUE="" C_RESET=""
fi

section() { printf '\n%s== %s ==%s\n' "$C_BOLD$C_BLUE" "$1" "$C_RESET"; }
info() { printf '%s\n' "$*"; }
warn() { printf '%sWARN:%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
die() { printf '%sERROR:%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; exit 1; }

# ask "<prompt>" <default answer when --yes>
# Reads from /dev/tty so it also works when stdin is a pipe.
ask() {
  local prompt="$1" yes_answer="$2" reply
  if [ "$ASSUME_YES" -eq 1 ]; then
    printf '%s %s(--yes: %s)%s\n' "$prompt" "$C_DIM" "$yes_answer" "$C_RESET" >&2
    REPLY_VALUE="$yes_answer"
    return 0
  fi
  if ! { : </dev/tty; } 2>/dev/null; then
    die "No terminal to ask for consent. Re-run interactively or pass --yes."
  fi
  printf '%s ' "$prompt" >/dev/tty
  IFS= read -r reply </dev/tty || reply=""
  REPLY_VALUE="$reply"
}

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

expand_home() {
  # shellcheck disable=SC2088 # matching a literal "~/" prefix on purpose
  case "$1" in
    "~") printf '%s' "$HOME" ;;
    "~/"*) printf '%s/%s' "$HOME" "${1#\~/}" ;;
    *) printf '%s' "$1" ;;
  esac
}

# --- Platform -----------------------------------------------------------------
detect_platform() {
  case "$(uname -s)" in
    Darwin) OS="mac" ;;
    Linux)
      if [ -n "${WSL_DISTRO_NAME:-}" ] || grep -qi microsoft /proc/version 2>/dev/null; then
        OS="wsl"
      else
        OS="linux"
      fi
      ;;
    *) die "Unsupported platform: $(uname -s)" ;;
  esac

  PKG="none"
  if [ "$OS" = "mac" ]; then
    command -v brew >/dev/null 2>&1 && PKG="brew"
  elif command -v apt-get >/dev/null 2>&1; then
    PKG="apt"
  elif command -v brew >/dev/null 2>&1; then
    PKG="brew"
  fi
}

# Does a deps.list id suffix (@mac, @linux, @wsl, @unix) apply here?
platform_matches() {
  case "$1" in
    *@mac) [ "$OS" = "mac" ] ;;
    *@linux) [ "$OS" = "linux" ] ;;
    *@wsl) [ "$OS" = "wsl" ] ;;
    *@unix) [ "$OS" = "linux" ] || [ "$OS" = "wsl" ] ;;
    *@*) return 1 ;;
    *) return 0 ;;
  esac
}

# --- deps.list parsing ----------------------------------------------------------
D_ID=() D_TIER=() D_CHECK=() D_BREW=() D_APT=() D_FALLBACK=() D_REQBY=()

load_deps() {
  [ -f "$DEPS_FILE" ] || die "Dependency list not found: $DEPS_FILE"
  local line n=0 id tier check brew apt fallback reqby
  while IFS= read -r line || [ -n "$line" ]; do
    n=$((n + 1))
    case "$(trim "$line")" in "" | "#"*) continue ;; esac
    IFS='|' read -r id tier check brew apt fallback reqby <<<"$line"
    id="$(trim "$id")" tier="$(trim "$tier")" check="$(trim "$check")"
    brew="$(trim "$brew")" apt="$(trim "$apt")" fallback="$(trim "$fallback")"
    reqby="$(trim "$reqby")"

    [ -n "$id" ] && [ -n "$reqby" ] || die "deps.list:$n: expected 7 '|'-separated fields"
    case "$tier" in required | optional) ;; *) die "deps.list:$n: tier must be required|optional, got '$tier'" ;; esac
    case "$check" in cmd:?* | file:?* | py:?* | font:?*) ;; *) die "deps.list:$n: bad check '$check'" ;; esac
    case "$brew" in - | brew:?* | cask:?*) ;; *) die "deps.list:$n: bad brew field '$brew'" ;; esac
    case "$apt" in - | apt:?*) ;; *) die "deps.list:$n: bad apt field '$apt'" ;; esac
    case "$fallback" in - | sh:?* | nerdfont:?* | manual:?*) ;; *) die "deps.list:$n: bad fallback '$fallback'" ;; esac

    platform_matches "$id" || continue
    D_ID+=("${id%@*}") D_TIER+=("$tier") D_CHECK+=("$check") D_BREW+=("$brew")
    D_APT+=("$apt") D_FALLBACK+=("$fallback") D_REQBY+=("$reqby")
  done <"$DEPS_FILE"
}

# --- Checks -------------------------------------------------------------------
windows_font_dirs() {
  local localappdata
  printf '%s\n' "/mnt/c/Windows/Fonts"
  localappdata="$(cd /mnt/c 2>/dev/null && cmd.exe /c 'echo %LOCALAPPDATA%' </dev/null 2>/dev/null | tr -d '\r')"
  if [ -n "$localappdata" ] && command -v wslpath >/dev/null 2>&1; then
    printf '%s\n' "$(wslpath -u "$localappdata" 2>/dev/null)/Microsoft/Windows/Fonts"
  fi
}

font_present() {
  local pattern="$1.*nerd" dir
  case "$OS" in
    mac)
      for dir in "$HOME/Library/Fonts" "/Library/Fonts"; do
        grep -qi "$pattern" <<<"$(ls "$dir" 2>/dev/null)" && return 0
      done
      ;;
    linux)
      command -v fc-list >/dev/null 2>&1 && grep -qi "$pattern" <<<"$(fc-list 2>/dev/null)" && return 0
      ;;
    wsl)
      # The terminal (Windows Terminal) renders glyphs, so the font must be on Windows.
      while IFS= read -r dir; do
        [ -n "$dir" ] && grep -qi "$pattern" <<<"$(ls "$dir" 2>/dev/null)" && return 0
      done <<EOF
$(windows_font_dirs)
EOF
      ;;
  esac
  return 1
}

dep_present() {
  local check="$1" kind value item
  kind="${check%%:*}" value="${check#*:}"
  case "$kind" in
    cmd | file)
      local IFS=','
      for item in $value; do
        item="$(trim "$item")"
        if [ "$kind" = "cmd" ]; then
          command -v "$item" >/dev/null 2>&1 && return 0
        else
          [ -e "$(expand_home "$item")" ] && return 0
        fi
      done
      return 1
      ;;
    py) command -v python3 >/dev/null 2>&1 && python3 -c "import $value" >/dev/null 2>&1 ;;
    font) font_present "$value" ;;
  esac
}

# Which install method applies on this machine: brew:/cask:/apt:/sh:/nerdfont:/manual:/none
resolve_method() {
  local i="$1"
  if [ "$PKG" = "brew" ] && [ "${D_BREW[$i]}" != "-" ]; then
    case "${D_BREW[$i]}" in
      cask:*) [ "$OS" = "mac" ] && { printf '%s' "${D_BREW[$i]}"; return; } ;;
      *) printf '%s' "${D_BREW[$i]}"; return ;;
    esac
  fi
  if [ "$PKG" = "apt" ] && [ "${D_APT[$i]}" != "-" ]; then
    printf '%s' "${D_APT[$i]}"
    return
  fi
  if [ "${D_FALLBACK[$i]}" != "-" ]; then
    printf '%s' "${D_FALLBACK[$i]}"
    return
  fi
  printf 'none'
}

describe_method() {
  case "$1" in
    brew:*) printf 'brew install %s' "${1#brew:}" ;;
    cask:*) printf 'brew install --cask %s' "${1#cask:}" ;;
    apt:*) printf 'sudo apt-get install -y %s' "${1#apt:}" ;;
    sh:*) printf '%s' "${1#sh:}" ;;
    nerdfont:*)
      case "$OS" in
        wsl) printf 'install %s Nerd Font on the Windows host (per-user)' "${1#nerdfont:}" ;;
        *) printf 'oh-my-posh font install %s' "${1#nerdfont:}" ;;
      esac
      ;;
    manual:*) printf 'manual: %s' "${1#manual:}" ;;
    none) printf 'no install method for this platform' ;;
  esac
}

# Indices of missing deps: auto-installable (required/optional) vs manual-only.
MISSING_REQ="" MISSING_OPT="" MANUAL_REQ="" MANUAL_OPT=""

dependency_preflight() {
  section "Dependencies ($OS, package manager: $PKG)"
  MISSING_REQ="" MISSING_OPT="" MANUAL_REQ="" MANUAL_OPT=""
  local i method mark
  for i in "${!D_ID[@]}"; do
    if dep_present "${D_CHECK[$i]}"; then
      printf '  %s✔%s %-9s %s\n' "$C_GREEN" "$C_RESET" "${D_TIER[$i]}" "${D_ID[$i]}"
      continue
    fi
    method="$(resolve_method "$i")"
    if [ "${D_TIER[$i]}" = "required" ]; then
      mark="${C_RED}✘${C_RESET}"
      case "$method" in manual:* | none) MANUAL_REQ="$MANUAL_REQ $i" ;; *) MISSING_REQ="$MISSING_REQ $i" ;; esac
    else
      mark="${C_YELLOW}✘${C_RESET}"
      case "$method" in manual:* | none) MANUAL_OPT="$MANUAL_OPT $i" ;; *) MISSING_OPT="$MISSING_OPT $i" ;; esac
    fi
    printf '  %s %-9s %s%s%s\n' "$mark" "${D_TIER[$i]}" "$C_BOLD" "${D_ID[$i]}" "$C_RESET"
    printf '      %sneeded by:%s %s\n' "$C_DIM" "$C_RESET" "${D_REQBY[$i]}"
    printf '      %sinstall:%s   %s\n' "$C_DIM" "$C_RESET" "$(describe_method "$method")"
  done
}

# --- Installing ---------------------------------------------------------------
install_nerd_font() {
  local name="$1"
  case "$OS" in
    mac | linux)
      command -v oh-my-posh >/dev/null 2>&1 || { warn "oh-my-posh is needed to install fonts"; return 1; }
      oh-my-posh font install "$name" || return 1
      [ "$OS" = "linux" ] && command -v fc-cache >/dev/null 2>&1 && fc-cache -f >/dev/null
      return 0
      ;;
    wsl)
      if command -v pwsh.exe >/dev/null 2>&1; then
        info "Installing $name Nerd Font on Windows via PowerShell NerdFonts module..."
        (cd /mnt/c && pwsh.exe -NoProfile -Command \
          "Install-PSResource -Name NerdFonts -TrustRepository; Import-Module NerdFonts; Install-NerdFont -Name $name" </dev/null) && return 0
        warn "pwsh NerdFonts install failed; trying the next method"
      fi
      if command -v oh-my-posh.exe >/dev/null 2>&1; then
        info "Installing $name Nerd Font on Windows via oh-my-posh.exe..."
        (cd /mnt/c && oh-my-posh.exe font install "$name" </dev/null) && return 0
        warn "oh-my-posh.exe font install failed; trying the next method"
      fi
      if command -v powershell.exe >/dev/null 2>&1 && command -v iconv >/dev/null 2>&1 && command -v base64 >/dev/null 2>&1; then
        # Windows PowerShell 5.1 has no Install-PSResource: do a per-user install
        # (no admin) from the official Nerd Fonts release zip instead.
        info "Installing $name Nerd Font on Windows (per-user) from the Nerd Fonts release..."
        local script encoded
        script="\$ErrorActionPreference='Stop'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
\$zip=Join-Path \$env:TEMP 'nf-$name.zip'; \$dir=Join-Path \$env:TEMP 'nf-$name'
Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/ryanoasis/nerd-fonts/releases/latest/download/$name.zip' -OutFile \$zip
Expand-Archive -Force -Path \$zip -DestinationPath \$dir
\$fonts=Join-Path \$env:LOCALAPPDATA 'Microsoft\\Windows\\Fonts'
New-Item -ItemType Directory -Force -Path \$fonts | Out-Null
Get-ChildItem -Path \$dir -Recurse -Include *.ttf,*.otf | ForEach-Object {
  \$target=Join-Path \$fonts \$_.Name
  if (-not (Test-Path \$target)) { Copy-Item \$_.FullName \$target }
  New-ItemProperty -Force -Path 'HKCU:\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts' -Name (\$_.BaseName + ' (TrueType)') -Value \$target | Out-Null
}
Remove-Item -Recurse -Force \$zip,\$dir"
        encoded="$(printf '%s' "$script" | iconv -f UTF-8 -t UTF-16LE | base64 | tr -d '\n')"
        (cd /mnt/c && powershell.exe -NoProfile -NonInteractive -EncodedCommand "$encoded" </dev/null) && return 0
      fi
      warn "Could not install the font automatically. Install the '$name' Nerd Font on Windows: https://www.nerdfonts.com/font-downloads"
      return 1
      ;;
  esac
}

install_deps() {
  local indices="$1" i method apt_pkgs="" brew_pkgs="" cask_pkgs="" failed=""

  for i in $indices; do
    method="$(resolve_method "$i")"
    case "$method" in
      apt:*) apt_pkgs="$apt_pkgs ${method#apt:}" ;;
      brew:*) brew_pkgs="$brew_pkgs ${method#brew:}" ;;
      cask:*) cask_pkgs="$cask_pkgs ${method#cask:}" ;;
    esac
  done

  if [ -n "$apt_pkgs" ]; then
    section "apt"
    # shellcheck disable=SC2086 # word splitting is intended
    if ! { sudo apt-get update -qq && sudo apt-get install -y $apt_pkgs; }; then
      warn "apt-get reported an error"
    fi
  fi
  if [ -n "$brew_pkgs" ]; then
    section "brew"
    # shellcheck disable=SC2086
    brew install $brew_pkgs || warn "brew install reported an error"
  fi
  if [ -n "$cask_pkgs" ]; then
    section "brew casks"
    # shellcheck disable=SC2086
    brew install --cask $cask_pkgs || warn "brew install --cask reported an error"
  fi

  # Scripted installs run one at a time, in deps.list order.
  for i in $indices; do
    method="$(resolve_method "$i")"
    case "$method" in
      sh:*)
        section "${D_ID[$i]}"
        info "$ ${method#sh:}"
        bash -c "${method#sh:}" || warn "${D_ID[$i]} installer reported an error"
        ;;
      nerdfont:*)
        section "${D_ID[$i]}"
        install_nerd_font "${method#nerdfont:}"
        ;;
    esac
  done
  hash -r

  section "Re-checking"
  for i in $indices; do
    if dep_present "${D_CHECK[$i]}"; then
      printf '  %s✔%s %s\n' "$C_GREEN" "$C_RESET" "${D_ID[$i]}"
    else
      printf '  %s✘%s %s (%s)\n' "$C_RED" "$C_RESET" "${D_ID[$i]}" "${D_TIER[$i]}"
      [ "${D_TIER[$i]}" = "required" ] && failed="$failed ${D_ID[$i]}"
    fi
  done
  REQUIRED_STILL_MISSING="$failed"
}

# --- Link planning ------------------------------------------------------------
L_REL=() L_SRC=() L_STATE=() # state: linked | new | conflict
L_KIND=()                      # stow | skill
CREATE_DIRS=""

is_container() {
  local c
  for c in $STOW_CONTAINERS; do [ "$1" = "$c" ] && return 0; done
  return 1
}

resolve_path() {
  # Portable realpath (older macOS has no readlink -f): follow file symlinks
  # hop by hop, then let cd -P resolve any directory symlinks.
  local target="$1" dir link hops=0
  while [ -L "$target" ] && [ "$hops" -lt 40 ]; do
    link="$(readlink "$target")"
    case "$link" in
      /*) target="$link" ;;
      *) target="$(dirname "$target")/$link" ;;
    esac
    hops=$((hops + 1))
  done
  if [ -d "$target" ]; then
    (cd -P "$target" 2>/dev/null && pwd)
  else
    dir="$(dirname "$target")"
    (cd -P "$dir" 2>/dev/null && printf '%s/%s' "$(pwd)" "$(basename "$target")")
  fi
}

# linked | new | conflict for $HOME/<rel> vs repo <src>
classify_target() {
  local rel="$1" src="$2" dst="$HOME/$1" child
  if [ -L "$dst" ]; then
    if [ -e "$dst" ] && [ "$(resolve_path "$dst")" = "$(resolve_path "$src")" ]; then
      echo linked
    else
      echo conflict
    fi
  elif [ ! -e "$dst" ]; then
    echo new
  elif [ -d "$dst" ] && [ -d "$src" ]; then
    # A real directory whose entries are all our links (stow "unfolded") is fine.
    for child in "$dst"/* "$dst"/.[!.]*; do
      [ -e "$child" ] || [ -L "$child" ] || continue
      [ -L "$child" ] && [ -e "$child" ] || { echo conflict; return; }
      case "$(resolve_path "$child")" in "$(resolve_path "$src")"/*) ;; *) echo conflict; return ;; esac
    done
    [ -n "$(ls -A "$src" 2>/dev/null)" ] && [ -z "$(ls -A "$dst" 2>/dev/null)" ] && { echo conflict; return; }
    echo linked
  else
    echo conflict
  fi
}

add_link() {
  L_REL+=("$1") L_SRC+=("$2") L_KIND+=("$3") L_STATE+=("$(classify_target "$1" "$2")")
}

collect_stow_items() {
  local rel="$1" entry name
  for entry in "$DOTFILES_DIR/$PACKAGE/${rel:+$rel/}"* "$DOTFILES_DIR/$PACKAGE/${rel:+$rel/}".[!.]*; do
    [ -e "$entry" ] || continue
    name="${rel:+$rel/}$(basename "$entry")"
    if [ -d "$entry" ] && is_container "$name"; then
      [ -d "$HOME/$name" ] && [ ! -L "$HOME/$name" ] || CREATE_DIRS="$CREATE_DIRS $name"
      collect_stow_items "$name"
    else
      add_link "$name" "$entry" stow
    fi
  done
}

# Paths stow itself reports as conflicts (dry run, changes nothing).
stow_dry_run_conflicts() {
  stow -n -v -d "$DOTFILES_DIR" -t "$HOME" --restow "$PACKAGE" 2>&1 |
    sed -n \
      -e 's/.*over existing target \(.*\) since.*/\1/p' \
      -e 's/.*existing target is [^:]*: \(.*\)$/\1/p'
}

link_preflight() {
  section "Links into \$HOME"
  L_REL=() L_SRC=() L_STATE=() L_KIND=() CREATE_DIRS=""
  collect_stow_items ""
  add_link ".claude/skills" "$DOTFILES_DIR/agent-skills" skill
  add_link ".gemini/config/skills" "$DOTFILES_DIR/agent-skills" skill

  local i d
  for d in $CREATE_DIRS; do
    printf '  %s+%s ~/%s/ %s(directory will be created)%s\n' "$C_BLUE" "$C_RESET" "$d" "$C_DIM" "$C_RESET"
  done
  for i in "${!L_REL[@]}"; do
    case "${L_STATE[$i]}" in
      linked) printf '  %s✔%s ~/%s\n' "$C_GREEN" "$C_RESET" "${L_REL[$i]}" ;;
      new) printf '  %s+%s ~/%s %s-> %s%s\n' "$C_BLUE" "$C_RESET" "${L_REL[$i]}" "$C_DIM" "${L_SRC[$i]#"$DOTFILES_DIR"/}" "$C_RESET" ;;
      conflict) printf '  %s!%s ~/%s %s(exists and is not ours: will be backed up)%s\n' "$C_YELLOW" "$C_RESET" "${L_REL[$i]}" "$C_DIM" "$C_RESET" ;;
    esac
  done

  # Cross-check against stow's own dry run: anything it would refuse must be
  # covered by a planned backup, otherwise stop rather than guess.
  UNEXPECTED_CONFLICTS=""
  if command -v stow >/dev/null 2>&1; then
    local path covered
    while IFS= read -r path; do
      [ -n "$path" ] || continue
      covered=0
      for i in "${!L_REL[@]}"; do
        [ "${L_STATE[$i]}" = "conflict" ] || continue
        case "$path" in "${L_REL[$i]}" | "${L_REL[$i]}"/*) covered=1 ;; esac
      done
      [ "$covered" -eq 1 ] || UNEXPECTED_CONFLICTS="$UNEXPECTED_CONFLICTS $path"
    done <<EOF
$(stow_dry_run_conflicts)
EOF
    [ -z "$UNEXPECTED_CONFLICTS" ] || warn "stow reports conflicts not covered by the plan:$UNEXPECTED_CONFLICTS"
  else
    warn "stow is not installed, so the dry run was skipped"
  fi
}

count_state() {
  local want="$1" i n=0
  for i in "${!L_STATE[@]}"; do [ "${L_STATE[$i]}" = "$want" ] && n=$((n + 1)); done
  echo "$n"
}

apply_links() {
  local i d rel
  for d in $CREATE_DIRS; do mkdir -p "$HOME/$d"; done
  for i in "${!L_REL[@]}"; do
    rel="${L_REL[$i]}"
    mkdir -p "$(dirname "$HOME/$rel")"
    if [ "${L_STATE[$i]}" = "conflict" ]; then
      mkdir -p "$BACKUP_DIR/$(dirname "$rel")"
      mv "$HOME/$rel" "$BACKUP_DIR/$rel" || die "Could not back up ~/$rel"
      info "  backed up ~/$rel -> $BACKUP_DIR/$rel"
    fi
  done

  stow -d "$DOTFILES_DIR" -t "$HOME" --restow "$PACKAGE" || die "stow failed (backups are in $BACKUP_DIR)"
  for i in "${!L_REL[@]}"; do
    [ "${L_KIND[$i]}" = "skill" ] && ln -sfn "${L_SRC[$i]}" "$HOME/${L_REL[$i]}"
  done
}

# --- Agent statusLine wiring ----------------------------------------------------
W_LABEL=() W_FILE=() W_VALUE=() W_STATE=() # state: ok | change | skip:<reason>

plan_wiring() {
  W_LABEL=() W_FILE=() W_VALUE=() W_STATE=()
  add_wiring "Claude Code" claude "$HOME/.claude/settings.json" \
    "{\"type\":\"command\",\"command\":\"$HOME/.config/oh-my-posh/claude-statusline.sh\"}"
  add_wiring "Antigravity CLI" antigravity "$HOME/.gemini/antigravity-cli/settings.json" \
    "{\"type\":\"command\",\"command\":\"oh-my-posh antigravity --config $HOME/.config/oh-my-posh/agy-omp.json\",\"enabled\":true}"
}

add_wiring() {
  local label="$1" cli="$2" file="$3" value="$4" state
  if ! command -v "$cli" >/dev/null 2>&1; then
    state="skip:$cli not installed"
  elif [ ! -d "$(dirname "$file")" ]; then
    state="skip:$(dirname "$file") does not exist yet (start $cli once)"
  elif ! command -v jq >/dev/null 2>&1; then
    state="skip:jq not installed"
  elif [ -f "$file" ] && ! jq empty "$file" >/dev/null 2>&1; then
    state="skip:$file is not valid JSON"
  elif [ -f "$file" ] && jq -e --argjson v "$value" '(.statusLine // {}) as $s | all($v | to_entries[]; $s[.key] == .value)' "$file" >/dev/null 2>&1; then
    state="ok"
  else
    state="change"
  fi
  W_LABEL+=("$label") W_FILE+=("$file") W_VALUE+=("$value") W_STATE+=("$state")
}

wiring_report() {
  section "Agent status lines"
  local i
  for i in "${!W_LABEL[@]}"; do
    case "${W_STATE[$i]}" in
      ok) printf '  %s✔%s %s\n' "$C_GREEN" "$C_RESET" "${W_LABEL[$i]}" ;;
      change)
        printf '  %s~%s %s: ~%s\n' "$C_BLUE" "$C_RESET" "${W_LABEL[$i]}" "${W_FILE[$i]#"$HOME"}"
        printf '      %scurrent:%s %s\n' "$C_DIM" "$C_RESET" "$([ -f "${W_FILE[$i]}" ] && jq -c '.statusLine // "none"' "${W_FILE[$i]}" || echo 'no settings file')"
        printf '      %snew:%s     %s\n' "$C_DIM" "$C_RESET" "${W_VALUE[$i]}"
        ;;
      skip:*) printf '  %s-%s %s %s(%s)%s\n' "$C_DIM" "$C_RESET" "${W_LABEL[$i]}" "$C_DIM" "${W_STATE[$i]#skip:}" "$C_RESET" ;;
    esac
  done
}

apply_wiring() {
  local i file tmp rel
  for i in "${!W_LABEL[@]}"; do
    [ "${W_STATE[$i]}" = "change" ] || continue
    file="${W_FILE[$i]}"
    rel="${file#"$HOME"/}"
    if [ -f "$file" ]; then
      mkdir -p "$BACKUP_DIR/$(dirname "$rel")"
      cp -p "$file" "$BACKUP_DIR/$rel"
    else
      printf '{}\n' >"$file"
    fi
    tmp="$(mktemp)"
    if jq --argjson v "${W_VALUE[$i]}" '.statusLine = ((.statusLine // {}) + $v)' "$file" >"$tmp"; then
      cat "$tmp" >"$file" # keeps the file's permissions and any symlink
      info "  updated ${W_LABEL[$i]}$([ -f "$BACKUP_DIR/$rel" ] && printf ' (backup: %s)' "$BACKUP_DIR/$rel")"
    else
      warn "Could not update $file"
    fi
    rm -f "$tmp"
  done
}

# ==============================================================================
detect_platform
load_deps
dependency_preflight
link_preflight
plan_wiring
wiring_report

if [ "$MODE" = "check" ]; then
  section "Summary (read-only check, nothing was changed)"
  if [ -n "$MISSING_REQ$MANUAL_REQ" ]; then
    info "Missing required dependencies:$(for i in $MISSING_REQ $MANUAL_REQ; do printf ' %s' "${D_ID[$i]}"; done)"
    exit 1
  fi
  [ -z "$MANUAL_OPT" ] || info "Optional, install by hand if wanted:$(for i in $MANUAL_OPT; do printf ' %s' "${D_ID[$i]}"; done)"
  info "All required dependencies are present."
  exit 0
fi

# --- 1. Dependencies ------------------------------------------------------------
REQUIRED_STILL_MISSING=""
[ -z "$MANUAL_OPT" ] || info "
Optional, install by hand if wanted (see 'install:' above):$(for i in $MANUAL_OPT; do printf ' %s' "${D_ID[$i]}"; done)"
if [ -n "$MANUAL_REQ" ]; then
  die "Required dependencies need a manual install first (see 'install:' above):$(for i in $MANUAL_REQ; do printf ' %s' "${D_ID[$i]}"; done). Nothing was changed."
fi
if [ -z "$MISSING_REQ$MISSING_OPT" ]; then
  info ""
  info "All installable dependencies are present."
else
  if [ "$OS" = "mac" ] && [ "$PKG" = "none" ]; then
    # shellcheck disable=SC2016 # the command is printed for the user, not run
    die 'Homebrew is required on macOS. Install it (https://brew.sh), then re-run: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  fi
  echo
  if [ -n "$MISSING_REQ" ]; then
    ask "Install missing dependencies? [a]ll / [r]equired only / [N]o:" a
  else
    ask "Install missing optional dependencies? [a]ll / [N]o:" a
  fi
  case "$REPLY_VALUE" in
    a | A | all) install_deps "$MISSING_REQ $MISSING_OPT" ;;
    r | R | required) [ -n "$MISSING_REQ" ] && install_deps "$MISSING_REQ" ;;
    *)
      if [ -n "$MISSING_REQ" ]; then
        info "Aborted. Nothing was changed."
        exit 0
      fi
      info "Skipping optional dependencies."
      ;;
  esac
  if [ -n "$REQUIRED_STILL_MISSING" ]; then
    die "Required dependencies still missing:$REQUIRED_STILL_MISSING. Nothing in \$HOME was changed; fix these and re-run."
  fi
  # Re-plan: stow and jq may have just been installed.
  link_preflight
  plan_wiring
fi

# --- 2. Links -------------------------------------------------------------------
if [ -n "$UNEXPECTED_CONFLICTS" ]; then
  die "Stopping before linking: stow found conflicts the installer can't back up safely:$UNEXPECTED_CONFLICTS"
fi
CONFLICTS="$(count_state conflict)" NEW_LINKS="$(count_state new)"
if [ "$CONFLICTS" -eq 0 ] && [ "$NEW_LINKS" -eq 0 ] && [ -z "$CREATE_DIRS" ]; then
  info ""
  info "All links are already in place."
else
  echo
  [ "$CONFLICTS" -gt 0 ] && info "$CONFLICTS existing item(s) marked ! will be moved to $BACKUP_DIR/ (not deleted)."
  ask "Create/update $((CONFLICTS + NEW_LINKS)) link(s) as listed above? [y/N]:" y
  case "$REPLY_VALUE" in
    y | Y | yes) ;;
    *) info "Aborted before linking. Dependencies (if any) were installed; \$HOME links are unchanged."; exit 0 ;;
  esac
  section "Linking"
  apply_links
  link_preflight
  if [ "$(count_state conflict)" -ne 0 ] || [ "$(count_state new)" -ne 0 ] || [ -n "$UNEXPECTED_CONFLICTS" ]; then
    die "Linking did not complete cleanly; see above. Backups: $BACKUP_DIR"
  fi
fi

# --- 3. Agent wiring ------------------------------------------------------------
CHANGES=0
for s in "${W_STATE[@]}"; do [ "$s" = "change" ] && CHANGES=$((CHANGES + 1)); done
if [ "$CHANGES" -gt 0 ]; then
  wiring_report
  echo
  ask "Update statusLine in $CHANGES settings file(s) as shown? Only the statusLine key changes. [y/N]:" y
  case "$REPLY_VALUE" in
    y | Y | yes) apply_wiring ;;
    *) info "Skipped status line wiring." ;;
  esac
fi

# --- Summary --------------------------------------------------------------------
section "Done"
[ -d "$BACKUP_DIR" ] && info "Backups: $BACKUP_DIR (move items back to restore; remove the symlink first)"
info "Manual follow-ups, if not done already:"
case "$OS" in
  wsl) info "  - Windows Terminal: Settings > Defaults > Appearance > Font face = CaskaydiaCove Nerd Font" ;;
  mac) info "  - Terminal/iTerm2: set the font to CaskaydiaCove Nerd Font" ;;
  linux) info "  - Terminal emulator: set the font to CaskaydiaCove Nerd Font" ;;
esac
[ "$(basename "${SHELL:-}")" = "zsh" ] || info "  - Make zsh your login shell: chsh -s \"\$(command -v zsh)\""
info "  - Open a new terminal to load the new shell config."
