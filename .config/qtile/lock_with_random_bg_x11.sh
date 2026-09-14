#!/usr/bin/env bash
IMG="$(find ~/Pictures/wallpapers -type f \( -iname '*.jpg' -o -iname '*.png' \) | shuf -n1)"
if [[ -z "$IMG" ]]; then
  exec i3lock --color=000000 --nofork --show-failed-attempts --ignore-empty-password
else
  exec i3lock --image="$IMG" --nofork --show-failed-attempts --ignore-empty-password
fi
