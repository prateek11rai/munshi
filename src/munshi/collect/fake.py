from pathlib import Path

from munshi.collect.loop import Window
from munshi.store import Event
from munshi.timefmt import Clock


class ScriptedWindows:
    """A window source that plays back a script against a clock."""

    def __init__(
        self,
        clock: Clock,
        steps: list[tuple],
        away: list[tuple[float, float]] | None = None,
        pid: int = 4242,
    ) -> None:
        """Create the source.

        Args:
            clock: The clock the script is read against.
            steps: (time, app, title), optionally followed by pid and bundle id; each
                holds until the next. app None means no window.
            away: (start, end) stretches with no input.
            pid: Process id reported for windows whose step names none.
        """
        self.clock = clock
        self.steps = sorted(steps, key=lambda step: step[0])
        self.away = away or []
        self.pid = pid

    def front_window(self) -> Window | None:
        """Return the scripted window for the current time.

        Returns:
            The window, or None.
        """
        now = self.clock.now()
        current = None
        for step in self.steps:
            if step[0] <= now:
                current = step
        if current is None or current[1] is None:
            return None
        pid = current[3] if len(current) > 3 else self.pid
        bundle = current[4] if len(current) > 4 else None
        return Window(app=current[1], title=current[2], pid=pid, bundle=bundle)

    def idle_seconds(self) -> float:
        """Return scripted idle time.

        Returns:
            Seconds since the start of the current away stretch, else 0.
        """
        now = self.clock.now()
        for start, end in self.away:
            if start <= now < end:
                return now - start
        return 0.0


class ScriptedScanner:
    """A git or file scanner that returns prepared events once their time has come."""

    def __init__(self, events: list[Event]) -> None:
        """Create the scanner.

        Args:
            events: Events to hand out; each is returned by the first scan at or after its start.
        """
        self.pending = sorted(events, key=lambda event: event.start)
        self.calls = 0

    def scan(self, roots: list[Path], since: float, now: float) -> list[Event]:
        """Return the prepared events that are due.

        Args:
            roots: Ignored.
            since: Ignored.
            now: Current time, epoch seconds.

        Returns:
            Due events.
        """
        self.calls += 1
        due = [event for event in self.pending if event.start <= now]
        self.pending = [event for event in self.pending if event.start > now]
        return due
