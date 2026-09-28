#!/usr/bin/env bash
# swaylock with a random wallpaper (Wayland counterpart of lock_with_random_bg_x11.sh).
# Run by swayidle on idle, before sleep and on `loginctl lock-session` (Mod+L).
# Colours/indicator/font come from ~/.config/swaylock/config, which bin/theme.sh
# switches between Rosé Pine and Dawn; no image -> the palette's base colour.
# -f daemonizes once the lock is up, so swayidle -w holds suspend until then.
pgrep -u "$USER" -x swaylock >/dev/null && exit 0
IMG="$(find ~/Pictures/wallpapers -name .git -prune -o -type f \( -iname '*.jpg' -o -iname '*.png' \) -print | shuf -n1)"
if [[ -z "$IMG" ]]; then
  exec swaylock -f
else
  exec swaylock -f --image "$IMG"
fi
