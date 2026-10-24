import platform
import sys
from pathlib import Path

from munshi.config import ConfigError, demo_home, from_raw, load_config, real_home
from munshi.write.model import Ollama


def doctor(demo_mode: bool) -> int:
    """Print ✓/✗ checks. Reads only booleans and versions; creates nothing.

    Args:
        demo_mode: Check the demo home instead of the real one.

    Returns:
        0.
    """
    home = demo_home() if demo_mode else real_home()
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
        f"config {'at' if config_path.exists() else 'will be at'} {short_path(config_path)}",
    )
    return 0


def short_path(path: Path) -> str:
    """Show a path relative to the home folder.

    Args:
        path: Any path.

    Returns:
        "~/..." when under the home folder, else the full path.
    """
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)
