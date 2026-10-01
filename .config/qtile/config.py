
import gc
import os
import re
import shutil
import colors as color_mod
import subprocess
from zoneinfo import ZoneInfo 
from libqtile import bar, confreader, layout, qtile, widget, hook
from libqtile.config import Click, Drag, Group, Key, Match, Screen
from libqtile.lazy import lazy
from libqtile.utils import guess_terminal, logger
from qtile_extras import widget as xwidget 
from types import FunctionType

mod = "mod4"

# Backend = platform here: Wayland is the Fedora/Plasma laptop, X11 the EL VM.
# (qtile sets core.name before loading the config.)
WAYLAND = getattr(qtile.core, "name", None) == "wayland"
terminal = "kitty"
# Prefer the native RPM once installed; fall back to the flatpak until then.
browser = "brave-browser" if shutil.which("brave-browser") else "flatpak run com.brave.Browser"
editor  = "codium"
files = "dolphin" if WAYLAND else "nautilus"   # Fedora KDE: dolphin; EL GNOME: nautilus
notes = "flatpak run md.obsidian.Obsidian"   # not autostarted under Wayland (autostart_wayland.sh)

# helpers
def _physical_screen_order(qtile):
    """Screen order by physical x, not RandR order (scrambled on this host)."""
    return sorted(range(len(qtile.screens)),
                  key=lambda i: (qtile.screens[i].x, qtile.screens[i].y))


def _relative_screen(qtile, direction):
    order = _physical_screen_order(qtile)
    if not order:
        return qtile.current_screen.index
    try:
        pos = order.index(qtile.current_screen.index)
    except ValueError:
        pos = 0
    step = 1 if direction == "next" else -1
    return order[(pos + step) % len(order)]


@lazy.function
def goto_group(qtile, name):
    """Switch to a group on its pinned screen (plain toscreen breaks pinning)."""
    _show_group(qtile, name)


def _show_group(qtile, name):
    target = GROUP_SCREEN.get(name)
    if target is not None and target < len(qtile.screens):
        qtile.groups_map[name].toscreen(target)
        qtile.focus_screen(target)
    else:
        qtile.groups_map[name].toscreen()


@lazy.function
def move_window_to_group(qtile, name, follow=True):
    """Move focused window to a group, keeping that group on its pinned screen."""
    win = qtile.current_window
    if win is None:
        return
    win.togroup(name)
    target = GROUP_SCREEN.get(name)
    if target is not None and target < len(qtile.screens):
        qtile.groups_map[name].toscreen(target)
        if follow:
            qtile.focus_screen(target)
    elif follow:
        qtile.groups_map[name].toscreen()


@lazy.function
def focus_screen_in_direction(qtile, direction="next"):
    """Move the cursor/focus to the next screen in PHYSICAL order."""
    qtile.focus_screen(_relative_screen(qtile, direction))


@lazy.function
def move_window_to_screen(qtile, direction="next"):
    """Move the focused window to the next/prev screen in PHYSICAL order."""
    target_screen_index = _relative_screen(qtile, direction)
    target_group = qtile.screens[target_screen_index].group
    if qtile.current_window and target_group:
        qtile.current_window.togroup(target_group.name)
        qtile.focus_screen(target_screen_index)

keys = [ 
    Key([mod], "Left",  lazy.layout.left(),  desc="Focus left"),
    Key([mod], "Right", lazy.layout.right(), desc="Focus right"),
    Key([mod], "Up",    lazy.layout.up(),    desc="Focus up"),
    Key([mod], "Down",  lazy.layout.down(),  desc="Focus down"),
    Key([mod], "t", lazy.layout.next(), desc="Move window focus to other window"),
    Key([mod, "shift"], "Left", lazy.layout.shuffle_left(), desc="Move window to the left"),
    Key([mod, "shift"], "Right", lazy.layout.shuffle_right(), desc="Move window to the right"),
    Key([mod, "shift"], "Down", lazy.layout.shuffle_down(), desc="Move window down"),
    Key([mod, "shift"], "Up", lazy.layout.shuffle_up(), desc="Move window up"),
    Key([mod, "control"], "Left", lazy.layout.grow_left(), desc="Grow window to the left"),
    Key([mod, "control"], "Right", lazy.layout.grow_right(), desc="Grow window to the right"),
    Key([mod, "control"], "Down", lazy.layout.grow_down(), desc="Grow window down"),
    Key([mod, "control"], "Up", lazy.layout.grow_up(), desc="Grow window up"),
    Key([mod], "n", lazy.layout.normalize(), desc="Reset all window sizes"),
     # new launch shortcuts
    Key([mod], "b", lazy.spawn(browser), desc="Launch browser"),
    Key([mod], "d", lazy.spawn(files),   desc="Launch file manager"),
    Key([mod, "mod1"], "space", lazy.spawn("rofi -show drun"), desc="Launch rofi"),
    Key([mod], "e", lazy.spawn(editor), desc="Launch VSCodium"),
    Key([mod], "o", lazy.spawn(notes), desc="Launch Obsidian"),
    # screenshots (see bin/screenshot.sh for why not the flameshot daemon)
    Key([], "Print", lazy.spawn(os.path.expanduser("~/bin/screenshot.sh") + " gui"), desc="Screenshot: select region"),
    Key([mod, "mod1"], "s", lazy.spawn(os.path.expanduser("~/bin/screenshot.sh") + " gui"), desc="Screenshot: select region (for keyboards without Print)"),
    Key(["shift"], "Print", lazy.spawn(os.path.expanduser("~/bin/screenshot.sh") + " clip"), desc="Screenshot: full screen to clipboard"),
    Key(["control"], "Print", lazy.spawn(os.path.expanduser("~/bin/screenshot.sh") + " full"), desc="Screenshot: full screen to ~/Pictures"),
    Key(
        [mod, "shift"],
        "Return",
        lazy.layout.toggle_split(),
        desc="Toggle between split and unsplit sides of stack",
    ),
    Key([mod], "q", lazy.spawn(terminal), desc="Launch terminal"),
    Key([mod, "mod1"], "Tab", lazy.next_layout(), desc="Toggle between layouts"),
    Key([mod,"mod1"], "x", lazy.window.kill(), desc="Kill focused window"),
    Key(
        [mod],
        "f",
        lazy.window.toggle_fullscreen(),
        desc="Toggle fullscreen on the focused window",
    ),
    Key([mod], "space", lazy.window.toggle_floating(), desc="Toggle floating on the focused window"),
    # laptop keys (absent on the EL VM, harmless there)
    Key([], "XF86AudioRaiseVolume", lazy.spawn("pactl set-sink-volume @DEFAULT_SINK@ +5%"), desc="Volume up"),
    Key([], "XF86AudioLowerVolume", lazy.spawn("pactl set-sink-volume @DEFAULT_SINK@ -5%"), desc="Volume down"),
    Key([], "XF86AudioMute", lazy.spawn("pactl set-sink-mute @DEFAULT_SINK@ toggle"), desc="Mute"),
    Key([], "XF86AudioMicMute", lazy.spawn("pactl set-source-mute @DEFAULT_SOURCE@ toggle"), desc="Mute mic"),
    Key([], "XF86MonBrightnessUp", lazy.spawn("brightnessctl set 5%+"), desc="Brightness up"),
    Key([], "XF86MonBrightnessDown", lazy.spawn("brightnessctl set 5%-"), desc="Brightness down"),
    # Lock: logind broadcasts it and the session's listener runs the themed
    # locker (swayidle -> swaylock on Wayland, xss-lock -> i3lock on X11).
    Key([mod], "l", lazy.spawn("loginctl lock-session"), desc="Lock the screen"),
    Key([mod, "control"], "r", lazy.reload_config(), desc="Reload the config"),
    Key([mod, "control"], "q", lazy.shutdown(), desc="Shutdown Qtile"),
    Key([mod], "r", lazy.spawncmd(prompt="Run: "), desc="Spawn a command"),
    Key([mod], "Tab", focus_screen_in_direction(direction="next"),
        desc='Next monitor (physical order)'),
    Key([mod, "shift"], "Tab", focus_screen_in_direction(direction="prev"),
        desc='Previous monitor (physical order)'),
    Key([mod, "mod1"], "Left", move_window_to_screen(direction="prev"), desc="Move window to previous monitor"),
    Key([mod, "mod1"], "Right", move_window_to_screen(direction="next"), desc="Move window to next monitor"),
]

for vt in range(1, 8):
    keys.append(
        Key(
            ["control", "mod1"],
            f"f{vt}",
            lazy.core.change_vt(vt).when(func=lambda: qtile.core.name == "wayland"),
            desc=f"Switch to VT{vt}",
        )
    )

# screen roles
# Resolved from the real outputs by generate_screens() below, which qtile calls
# on start and on every hotplug with either backend (xrandr is not available to
# the Wayland backend at config load). Index here == qtile screen index.
SCREEN = {"small": 0, "portrait": 0, "landscape": 0}

def _screen_roles(rects):
    if not rects:
        return {"small": 0, "portrait": 0, "landscape": 0}
    idx = range(len(rects))
    small = min(idx, key=lambda i: rects[i].width * rects[i].height)   # built-in laptop panel
    portrait = next((i for i in idx if rects[i].height > rects[i].width), small)
    landscape = next((i for i in idx if i not in (small, portrait)), small)
    return {"small": small, "portrait": portrait, "landscape": landscape}

# Which display each group lives on (role -> index via SCREEN).
GROUP_ROLE = {
    "1": "portrait",    # brave
    "2": "landscape",   # codium
    "5": "small",       # nautilus / dolphin
    "6": "small",       # obsidian
    "9": "landscape",   # citrix (the monitor Citrix itself picks for this layout)
}
GROUP_SCREEN = {name: SCREEN[role] for name, role in GROUP_ROLE.items()}

# Citrix Workspace session (wfica, X11 via Xwayland). Spanning several monitors
# needs _NET_WM_FULLSCREEN_MONITORS, which the wlroots Xwayland WM does not
# offer (wfica logs "multi-monitor is not supported by current window
# manager"), so the session runs fullscreen on ONE monitor in its own group 9.
# Its splash/login/error/reconnect dialogs are Wfica_* and float on top (ON_TOP).
CITRIX_SESSION = Match(wm_class=re.compile(r"^[Ww]fica$"))
CITRIX_DIALOG = Match(wm_class=re.compile(r"^Wfica_"))

# Spawn rules. X11: wm_class of the RUNNING window (codium reports "codium").
# Wayland: the app_id (brave-browser, codium, org.gnome.Nautilus, obsidian, ...).
GROUP_MATCHES = {
    "1": [Match(wm_class=re.compile(r"^(brave-browser|com\.brave\.Browser)$"))],
    "2": [Match(wm_class="codium")],
    "5": [Match(wm_class=re.compile(r"^(nautilus|org\.gnome\.Nautilus|org\.kde\.dolphin)$"))],
    "6": [Match(wm_class=re.compile(r"^(md\.obsidian\.obsidian|obsidian)$"))],
    "7": [Match(wm_class=re.compile(r"^(KeePassXC|keepassxc|org\.keepassxc\.KeePassXC)$"))],
    "9": [CITRIX_SESSION],
}

# Groups whose apps also pull the view to them when they open (see follow_app_group).
FOLLOW_GROUPS = {"1", "2", "7", "9"}

groups = []
for _name in "123456789":
    _kw = {}
    if _name in GROUP_SCREEN:  # re-pinned by generate_screens once outputs are known
        _kw["screen_affinity"] = GROUP_SCREEN[_name]
    if _name in GROUP_MATCHES:
        _kw["matches"] = GROUP_MATCHES[_name]
    groups.append(Group(_name, **_kw))

for i in groups:
    keys.extend(
        [
            Key(
                [mod],
                i.name,
                goto_group(i.name),
                desc=f"Switch to group {i.name} (on its pinned screen)",
            ),
            Key(
                [mod, "shift"],
                i.name,
                move_window_to_group(i.name),
                desc=f"Move focused window to group {i.name} (keeps pinning)",
             ),
        ]
    )

# Light/dark mode. ~/bin/theme.sh owns the state file and re-themes every
# toolkit; it ends with a reload_config so this picks up the new palette.
THEME_MODE_FILE = os.path.join(
    os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "theme-mode")

def _read_theme_mode():
    try:
        with open(THEME_MODE_FILE) as f:
            return "light" if f.read().strip() == "light" else "dark"
    except OSError:
        return "dark"

THEME_MODE = _read_theme_mode()
doom_colors = color_mod.RosePineDawn if THEME_MODE == "light" else color_mod.RosePine
layout_theme = {"border_width": 1,
                "margin": 0,
                "border_focus": doom_colors[7],
                "border_normal": doom_colors[0]
                }


layouts = [
    layout.Columns(border_focus_stack=["#d75f5f", "#8f3d3d"], **layout_theme),
    layout.Spiral(main_pane="left", clockwise=True, **layout_theme),
    layout.Max(**layout_theme),
]

widget_defaults = dict(
    font="JetBrainsMono Nerd Font",
    fontsize=12,
    padding=2,
    background=doom_colors[0]
)

extension_defaults = widget_defaults.copy()

# helpers
@lazy.function
def toggle_vol_text(qtile):
    # Every live bar's volume widget, not widgets_map["pulsevolume"]: after a
    # screen rebuild that name belongs to a dead widget (new ones get _N).
    for w in [w for s in qtile.screens if s.top for w in s.top.widgets
              if isinstance(w, widget.PulseVolume)]:
        _toggle_one_vol(w)


def _toggle_one_vol(w):
    w.fmt ="" if w.fmt.endswith("{}") else " {}"   # no percent sign
    w.bar.draw()
    
@lazy.function
def power_menu(qtile):
    qtile.spawn(
        "bash -c '"
        "choice=$(GTK_THEME=" + ("Adwaita" if THEME_MODE == "light" else "Adwaita:dark") + " yad --width=200 --height=50 "
        "--title=\"Power Menu\" "
        "--button=\"Shutdown:0\" --button=\"Reboot:1\" "
        "--center --on-top --no-markup --undecorated); "
        "code=$?; "
        "if [ \"$code\" -eq 0 ]; then systemctl poweroff; "
        "elif [ \"$code\" -eq 1 ]; then systemctl reboot; fi'"
    )


def _default_route_iface(fallback="eth0"):
    """Interface of the lowest-metric default route (dock ethernet vs wifi on the laptop)."""
    try:
        with open("/proc/net/route") as f:
            rows = [l.split() for l in f.readlines()[1:]]
        return min((r for r in rows if r[1] == "00000000"), key=lambda r: int(r[6]))[0]
    except (OSError, ValueError, IndexError):
        return fallback

def _run(*cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


class _StateIcon(widget.GenPollText):
    """Icon whose glyph and colour follow probe() -> state key in STATES."""
    STATES = {}

    def __init__(self, **config):
        # Start in the theme colour: _TextBox bakes foreground into its text
        # layout at configure time (default white - invisible on Dawn).
        config.setdefault("foreground", next(iter(self.STATES.values()))[1])
        super().__init__(func=self._render, **config)

    def probe(self):
        raise NotImplementedError

    def label(self, state):
        """Extra text after the glyph (none by default)."""
        return ""

    def update(self, text):
        # _TextBox.update() skips the redraw when the text is unchanged, but the
        # state may only have changed colour (bluetooth off/on/connected share
        # one glyph) - redraw then too.
        recoloured = getattr(self, "_drawn_colour", None) != self.foreground
        super().update(text)
        if recoloured and self.text == text and self.can_draw():
            self.draw()
        self._drawn_colour = self.foreground

    def _render(self):
        state = self.probe()
        glyph, colour = self.STATES[state]
        # Setting self.foreground alone never reaches the drawn text; recolour
        # the layout like qtile's own widgets (df, chord) do.
        self.foreground = colour
        if getattr(self, "layout", None) is not None:
            self.layout.colour = colour
        return glyph + self.label(state)

    def act(self, *cmds):
        """Run commands in order off the event loop (qtile IS the compositor on
        Wayland: a blocking call freezes the screen), then redraw right away."""
        def work():
            for cmd in cmds:
                _run(*cmd)

        def run():
            fut = qtile.run_in_executor(work)
            fut.add_done_callback(lambda _: qtile.call_soon_threadsafe(self.force_update))
        return run


class MicIcon(_StateIcon):
    """Default PipeWire source, same design as the volume widget: icon only,
    left click shows "<icon> 35%" ("M" when muted), middle mixer (inputs tab),
    right mute, wheel +-5 %."""
    STATES = {
        # Font Awesome, like the volume widget's \uf028 (same family and size)
        "on":    ("\uf130", doom_colors[7][0]),   # fa-microphone
        "muted": ("\uf131", doom_colors[9][0]),   # fa-microphone-slash
        "none":  ("\uf131", doom_colors[9][0]),
    }
    SRC = "@DEFAULT_AUDIO_SOURCE@"

    def __init__(self, **config):
        self.show_level = False
        self._level = None
        config.setdefault("mouse_callbacks", {
            "Button1": self._toggle_level,
            "Button2": lazy.spawn("pavucontrol -t 4"),                 # mixer, input devices tab
            "Button3": self.act(("wpctl", "set-mute", self.SRC, "toggle")),
            "Button4": self.act(("wpctl", "set-volume", "-l", "1.0", self.SRC, "5%+")),
            "Button5": self.act(("wpctl", "set-volume", self.SRC, "5%-")),
        })
        super().__init__(**config)

    def probe(self):
        out = _run("wpctl", "get-volume", self.SRC)            # "Volume: 0.35 [MUTED]"
        try:
            self._level = round(float(out.split()[1]) * 100)
        except (IndexError, ValueError):
            self._level = None
        return "none" if not out else ("muted" if "MUTED" in out else "on")

    def label(self, state):
        # PulseVolume's unmute_format "{volume}%" / mute_format "M"
        if not self.show_level or self._level is None:
            return ""
        return " M" if state == "muted" else f" {self._level}%"

    def _toggle_level(self):
        self.show_level = not self.show_level
        self.force_update()


class BluetoothIcon(_StateIcon):
    """Adapter state: left click switches the radio, right click opens blueman."""
    STATES = {
        # Font Awesome fa-bluetooth-b, like the volume/mic icons; FA has no
        # "off" variant, so the state is the colour: muted / pine / foam.
        "off":       ("\uf294", doom_colors[9][0]),
        "on":        ("\uf294", doom_colors[6][0]),
        "connected": ("\uf294", doom_colors[4][0]),
    }

    def __init__(self, **config):
        config.setdefault("mouse_callbacks", {
            "Button1": self._toggle,
            "Button3": lambda: qtile.spawn("blueman-manager"),
        })
        super().__init__(**config)

    def probe(self):
        if "Powered: yes" not in _run("bluetoothctl", "show"):
            return "off"            # also: rfkill-blocked, or no adapter/bluetoothd
        return "connected" if _run("bluetoothctl", "devices", "Connected").strip() else "on"

    def _toggle(self):
        if self.probe() == "off":   # soft-blocked radios refuse "power on" until unblocked
            self.act(("rfkill", "unblock", "bluetooth"), ("sleep", "1"),
                     ("bluetoothctl", "power", "on"))()
        else:
            self.act(("bluetoothctl", "power", "off"))()


def init_widgets(include_systray=True, include_updates=True):
    widgets = [
        # LEFT cluster
        widget.Spacer(length=4),  # tiny padding
        widget.GroupBox(
            padding_x=0,
            margin_x=1,
            active = doom_colors[8],
            inactive = doom_colors[9],
            rounded = True,
            highlight_color = doom_colors[0],
            highlight_method = "line",
            this_current_screen_border = doom_colors[7],
            this_screen_border = doom_colors[4],
            other_current_screen_border = doom_colors[7],
            other_screen_border = doom_colors[4],
            disable_drag=True,
        ),
        widget.Prompt(name="prompt", prompt="Run: ", padding=5, foreground = doom_colors[1]),
        widget.Spacer(length=6),
        # centre
        widget.Spacer(length=bar.STRETCH),
        widget.Clock(
            format="%H:%M   %d-%m-%Y",
            timezone=ZoneInfo("Europe/Vienna"),
            foreground = doom_colors[1],
        ),
        widget.Spacer(length=bar.STRETCH),

        # RIGHT cluster
        # Light/dark toggle: icon shows the ACTIVE mode (moon = dark, sun = light).
        # theme.sh re-themes everything and reloads this config, which redraws the icon.
        widget.TextBox(
            text="\U000f05a8" if THEME_MODE == "light" else "\U000f0594",  # nf-md-white_balance_sunny / nf-md-weather_night
            fontsize=15,
            padding=6,
            foreground = doom_colors[5],
            mouse_callbacks={
                "Button1": lazy.spawn(os.path.expanduser("~/bin/theme.sh") + " toggle"),
            },
        ),
        # Wallpaper switcher (same script as the autostart loop).
        widget.TextBox(
            text="\U000f00e3",        # Nerd Font paint brush (nf-md-brush)
            fontsize=15,
            padding=6,
            foreground = doom_colors[7],
            mouse_callbacks={
                "Button1": lazy.spawn(os.path.expanduser("~/bin/wallpaper.sh")),
            },
        ),
        widget.Net(
            interface=_default_route_iface(),   # pin: avoids enumerating docker0/virbr0/veth* each poll
            # ▾/▴ are 1-char arrows from the Nerd-Font set
            format="{down:.0f}{down_suffix}▾{up:.0f}{up_suffix}▴",
            update_interval=5,
            mouse_callbacks={
                "Button3": lazy.spawn("nm-connection-editor"),  # right-click → open NetworkManager GUI
            },
            foreground = doom_colors[5],
        ),
        widget.PulseVolume(
            name="pulsevolume",
            foreground = doom_colors[7],
            fmt=" {}",                       # single value, no % sign
            mouse_callbacks={
                "Button1": toggle_vol_text,                                           # show/hide value
                "Button2": lazy.spawn("pavucontrol"),                                 # open mixer
                "Button3": lazy.spawn("pactl set-sink-mute @DEFAULT_SINK@ toggle"),   # mute/unmute
                "Button4": lazy.spawn("pactl set-sink-volume @DEFAULT_SINK@ +5%"),    # vol +5 %
                "Button5": lazy.spawn("pactl set-sink-volume @DEFAULT_SINK@ -5%"),    # vol –5 %
            },
        ),
        widget.Memory(
            foreground = doom_colors[8],
            format="\U000f035b {MemUsed:>3.1f}G",   # nf-md-memory (NF v3; the old U+F538 fell back to a Tibetan font)
            measure_mem="G",               # tell the widget we want GiB/GB
            update_interval=5,
        ),
        widget.CPU(foreground = doom_colors[4],format=" {load_percent:>3}%", update_interval=5),
        # Screenshot launcher (fresh process per capture; see bin/screenshot.sh).
        widget.TextBox(
            text="\U000f0100",        # Nerd Font camera (nf-md-camera)
            fontsize=15,
            padding=6,
            foreground = doom_colors[8],
            mouse_callbacks={
                "Button1": lazy.spawn(os.path.expanduser("~/bin/screenshot.sh") + " gui"),   # region select
                "Button2": lazy.spawn(os.path.expanduser("~/bin/screenshot.sh") + " full"),  # whole screen -> ~/Pictures
                "Button3": lazy.spawn(os.path.expanduser("~/bin/screenshot.sh") + " clip"),  # whole screen -> clipboard
            },
        ),
        ]
    if WAYLAND:
        # Mic + bluetooth next to the volume, Wayland (Fedora laptop) only; their
        # services (blueman-applet) start in autostart_wayland.sh.
        at = next(i for i, w in enumerate(widgets) if isinstance(w, widget.PulseVolume)) + 1
        widgets[at:at] = [
            MicIcon(update_interval=2),      # bar-default size/padding, as PulseVolume
            BluetoothIcon(update_interval=5),   # bar-default size/padding, as PulseVolume
        ]
    if include_systray:
        # XEmbed Systray is X11-only; on Wayland tray icons are StatusNotifierItems
        # (nm-applet --indicator, copyq, ...).
        if WAYLAND:
            widgets.append(widget.StatusNotifier(icon_size=12, padding=2))
        else:
            widgets.append(widget.Systray(icon_size=12, padding=2))
    widgets.extend([
        widget.Spacer(length=3),
    ])
    # CheckUpdates spawns a dnf process per poll; keep it on one bar only.
    widgets.extend([
        widget.CheckUpdates(
            distro="Fedora",  # This uses the DNF backend, which works for Rocky/RHEL
            display_format="󱧕 {updates}", #  is a Nerd Font package icon
            no_update_string="󱧕 0",
            colour_have_updates=doom_colors[5], # gold
            # muted grey reads fine on the dark base but washes out on Dawn's cream
            colour_no_updates=doom_colors[9] if THEME_MODE == "dark" else doom_colors[1],
            update_interval=1800, # Check every 30 mins
            mouse_callbacks={
                # Left-click runs system_update.sh in a terminal.
                "Button1": lazy.spawn([
                    terminal,
                    "-e",
                    os.path.expanduser("~/.config/qtile/system_update.sh"),
                ])
            },
            padding=1,
        ),
    ] if include_updates else [])
    widgets.extend([
        widget.Spacer(length=1),
        # Lock screen (i3lock-color on X11, swaylock on Wayland; themed via theme.sh,
        # same script xss-lock / swayidle use).
        widget.TextBox(
            text="\U000f033e",        # Nerd Font lock (nf-md-lock)
            padding=6,
            fontsize=15,
            foreground = doom_colors[7],
            mouse_callbacks={
                "Button1": lazy.spawn(os.path.expanduser(
                    "~/.config/qtile/lock_with_random_bg_wayland.sh" if WAYLAND
                    else "~/.config/qtile/lock_with_random_bg_x11.sh")),
            },
        ),
        widget.TextBox(
            text="⏻",
            padding=6,
            fontsize=16,
            foreground = doom_colors[1],   # explicit: the widget default (#ffffff) vanishes on Dawn
            mouse_callbacks={
                 # Reboot or shut down, see system_power.sh.
                 "Button1": lazy.spawn([
                     terminal,
                     "-e",
                     os.path.expanduser("~/.config/qtile/system_power.sh"),
                 ])}),
        widget.Spacer(length=4),
    ])
    return widgets


def _retire_systray():
    """Release the X tray selection before the Systray below is rebuilt.

    Systray guards _NET_SYSTEM_TRAY_S0 with a CLASS-level instance counter, so
    constructing a second one while the first is still alive raises
    ConfigError("Only one Systray can be used.") and qtile swaps in a
    "Widget crashed: Systray" placeholder ~277 px wide -- which eats the slack
    the two bar.STRETCH spacers would have had and drags the whole right-hand
    cluster in towards the clock.

    This function runs on every screen change, including the reconfigure that
    randr triggers seconds after login, so the old instance has to go first.
    repin_groups() does finalize stale bars, but only once the new widgets have
    been configured - too late for the selection.
    """
    if WAYLAND:  # Wayland tray icons are StatusNotifierItems; no X selection
        return
    for w in [o for o in gc.get_objects() if isinstance(o, widget.Systray)]:
        if getattr(w, "configured", False):
            try:
                w.finalize()
            except Exception:  # never let this stop the bar from being built
                logger.exception("could not retire the previous Systray")


def _build_screens(rects):
    """One bar per output; also re-derives the screen roles and group pinning."""
    _retire_systray()
    SCREEN.update(_screen_roles(rects))
    for name, role in GROUP_ROLE.items():
        GROUP_SCREEN[name] = SCREEN[role]
        if name in qtile.groups_map:
            qtile.groups_map[name].screen_affinity = SCREEN[role]
    # After qtile has configured these screens: start, reload and hotplug alike
    # (the screens_reconfigured hook would miss start and reload).
    qtile.call_soon(repin_groups)
    return [
        Screen(top=bar.Bar(init_widgets(include_systray=(i == 0), include_updates=(i == 0)), 28, opacity=0.70))
        for i in range(max(1, len(rects)))
    ]


def generate_screens(outputs):
    """qtile >= 0.35 calls this on start and on every output change."""
    return _build_screens([o.rect for o in outputs])


# generate_screens() is a qtile 0.35 API. Older qtile ignores it, then finds no
# `screens` at all, so every output comes up as a bare Screen() with no bar --
# and nothing is logged, because Config.update() just falls back to a default
# rather than raising. Both bootstraps install >= 0.35, so this is only a safety
# net for a venv predating that floor: build the list eagerly from the outputs
# the core already knows about (no xrandr, so either backend works). Probe the
# config API, not a version string: libqtile exports no __version__.
if "generate_screens" not in getattr(confreader.Config, "__annotations__", {}):
    # getattr, as with qtile.core.name above: the module-level `qtile` proxy is
    # still the undefined-core stub to a type checker.
    screens = _build_screens(list(getattr(qtile.core, "get_screen_info", list)()))

Drag([mod], "Button1", lazy.window.set_position_floating(),
     start=lazy.window.get_position()),

mouse = [
    Drag([mod], "Button1", lazy.window.set_position_floating(), start=lazy.window.get_position()),
    Drag([mod], "Button3", lazy.window.set_size_floating(), start=lazy.window.get_size()),
    Click([mod], "Button2", lazy.window.bring_to_front()),
   # Use standard group cycling
    Click([mod], "Button4", lazy.screen.next_group()),
    Click([mod], "Button5", lazy.screen.prev_group()),
]

dgroups_key_binder = None
dgroups_app_rules = []  # type: list
follow_mouse_focus = True
bring_front_click = True
floats_kept_above = True

# Screenshot editor (bin/screenshot.sh gui on Wayland: slurp -> grim -> swappy).
# slurp is a layer-shell overlay and always on top; swappy is a normal window,
# so it gets floated, centred, raised above everything and focused (see
# _keep_on_top) instead of landing behind the other apps.
SCREENSHOT_EDITOR = Match(wm_class=re.compile(r"^(swappy|me\.jtheoof\.swappy)$"))

# xdg-desktop-portal file pickers / save dialogs (flatpaks, browsers, ...).
# qtile has no xdg-foreign, so they cannot attach to the app that opened them
# and would otherwise be tiled as a normal window.
PORTAL_DIALOG = Match(wm_class=re.compile(
    r"^(xdg-desktop-portal-(gtk|kde)|org\.freedesktop\.impl\.portal\.desktop\.(gtk|kde))$"))

# Floated, centred, raised above everything and focused (_keep_on_top).
ON_TOP = [SCREENSHOT_EDITOR, PORTAL_DIALOG, CITRIX_DIALOG]
cursor_warp = True
floating_layout = layout.Floating(
    float_rules=[
        *layout.Floating.default_float_rules,
        Match(wm_class="confirmreset"),   # gitk
        Match(wm_class="dialog"),         # dialog boxes
        Match(wm_class="download"),       # downloads
        Match(wm_class="error"),          # error msgs
        Match(wm_class="file_progress"),  # file progress boxes
        Match(wm_class='kdenlive'),       # kdenlive
        Match(wm_class="makebranch"),     # gitk
        Match(wm_class="maketag"),        # gitk
        Match(wm_class="notification"),   # notifications
        Match(wm_class='pinentry-gtk-2'), # GPG key password entry
        Match(wm_class="ssh-askpass"),    # ssh-askpass
        Match(wm_class="toolbar"),        # toolbars
        Match(wm_class="Yad"),            # yad boxes
        Match(title="branchdialog"),      # gitk
        Match(title='Confirmation'),      # tastyworks exit box
        Match(title='Qalculate!'),        # qalculate-gtk
        Match(title="pinentry"),          # GPG key password entry
        Match(wm_class="rofi"),           # Rofi Launcher
        *ON_TOP,                          # swappy, portal file dialogs
    ]
)
auto_fullscreen = True
focus_on_window_activation = "smart"
reconfigure_screens = True

auto_minimize = True

# Wayland input (ignored on X11). Keyboard layout comes from XKB_DEFAULT_* which
# bin/starting-qtile-wayland.sh derives from localectl.
try:
    from libqtile.backend.wayland import InputConfig
    wl_input_rules = {"type:touchpad": InputConfig(tap=True, dwt=True, natural_scroll=False)}
except ImportError:
    wl_input_rules = None

# Wayland cursor (X11 reads XCURSOR_THEME / ~/.icons/default), follows theme.sh.
wl_xcursor_theme = "BreezeX-RosePineDawn-Linux" if THEME_MODE == "light" else "BreezeX-RosePine-Linux"
wl_xcursor_size = 24

def repin_groups():
    """Clean up after generate_screens replaced the Screen objects.

    generate_screens returns fresh Screen objects on every change (kanshi
    rotating the portrait panel, dock/undock, reload), but qtile's Screen.__eq__
    calls two screens on the same output port EQUAL, whatever their geometry.
    So qtile's own cleanup ("finalize screens not in new_screens") and
    Group.set_screen ("already there") both skip the old objects:
      - old bars stay alive and drawn (the pre-rotation 1920 px dark bar over
        the portrait panel, clock frozen, widgets still polling);
      - groups keep laying out for the old geometry (brave 1920 px wide on the
        1200 px panel, spilling onto the next monitor).
    So: finalize every bar that is not a live screen's bar (by identity), then
    give every live screen exactly one group - its pinned group first - and lay
    everything out again.
    """
    live = qtile.screens

    live_bars = [g for s in live for g in s.gaps]
    for b in [o for o in gc.get_objects() if isinstance(o, bar.Bar)]:
        if b.window is not None and not any(b is lb for lb in live_bars):
            b.finalize()
    # ...and forget their widgets: widgets_map would otherwise keep resolving
    # names ("pulsevolume", "micicon") to the dead copies.
    live_widgets = {id(w) for b in live_bars for w in getattr(b, "widgets", [])}
    for name in [n for n, w in qtile.widgets_map.items() if id(w) not in live_widgets]:
        del qtile.widgets_map[name]

    plan, taken = [], set()
    for i, scr in enumerate(live):
        cur = scr.group.name if scr.group else None
        pinned = [n for n in GROUP_ROLE if GROUP_SCREEN[n] == i and n not in taken]
        # own pinned group (keep the shown one if it is), then an unpinned
        # leftover, then any free unpinned group
        if cur in pinned:
            name = cur
        elif pinned:
            name = pinned[0]
        elif cur is not None and cur not in taken and cur not in GROUP_SCREEN:
            name = cur
        else:
            name = next((g.name for g in qtile.groups
                         if g.name not in taken and g.name not in GROUP_SCREEN), None)
        if name is None:
            continue
        taken.add(name)
        plan.append((scr, qtile.groups_map[name]))

    for g in qtile.groups:
        if g.screen is not None:
            g.hide()
    for scr, g in plan:
        scr.group = g
        g.set_screen(scr, warp=False)
    if qtile.current_screen not in live:
        qtile.focus_screen(0)
    hook.fire("setgroup")


@hook.subscribe.client_managed
def follow_app_group(client):
    """Show the group of a newly opened FOLLOW_GROUPS app, on its pinned screen.
    Placement itself is GROUP_MATCHES; client_managed fires after it has run."""
    group = getattr(client, "group", None)
    if group is not None and group.name in FOLLOW_GROUPS:
        _show_group(qtile, group.name)

wmname = "LG3D"

@hook.subscribe.startup_once
def start_once():
    home = os.path.expanduser('~')
    if WAYLAND:
        autostart_script = os.path.join(home, '.config/qtile/autostart_wayland.sh')
    else:
        autostart_script = os.path.join(home, '.config/qtile/autostart_x11.sh')
    subprocess.call([autostart_script])


# glibc heap trim
# Polling widgets fragment the heap so glibc never trims it; force a periodic trim.
import ctypes as _ctypes

MALLOC_TRIM_INTERVAL = 900  # seconds

try:
    _libc = _ctypes.CDLL("libc.so.6", use_errno=True)
except OSError as _exc:  # pragma: no cover - non-glibc
    _libc = None
    logger.warning("malloc_trim unavailable: %s", _exc)


def _malloc_trim():
    if _libc is not None:
        try:
            _libc.malloc_trim(0)
        except Exception as exc:
            logger.warning("malloc_trim failed: %s", exc)
    qtile.call_later(MALLOC_TRIM_INTERVAL, _malloc_trim)


@hook.subscribe.startup_complete
def _start_malloc_trim():
    qtile.call_later(MALLOC_TRIM_INTERVAL, _malloc_trim)


# Window transparency
# Compositor (xcompmgr/fastcompmgr) has no opacity rules, only _NET_WM_WINDOW_OPACITY;
# qtile sets focused 0.90 / others 0.85 here.
_OPACITY_FOCUSED = 0.90
_OPACITY_UNFOCUSED = 0.85

def _apply_opacity(focused):
    for w in list(qtile.windows_map.values()):
        try:
            if SCREENSHOT_EDITOR.compare(w):
                continue   # stays opaque, see _keep_on_top
            w.opacity = _OPACITY_FOCUSED if w is focused else _OPACITY_UNFOCUSED
        except Exception:
            pass

@hook.subscribe.client_focus
def _opacity_on_focus(window):
    _apply_opacity(window)

@hook.subscribe.client_managed
def _opacity_on_managed(window):
    try:
        window.opacity = _OPACITY_UNFOCUSED
    except Exception:
        pass

@hook.subscribe.client_managed
def _citrix_never_minimize(window):
    """wfica iconifies itself (e.g. fullscreen losing focus), and qtile's Wayland
    backend grants every minimize request (auto_minimize is not consulted), so
    the session vanished with no way back. Refuse minimizing for Citrix windows."""
    if WAYLAND and (CITRIX_SESSION.compare(window) or CITRIX_DIALOG.compare(window)):
        window.handle_request_minimize = lambda minimize: False
        if window.minimized:
            window.minimized = False


def _fit_on_screen(window, margin=24):
    """Centre a floating window in its screen's free area (below the bar),
    shrunk to fit. qtile's center() keeps the window's own size, so a portal
    file picker wider than the 1200 px portrait panel (GTK remembers the size
    from bigger monitors) hung off both edges with parts unreachable."""
    scr = window.group.screen if window.group else None
    if scr is None:
        return
    w = min(window.width, scr.dwidth - 2 * margin)
    h = min(window.height, scr.dheight - 2 * margin)
    window.place(scr.dx + (scr.dwidth - w) // 2, scr.dy + (scr.dheight - h) // 2,
                 w, h, window.borderwidth, window.bordercolor, above=True)


@hook.subscribe.client_managed
def _keep_on_top(window):
    if not any(m.compare(window) for m in ON_TOP):
        return
    if SCREENSHOT_EDITOR.compare(window):
        window.opacity = 1.0
    _fit_on_screen(window)
    # bring_to_front, not keep_above: on Wayland keep_above is a layer BELOW
    # max-layout and fullscreen windows; bring-to-front sits above both, under
    # the bar/notifications. qtile only re-layers a window on float-state
    # changes, so it stays there while the window is open (dragging included).
    window.bring_to_front()
    window.focus()

@hook.subscribe.startup_complete
def _opacity_on_start():
    _apply_opacity(qtile.current_window)
