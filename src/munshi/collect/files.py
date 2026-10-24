import logging
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from munshi.collect.git import find_repos
from munshi.redact import redact
from munshi.store import Event

log = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess]
MAX_FILES = 20
QUERY = "kMDItemFSContentChangeDate >= $time.now(-300) && kMDItemContentType != public.folder"


class FileScanner:
    """Finds files changed in the last five minutes under the roots, outside git repos."""

    def __init__(self, run: Runner = subprocess.run, mdfind: str = "/usr/bin/mdfind") -> None:
        """Create the scanner.

        Args:
            run: subprocess.run or a stand-in for tests.
            mdfind: Path of Spotlight's command line tool.
        """
        self.run = run
        self.mdfind = mdfind

    def changed(self, root: Path) -> list[Path]:
        """Ask Spotlight for recently changed files under one root.

        Args:
            root: An allowed root folder.

        Returns:
            Paths reported by Spotlight.
        """
        result = self.run(
            [self.mdfind, "-onlyin", str(root), QUERY],
            capture_output=True,
            text=True,
            timeout=10,
            env={**os.environ, "LC_ALL": "C"},
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("mdfind failed")
        return [Path(line) for line in result.stdout.splitlines() if line.strip()]

    def scan(self, roots: list[Path], since: float, now: float) -> list[Event]:
        """Return one file event per changed file (names only).

        Args:
            roots: Allowed root folders.
            since: Unused; Spotlight already limits to the last five minutes.
            now: Current time, epoch seconds.

        Returns:
            File events, at most MAX_FILES.
        """
        repos = find_repos(roots)
        events: list[Event] = []
        for root in roots:
            try:
                paths = self.changed(root)
            except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
                log.warning("file scan skipped a root: %s", type(exc).__name__)
                continue
            for path in paths:
                if len(events) >= MAX_FILES:
                    return events
                if not path.is_relative_to(root) or any(path.is_relative_to(r) for r in repos):
                    continue
                parts = path.relative_to(root).parts
                if not parts or any(part.startswith(".") for part in parts):
                    continue
                folder = parts[0] if len(parts) > 1 else root.name
                events.append(
                    Event(
                        "file", now, now, title=redact(path.name), detail={"folder": redact(folder)}
                    )
                )
        return events
