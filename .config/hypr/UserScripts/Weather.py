#!/usr/bin/env python3
"""Weather for waybar's custom/weather module -- data from Open-Meteo.

Open-Meteo (https://open-meteo.com): free, no API key, plain JSON, DWD ICON /
Météo-France AROME / GeoSphere Austria models.

History: this file used to be the rxyhn wttr.in script (unused); Weather.sh
was the live wttr.in one until 2026-09-15. wttr.in is a single-maintainer
hobby service -- expired TLS certs, 503s and rate-limit pages are a
recurring thing -- and returns ASCII art that had to be scraped with
`sed 's/^.{15}//'`, so every hiccup left the bar showing an "!" with an
empty tooltip until the cache expired. A rofi -dmenu forecast was tried in
between and looked like a list of file names, hence the GTK pane.

Usage:
  Weather.py          bar output (waybar json); also written to BAR_FILE
  Weather.py -f       force a refresh (ignore the cache age), then bar output
  Weather.py --refresh
                      what the systemd user timer runs (weather.timer, every
                      15 min): fetch if the cache is about to expire, write
                      BAR_FILE, poke waybar (signal 9). Exit 1 when the
                      fetch failed so the unit's Restart=on-failure retries.
  Weather.py --pane   forecast pane (see pane.py for the shared scaffold):
                      current details, next 12 h, 7 days

Since 2026-09-16 the waybar module no longer runs this script on its
interval: with three monitors that was three python starts (~50 ms CPU
each) every 15 min, all racing for the same cache. The timer refreshes
once, and the module's exec just cats BAR_FILE (falling back to this
script only if the file is missing or older than 20 min, i.e. the timer
is not running).

Failure behaviour: a failed fetch never overwrites the cache. With a cache
younger than STALEAGE the old values are shown dimmed (class "stale", reason
in the tooltip); with nothing usable the module hides itself (empty text)
and the reason goes to stderr, i.e. waybar's log.

Icons: Nerd Font "md-weather_*" glyphs (Material Design set, so they all
share one size/baseline). Every codepoint below was looked up by glyph name
in the installed JetBrainsMono Nerd Font (fontTools) -- see NetworkMenu.sh
on why guessing codepoints is not done in this repo.

Bar mode deliberately imports nothing GTK-related: it runs every 15 min.
Bar clicks: left = pane, right = windy.com (the detailed view), middle = refresh.
"""

import json
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime

PLACE = "Vienna"
LAT, LON = 48.21, 16.37

CACHE = os.path.expanduser("~/.cache/rbn/weather.json")
BAR_FILE = os.path.expanduser("~/.cache/rbn/weather.bar.json")   # what the waybar module cats
MAXAGE = 900        # s; Open-Meteo refreshes "current" every 15 min
STALEAGE = 21600    # s; keep showing old data this long while the API is unreachable, then hide

BROWSER_URL = f"https://www.windy.com/{LAT}/{LON}?{LAT},{LON},9"
API = (
    "https://api.open-meteo.com/v1/forecast"
    f"?latitude={LAT}&longitude={LON}"
    "&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
    "precipitation,weather_code,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
    "&hourly=temperature_2m,precipitation_probability,precipitation,weather_code,is_day"
    "&forecast_hours=12"
    "&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,"
    "precipitation_sum,precipitation_probability_max,wind_speed_10m_max"
    "&forecast_days=7&timezone=auto"
)


# ------------------------------------------------------------ icons/text --

SUNNY = "\U000F0599"          # md-weather_sunny
NIGHT = "\U000F0594"          # md-weather_night
PARTLY = "\U000F0595"         # md-weather_partly_cloudy
NIGHT_PARTLY = "\U000F0F31"   # md-weather_night_partly_cloudy
CLOUDY = "\U000F0590"         # md-weather_cloudy
FOG = "\U000F0591"            # md-weather_fog
PARTLY_RAINY = "\U000F0F33"   # md-weather_partly_rainy
RAINY = "\U000F0597"          # md-weather_rainy
POURING = "\U000F0596"        # md-weather_pouring
SNOWY_RAINY = "\U000F067F"    # md-weather_snowy_rainy
PARTLY_SNOWY = "\U000F0F34"   # md-weather_partly_snowy
SNOWY = "\U000F0598"          # md-weather_snowy
SNOWY_HEAVY = "\U000F0F36"    # md-weather_snowy_heavy
LIGHTNING_RAINY = "\U000F067E"  # md-weather_lightning_rainy
HAIL = "\U000F0592"           # md-weather_hail
UNKNOWN = "\U0000F06A"        # fa-exclamation_circle

SUNRISE_ICON = "\U000F059C"   # md-weather_sunset_up
SUNSET_ICON = "\U000F059B"    # md-weather_sunset_down
WIND_ICON = "\U000F059D"      # md-weather_windy
HUMIDITY_ICON = "\U000F058E"  # md-water_percent
THERMO_ICON = "\U000F050F"    # md-thermometer

# WMO weather code -> (text, day icon, night icon, css kind)
# css kind maps onto the class names waybar/style*.css already know.
WMO = {
    0:  ("Clear sky",                SUNNY,           NIGHT,         "clear"),
    1:  ("Mainly clear",             SUNNY,           NIGHT,         "clear"),
    2:  ("Partly cloudy",            PARTLY,          NIGHT_PARTLY,  "cloudy"),
    3:  ("Overcast",                 CLOUDY,          CLOUDY,        "cloudy"),
    45: ("Fog",                      FOG,             FOG,           "cloudy"),
    48: ("Freezing fog",             FOG,             FOG,           "cloudy"),
    51: ("Light drizzle",            PARTLY_RAINY,    RAINY,         "rainy"),
    53: ("Drizzle",                  PARTLY_RAINY,    RAINY,         "rainy"),
    55: ("Heavy drizzle",            PARTLY_RAINY,    RAINY,         "rainy"),
    56: ("Light freezing drizzle",   SNOWY_RAINY,     SNOWY_RAINY,   "rainy"),
    57: ("Freezing drizzle",         SNOWY_RAINY,     SNOWY_RAINY,   "rainy"),
    61: ("Light rain",               PARTLY_RAINY,    RAINY,         "rainy"),
    63: ("Rain",                     RAINY,           RAINY,         "rainy"),
    65: ("Heavy rain",               POURING,         POURING,       "rainy"),
    66: ("Light freezing rain",      SNOWY_RAINY,     SNOWY_RAINY,   "rainy"),
    67: ("Freezing rain",            SNOWY_RAINY,     SNOWY_RAINY,   "rainy"),
    71: ("Light snow",               PARTLY_SNOWY,    SNOWY,         "snowy"),
    73: ("Snow",                     SNOWY,           SNOWY,         "snowy"),
    75: ("Heavy snow",               SNOWY_HEAVY,     SNOWY_HEAVY,   "snowy"),
    77: ("Snow grains",              PARTLY_SNOWY,    SNOWY,         "snowy"),
    80: ("Light showers",            PARTLY_RAINY,    RAINY,         "rainy"),
    81: ("Showers",                  RAINY,           RAINY,         "rainy"),
    82: ("Violent showers",          POURING,         POURING,       "rainy"),
    85: ("Light snow showers",       PARTLY_SNOWY,    SNOWY,         "snowy"),
    86: ("Snow showers",             SNOWY_HEAVY,     SNOWY_HEAVY,   "snowy"),
    95: ("Thunderstorm",             LIGHTNING_RAINY, LIGHTNING_RAINY, "severe"),
    96: ("Thunderstorm, light hail", HAIL,            HAIL,          "severe"),
    99: ("Thunderstorm, heavy hail", HAIL,            HAIL,          "severe"),
}
CSS_CLASS = {
    ("clear", True): "sunnyDay",        ("clear", False): "clearNight",
    ("cloudy", True): "cloudyFoggyDay", ("cloudy", False): "cloudyFoggyNight",
    ("rainy", True): "rainyDay",        ("rainy", False): "rainyNight",
    ("snowy", True): "showyIcyDay",     ("snowy", False): "snowyIcyNight",  # sic, matches the css
    ("severe", True): "severe",         ("severe", False): "severe",
}


def describe(code):
    return WMO.get(code, (f"Unknown ({code})",))[0]


def icon(code, is_day):
    entry = WMO.get(code)
    if not entry:
        return UNKNOWN
    return entry[1] if is_day else entry[2]


def css_class(code, is_day):
    entry = WMO.get(code)
    return CSS_CLASS[(entry[3], bool(is_day))] if entry else "default"


def wind_dir(deg):
    return ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][int((deg + 22) // 45) % 8]


def hhmm(iso):
    return iso[11:16]


def weekday(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%a %d.%m.")


# --------------------------------------------------------------- data ----

def cache_age():
    try:
        return time.time() - os.stat(CACHE).st_mtime
    except FileNotFoundError:
        return float("inf")


def fetch():
    """Refresh the cache. Returns None on success, else a short reason."""
    try:
        with urllib.request.urlopen(API, timeout=10) as r:
            raw = r.read()
        data = json.loads(raw)
        if data.get("current", {}).get("temperature_2m") is None or len(data.get("daily", {}).get("time", [])) < 7:
            return "unexpected answer from open-meteo.com"
    except urllib.error.HTTPError as e:
        return f"open-meteo.com returned HTTP {e.code}"
    except urllib.error.URLError as e:
        r = e.reason
        if isinstance(r, ssl.SSLCertVerificationError):
            return f"TLS error: {r.verify_message}"
        if isinstance(r, socket.gaierror):
            return "DNS lookup failed"
        if isinstance(r, (socket.timeout, TimeoutError)):
            return "timeout"
        return str(r)
    except (TimeoutError, socket.timeout):
        return "timeout"
    except (ValueError, OSError) as e:
        return str(e)
    # only replace the cache with a complete, valid answer
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE + ".tmp", "wb") as f:
        f.write(raw)
    os.replace(CACHE + ".tmp", CACHE)
    return None


def load(force=False):
    """Returns (data or None, fetch_error, stale_note)."""
    error = None
    if force or cache_age() > MAXAGE:
        error = fetch()
    try:
        with open(CACHE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None, error or "no data", None
    stale = None
    if error:
        stale = f"stale, from {datetime.fromtimestamp(os.stat(CACHE).st_mtime):%H:%M} – {error}"
    return data, error, stale


# ---------------------------------------------------------------- bar ----

HIDDEN = json.dumps({"text": "", "alt": "", "tooltip": "", "class": "hidden"})


def write_bar(payload):
    """Atomically write the module's JSON line to BAR_FILE."""
    os.makedirs(os.path.dirname(BAR_FILE), exist_ok=True)
    with open(BAR_FILE + ".tmp", "w") as f:
        f.write(payload + "\n")
    os.replace(BAR_FILE + ".tmp", BAR_FILE)


def bar_payload(force):
    """(json line for waybar, fetch error or None)."""
    data, error, stale = load(force)
    if data is None:
        print(f"Weather.py: {error}", file=sys.stderr)
        return HIDDEN, error   # waybar hides a custom module whose text is empty
    if error and cache_age() > STALEAGE:
        print(f"Weather.py: cache too old, hiding ({error})", file=sys.stderr)
        return HIDDEN, error

    c, d = data["current"], data["daily"]
    code, day = c["weather_code"], bool(c["is_day"])
    cond = describe(code)
    tooltip = "\n".join([
        f"{PLACE} – {cond}",
        f"{c['temperature_2m']} °C, feels like {round(c['apparent_temperature'])} °C"
        f"  ·  today {round(d['temperature_2m_min'][0])}° / {round(d['temperature_2m_max'][0])}°",
        f"Wind {round(c['wind_speed_10m'])} km/h {wind_dir(c['wind_direction_10m'])}, gusts {round(c['wind_gusts_10m'])} km/h"
        f"  ·  humidity {c['relative_humidity_2m']} %",
        f"Rain today {round(d['precipitation_sum'][0], 1)} mm ({d['precipitation_probability_max'][0] or 0} %)"
        f"  ·  sunrise {hhmm(d['sunrise'][0])}, sunset {hhmm(d['sunset'][0])}",
        f"Updated {hhmm(c['time'])}  ·  click: forecast, middle-click: refresh",
    ] + ([f"({stale})"] if stale else []))
    return json.dumps({
        "text": f"{round(c['temperature_2m'])} °C {icon(code, day)}",
        "alt": cond,
        "tooltip": tooltip,
        "class": "stale" if stale else css_class(code, day),
    }, ensure_ascii=False), error


def bar(force):
    payload, _ = bar_payload(force)
    write_bar(payload)
    print(payload)


def refresh():
    """Timer entry point: refresh a little early so a 15-min timer never
    lands just inside MAXAGE and skips a whole period."""
    payload, error = bar_payload(force=cache_age() > MAXAGE - 120)
    write_bar(payload)
    subprocess.run(["pkill", "-RTMIN+9", "waybar"])
    return 1 if error else 0


# --------------------------------------------------------------- pane ----

def make_pane():
    """(Pane, build) -- run standalone via pane_main(), or hosted by hyprpanes.py."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pane import Pane, spawn, poke_waybar

    css = """
    .hero-icon  { font-size: 64px; margin-right: 6px; }
    .hero-temp  { font-size: 40px; font-weight: bold; }
    .hero-cond  { font-size: 15px; }
    .detail-icon { font-size: 15px; min-width: 22px; }
    .hour-time { font-size: 11px; }
    .hour-icon { font-size: 22px; }
    .hour-temp { font-weight: bold; }
    .hour-rain { font-size: 11px; }
    .day-icon { font-size: 20px; }
    .day-hi { font-weight: bold; }
    """
    pn = Pane("hypr.weather-pane", anchor="left", css=css)

    def temp_bar(lo, hi, wmin, wmax):
        """Horizontal min..max bar, relative to the week's range."""
        Gtk, Gdk, p = pn.Gtk, pn.Gdk, pn.p
        area = Gtk.DrawingArea(content_width=120, content_height=8, valign=Gtk.Align.CENTER, hexpand=True)
        track, fill = Gdk.RGBA(), Gdk.RGBA()
        track.parse(p["overlay"]); fill.parse(p["accent"])

        def draw(_a, cr, w, h):
            span = max(wmax - wmin, 1)
            x0, x1 = w * (lo - wmin) / span, w * (hi - wmin) / span
            for x, width, rgba in ((0, w, track), (x0, max(x1 - x0, h), fill)):
                cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)
                r = h / 2
                cr.new_sub_path()
                cr.arc(x + r, r, r, 3.14159 / 2, 3 * 3.14159 / 2)
                cr.arc(x + width - r, r, r, -3.14159 / 2, 3.14159 / 2)
                cr.close_path()
                cr.fill()
        area.set_draw_func(draw)
        return area

    def build(pn, root, force=False):
        Gtk, L = pn.Gtk, pn.label
        data, error, stale = load(force)
        if force:
            write_bar(bar_payload(False)[0])   # the module cats this file, so refresh it before the poke
            poke_waybar(9)
        if data is None:
            root.append(L(f"Weather unavailable: {error}", "warm"))
            return
        c, d, h = data["current"], data["daily"], data["hourly"]
        code, day = c["weather_code"], bool(c["is_day"])

        # -- header: big icon + temperature | details grid
        head = pn.box(spacing=24)
        head.append(L(icon(code, day), "hero-icon warm", valign=Gtk.Align.CENTER))
        col = pn.box(vertical=True, valign=Gtk.Align.CENTER)
        col.append(L(f"{round(c['temperature_2m'])}°", "hero-temp"))
        col.append(L(describe(code), "hero-cond"))
        col.append(L(f"{PLACE}  ·  {round(d['temperature_2m_min'][0])}° / {round(d['temperature_2m_max'][0])}° today", "muted small"))
        head.append(col)
        grid = Gtk.Grid(column_spacing=10, row_spacing=4, halign=Gtk.Align.END, hexpand=True, valign=Gtk.Align.CENTER)
        details = [
            (THERMO_ICON, "Feels like", f"{round(c['apparent_temperature'])}°"),
            (WIND_ICON, "Wind", f"{round(c['wind_speed_10m'])} km/h {wind_dir(c['wind_direction_10m'])}, gusts {round(c['wind_gusts_10m'])}"),
            (HUMIDITY_ICON, "Humidity", f"{c['relative_humidity_2m']} %"),
            (RAINY, "Rain today", f"{round(d['precipitation_sum'][0], 1)} mm  ·  {d['precipitation_probability_max'][0] or 0} %"),
            (SUNRISE_ICON, "Sunrise", hhmm(d["sunrise"][0])),
            (SUNSET_ICON, "Sunset", hhmm(d["sunset"][0])),
        ]
        for i, (ic, key, val) in enumerate(details):
            r, cidx = i % 3, (i // 3) * 3
            grid.attach(L(ic, "detail-icon accent2", xalign=0.5), cidx, r, 1, 1)
            grid.attach(L(key, "muted"), cidx + 1, r, 1, 1)
            grid.attach(L(val, margin_end=18 if cidx == 0 else 0), cidx + 2, r, 1, 1)
        head.append(grid)
        root.append(head)

        # -- next 12 hours
        root.append(pn.section("Next 12 hours"))
        hours = pn.box(cls="card", homogeneous=True)
        for i, t in enumerate(h["time"]):
            colh = pn.box(vertical=True, spacing=2)
            colh.append(L("now" if i == 0 else hhmm(t), "hour-time " + ("warm" if i == 0 else "muted"), xalign=0.5))
            colh.append(L(icon(h["weather_code"][i], h["is_day"][i]), "hour-icon accent", xalign=0.5))
            colh.append(L(f"{round(h['temperature_2m'][i])}°", "hour-temp", xalign=0.5))
            prob = h["precipitation_probability"][i] or 0
            colh.append(L(f"{prob} %" if prob else " ", "hour-rain cold", xalign=0.5))
            hours.append(colh)
        root.append(hours)

        # -- 7 days
        root.append(pn.section("7 days"))
        days = Gtk.Grid(column_spacing=14, row_spacing=6)
        days.add_css_class("card")
        los, his = d["temperature_2m_min"], d["temperature_2m_max"]
        wmin, wmax = min(los), max(his)
        for i, t in enumerate(d["time"]):
            prob = d["precipitation_probability_max"][i] or 0
            mm = round(d["precipitation_sum"][i], 1)
            days.attach(L("Today" if i == 0 else weekday(t), margin_start=6), 0, i, 1, 1)
            days.attach(L(icon(d["weather_code"][i], True), "day-icon accent", xalign=0.5), 1, i, 1, 1)
            days.attach(L(describe(d["weather_code"][i]), "muted", hexpand=True), 2, i, 1, 1)
            days.attach(L(f"{prob} %  {mm} mm" if prob or mm else "", "cold", xalign=1.0), 3, i, 1, 1)
            days.attach(L(f"{round(los[i])}°", "muted", xalign=1.0), 4, i, 1, 1)
            days.attach(temp_bar(los[i], his[i], wmin, wmax), 5, i, 1, 1)
            days.attach(L(f"{round(his[i])}°", "day-hi", margin_end=6), 6, i, 1, 1)
        root.append(days)

        # -- footer
        foot = pn.box(spacing=8, cls="footer")
        foot.append(L(f"Updated {hhmm(c['time'])}  ·  Open-Meteo", hexpand=True, valign=Gtk.Align.CENTER))
        if stale:
            foot.append(L(f"({stale})", "warm", valign=Gtk.Align.CENTER))
        foot.append(pn.button("Refresh", lambda: (pn.clear(root), build(pn, root, force=True))))
        foot.append(pn.button("windy.com", lambda: (spawn(["xdg-open", BROWSER_URL]), pn.close())))
        root.append(foot)

    return pn, build


def pane_main():
    pn, build = make_pane()
    pn.run(build)


# --------------------------------------------------------------- main ----

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--pane":
        pane_main()
    elif arg == "--refresh":
        sys.exit(refresh())
    else:
        bar(force=(arg == "-f"))
