import sqlite3
import tempfile
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from munshi import demo
from munshi.config import Config
from munshi.store import Store
from munshi.timefmt import SLOT_SECONDS, FakeClock, at, day_bounds, slot_start
from munshi.write.model import JsonModel
from munshi.write.writer import Result, Writer


@dataclass
class Report:
    """What an eval run measured."""

    model: str
    result: Result
    wall: float
    source: str = "demo"

    def lines(self) -> list[str]:
        """Format the report.

        Returns:
            Printable lines.
        """
        r = self.result
        judged = r.accepted + r.rejected
        blocks = max(1, r.accepted + r.fallback)
        secs = r.seconds or [0.0]
        out = [
            f"model {self.model} over {r.slots} {self.source} slots",
            f"blocks accepted {r.accepted} · rejected {r.rejected} · fallback {r.fallback}",
        ]
        if judged:
            out.append(f"acceptance {100 * r.accepted / judged:.0f}% of model blocks")
        out.append(f"fallback rate {100 * r.fallback / blocks:.0f}% of blocks")
        out.append(
            f"seconds per slot: mean {sum(secs) / len(secs):.1f} · max {max(secs):.1f}"
            f" · total {self.wall:.0f}"
        )
        out += [
            f"  rejected: {k} × {v}" for k, v in sorted(r.reasons.items(), key=lambda kv: -kv[1])
        ]
        if r.model_errors:
            out.append(f"  model errors: {r.model_errors}")
        return out


def run_eval(
    config: Config, model: JsonModel, slots: int | None = None, today: date | None = None
) -> Report:
    """Write every demo slot with a model into a throwaway in-memory store.

    Args:
        config: Settings.
        model: The model under test.
        slots: Only the first N slots when given.
        today: The demo's "today"; defaults to the real today.

    Returns:
        The report.
    """
    today = today or date.today()
    store = Store(":memory:")
    store.set("known_repos", ["lantern", "tidepool"])
    demo.add_day(store, today - timedelta(days=1), demo.YESTERDAY, demo.GIT["yesterday"])
    demo.add_day(store, today, demo.TODAY, demo.GIT["today"])
    clock = FakeClock(at(today, demo.DEMO_NOW))
    writer = Writer(store, config, clock, model)
    return write_all(writer, model, writer.pending(clock.now())[: slots or None], "demo")


def write_all(writer: Writer, model: JsonModel, starts: list[float], source: str) -> Report:
    """Write the given slots and time the run.

    Args:
        writer: A writer over a throwaway store.
        model: The model under test.
        starts: Slot starts to write.
        source: "demo" or "real", for the report.

    Returns:
        The report.
    """
    result = Result()
    began = time.monotonic()
    for n, start in enumerate(starts, 1):
        writer.write_slot(start, result)
        print(f"\r{n}/{len(starts)} slots", end="", flush=True)
    print()
    return Report(model.name, result, time.monotonic() - began, source)


def day_slots(store: Store, day: date, now: float) -> list[float]:
    """Return a day's finished slots that hold window time.

    Args:
        store: The store.
        day: The day.
        now: Current time; the slot holding it is not finished.

    Returns:
        Slot starts, oldest first.
    """
    lo, hi = day_bounds(day)
    hi = min(hi, slot_start(now))
    starts: set[float] = set()
    for event in store.events(lo, hi, ("window",)):
        t = slot_start(max(event.start, lo))
        while t < min(event.end, hi):
            starts.add(t)
            t = slot_start(t + SLOT_SECONDS + 1)
    return sorted(starts)


def run_real_eval(
    config: Config, model: JsonModel, db: Path, day: date, now: float, slots: int | None = None
) -> Report:
    """Rewrite a day's real slots into a scratch copy of the store; the real one is untouched.

    The day's blocks, slot marks and the topics first seen that day are removed from the
    copy first, so the model sees what it saw the first time.

    Args:
        config: Settings.
        model: The model under test.
        db: The real database file.
        day: The day to rewrite.
        now: Current time, epoch seconds.
        slots: Only the first N slots when given.

    Returns:
        The report (numbers only).
    """
    lo, hi = day_bounds(day)
    with tempfile.TemporaryDirectory(prefix="munshi-eval-") as scratch:
        copy = Path(scratch) / "munshi.db"
        source = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        target = sqlite3.connect(copy)
        try:
            source.backup(target)
        finally:
            source.close()
            target.close()
        store = Store(copy)
        try:
            store.db.execute("DELETE FROM blocks WHERE start >= ? AND start < ?", (lo, hi))
            store.db.execute("DELETE FROM slots WHERE start >= ? AND start < ?", (lo, hi))
            store.db.execute("DELETE FROM topics WHERE first_seen >= ?", (lo,))
            store.db.commit()
            writer = Writer(store, config, FakeClock(now), model)
            return write_all(writer, model, day_slots(store, day, now)[: slots or None], "real")
        finally:
            store.close()
