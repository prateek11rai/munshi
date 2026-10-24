import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from munshi.collect.procs import ProcessWords
from munshi.config import Config, contains_word
from munshi.control import is_paused
from munshi.redact import redact
from munshi.store import Event, Store
from munshi.timefmt import Clock, day_of

log = logging.getLogger(__name__)

POLL_SECONDS = 10
SCAN_SECONDS = 5 * 60
EXTEND_GAP = 15
AWAY_AFTER = 3 * 60
PRIVATE_MARKERS = ("private browsing", "incognito", "inprivate")


@dataclass
class Window:
    """The front app and, when known, its focused window's title."""

    app: str
    title: str | None = None
    pid: int | None = None


class WindowSource(Protocol):
    """Where the collector reads the front window and idle time from."""

    def front_window(self) -> Window | None:
        """Return the front app and window title.

        Returns:
            The window, or None when nothing is in front.
        """
        ...

    def idle_seconds(self) -> float:
        """Return seconds since the last keyboard or mouse input.

        Returns:
            Idle seconds.
        """
        ...


class Scanner(Protocol):
    """Scans allowed roots for git state or changed files."""

    def scan(self, roots: list[Path], since: float, now: float) -> list[Event]:
        """Return new events found under the roots.

        Args:
            roots: Allowed root folders.
            since: Time of the previous scan, epoch seconds.
            now: Current time, epoch seconds.

        Returns:
            Events to store.
        """
        ...


def scrub(event: Event, words: list[str]) -> Event | None:
    """Drop the parts of a git or file event that contain a blocked title word.

    Args:
        event: A git or file event.
        words: Lower-cased blocked words.

    Returns:
        The event without those parts, or None when the event itself is blocked.
    """
    if not words:
        return event
    if contains_word(event.repo, words) or contains_word(event.title, words):
        return None
    detail = dict(event.detail)
    if contains_word(detail.get("folder"), words) or contains_word(detail.get("branch"), words):
        return None
    if "commits" in detail:
        detail["commits"] = [
            c for c in detail["commits"] if not contains_word(c.get("subject"), words)
        ]
    if "files" in detail:
        detail["files"] = [name for name in detail["files"] if not contains_word(name, words)]
    event.detail = detail
    return event


def is_private(title: str | None) -> bool:
    """Tell whether a window title belongs to a private browsing window.

    Args:
        title: The window title.

    Returns:
        True for private, incognito or InPrivate windows.
    """
    lowered = (title or "").lower()
    return any(marker in lowered for marker in PRIVATE_MARKERS)


class Collector:
    """Polls the front window and idle time, and scans git and files, into the store."""

    def __init__(
        self,
        store: Store,
        config: Config,
        windows: WindowSource,
        clock: Clock,
        scanners: tuple[Scanner, ...] = (),
        own_pid: int | None = None,
        procs: ProcessWords | None = None,
    ) -> None:
        """Create the collector.

        Args:
            store: Where events go.
            config: App rules, blocked words and allowed roots.
            windows: Front window and idle source.
            clock: Time source.
            scanners: Git and file scanners, run every five minutes.
            own_pid: This process; its windows are never recorded.
            procs: Command-line word check; built from the config when None.
        """
        self.store = store
        self.config = config
        self.windows = windows
        self.clock = clock
        self.scanners = scanners
        self.own_pid = os.getpid() if own_pid is None else own_pid
        self.procs = procs or ProcessWords(config.ignore_process_words)
        self.current: Event | None = None
        self.next_scan = 0.0

    def count(self, now: float, name: str) -> None:
        """Add one poll to a per-day counter (numbers only, for `munshi stats`).

        Args:
            now: Current time, epoch seconds.
            name: E.g. "recorded", "ignored app", "title word".
        """
        self.store.bump(day_of(now).isoformat(), name)

    def skip_reason(self, win: Window | None) -> str | None:
        """Tell why a front window must not be recorded.

        Title and app words are checked on the raw title, before redaction.

        Args:
            win: The front window, or None.

        Returns:
            The reason, or None when the window may be recorded.
        """
        if win is None:
            return "no window"
        if win.pid == self.own_pid:
            return "own window"
        if not self.config.apps.records(win.app):
            return "ignored app"
        words = self.config.ignore_title_words
        if contains_word(win.title, words) or contains_word(win.app, words):
            return "title word"
        if self.procs.matches(win.pid, win.app):
            return "process word"
        return None

    def tick(self) -> None:
        """Poll once: extend or start an event, and scan when a scan is due."""
        now = self.clock.now()
        if is_paused(self.store, now):
            self.current = None
            self.store.set("last_scan", now)
            self.count(now, "paused")
            return
        if self.current and now - self.current.end > EXTEND_GAP + POLL_SECONDS:
            self.current = None
        idle = self.windows.idle_seconds()
        if idle >= AWAY_AFTER:
            self._away(now, now - idle)
            self.count(now, "away")
        else:
            self.count(now, self._window(now, idle))
        if now >= self.next_scan:
            self.scan(now)

    def _away(self, now: float, last_input: float) -> None:
        current = self.current
        start = last_input
        if current and current.kind == "away":
            if self._extend(now):
                return
            current, start = None, now
        if current:
            start = max(current.start, min(current.end, last_input))
            self._extend(start)
        self.current = Event("away", start, now)
        self.store.add_event(self.current)

    def _window(self, now: float, idle: float) -> str:
        win = self.windows.front_window()
        reason = self.skip_reason(win)
        if reason or win is None:
            if self.current:
                self._extend(now)
            self.current = None
            return reason or "no window"
        private = is_private(win.title)
        title = None if private else redact(win.title)
        outcome = "private" if private else "recorded"
        current = self.current
        if (
            current
            and current.kind == "window"
            and (current.app, current.title) == (win.app, title)
            and now - current.end <= EXTEND_GAP
            and self._extend(now)
        ):
            return outcome
        start = now
        if current and current.kind == "away":
            start = max(current.start, now - idle)
            self._extend(start)
        elif current:
            self._extend(now)
        self.current = Event("window", start, now, app=win.app, title=title)
        self.store.add_event(self.current)
        return outcome

    def _extend(self, end: float) -> bool:
        if not self.current or self.current.id is None:
            return False
        was, self.current.end = self.current.end, max(self.current.start, end)
        if self.store.extend_event(self.current.id, self.current.end, was):
            return True
        self.current = None
        return False

    def scan(self, now: float) -> None:
        """Run the git and file scanners if any roots are allowed.

        Args:
            now: Current time, epoch seconds.
        """
        self.next_scan = now + SCAN_SECONDS
        roots = self.config.roots()
        if not roots or not self.scanners:
            return
        since = self.store.get("last_scan", now - SCAN_SECONDS)
        for scanner in self.scanners:
            try:
                for event in scanner.scan(roots, since, now):
                    if kept := scrub(event, self.config.ignore_title_words):
                        self.store.add_event(kept)
            except Exception as exc:  # a broken repo must not stop the window log
                log.warning("scanner %s failed: %s", type(scanner).__name__, type(exc).__name__)
        self.store.set("last_scan", now)

    def run(self, stop: threading.Event, interval: float = POLL_SECONDS) -> None:
        """Poll until stopped.

        Args:
            stop: Set it to end the loop.
            interval: Seconds between polls.
        """
        while not stop.is_set():
            started = time.monotonic()
            try:
                self.tick()
            except Exception as exc:  # keep collecting after a bad poll
                log.warning("collector tick failed: %s", type(exc).__name__)
            stop.wait(max(0.0, interval - (time.monotonic() - started)))
