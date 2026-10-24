import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from munshi.config import Config
from munshi.control import is_paused
from munshi.redact import redact
from munshi.store import Event, Store
from munshi.timefmt import Clock

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
    ) -> None:
        """Create the collector.

        Args:
            store: Where events go.
            config: App rules and allowed roots.
            windows: Front window and idle source.
            clock: Time source.
            scanners: Git and file scanners, run every five minutes.
            own_pid: This process; its windows are never recorded.
        """
        self.store = store
        self.config = config
        self.windows = windows
        self.clock = clock
        self.scanners = scanners
        self.own_pid = os.getpid() if own_pid is None else own_pid
        self.current: Event | None = None
        self.next_scan = 0.0

    def tick(self) -> None:
        """Poll once: extend or start an event, and scan when a scan is due."""
        now = self.clock.now()
        if is_paused(self.store, now):
            self.current = None
            self.store.set("last_scan", now)
            return
        if self.current and now - self.current.end > EXTEND_GAP + POLL_SECONDS:
            self.current = None
        idle = self.windows.idle_seconds()
        if idle >= AWAY_AFTER:
            self._away(now, now - idle)
        else:
            self._window(now, idle)
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

    def _window(self, now: float, idle: float) -> None:
        win = self.windows.front_window()
        if win is None or win.pid == self.own_pid or not self.config.apps.records(win.app):
            if self.current:
                self._extend(now)
            self.current = None
            return
        title = None if is_private(win.title) else redact(win.title)
        current = self.current
        if (
            current
            and current.kind == "window"
            and (current.app, current.title) == (win.app, title)
            and now - current.end <= EXTEND_GAP
            and self._extend(now)
        ):
            return
        start = now
        if current and current.kind == "away":
            start = max(current.start, now - idle)
            self._extend(start)
        elif current:
            self._extend(now)
        self.current = Event("window", start, now, app=win.app, title=title)
        self.store.add_event(self.current)

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
                    self.store.add_event(event)
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
