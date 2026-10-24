import pytest

from munshi.collect.fake import ScriptedScanner, ScriptedWindows
from munshi.collect.loop import AWAY_AFTER, Collector, Window
from munshi.config import Config
from munshi.control import UNTIL_RESUME, forget, pause, resume
from munshi.store import Event, Store
from munshi.timefmt import FakeClock

T0 = 1_800_000_000.0


def run(collector, clock, seconds, step=10):
    for _ in range(int(seconds // step)):
        collector.tick()
        clock.advance(step)


def make(steps, away=None, config=None, scanners=(), own_pid=1):
    clock = FakeClock(T0)
    store = Store(":memory:")
    source = ScriptedWindows(
        clock,
        [(T0 + at, app, title) for at, app, title in steps],
        [(T0 + a, T0 + b) for a, b in (away or [])],
    )
    collector = Collector(store, config or Config(), source, clock, scanners, own_pid=own_pid)
    return clock, store, collector


def windows(store):
    return [(e.kind, e.app, e.title, e.start - T0, e.end - T0) for e in store.events(0, 4e9)]


def test_same_window_extends_one_row():
    clock, store, c = make([(0, "Code", "cache.py — tidepool")])
    run(c, clock, 60)
    assert windows(store) == [("window", "Code", "cache.py — tidepool", 0, 50)]


def test_switch_starts_new_contiguous_row():
    clock, store, c = make(
        [(0, "Code", "a.py — tidepool"), (30, "Google Chrome", "SQLite WAL mode")]
    )
    run(c, clock, 60)
    assert windows(store) == [
        ("window", "Code", "a.py — tidepool", 0, 30),
        ("window", "Google Chrome", "SQLite WAL mode", 30, 50),
    ]


def test_ignored_and_only_mode_and_own_pid():
    clock, store, c = make([(0, "1Password", "Vault"), (20, "Code", "x"), (40, "Ghostty", "~")])
    run(c, clock, 60)
    assert [w[1] for w in windows(store)] == ["Code", "Ghostty"]

    config = Config.model_validate({"apps": {"mode": "only", "only": ["Ghostty"]}})
    clock, store, c = make([(0, "Code", "x"), (20, "Ghostty", "~")], config=config)
    run(c, clock, 40)
    assert [w[1] for w in windows(store)] == ["Ghostty"]

    clock, store, c = make([(0, "Python", "Munshi")], own_pid=4242)
    run(c, clock, 30)
    assert windows(store) == []


def test_private_window_keeps_app_only_and_titles_redacted():
    clock, store, c = make(
        [
            (0, "Safari", "Private Browsing — something"),
            (20, "Google Chrome", "mail ana@example.org https://example.com/a?b=1"),
        ]
    )
    run(c, clock, 40)
    assert [(w[1], w[2]) for w in windows(store)] == [
        ("Safari", None),
        ("Google Chrome", "mail [email] example.com"),
    ]


def test_idle_closes_window_at_last_input_and_records_away():
    clock, store, c = make([(0, "Code", "a.py — tidepool")], away=[(60, 60 + 600)])
    run(c, clock, 60 + 600 + 60)
    rows = windows(store)
    assert rows[0] == ("window", "Code", "a.py — tidepool", 0, 60)
    assert rows[1][:2] == ("away", None) and rows[1][3] == 60
    assert rows[1][4] == pytest.approx(60 + 600, abs=10)
    assert rows[2][:2] == ("window", "Code") and rows[2][3] == pytest.approx(660, abs=10)
    assert AWAY_AFTER == 180


def test_gap_starts_new_row():
    clock, store, c = make([(0, "Code", "x")])
    run(c, clock, 30)
    clock.advance(600)
    run(c, clock, 20)
    assert len(windows(store)) == 2


def test_pause_stops_recording_until_resume():
    clock, store, c = make([(0, "Code", "x"), (100, "Ghostty", "~")])
    run(c, clock, 30)
    pause(store, clock.now(), None)
    assert store.get("paused_until") == UNTIL_RESUME
    run(c, clock, 200)
    resume(store)
    run(c, clock, 30)
    rows = windows(store)
    assert [(r[1], r[3]) for r in rows] == [("Code", 0), ("Ghostty", 230)]


def test_timed_pause_expires():
    clock, store, c = make([(0, "Code", "x")])
    pause(store, clock.now(), 0.5)
    run(c, clock, 60)
    assert windows(store)[0][3] == 30


def test_forget_drops_current_event_and_collection_continues():
    clock, store, c = make([(0, "Code", "x")])
    run(c, clock, 7200)
    forget(store, clock.now(), 60)
    run(c, clock, 30)
    rows = windows(store)
    assert rows[0][3:] == (0, 3600)
    assert rows[-1][3] >= 7200 and len(rows) == 2
    assert store.note("where").source == "fallback"


def test_scans_only_with_roots_every_five_minutes(tmp_path):
    git = ScriptedScanner([Event("git", T0 + 1, T0 + 1, repo="tidepool", detail={"dirty": 1})])
    clock, store, c = make([(0, "Code", "x")], scanners=(git,))
    run(c, clock, 700)
    assert git.calls == 0

    config = Config(allowed_roots=[str(tmp_path)])
    clock, store, c = make([(0, "Code", "x")], config=config, scanners=(git,))
    run(c, clock, 700)
    assert git.calls == 3
    assert store.repos() == ["tidepool"]


def test_broken_scanner_does_not_stop_collection(tmp_path):
    class Broken:
        def scan(self, roots, since, now):
            raise OSError("nope")

    config = Config(allowed_roots=[str(tmp_path)])
    clock, store, c = make([(0, "Code", "x")], config=config, scanners=(Broken(),))
    run(c, clock, 30)
    assert len(windows(store)) == 1


def test_window_dataclass():
    assert Window("Code").title is None
