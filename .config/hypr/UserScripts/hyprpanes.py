#!/usr/bin/env python3
"""hyprpanes -- one resident process for all the waybar dropdown panes.

  hyprpanes.py daemon          run the daemon (systemd --user: hyprpanes.service)
  hyprpanes.py toggle NAME     open NAME (closing any other pane first), or
                               close it if it is the one open
  hyprpanes.py close           close whatever is open
  hyprpanes.py status | quit

  NAME: weather | power | bluetooth | calendar | quick | keybinds

Why (2026-09-16): every pane used to be its own process -- python + PyGObject
+ GTK4 + a Vulkan renderer per surface -- ~600-900 ms CPU and 120 MB per
click, of which the actual pane content was a few tens of ms. The daemon
pays the GTK start once (~60 MB resident, 0 % CPU while idle) and then
shows a pane in the time its build() takes, i.e. mostly the bluetoothctl /
nmcli / pw-dump calls it makes. Measured: see the numbers next to the
waybar module definitions.

How: pane.py's Pane.open()/close() work inside any Gtk.Application; each
pane script exposes make_pane() -> (Pane, build). The daemon imports the
script on first use and re-imports it whenever its file (or pane.py)
changed on disk, so editing a pane keeps working the way it did when each
click started a fresh interpreter -- no restart needed.

Fallback: if the daemon is not running (socket refused), `toggle` execs the
pane's standalone script instead, so the bar keeps working either way.
"""

# the client path (what every bar click runs) imports only these three;
# traceback/subprocess/importlib alone cost ~20 ms of startup (python -X importtime)
import os
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "hypr-panes")
SOCK = os.path.join(RUN_DIR, "hyprpanes.sock")
LAYER_SHELL_LIB = "/usr/lib/libgtk4-layer-shell.so"

# name -> (module in this directory, standalone argv for the fallback)
PANES = {
    "weather":   ("Weather",       ["--pane"]),
    "power":     ("PowerPane",     []),
    "bluetooth": ("BluetoothPane", []),
    "calendar":  ("CalendarPane",  []),
    "quick":     ("QuickSettings", []),
    "keybinds":  ("KeybindsPane",  []),
}


# ------------------------------------------------------------- client ----

def client(argv):
    cmd = " ".join(argv)
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(SOCK)
        s.sendall((cmd + "\n").encode())
        reply = s.recv(4096).decode().strip()
    except OSError as e:
        if argv[0] == "toggle" and len(argv) > 1 and argv[1] in PANES:
            # daemon not running: standalone pane, exactly as before the daemon
            mod, args = PANES[argv[1]]
            os.execv(os.path.join(HERE, mod + ".py"), [os.path.join(HERE, mod + ".py")] + args)
        print(f"hyprpanes: daemon not reachable ({e})", file=sys.stderr)
        return 1
    if reply:
        print(reply)
    return 0 if not reply.startswith("error") else 1


# ------------------------------------------------------------- daemon ----

class Daemon:
    def __init__(self):
        global importlib, subprocess, traceback
        import importlib
        import subprocess
        import traceback
        sys.path.insert(0, HERE)
        import pane as pane_mod
        self.pane_mod = pane_mod
        self.mtimes = {"pane": os.path.getmtime(pane_mod.__file__)}
        self.modules = {}
        self.current = None          # (name, Pane)
        self.app = None

    # -- module (re)loading ---------------------------------------------

    def _mtime(self, modname):
        return os.path.getmtime(os.path.join(HERE, modname + ".py"))

    def module(self, modname):
        """Import a pane script, re-importing it (and everything, if pane.py
        changed) when the file on disk is newer than what is loaded."""
        if self._mtime("pane") != self.mtimes["pane"]:
            self.mtimes["pane"] = self._mtime("pane")
            importlib.reload(self.pane_mod)
            for m in list(self.modules):
                self.modules[m] = importlib.reload(self.modules[m])
                self.mtimes[m] = self._mtime(m)
            print("hyprpanes: pane.py changed, reloaded everything", file=sys.stderr)
        if modname not in self.modules:
            self.modules[modname] = importlib.import_module(modname)
            self.mtimes[modname] = self._mtime(modname)
        elif self._mtime(modname) != self.mtimes[modname]:
            self.mtimes[modname] = self._mtime(modname)
            self.modules[modname] = importlib.reload(self.modules[modname])
            print(f"hyprpanes: {modname}.py changed, reloaded", file=sys.stderr)
        return self.modules[modname]

    # -- pane control ------------------------------------------------------

    def close(self):
        if self.current:
            name, pn = self.current
            self.current = None
            pn.close()

    def open(self, name):
        modname, _ = PANES[name]
        mod = self.module(modname)
        pn, build = mod.make_pane()
        pn.bind_gtk()
        self.current = (name, pn)

        def closed():
            if self.current and self.current[1] is pn:
                self.current = None
        try:
            pn.open(self.app, build, on_closed=closed)
        except Exception:
            self.current = None
            try:
                pn.close()
            except Exception:
                pass
            raise

    def handle(self, line):
        parts = line.split()
        if not parts:
            return "error: empty command"
        cmd, arg = parts[0], (parts[1] if len(parts) > 1 else "")
        if cmd == "toggle":
            if arg not in PANES:
                return f"error: unknown pane '{arg}' (have: {' '.join(PANES)})"
            if self.current and self.current[0] == arg:
                self.close()
                return f"closed {arg}"
            self.close()
            try:
                self.open(arg)
            except Exception as e:
                tb = traceback.format_exc()
                print(tb, file=sys.stderr)
                subprocess.Popen(["notify-send", "-u", "critical", f"hyprpanes: {arg} failed", str(e)],
                                 env=self.pane_mod.clean_env())
                return f"error: {e}"
            return f"opened {arg}"
        if cmd == "close":
            was = self.current[0] if self.current else None
            self.close()
            return f"closed {was}" if was else "nothing open"
        if cmd == "status":
            return f"open: {self.current[0]}" if self.current else "idle"
        if cmd == "quit":
            self.GLib.idle_add(self.app.quit)
            return "bye"
        return f"error: unknown command '{cmd}'"

    # -- socket + main loop ------------------------------------------------

    def run(self):
        if LAYER_SHELL_LIB not in os.environ.get("LD_PRELOAD", ""):
            os.execve(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:],
                      {**os.environ, "LD_PRELOAD": LAYER_SHELL_LIB,
                       "GSK_RENDERER": os.environ.get("GSK_RENDERER", "cairo")})
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk, GLib, Gio
        self.GLib, self.Gio = GLib, Gio

        self.app = app = Gtk.Application(application_id="hypr.panes")

        def activate(app):
            if getattr(self, "_started", False):
                return   # a second `daemon` invocation just lands here and exits
            self._started = True
            app.hold()
            os.makedirs(RUN_DIR, exist_ok=True)
            try:
                os.unlink(SOCK)
            except FileNotFoundError:
                pass
            svc = self.svc = Gio.SocketService.new()
            svc.add_address(Gio.UnixSocketAddress.new(SOCK), Gio.SocketType.STREAM, Gio.SocketProtocol.DEFAULT, None)
            svc.connect("incoming", self.incoming)
            svc.start()
            # theme switches (DarkLight.sh) restyle the open pane in place
            self._theme_mon = Gio.File.new_for_path(self.pane_mod.THEME_STATE).monitor_file(Gio.FileMonitorFlags.NONE, None)
            self._theme_mon.connect("changed", lambda *_: self.current and self.current[1].restyle())
            try:
                from gi.repository import GLibUnix
                signal_add = GLibUnix.signal_add
            except (ImportError, ValueError):
                signal_add = GLib.unix_signal_add
            for sig in (2, 15):
                signal_add(GLib.PRIORITY_HIGH, sig, lambda: (app.quit(), False)[1])
            print(f"hyprpanes: listening on {SOCK}", file=sys.stderr)

        def shutdown(app):
            self.close()
            try:
                os.unlink(SOCK)
            except OSError:
                pass
        app.connect("activate", activate)
        app.connect("shutdown", shutdown)
        app.run(None)

    def incoming(self, svc, conn, _src):
        istream = self.Gio.DataInputStream.new(conn.get_input_stream())
        try:
            line, _ = istream.read_line_utf8(None)
            reply = self.handle(line or "")
        except Exception as e:
            reply = f"error: {e}"
            traceback.print_exc()
        try:
            conn.get_output_stream().write_all((reply + "\n").encode(), None)
            conn.close(None)
        except Exception:
            pass
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip())
        sys.exit(0)
    if sys.argv[1] == "daemon":
        Daemon().run()
    else:
        sys.exit(client(sys.argv[1:]))
