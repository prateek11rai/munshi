import subprocess

from munshi.collect.fake import ScriptedWindows
from munshi.collect.loop import Collector
from munshi.collect.tmux import TmuxPane, bare_title, repo_name
from munshi.config import Config
from munshi.stats import counters
from munshi.store import Store
from munshi.timefmt import FakeClock, day_of
from munshi.write.slots import compact

T0 = 1_800_000_000.0


def layout(tmp_path):
    root = tmp_path / "code"
    for repo in ("tidepool", "acme-tools"):
        (root / repo / "src").mkdir(parents=True)
        (root / repo / ".git").mkdir()
    (root / "notes").mkdir()
    (tmp_path / "elsewhere").mkdir()
    return root.resolve()


def fake_tmux(path, command="claude", clients="10\tother\n20\tmlh\n", fail=False):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        assert kwargs.get("shell") is not True and kwargs["timeout"] == 1
        if fail:
            raise subprocess.TimeoutExpired(args, 1)
        if args[1] == "list-clients":
            return subprocess.CompletedProcess(args, 0, clients, "")
        assert args[1:5] == ["display-message", "-p", "-t", "=mlh:"]
        return subprocess.CompletedProcess(args, 0, f"{path}\t{command}\n", "")

    run.calls = calls
    return run


def test_bare_titles():
    assert bare_title("tmux") and bare_title(None) and bare_title(" ") and bare_title("tmux a")
    assert not bare_title("zsh") and not bare_title("~/code/tidepool — pytest")


def test_repo_name_only_inside_roots(tmp_path):
    root = layout(tmp_path)
    assert repo_name(root / "tidepool" / "src", [root]) == (True, "tidepool")
    assert repo_name(root / "notes", [root]) == (True, None)
    assert repo_name((tmp_path / "elsewhere").resolve(), [root]) == (False, None)


def test_context_names_command_and_repo_never_the_path(tmp_path):
    root = layout(tmp_path)
    run = fake_tmux(root / "tidepool" / "src")
    assert TmuxPane([root], run=run, tmux="/usr/bin/tmux").context() == "claude — tidepool"
    assert run.calls[0] == [
        "/usr/bin/tmux", "list-clients", "-F", "#{client_activity}\t#{session_name}"
    ]  # fmt: skip
    notes = TmuxPane([root], run=fake_tmux(root / "notes", "vim"), tmux="tmux")
    assert notes.context() == "vim"
    outside = TmuxPane([root], run=fake_tmux(tmp_path / "elsewhere"), tmux="tmux")
    assert outside.context() is None


def test_context_errors_give_nothing(tmp_path):
    root = layout(tmp_path)
    assert TmuxPane([root], run=fake_tmux(root, fail=True), tmux="tmux").context() is None
    assert TmuxPane([root], run=fake_tmux(root, clients=""), tmux="tmux").context() is None
    assert TmuxPane([], run=fake_tmux(root), tmux="tmux").context() is None
    assert TmuxPane([root], run=fake_tmux(root), tmux="").context() is None


def collect(tmp_path, steps, path, config=None):
    root = layout(tmp_path)
    config = config or Config(allowed_roots=[str(root)])
    clock = FakeClock(T0)
    store = Store(":memory:")
    source = ScriptedWindows(clock, [(T0 + s[0], *s[1:]) for s in steps])
    run = fake_tmux(root / path)
    tmux = TmuxPane([root], run=run, tmux="tmux")
    collector = Collector(store, config, source, clock, own_pid=1, tmux=tmux)
    for _ in range(6):
        collector.tick()
        clock.advance(10)
    return store, run


def test_terminal_titled_tmux_records_command_and_repo(tmp_path):
    store, run = collect(
        tmp_path,
        [(0, "WezTerm", "tmux"), (30, "Code", "tmux")],
        "tidepool/src",
    )
    events = store.events(0, 4e9)
    assert [(e.app, e.title) for e in events] == [
        ("WezTerm", "claude — tidepool"),
        ("Code", "tmux"),
    ]
    slot = compact(events, T0, T0 + 900, ["tidepool", "Other"])
    assert slot.items[0].project == "tidepool"
    assert len(run.calls) == 6
    assert counters(store, day_of(T0)) == {"recorded": 6, "tmux context": 3}


def test_terminal_with_a_real_title_is_left_alone(tmp_path):
    store, run = collect(tmp_path, [(0, "WezTerm", "~/code/tidepool — pytest")], "tidepool")
    assert [e.title for e in store.events(0, 4e9)] == ["~/code/tidepool — pytest"]
    assert run.calls == []


def test_repo_with_a_title_word_keeps_the_window_out(tmp_path):
    config = Config(allowed_roots=[str(tmp_path / "code")], ignore_title_words=["acme"])
    store, _ = collect(tmp_path, [(0, "WezTerm", "tmux")], "acme-tools/src", config)
    assert store.events(0, 4e9) == []
    assert counters(store, day_of(T0)) == {"title word": 6, "tmux context": 6}
