#!/usr/bin/env python3
"""Calendar pane for waybar's clock module (left-click).

Month grid with week numbers plus the events of the selected day and what's
coming up, read straight from Thunderbird's calendar storage
(~/.thunderbird/<profile>/calendar-data/cache.sqlite for network calendars,
local.sqlite for local ones) -- so it's your real Google/CalDAV events, no
extra sync. Calendar names/colours come from the profile's prefs.js.
The DB files are copied (incl. -wal) before reading so a running
Thunderbird is never touched. Recurring events are expanded with
dateutil (RRULE/RDATE/EXDATE + modified instances).

Right-click on the clock (and the button here) opens Thunderbird's
calendar tab. Thunderbird 155's command line has no "go to date" option
(only -calendar / -file), so "open for that date" isn't possible from
outside -- the pane shows the day's events itself instead.

  CalendarPane.py            open/close the pane
  CalendarPane.py --dump     print this month's events (debugging)
"""

import calendar
import glob
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pane import Pane, spawn  # noqa: E402

TB_PROFILES = os.path.expanduser("~/.thunderbird")
IGNORE_CALENDARS = {"Kalenderwochen"}   # week numbers are drawn by the grid itself
LOCAL_TZ = datetime.now().astimezone().tzinfo

FLAG_ALLDAY = 8
FLAG_RECUR = 16
PREV = "\U000F0141"     # md-chevron_left
NEXT = "\U000F0142"     # md-chevron_right
TODAY_ICON = "\U000F00F0"   # md-calendar_clock
CLOCK = "\U000F0150"    # md-clock_outline
PIN = "\U000F034E"      # md-map_marker


# ------------------------------------------------------------ thunderbird --

def profile_dir():
    """Thunderbird's default-release profile (the one with calendar data)."""
    cands = sorted(glob.glob(f"{TB_PROFILES}/*/calendar-data/cache.sqlite"), key=os.path.getmtime, reverse=True)
    return os.path.dirname(os.path.dirname(cands[0])) if cands else None


def calendars(profile):
    """{cal_id: (name, color)} for enabled calendars."""
    cals = {}
    try:
        with open(f"{profile}/prefs.js") as f:
            prefs = f.read()
    except OSError:
        return cals
    for m in re.finditer(r'user_pref\("calendar\.registry\.([\w-]+)\.(name|color|disabled)", (.*?)\);', prefs):
        cid, key, val = m.groups()
        cals.setdefault(cid, {})[key] = val.strip('"')
    return {cid: (c.get("name", cid), c.get("color", "#7aa2f7")) for cid, c in cals.items()
            if c.get("disabled") != "true" and c.get("name") not in IGNORE_CALENDARS}


def open_db(path):
    """Copy the sqlite file (+wal/shm) to a temp dir and open that read-only."""
    tmp = tempfile.mkdtemp(prefix="calpane-")
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            shutil.copy2(path + suffix, os.path.join(tmp, "db.sqlite" + suffix))
    return sqlite3.connect(f"file:{tmp}/db.sqlite?mode=ro", uri=True), tmp


def to_dt(us, tz):
    """Thunderbird stores µs since epoch; all-day events as local midnight in tz."""
    try:
        zone = ZoneInfo(tz) if tz and tz not in ("floating", "UTC") else LOCAL_TZ
    except Exception:  # noqa: BLE001
        zone = LOCAL_TZ
    return datetime.fromtimestamp(us / 1e6, tz=zone)


def fix_until(rrule, zone):
    """dateutil wants UNTIL naive when DTSTART is naive: convert Z/date-only UNTIL to zone-local naive."""
    def repl(m):
        val = m.group(1)
        if val.endswith("Z"):
            dt = datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(zone)
            return "UNTIL=" + dt.strftime("%Y%m%dT%H%M%S")
        if len(val) == 8:
            return "UNTIL=" + val + "T235959"
        return "UNTIL=" + val
    return re.sub(r"UNTIL=([0-9TZ]+)", repl, rrule)


def parse_dates(line, zone):
    """EXDATE/RDATE line -> naive zone-local datetimes."""
    out = []
    head, _, body = line.partition(":")
    tzid = re.search(r"TZID=([^;:]+)", head)
    src_zone = ZoneInfo(tzid.group(1)) if tzid else None
    for v in body.split(","):
        v = v.strip()
        try:
            if v.endswith("Z"):
                dt = datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(zone)
            elif "T" in v:
                dt = datetime.strptime(v, "%Y%m%dT%H%M%S")
                if src_zone:
                    dt = dt.replace(tzinfo=src_zone).astimezone(zone)
            else:
                dt = datetime.strptime(v, "%Y%m%d")
            out.append(dt.replace(tzinfo=None))
        except ValueError:
            pass
    return out


def events(start, end):
    """Event occurrences overlapping [start, end) (aware datetimes), sorted."""
    profile = profile_dir()
    if not profile:
        return [], "no Thunderbird profile with calendar data found"
    cals = calendars(profile)
    from dateutil.rrule import rrulestr, rruleset
    out = []
    for dbname in ("cache.sqlite", "local.sqlite"):
        path = f"{profile}/calendar-data/{dbname}"
        if not os.path.exists(path):
            continue
        db, tmp = open_db(path)
        try:
            rec = {}
            for item_id, ical in db.execute("select item_id, icalString from cal_recurrence"):
                rec.setdefault(item_id, []).append(ical.strip())
            props = {}
            for item_id, key, value in db.execute("select item_id, key, value from cal_properties where key='LOCATION'"):
                props[item_id] = value
            exceptions = {}   # parent id -> {recurrence_id µs}
            for (pid, rid) in db.execute("select id, recurrence_id from cal_events where recurrence_id is not null"):
                exceptions.setdefault(pid, set()).add(rid)
            rows = db.execute("select cal_id, id, title, flags, event_start, event_end, event_start_tz, recurrence_id "
                              "from cal_events where ical_status is null or ical_status != 'CANCELLED'").fetchall()
        finally:
            db.close()
            shutil.rmtree(tmp, ignore_errors=True)
        for cal_id, eid, title, flags, s_us, e_us, tz, rid in rows:
            if cal_id not in cals or s_us is None:
                continue
            name, color = cals[cal_id]
            allday = bool(flags & FLAG_ALLDAY)
            s, e = to_dt(s_us, tz), to_dt(e_us or s_us, tz)
            dur = e - s
            starts = []
            if flags & FLAG_RECUR and rid is None and eid in rec:
                zone = s.tzinfo
                s_naive = s.replace(tzinfo=None)
                rs = rruleset()
                try:
                    for line in rec[eid]:
                        if line.startswith("RRULE:"):
                            rs.rrule(rrulestr(fix_until(line, zone), dtstart=s_naive))
                        elif line.startswith("EXDATE"):
                            for d in parse_dates(line, zone):
                                rs.exdate(d if "T" in line.partition(":")[2] else d.replace(hour=s_naive.hour, minute=s_naive.minute))
                        elif line.startswith("RDATE"):
                            for d in parse_dates(line, zone):
                                rs.rdate(d)
                    lo, hi = (start - dur).astimezone(zone).replace(tzinfo=None), end.astimezone(zone).replace(tzinfo=None)
                    skip = exceptions.get(eid, set())
                    for occ in rs.between(lo, hi, inc=True):
                        occ = occ.replace(tzinfo=zone)
                        if int(occ.timestamp() * 1e6) in skip:
                            continue
                        starts.append(occ)
                except Exception:  # noqa: BLE001  (odd rule -> show the first instance only)
                    starts.append(s)
            else:
                starts.append(s)
            for os_ in starts:
                oe = os_ + dur
                if oe > start and os_ < end:
                    out.append(dict(start=os_.astimezone(LOCAL_TZ), end=oe.astimezone(LOCAL_TZ), title=title or "(untitled)",
                                    allday=allday, cal=name, color=color, location=props.get(eid, "")))
    out.sort(key=lambda ev: (ev["start"], not ev["allday"], ev["title"]))
    return out, None


def by_day(evs):
    days = {}
    for ev in evs:
        d = ev["start"].date()
        last = (ev["end"] - timedelta(microseconds=1)).date() if ev["allday"] else ev["end"].date()
        while d <= max(last, ev["start"].date()):
            days.setdefault(d, []).append(ev)
            d += timedelta(days=1)
    return days


# ---------------------------------------------------------------- pane ---

def make_pane():
    """(Pane, build) -- run standalone via pane_main(), or hosted by hyprpanes.py."""
    css = """
    .month { font-size: 16px; font-weight: bold; }
    .dow { font-size: 10px; letter-spacing: 1px; }
    .wk  { font-size: 10px; }
    button.day { padding: 4px 2px; min-width: 40px; min-height: 40px; border-radius: 8px; border-color: transparent;
                 background-color: transparent; }
    button.day:hover { background-color: alpha(currentColor, 0.08); }
    button.day.other label.num { opacity: 0.35; }
    button.day.today { border-color: currentColor; }
    button.day.sel { background-color: alpha(currentColor, 0.18); }
    button.day.sel label.num { font-weight: bold; }
    label.num { font-size: 13px; }
    label.dots { font-size: 8px; }
    .ev-time { font-size: 11px; min-width: 88px; }
    .ev-title { font-size: 13px; }
    .ev-cal { font-size: 10px; }
    .agenda-day { font-size: 11px; font-weight: bold; letter-spacing: 1px; margin-top: 6px; }
    """
    pn = Pane("hypr.calendar-pane", anchor="center", css=css)
    state = dict(month=date.today().replace(day=1), selected=date.today())
    cache = {}

    def month_events(first):
        if first not in cache:
            # grid shows 6 weeks starting the Monday on/before the 1st
            gstart = first - timedelta(days=first.weekday())
            gend = gstart + timedelta(days=42)
            start = datetime.combine(gstart, datetime.min.time(), LOCAL_TZ)
            end = datetime.combine(gend, datetime.min.time(), LOCAL_TZ)
            evs, err = events(start, end)
            cache[first] = (by_day(evs), err, gstart)
        return cache[first]

    def event_row(ev, show_date=False):
        row = pn.box(spacing=10)
        # calendar colour bar (drawn: GTK4 has no per-widget CSS colour without a provider)
        bar = pn.Gtk.DrawingArea(content_width=4, hexpand=False)
        rgba = pn.Gdk.RGBA(); rgba.parse(ev["color"])
        bar.set_draw_func(lambda _a, cr, w, h, rgba=rgba: (cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, 1),
                                                          cr.rectangle(0, 0, w, h), cr.fill()))
        row.append(bar)
        when = "all day" if ev["allday"] else f"{ev['start']:%H:%M} – {ev['end']:%H:%M}"
        if show_date:
            when = f"{ev['start']:%a %d.%m.}  " + ("" if ev["allday"] else f"{ev['start']:%H:%M}")
        row.append(pn.label(when, "ev-time muted", valign=pn.Gtk.Align.CENTER))
        col = pn.box(vertical=True, hexpand=True)
        col.append(pn.label(ev["title"], "ev-title", ellipsize=3, max_width_chars=40))
        sub = ev["cal"] + (f"  ·  {PIN} {ev['location']}" if ev["location"] else "")
        col.append(pn.label(sub, "ev-cal muted", ellipsize=3, max_width_chars=48))
        row.append(col)
        return row

    def build(pn, root):
        Gtk, L = pn.Gtk, pn.label
        first, sel = state["month"], state["selected"]
        days, err, gstart = month_events(first)
        today = date.today()

        cols = pn.box(spacing=22)
        root.append(cols)

        # -- left: month grid
        left = pn.box(vertical=True, spacing=6)
        nav = pn.box(spacing=6)
        nav.append(L(f"{first:%B %Y}", "month", hexpand=True, valign=Gtk.Align.CENTER))

        def go(months):
            m = first.month - 1 + months
            state["month"] = date(first.year + m // 12, m % 12 + 1, 1)
            pn.rebuild()
        nav.append(pn.button(TODAY_ICON, lambda: (state.update(month=today.replace(day=1), selected=today), pn.rebuild()), cls="flat"))
        nav.append(pn.button(PREV, lambda: go(-1), cls="flat"))
        nav.append(pn.button(NEXT, lambda: go(1), cls="flat"))
        left.append(nav)

        grid = Gtk.Grid(column_spacing=2, row_spacing=2)
        grid.attach(L("KW", "wk muted", xalign=0.5), 0, 0, 1, 1)
        for i in range(7):
            d = gstart + timedelta(days=i)
            grid.attach(L(f"{d:%a}".upper()[:2], "dow muted", xalign=0.5), i + 1, 0, 1, 1)
        for w in range(6):
            monday = gstart + timedelta(days=7 * w)
            grid.attach(L(f"{monday.isocalendar()[1]}", "wk muted", xalign=0.5), 0, w + 1, 1, 1)
            for i in range(7):
                d = monday + timedelta(days=i)
                b = Gtk.Button()
                b.add_css_class("day")
                if d.month != first.month:
                    b.add_css_class("other")
                if d == today:
                    b.add_css_class("today")
                if d == sel:
                    b.add_css_class("sel")
                cell = pn.box(vertical=True)
                num = L(str(d.day), "num", xalign=0.5)
                if i >= 5:
                    num.add_css_class("muted")
                cell.append(num)
                evs = days.get(d, [])
                dots = "".join(f'<span foreground="{ev["color"]}">●</span>' for ev in evs[:4])
                dl = L(dots or " ", "dots", xalign=0.5)
                dl.set_use_markup(True)
                cell.append(dl)
                b.set_child(cell)
                b.connect("clicked", lambda _b, d=d: (state.update(selected=d, month=d.replace(day=1)), pn.rebuild()))
                grid.attach(b, i + 1, w + 1, 1, 1)
        left.append(grid)
        cols.append(left)

        # -- right: selected day + upcoming
        right = pn.box(vertical=True, spacing=4, width_request=360)
        title = "Today" if sel == today else ("Tomorrow" if sel == today + timedelta(days=1) else f"{sel:%A}")
        right.append(L(f"{title}  ·  {sel:%d. %B}", "month"))
        card = pn.card(spacing=6)
        sel_evs = days.get(sel, [])
        if err:
            card.append(L(err, "bad small"))
        elif not sel_evs:
            card.append(L("No events.", "muted"))
        for ev in sel_evs:
            card.append(event_row(ev))
        right.append(card)

        # upcoming: next 8 events after the selected day, within the loaded range (+ next month if needed)
        upcoming = []
        for d in sorted(days):
            if d > sel:
                for ev in days[d]:
                    if ev["start"].date() == d and ev not in upcoming:
                        upcoming.append(ev)
        if upcoming:
            right.append(pn.section("Upcoming"))
            card = pn.card(spacing=6)
            for ev in upcoming[:8]:
                card.append(event_row(ev, show_date=True))
            right.append(card)
        cols.append(right)

        foot = pn.box(spacing=8, cls="footer")
        foot.append(L(f"{CLOCK} {datetime.now():%H:%M}  ·  events from Thunderbird", hexpand=True, valign=Gtk.Align.CENTER))
        foot.append(pn.button("Open in Thunderbird", lambda: (spawn(["thunderbird", "-calendar"]), pn.close())))
        root.append(foot)

    return pn, build


def pane_main():
    pn, build = make_pane()
    pn.run(build)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--dump":
        first = date.today().replace(day=1)
        start = datetime.combine(first, datetime.min.time(), LOCAL_TZ)
        evs, err = events(start, start + timedelta(days=35))
        print(err or f"{len(evs)} events")
        for ev in evs:
            print(f"{ev['start']:%a %d.%m. %H:%M}  {'*' if ev['allday'] else ' '}  {ev['title'][:50]:50}  [{ev['cal']}]")
    else:
        pane_main()
