#!/bin/bash
# Adapted from the reference's scripts/GameMode.sh -- toggle animations/
# blur/shadows/gaps off for games. Drops the PywalSwww.sh call (this setup
# doesn't use pywal dynamic theming, see theme.sh) and uses our own
# wallpaper.sh/Refresh.sh in its place.
SCRIPTSDIR="$HOME/.config/hypr/scripts"

HYPRGAMEMODE=$(hyprctl getoption animations:enabled | awk 'NR==1{print $2}')
if [ "$HYPRGAMEMODE" = 1 ]; then
    hyprctl --batch "\
        keyword animations:enabled 0;\
        keyword decoration:drop_shadow 0;\
        keyword decoration:blur:passes 0;\
        keyword general:gaps_in 0;\
        keyword general:gaps_out 0;\
        keyword general:border_size 1;\
        keyword decoration:rounding 0"
    pkill hyprpaper
    notify-send -e -u low -a "Hyprland" "Game mode enabled. All animations off"
else
    # The reference's own GameMode.sh has a trailing `hyprctl reload` meant
    # to restore settings.conf's real gaps/shadow/rounding/blur values here
    # -- but it sits after both branches' `exit`, so it's dead code there
    # and animations-off never actually restores. Reachable here instead.
    hyprctl reload
    hyprpaper &
    disown
    sleep 0.3
    ~/bin/wallpaper.sh restore || ~/bin/wallpaper.sh
    sleep 0.3
    "${SCRIPTSDIR}/Refresh.sh"
    notify-send -e -u normal -a "Hyprland" "Game mode disabled. All animations normal"
fi
