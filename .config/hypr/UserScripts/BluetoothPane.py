#!/usr/bin/env python3
"""Bluetooth pane for waybar's bluetooth module (left-click). The everyday
case -- power on/off, (re)connect a known device, see its battery -- without
opening blueman-manager, which stays on right-click for pairing and
everything else. Talks to BlueZ through bluetoothctl, the same thing
scripts/BluetoothToggle.sh uses (rfkill deliberately not used, see there).
"""

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pane import Pane, sh, spawn, clean_env  # noqa: E402

# Nerd Font glyphs (names verified in the installed JetBrainsMono Nerd Font)
BT_ON = "\U000F00AF"       # md-bluetooth
BT_OFF = "\U000F00B2"      # md-bluetooth_off
BT_CONN = "\U000F00B1"     # md-bluetooth_connect
DEV_ICONS = {              # BlueZ "Icon:" -> glyph
    "audio-headset": "\U000F02CB",      # md-headset
    "audio-headphones": "\U000F02CB",   # md-headset
    "audio-card": "\U000F04C3",         # md-speaker
    "input-keyboard": "\U000F030C",     # md-keyboard
    "input-mouse": "\U000F037D",        # md-mouse
    "input-gaming": "\U000F0297",       # md-gamepad_variant
    "phone": "\U000F011C",              # md-cellphone
    "computer": "\U000F0322",           # md-laptop
}
DEV_DEFAULT = "\U000F00AF"  # md-bluetooth
BATTERY = "\U000F0079"      # md-battery
SCAN = "\U000F0349"         # md-magnify


def adapter():
    out = sh(["bluetoothctl", "show"])
    g = lambda k: (re.search(rf"{k}: (\S+)", out) or [None, None])[1]  # noqa: E731
    return dict(present=bool(out.strip()), name=g("Name"), powered=g("Powered") == "yes",
                discovering=g("Discovering") == "yes")


def devices():
    devs = []
    for line in sh(["bluetoothctl", "devices"]).splitlines():
        m = re.match(r"Device (\S+) (.*)", line)
        if not m:
            continue
        mac = m.group(1)
        info = sh(["bluetoothctl", "info", mac])
        g = lambda k: (re.search(rf"^\s*{k}: (.*)$", info, re.M) or [None, ""])[1].strip()  # noqa: E731
        bat = re.search(r"Battery Percentage: 0x[0-9a-f]+ \((\d+)\)", info)
        devs.append(dict(mac=mac, name=g("Alias") or m.group(2), icon=DEV_ICONS.get(g("Icon"), DEV_DEFAULT),
                         paired=g("Paired") == "yes", trusted=g("Trusted") == "yes",
                         connected=g("Connected") == "yes", battery=int(bat.group(1)) if bat else None))
    devs.sort(key=lambda d: (not d["connected"], not d["paired"], d["name"].lower()))
    return devs


def make_pane():
    """(Pane, build) -- run standalone via pane_main(), or hosted by hyprpanes.py."""
    css = """
    .hero-icon { font-size: 44px; }
    .dev-icon { font-size: 22px; min-width: 30px; }
    .dev-name { font-size: 13px; }
    """
    pn = Pane("hypr.bluetooth-pane", anchor="right", css=css, width=440)
    busy = {}

    def run_bg(cmd, then=None):
        """bluetoothctl connect/disconnect take a few seconds -- don't block the UI."""
        def worker():
            subprocess.run(cmd, capture_output=True, timeout=30, env=clean_env())
            pn.GLib.idle_add(lambda: (then and then(), pn.rebuild(), False)[2])
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def build(pn, root):
        Gtk, L = pn.Gtk, pn.label
        a = adapter()

        head = pn.box(spacing=16)
        head.append(L(BT_ON if a["powered"] else BT_OFF, "hero-icon " + ("accent" if a["powered"] else "muted"),
                      valign=Gtk.Align.CENTER))
        col = pn.box(vertical=True, valign=Gtk.Align.CENTER, hexpand=True)
        col.append(L("Bluetooth", "title"))
        col.append(L(("On" if a["powered"] else "Off") + (f"  ·  {a['name']}" if a["name"] else "") if a["present"]
                     else "No bluetooth adapter found", "muted small"))
        head.append(col)
        sw = Gtk.Switch(active=a["powered"], valign=Gtk.Align.CENTER, sensitive=a["present"])

        def set_power(_s, want):
            # `bluetoothctl power on` returns before the adapter reports
            # Powered: yes -- redrawing right away showed the switch snapping
            # back to off. Poll the adapter until it matches (or 5 s), then redraw.
            if want:
                # blueman's applet leaves an rfkill soft block behind sometimes,
                # and BlueZ then answers "power on" with org.bluez.Error.Failed --
                # unblocking first is enough (BlueZ auto-powers the adapter).
                subprocess.run(["rfkill", "unblock", "bluetooth"], capture_output=True, env=clean_env())
            subprocess.run(["bluetoothctl", "power", "on" if want else "off"], capture_output=True, env=clean_env())
            tries = [0]

            def poll():
                tries[0] += 1
                if adapter()["powered"] == want or tries[0] > 10:
                    pn.rebuild()
                    return False
                return True
            pn.GLib.timeout_add(500, poll)
            return False
        sw.connect("state-set", set_power)
        head.append(sw)
        root.append(head)

        if not a["powered"]:
            root.append(L("Turn it on to see your devices.", "muted", margin_top=12))
        else:
            devs = devices()
            root.append(pn.section("Devices"))
            card = pn.card(spacing=2)
            if not devs:
                card.append(L("No known devices -- pair one in blueman (right-click the icon).", "muted small"))
            for d in devs:
                row = pn.box(spacing=10)
                row.append(L(d["icon"], "dev-icon " + ("accent" if d["connected"] else "muted"), xalign=0.5,
                             valign=Gtk.Align.CENTER))
                col = pn.box(vertical=True, hexpand=True, valign=Gtk.Align.CENTER)
                col.append(L(d["name"], "dev-name"))
                bits = ["connected" if d["connected"] else ("paired" if d["paired"] else "not paired")]
                if d["battery"] is not None:
                    bits.append(f"{BATTERY} {d['battery']} %")
                if d["trusted"]:
                    bits.append("trusted")
                col.append(L("  ·  ".join(bits), "muted small"))
                row.append(col)
                mac = d["mac"]
                if busy.get(mac):
                    row.append(L(busy[mac] + "…", "muted small", valign=Gtk.Align.CENTER))
                elif d["connected"]:
                    row.append(pn.button("Disconnect", lambda mac=mac: (busy.__setitem__(mac, "disconnecting"), pn.rebuild(),
                                                                         run_bg(["bluetoothctl", "disconnect", mac],
                                                                                lambda: busy.pop(mac, None))),
                                         valign=Gtk.Align.CENTER))
                else:
                    verb = "Connect" if d["paired"] else "Pair"
                    cmd = ["bluetoothctl", "connect", mac] if d["paired"] else \
                          ["sh", "-c", f"bluetoothctl pair {mac} && bluetoothctl trust {mac} && bluetoothctl connect {mac}"]
                    row.append(pn.button(verb, lambda mac=mac, cmd=cmd, verb=verb: (busy.__setitem__(mac, verb.lower() + "ing"), pn.rebuild(),
                                                                                    run_bg(cmd, lambda: busy.pop(mac, None))),
                                         cls="flat" if not d["paired"] else None, valign=Gtk.Align.CENTER))
                card.append(row)
            root.append(card)

        foot = pn.box(spacing=8, cls="footer")
        foot.append(L("scanning…" if a["discovering"] else "", "muted", hexpand=True, valign=Gtk.Align.CENTER))
        if a["powered"]:
            # a short discovery so unpaired devices nearby show up in the list
            foot.append(pn.button(f"{SCAN} Scan 8 s", lambda: run_bg(["bluetoothctl", "--timeout", "8", "scan", "on"])))
        foot.append(pn.button("blueman", lambda: (spawn(["blueman-manager"]), pn.close())))
        root.append(foot)

    return pn, build


def pane_main():
    pn, build = make_pane()
    pn.run(build)


if __name__ == "__main__":
    pane_main()
