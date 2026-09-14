#!/usr/bin/env bash
# wallpaper.sh -- set a random wallpaper from ~/Pictures/wallpapers (recursive).
#
#   wallpaper.sh            random image, never the one currently shown
#   wallpaper.sh restore    re-apply the last one (feh keeps it in ~/.fehbg)
#
# Used by the qtile autostart (initial + every 5 min) and by the paint-brush
# button in the bar. The file list is cached in $XDG_RUNTIME_DIR so the
# periodic call does not re-walk the whole tree every time: it is rebuilt only
# when a directory in the tree is newer than the cache (adding/removing a file
# bumps its parent directory's mtime), so new wallpapers are picked up without
# a restart.
set -u
WALLPAPER_DIR="${WALLPAPER_DIR:-$HOME/Pictures/wallpapers}"
CACHE="${XDG_RUNTIME_DIR:-/tmp}/wallpapers.list"

if [ "${1:-}" = restore ]; then
    [ -x "$HOME/.fehbg" ] && exec "$HOME/.fehbg"
    exit 0
fi

if [ ! -s "$CACHE" ] || find "$WALLPAPER_DIR" -name .git -prune -o -type d -newer "$CACHE" -print -quit | grep -q .; then
    find "$WALLPAPER_DIR" -name .git -prune -o -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) -print > "$CACHE"
fi
mapfile -t WALLPAPERS < "$CACHE"
(( ${#WALLPAPERS[@]} == 0 )) && exit 0

# current one, as recorded by feh:  feh --no-fehbg --bg-fill '/path/to/img'
current=$(sed -n "s/.*--bg-fill '\(.*\)'.*/\1/p" "$HOME/.fehbg" 2>/dev/null)
if (( ${#WALLPAPERS[@]} > 1 )); then
    while :; do
        pick="${WALLPAPERS[RANDOM % ${#WALLPAPERS[@]}]}"
        [ "$pick" != "$current" ] && break
    done
else
    pick="${WALLPAPERS[0]}"
fi
exec feh --bg-fill "$pick"
