#!/usr/bin/env python3
"""Keybindings cheat sheet pane (SUPER + K). Replaces scripts/KeyHints.sh,
a yad table with a hand-maintained copy of the binds that drifted from the
real config.

REWRITTEN (2026-10-12): the original read hypr/keybinds.lua +
keybinds_laptop.lua by executing them with `lua` against a stub `hl` object
that recorded every hl.bind() call. That native-Lua config never actually
worked on this host -- this build (Hyprland 0.51.1 / hyprlang 0.6.4, built
from source against Fedora 44's stable libs) has no Lua config support at
all (see hyprland.conf's own header comment for the full story). The real
keybinds live in hypr/keybinds.conf, plain hyprlang `bind = MODS, KEY,
DISPATCHER, ARGS` syntax -- parsed directly here instead, with `### NAME
###`-style section headers (the convention keybinds.conf actually uses,
confirmed via grep, not the old `---- NAME ----` one) and `$var`
substitution for keybinds.conf's own $mainMod/$browser/etc. definitions.

  KeybindsPane.py           open/close the pane (see pane.py)
  KeybindsPane.py --dump    print the parsed binds as text (debugging)
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pane import Pane  # noqa: E402

HYPR = os.path.expanduser("~/.config/hypr")
FILE = f"{HYPR}/keybinds.conf"

MOD_NAMES = {"SUPER": "\U000F05B3 Super", "SHIFT": "Shift", "CTRL": "Ctrl", "ALT": "Alt"}  # md-microsoft_windows
KEY_NAMES = {
    "left": "←", "right": "→", "up": "↑", "down": "↓", "Return": "Enter", "Space": "Space", "Tab": "Tab",
    "Escape": "Esc", "Print": "PrtSc", "period": ".", "comma": ",", "bracketleft": "[", "bracketright": "]",
    "mouse_down": "Scroll ↓", "mouse_up": "Scroll ↑", "mouse:272": "LMB", "mouse:273": "RMB",
    "XF86AudioRaiseVolume": "Vol +", "XF86AudioLowerVolume": "Vol −", "XF86AudioMute": "Mute",
    "XF86AudioMicMute": "Mic mute", "XF86AudioPlay": "Play", "XF86AudioPause": "Pause", "XF86AudioNext": "Next",
    "XF86AudioPrev": "Prev", "XF86AudioStop": "Stop", "XF86Sleep": "Sleep", "XF86RFKill": "Airplane",
    "XF86MonBrightnessUp": "Brightness +", "XF86MonBrightnessDown": "Brightness −",
    "XF86KbdBrightnessUp": "Kbd light +", "XF86KbdBrightnessDown": "Kbd light −", "XF86TouchpadToggle": "Touchpad",
}
DIRS = {"l": "left", "r": "right", "u": "up", "d": "down"}

# exec commands (after $var substitution) -> readable text. Matched by
# substring since $browser resolves to a long inline shell fallback.
CMD_DESC = [
    ("hyprctl reload", "Reload Hyprland config"),
    ("rofi -show run", "Run prompt (rofi)"),
    ("pkill rofi || rofi -show drun", "App launcher (rofi)"),
    ("kitty", "Terminal (kitty)"),
    ("codium", "Editor (VSCodium)"),
    ("dolphin", "Files (Dolphin)"),
    ("brave-browser", "Browser (Brave)"),
    ("md.obsidian.Obsidian", "Obsidian"),
    ("loginctl lock-session", "Lock screen"),
    ("wlogout", "Logout menu"),
    ("screenshot.sh gui", "Screenshot: select region"),
    ("screenshot.sh clip", "Screenshot: full screen to clipboard"),
    ("screenshot.sh full", "Screenshot: full screen to ~/Pictures"),
    ("pactl set-sink-volume @DEFAULT_SINK@ +5%", "Volume up"),
    ("pactl set-sink-volume @DEFAULT_SINK@ -5%", "Volume down"),
    ("pactl set-sink-mute", "Mute"),
    ("pactl set-source-mute", "Mute microphone"),
    ("brightnessctl set 5%+", "Brightness up"),
    ("brightnessctl set 5%-", "Brightness down"),
    ("general:layout", "Toggle dwindle/master layout"),
]


def parse():
    """Read keybinds.conf directly -- plain hyprlang syntax, not Lua."""
    binds = []
    try:
        with open(FILE) as f:
            lines = f.readlines()
    except OSError:
        return binds

    variables = {}
    for raw in lines:
        m = re.match(r"^\$(\w+)\s*=\s*(.+?)\s*$", raw)
        if m:
            variables[m.group(1)] = m.group(2)

    def resolve(s):
        for _ in range(3):  # a couple passes in case a var references another
            new = s
            for name, val in variables.items():
                new = new.replace(f"${name}", val)
            if new == s:
                break
            s = new
        return s

    section = "Other"
    for lineno, raw in enumerate(lines, 1):
        s = raw.rstrip("\n")
        hdr = re.match(r"^###\s+(.+?)\s+###$", s.strip())
        if hdr:
            section = hdr.group(1)
            continue
        m = re.match(r"^(bind[a-z]*)\s*=\s*([^,]*),\s*([^,]+?)\s*,\s*(.+)$", s.strip())
        if not m:
            continue
        _bindtype, mods_raw, key, rest = m.groups()
        mods = resolve(mods_raw).split()
        key = resolve(key).strip()
        full_key = "+".join(mods + [key]) if mods else key
        dispatcher, _, arg = rest.partition(",")
        dispatcher = dispatcher.strip().rstrip(",")
        arg = resolve(arg.strip())
        binds.append({
            "key": full_key, "path": dispatcher, "args": [arg] if arg else [],
            "section": section, "comment": "", "line": lineno,
        })
    return binds


def describe(b):
    if b["comment"]:
        return b["comment"][0].upper() + b["comment"][1:]
    path, args = b["path"], b["args"]
    a = args[0] if args else ""

    if path == "exec":
        for needle, desc in CMD_DESC:
            if needle in a:
                return desc
        return a
    if path in ("togglefloating",):
        return "Toggle floating"
    if path == "fullscreen":
        return "Fullscreen"
    if path == "forcekillactive":
        return "Kill window"
    if path == "killactive":
        return "Close window"
    if path == "pseudo":
        return "Pseudo-tile (dwindle)"
    if path == "togglegroup":
        return "Toggle window group"
    if path == "cyclenext":
        return "Next window in layout"
    if path == "changegroupactive":
        return "Next window in group"
    if path == "togglesplit":
        return "Toggle split"
    if path == "exit":
        return "Exit Hyprland"
    if path == "movefocus":
        return f"Focus {DIRS.get(a, a)}"
    if path == "movewindow":
        if a in DIRS:
            return f"Move window {DIRS[a]}"
        if a.startswith("mon:"):
            return "Move window to next monitor" if "+" in a else "Move window to previous monitor"
        return "Drag window" if not a else f"Move window {a}"
    if path == "resizewindow":
        return "Resize window (drag)"
    if path == "resizeactive":
        m = re.match(r"^(-?\d+)\s+(-?\d+)$", a)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            return "Grow window " + ("←" if x < 0 else "→" if x > 0 else "↑" if y < 0 else "↓")
        return "Resize window"
    if path == "focusmonitor":
        return "Next monitor" if a == "+1" else "Previous monitor" if a == "-1" else f"Focus monitor {a}"
    if path == "workspace":
        return f"Go to workspace {a}"
    if path == "movetoworkspace":
        return f"Move window to workspace {a}"
    return path + (f" {a}" if a else "")


def key_parts(key):
    parts = [k.strip() for k in key.split("+")]
    return [MOD_NAMES.get(p, KEY_NAMES.get(p, p)) for p in parts]


def collapse(rows):
    """Fold 'SUPER + 1' .. 'SUPER + 0' style runs into one row."""
    out, seen = [], {}
    for r in rows:
        m = re.match(r"^(.*?)(\d)$", r["key"])
        n = re.sub(r"\d+", "N", r["desc"]) if m else None
        sig = (m.group(1), n) if m else None
        if sig and sig in seen:
            seen[sig]["keys"].append(m.group(2))
            continue
        if sig:
            r = dict(r, keys=[m.group(2)], prefix=m.group(1), tmpl=n)
            seen[sig] = r
        out.append(r)
    for r in out:
        if r.get("keys") and len(r["keys"]) > 2:
            r["key"] = f"{r['prefix']}{r['keys'][0]} … {r['keys'][-1]}"
            r["desc"] = r["tmpl"].replace("N", f"{r['keys'][0]}–{r['keys'][-1]}")
    return out


def load():
    binds = parse()
    sections = {}
    for b in binds:
        sections.setdefault(b["section"], []).append(dict(key=b["key"], desc=describe(b),
                                                          cmd=str(b["args"][0]) if b["path"] == "exec" else ""))
    return {name: collapse(rows) for name, rows in sections.items()}


def make_pane():
    """(Pane, build) -- run standalone via pane_main(), or hosted by hyprpanes.py."""
    css = """
    .kbd { font-size: 11px; }
    .kbd.mod { font-weight: bold; }
    .desc { font-size: 12px; }
    .sec-title { font-size: 11px; font-weight: bold; letter-spacing: 1px; margin-bottom: 4px; }
    """
    pn = Pane("hypr.keybinds-pane", anchor="center", css=css)

    try:
        sections = load()
        error = None
    except Exception as e:  # noqa: BLE001
        sections, error = {}, str(e)

    def build(pn, root):
        Gtk, L = pn.Gtk, pn.label
        head = pn.box(spacing=12)
        head.append(L("Keybindings", "title", valign=Gtk.Align.CENTER))
        head.append(L("from keybinds.conf", "muted small", valign=Gtk.Align.CENTER, hexpand=True))
        entry = Gtk.SearchEntry(placeholder_text="filter…", width_chars=24)
        head.append(entry)
        root.append(head)
        if error:
            root.append(L(f"Could not parse keybinds: {error}", "bad", margin_top=10))
            return

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True,
                                      propagate_natural_width=True, max_content_height=900, margin_top=10)
        cols = pn.box(spacing=14, valign=Gtk.Align.START)
        scroller.set_child(cols)
        root.append(scroller)

        def render(filter_text=""):
            pn.clear(cols)
            q = filter_text.lower().strip()
            # two columns, balanced by row count, sections kept whole
            visible = []
            for name, rows in sections.items():
                rows = [r for r in rows if not q or q in r["key"].lower() or q in r["desc"].lower() or q in r["cmd"].lower()]
                if rows:
                    visible.append((name, rows))
            columns = [pn.box(vertical=True, spacing=10, hexpand=True, valign=Gtk.Align.START) for _ in range(2)]
            heights = [0, 0]
            for name, rows in visible:
                ci = 0 if heights[0] <= heights[1] else 1     # shorter column takes the next section
                heights[ci] += len(rows) + 2
                card = pn.card(spacing=3)
                card.append(L(name.upper(), "sec-title muted"))
                grid = Gtk.Grid(column_spacing=12, row_spacing=3)
                for i, r in enumerate(rows):
                    chips = pn.box(spacing=3, valign=Gtk.Align.CENTER)
                    for part in key_parts(r["key"]):
                        c = L(part, "kbd", xalign=0.5)
                        if part in MOD_NAMES.values():
                            c.add_css_class("mod")
                        chips.append(c)
                    grid.attach(chips, 0, i, 1, 1)
                    desc = L(r["desc"], "desc", hexpand=True, ellipsize=3, max_width_chars=44)
                    if r["cmd"]:
                        desc.set_tooltip_text(r["cmd"])
                    grid.attach(desc, 1, i, 1, 1)
                card.append(grid)
                columns[ci].append(card)
            for c in columns:
                if c.get_first_child() is not None:
                    cols.append(c)
            if not visible:
                cols.append(L("nothing matches", "muted"))

        render()
        entry.connect("search-changed", lambda e: render(e.get_text()))
        entry.grab_focus()

    return pn, build


def pane_main():
    pn, build = make_pane()
    pn.run(build)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dump":
        for name, rows in load().items():
            print(f"== {name}")
            for r in rows:
                print(f"  {r['key']:28} {r['desc']}")
    else:
        pane_main()
