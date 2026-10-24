import argparse
import logging
import platform
import re
import sys
import threading
import time
from datetime import date, timedelta
from pathlib import Path

from munshi import __version__, control, demo
from munshi.config import Config, ConfigError, demo_home, from_raw, load_config, real_home
from munshi.store import Store
from munshi.timefmt import Clock, FakeClock, SystemClock, at, day_of, hm
from munshi.write import journal
from munshi.write.hours import day_hours, timesheet, to_csv
from munshi.write.model import Ollama
from munshi.write.notes import day_note
from munshi.write.writer import Writer, run_forever

WRITE_EVERY = 15 * 60


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the munshi command.

    Returns:
        The configured parser.
    """
    parser = argparse.ArgumentParser(prog="munshi", description="Your daily work register.")
    parser.add_argument("--version", action="version", version=f"munshi {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, text: str, demo_flag: bool = True) -> argparse.ArgumentParser:
        cmd = sub.add_parser(name, help=text, description=text)
        if demo_flag:
            cmd.add_argument("--demo", action="store_true", help="use the demo home")
        return cmd

    start = add("start", "Start the buddy (and, without --demo, recording).")
    start.add_argument("--self-test", action="store_true", help=argparse.SUPPRESS)
    add("doctor", "Check the setup.")
    demo_cmd = add("demo", "Load or clear the two made-up demo days.", demo_flag=False)
    demo_cmd.add_argument("action", choices=["load", "clear"])
    add("write", "Run the writer once now.")
    for name, text in (("journal", "Write and print a day's journal."), ("hours", "Hours.")):
        cmd = add(name, text)
        cmd.add_argument("--date", type=date.fromisoformat, help="YYYY-MM-DD")
        if name == "hours":
            cmd.add_argument("--csv", action="store_true", help="print CSV")
    pause = add("pause", "Pause recording.")
    pause.add_argument("--for", dest="duration", help="30m or 1h; default until resume")
    add("resume", "Resume recording.")
    forget = add("forget", "Forget recent time.")
    forget.add_argument("--last", default="60m", help="e.g. 60m or 2h")
    preview = add("preview", "Serve the card on http://127.0.0.1:8765.")
    preview.add_argument("--port", type=int, default=8765, help=argparse.SUPPRESS)
    ev = add("eval", "Run the writer over the demo days with a model.")
    ev.add_argument("--model", help="Ollama model name")
    ev.add_argument("--slots", type=int, help="only the first N slots")
    return parser


def minutes(text: str) -> float:
    """Parse "30m", "1h" or "90" into minutes.

    Args:
        text: The duration.

    Returns:
        Minutes.

    Raises:
        ValueError: For anything else.
    """
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(m|min|h)?\s*", text)
    if not match:
        raise ValueError(f"not a duration: {text}")
    value = float(match.group(1))
    return value * 60 if match.group(2) == "h" else value


def open_home(demo_mode: bool) -> tuple[Path, Config, Store, Clock]:
    """Open the real or demo home; the demo is loaded when missing or out of date.

    Args:
        demo_mode: Use the demo home.

    Returns:
        (home, config, store, clock).
    """
    home = demo_home() if demo_mode else real_home()
    config = load_config(home)
    store = Store.at_home(home)
    if not demo_mode:
        return home, config, store, SystemClock()
    if demo.is_stale(store):
        store.close()
        demo.load(home)
        print("Loaded the demo days.")
        store = Store.at_home(home)
    return home, config, store, demo.clock(store)


def model_or_none(config: Config, name: str | None = None) -> Ollama | None:
    """Return the local model, or None (with a note) when Ollama is not answering.

    Args:
        config: Settings.
        name: Model name overriding the config.

    Returns:
        The client or None.
    """
    model = Ollama.from_config(config, name)
    reachable, present = model.status()
    if not reachable:
        print("Ollama is not reachable; code writes the blocks instead.")
        return None
    if not present:
        print(f"Model {model.name} is not pulled; code writes the blocks instead.")
        return None
    return model


def cmd_doctor(args: argparse.Namespace) -> int:
    """Print ✓/✗ checks. Reads only booleans and versions; creates nothing.

    Args:
        args: Parsed arguments.

    Returns:
        0.
    """
    home = demo_home() if args.demo else real_home()
    config_path = home / "config.toml"
    config = from_raw({})
    if config_path.exists():
        try:
            config = load_config(home)
        except ConfigError:
            print("✗ config file has a bad value")

    def line(ok: bool, text: str) -> None:
        print(f"{'✓' if ok else '✗'} {text}")

    line(sys.version_info >= (3, 13), f"Python {platform.python_version()}")
    mac = platform.mac_ver()[0]
    line(bool(mac), f"macOS {mac}" if mac else "macOS (not macOS: the collector will not run)")
    reachable, present = Ollama.from_config(config).status()
    line(reachable, "Ollama reachable" if reachable else "Ollama not reachable (ollama serve)")
    line(present, f"model {config.model} present" if present else f"model {config.model} missing")
    if mac:
        from munshi.collect.macos import accessibility_granted

        granted = accessibility_granted()
        line(
            granted,
            "Accessibility granted"
            if granted
            else "Accessibility not granted: app names only, no titles",
        )
    roots = len(config.allowed_roots)
    line(
        roots > 0,
        f"{roots} allowed roots" if roots else "no allowed roots: git and file scanning is off",
    )
    line(home.is_dir(), "data dir exists" if home.is_dir() else "data dir not created yet")
    line(
        config_path.exists(),
        f"config {'at' if config_path.exists() else 'will be at'} {_short(config_path)}",
    )
    return 0


def _short(path: Path) -> str:
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def cmd_write(args: argparse.Namespace) -> int:
    """Run the writer once.

    Args:
        args: Parsed arguments.

    Returns:
        0.
    """
    home, config, store, clock = open_home(args.demo)
    result = Writer(store, config, clock, model_or_none(config), home).run()
    print(result.line() if result.slots else "Nothing to write; every finished slot is written.")
    for reason, count in sorted(result.reasons.items()):
        print(f"  rejected: {reason} × {count}")
    for day in result.days_closed:
        print(f"  closed {day}")
    return 0


def cmd_journal(args: argparse.Namespace) -> int:
    """Write and print a day's journal.

    Args:
        args: Parsed arguments.

    Returns:
        0.
    """
    home, config, store, clock = open_home(args.demo)
    day = args.date or day_of(clock.now()) - timedelta(days=1)
    if day < day_of(clock.now()) and not store.note("day", day.isoformat()):
        note = day_note(store, day, clock.now(), model_or_none(config))
        if note:
            store.add_note(note)
    page, _ = journal.write(store, home, day)
    print(page.read_text(), end="")
    return 0


def cmd_hours(args: argparse.Namespace) -> int:
    """Print hours per project and topic.

    Args:
        args: Parsed arguments.

    Returns:
        0.
    """
    _, _, store, clock = open_home(args.demo)
    day = args.date or day_of(clock.now())
    rows = day_hours(store, day)
    if args.csv:
        print(to_csv(day, rows), end="")
    else:
        print(timesheet(rows) or "Nothing recorded.")
    return 0


def cmd_pause(args: argparse.Namespace) -> int:
    """Pause recording.

    Args:
        args: Parsed arguments.

    Returns:
        0.
    """
    _, _, store, clock = open_home(args.demo)
    span = minutes(args.duration) if args.duration else None
    control.pause(store, clock.now(), span)
    until = control.paused_until(store, clock.now())
    print("Paused until you resume." if span is None else f"Paused until {hm(float(until))}.")
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    """Resume recording.

    Args:
        args: Parsed arguments.

    Returns:
        0.
    """
    _, _, store, _ = open_home(args.demo)
    control.resume(store)
    print("Recording again.")
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    """Forget recent time.

    Args:
        args: Parsed arguments.

    Returns:
        0.
    """
    _, _, store, clock = open_home(args.demo)
    span = minutes(args.last)
    counts = control.forget(store, clock.now(), span)
    print(f"Forgot the last {int(span)} min: {counts['events'] + counts['trimmed']} events, "
          f"{counts['blocks']} blocks.")  # fmt: skip
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    """Serve the card for a browser.

    Args:
        args: Parsed arguments.

    Returns:
        0.
    """
    from munshi.ui.preview import serve
    from munshi.ui.service import Service

    home, _, store, _ = open_home(args.demo)
    store.close()
    server = serve(Service(home, args.demo), args.port)
    print(f"Card at http://127.0.0.1:{args.port} (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    """Run the writer over fresh copies of the demo days and report.

    Args:
        args: Parsed arguments.

    Returns:
        0, or 1 when the model is not available.
    """
    if not args.demo:
        print("eval runs on the demo days; add --demo.")
        return 1
    home = demo_home()
    config = load_config(home) if (home / "config.toml").exists() else from_raw({})
    model = model_or_none(config, args.model)
    if model is None:
        return 1
    today = date.today()
    store = Store(":memory:")
    store.set("known_repos", ["lantern", "tidepool"])
    demo.add_day(store, today - timedelta(days=1), demo.YESTERDAY, demo.GIT["yesterday"])
    demo.add_day(store, today, demo.TODAY, demo.GIT["today"])
    clock = FakeClock(at(today, demo.DEMO_NOW))
    writer = Writer(store, config, clock, model)
    pending = writer.pending(clock.now())[: args.slots or None]
    from munshi.write.writer import Result

    result = Result()
    began = time.monotonic()
    for n, start in enumerate(pending, 1):
        writer.write_slot(start, result)
        print(f"\r{n}/{len(pending)} slots", end="", flush=True)
    print()
    total = result.accepted + result.rejected
    secs = result.seconds or [0.0]
    print(f"model {model.name} over {result.slots} demo slots")
    print(
        f"blocks accepted {result.accepted} · rejected {result.rejected}"
        f" · fallback {result.fallback}"
    )
    if total:
        print(f"acceptance {100 * result.accepted / total:.0f}% of model blocks")
    blocks = max(1, result.accepted + result.fallback)
    print(f"fallback rate {100 * result.fallback / blocks:.0f}% of blocks")
    print(f"seconds per slot: mean {sum(secs) / len(secs):.1f} · max {max(secs):.1f} · "
          f"total {time.monotonic() - began:.0f}")  # fmt: skip
    for reason, count in sorted(result.reasons.items(), key=lambda kv: -kv[1]):
        print(f"  rejected: {reason} × {count}")
    if result.model_errors:
        print(f"  model errors: {result.model_errors}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """Load or clear the demo days.

    Args:
        args: Parsed arguments.

    Returns:
        0.
    """
    if args.action == "load":
        home = demo.load()
        print(f"Loaded two made-up days into {_short(home)}.")
    else:
        demo.clear()
        print("Cleared the demo home.")
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    """Start the buddy; without --demo also the collector.

    Args:
        args: Parsed arguments.

    Returns:
        Exit code.
    """
    if sys.platform != "darwin":
        print("The buddy needs macOS. Try `munshi preview --demo` in a browser.")
        return 1
    from munshi.ui.app import run
    from munshi.ui.service import Service

    home, config, store, clock = open_home(args.demo)
    stop = threading.Event()
    model = model_or_none(config)
    writer = Writer(store, config, clock, model, home)
    threads = [
        threading.Thread(
            target=run_forever,
            args=(writer, stop, WRITE_EVERY, WRITE_EVERY if args.demo else 60),
            daemon=True,
            name="writer",
        )
    ]
    if not args.demo:
        threads.append(collector_thread(home, config, stop))
    return run(Service(home, args.demo), threads, stop, self_test=args.self_test)


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


COMMANDS = {
    "doctor": cmd_doctor,
    "demo": cmd_demo,
    "write": cmd_write,
    "journal": cmd_journal,
    "hours": cmd_hours,
    "pause": cmd_pause,
    "resume": cmd_resume,
    "forget": cmd_forget,
    "preview": cmd_preview,
    "eval": cmd_eval,
    "start": cmd_start,
}


def main(argv: list[str] | None = None) -> int:
    """Run the munshi command line.

    Args:
        argv: Arguments without the program name; defaults to sys.argv.

    Returns:
        The process exit code.
    """
    logging.basicConfig(level=logging.WARNING, format="munshi: %(message)s")
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except (ConfigError, ValueError) as exc:
        print(f"munshi: {exc}", file=sys.stderr)
        return 2
