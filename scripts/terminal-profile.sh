#!/usr/bin/env bash
# Give the current macOS user the same Terminal.app look: imports the "Dotfiles Dark" profile
# (scripts/terminal/Dotfiles Dark.terminal: Google Sans Code NF SemiBold 14, 120x30, the same
# colors, spacing and anti-aliasing as the author's "Clear Dark") and makes it the default for
# new windows. Terminal prefs are per user, so run this once in each macOS account.
#
#   scripts/terminal-profile.sh --check    read-only report; exit 0 = already set up,
#                                          10 = apply would change something, 11 = font missing
#   scripts/terminal-profile.sh --dry-run  show what apply would do, change nothing
#   scripts/terminal-profile.sh            apply (backs up Terminal prefs first)
#
# ./install.sh runs this too (plan, consent, apply), so on a new account `git pull && ./install.sh` is enough.
# Nothing is deleted: existing profiles stay, so switching back is Terminal > Settings > Profiles.
# If the profile already exists it is not re-imported; to pick up a changed .terminal file, delete
# "Dotfiles Dark" in Terminal > Settings > Profiles and run this again.
set -u

PROFILE="Dotfiles Dark"
HERE="$(cd "$(dirname "$0")" && pwd)"
FILE="$HERE/terminal/Dotfiles Dark.terminal"
FONT_FILE="GoogleSansCodeNerdFontPropo-SemiBold.ttf" # the profile's font: GoogleSansCodeNFP-SemiBold

mode=apply
case "${1:-}" in
  "") ;;
  --check) mode=check ;;
  --dry-run) mode=dry ;;
  *) echo "usage: $0 [--check|--dry-run]" >&2; exit 2 ;;
esac

[ "$(uname -s)" = Darwin ] || { echo "Terminal.app is macOS only; nothing to do."; exit 0; }
[ -f "$FILE" ] || { echo "missing $FILE" >&2; exit 1; }

font_ok=no
for d in "$HOME/Library/Fonts" /Library/Fonts; do
  [ -f "$d/$FONT_FILE" ] && font_ok=yes
done
prefs="$(defaults read com.apple.Terminal "Window Settings" 2>/dev/null || true)"
case "$prefs" in *"\"$PROFILE\""* | *"$PROFILE = "*) have=yes ;; *) have=no ;; esac
cur="$(defaults read com.apple.Terminal "Default Window Settings" 2>/dev/null || echo "?")"

echo "font $FONT_FILE installed: $font_ok"
echo "profile '$PROFILE' present: $have"
echo "current default profile:   $cur"
if [ "$font_ok" = no ]; then state=nofont
elif [ "$have" = yes ] && [ "$cur" = "$PROFILE" ]; then state=ok
else state=change; fi
if [ "$mode" = check ]; then
  case "$state" in ok) exit 0 ;; change) exit 10 ;; *) exit 11 ;; esac
fi

if [ "$font_ok" = no ]; then
  echo "Font missing, so nothing was changed (Terminal would fall back to another font)." >&2
  echo "Install it first:  oh-my-posh font install GoogleSansCode   (or ./install.sh), then re-run." >&2
  exit 1
fi
if [ "$have" = yes ] && [ "$cur" = "$PROFILE" ]; then
  echo "Already set up. Nothing to do."
  exit 0
fi
if [ "$mode" = dry ]; then
  [ "$have" = no ] && echo "would: back up Terminal prefs, import '$FILE'"
  echo "would: set '$PROFILE' as default and startup profile"
  exit 0
fi

bk="${BACKUP_DIR:-$HOME/.dotfiles_backup_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$bk" && defaults export com.apple.Terminal "$bk/com.apple.Terminal.plist" \
  && echo "backed up Terminal prefs to $bk/com.apple.Terminal.plist"

if [ "$have" = no ]; then
  open -a Terminal "$FILE" || { echo "could not import the profile" >&2; exit 1; }
  i=0
  while [ "$i" -lt 20 ]; do
    [ "$(osascript -e "tell application \"Terminal\" to exists settings set \"$PROFILE\"" 2>/dev/null)" = true ] && break
    sleep 0.5; i=$((i + 1))
  done
fi

osascript <<EOF >/dev/null 2>&1
tell application "Terminal"
  set default settings to settings set "$PROFILE"
  set startup settings to settings set "$PROFILE"
end tell
EOF
got="$(osascript -e 'tell application "Terminal" to get name of default settings' 2>/dev/null)"
if [ "$got" = "$PROFILE" ]; then
  echo "Done. '$PROFILE' is now the default; open a new window/tab to see it."
else
  echo "Import or default change did not take (default is '$got'). Prefs backup is in $bk." >&2
  echo "Manual: Terminal > Settings > Profiles > '$PROFILE' > Default." >&2
  exit 1
fi
