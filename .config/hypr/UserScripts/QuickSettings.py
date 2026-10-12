#!/usr/bin/env python3
"""Quick settings pane (waybar audio module, left-click): the GNOME-style
"everything you'd otherwise hunt through three menus for" panel.

  sliders  brightness (brightnessctl), volume + mic (wpctl, i.e. WirePlumber)
  pickers  output / input device (pw-dump for the list, wpctl set-default)
  tiles    dark/light theme (DarkLight.sh), night light (hyprsunset via
           NightlightToggle.sh), blur (PowerModeCommon.sh's apply_blur_on/off),
           Wi-Fi (nmcli radio), Bluetooth (BluetoothToggle.sh), game mode
           (GameMode.sh: animations/gaps off)
  footer   wallpaper picker (WallpaperSelect.sh), random wallpaper
           (WallpaperRandom.sh), pavucontrol

Before this (2026-09-15) these were scattered across unrelated modules:
nightlight on dark/light's right-click, blur on the battery's middle-click,
wallpaper on the launcher's middle-click; backlight had no click at all and
the mic had its own bar icon. The bar now shows one audio icon (with the
mic state folded into it) and this pane behind it; pavucontrol stays on
right-click as the detailed app.

The caffeine toggle is deliberately NOT here: waybar's idle_inhibitor
module holds the Wayland idle-inhibit itself and can't be flipped from
outside, and a second (systemd-inhibit) mechanism would show one state in
the bar and another here.
"""

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pane import Pane, sh, spawn, clean_env  # noqa: E402

SCRIPTS = os.path.expanduser("~/.config/hypr/scripts")
THEME_STATE = os.path.expanduser("~/.local/state/theme-mode")

# Nerd Font glyphs (names verified in the installed JetBrainsMono Nerd Font)
BRIGHTNESS = "\U000F00DF"   # md-brightness_6
VOLUME = "\U000F057E"       # md-volume_high
VOLUME_MUTED = "\U000F0581" # md-volume_off
MIC = "\U000F036C"          # md-microphone
MIC_MUTED = "\U000F036D"    # md-microphone_off
THEME = "\U000F050E"        # md-theme_light_dark
NIGHTLIGHT = "\U000F059A"   # md-weather_sunset
BLUR = "\U000F00B5"         # md-blur
WIFI = "\U000F05A9"         # md-wifi
WIFI_OFF = "\U000F05AA"     # md-wifi_off
BT = "\U000F00AF"           # md-bluetooth
GAME = "\U000F0297"         # md-gamepad_variant
SPEAKER = "\U000F04C3"      # md-speaker


# --------------------------------------------------------------- state ---

def brightness():
    parts = sh(["brightnessctl", "-m"]).strip().split(",")
    try:
        return int(parts[3].rstrip("%"))
    except (IndexError, ValueError):
        return None


def volume(target):
    out = sh(["wpctl", "get-volume", target])
    m = re.search(r"Volume: ([\d.]+)( \[MUTED\])?", out)
    return (round(float(m.group(1)) * 100), bool(m.group(2))) if m else (None, False)


def audio_devices():
    """{'sink': [(id, desc, is_default)], 'source': [...]} from pw-dump."""
    try:
        objs = json.loads(sh(["pw-dump"]) or "[]")
    except ValueError:
        objs = []
    defaults = {}
    for o in objs:
        if o.get("type") == "PipeWire:Interface:Metadata":
            for m in o.get("metadata", []):
                if m.get("key") in ("default.audio.sink", "default.audio.source"):
                    defaults[m["key"].split(".")[-1]] = m["value"]["name"]
    devs = {"sink": [], "source": []}
    for o in objs:
        props = o.get("info", {}).get("props", {}) if o.get("type") == "PipeWire:Interface:Node" else {}
        cls = props.get("media.class")
        if cls in ("Audio/Sink", "Audio/Source"):
            kind = "sink" if cls == "Audio/Sink" else "source"
            name = props.get("node.name", "")
            devs[kind].append((o["id"], props.get("node.description") or props.get("node.nick") or name,
                               name == defaults.get(kind)))
    return devs


def hypr_bool(opt):
    # `hyprctl -j getoption` returns the value under "int" (confirmed live:
    # {"option": "...", "int": 1, "set": true}), not "bool" -- the latter
    # key doesn't exist, so .get("bool") always silently returned None/False
    # regardless of actual state. Caught by testing live, not assumed.
    try:
        return bool(json.loads(sh(["hyprctl", "-j", "getoption", opt])).get("int"))
    except (ValueError, AttributeError):
        return False


# Keyed by "light"/"dark" (qtile's theme-mode file convention), not a
# palette name directly -- the reference repo's own file held the palette
# name as-is. Same fix as pane.py's palette().
THEME_LABELS = {"dark": "Rosé Pine Moon", "light": "Rosé Pine Dawn"}


def theme_mode():
    try:
        with open(THEME_STATE) as f:
            return f.read().strip()
    except OSError:
        return ""


def wifi():
    on = sh(["nmcli", "radio", "wifi"]).strip() == "enabled"
    ssid = ""
    # --rescan no: without it nmcli kicks off a Wi-Fi scan whenever the last
    # one is stale and blocks for it -- the pane took 4-5 s to appear (2026-09-16)
    for line in sh(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi", "list", "--rescan", "no"]).splitlines():
        if line.startswith("yes:"):
            ssid = line[4:]
    return on, ssid


def bluetooth():
    out = sh(["bluetoothctl", "show"])
    return "Powered: yes" in out, len(re.findall(r"^Device ", sh(["bluetoothctl", "devices", "Connected"]), re.M))


# ---------------------------------------------------------------- pane ---

def make_pane():
    """(Pane, build) -- run standalone via pane_main(), or hosted by hyprpanes.py."""
    css = """
    .tiles button.tile { min-width: 0; }
    dropdown button { padding: 2px 8px; font-size: 12px; }
    dropdown popover { background-color: transparent; }
    button.slider-btn { padding: 2px 0; min-width: 34px; margin-right: -4px; }
    """
    pn = Pane("hypr.quick-settings", anchor="right", css=css, width=520)

    def build(pn, root):
        Gtk, L = pn.Gtk, pn.label

        head = pn.box(spacing=12)
        head.append(L("Quick settings", "title", hexpand=True))
        root.append(head)

        # -- sliders
        card = pn.card(spacing=6, margin_top=10)
        b = brightness()
        if b is not None:
            card.append(pn.slider(b, lambda v: subprocess.run(["brightnessctl", "-q", "set", f"{max(1, round(v))}%"], env=clean_env()),
                                  icon=BRIGHTNESS))
        vol, muted = volume("@DEFAULT_AUDIO_SINK@")
        if vol is not None:
            row = pn.slider(vol, lambda v: subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{round(v)}%"], env=clean_env()),
                            icon=None, hi=150)
            mute = pn.button(VOLUME_MUTED if muted else VOLUME,
                             lambda: (subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"], env=clean_env()), pn.rebuild()),
                             cls="flat slider-btn " + ("bad" if muted else "accent"))
            mute.set_tooltip_text("Toggle mute")
            row.prepend(mute)
            card.append(row)
        mvol, mmuted = volume("@DEFAULT_AUDIO_SOURCE@")
        if mvol is not None:
            row = pn.slider(mvol, lambda v: subprocess.run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", f"{round(v)}%"], env=clean_env()),
                            icon=None)
            mute = pn.button(MIC_MUTED if mmuted else MIC,
                             lambda: (subprocess.run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle"], env=clean_env()), pn.rebuild()),
                             cls="flat slider-btn " + ("bad" if mmuted else "accent"))
            mute.set_tooltip_text("Toggle microphone mute")
            row.prepend(mute)
            card.append(row)
        root.append(card)

        # -- device pickers
        devs = audio_devices()
        pick = Gtk.Grid(column_spacing=10, row_spacing=6, margin_top=8)
        for r, (kind, title) in enumerate((("sink", "Output"), ("source", "Input"))):
            items = devs[kind]
            if not items:
                continue
            pick.attach(L(title, "muted", width_chars=7), 0, r, 1, 1)
            dd = Gtk.DropDown.new_from_strings([d[1] for d in items])
            dd.set_hexpand(True)
            for i, d in enumerate(items):
                if d[2]:
                    dd.set_selected(i)

            def changed(dd, _p, items=items):
                subprocess.run(["wpctl", "set-default", str(items[dd.get_selected()][0], env=clean_env())])
            dd.connect("notify::selected", changed)
            pick.attach(dd, 1, r, 1, 1)
        root.append(pick)

        # -- tiles
        root.append(pn.section("Toggles"))
        grid = Gtk.Grid(column_spacing=8, row_spacing=8, column_homogeneous=True)
        grid.add_css_class("tiles")
        mode = theme_mode()
        night = bool(sh(["pidof", "hyprsunset"]).strip())
        blur = hypr_bool("decoration:blur:enabled")
        won, ssid = wifi()
        bon, bconn = bluetooth()
        game = not hypr_bool("animations:enabled")

        def after(cmd, delay=400):
            """run a toggle script, then re-read state once it had time to apply"""
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=clean_env())
            pn.GLib.timeout_add(delay, lambda: (pn.rebuild(), False)[1])

        tiles = [
            # DarkLight.sh doesn't exist on this host -- qtile's own
            # ~/bin/theme.sh toggle is the shared mechanism (re-themes both
            # sessions the same way qtile's own toggle does).
            (THEME, "Theme", True, THEME_LABELS.get(mode, "Rose Pine"),
             lambda: after([os.path.expanduser("~/bin/theme.sh"), "toggle"], 1500)),
            # NightlightToggle.sh doesn't exist -- inline pidof/spawn/pkill
            # toggle of hyprsunset itself (4000K, a reasonable warm default).
            (NIGHTLIGHT, "Night light", night, "hyprsunset on" if night else "off",
             lambda: after(["bash", "-c", "pidof hyprsunset >/dev/null && pkill hyprsunset || hyprsunset -t 4000 &"])),
            # PowerModeCommon.sh doesn't exist -- direct hyprctl keyword,
            # same effect as its apply_blur_on/off functions.
            (BLUR, "Blur", blur, "on" if blur else "off",
             lambda: after(["hyprctl", "keyword", "decoration:blur:enabled", "0" if blur else "1"])),
            (WIFI if won else WIFI_OFF, "Wi-Fi", won, ssid or ("on, not connected" if won else "off"),
             lambda: after(["nmcli", "radio", "wifi", "off" if won else "on"], 800)),
            # BluetoothToggle.sh doesn't exist -- rfkill, same as qtile's own
            # BluetoothIcon widget (config.py) uses for this exact toggle.
            (BT, "Bluetooth", bon, (f"{bconn} connected" if bconn else "on") if bon else "off",
             lambda: after(["rfkill", "toggle", "bluetooth"], 800)),
            # GameMode.sh doesn't exist -- direct hyprctl keyword toggling
            # the one thing qtile's own "game mode" concept never had an
            # equivalent for anyway (animations off for perf).
            (GAME, "Game mode", game, "animations off" if game else "animations on",
             lambda: after(["hyprctl", "keyword", "animations:enabled", "0" if not game else "1"], 1500)),
        ]
        for i, (ic, name, active, sub, fn) in enumerate(tiles):
            grid.attach(pn.tile(ic, name, active, fn, sub), i % 3, i // 3, 1, 1)
        root.append(grid)

        foot = pn.box(spacing=8, cls="footer")
        foot.append(L("", hexpand=True))
        # WallpaperSelect.sh (interactive rofi picker) and WallpaperRandom.sh
        # don't exist on this host -- qtile's ~/bin/wallpaper.sh (shared
        # between sessions) only does random selection, no picker UI, so
        # there's one button here instead of two. Pane stays open so you can
        # re-roll until one sticks.
        foot.append(pn.button("Random wallpaper", lambda: spawn([os.path.expanduser("~/bin/wallpaper.sh")])))
        foot.append(pn.button("pavucontrol", lambda: (spawn(["pavucontrol"]), pn.close())))
        root.append(foot)

    return pn, build


def pane_main():
    pn, build = make_pane()
    pn.run(build)


if __name__ == "__main__":
    pane_main()
