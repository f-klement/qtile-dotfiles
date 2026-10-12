#!/bin/bash
# Ported from the reference's scripts/Refresh.sh -- restart waybar/rofi/swaync.
_ps=(waybar rofi swaync)
for _prs in "${_ps[@]}"; do
    pidof "${_prs}" >/dev/null && pkill "${_prs}"
done

sleep 0.3
waybar -c ~/.config/waybar/config -s ~/.config/waybar/style.css &

sleep 0.5
swaync > /dev/null 2>&1 &

exit 0
