#!/bin/bash
# Adapted from the reference's scripts/SwitchKeyboardLayout.sh -- cycles
# through input:kb_layout's comma-separated list. Reads settings.conf's
# real hyprlang syntax (`kb_layout = de,us`) instead of the reference's
# settings.lua (`kb_layout = "de"`).

layout_f="$HOME/.cache/kb_layout"
settings_file="$HOME/.config/hypr/settings.conf"

kb_layout_line=$(grep -oP '^\s*kb_layout\s*=\s*\K.*' "$settings_file" | tr -d ' ')
IFS=',' read -ra layout_mapping <<< "$kb_layout_line"
layout_count=${#layout_mapping[@]}

if [ "$layout_count" -eq 0 ]; then
    notify-send -u low -a "Hyprland" "No kb_layout configured in settings.conf"
    exit 1
fi

if [ ! -f "$layout_f" ]; then
    echo "${layout_mapping[0]}" > "$layout_f"
fi
current_layout=$(cat "$layout_f")

current_index=0
for ((i = 0; i < layout_count; i++)); do
    if [ "$current_layout" == "${layout_mapping[i]}" ]; then
        current_index=$i
        break
    fi
done

next_index=$(( (current_index + 1) % layout_count ))
new_layout="${layout_mapping[next_index]}"

hyprctl keyword input:kb_layout "$kb_layout_line"
hyprctl switchxkblayout all "$next_index"
echo "$new_layout" > "$layout_f"

notify-send -u low -a "Hyprland" "Keyboard layout: $new_layout"
