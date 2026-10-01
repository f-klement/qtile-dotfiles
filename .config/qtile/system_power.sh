#!/usr/bin/env bash
# Power action for the qtile power (⏻) widget: reboot or shut down.

set -u

title() { printf '\033]0;%s\007' "$1"; }

title 'POWER - reboot or shut down'
echo '================================================================'
echo ' POWER'
echo '   r  reboot     (sudo reboot)'
echo '   s  shut down  (sudo poweroff)'
echo ' Anything else cancels. The machine goes down IMMEDIATELY after'
echo ' your password - unsaved work will be lost.'
echo '================================================================'
echo
read -r -n 1 -p 'Choice [r/s]: ' choice
echo
case "$choice" in
    r|R) action=reboot;   label='REBOOT' ;;
    s|S) action=poweroff; label='SHUT DOWN' ;;
    *)   title 'Power - cancelled'; echo 'Cancelled.'; sleep 1; exit 0 ;;
esac

title "$label - password will $action this machine now"
if ! sudo -v; then
    title "$label - ABORTED (no sudo)"
    echo "No sudo privileges - $action cancelled."
    read -r _
    exit 1
fi

title "$label - now"
sudo -n "$action"

# Only reached if the command itself failed; otherwise the machine is going down.
title "$label - FAILED"
echo
echo "--- $action failed. Press Enter to close. ---"
read -r _
