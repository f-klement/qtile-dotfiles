#!/usr/bin/env bash
# swaylock with a random wallpaper (Wayland counterpart of lock_with_random_bg_x11.sh).
# -f daemonizes once the lock is up, so swayidle -w holds suspend until then.
pgrep -u "$USER" -x swaylock >/dev/null && exit 0
IMG="$(find ~/Pictures/wallpapers -name .git -prune -o -type f \( -iname '*.jpg' -o -iname '*.png' \) -print | shuf -n1)"
if [[ -z "$IMG" ]]; then
  exec swaylock -f --color 000000 --show-failed-attempts --ignore-empty-password
else
  exec swaylock -f --image "$IMG" --scaling fill --show-failed-attempts --ignore-empty-password
fi
