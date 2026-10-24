import os
import subprocess
import threading

from helpers import DAY, FakeModel, git, window

from munshi import stats
from munshi.collect.procs import ps_field, usage
from munshi.config import Config
from munshi.store import Store
from munshi.timefmt import FakeClock, at
from munshi.write.writer import Writer

SECRET_TEXT = ("cache.py", "tidepool", "SQLite", "lantern", "Code", "Chrome", "station")


def filled_store():
    store = Store(":memory:")
    store.set("known_repos", ["tidepool", "lantern"])
    window(store, "14:00", "14:09", "Code", "cache.py — tidepool")
    window(store, "14:09", "14:14", "Google Chrome", "SQLite WAL mode")
    window(store, "14:15", "14:29", "Code", "nav.md — lantern")
    git(store, "14:05", "tidepool", commits=["fix: cache tide chart per station"], dirty=2)
    store.bump(DAY.isoformat(), "recorded", 40)
    store.bump(DAY.isoformat(), "title word", 3)
    store.bump(DAY.isoformat(), "process word", 5)
    reply = {
        "blocks": [
            {
                "evidence": ["e1"],
                "project": "tidepool",
                "topic": "tide-chart caching",
                "summary": "Cached the tide chart per station",
            },
            {"evidence": ["e9"], "project": "Other", "topic": "x", "summary": "SQLite"},
        ]
    }
    model = FakeModel(reply, {"blocks": []})
    clock = FakeClock(at(DAY, "14:31"))
    Writer(store, Config(), clock, model).run()
    return store, clock


def test_report_has_numbers_and_no_recorded_text(monkeypatch):
    store, clock = filled_store()
    monkeypatch.setattr(stats, "usage", lambda pid: (64.2, 0.3))
    stats.record_status(store, clock.now() - 120, os.getpid(), True)
    lines = stats.report(store, DAY, clock.now())
    text = "\n".join(lines)
    assert lines[0] == f"stats for {DAY.isoformat()} (numbers only)"
    assert "events: window 3 (28 min) · away 0 (0 min) · git 1 · file 0" in text
    assert "polls: recorded 40 · title word 3 · process word 5" in text
    assert (
        "slots written 2 · blocks accepted 1 · rejected 1 · fallback 2 · fallback rate 67%" in text
    )
    assert "  unknown evidence id × 1" in text
    assert "seconds per slot: mean" in text and "(2 model calls)" in text
    assert "last writer run: just now, 2 slots in" in text
    assert "app: running · checked 2 min ago · Accessibility granted · RSS 64 MB · CPU 0.3%" in text
    assert not any(word in text for word in SECRET_TEXT)


def test_report_on_an_empty_day():
    store = Store(":memory:")
    text = "\n".join(stats.report(store, DAY, at(DAY, "09:00")))
    assert "polls: none" in text and "last writer run: none yet" in text
    assert "app: no status stored yet" in text


def test_app_line_when_the_app_is_gone(monkeypatch):
    store = Store(":memory:")
    monkeypatch.setattr(stats, "usage", lambda pid: None)
    stats.record_status(store, 0, 999_999_999, False)
    line = stats.app_line(store, 60)
    assert line == "app: not running · checked 1 min ago · Accessibility not granted"


def test_status_loop_stores_at_launch_then_stops(tmp_path, monkeypatch):
    monkeypatch.setattr(stats, "usage", lambda pid: (50.0, 1.5))
    stop = threading.Event()
    stop.set()
    stats.status_loop(tmp_path, stop, lambda: 1000.0, lambda: True)
    store = Store.at_home(tmp_path)
    status = store.get("app_status")
    assert status == {
        "pid": os.getpid(),
        "at": 1000.0,
        "accessibility": True,
        "rss_mb": 50.0,
        "cpu": 1.5,
    }


def test_usage_parses_ps_and_survives_failures():
    def ok(args, **kwargs):
        assert args == ["/bin/ps", "-o", "rss,%cpu=", "-p", "42"]
        return subprocess.CompletedProcess(args, 0, " 65536  2,5\n", "")

    def broken(args, **kwargs):
        raise subprocess.TimeoutExpired(args, 2)

    assert usage(42, ok) == (64.0, 2.5)
    assert usage(42, broken) is None
    assert ps_field(42, "command", lambda a, **k: subprocess.CompletedProcess(a, 1, "", "")) is None
