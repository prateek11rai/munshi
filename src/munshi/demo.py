import hashlib
import shutil
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from munshi.config import demo_home, ensure_home
from munshi.store import Block, Event, Note, Store
from munshi.timefmt import SLOT_SECONDS, SystemClock, at, day_bounds, day_of, slot_start
from munshi.write.notes import facts

DEMO_NOW = "16:05"
UNWRITTEN_FROM = "15:15"
CODE, TERM, CHROME, PREVIEW, FINDER = "Code", "Ghostty", "Google Chrome", "Preview", "Finder"

ISSUE = (CHROME, "Issue #18 · tidepool")
CACHE = (CODE, "cache.py — tidepool")
PYTEST = (TERM, "~/code/tidepool — pytest")
CI = (CODE, "ci.yml — tidepool")
TABLES = (PREVIEW, "tide-tables-2026.pdf")
WAL = (CHROME, "SQLite WAL mode")
FSYNC = (CHROME, "fsync and write barriers")
NAV = (CODE, "nav.md — lantern")
SIDEBAR = (CODE, "sidebar.js — lantern")
PREVIEW_PAGE = (CHROME, "Sidebar preview · lantern")
HN = (CHROME, "Hacker News")
BEATS = (CHROME, "lo-fi beats - YouTube")
DOWNLOADS = (FINDER, "Downloads")


@dataclass
class Segment:
    """A stretch of made-up work: who did what, and which windows were open."""

    start: str
    end: str
    project: str | None
    topic: str = ""
    summary: str = ""
    windows: tuple[tuple[tuple[str, str], int], ...] = ()


YESTERDAY = [
    Segment("09:15", "09:40", "tidepool", "CI fix", "Read issue about the failing tidepool CI",
            ((ISSUE, 25),)),
    Segment("09:40", "10:25", "tidepool", "CI fix", "Fixed the tidepool CI job and pytest run",
            ((PYTEST, 6), (CI, 9))),
    Segment("10:25", "10:40", None),
    Segment("10:40", "12:10", "tidepool", "tide-chart caching",
            "Tightened tide chart caching in tidepool", ((CACHE, 8), (PYTEST, 4), (TABLES, 3))),
    Segment("12:10", "13:00", "Other", "SQLite WAL reading",
            "Read about SQLite WAL mode, fsync and write barriers", ((WAL, 7), (FSYNC, 5))),
    Segment("13:00", "14:00", None),
    Segment("14:00", "15:45", "lantern", "docs navigation",
            "Reworked the lantern docs sidebar navigation", ((NAV, 7), (SIDEBAR, 5),
                                                             (PREVIEW_PAGE, 3))),
    Segment("15:45", "16:10", None),
    Segment("16:10", "17:00", "tidepool", "tide-chart caching",
            "Tightened tide chart caching in tidepool", ((CACHE, 9), (PYTEST, 5))),
    Segment("17:00", "17:40", "Other", "SQLite WAL reading",
            "Read about SQLite WAL mode with lo-fi beats", ((WAL, 10), (BEATS, 4))),
    Segment("17:40", "18:10", None),
]  # fmt: skip

TODAY = [
    Segment("09:30", "10:15", "tidepool", "tide-chart caching",
            "Tightened tide chart caching in tidepool", ((CACHE, 9), (PYTEST, 5))),
    Segment("10:15", "10:30", "Other", "news", "Skimmed Hacker News", ((HN, 15),)),
    Segment("10:30", "11:50", "lantern", "docs navigation",
            "Reworked the lantern docs sidebar navigation", ((NAV, 8), (PREVIEW_PAGE, 4))),
    Segment("11:50", "12:05", None),
    Segment("12:05", "12:50", "Other", "SQLite WAL reading",
            "Read about SQLite WAL mode, fsync and write barriers", ((WAL, 8), (FSYNC, 5))),
    Segment("12:50", "13:40", None),
    Segment("13:40", "14:10", "Other", "news", "Skimmed Hacker News, YouTube beats and downloads",
            ((HN, 6), (BEATS, 3), (DOWNLOADS, 2))),
    Segment("14:10", "15:40", "tidepool", "tide-chart caching",
            "Tightened tide chart caching in tidepool",
            ((CACHE, 9), (PYTEST, 4), (ISSUE, 3), (TABLES, 2))),
    Segment("15:40", "16:00", "Other", "SQLite WAL reading", "Read about SQLite WAL mode",
            ((WAL, 20),)),
]  # fmt: skip

GIT = {
    "yesterday": [
        ("10:20", "tidepool", ["ci: pin python for the test job"], ["ci.yml"]),
        ("12:05", "tidepool", ["fix: cache tide chart per station"], ["cache.py", "test_cache.py"]),
        ("15:30", "lantern", ["docs: group pages in the sidebar"], []),
        ("16:55", "tidepool", [], ["cache.py", "stations.json"]),
    ],
    "today": [
        ("10:10", "tidepool", [], ["cache.py"]),
        ("11:45", "lantern", ["docs: link the tide glossary"], []),
        ("15:05", "tidepool", ["fix: refresh tide chart cache at midnight"], ["cache.py"]),
        ("15:55", "tidepool", [], ["cache.py", "test_cache.py", "stations.json"]),
    ],
}

YESTERDAY_BULLETS = [
    ("tidepool: tide-chart caching and a CI fix", "tidepool"),
    ("lantern: docs navigation in the sidebar", "lantern"),
    ("Reading: SQLite WAL and fsync", "Other"),
]
WHERE_TEXT = "You were tightening the tide-chart caching in tidepool, then reading SQLite WAL docs."


def add_day(store: Store, day: date, segments: list[Segment], git: list) -> None:
    """Add a made-up day's window, away and git events.

    Args:
        store: The demo store.
        day: The day.
        segments: The day's segments.
        git: (time, repo, commits, uncommitted files) tuples.
    """
    for seg in segments:
        start, end = at(day, seg.start), at(day, seg.end)
        if seg.project is None:
            store.add_event(Event("away", start, end))
            continue
        t, n = start, 0
        while t < end:
            (app, title), minutes = seg.windows[n % len(seg.windows)]
            stop = min(end, t + minutes * 60)
            store.add_event(Event("window", t, stop, app=app, title=title))
            t, n = stop, n + 1
    for when, repo, commits, files in git:
        detail = {
            "branch": "main",
            "commits": [
                {"hash": hashlib.sha256(s.encode()).hexdigest()[:7], "subject": s} for s in commits
            ],
            "dirty": len(files),
            "files": files,
        }
        store.add_event(Event("git", at(day, when), at(day, when), repo=repo, detail=detail))


def add_blocks(store: Store, day: date, segments: list[Segment], until: float) -> None:
    """Add the fixed, already written blocks for each finished slot before `until`.

    Args:
        store: The demo store.
        day: The day.
        segments: The day's segments.
        until: Slots starting at or after this stay unwritten.
    """
    lo, hi = day_bounds(day)
    events = store.events(lo, hi, ("window",))
    slot = slot_start(at(day, segments[0].start))
    while slot < min(until, at(day, segments[-1].end)):
        end = slot + SLOT_SECONDS
        for seg in segments:
            s, e = max(at(day, seg.start), slot), min(at(day, seg.end), end)
            if seg.project is None or e <= s:
                continue
            inside = [ev for ev in events if ev.start < e and ev.end > s]
            active = sum(min(ev.end, e) - max(ev.start, s) for ev in inside)
            block = Block(slot, s, e, active, seg.project, seg.topic, seg.summary, "demo",
                          [ev.id for ev in inside if ev.id])  # fmt: skip
            store.add_block(block)
        store.mark_slot(slot, end, accepted=1)
        slot = end


def load(home: Path | None = None, today: date | None = None) -> Path:
    """Write the two made-up days into the demo home, replacing what was there.

    Args:
        home: Demo home; defaults to `./.data/demo`.
        today: The demo's "today"; defaults to the real today.

    Returns:
        The demo home.
    """
    home = home or demo_home()
    clear(home)
    ensure_home(home)
    today = today or date.today()
    yesterday = today - timedelta(days=1)
    store = Store.at_home(home)
    demo_now = at(today, DEMO_NOW)
    store.set("demo_offset", demo_now - time.time())
    store.set("demo_day", today.isoformat())
    store.set("known_repos", ["lantern", "tidepool"])
    add_day(store, yesterday, YESTERDAY, GIT["yesterday"])
    add_day(store, today, TODAY, GIT["today"])
    add_blocks(store, yesterday, YESTERDAY, at(today, "00:00"))
    add_blocks(store, today, TODAY, at(today, UNWRITTEN_FROM))
    lo, hi = day_bounds(yesterday)
    blocks = store.blocks(lo, hi)
    bullets = [
        {"text": text, "cites": [b.id for b in blocks if b.project == project]}
        for text, project in YESTERDAY_BULLETS
    ]
    store.add_note(
        Note("day", yesterday.isoformat(), hi, lo, hi, "\n".join(t for t, _ in YESTERDAY_BULLETS),
             "demo", sorted(c for b in bullets for c in b["cites"]), {"bullets": bullets})
    )  # fmt: skip
    written = demo_now - 6 * 60
    recent = store.blocks(written - 2 * 3600, written)
    store.add_note(
        Note("where", today.isoformat(), written, written - 2 * 3600, written, WHERE_TEXT, "demo",
             [b.id for b in recent if b.id], facts(store, written))
    )  # fmt: skip
    store.close()
    return home


def clear(home: Path | None = None) -> None:
    """Delete the demo home.

    Args:
        home: Demo home; defaults to `./.data/demo`.
    """
    home = home or demo_home()
    if home.exists():
        shutil.rmtree(home)


def clock(store: Store) -> SystemClock:
    """Return the demo clock: real time shifted so the demo starts at 16:05 on its day.

    Args:
        store: The demo store.

    Returns:
        The clock.
    """
    return SystemClock(float(store.get("demo_offset", 0.0)))


def is_stale(store: Store) -> bool:
    """Tell whether the demo needs loading (missing, or its day has passed).

    Args:
        store: The demo store.

    Returns:
        True when `demo load` should run.
    """
    day = store.get("demo_day")
    return day is None or day_of(clock(store).now()).isoformat() != day
