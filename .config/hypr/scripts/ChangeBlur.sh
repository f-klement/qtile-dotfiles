#!/bin/bash
# Ported near-verbatim from the hyprland-arch-dotfiles reference's
# scripts/ChangeBlur.sh -- toggle between two blur presets on the fly.
# notif icon swapped for our own asset (the reference's bell.png isn't
# part of this port).

STATE=$(hyprctl -j getoption decoration:blur:passes | jq ".int")

if [ "${STATE}" == "2" ]; then
    hyprctl keyword decoration:blur:size 2
    hyprctl keyword decoration:blur:passes 1
    notify-send -e -u low -a "Hyprland" "Less blur"
else
    hyprctl keyword decoration:blur:size 5
    hyprctl keyword decoration:blur:passes 2
    notify-send -e -u low -a "Hyprland" "Normal blur"
fi
