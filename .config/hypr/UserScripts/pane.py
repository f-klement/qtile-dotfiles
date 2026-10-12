"""Shared scaffold for the waybar dropdown panes (Weather.py, PowerPane.py,
KeybindsPane.py, BluetoothPane.py, QuickSettings.py, CalendarPane.py).

A pane is a GTK4 window turned into a wlr-layer-shell surface (the same
protocol waybar uses), anchored under the top bar. Each pane script has
make_pane() -> (Pane, build), where build(pane, root) fills the content box.

Normally the panes are hosted by the hyprpanes daemon (hyprpanes.py,
systemd --user hyprpanes.service): the bar runs `hyprpanes.py toggle NAME`
and the daemon calls Pane.open() inside its long-lived Gtk.Application
(~50-150 ms to a visible pane). Running a script directly still works and
is what the client falls back to when the daemon is down: pane_main() ->
Pane.run(build) makes the process itself the pane (~350 ms).

What every pane gets from here:
  * LD_PRELOAD re-exec: gtk4-layer-shell must be loaded before
    libwayland-client, which the python binary already links -- the
    documented fix is LD_PRELOAD (gtk4-layer-shell/linking.md).
  * toggle: a pidfile in $XDG_RUNTIME_DIR/hypr-panes/ is checked before
    anything GTK is imported -- if that pane is already up, the launcher
    just SIGTERMs it and exits (~15 ms instead of a second full
    python + GTK start, measured 2026-09-16). Gtk.Application's
    single-instance behaviour (a second launch calls activate() in the
    running one, which quits it) stays as the fallback for a stale pidfile.
    (Never use `pkill -f` for this from waybar -- the pattern also matches
    waybar's own `sh -c` wrapper and kills the launcher itself.)
  * GSK_RENDERER=cairo: GTK 4.22 picks the Vulkan renderer by default and
    initialises it once per surface (shade + pane). Measured 2026-09-16 on
    this machine: ~700 ms CPU and ~120 MB per open with Vulkan, ~570 ms /
    ~90 MB with cairo, and idle CPU while open drops from ~1 % to ~0.2 %.
    Nothing here needs a GPU renderer (flat colours, text, cairo bars).
  * closing: Esc; a click anywhere outside; or the pointer resting outside
    the pane for LEAVE_MS. "Outside" is detected on an invisible full-screen
    "shade" layer surface underneath the pane (the rofi/wofi approach) --
    it swallows the click and sees the pointer. Closing on keyboard-focus
    loss was tried first and is unusable with focus-follows-mouse: the
    pane closed the instant the pointer moved.
  * palette following ~/.local/state/theme-mode (DarkLight.sh), base CSS, and
    a few widget helpers so the panes look like one family. The state file
    is watched while a pane is open, so a theme switch (e.g. from the
    quick-settings tile) restyles the open pane in place.

Icons: Nerd Font glyphs, written as \\U escapes with the glyph name next to
them -- every codepoint was looked up by name in the installed JetBrainsMono
Nerd Font (fontTools). See NetworkMenu.sh on why nothing here is guessed.
"""

import os
import signal
import subprocess
import sys

LAYER_SHELL_LIB = "/usr/lib/libgtk4-layer-shell.so"
LEAVE_MS = 1000   # pointer outside the pane this long -> close
PID_DIR = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "hypr-panes")
THEME_STATE = os.path.expanduser("~/.local/state/theme-mode")

# Matching the desktop themes DarkLight.sh rotates through (Tokyo Night /
# Rose Pine Moon / Rose Pine Dawn, keyed by ~/.local/state/theme-mode); see
# hypr/themes/<mode>/ and waybar/style/*.css.
PALETTES = {
    "tokyo-night":    dict(bg="#1a1b26", surface="#24283b", overlay="#3b4261", fg="#c0caf5",
                           muted="#565f89", accent="#7aa2f7", accent2="#bb9af7", warm="#e0af68",
                           cold="#7dcfff", good="#9ece6a", bad="#f7768e"),
    "rose-pine":      dict(bg="#232136", surface="#2a273f", overlay="#44415a", fg="#e0def4",
                           muted="#908caa", accent="#c4a7e7", accent2="#9ccfd8", warm="#f6c177",
                           cold="#9ccfd8", good="#3e8fb0", bad="#eb6f92"),
    "rose-pine-dawn": dict(bg="#faf4ed", surface="#fffaf3", overlay="#dfdad9", fg="#575279",
                           muted="#797593", accent="#907aa9", accent2="#56949f", warm="#ea9d34",
                           cold="#56949f", good="#286983", bad="#b4637a"),
}


def palette():
    # This host's theme-mode file holds "light"/"dark" (qtile's convention,
    # see config.py's _read_theme_mode), not a PALETTES key directly --
    # the reference repo's own file held a palette name ("rose-pine-dawn")
    # as-is, since it rotated between named themes rather than a light/dark
    # toggle. Map explicitly instead of looking the raw value up in
    # PALETTES directly, which would always silently miss and fall back to
    # the dark default regardless of actual mode.
    try:
        with open(THEME_STATE) as f:
            mode = f.read().strip()
    except OSError:
        mode = ""
    key = "rose-pine-dawn" if mode == "light" else "rose-pine"
    return PALETTES.get(key, PALETTES["rose-pine"])


def sh(cmd, **kw):
    """Run a shell command, return stdout ('' on failure)."""
    try:
        return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True,
                              timeout=kw.pop("timeout", 10), env=clean_env(), **kw).stdout
    except (subprocess.SubprocessError, OSError):
        return ""


def clean_env():
    """The pane runs with LD_PRELOAD=libgtk4-layer-shell (see run()); anything
    we launch must NOT inherit that -- a GTK3/Electron app (tuxedo-control-center,
    blueman, pavucontrol) crashes on it with "gdk_display_manager_get() was
    called before gtk_init()"."""
    env = dict(os.environ)
    env.pop("LD_PRELOAD", None)
    return env


def spawn(cmd):
    """Fire-and-forget a command (list or shell string), detached from the pane."""
    subprocess.Popen(cmd, shell=isinstance(cmd, str), stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True, env=clean_env())


def poke_waybar(signal):
    """Ask a waybar custom module ("signal": N) to re-run its exec now."""
    subprocess.run(["pkill", f"-RTMIN+{signal}", "waybar"])


def base_css(p):
    return f"""
    /* the window itself is invisible: no CSD shadow/border ring around the card */
    /* GTK4 reserves a transparent margin around the window for the CSD
       shadow even with the shadow off -- that was the "gap" under the bar */
    window.pane, window.pane decoration, window.shade, window.shade decoration {{
        background: transparent; box-shadow: none; border: none; outline: none; margin: 0; padding: 0; }}
    .pane {{
        background-color: {p['bg']}; color: {p['fg']};
        border-radius: 14px; border: 1px solid {p['overlay']};
        padding: 18px 22px 14px 22px;
        font-family: "JetBrainsMono Nerd Font"; font-size: 13px;
    }}
    .title   {{ font-size: 18px; font-weight: bold; }}
    .muted   {{ color: {p['muted']}; }}
    .accent  {{ color: {p['accent']}; }}
    .accent2 {{ color: {p['accent2']}; }}
    .warm    {{ color: {p['warm']}; }}
    .cold    {{ color: {p['cold']}; }}
    .good    {{ color: {p['good']}; }}
    .bad     {{ color: {p['bad']}; }}
    .small   {{ font-size: 11px; }}
    .big     {{ font-size: 40px; font-weight: bold; }}
    .icon    {{ font-size: 20px; }}
    .section {{ font-size: 11px; color: {p['muted']}; margin-top: 16px; margin-bottom: 6px;
                letter-spacing: 1px; }}
    .card    {{ background-color: {p['surface']}; border-radius: 10px; padding: 8px 10px; }}
    .footer  {{ color: {p['muted']}; font-size: 11px; margin-top: 14px; }}
    button {{ background-color: {p['surface']}; color: {p['fg']}; border: 1px solid {p['overlay']};
              border-radius: 8px; padding: 4px 12px; font-size: 12px; box-shadow: none;
              text-shadow: none; background-image: none; }}
    button:hover {{ background-color: {p['overlay']}; }}
    button.flat {{ background-color: transparent; border-color: transparent; }}
    button.flat:hover {{ background-color: {p['overlay']}; }}
    button.active, button.tile.active {{ background-color: {p['accent']}; color: {p['bg']};
                                         border-color: {p['accent']}; }}
    button.tile {{ padding: 10px 12px; border-radius: 10px; min-width: 120px; }}
    button.tile label.tile-icon {{ font-size: 18px; }}
    button.tile label.tile-sub {{ font-size: 10px; opacity: 0.75; }}
    scale trough {{ background-color: {p['overlay']}; border-radius: 4px; min-height: 6px; border: none; }}
    scale highlight {{ background-color: {p['accent']}; border-radius: 4px; min-height: 6px; border: none; }}
    scale slider {{ background-color: {p['fg']}; border-radius: 8px; min-width: 14px; min-height: 14px;
                    margin: -5px; border: none; box-shadow: none; }}
    entry {{ background-color: {p['surface']}; color: {p['fg']}; border: 1px solid {p['overlay']};
             border-radius: 8px; padding: 4px 10px; caret-color: {p['fg']}; }}
    entry:focus {{ border-color: {p['accent']}; }}
    scrolledwindow {{ background: transparent; border: none; }}
    scrollbar {{ background: transparent; }}
    scrollbar slider {{ background-color: {p['overlay']}; border-radius: 4px; min-width: 6px; }}
    .kbd {{ background-color: {p['overlay']}; border-radius: 5px; padding: 1px 6px; font-size: 11px; }}
    """


class Pane:
    # margins: 0 down so the card sits flush under the bar (its exclusive zone
    # already ends at the bar edge), 3 sideways to line up with waybar/config's
    # margin-left/right.
    def __init__(self, app_id, anchor="left", css="", width=None, margin_top=0, margin_side=3):
        self.app_id = app_id
        self.anchor = anchor
        self.extra_css = css
        self.width = width
        self.margin_top, self.margin_side = margin_top, margin_side
        self.p = palette()
        self.win = self.root = self.shade = None
        self._build = None
        self._on_closed = None
        self._timeouts = []
        self._ticking = False

    # ---- widget helpers (usable once run() has imported Gtk) -------------

    def label(self, text, cls=None, xalign=0.0, **kw):
        l = self.Gtk.Label(label=text, xalign=xalign, **kw)
        for c in (cls.split() if cls else []):
            l.add_css_class(c)
        return l

    def section(self, text):
        return self.label(text.upper(), "section")

    def box(self, vertical=False, spacing=0, cls=None, **kw):
        b = self.Gtk.Box(orientation=self.Gtk.Orientation.VERTICAL if vertical else self.Gtk.Orientation.HORIZONTAL,
                         spacing=spacing, **kw)
        for c in (cls.split() if cls else []):
            b.add_css_class(c)
        return b

    def card(self, vertical=True, spacing=4, **kw):
        return self.box(vertical, spacing, "card", **kw)

    def button(self, text, on_click, cls=None, **kw):
        b = self.Gtk.Button(label=text, **kw)
        for c in (cls.split() if cls else []):
            b.add_css_class(c)
        b.connect("clicked", lambda *_: on_click())
        return b

    def tile(self, icon, text, active, on_click, sub=None):
        """GNOME-style toggle tile: icon + label (+ small sub line)."""
        Gtk = self.Gtk
        b = Gtk.Button()
        b.add_css_class("tile")
        if active:
            b.add_css_class("active")
        row = self.box(spacing=10)
        ic = self.label(icon, "tile-icon", xalign=0.5)
        row.append(ic)
        col = self.box(vertical=True, valign=Gtk.Align.CENTER)
        col.append(self.label(text))
        if sub:
            col.append(self.label(sub, "tile-sub"))
        row.append(col)
        b.set_child(row)
        b.connect("clicked", lambda *_: on_click())
        return b

    def slider(self, value, on_change, icon=None, lo=0, hi=100, step=1):
        """Horizontal scale with an optional leading icon; on_change(value) fires on release/keys."""
        Gtk = self.Gtk
        row = self.box(spacing=10)
        if icon is not None:
            row.append(self.label(icon, "icon accent", xalign=0.5, width_chars=2))
        sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, step)
        sc.set_value(value)
        sc.set_hexpand(True)
        sc.set_draw_value(False)
        pending = [None]

        def changed(s):
            # debounce: apply 80 ms after the last movement, not on every pixel
            if pending[0]:
                self.GLib.source_remove(pending[0])
            pending[0] = self.GLib.timeout_add(80, lambda: (on_change(s.get_value()), pending.__setitem__(0, None))[1])
        sc.connect("value-changed", changed)
        row.append(sc)
        val = self.label(f"{round(value)}", "muted", xalign=1.0, width_chars=4)
        sc.connect("value-changed", lambda s: val.set_text(f"{round(s.get_value())}"))
        row.append(val)
        row.scale = sc
        return row

    def every(self, ms, fn):
        """Call fn() every ms milliseconds while the pane is open (fn returns False to stop)."""
        self._timeouts.append(self.GLib.timeout_add(ms, lambda: bool(fn())))

    def clear(self, widget):
        while (child := widget.get_first_child()) is not None:
            widget.remove(child)

    def rebuild(self):
        self.clear(self.root)
        self._build(self, self.root)

    # ---- lifecycle ---------------------------------------------------------
    #
    # Two ways to run a pane:
    #   run(build)        standalone process: re-exec with LD_PRELOAD, own
    #                     Gtk.Application, exits when the pane closes.
    #   open(app, build)  inside an already running Gtk.Application -- the
    #                     hyprpanes daemon (hyprpanes.py), which keeps GTK
    #                     warm and shows panes in tens of ms instead of ~500.
    # Both end up in open(); close() tears the windows down and cancels the
    # pane's timeouts (every()), so a daemon never leaks a rebuild timer.

    def _pidfile(self):
        return os.path.join(PID_DIR, self.app_id + ".pid")

    def _toggle_running(self):
        """If this pane is already open (live pidfile, same script), terminate it
        and return True. Runs before the re-exec and before any GTK import."""
        try:
            with open(self._pidfile()) as f:
                pid = int(f.read().strip())
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmdline = f.read()
        except (OSError, ValueError):
            return False
        if os.path.basename(sys.argv[0]).encode() not in cmdline:
            return False   # pid reused by something else: stale file
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return False
        try:
            os.unlink(self._pidfile())
        except OSError:
            pass
        return True

    def _write_pidfile(self):
        os.makedirs(PID_DIR, exist_ok=True)
        with open(self._pidfile(), "w") as f:
            f.write(str(os.getpid()))

    def _remove_pidfile(self):
        try:
            with open(self._pidfile()) as f:
                if int(f.read().strip()) == os.getpid():
                    os.unlink(self._pidfile())
        except (OSError, ValueError):
            pass

    def bind_gtk(self):
        """Import GTK (needs LD_PRELOAD already in place) and keep the modules on self."""
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("Gtk4LayerShell", "1.0")
        from gi.repository import Gtk, Gdk, GLib, Gio, Gtk4LayerShell as LayerShell
        self.Gtk, self.Gdk, self.GLib, self.Gio, self.LayerShell = Gtk, Gdk, GLib, Gio, LayerShell

    def _install_css(self):
        Gtk, Gdk = self.Gtk, self.Gdk
        self._provider = Gtk.CssProvider()
        self._provider.load_from_string(base_css(self.p) + self.extra_css)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self._provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def _remove_css(self):
        if getattr(self, "_provider", None) is not None:
            self.Gtk.StyleContext.remove_provider_for_display(self.Gdk.Display.get_default(), self._provider)
            self._provider = None

    def restyle(self):
        """~/.local/state/theme-mode changed: reload the palette CSS and redraw
        (cairo-drawn bits read pn.p, so a rebuild is needed too)."""
        p = palette()
        if p == self.p:
            return
        self.p = p
        if getattr(self, "_provider", None) is not None:
            self._provider.load_from_string(base_css(p) + self.extra_css)
        if self.root is not None:
            self.rebuild()

    def watch_theme(self):
        """Gio file monitor on the theme state file -> restyle(). Returns the monitor (keep a ref)."""
        mon = self.Gio.File.new_for_path(THEME_STATE).monitor_file(self.Gio.FileMonitorFlags.NONE, None)
        mon.connect("changed", lambda *_: self.restyle())
        return mon

    def open(self, app, build, on_closed=None):
        """Create the shade + pane windows in `app` and fill them with build()."""
        Gtk, Gdk, GLib, LayerShell = self.Gtk, self.Gdk, self.GLib, self.LayerShell
        self._build = build
        self._on_closed = on_closed
        self.p = palette()
        self._install_css()

        # shade: covers the whole output (exclusive zones ignored, so the
        # bar too); any click on it closes the pane. Created first so the
        # pane, on the same layer, stacks above it.
        shade = self.shade = Gtk.Window(application=app, title=self.app_id + "-shade", decorated=False)
        shade.add_css_class("shade")
        LayerShell.init_for_window(shade)
        LayerShell.set_namespace(shade, self.app_id + "-shade")
        LayerShell.set_layer(shade, LayerShell.Layer.TOP)
        for edge in (LayerShell.Edge.TOP, LayerShell.Edge.BOTTOM, LayerShell.Edge.LEFT, LayerShell.Edge.RIGHT):
            LayerShell.set_anchor(shade, edge, True)
        LayerShell.set_exclusive_zone(shade, -1)
        LayerShell.set_keyboard_mode(shade, LayerShell.KeyboardMode.NONE)
        click = Gtk.GestureClick(button=0)
        click.connect("pressed", lambda *_: self.close())
        shade.add_controller(click)
        # pointer outside the pane (= over the shade) for LEAVE_MS closes;
        # coming back into the pane cancels
        leave_timer = [None]

        def arm():
            if os.environ.get("PANE_KEEP_OPEN"):   # PANE_KEEP_OPEN=1: screenshots/debugging
                return
            if leave_timer[0] is None:
                leave_timer[0] = GLib.timeout_add(LEAVE_MS, lambda: self.close() or False)
                self._timeouts.append(leave_timer[0])

        def disarm(*_):
            if leave_timer[0] is not None:
                GLib.source_remove(leave_timer[0])
                if leave_timer[0] in self._timeouts:
                    self._timeouts.remove(leave_timer[0])
                leave_timer[0] = None
        smotion = Gtk.EventControllerMotion()
        smotion.connect("enter", lambda *_: arm())
        smotion.connect("motion", lambda *_: arm())
        shade.add_controller(smotion)
        shade.present()

        win = self.win = Gtk.Window(application=app, title=self.app_id, resizable=False, decorated=False)
        win.add_css_class("pane")
        LayerShell.init_for_window(win)
        LayerShell.set_namespace(win, self.app_id)
        LayerShell.set_layer(win, LayerShell.Layer.TOP)
        LayerShell.set_anchor(win, LayerShell.Edge.TOP, True)
        if self.anchor in ("left", "right"):
            LayerShell.set_anchor(win, getattr(LayerShell.Edge, self.anchor.upper()), True)
            LayerShell.set_margin(win, getattr(LayerShell.Edge, self.anchor.upper()), self.margin_side)
        LayerShell.set_margin(win, LayerShell.Edge.TOP, self.margin_top)
        LayerShell.set_keyboard_mode(win, LayerShell.KeyboardMode.ON_DEMAND)

        self.root = self.box(vertical=True, cls="pane")
        if self.width:
            self.root.set_size_request(self.width, -1)
        win.set_child(self.root)
        build(self, self.root)

        pmotion = Gtk.EventControllerMotion()
        pmotion.connect("enter", disarm)
        pmotion.connect("motion", disarm)
        pmotion.connect("leave", lambda *_: arm())
        win.add_controller(pmotion)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, kv, *_: (self.close(), True)[1] if kv == Gdk.KEY_Escape else False)
        win.add_controller(keys)
        win.present()

    def close(self):
        if self.win is None:
            return
        ctx = self.GLib.MainContext.default()
        for t in self._timeouts:          # skip ones that already returned False
            src = ctx.find_source_by_id(t)
            if src is not None and not src.is_destroyed():
                self.GLib.source_remove(t)
        self._timeouts = []
        self._ticking = False
        self._remove_css()
        win, shade = self.win, self.shade
        self.win = self.root = self.shade = None
        win.destroy()
        shade.destroy()
        if self._on_closed:
            self._on_closed()

    def run(self, build):
        """Standalone: this process is the pane."""
        if self._toggle_running():
            return
        if LAYER_SHELL_LIB not in os.environ.get("LD_PRELOAD", ""):
            os.execve(sys.executable, [sys.executable] + [os.path.abspath(sys.argv[0])] + sys.argv[1:],
                      {**os.environ, "LD_PRELOAD": LAYER_SHELL_LIB,
                       "GSK_RENDERER": os.environ.get("GSK_RENDERER", "cairo")})
        self.bind_gtk()
        self._theme_mon = self.watch_theme()

        app = self.Gtk.Application(application_id=self.app_id)
        app.connect("shutdown", lambda *_: self._remove_pidfile())

        def activate(app):
            if self.win is not None:      # second launch -> toggle off
                app.quit()
                return
            self._write_pidfile()
            self.open(app, build, on_closed=app.quit)

        app.connect("activate", activate)
        app.run(None)
