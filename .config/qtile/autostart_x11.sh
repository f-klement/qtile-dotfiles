#!/usr/bin/env bash 

export PATH="/usr/local/bin:$PATH"

/usr/local/bin/dunst &

# KDE polkit agent (works with qtile)
if [ -x /usr/libexec/polkit-kde-authentication-agent-1 ]; then
    /usr/libexec/polkit-kde-authentication-agent-1 &
fi

# Theming (Rosé Pine dark / Rosé Pine Dawn light, see bin/theme.sh): re-asserts
# the saved mode's gsettings (gsd-xsettings -> XSETTINGS for every GTK/Chromium/
# Electron app) and regenerates the per-toolkit files. The bar's sun/moon toggles.
~/bin/theme.sh apply

# xdg-desktop-portal-gtk draws the file pickers for flatpaks/portal-aware apps.
# It is a plain GTK3 systemd --user service that outlives X sessions, so it can
# sit on a stale DISPLAY or keep a stale copy of the theme CSS in memory (which
# is how the pickers stayed light after the theme swap). Point the user manager
# at this session's display and start it fresh; nothing has a portal session
# open yet at this point, so the restart is invisible.
dbus-update-activation-environment --systemd DISPLAY XAUTHORITY
systemctl --user restart xdg-desktop-portal-gtk.service xdg-desktop-portal.service 2>/dev/null &

# Toolkit env lives in bin/starting-qtile.sh so all spawned apps inherit it.
xprop -root -set _NET_WM_DESKTOP_ENVIRONMENT "Qtile"
export XDG_CURRENT_DESKTOP=Qtile
export DESKTOP_SESSION=qtile

# Secrets: KWallet is D-Bus activated, but pam_kwallet5.so only opens a socket
# (kwallet5.socket) with the login password at SDDM auth time - it still needs
# pam_kwallet_init to read the env var it sets (PAM_KWALLET5_LOGIN) and forward
# it over that socket. Plasma sessions do this via plasma-kwallet-pam.service,
# which never runs here since we're not a Plasma session. Without it kdewallet
# stays locked and every app prompts for its password on first use.
/usr/libexec/pam_kwallet_init &

# Tray
nm-applet &
copyq &
export QTILE_CHECK_SKIP_STUBS=1

# Compositor (X11). NOT picom (it stripes translucent windows on this Xvnc).
# fastcompmgr preferred, xcompmgr -n fallback; opacity is driven by config.py.
if command -v fastcompmgr >/dev/null 2>&1; then
    fastcompmgr &
else
    xcompmgr -n &
fi

# Wallpaper: random on start, then a fresh one every 5 min (see bin/wallpaper.sh).
~/bin/wallpaper.sh
(
  while sleep 300; do
    ~/bin/wallpaper.sh
  done
) &

# Blank after 1 h; lock on idle/suspend. This is a long-lived private server
# session, not a shared desktop, so idle locking is deliberately relaxed.
xset s 3600 -dpms
# NOTE: run xss-lock on the session's existing bus, not via dbus-run-session,
# or idle/inhibit signalling lands on a different bus than the rest of the session.
xss-lock -- ~/.config/qtile/lock_with_random_bg_x11.sh &

# User apps
if command -v brave-browser >/dev/null 2>&1; then brave-browser & else flatpak run com.brave.Browser & fi
flatpak run md.obsidian.Obsidian &
codium &
nautilus &
