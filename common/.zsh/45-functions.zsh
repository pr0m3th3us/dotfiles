# --- Functions ------------------------------------------------

# Re-link dotfiles after adding/removing files in the repo.
# Usage: restow [-d <dotfiles-dir>] [package...]   (default package: common)
restow() {
  command -v stow >/dev/null 2>&1 || { echo "restow: stow is not installed" >&2; return 1; }
  local dir="${DOTFILES_DIR:-$HOME/projects/dotfiles}"
  if [[ "$1" == "-d" ]]; then
    [[ -n "$2" ]] || { echo "usage: restow [-d <dir>] [package...]" >&2; return 1; }
    dir="$2"
    shift 2
  fi
  (( $# )) || set -- common
  stow -d "$dir" -t "$HOME" --restow "$@" && echo "restowed $* from $dir"
}
