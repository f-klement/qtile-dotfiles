#!/usr/bin/env bash 

export PATH="/usr/local/bin:$PATH"

/usr/local/bin/dunst &

# KDE polkit agent (works with qtile)
if [ -x /usr/libexec/polkit-kde-authentication-agent-1 ]; then
    /usr/libexec/polkit-kde-authentication-agent-1 &
fi

# Theming (Rosé Pine, dark). gsd-xsettings turns these gsettings into XSETTINGS
# for every GTK/Chromium/Electron app, incl. ones launched later from rofi.
# NOTE: gtk-theme must be a ~/.themes dir name; "Adwaita:dark" resolves to LIGHT.
gsettings set org.gnome.desktop.interface gtk-theme        'rose-pine-gtk'
gsettings set org.gnome.desktop.interface icon-theme       'Papirus-Dark'
gsettings set org.gnome.desktop.interface cursor-theme     'BreezeX-RosePine-Linux'
gsettings set org.gnome.desktop.interface cursor-size      24
gsettings set org.gnome.desktop.interface font-name        'Cantarell 11'
gsettings set org.gnome.desktop.interface monospace-font-name 'JetBrains Mono Nerd Font 10'
xsetroot -cursor_name left_ptr

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

# Blank after 5 min; lock on idle/suspend.
xset s 300 -dpms
# NOTE: run xss-lock on the session's existing bus, not via dbus-run-session,
# or idle/inhibit signalling lands on a different bus than the rest of the session.
xss-lock -- ~/.config/qtile/lock_with_random_bg_x11.sh &

# User apps
if command -v brave-browser >/dev/null 2>&1; then brave-browser & else flatpak run com.brave.Browser & fi
flatpak run md.obsidian.Obsidian &
codium &
nautilus &
