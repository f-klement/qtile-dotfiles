#!/usr/bin/env bash
# Set a random wallpaper from ~/Pictures/wallpapers (never the current one).
#   wallpaper.sh          random image      wallpaper.sh restore   re-apply last (~/.fehbg)
# The file list is cached in $XDG_RUNTIME_DIR, rebuilt only when a dir mtime changes.
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
