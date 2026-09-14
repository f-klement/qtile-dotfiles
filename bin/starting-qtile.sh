#!/usr/bin/env bash
set -euo pipefail

LOGFILE="${HOME}/.local/share/qtile-startup.log"
VENV_QTILE="${HOME}/.local/venvs/qtile/bin/qtile"

echo "[$(date)] Starting custom Qtile session" >> "$LOGFILE"

# Wait for GNOME to initialize
sleep 5
# Kill leftover GNOME session processes
for PROC in \
  gnome-shell \
  gnome-software \
  gnome-shell-calendar-server \
  evolution-calendar-factory-subprocess \
  evolution-addressbook-factory-subprocess; do
  if pgrep -x "$PROC" > /dev/null; then
    echo "[$(date)] Killing $PROC" >> "$LOGFILE"
    pkill -x "$PROC" || echo "[$(date)] Warning: Failed to kill $PROC" >> "$LOGFILE"
  fi
done

# gnome-keyring: inject socket paths before qtile launches
eval "$(gnome-keyring-daemon --start --components=pkcs11,secrets,ssh,gpg)"
export SSH_AUTH_SOCK GNOME_KEYRING_CONTROL

dbus-update-activation-environment --systemd GNOME_KEYRING_CONTROL SSH_AUTH_SOCK

# Toolkit env: everything qtile spawns inherits this (GTK via XSETTINGS instead).
# Do NOT export GTK_THEME here -- it disables prefer-dark and breaks libadwaita.
export QT_QPA_PLATFORMTHEME=qt5ct
export XCURSOR_THEME=BreezeX-RosePine-Linux
export XCURSOR_SIZE=24
# Keep __pycache__ out of the stowed (symlinked) config dirs.
export PYTHONPYCACHEPREFIX="$HOME/.cache/python-pycache"
dbus-update-activation-environment --systemd QT_QPA_PLATFORMTHEME XCURSOR_THEME XCURSOR_SIZE PYTHONPYCACHEPREFIX

# glibc tuning: pin the trim threshold (stops qtile's heap ratcheting) + cap arenas.
export MALLOC_TRIM_THRESHOLD_=131072
export MALLOC_ARENA_MAX=2

if [[ -x "$VENV_QTILE" ]]; then
  echo "[$(date)] Starting Qtile from $VENV_QTILE" >> "$LOGFILE"
  exec "$VENV_QTILE" start
else
  echo "[$(date)] ERROR: Qtile binary not found at $VENV_QTILE" >> "$LOGFILE"
  exit 1
fi
