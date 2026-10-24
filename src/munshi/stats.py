import json
import os
import threading
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from munshi.collect.procs import usage
from munshi.store import Store
from munshi.timefmt import ago, day_bounds

STATUS_EVERY = 10 * 60
POLL_ORDER = (
    "recorded",
    "private",
    "ignored app",
    "title word",
    "process word",
    "own window",
    "no window",
    "paused",
    "away",
)


def counters(store: Store, day: date) -> dict[str, int]:
    """Return the collector's poll counters for a day.

    Args:
        store: The store.
        day: The day.

    Returns:
        Counter name to polls.
    """
    rows = store.db.execute(
        "SELECT name, n FROM counters WHERE day = ?", (day.isoformat(),)
    ).fetchall()
    return {row["name"]: row["n"] for row in rows}


def slot_rows(store: Store, day: date) -> list[dict[str, Any]]:
    """Return a day's written slots with their counts.

    Args:
        store: The store.
        day: The day.

    Returns:
        One dict per slot: accepted, rejected, fallback, seconds, reasons.
    """
    start, end = day_bounds(day)
    rows = store.db.execute(
        "SELECT * FROM slots WHERE start >= ? AND start < ? ORDER BY start", (start, end)
    ).fetchall()
    return [{**dict(row), "reasons": json.loads(row["reasons"])} for row in rows]


def event_totals(store: Store, day: date) -> dict[str, tuple[int, float]]:
    """Count a day's events per kind and their minutes inside the day.

    Args:
        store: The store.
        day: The day.

    Returns:
        Kind to (count, minutes).
    """
    start, end = day_bounds(day)
    totals: dict[str, tuple[int, float]] = {}
    for event in store.events(start, end):
        count, minutes = totals.get(event.kind, (0, 0.0))
        inside = max(0.0, min(event.end, end) - max(event.start, start))
        totals[event.kind] = (count + 1, minutes + inside / 60)
    return totals


def pid_alive(pid: int) -> bool:
    """Tell whether a process exists.

    Args:
        pid: The process id.

    Returns:
        True when it is running.
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def report(store: Store, day: date, now: float) -> list[str]:
    """Build the stats lines: numbers and fixed labels only, never recorded text.

    Args:
        store: The store.
        day: The day to report.
        now: Current time, epoch seconds.

    Returns:
        Printable lines.
    """
    out = [f"stats for {day.isoformat()} (numbers only)"]
    totals = event_totals(store, day)
    parts = []
    for kind in ("window", "away", "git", "file"):
        count, minutes = totals.get(kind, (0, 0.0))
        timed = f" ({minutes:.0f} min)" if kind in {"window", "away"} else ""
        parts.append(f"{kind} {count}{timed}")
    out.append("events: " + " · ".join(parts))
    polls = counters(store, day)
    names = [n for n in POLL_ORDER if n in polls] + sorted(set(polls) - set(POLL_ORDER))
    out.append("polls: " + (" · ".join(f"{n} {polls[n]}" for n in names) if polls else "none"))
    slots = slot_rows(store, day)
    accepted = sum(s["accepted"] for s in slots)
    rejected = sum(s["rejected"] for s in slots)
    fallback = sum(s["fallback"] for s in slots)
    made = accepted + fallback
    rate = f" · fallback rate {100 * fallback / made:.0f}%" if made else ""
    out.append(
        f"slots written {len(slots)} · blocks accepted {accepted} · rejected {rejected}"
        f" · fallback {fallback}{rate}"
    )
    reasons: dict[str, int] = {}
    for slot in slots:
        for name, count in slot["reasons"].items():
            reasons[name] = reasons.get(name, 0) + count
    for name, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        out.append(f"  {name} × {count}")
    secs = [s["seconds"] for s in slots if s["seconds"] is not None]
    if secs:
        out.append(
            f"seconds per slot: mean {sum(secs) / len(secs):.1f} · max {max(secs):.1f}"
            f" ({len(secs)} model calls)"
        )
    last = store.get("last_write")
    if last:
        out.append(
            f"last writer run: {ago(now - last['at'])}, {last['slots']} slots"
            f" in {last['seconds']:.1f} s"
        )
    else:
        out.append("last writer run: none yet")
    out.append(app_line(store, now))
    return out


def app_line(store: Store, now: float) -> str:
    """Describe the running app from what it stored last.

    Args:
        store: The store.
        now: Current time, epoch seconds.

    Returns:
        One line: running or not, Accessibility, memory and CPU.
    """
    status = store.get("app_status")
    if not status:
        return "app: no status stored yet"
    running = pid_alive(int(status["pid"]))
    line = f"app: {'running' if running else 'not running'} · checked {ago(now - status['at'])}"
    line += f" · Accessibility {'granted' if status['accessibility'] else 'not granted'}"
    if status.get("rss_mb") is not None:
        line += f" · RSS {status['rss_mb']:.0f} MB · CPU {status['cpu']:.1f}%"
    return line


def record_status(store: Store, now: float, pid: int, accessibility: bool) -> None:
    """Store the running app's Accessibility flag, memory and CPU share.

    Args:
        store: The store.
        now: Current time, epoch seconds.
        pid: The app's process id.
        accessibility: Whether window titles can be read.
    """
    use = usage(pid)
    store.set(
        "app_status",
        {
            "pid": pid,
            "at": now,
            "accessibility": accessibility,
            "rss_mb": use[0] if use else None,
            "cpu": use[1] if use else None,
        },
    )


def status_loop(
    home: Path,
    stop: threading.Event,
    now: Callable[[], float],
    accessibility: Callable[[], bool],
    interval: float = STATUS_EVERY,
) -> None:
    """Store the app's status at launch and every `interval` seconds until stopped.

    Args:
        home: Data home.
        stop: Set it to end the loop.
        now: Time source.
        accessibility: Reads the Accessibility flag.
        interval: Seconds between updates.
    """
    while True:
        store = Store.at_home(home)
        try:
            record_status(store, now(), os.getpid(), accessibility())
        except Exception:  # noqa: S110 (stats must never stop the app)
            pass
        finally:
            store.close()
        if stop.wait(interval):
            return
