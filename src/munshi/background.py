import threading
from pathlib import Path

from munshi.config import Config
from munshi.store import Store
from munshi.timefmt import Clock, SystemClock


def status_thread(home: Path, clock: Clock, stop: threading.Event) -> threading.Thread:
    """Build the thread that stores Accessibility, memory and CPU every ten minutes.

    Args:
        home: Data home.
        clock: Time source.
        stop: Stops the loop.

    Returns:
        The thread, not started.
    """
    from munshi.collect.macos import accessibility_granted
    from munshi.stats import status_loop

    return threading.Thread(
        target=status_loop,
        args=(home, stop, clock.now, accessibility_granted),
        daemon=True,
        name="status",
    )


def collector_thread(home: Path, config: Config, stop: threading.Event) -> threading.Thread:
    """Build the real collector thread (never used with --demo).

    Args:
        home: Data home.
        config: Settings.
        stop: Stops the loop.

    Returns:
        The thread, not started.
    """
    from munshi.collect.files import FileScanner
    from munshi.collect.git import GitScanner
    from munshi.collect.loop import Collector
    from munshi.collect.macos import MacWindowSource

    collector = Collector(
        Store.at_home(home), config, MacWindowSource(), SystemClock(), (GitScanner(), FileScanner())
    )
    return threading.Thread(target=collector.run, args=(stop,), daemon=True, name="collector")
