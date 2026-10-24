import subprocess
from pathlib import Path

from munshi.collect.files import FileScanner
from munshi.collect.git import GitScanner, find_repos, parse_status

NOW = 1_800_000_000.0


def make_tree(tmp_path):
    (tmp_path / "tidepool" / ".git").mkdir(parents=True)
    (tmp_path / "group" / "lantern" / ".git").mkdir(parents=True)
    (tmp_path / "a" / "b" / "deep" / ".git").mkdir(parents=True)
    (tmp_path / ".hidden" / "x" / ".git").mkdir(parents=True)
    (tmp_path / "notes").mkdir()
    return tmp_path


def test_find_repos_depth_two(tmp_path):
    root = make_tree(tmp_path)
    assert [p.name for p in find_repos([root])] == ["lantern", "tidepool"]
    assert find_repos([root / "missing"]) == []


def test_parse_status():
    out = " M src/cache.py\0?? notes/todo.md\0R  new.py\0old.py\0A  docs/\0 M src/cache.py\0"
    assert parse_status(out) == ["cache.py", "todo.md", "new.py", "docs"]
    assert parse_status("") == []


class FakeRun:
    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = []

    def __call__(self, cmd, **kwargs):
        assert isinstance(cmd, list) and "shell" not in kwargs
        assert kwargs["timeout"] and kwargs["check"] is False
        self.calls.append(cmd)
        repo, sub = Path(cmd[2]).name, cmd[3]
        out = self.outputs.get((repo, sub), "")
        code = 128 if out is None else 0
        return subprocess.CompletedProcess(cmd, code, out or "", "")


def git_outputs(dirty=" M src/cache.py\0?? b.txt\0"):
    return {
        ("tidepool", "rev-parse"): "main\n",
        ("tidepool", "log"): f"abc1234\x1f{int(NOW) - 60}\x1ffix: cache tide chart per station\n"
        f"old9999\x1f{int(NOW) - 9999}\x1fold commit\n",
        ("tidepool", "status"): dirty,
        ("lantern", "rev-parse"): None,
    }


def test_git_scan_reads_branch_commits_and_names_only(tmp_path):
    root = make_tree(tmp_path)
    run = FakeRun(git_outputs())
    scanner = GitScanner(run=run, git="/usr/bin/git")
    [event] = scanner.scan([root], since=NOW - 300, now=NOW)
    assert event.kind == "git" and event.repo == "tidepool"
    assert event.detail == {
        "branch": "main",
        "commits": [{"hash": "abc1234", "subject": "fix: cache tide chart per station"}],
        "dirty": 2,
        "files": ["cache.py", "b.txt"],
    }
    log_cmd = next(c for c in run.calls if c[3] == "log")
    assert log_cmd[:3] == ["/usr/bin/git", "-C", str(root / "tidepool")]
    assert not any("diff" in part or "show" in part for c in run.calls for part in c)


def test_git_scan_only_emits_changes(tmp_path):
    root = make_tree(tmp_path)
    outputs = git_outputs()
    outputs[("tidepool", "log")] = ""
    scanner = GitScanner(run=FakeRun(outputs), git="git")
    assert len(scanner.scan([root], NOW - 300, NOW)) == 1
    assert scanner.scan([root], NOW, NOW + 300) == []
    outputs[("tidepool", "status")] = " M src/cache.py\0"
    [event] = scanner.scan([root], NOW + 300, NOW + 600)
    assert event.detail["dirty"] == 1


def test_git_scan_redacts(tmp_path):
    root = make_tree(tmp_path)
    outputs = git_outputs()
    outputs[("tidepool", "log")] = f"abc\x1f{int(NOW)}\x1fping ana@example.org about 12345678\n"
    [event] = GitScanner(run=FakeRun(outputs), git="git").scan([root], NOW - 300, NOW)
    assert event.detail["commits"][0]["subject"] == "ping [email] about [number]"


def test_git_timeout_skips_repo(tmp_path):
    root = make_tree(tmp_path)

    def slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 10)

    assert GitScanner(run=slow, git="git").scan([root], NOW - 300, NOW) == []


def test_file_scan_names_only_outside_repos(tmp_path):
    root = make_tree(tmp_path)
    paths = [
        root / "notes" / "standup.md",
        root / "tidepool" / "src" / "cache.py",
        root / "notes" / ".obsidian" / "workspace.json",
        root / "tide-tables-2026.pdf",
        Path("/elsewhere/file.txt"),
    ]
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "\n".join(map(str, paths)) + "\n", "")

    events = FileScanner(run=run).scan([root], NOW - 300, NOW)
    assert [(e.title, e.detail["folder"]) for e in events] == [
        ("standup.md", "notes"),
        ("tide-tables-2026.pdf", root.name),
    ]
    assert calls[0][:3] == ["/usr/bin/mdfind", "-onlyin", str(root)]
    assert "$time.now(-300)" in calls[0][3]


def test_file_scan_failure_is_skipped(tmp_path):
    def run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "", "err")

    assert FileScanner(run=run).scan([tmp_path], NOW - 300, NOW) == []


def test_git_scan_after_a_restart_reports_only_real_changes(tmp_path):
    root = make_tree(tmp_path)
    first = GitScanner(run=FakeRun(git_outputs()), git="/usr/bin/git")
    [event] = first.scan([root], since=NOW - 300, now=NOW)
    stored = {"tidepool": {**event.detail, "commits": []}}
    quiet = {**git_outputs(), ("tidepool", "log"): ""}
    restarted = GitScanner(run=FakeRun(quiet), git="/usr/bin/git", previous=stored.get)
    assert restarted.scan([root], since=NOW, now=NOW + 300) == []
    moved = {**quiet, ("tidepool", "status"): " M src/cache.py\0"}
    again = GitScanner(run=FakeRun(moved), git="/usr/bin/git", previous=stored.get)
    [changed] = again.scan([root], since=NOW, now=NOW + 300)
    assert changed.detail["dirty"] == 1
    fresh = GitScanner(run=FakeRun(quiet), git="/usr/bin/git", previous=lambda name: None)
    assert len(fresh.scan([root], since=NOW, now=NOW + 300)) == 1
