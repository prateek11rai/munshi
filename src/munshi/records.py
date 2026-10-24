import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Event:
    """One recorded fact: a window, an away stretch, a git snapshot or a changed file."""

    kind: str
    start: float
    end: float
    app: str | None = None
    title: str | None = None
    repo: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    id: int | None = None

    @property
    def seconds(self) -> float:
        """Length of the event.

        Returns:
            Seconds, never negative.
        """
        return max(0.0, self.end - self.start)


@dataclass
class Block:
    """A labelled stretch of work inside one 15-minute slot."""

    slot: float
    start: float
    end: float
    active: float
    project: str
    topic: str
    summary: str
    source: str
    evidence: list[int] = field(default_factory=list)
    id: int | None = None


@dataclass
class Note:
    """A written note: "where" (where was I) or "day" (a day's summary)."""

    kind: str
    day: str
    created: float
    span_start: float
    span_end: float
    text: str
    source: str
    cites: list[int] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    id: int | None = None


def event_from(row: sqlite3.Row) -> Event:
    """Build an event from a database row.

    Args:
        row: A row of `events`.

    Returns:
        The event.
    """
    return Event(
        kind=row["kind"],
        start=row["start"],
        end=row["end"],
        app=row["app"],
        title=row["title"],
        repo=row["repo"],
        detail=json.loads(row["detail"]),
        id=row["id"],
    )


def block_from(row: sqlite3.Row) -> Block:
    """Build a block from a database row.

    Args:
        row: A row of `blocks`.

    Returns:
        The block.
    """
    return Block(
        slot=row["slot"],
        start=row["start"],
        end=row["end"],
        active=row["active"],
        project=row["project"],
        topic=row["topic"],
        summary=row["summary"],
        source=row["source"],
        evidence=json.loads(row["evidence"]),
        id=row["id"],
    )


def note_from(row: sqlite3.Row) -> Note:
    """Build a note from a database row.

    Args:
        row: A row of `notes`.

    Returns:
        The note.
    """
    return Note(
        kind=row["kind"],
        day=row["day"],
        created=row["created"],
        span_start=row["span_start"],
        span_end=row["span_end"],
        text=row["text"],
        source=row["source"],
        cites=json.loads(row["cites"]),
        facts=json.loads(row["facts"]),
        id=row["id"],
    )
