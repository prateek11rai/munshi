import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('window', 'away', 'git', 'file')),
    start REAL NOT NULL,
    end REAL NOT NULL,
    app TEXT,
    title TEXT,
    repo TEXT,
    detail TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS events_time ON events (start, end);
CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY,
    slot REAL NOT NULL,
    start REAL NOT NULL,
    end REAL NOT NULL,
    active REAL NOT NULL,
    project TEXT NOT NULL,
    topic TEXT NOT NULL,
    summary TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('model', 'fallback', 'demo')),
    evidence TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS blocks_time ON blocks (start, end);
CREATE TABLE IF NOT EXISTS slots (
    start REAL PRIMARY KEY,
    written REAL NOT NULL,
    accepted INTEGER NOT NULL DEFAULT 0,
    rejected INTEGER NOT NULL DEFAULT 0,
    fallback INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS topics (
    name TEXT PRIMARY KEY COLLATE NOCASE,
    project TEXT NOT NULL,
    first_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('where', 'day')),
    day TEXT NOT NULL,
    created REAL NOT NULL,
    span_start REAL NOT NULL,
    span_end REAL NOT NULL,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    cites TEXT NOT NULL DEFAULT '[]',
    facts TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


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


class Store:
    """SQLite storage for events, blocks, slots, topics, notes and state."""

    def __init__(self, path: Path | str) -> None:
        """Open (and if needed create) the database.

        Args:
            path: Database file, or ":memory:".
        """
        self.path = str(path)
        self.db = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        if self.path != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self.db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        self.db.commit()

    @classmethod
    def at_home(cls, home: Path) -> "Store":
        """Open the store inside a data home.

        Args:
            home: The data home folder (must exist).

        Returns:
            The opened store.
        """
        store = cls(home / "munshi.db")
        (home / "munshi.db").chmod(0o600)
        return store

    def close(self) -> None:
        """Close the database connection."""
        self.db.close()

    def schema_version(self) -> int:
        """Return the stored schema version.

        Returns:
            The `user_version` pragma.
        """
        return self.db.execute("PRAGMA user_version").fetchone()[0]

    # Events

    def add_event(self, event: Event) -> int:
        """Insert an event.

        Args:
            event: The event; its id is set on return.

        Returns:
            The new row id.
        """
        cur = self.db.execute(
            "INSERT INTO events (kind, start, end, app, title, repo, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.kind,
                event.start,
                event.end,
                event.app,
                event.title,
                event.repo,
                json.dumps(event.detail),
            ),
        )
        self.db.commit()
        event.id = cur.lastrowid
        return event.id

    def extend_event(self, event_id: int, end: float) -> None:
        """Move an event's end time.

        Args:
            event_id: The event row id.
            end: The new end, epoch seconds.
        """
        self.db.execute("UPDATE events SET end = ? WHERE id = ?", (end, event_id))
        self.db.commit()

    def events(self, start: float, end: float, kinds: tuple[str, ...] = ()) -> list[Event]:
        """Return events overlapping a time range, oldest first.

        Args:
            start: Range start, epoch seconds.
            end: Range end, epoch seconds.
            kinds: Only these kinds when given.

        Returns:
            The events.
        """
        sql = "SELECT * FROM events WHERE end >= ? AND start < ?"
        params: list[Any] = [start, end]
        if kinds:
            sql += f" AND kind IN ({','.join('?' * len(kinds))})"
            params += list(kinds)
        rows = self.db.execute(sql + " ORDER BY start, id", params).fetchall()
        return [_event(row) for row in rows]

    def last_event(self, kinds: tuple[str, ...] = (), repo: str | None = None) -> Event | None:
        """Return the most recent event of some kinds.

        Args:
            kinds: Only these kinds when given.
            repo: Only this repo when given.

        Returns:
            The event, or None.
        """
        sql, params = "SELECT * FROM events WHERE 1=1", []
        if kinds:
            sql += f" AND kind IN ({','.join('?' * len(kinds))})"
            params += list(kinds)
        if repo is not None:
            sql += " AND repo = ?"
            params.append(repo)
        row = self.db.execute(sql + " ORDER BY end DESC, id DESC LIMIT 1", params).fetchone()
        return _event(row) if row else None

    def repos(self) -> list[str]:
        """Return every repo name seen in git events.

        Returns:
            Sorted repo names.
        """
        rows = self.db.execute("SELECT DISTINCT repo FROM events WHERE kind = 'git'").fetchall()
        return sorted(row[0] for row in rows if row[0])

    def prune_events(self, before: float) -> int:
        """Delete raw events that ended before a time.

        Args:
            before: Epoch seconds.

        Returns:
            Rows deleted.
        """
        cur = self.db.execute("DELETE FROM events WHERE end < ?", (before,))
        self.db.commit()
        return cur.rowcount

    # Blocks and slots

    def add_block(self, block: Block) -> int:
        """Insert a block and remember its topic.

        Args:
            block: The block; its id is set on return.

        Returns:
            The new row id.
        """
        cur = self.db.execute(
            "INSERT INTO blocks (slot, start, end, active, project, topic, summary, source, "
            "evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                block.slot,
                block.start,
                block.end,
                block.active,
                block.project,
                block.topic,
                block.summary,
                block.source,
                json.dumps(block.evidence),
            ),
        )
        self.db.execute(
            "INSERT OR IGNORE INTO topics (name, project, first_seen) VALUES (?, ?, ?)",
            (block.topic, block.project, block.start),
        )
        self.db.commit()
        block.id = cur.lastrowid
        return block.id

    def blocks(self, start: float, end: float) -> list[Block]:
        """Return blocks overlapping a time range, oldest first.

        Args:
            start: Range start, epoch seconds.
            end: Range end, epoch seconds.

        Returns:
            The blocks.
        """
        rows = self.db.execute(
            "SELECT * FROM blocks WHERE end > ? AND start < ? ORDER BY start, id", (start, end)
        ).fetchall()
        return [_block(row) for row in rows]

    def mark_slot(
        self, start: float, written: float, accepted: int = 0, rejected: int = 0, fallback: int = 0
    ) -> None:
        """Record that a slot has been written.

        Args:
            start: Slot start, epoch seconds.
            written: When it was written.
            accepted: Model blocks accepted.
            rejected: Model blocks rejected.
            fallback: Code-made blocks.
        """
        self.db.execute(
            "INSERT OR REPLACE INTO slots (start, written, accepted, rejected, fallback) "
            "VALUES (?, ?, ?, ?, ?)",
            (start, written, accepted, rejected, fallback),
        )
        self.db.commit()

    def written_slots(self, start: float, end: float) -> set[float]:
        """Return the starts of written slots in a range.

        Args:
            start: Range start, epoch seconds.
            end: Range end, epoch seconds.

        Returns:
            Slot starts.
        """
        rows = self.db.execute(
            "SELECT start FROM slots WHERE start >= ? AND start < ?", (start, end)
        ).fetchall()
        return {row[0] for row in rows}

    def topics(self) -> list[str]:
        """Return known topic names.

        Returns:
            Topic names, oldest first.
        """
        rows = self.db.execute("SELECT name FROM topics ORDER BY first_seen").fetchall()
        return [row[0] for row in rows]

    # Notes

    def add_note(self, note: Note) -> int:
        """Insert a note, replacing an older note of the same kind and day.

        Args:
            note: The note; its id is set on return.

        Returns:
            The new row id.
        """
        self.db.execute("DELETE FROM notes WHERE kind = ? AND day = ?", (note.kind, note.day))
        cur = self.db.execute(
            "INSERT INTO notes (kind, day, created, span_start, span_end, text, source, cites, "
            "facts) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                note.kind,
                note.day,
                note.created,
                note.span_start,
                note.span_end,
                note.text,
                note.source,
                json.dumps(note.cites),
                json.dumps(note.facts),
            ),
        )
        self.db.commit()
        note.id = cur.lastrowid
        return note.id

    def note(self, kind: str, day: str | None = None) -> Note | None:
        """Return the latest note of a kind, optionally for one day.

        Args:
            kind: "where" or "day".
            day: ISO date, or None for the latest of any day.

        Returns:
            The note, or None.
        """
        sql, params = "SELECT * FROM notes WHERE kind = ?", [kind]
        if day is not None:
            sql += " AND day = ?"
            params.append(day)
        row = self.db.execute(sql + " ORDER BY created DESC LIMIT 1", params).fetchone()
        return _note(row) if row else None

    # Forget

    def forget(self, start: float, end: float) -> dict[str, int]:
        """Delete events, blocks and notes overlapping a range, and orphaned topics.

        Args:
            start: Range start, epoch seconds.
            end: Range end, epoch seconds.

        Returns:
            Rows deleted per table.
        """
        counts = {}
        for table, lo, hi in (
            ("events", "start", "end"),
            ("blocks", "start", "end"),
            ("notes", "span_start", "span_end"),
        ):
            cur = self.db.execute(
                f"DELETE FROM {table} WHERE {hi} > ? AND {lo} < ?",  # noqa: S608
                (start, end),
            )
            counts[table] = cur.rowcount
        self.db.execute("DELETE FROM topics WHERE name NOT IN (SELECT topic FROM blocks)")
        self.db.commit()
        return counts

    # State

    def get(self, key: str, default: Any = None) -> Any:
        """Read a state value.

        Args:
            key: State key.
            default: Returned when the key is missing.

        Returns:
            The decoded JSON value.
        """
        row = self.db.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value: Any) -> None:
        """Write a state value.

        Args:
            key: State key.
            value: Any JSON-serialisable value; None deletes the key.
        """
        if value is None:
            self.db.execute("DELETE FROM state WHERE key = ?", (key,))
        else:
            self.db.execute(
                "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, json.dumps(value))
            )
        self.db.commit()


def _event(row: sqlite3.Row) -> Event:
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


def _block(row: sqlite3.Row) -> Block:
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


def _note(row: sqlite3.Row) -> Note:
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
