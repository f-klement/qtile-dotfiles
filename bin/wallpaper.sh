#!/usr/bin/env bash
# Set a random wallpaper from ~/Pictures/wallpapers (never the current one).
#   wallpaper.sh          random image      wallpaper.sh restore   re-apply last
# X11: feh (~/.fehbg). qtile-wayland: swaybg. Hyprland: hyprpaper (IPC,
# ipc=on in hyprpaper.conf). Current image in $XDG_STATE_HOME/wallpaper,
# shared across both Wayland backends.
# The file list is cached in $XDG_RUNTIME_DIR, rebuilt only when a dir mtime changes.
set -u
WALLPAPER_DIR="${WALLPAPER_DIR:-$HOME/Pictures/wallpapers}"
CACHE="${XDG_RUNTIME_DIR:-/tmp}/wallpapers.list"
WL_STATE="${XDG_STATE_HOME:-$HOME/.local/state}/wallpaper"

# swaybg holds the image for as long as it runs: start the new one, then drop
# the old ones, so there is no flash of empty background in between.
set_wayland_swaybg() {
    local old
    old=$(pgrep -u "$USER" -x swaybg)
    swaybg -i "$1" -m fill >/dev/null 2>&1 &
    disown
    mkdir -p "${WL_STATE%/*}" && printf '%s\n' "$1" > "$WL_STATE"
    sleep 0.3
    [ -n "$old" ] && kill $old 2>/dev/null
    exit 0
}

# hyprpaper: preload the new image, point every monitor at it, then unload
# the previous one -- same "no gap" ordering as the swaybg path above.
set_wayland_hyprpaper() {
    local old
    old=$(cat "$WL_STATE" 2>/dev/null)
    hyprctl hyprpaper preload "$1" >/dev/null 2>&1
    hyprctl hyprpaper wallpaper ",$1" >/dev/null 2>&1
    mkdir -p "${WL_STATE%/*}" && printf '%s\n' "$1" > "$WL_STATE"
    [ -n "$old" ] && [ "$old" != "$1" ] && hyprctl hyprpaper unload "$old" >/dev/null 2>&1
    exit 0
}

set_wayland() {
    if [ -n "${HYPRLAND_INSTANCE_SIGNATURE:-}" ]; then
        set_wayland_hyprpaper "$1"
    else
        set_wayland_swaybg "$1"
    fi
}

if [ "${1:-}" = restore ]; then
    if [ -n "${WAYLAND_DISPLAY:-}" ]; then
        [ -s "$WL_STATE" ] && set_wayland "$(cat "$WL_STATE")"
    else
        [ -x "$HOME/.fehbg" ] && exec "$HOME/.fehbg"
    fi
    exit 0
fi

if [ ! -s "$CACHE" ] || find "$WALLPAPER_DIR" -name .git -prune -o -type d -newer "$CACHE" -print -quit | grep -q .; then
    find "$WALLPAPER_DIR" -name .git -prune -o -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) -print > "$CACHE"
fi
mapfile -t WALLPAPERS < "$CACHE"
(( ${#WALLPAPERS[@]} == 0 )) && exit 0

if [ -n "${WAYLAND_DISPLAY:-}" ]; then
    current=$(cat "$WL_STATE" 2>/dev/null)
else
    current=$(sed -n "s/.*--bg-fill '\(.*\)'.*/\1/p" "$HOME/.fehbg" 2>/dev/null)
fi
if (( ${#WALLPAPERS[@]} > 1 )); then
    while :; do
        pick="${WALLPAPERS[RANDOM % ${#WALLPAPERS[@]}]}"
        [ "$pick" != "$current" ] && break
    done
else
    pick="${WALLPAPERS[0]}"
fi
[ -n "${WAYLAND_DISPLAY:-}" ] && set_wayland "$pick"
exec feh --bg-fill "$pick"
