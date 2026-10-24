import subprocess

import pytest

from munshi.collect.fake import ScriptedScanner, ScriptedWindows
from munshi.collect.loop import AWAY_AFTER, Collector, Window, scrub
from munshi.collect.procs import ProcessWords, is_firefox
from munshi.config import Config
from munshi.control import UNTIL_RESUME, forget, pause, resume
from munshi.stats import counters
from munshi.store import Event, Store
from munshi.timefmt import FakeClock, day_of

T0 = 1_800_000_000.0


def run(collector, clock, seconds, step=10):
    for _ in range(int(seconds // step)):
        collector.tick()
        clock.advance(step)


def make(steps, away=None, config=None, scanners=(), own_pid=1, procs=None):
    clock = FakeClock(T0)
    store = Store(":memory:")
    source = ScriptedWindows(
        clock,
        [(T0 + step[0], *step[1:]) for step in steps],
        [(T0 + a, T0 + b) for a, b in (away or [])],
    )
    collector = Collector(
        store, config or Config(), source, clock, scanners, own_pid=own_pid, procs=procs
    )
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


def polls(store):
    return counters(store, day_of(T0))


def test_title_word_window_is_not_recorded_at_all():
    config = Config(ignore_title_words=["ACME"])
    clock, store, c = make(
        [
            (0, "Code", "a.py — tidepool"),
            (30, "Google Chrome", "Quarterly plan - Acme Wiki"),
            (60, "Google Chrome", "SQLite WAL mode"),
        ],
        config=config,
    )
    run(c, clock, 90)
    assert windows(store) == [
        ("window", "Code", "a.py — tidepool", 0, 30),
        ("window", "Google Chrome", "SQLite WAL mode", 60, 80),
    ]
    assert polls(store) == {"recorded": 6, "title word": 3}


def test_title_word_checked_before_redaction_and_on_app_name():
    config = Config(ignore_title_words=["acme"])
    clock, store, c = make(
        [(0, "Google Chrome", "https://wiki.example.com/acme/page"), (30, "Acme Chat", None)],
        config=config,
    )
    run(c, clock, 60)
    assert windows(store) == []
    assert polls(store) == {"title word": 6}


def fake_ps(commands, open_files=None):
    """Fake `ps` (command lines by pid) and `lsof` (open file paths by pid)."""
    calls = []
    open_files = open_files or {}

    def run(args, **kwargs):
        calls.append(args)
        assert kwargs.get("shell") is not True
        pid = int(args[args.index("-p") + 1])
        if args[0] == "/usr/sbin/lsof":
            assert args == ["/usr/sbin/lsof", "-w", "-a", "-p", str(pid), "-Fn"]
            files = open_files.get(pid)
            if isinstance(files, Exception):
                raise files
            out = "".join(f"p{pid}\nf{n}\nn{path}\n" for n, path in enumerate(files or []))
            return subprocess.CompletedProcess(args, 0 if files else 1, out, "")
        assert args[:3] == ["/bin/ps", "-o", "command="]
        command = commands.get(pid)
        if isinstance(command, Exception):
            raise command
        if command is None:
            return subprocess.CompletedProcess(args, 1, "", "")
        return subprocess.CompletedProcess(args, 0, command + "\n", "")

    run.calls = calls
    return run


FIREFOX = "/Applications/Firefox.app/Contents/MacOS/firefox"


def test_process_word_skips_the_work_browser_profile():
    ps = fake_ps(
        {
            11: f"{FIREFOX} -profile /Users/me/Library/Firefox/Profiles/x1.Acme-work",
            12: f"{FIREFOX} -profile /Users/me/Library/Firefox/Profiles/y2.home",
        },
        {12: ["/Users/me/Library/Firefox/Profiles/y2.home/.parentlock"]},
    )
    config = Config(ignore_process_words=["acme"])
    clock, store, c = make(
        [
            (0, "Firefox", "Team board", 11),
            (30, "Firefox", "SQLite WAL mode", 12),
            (60, "Firefox", "Team board", 11),
        ],
        config=config,
        procs=ProcessWords(config.ignore_process_words, run=ps),
    )
    run(c, clock, 90)
    assert windows(store) == [("window", "Firefox", "SQLite WAL mode", 30, 60)]
    assert polls(store) == {"process word": 6, "recorded": 3}
    assert [(call[0], call[-1]) for call in ps.calls] == [
        ("/bin/ps", "11"),
        ("/bin/ps", "12"),
        ("/usr/sbin/lsof", "-Fn"),
    ]


PROFILES = "/Users/me/Library/Application Support/Firefox/Profiles"


def test_firefox_profile_folder_name_blocks_the_work_profile():
    ps = fake_ps(
        {21: FIREFOX, 22: FIREFOX},
        {
            21: [f"{PROFILES}/k3x9.Acme-2/.parentlock", f"{PROFILES}/k3x9.Acme-2/places.sqlite"],
            22: [f"{PROFILES}/h7q2.default-release/.parentlock", "/usr/lib/libc.dylib"],
        },
    )
    config = Config(ignore_process_words=["acme"])
    clock, store, c = make(
        [
            (0, "Firefox", "Team board", 21, "org.mozilla.firefox"),
            (30, "Firefox", "SQLite WAL mode", 22, "org.mozilla.firefox"),
            (60, "Firefox", "Team board", 21, "org.mozilla.firefox"),
        ],
        config=config,
        procs=ProcessWords(config.ignore_process_words, run=ps),
    )
    run(c, clock, 90)
    assert windows(store) == [("window", "Firefox", "SQLite WAL mode", 30, 60)]
    assert polls(store) == {"process word": 6, "recorded": 3}
    assert len(ps.calls) == 4


def test_firefox_profile_check_failures_are_no_match_and_not_cached():
    words = ["acme"]
    failing = fake_ps({21: FIREFOX}, {21: OSError("no lsof")})
    procs = ProcessWords(words, run=failing)
    assert not procs.matches(21, "Firefox", "org.mozilla.firefox") and procs.cache == {}
    empty = ProcessWords(words, run=fake_ps({21: FIREFOX}, {21: ["/usr/lib/libc.dylib"]}))
    assert not empty.matches(21, "Firefox", "org.mozilla.firefox") and empty.cache == {}
    other = fake_ps({31: "/Applications/Code.app/Contents/MacOS/Electron"})
    assert not ProcessWords(words, run=other).matches(31, "Code", "com.microsoft.VSCode")
    assert [call[0] for call in other.calls] == ["/bin/ps"]
    assert is_firefox("Firefox Nightly", None) and not is_firefox("Firefox", "com.example.app")


def test_process_word_failure_records_and_retries():
    ps = fake_ps({11: OSError("no ps")})
    config = Config(ignore_process_words=["acme"])
    words = ProcessWords(config.ignore_process_words, run=ps)
    clock, store, c = make([(0, "Firefox", "SQLite WAL mode", 11)], config=config, procs=words)
    run(c, clock, 30)
    assert [w[1] for w in windows(store)] == ["Firefox"]
    assert len(ps.calls) == 3 and words.cache == {}
    assert not ProcessWords(["acme"], run=fake_ps({})).matches(99, "Firefox")


def test_process_words_off_never_runs_ps():
    ps = fake_ps({})
    clock, store, c = make([(0, "Firefox", "x", 11)], procs=ProcessWords([], run=ps))
    run(c, clock, 30)
    assert ps.calls == [] and len(windows(store)) == 1


def test_skip_counters_by_reason():
    clock, store, c = make(
        [
            (0, "1Password", "Vault"),
            (20, "Python", "Munshi", 1),
            (40, None, None),
            (60, "Safari", "Private Browsing"),
            (80, "Code", "x"),
        ],
        away=[(100, 400)],
    )
    run(c, clock, 100)
    pause(store, clock.now(), None)
    run(c, clock, 20)
    assert polls(store) == {
        "ignored app": 2,
        "own window": 2,
        "no window": 2,
        "private": 2,
        "recorded": 2,
        "paused": 2,
    }
    resume(store)
    run(c, clock, 300)
    assert polls(store)["away"] > 0


def test_git_and_file_names_with_title_words_are_dropped(tmp_path):
    events = [
        Event(
            "git",
            T0,
            T0,
            repo="tidepool",
            detail={
                "branch": "main",
                "commits": [
                    {"hash": "a", "subject": "fix acme export"},
                    {"hash": "b", "subject": "fix: cache tide chart"},
                ],
                "dirty": 2,
                "files": ["acme_notes.md", "cache.py"],
            },
        ),
        Event("git", T0, T0, repo="acme-tools", detail={"branch": "main"}),
        Event("file", T0, T0, title="plan.md", detail={"folder": "Acme"}),
        Event("file", T0, T0, title="tides.csv", detail={"folder": "notes"}),
    ]
    config = Config(allowed_roots=[str(tmp_path)], ignore_title_words=["acme"])
    clock, store, c = make([(0, "Code", "x")], config=config, scanners=(ScriptedScanner(events),))
    run(c, clock, 20)
    kept = store.events(0, 4e9, ("git", "file"))
    assert [(e.kind, e.repo, e.title) for e in kept] == [
        ("git", "tidepool", None),
        ("file", None, "tides.csv"),
    ]
    assert kept[0].detail["commits"] == [{"hash": "b", "subject": "fix: cache tide chart"}]
    assert kept[0].detail["files"] == ["cache.py"] and kept[0].detail["dirty"] == 2
    assert scrub(Event("git", 0, 0, repo="x"), []) is not None
