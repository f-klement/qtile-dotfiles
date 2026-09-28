#!/usr/bin/env bash
# qtile Wayland session autostart (startup_once in config.py). Counterpart of
# autostart_x11.sh; the session env comes from bin/starting-qtile-wayland.sh.

export PATH="$HOME/bin:$HOME/.local/bin:/usr/local/bin:$PATH"

# Hand this session to the systemd/D-Bus activation env. WAYLAND_DISPLAY and
# DISPLAY (Xwayland) only exist now that qtile is up. Anything D-Bus activated
# (portals, kitty via xdg-open, ...) would otherwise see Plasma's old values.
dbus-update-activation-environment --systemd \
  WAYLAND_DISPLAY DISPLAY XDG_CURRENT_DESKTOP XDG_SESSION_DESKTOP XDG_SESSION_TYPE \
  DESKTOP_SESSION QT_QPA_PLATFORM QT_QPA_PLATFORMTHEME QT_WAYLAND_DISABLE_WINDOWDECORATION \
  MOZ_ENABLE_WAYLAND ELECTRON_OZONE_PLATFORM_HINT XCURSOR_THEME XCURSOR_SIZE PYTHONPYCACHEPREFIX

# Portals are long-lived systemd --user services. The user manager lingers
# (podman), so they can still hold a previous (Plasma) session's env and backend
# choice. Stop the backends and restart the frontend: it re-reads
# qtile-portals.conf (gtk file pickers/settings, wlr screenshot/screencast) and
# activates the backends in this session's env.
( systemctl --user stop xdg-desktop-portal-gtk.service xdg-desktop-portal-wlr.service \
                        xdg-desktop-portal-kde.service 2>/dev/null
  systemctl --user restart xdg-desktop-portal.service 2>/dev/null ) &

# Outputs: kanshi applies the matching profile from ~/.config/kanshi/config
# (positions, the rotated portrait panel) and follows dock/undock. qtile
# re-runs generate_screens on every change.
command -v kanshi >/dev/null && kanshi &

# Theming (Rosé Pine dark / Dawn light, see bin/theme.sh). Native Wayland GTK
# reads gsettings directly, no XSETTINGS daemon needed.
~/bin/theme.sh apply

# Notifications (dunst is a native layer-shell client on Wayland).
dunst &

# Polkit agent: kf6 path on Fedora 40+, plain libexec on EL.
for agent in /usr/libexec/kf6/polkit-kde-authentication-agent-1 \
             /usr/libexec/polkit-kde-authentication-agent-1; do
  [ -x "$agent" ] && { "$agent" & break; }
done

# Secrets: KWallet (ksecretd) is D-Bus activated and unlocked by pam_kwallet at
# the SDDM login, the same wallet the Plasma session uses. Nothing to start.

# Tray (StatusNotifier in the bar; nm-applet needs --indicator for SNI).
nm-applet --indicator &
copyq &
export QTILE_CHECK_SKIP_STUBS=1

# Wallpaper: random on start, then a fresh one every 5 min (swaybg, see bin/wallpaper.sh).
~/bin/wallpaper.sh
(
  while sleep 300; do
    ~/bin/wallpaper.sh
  done
) &

# Lock after 5 min idle, before suspend, and on `loginctl lock-session`;
# screens off one minute after locking. -w: suspend waits until the lock is up.
# wlopm = DPMS (output-power protocol). NOT wlr-randr --off: that removes the
# output, and qtile would reshuffle its groups as if the monitor was unplugged.
swayidle -w \
  timeout 300 ~/.config/qtile/lock_with_random_bg_wayland.sh \
  timeout 360 'wlopm --off "*"' resume 'wlopm --on "*"' \
  before-sleep ~/.config/qtile/lock_with_random_bg_wayland.sh \
  lock ~/.config/qtile/lock_with_random_bg_wayland.sh &

# User apps
if command -v brave-browser >/dev/null 2>&1; then brave-browser & else flatpak run com.brave.Browser & fi
flatpak run md.obsidian.Obsidian &
codium &
if command -v nautilus >/dev/null 2>&1; then nautilus & else dolphin & fi
