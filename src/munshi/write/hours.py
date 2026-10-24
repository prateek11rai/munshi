import csv
import io
from dataclasses import dataclass, field
from datetime import date

from munshi.store import Block, Store
from munshi.timefmt import day_bounds, hours_text, quarter_hours


@dataclass
class ProjectHours:
    """Active time of one project on one day, with its topics."""

    project: str
    seconds: float
    topics: dict[str, float] = field(default_factory=dict)

    @property
    def hours(self) -> float:
        """Hours rounded to the nearest quarter.

        Returns:
            Rounded hours.
        """
        return quarter_hours(self.seconds)

    def topic_names(self) -> list[str]:
        """Topics, biggest first.

        Returns:
            Topic names.
        """
        return sorted(self.topics, key=lambda t: -self.topics[t])


def clip(block: Block, start: float, end: float) -> float:
    """Return a block's active seconds inside a range, split in proportion.

    Args:
        block: The block.
        start: Range start, epoch seconds.
        end: Range end, epoch seconds.

    Returns:
        Active seconds that fall inside the range.
    """
    length = block.end - block.start
    if length <= 0:
        return block.active if start <= block.start < end else 0.0
    inside = max(0.0, min(block.end, end) - max(block.start, start))
    return block.active * inside / length


def day_hours(store: Store, day: date) -> list[ProjectHours]:
    """Active time per project and topic for a local day (midnight to midnight).

    Args:
        store: The store.
        day: The day.

    Returns:
        Projects, biggest first.
    """
    start, end = day_bounds(day)
    rows: dict[str, ProjectHours] = {}
    for block in store.blocks(start, end):
        seconds = clip(block, start, end)
        if seconds <= 0:
            continue
        row = rows.setdefault(block.project, ProjectHours(block.project, 0.0))
        row.seconds += seconds
        row.topics[block.topic] = row.topics.get(block.topic, 0.0) + seconds
    return sorted(rows.values(), key=lambda r: -r.seconds)


def day_totals(store: Store, day: date) -> tuple[float, float]:
    """Active and away seconds for a day.

    Args:
        store: The store.
        day: The day.

    Returns:
        (active seconds, away seconds).
    """
    start, end = day_bounds(day)
    active = sum(clip(b, start, end) for b in store.blocks(start, end))
    away = sum(
        max(0.0, min(e.end, end) - max(e.start, start)) for e in store.events(start, end, ("away",))
    )
    return active, away


def timesheet(rows: list[ProjectHours]) -> str:
    """Lines for a timesheet: "tidepool · 2.5 h · tide-chart caching, CI fix".

    Args:
        rows: Output of `day_hours`.

    Returns:
        One line per project with at least a quarter hour.
    """
    lines = [
        f"{r.project} · {hours_text(r.hours)} h · {', '.join(r.topic_names()[:4])}"
        for r in rows
        if r.hours > 0
    ]
    return "\n".join(lines)


def to_csv(day: date, rows: list[ProjectHours]) -> str:
    """CSV with `date,project,topic,hours`, hours rounded to a quarter.

    Args:
        day: The day.
        rows: Output of `day_hours`.

    Returns:
        CSV text with a header.
    """
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["date", "project", "topic", "hours"])
    for row in rows:
        for topic in row.topic_names():
            hours = quarter_hours(row.topics[topic])
            if hours > 0:
                writer.writerow([day.isoformat(), row.project, topic, hours_text(hours)])
    return out.getvalue()
