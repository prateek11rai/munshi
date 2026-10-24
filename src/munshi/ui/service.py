import threading
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

from munshi import control, demo
from munshi.config import Config, load_config
from munshi.store import Store
from munshi.timefmt import Clock, SystemClock, ago, day_bounds, day_of, duration, hm, hours_text
from munshi.write.blocks import merge_adjacent
from munshi.write.hours import day_hours, day_totals, timesheet
from munshi.write.model import JsonModel, Ollama
from munshi.write.notes import code_day_bullets, facts_text
from munshi.write.writer import Writer

MIN_AWAY = 5 * 60
PAUSE_CHOICES = {"30": 30.0, "60": 60.0, "until": None}


class Service:
    """Everything the card can show or do, shared by the app window and the preview."""

    def __init__(
        self,
        home: Path,
        demo_mode: bool,
        model: Callable[[Config], JsonModel | None] | None = None,
    ) -> None:
        """Create the service.

        Args:
            home: Data home (real or demo).
            demo_mode: Use the demo clock.
            model: Builds the model from the config; defaults to the local Ollama.
        """
        self.home = home
        self.demo = demo_mode
        self.make_model = model or (lambda config: Ollama.from_config(config))
        self.models: dict[tuple[str, str], JsonModel | None] = {}
        self.lock = threading.Lock()
        self.busy = False

    def _model(self, config: Config) -> JsonModel | None:
        # One client per model, so what it learnt (e.g. no structured output) is kept.
        key = (config.ollama_url, config.model)
        if key not in self.models:
            self.models[key] = self.make_model(config)
        return self.models[key]

    def _open(self) -> tuple[Store, Config, Clock]:
        config = load_config(self.home)
        store = Store.at_home(self.home)
        clock: Clock = demo.clock(store) if self.demo else SystemClock()
        return store, config, clock

    def card(self) -> dict[str, Any]:
        """Build everything the card shows, formatted by code.

        Returns:
            A JSON-able dict: where, today, yesterday, hours, paused, flags.
        """
        store, _, clock = self._open()
        try:
            return self._card(store, clock.now())
        finally:
            store.close()

    def _card(self, store: Store, now: float) -> dict[str, Any]:
        today = day_of(now)
        yesterday = today - timedelta(days=1)
        note = store.note("where")
        where = {"text": "Nothing written yet.", "facts": "", "updated": ""}
        if note:
            where = {
                "text": note.text,
                "facts": facts_text(note.facts),
                "updated": "updated " + ago(now - note.created),
            }
        until = control.paused_until(store, now)
        paused = {"on": until is not None, "text": ""}
        if until == control.UNTIL_RESUME:
            paused["text"] = "Paused until you resume"
        elif until is not None:
            paused["text"] = f"Paused until {hm(float(until))}"
        return {
            "where": where,
            "today": self._timeline(store, today, now),
            "yesterday": self._yesterday(store, yesterday),
            "hours": {
                "today": self._hours(store, today),
                "yesterday": self._hours(store, yesterday),
            },
            "hours_view": store.get("hours_view", "today"),
            "paused": paused,
            "busy": self.busy,
            "demo": self.demo,
        }

    def _timeline(self, store: Store, day: Any, now: float) -> list[dict[str, str]]:
        start, end = day_bounds(day)
        rows: list[tuple[float, dict[str, str]]] = []
        for block in merge_adjacent(store.blocks(start, end)):
            lo, hi = max(block.start, start), min(block.end, end)
            rows.append(
                (
                    lo,
                    {
                        "kind": "block",
                        "time": f"{hm(lo)}–{hm(hi)}",
                        "project": block.project,
                        "topic": block.topic,
                    },
                )
            )
        for event in store.events(start, min(end, now), ("away",)):
            seconds = min(event.end, end) - max(event.start, start)
            if seconds >= MIN_AWAY:
                rows.append((event.start, {"kind": "away", "text": f"away {duration(seconds)}"}))
        return [row for _, row in sorted(rows, key=lambda r: r[0], reverse=True)]

    def _yesterday(self, store: Store, day: Any) -> dict[str, Any]:
        start, end = day_bounds(day)
        blocks = store.blocks(start, end)
        if not blocks:
            return {"lines": [], "total": "", "empty": "Nothing from yesterday yet."}
        note = store.note("day", day.isoformat())
        bullets = note.facts.get("bullets", []) if note else code_day_bullets(blocks)
        active, _ = day_totals(store, day)
        return {
            "lines": [b["text"] for b in bullets],
            "total": f"Active {duration(active)}",
            "empty": "",
        }

    def _hours(self, store: Store, day: Any) -> dict[str, Any]:
        rows = day_hours(store, day)
        top = max((r.seconds for r in rows), default=0) or 1
        active, _ = day_totals(store, day)
        return {
            "total": duration(active) if rows else "",
            "rows": [
                {
                    "project": r.project,
                    "hours": f"{hours_text(r.hours)} h",
                    "pct": round(100 * r.seconds / top),
                    "topics": ", ".join(r.topic_names()[:3]),
                }
                for r in rows
            ],
        }

    def refresh(self) -> dict[str, Any]:
        """Run the writer now, then return the card.

        Returns:
            The card, with "message" describing what was written.
        """
        if not self.lock.acquire(blocking=False):
            return {**self.card(), "message": "Already writing."}
        self.busy = True
        try:
            store, config, clock = self._open()
            try:
                model = self._model(config)
                status = getattr(model, "status", None)
                if model is not None and status is not None and not status()[0]:
                    model = None
                result = Writer(store, config, clock, model, self.home).run()
            finally:
                store.close()
            message = f"Wrote {result.accepted + result.fallback} blocks."
            if result.slots == 0:
                message = "Up to date."
            elif model is None:
                message += " The model was not reachable, so code wrote them."
        finally:
            self.busy = False
            self.lock.release()
        return {**self.card(), "message": message}

    def _act(self, fn: Callable[[Store, float], Any]) -> dict[str, Any]:
        store, _, clock = self._open()
        try:
            fn(store, clock.now())
        finally:
            store.close()
        return self.card()

    def pause(self, choice: str) -> dict[str, Any]:
        """Pause recording.

        Args:
            choice: "30", "60" or "until".

        Returns:
            The card.

        Raises:
            ValueError: For an unknown choice.
        """
        if choice not in PAUSE_CHOICES:
            raise ValueError("unknown pause choice")
        return self._act(lambda s, now: control.pause(s, now, PAUSE_CHOICES[choice]))

    def resume(self) -> dict[str, Any]:
        """Resume recording.

        Returns:
            The card.
        """
        return self._act(lambda s, now: control.resume(s))

    def forget(self) -> dict[str, Any]:
        """Forget the last hour.

        Returns:
            The card.
        """
        return self._act(lambda s, now: control.forget(s, now, 60))

    def set_hours_view(self, view: str) -> dict[str, Any]:
        """Remember which day the hours bars show.

        Args:
            view: "today" or "yesterday".

        Returns:
            The card.

        Raises:
            ValueError: For an unknown view.
        """
        if view not in {"today", "yesterday"}:
            raise ValueError("unknown view")
        return self._act(lambda s, now: s.set("hours_view", view))

    def timesheet(self, view: str) -> str:
        """Timesheet lines for today or yesterday.

        Args:
            view: "today" or "yesterday".

        Returns:
            Lines like "tidepool · 2.5 h · tide-chart caching, CI fix".
        """
        store, _, clock = self._open()
        try:
            day = day_of(clock.now()) - timedelta(days=1 if view == "yesterday" else 0)
            return timesheet(day_hours(store, day))
        finally:
            store.close()

    def paused(self) -> bool:
        """Tell whether recording is paused.

        Returns:
            The pause flag.
        """
        store, _, clock = self._open()
        try:
            return control.is_paused(store, clock.now())
        finally:
            store.close()

    def journal_dir(self) -> Path:
        """Return (and create) the journal folder.

        Returns:
            The folder path.
        """
        folder = self.home / "journal"
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        return folder
