from munshi.store import Store

UNTIL_RESUME = "until-resume"


def pause(store: Store, now: float, minutes: float | None) -> None:
    """Pause all recording.

    Args:
        store: The store holding the pause state.
        now: Current time, epoch seconds.
        minutes: How long to pause; None pauses until resumed.
    """
    store.set("paused_until", UNTIL_RESUME if minutes is None else now + minutes * 60)


def resume(store: Store) -> None:
    """Resume recording now.

    Args:
        store: The store holding the pause state.
    """
    store.set("paused_until", None)


def paused_until(store: Store, now: float) -> float | str | None:
    """Return when the pause ends.

    Args:
        store: The store holding the pause state.
        now: Current time, epoch seconds.

    Returns:
        Epoch seconds, UNTIL_RESUME, or None when not paused.
    """
    value = store.get("paused_until")
    if value == UNTIL_RESUME:
        return value
    if isinstance(value, int | float) and now < value:
        return float(value)
    return None


def is_paused(store: Store, now: float) -> bool:
    """Tell whether recording is paused.

    Args:
        store: The store holding the pause state.
        now: Current time, epoch seconds.

    Returns:
        True while paused.
    """
    return paused_until(store, now) is not None


def forget(store: Store, now: float, minutes: float = 60) -> dict[str, int]:
    """Delete everything that overlaps the last minutes and rewrite today's note.

    Args:
        store: The store.
        now: Current time, epoch seconds.
        minutes: How far back to forget.

    Returns:
        Rows deleted per table.
    """
    from munshi.timefmt import slot_start
    from munshi.write.notes import code_where_note

    cutoff = now - minutes * 60
    counts = store.forget(cutoff, now + 1, slot_start(cutoff))
    store.add_note(code_where_note(store, now))
    return counts
