#!/usr/bin/env bash
# Session entry for qtile on Wayland, started by the display manager via
# /usr/share/wayland-sessions/qtile-dotfiles.desktop (fedora_wayland_bootstrap.sh).
# Counterpart of starting-qtile.sh (X11, anchored in gnome-session). Everything
# exported here is inherited by qtile and all it spawns; autostart_wayland.sh
# hands it on to systemd/D-Bus once WAYLAND_DISPLAY exists.
set -euo pipefail

LOGFILE="${HOME}/.local/share/qtile-startup.log"
mkdir -p "${LOGFILE%/*}"
echo "[$(date)] Starting Qtile Wayland session" >> "$LOGFILE"

# Desktop identity. "wlroots" lets xdg-desktop-portal-wlr match; the portal
# routing itself is ~/.config/xdg-desktop-portal/qtile-portals.conf.
export XDG_CURRENT_DESKTOP=qtile:wlroots
export XDG_SESSION_DESKTOP=qtile
export DESKTOP_SESSION=qtile
export XDG_SESSION_TYPE=wayland

# Toolkits: native Wayland where possible, XWayland as fallback.
export QT_QPA_PLATFORM="wayland;xcb"
export QT_WAYLAND_DISABLE_WINDOWDECORATION=1
export MOZ_ENABLE_WAYLAND=1
export ELECTRON_OZONE_PLATFORM_HINT=auto
export SDL_VIDEODRIVER="wayland,x11"
export _JAVA_AWT_WM_NONREPARENTING=1

# Qt theme. With plasma-integration installed (Fedora KDE) the KDE platform
# theme styles Qt5 AND Qt6 apps from ~/.config/kdeglobals, which theme.sh keeps
# in Rosé Pine. qt5ct only reaches Qt5, and most KDE apps are Qt6.
# Do NOT export GTK_THEME: it disables prefer-dark and breaks libadwaita.
if compgen -G "/usr/lib64/qt6/plugins/platformthemes/KDEPlasmaPlatformTheme6.so" >/dev/null; then
  export QT_QPA_PLATFORMTHEME=kde
else
  export QT_QPA_PLATFORMTHEME=qt5ct
fi

# Cursor follows the light/dark mode saved by bin/theme.sh (default dark).
if [[ "$(cat "${XDG_STATE_HOME:-$HOME/.local/state}/theme-mode" 2>/dev/null)" == light ]]; then
  export XCURSOR_THEME=BreezeX-RosePineDawn-Linux
else
  export XCURSOR_THEME=BreezeX-RosePine-Linux
fi
export XCURSOR_SIZE=24

# Keyboard: the system XKB setting (localectl), which Plasma and X11 also use.
# qtile hands empty kb_* to xkbcommon, which then reads XKB_DEFAULT_*.
_xkb() { localectl status 2>/dev/null | sed -n "s/^ *X11 $1: *//p"; }
: "${XKB_DEFAULT_LAYOUT:=$(_xkb Layout)}" "${XKB_DEFAULT_VARIANT:=$(_xkb Variant)}" "${XKB_DEFAULT_OPTIONS:=$(_xkb Options)}"
export XKB_DEFAULT_LAYOUT XKB_DEFAULT_VARIANT XKB_DEFAULT_OPTIONS

# Keep __pycache__ out of the stowed (symlinked) config dirs.
export PYTHONPYCACHEPREFIX="$HOME/.cache/python-pycache"

# glibc tuning: pin the trim threshold (stops qtile's heap ratcheting) + cap arenas.
export MALLOC_TRIM_THRESHOLD_=131072
export MALLOC_ARENA_MAX=2

export PATH="$HOME/bin:$HOME/.local/bin:$PATH"

# Distro qtile (Fedora RPM) first, the EL-style venv as fallback.
QTILE="$(command -v qtile || echo "$HOME/.local/venvs/qtile/bin/qtile")"
if [[ -x "$QTILE" ]]; then
  echo "[$(date)] Starting Qtile from $QTILE (wayland)" >> "$LOGFILE"
  exec "$QTILE" start -b wayland
else
  echo "[$(date)] ERROR: no qtile binary found" >> "$LOGFILE"
  exit 1
fi
