import time
from dataclasses import dataclass
from datetime import date, timedelta

from munshi import demo
from munshi.config import Config
from munshi.store import Store
from munshi.timefmt import FakeClock, at
from munshi.write.model import JsonModel
from munshi.write.writer import Result, Writer


@dataclass
class Report:
    """What an eval run measured."""

    model: str
    result: Result
    wall: float

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
            f"model {self.model} over {r.slots} demo slots",
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
    pending = writer.pending(clock.now())[: slots or None]
    result = Result()
    began = time.monotonic()
    for n, start in enumerate(pending, 1):
        writer.write_slot(start, result)
        print(f"\r{n}/{len(pending)} slots", end="", flush=True)
    print()
    return Report(model.name, result, time.monotonic() - began)
