#!/usr/bin/env bash 

# Start notification daemon
/usr/local/bin/dunst &    
nm-applet &

bash eval $(/usr/bin/gnome-keyring-daemon --start --components=pkcs11,secrets,ssh,gpg) &

# policy-kit agent for graphical privilege prompts
/usr/libexec/polkit-gnome-authentication-agent-1 &

# clipboard manager
copyq &

# view settings
#(sleep 2 && xfsettingsd --daemon) &
export GTK_THEME=Adwaita-dark
export QTILE_CHECK_SKIP_STUBS=1

# compositor for transparency/shadows (X11 sessions)
#picom -b --config ~/.config/picom/picom.conf

# bluetooth tray
blueman-applet &

# screenshots
flatpak run org.flameshot.Flameshot &

# wallpaper service
variety --resume &

# screen-locker on suspend/idle (X11)
xss-lock -- i3lock -c 000000 &
