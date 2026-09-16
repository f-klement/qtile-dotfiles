#!/usr/bin/env bash
# Desktop-wide light/dark switch: Rosé Pine (dark) <-> Rosé Pine Dawn (light).
#   theme.sh toggle|dark|light   switch, re-theme everything, nudge running apps
#   theme.sh apply               re-apply the saved mode (autostart_x11.sh)
#   theme.sh status              print "dark" or "light"
# The mode lives in $XDG_STATE_HOME/theme-mode; qtile's config.py reads the same
# file to pick its palette and the sun/moon icon in the bar.
#
# What gets re-themed and how (see bootstrap 9.6 for the why of each route):
#   qtile bar/borders   config.py reads theme-mode      -> reload_config
#   GTK2/3 + Chromium   gsettings -> gsd-xsettings/XSETTINGS (live), settings.ini/gtkrc fallback
#   GTK4/libadwaita     gtk-4.0/gtk.css + settings.ini (new windows)
#   Qt5 native          qt5ct.conf + colors/<theme>.conf (next start)
#   Qt on KDE runtime   ~/.config/kdeglobals (next start)
#   kitty               current-theme.conf -> SIGUSR1 (live)
#   rofi / dunst        colors.rasi / dunstrc.d (live, dunstctl reload)
#   cursor              gsettings + ~/.icons/default + root window
#   Claude Code         ~/.claude/settings.json theme -> custom:<theme> (~/.claude/themes)
#   VSCodium, Obsidian  their own settings files (apps re-read them themselves)
set -euo pipefail

C="${XDG_CONFIG_HOME:-$HOME/.config}"
STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}"
STATE="$STATE_DIR/theme-mode"

current() { [ "$(cat "$STATE" 2>/dev/null)" = light ] && echo light || echo dark; }

case "${1:-toggle}" in
    status)     current; exit 0 ;;
    toggle)     [ "$(current)" = dark ] && MODE=light || MODE=dark ;;
    dark|light) MODE=$1 ;;
    apply)      MODE=$(current) ;;
    *) echo "usage: $(basename "$0") [toggle|dark|light|apply|status]" >&2; exit 2 ;;
esac

if [ "$MODE" = light ]; then
    THEME=rose-pine-dawn
    GTK_THEME=rose-pine-dawn-gtk
    ICON_THEME=Papirus-Light
    CURSOR_THEME=BreezeX-RosePineDawn-Linux
    PREFER_DARK=0
    CODIUM_THEME="Rosé Pine Dawn"
    OBSIDIAN_BASE=moonstone
else
    THEME=rose-pine
    GTK_THEME=rose-pine-gtk
    ICON_THEME=Papirus-Dark
    CURSOR_THEME=BreezeX-RosePine-Linux
    PREFER_DARK=1
    CODIUM_THEME="Rosé Pine Moon"
    OBSIDIAN_BASE=obsidian
fi

mkdir -p "$STATE_DIR"
echo "$MODE" > "$STATE"

# Generated files. rm first so a stow symlink into the repo becomes a real file
# instead of being written through (these targets are all git-ignored).
put()    { rm -f "$2"; cp "$1" "$2"; }
render() {
    rm -f "$2"
    sed -e "s|@THEME@|$THEME|g" -e "s|@GTK_THEME@|$GTK_THEME|g" \
        -e "s|@ICON_THEME@|$ICON_THEME|g" -e "s|@CURSOR_THEME@|$CURSOR_THEME|g" \
        -e "s|@PREFER_DARK@|$PREFER_DARK|g" "$1" > "$2"
}
put    "$C/kitty/$THEME.conf"          "$C/kitty/current-theme.conf"
put    "$C/rofi/colors-$THEME.rasi"    "$C/rofi/colors.rasi"
mkdir -p "$C/dunst/dunstrc.d"
put    "$C/dunst/colors-$THEME.conf"   "$C/dunst/dunstrc.d/50-colors.conf"
put    "$C/gtk-4.0/gtk-$THEME.css"     "$C/gtk-4.0/gtk.css"
put    "$C/kdeglobals.$THEME"          "$C/kdeglobals"
render "$C/gtk-3.0/settings.ini.in"    "$C/gtk-3.0/settings.ini"
render "$C/gtk-4.0/settings.ini.in"    "$C/gtk-4.0/settings.ini"
render "$C/qt5ct/qt5ct.conf.in"        "$C/qt5ct/qt5ct.conf"
render "$HOME/.gtkrc-2.0.in"           "$HOME/.gtkrc-2.0"

# GTK: gsd-xsettings turns these into XSETTINGS for every GTK/Chromium/Electron
# app, including ones launched later from rofi. Theme name MUST be a ~/.themes
# dir name ("Adwaita:dark" resolves to LIGHT via XSETTINGS).
gsettings set org.gnome.desktop.interface gtk-theme            "$GTK_THEME"
gsettings set org.gnome.desktop.interface icon-theme           "$ICON_THEME"
gsettings set org.gnome.desktop.interface cursor-theme         "$CURSOR_THEME"
gsettings set org.gnome.desktop.interface cursor-size          24
gsettings set org.gnome.desktop.interface font-name            'Cantarell 11'
gsettings set org.gnome.desktop.interface monospace-font-name  'JetBrains Mono Nerd Font 10'
# color-scheme only exists on GNOME >= 42 (portal prefers-color-scheme); no-op on EL8.
gsettings set org.gnome.desktop.interface color-scheme "prefer-$MODE" 2>/dev/null || true

# Cursor for non-GTK clients (read at their start) and the root window now.
mkdir -p "$HOME/.icons/default"
printf '[Icon Theme]\nName=Default\nComment=Default Cursor Theme\nInherits=%s\n' "$CURSOR_THEME" \
    > "$HOME/.icons/default/index.theme"
[ -n "${DISPLAY:-}" ] && XCURSOR_THEME=$CURSOR_THEME xsetroot -cursor_name left_ptr || true

# Claude Code: custom themes from ~/.claude/themes (stowed). settings.json is
# strict JSON, so round-trip it instead of sed.
python3 - "custom:$THEME" <<'PY'
import json, pathlib, sys
p = pathlib.Path.home() / ".claude" / "settings.json"
try:
    d = json.loads(p.read_text())
except FileNotFoundError:
    d = {}
if d.get("theme") != sys.argv[1]:
    d["theme"] = sys.argv[1]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=2) + "\n")
PY

# VSCodium (settings.json is JSONC -> sed the one key). Codium re-reads it live.
for f in "$C/VSCodium/User/settings.json" \
         "$HOME/.var/app/com.vscodium.codium/config/VSCodium/User/settings.json"; do
    [ -f "$f" ] && sed -i "s/\"workbench.colorTheme\": *\"[^\"]*\"/\"workbench.colorTheme\": \"$CODIUM_THEME\"/" "$f"
done

# Obsidian: base theme per vault ("obsidian" dark / "moonstone" light), the Rosé
# Pine CSS theme follows it. Obsidian reads appearance.json at start.
OBS_REG="$HOME/.var/app/md.obsidian.Obsidian/config/obsidian/obsidian.json"
[ -f "$OBS_REG" ] && python3 - "$OBS_REG" "$OBSIDIAN_BASE" <<'PY'
import json, pathlib, sys
for v in json.load(open(sys.argv[1]))["vaults"].values():
    p = pathlib.Path(v["path"]) / ".obsidian" / "appearance.json"
    if not p.is_file():
        continue
    d = json.loads(p.read_text())
    if d.get("theme") != sys.argv[2]:
        d["theme"] = sys.argv[2]
        p.write_text(json.dumps(d, indent=2) + "\n")
PY

[ "${1:-toggle}" = apply ] && exit 0

# Nudge what is already running (apply at session start has nothing to nudge).
dunstctl reload 2>/dev/null || true
pkill -USR1 -x kitty 2>/dev/null || true
QTILE="$HOME/.local/venvs/qtile/bin/qtile"
if [ -x "$QTILE" ] && pgrep -f "$QTILE start" >/dev/null; then
    "$QTILE" cmd-obj -o cmd -f reload_config >/dev/null 2>&1 || true
fi
