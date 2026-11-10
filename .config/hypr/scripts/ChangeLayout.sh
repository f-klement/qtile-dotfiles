#!/bin/bash
# Adapted from the reference's scripts/ChangeLayout.sh -- toggles
# general:layout between dwindle and master. The reference also rebinds
# SUPER+J/K/O on the fly to different dispatchers per layout (cyclenext vs
# layoutmsg cyclenext/cycleprev, togglesplit only under dwindle); we keep
# J/K/O bound the same way in both layouts instead (see keybinds.conf) --
# same end result (cycle/split still work) without runtime keybind
# rewriting, which is simpler to reason about and verify.

LAYOUT=$(hyprctl -j getoption general:layout | jq -r '.str')

if [ "$LAYOUT" = "master" ]; then
    hyprctl keyword general:layout dwindle
    notify-send -e -u low -a "Hyprland" "Dwindle layout"
else
    hyprctl keyword general:layout master
    notify-send -e -u low -a "Hyprland" "Master layout"
fi
