import os
import tomllib
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

DEFAULT_MODEL = "gemma4:e4b"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
BUILTIN_IGNORE = (
    "1Password",
    "Bitwarden",
    "Keychain Access",
    "System Settings",
    "loginwindow",
    "ScreenSaverEngine",
)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

CONFIG_TEMPLATE = """\
# Munshi settings. Everything stays on this computer.

# Any model you have pulled in Ollama (`ollama list`).
model = "gemma4:e4b"

# Must be this computer unless allow_remote_model = true is set on purpose.
ollama_url = "http://127.0.0.1:11434"
allow_remote_model = false

# Folders whose git repos and files Munshi may look at. Empty means none.
allowed_roots = []            # e.g. ["~/code", "~/Documents/notes"]

# Raw window events are deleted after this many days. Blocks, notes,
# the journal and hours are kept.
keep_events_days = 14

# A window whose title (or app name) contains one of these words is not
# recorded at all; git and file names containing one are dropped too.
ignore_title_words = []       # e.g. ["acme"]

# A window whose app was started with a command line containing one of these
# words is not recorded at all (e.g. a browser profile path).
ignore_process_words = []     # e.g. ["acme"]

[apps]
mode = "all"                  # or "only": record just the apps listed in `only`
only = []
ignore = []                   # added to the built-in list (password managers, lock screen, ...)
"""


class ConfigError(ValueError):
    """Raised when the config file holds a value Munshi refuses to use."""


def contains_word(text: str | None, words: list[str]) -> bool:
    """Tell whether a text contains any of the words, ignoring case.

    Args:
        text: The text, or None.
        words: Lower-cased words.

    Returns:
        True when one of the words appears anywhere in the text.
    """
    lowered = (text or "").lower()
    return bool(lowered) and any(word in lowered for word in words)


class AppsConfig(BaseModel):
    """Which apps are recorded.

    Attributes:
        mode: "all" records every app except ignored ones; "only" records just `only`.
        only: App names recorded in "only" mode.
        ignore: App names never recorded, on top of the built-in list.
    """

    model_config = ConfigDict(extra="forbid")

    mode: str = "all"
    only: list[str] = Field(default_factory=list)
    ignore: list[str] = Field(default_factory=list)

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, value: str) -> str:
        if value not in {"all", "only"}:
            raise ValueError('apps.mode must be "all" or "only"')
        return value

    def ignored(self) -> set[str]:
        """Return every ignored app name, built-in ones included.

        Returns:
            Lower-cased app names.
        """
        return {name.lower() for name in (*BUILTIN_IGNORE, *self.ignore)}

    def records(self, app: str) -> bool:
        """Tell whether an app may be recorded.

        Args:
            app: The app's display name.

        Returns:
            True when the app is neither ignored nor left out by "only" mode.
        """
        name = app.lower()
        if name in self.ignored():
            return False
        if self.mode == "only":
            return name in {n.lower() for n in self.only}
        return True


class Config(BaseModel):
    """Munshi settings read from `<home>/config.toml` plus env overrides.

    Attributes:
        model: Ollama model name.
        ollama_url: Base URL of the Ollama server.
        allow_remote_model: Allow a non-local Ollama URL.
        allowed_roots: Folders scanned for git repos and changed files.
        keep_events_days: Days raw events are kept.
        ignore_title_words: Words that keep a window (or git/file name) out of the record.
        ignore_process_words: Words in an app's command line that keep its windows out.
        apps: App recording rules.
    """

    model_config = ConfigDict(extra="forbid")

    model: str = DEFAULT_MODEL
    ollama_url: str = DEFAULT_OLLAMA_URL
    allow_remote_model: bool = False
    allowed_roots: list[str] = Field(default_factory=list)
    keep_events_days: int = Field(default=14, ge=1)
    ignore_title_words: list[str] = Field(default_factory=list)
    ignore_process_words: list[str] = Field(default_factory=list)
    apps: AppsConfig = Field(default_factory=AppsConfig)

    @field_validator("ignore_title_words", "ignore_process_words")
    @classmethod
    def _clean_words(cls, value: list[str]) -> list[str]:
        return sorted({word.strip().lower() for word in value if word.strip()})

    def roots(self) -> list[Path]:
        """Return the allowed roots as absolute paths.

        Returns:
            Expanded, resolved paths in config order.
        """
        return [Path(root).expanduser().resolve() for root in self.allowed_roots]

    def check_model_url(self) -> None:
        """Refuse a remote Ollama URL unless it was allowed on purpose.

        Raises:
            ConfigError: If the URL is not local and `allow_remote_model` is false.
        """
        parsed = urlparse(self.ollama_url)
        if parsed.scheme not in {"http", "https"}:
            raise ConfigError("ollama_url must start with http:// or https://")
        if parsed.hostname not in LOCAL_HOSTS and not self.allow_remote_model:
            raise ConfigError(
                "ollama_url points away from this computer; set allow_remote_model = true "
                "if you really mean it"
            )


def real_home() -> Path:
    """Return the real data home (`MUNSHI_HOME` or `~/.munshi`).

    Returns:
        The path; it may not exist yet.
    """
    return Path(os.environ.get("MUNSHI_HOME") or "~/.munshi").expanduser()


def demo_home() -> Path:
    """Return the demo home, `./.data/demo` under the current folder.

    Returns:
        The absolute path; it may not exist yet.
    """
    return (Path.cwd() / ".data" / "demo").resolve()


def ensure_home(home: Path) -> Path:
    """Create the home folder (mode 700) and a commented config file if missing.

    Args:
        home: The data home.

    Returns:
        The path of the config file.
    """
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    home.chmod(0o700)
    config_path = home / "config.toml"
    if not config_path.exists():
        config_path.write_text(CONFIG_TEMPLATE)
        config_path.chmod(0o600)
    return config_path


def load_config(home: Path) -> Config:
    """Load `<home>/config.toml` and apply env overrides.

    Args:
        home: The data home; created with a default config if missing.

    Returns:
        The validated config.

    Raises:
        ConfigError: If the file is not valid TOML or a value is refused.
    """
    path = ensure_home(home)
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"config.toml is not valid TOML: {exc}") from exc
    return from_raw(raw)


def from_raw(raw: dict) -> Config:
    """Validate settings after applying env overrides.

    Args:
        raw: Settings as read from TOML (may be empty).

    Returns:
        The validated config.

    Raises:
        ConfigError: If a value is refused.
    """
    raw = dict(raw)
    if model := os.environ.get("MUNSHI_MODEL"):
        raw["model"] = model
    if url := os.environ.get("MUNSHI_OLLAMA_URL"):
        raw["ollama_url"] = url
    try:
        config = Config.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"config.toml has a bad value: {describe(exc)}") from None
    config.check_model_url()
    return config


def describe(exc: ValidationError) -> str:
    """Name the bad settings without repeating their values (they may be private).

    Args:
        exc: The validation error.

    Returns:
        E.g. "apps.mode: Value error, apps.mode must be "all" or "only"".
    """
    parts = []
    for error in exc.errors():
        where = ".".join(str(part) for part in error["loc"]) or "config"
        parts.append(f"{where}: {error['msg']}")
    return "; ".join(parts)
