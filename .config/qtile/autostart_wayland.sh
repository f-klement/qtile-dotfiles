#!/usr/bin/env bash

export PATH="/usr/local/bin:$PATH"
wlr-randr --output Virtual-1 --mode 1920x1200@60
/usr/local/bin/seatd -g seat
mako &

# Keyring (run *before* any app that needs secrets)
eval "$(gnome-keyring-daemon --start --components=pkcs11,secrets,ssh,gpg)"

# Policy-kit agent (package name: polkit-gnome)
polkit-kde-agent-1 &
gsettings set org.gnome.desktop.interface gtk-theme Adwaita:dark
# Set Session Variables and Theming

if [ ! -f /tmp/qtile_autostart_done ]; then
  export XDG_CURRENT_DESKTOP="Qtile:Wayland"
  touch /tmp/qtile_autostart_done
fi

if [ ! -f /tmp/qtile_darkmode_set ]; then
  export GTK_THEME=Adwaita:dark
  export GTK_APPLICATION_PREFERENCES=prefer-dark-theme=1
  export QT_STYLE_OVERRIDE=adwaita-dark #
  export QT_QPA_PLATFORMTHEME="qt5ct" #
  touch /tmp/qtile_darkmode_set
fi

# Tray apps
nm-applet &
#blueman-applet &

# Clipboard manager
copyq &

# Cursor + View Settings
export GTK_THEME=Adwaita:dark
export QTILE_CHECK_SKIP_STUBS=1
export XCURSOR_THEME="Dracula"
export XCURSOR_SIZE="24"
export WLR_RENDERER=vulkan

# wallpaper service
swaybg_random() {
  local dir=~/Pictures/Wallpapers
  local file=$(find "$dir" -type f \( -iname '*.jpg' -o -iname '*.png' \) | shuf -n1)
  swaybg -i "$file" -m fill

swaybg_random
while sleep 300; do
  swaybg_random
done &

# Wayland idle & lock: use swayidle with inline random-bg lock
swayidle \
  timeout 300 'bash -c "
    IMG=\$(find ~/Pictures/wallpapers -type f \\( -iname '\''*.jpg'\'' -o -iname '\''*.png'\'' \\) | shuf -n1)
    if [ -z \"\$IMG\" ]; then
      swaylock -C000000
    else
      swaylock -i \"\$IMG\"
    fi"' \
  before-sleep 'bash -c "
    IMG=\$(find ~/Pictures/wallpapers -type f \\( -iname '\''*.jpg'\'' -o -iname '\''*.png'\'' \\) | shuf -n1)
    if [ -z \"\$IMG\" ]; then
      swaylock -C000000
    else
      swaylock -i \"\$IMG\"
    fi"' &

