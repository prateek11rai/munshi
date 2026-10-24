from datetime import date
from pathlib import Path

from munshi.store import Store
from munshi.timefmt import day_bounds, duration, hm, hours_text, long_day
from munshi.write.blocks import merge_adjacent
from munshi.write.hours import clip, day_hours, day_totals, to_csv


def left_open(store: Store, day: date) -> list[str]:
    """Repos with uncommitted files at the end of a day.

    Args:
        store: The store.
        day: The day.

    Returns:
        Lines like "tidepool: 3 uncommitted files".
    """
    start, end = day_bounds(day)
    lines = []
    for repo in store.repos():
        events = [e for e in store.events(start, end, ("git",)) if e.repo == repo]
        if events and (n := int(events[-1].detail.get("dirty", 0))):
            lines.append(f"{repo}: {n} uncommitted file{'s' if n != 1 else ''}")
    return lines


def render(store: Store, day: date) -> str:
    """Render a day's journal page in Markdown.

    Args:
        store: The store.
        day: The day.

    Returns:
        The Markdown text.
    """
    start, end = day_bounds(day)
    blocks = store.blocks(start, end)
    by_id = {b.id: b for b in blocks}
    active, away = day_totals(store, day)
    lines = [f"# {long_day(day)}", "", f"Active {duration(active)} · away {duration(away)}", ""]
    note = store.note("day", day.isoformat())
    lines.append("## Summary")
    if note:
        for bullet in note.facts.get("bullets", []):
            seconds = sum(clip(by_id[c], start, end) for c in bullet["cites"] if c in by_id)
            lines.append(f"- {bullet['text']} ({duration(seconds)})")
    else:
        lines.append("- Not summarised yet.")
    lines += ["", "## Timeline"]
    for block in merge_adjacent(blocks):
        lo, hi = max(block.start, start), min(block.end, end)
        lines.append(f"- {hm(lo)}–{hm(hi)} · {block.project} · {block.topic}")
    if not blocks:
        lines.append("- Nothing recorded.")
    lines += ["", "## Hours", "| Project | Hours | Topics |", "|---|---|---|"]
    for row in day_hours(store, day):
        topics = ", ".join(row.topic_names()[:4]).replace("|", "/")
        lines.append(f"| {row.project} | {hours_text(row.hours)} | {topics} |")
    if open_lines := left_open(store, day):
        lines += ["", "## Left open", *[f"- {line}" for line in open_lines]]
    return "\n".join(lines) + "\n"


def write(store: Store, home: Path, day: date) -> tuple[Path, Path]:
    """Write a day's journal page and hours CSV under the home folder.

    Args:
        store: The store.
        home: The data home.
        day: The day.

    Returns:
        (journal path, CSV path).
    """
    journal_dir, hours_dir = home / "journal", home / "hours"
    for folder in (journal_dir, hours_dir):
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    page = journal_dir / f"{day.isoformat()}.md"
    page.write_text(render(store, day))
    sheet = hours_dir / f"{day.isoformat()}.csv"
    sheet.write_text(to_csv(day, day_hours(store, day)))
    return page, sheet
