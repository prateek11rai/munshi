import time
from datetime import date, datetime, timedelta
from typing import Protocol

SLOT_SECONDS = 15 * 60


class Clock(Protocol):
    """Anything that tells the time in epoch seconds."""

    def now(self) -> float:
        """Return the current time.

        Returns:
            Epoch seconds.
        """
        ...


class SystemClock:
    """The real clock, optionally shifted by a fixed offset (used by the demo)."""

    def __init__(self, offset: float = 0.0) -> None:
        """Create the clock.

        Args:
            offset: Seconds added to the system time.
        """
        self.offset = offset

    def now(self) -> float:
        """Return the current time.

        Returns:
            Epoch seconds plus the offset.
        """
        return time.time() + self.offset


class FakeClock:
    """A clock that only moves when told to; for tests and scripted runs."""

    def __init__(self, start: float) -> None:
        """Create the clock.

        Args:
            start: The first time it reports, in epoch seconds.
        """
        self.t = start

    def now(self) -> float:
        """Return the current fake time.

        Returns:
            Epoch seconds.
        """
        return self.t

    def advance(self, seconds: float) -> None:
        """Move the clock forward.

        Args:
            seconds: How far to move.
        """
        self.t += seconds


def local(ts: float) -> datetime:
    """Convert epoch seconds to a naive local datetime.

    Args:
        ts: Epoch seconds.

    Returns:
        The local wall time.
    """
    return datetime.fromtimestamp(ts)


def day_of(ts: float) -> date:
    """Return the local calendar day of a timestamp.

    Args:
        ts: Epoch seconds.

    Returns:
        The local date.
    """
    return local(ts).date()


def day_bounds(day: date) -> tuple[float, float]:
    """Return local midnight to midnight for a day.

    Args:
        day: The calendar day.

    Returns:
        (start, end) in epoch seconds.
    """
    start = datetime.combine(day, datetime.min.time())
    return start.timestamp(), (start + timedelta(days=1)).timestamp()


def at(day: date, hhmm: str) -> float:
    """Return the epoch seconds of a local wall time on a day.

    Args:
        day: The calendar day.
        hhmm: Time as "HH:MM".

    Returns:
        Epoch seconds.
    """
    hours, minutes = (int(part) for part in hhmm.split(":"))
    return (
        datetime.combine(day, datetime.min.time()).replace(hour=hours, minute=minutes).timestamp()
    )


def slot_start(ts: float) -> float:
    """Return the start of the local 15-minute slot holding a timestamp.

    Args:
        ts: Epoch seconds.

    Returns:
        Epoch seconds of the slot start.
    """
    wall = local(ts)
    return wall.replace(minute=wall.minute - wall.minute % 15, second=0, microsecond=0).timestamp()


def hm(ts: float) -> str:
    """Format a timestamp as local "HH:MM".

    Args:
        ts: Epoch seconds.

    Returns:
        The formatted time.
    """
    return local(ts).strftime("%H:%M")


def duration(seconds: float) -> str:
    """Format a duration like "6 h 45 min", "45 min" or "3 h".

    Args:
        seconds: The duration.

    Returns:
        The formatted text, rounded to whole minutes.
    """
    minutes = int(round(seconds / 60))
    hours, minutes = divmod(minutes, 60)
    if hours and minutes:
        return f"{hours} h {minutes} min"
    if hours:
        return f"{hours} h"
    return f"{minutes} min"


def quarter_hours(seconds: float) -> float:
    """Round a duration to the nearest 0.25 h.

    Args:
        seconds: The duration.

    Returns:
        Hours rounded to a quarter.
    """
    return round(seconds / 900) / 4


def hours_text(hours: float) -> str:
    """Format quarter hours without trailing zeros ("2", "2.5", "1.75").

    Args:
        hours: Hours, already rounded.

    Returns:
        The formatted number.
    """
    return f"{hours:g}"


def ago(seconds: float) -> str:
    """Format how long ago something happened ("just now", "6 min ago", "2 h ago").

    Args:
        seconds: Seconds since it happened.

    Returns:
        The formatted text.
    """
    minutes = int(seconds // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    return f"{minutes // 60} h ago"


def long_day(day: date) -> str:
    """Format a day like "Saturday 24 October 2026".

    Args:
        day: The calendar day.

    Returns:
        The formatted text.
    """
    return f"{day.strftime('%A')} {day.day} {day.strftime('%B %Y')}"
