#!/bin/bash
## Network menu -- ported from the hyprland-arch-dotfiles reference's
## scripts/NetworkMenu.sh. Live SSID list with signal/security, one click
## to (re)connect, a Wi-Fi on/off toggle, and nm-connection-editor as the
## fallback for real profile editing. Wired as QuickSettings.py's Wi-Fi
## tile action (see pane.py's tile(), which only supports one click
## handler) rather than a plain toggle -- this menu's first entry already
## covers the toggle case, so nothing is lost.
##
## Toggle uses `nmcli radio wifi`, NOT rfkill -- rfkill operates below
## NetworkManager and can leave NM's own state out of sync with it.

rofi_config="$HOME/.config/rofi/config-compact.rasi"

wifi_state=$(nmcli radio wifi)
current_ssid=$(nmcli -t -f active,ssid dev wifi 2>/dev/null | awk -F: '$1=="yes"{print $2}')

if [ "$wifi_state" = "enabled" ]; then
    status="Wi-Fi is on$( [ -n "$current_ssid" ] && echo " -- connected to $current_ssid" || echo " -- not connected" )"
else
    status="Wi-Fi is off"
fi

build_menu() {
    if [ "$wifi_state" = "enabled" ]; then
        echo "Turn Wi-Fi off"
        nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list --rescan no 2>/dev/null \
            | awk -F: '$2 != "" && !seen[$2]++ {
                  mark = ($1 == "*") ? "* " : "  ";
                  lock = ($4 == "") ? "" : "  [locked]";
                  printf "%s%s (%s%%)%s\n", mark, $2, $3, lock
              }'
    else
        echo "Turn Wi-Fi on"
    fi
    echo "Connection Editor..."
}

choice=$(build_menu | rofi -dmenu -p "Network" -mesg "$status" -config "$rofi_config")

[ -n "$choice" ] || exit 0

case "$choice" in
    "Turn Wi-Fi off")
        nmcli radio wifi off
        notify-send -u low -a "Hyprland" 'Wi-Fi: OFF'
        ;;
    "Turn Wi-Fi on")
        nmcli radio wifi on
        notify-send -u low -a "Hyprland" 'Wi-Fi: ON'
        ;;
    "Connection Editor...")
        nm-connection-editor &
        disown
        ;;
    *)
        ssid=$(sed -E 's/^[* ] //; s/ \([0-9]+%\)(  \[locked\])?$//' <<< "$choice")
        locked=$(grep -q '\[locked\]$' <<< "$choice" && echo yes || echo no)

        if nmcli -t -f NAME connection show | grep -qxF "$ssid"; then
            if nmcli connection up id "$ssid" >/dev/null 2>&1; then
                notify-send -u low -a "Hyprland" "Connected to $ssid"
            else
                notify-send -u normal -a "Hyprland" "Failed to connect to $ssid"
            fi
        elif [ "$locked" = "yes" ]; then
            pw=$(rofi -dmenu -password -p "Password for $ssid" -config "$rofi_config")
            if [ -n "$pw" ]; then
                if nmcli device wifi connect "$ssid" password "$pw" >/dev/null 2>&1; then
                    notify-send -u low -a "Hyprland" "Connected to $ssid"
                else
                    notify-send -u normal -a "Hyprland" "Failed to connect to $ssid (wrong password?)"
                fi
            fi
        else
            if nmcli device wifi connect "$ssid" >/dev/null 2>&1; then
                notify-send -u low -a "Hyprland" "Connected to $ssid"
            else
                notify-send -u normal -a "Hyprland" "Failed to connect to $ssid"
            fi
        fi
        ;;
esac
