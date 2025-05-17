#!/usr/bin/env bash 

export PATH="/usr/local/bin:$PATH"

# Start notification daemon
/usr/local/bin/dunst &  

# ── Keyring (run *before* any app that needs secrets) ────────────────────
eval "$(gnome-keyring-daemon --start --components=pkcs11,secrets,ssh,gpg)"

# ── Policy-kit agent (package name: polkit-gnome) ────────────────────────
/usr/libexec/polkit-gnome-authentication-agent-1 &


# ── Tray apps ────────────────────────────────────────────────────────────
nm-applet &
#blueman-applet &              # requires: sudo dnf install blueman (not to be found on these corpo distros)

# screenshots
flatpak run org.flameshot.Flameshot &
# ── Clipboard manager ────────────────────────────────────────────────────
copyq &                       # dnf install copyq

# ── Cursor + GTK theme + View Settings ───────────────────────────────────
export GTK_THEME=Adwaita-dark
export QTILE_CHECK_SKIP_STUBS=1
export XCURSOR_THEME="Dracula"
export XCURSOR_SIZE="24"

# compositor for transparency/shadows (X11 sessions)
#picom -b --config ~/.config/picom/picom.conf

# wallpaper service
variety --resume &

# screen-locker on suspend/idle (X11)
# ── blank after 5 min ─────────────────────────────────────────────────────
xset s 300 -dpms

# ── on suspend/idle, pick a random lock-image and run i3lock ──────────────
# blank after 5 min
xset s 300 -dpms
# lock using our script
xss-lock -- ~/.config/qtile/lock_with_random_bg.sh &

