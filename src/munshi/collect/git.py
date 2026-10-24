import logging
import os
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from munshi.redact import redact
from munshi.store import Event

log = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess]
GIT_ENV = {"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
MAX_COMMITS = 20
MAX_FILES = 50


def find_repos(roots: list[Path], depth: int = 2) -> list[Path]:
    """Find git repos directly under the roots, at most `depth` folders down.

    Args:
        roots: Allowed root folders.
        depth: How many folder levels below a root to look.

    Returns:
        Repo folders, sorted, without duplicates.
    """
    found: set[Path] = set()

    def walk(folder: Path, level: int) -> None:
        if (folder / ".git").exists():
            found.add(folder)
            return
        if level >= depth:
            return
        try:
            children = sorted(p for p in folder.iterdir() if p.is_dir())
        except OSError:
            return
        for child in children:
            if not child.name.startswith("."):
                walk(child, level + 1)

    for root in roots:
        if root.is_dir():
            walk(root, 0)
    return sorted(found)


class GitScanner:
    """Reads branch, new commits and uncommitted file names from repos under the roots."""

    def __init__(self, run: Runner = subprocess.run, git: str | None = None) -> None:
        """Create the scanner.

        Args:
            run: subprocess.run or a stand-in for tests.
            git: Path of the git binary; found on PATH when None.
        """
        self.run = run
        self.git = git or shutil.which("git") or "/usr/bin/git"
        self.last: dict[str, dict[str, Any]] = {}

    def _git(self, repo: Path, *args: str) -> str:
        result = self.run(
            [self.git, "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, **GIT_ENV},
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"git {args[0]} failed")
        return result.stdout

    def snapshot(self, repo: Path, since: float) -> dict[str, Any]:
        """Read one repo's state.

        Args:
            repo: The repo folder.
            since: Only commits after this time, epoch seconds.

        Returns:
            A dict with branch, commits [{hash, subject}], dirty count and file names.
        """
        branch = self._git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip()
        stamp = datetime.fromtimestamp(since, UTC).strftime("%Y-%m-%d %H:%M:%S +0000")
        log_out = self._git(
            repo, "log", f"--since={stamp}", f"-n{MAX_COMMITS}", "--format=%h%x1f%ct%x1f%s"
        )
        commits = []
        for line in log_out.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 3 and parts[1].isdigit() and int(parts[1]) > since:
                commits.append({"hash": parts[0], "subject": redact(parts[2])})
        status = self._git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=normal")
        names = parse_status(status)
        return {
            "branch": redact(branch),
            "commits": commits,
            "dirty": len(names),
            "files": [redact(n) for n in names[:MAX_FILES]],
        }

    def scan(self, roots: list[Path], since: float, now: float) -> list[Event]:
        """Return a git event per repo whose state changed since the last scan.

        Args:
            roots: Allowed root folders.
            since: Time of the previous scan, epoch seconds.
            now: Current time, epoch seconds.

        Returns:
            Git events.
        """
        events = []
        for repo in find_repos(roots):
            try:
                snap = self.snapshot(repo, since)
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
                log.warning("git scan skipped a repo: %s", type(exc).__name__)
                continue
            key = str(repo)
            changed = snap["commits"] or {k: snap[k] for k in ("branch", "dirty", "files")} != {
                k: self.last.get(key, {}).get(k) for k in ("branch", "dirty", "files")
            }
            self.last[key] = snap
            if changed:
                events.append(Event("git", now, now, repo=repo.name, detail=snap))
        return events


def parse_status(out: str) -> list[str]:
    """Parse `git status --porcelain=v1 -z` into file base names.

    Args:
        out: The raw output.

    Returns:
        Base names of changed or untracked files, in order, without duplicates.
    """
    names: list[str] = []
    entries = out.split("\0")
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if "R" in code or "C" in code:
            i += 1  # the next entry is the old path of a rename or copy
        name = Path(path.rstrip("/")).name
        if name and name not in names:
            names.append(name)
    return names
