import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from munshi.config import Config
from munshi.store import Store
from munshi.timefmt import SLOT_SECONDS, Clock, day_bounds, day_of, slot_start
from munshi.write import blocks as blk
from munshi.write import journal
from munshi.write.model import JsonModel, ModelError
from munshi.write.notes import day_note, where_note
from munshi.write.slots import compact

log = logging.getLogger(__name__)

LOOKBACK = 2 * 24 * 3600
CLOSE_DAYS = 7
RUN_LOCK = threading.Lock()
MODEL_ERROR = "model error"


@dataclass
class Result:
    """What one writer run did."""

    slots: int = 0
    accepted: int = 0
    rejected: int = 0
    fallback: int = 0
    model_errors: int = 0
    seconds: list[float] = field(default_factory=list)
    reasons: dict[str, int] = field(default_factory=dict)
    days_closed: list[str] = field(default_factory=list)

    def line(self) -> str:
        """One-line report.

        Returns:
            E.g. "4 slots: 6 blocks written, 1 rejected, 2 fallback".
        """
        written = self.accepted + self.fallback
        text = (
            f"{self.slots} slot{'s' if self.slots != 1 else ''}: {written} blocks written "
            f"({self.accepted} by the model), {self.rejected} rejected, {self.fallback} fallback"
        )
        if self.model_errors:
            text += f", {self.model_errors} model errors"
        return text


def known_projects(store: Store, config: Config) -> list[str]:
    """Return repo names under the allowed roots or seen in git events, plus "Other".

    Args:
        store: The store.
        config: Settings (allowed roots).

    Returns:
        Sorted project names with "Other" last.
    """
    from munshi.collect.git import find_repos

    names = set(store.repos()) | set(store.get("known_repos", []))
    names |= {repo.name for repo in find_repos(config.roots())}
    return sorted(names - {"Other"}, key=str.lower) + ["Other"]


class Writer:
    """Turns finished slots into blocks, then refreshes notes and closes past days."""

    def __init__(
        self,
        store: Store,
        config: Config,
        clock: Clock,
        model: JsonModel | None,
        home: Path | None = None,
    ) -> None:
        """Create the writer.

        Args:
            store: The store.
            config: Settings.
            clock: Time source.
            model: The model, or None for code-only blocks and notes.
            home: Data home for journal and hours files; None skips files.
        """
        self.store = store
        self.config = config
        self.clock = clock
        self.model = model
        self.home = home

    def pending(self, now: float) -> list[float]:
        """Return finished, unwritten slot starts with events, oldest first.

        Args:
            now: Current time, epoch seconds.

        Returns:
            Slot starts.
        """
        last_full = slot_start(now)
        events = self.store.events(now - LOOKBACK, last_full, ("window",))
        starts: set[float] = set()
        for event in events:
            t = slot_start(max(event.start, now - LOOKBACK))
            while t < min(event.end, last_full):
                starts.add(t)
                t = slot_start(t + SLOT_SECONDS + 1)
        written = self.store.written_slots(now - LOOKBACK - SLOT_SECONDS, last_full)
        return sorted(starts - written)

    def write_slot(self, start: float, result: Result) -> None:
        """Write one slot's blocks (model first, code fallback) and mark it written.

        Args:
            start: Slot start, epoch seconds.
            result: Counters to update.
        """
        end = slot_start(start + SLOT_SECONDS + 1)
        projects = known_projects(self.store, self.config)
        slot = compact(self.store.events(start, end), start, end, projects)
        topics = self.store.topics()
        taken: set[str] = set()
        made, accepted, rejected = [], 0, 0
        reasons: dict[str, int] = {}
        seconds = None
        if self.model is not None and slot.window_items():
            began = time.monotonic()
            try:
                answer = self.model.chat_json(
                    blk.SYSTEM, blk.prompt(slot, projects, topics), blk.schema(slot, projects)
                )
                replies = blk.parse(answer)
                if replies is None:
                    rejected += 1
                    reasons["bad shape"] = reasons.get("bad shape", 0) + 1
                for reply in replies or []:
                    block, reason = blk.check(reply, slot, projects, topics, taken)
                    if block:
                        made.append(block)
                        accepted += 1
                        topics.append(block.topic)
                    else:
                        rejected += 1
                        reasons[reason] = reasons.get(reason, 0) + 1
            except ModelError:
                result.model_errors += 1
                reasons[MODEL_ERROR] = 1
            seconds = time.monotonic() - began
            result.seconds.append(seconds)
        backup = blk.fallback(slot, taken, projects)
        for block in sorted(made + backup, key=lambda b: b.start):
            self.store.add_block(block)
        self.store.mark_slot(
            start, self.clock.now(), accepted, rejected, len(backup), seconds, reasons
        )
        for reason, count in reasons.items():
            if reason != MODEL_ERROR:
                result.reasons[reason] = result.reasons.get(reason, 0) + count
        result.slots += 1
        result.accepted += accepted
        result.rejected += rejected
        result.fallback += len(backup)

    def close_days(self, now: float, result: Result) -> None:
        """Write day notes, journal pages and hours for past days not closed yet.

        Args:
            now: Current time, epoch seconds.
            result: Updated with the days closed.
        """
        today = day_of(now)
        for back in range(CLOSE_DAYS, 0, -1):
            day = today - timedelta(days=back)
            if self.store.note("day", day.isoformat()):
                continue
            note = day_note(self.store, day, now, self.model)
            if note is None:
                continue
            self.store.add_note(note)
            if self.home is not None:
                journal.write(self.store, self.home, day)
            result.days_closed.append(day.isoformat())

    def run(self) -> Result:
        """Write all pending slots, refresh the "where" note, close past days, prune.

        Returns:
            What was done.
        """
        result = Result()
        with RUN_LOCK:
            began = time.monotonic()
            now = self.clock.now()
            for start in self.pending(now):
                self.write_slot(start, result)
            self.store.add_note(where_note(self.store, now, self.model))
            self.close_days(now, result)
            cutoff = day_bounds(day_of(now))[0] - self.config.keep_events_days * 86400
            self.store.prune_events(cutoff)
            self.store.set(
                "last_write",
                {"at": now, "slots": result.slots, "seconds": time.monotonic() - began},
            )
        return result


def run_forever(writer: Writer, stop: threading.Event, interval: float, first: float) -> None:
    """Run the writer every `interval` seconds until stopped.

    Args:
        writer: The writer.
        stop: Set it to end the loop.
        interval: Seconds between runs.
        first: Seconds before the first run.
    """
    if stop.wait(first):
        return
    while True:
        try:
            writer.run()
        except Exception as exc:  # keep the writer alive after a bad run
            log.warning("writer run failed: %s", type(exc).__name__)
        if stop.wait(interval):
            return
