#!/usr/bin/env bash
# Screenshots on this xrdp/Xvnc desktop.
#   gui  - flameshot region selector   full - whole screen -> ~/Pictures   clip - -> clipboard
# Gotchas: flameshot's resident daemon caches the (xrdp-changing) geometry -> kill &
# start fresh each time. Its portal modes need gnome-shell (dead) -> use ImageMagick
# for full/clip. flameshot 14 gui also needs useX11LegacyScreenshot=true in its ini
# (~/.var, not stowed), so assert that key before each launch.
mode="${1:-gui}"
ini="$HOME/.var/app/org.flameshot.Flameshot/config/flameshot/flameshot.ini"
ensure_x11_legacy() {
  grep -qx 'useX11LegacyScreenshot=true' "$ini" 2>/dev/null && return
  mkdir -p "${ini%/*}"
  if grep -q '^\[General\]' "$ini" 2>/dev/null; then
    sed -i '/^useX11LegacyScreenshot=/d; /^\[General\]/a useX11LegacyScreenshot=true' "$ini"
  else
    { printf '[General]\nuseX11LegacyScreenshot=true\n'; if [ -f "$ini" ]; then cat "$ini"; fi; } \
      > "$ini.tmp" && mv "$ini.tmp" "$ini"
  fi
}
case "$mode" in
  gui)
    flatpak kill org.flameshot.Flameshot 2>/dev/null || true
    for _ in $(seq 10); do
      flatpak ps --columns=application 2>/dev/null | grep -q '^org.flameshot.Flameshot$' || break
      sleep 0.2
    done
    ensure_x11_legacy
    exec flatpak run org.flameshot.Flameshot gui
    ;;
  full)
    out="$HOME/Pictures/screenshot-$(date +%Y%m%d-%H%M%S).png"
    import -window root "$out" && notify-send -i camera-photo "Screenshot saved" "$out"
    ;;
  clip)
    import -window root png:- | copyq copy image/png - \
      && notify-send -i camera-photo "Screenshot" "copied to clipboard"
    ;;
  *) echo "usage: $0 [gui|full|clip]" >&2; exit 2 ;;
esac
