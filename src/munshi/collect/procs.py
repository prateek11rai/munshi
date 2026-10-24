import subprocess
from collections.abc import Callable

from munshi.config import contains_word

Runner = Callable[..., subprocess.CompletedProcess]
PS = "/bin/ps"
PS_TIMEOUT = 2
CACHE_LIMIT = 512


def ps_field(pid: int, field: str, run: Runner = subprocess.run) -> str | None:
    """Read one `ps` column for a process.

    Args:
        pid: The process id.
        field: A `ps -o` keyword, e.g. "command" or "rss,%cpu".
        run: subprocess.run or a stand-in for tests.

    Returns:
        The column text, or None on any error.
    """
    try:
        result = run(
            [PS, "-o", f"{field}=", "-p", str(int(pid))],
            capture_output=True,
            text=True,
            timeout=PS_TIMEOUT,
            check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


class ProcessWords:
    """Tells whether an app was started with a command line holding a blocked word.

    The command line is read once per process and only the yes/no answer is kept;
    a failed read counts as no match and is tried again on the next poll.
    """

    def __init__(self, words: list[str], run: Runner = subprocess.run) -> None:
        """Create the matcher.

        Args:
            words: Lower-cased words; empty turns the check off.
            run: subprocess.run or a stand-in for tests.
        """
        self.words = words
        self.run = run
        self.cache: dict[tuple[int, str], bool] = {}

    def matches(self, pid: int | None, app: str = "") -> bool:
        """Tell whether the process's command line contains a blocked word.

        Args:
            pid: The front app's process id.
            app: The app's name, part of the cache key so a reused pid is read again.

        Returns:
            True when a word appears in the command line.
        """
        if not self.words or pid is None:
            return False
        key = (pid, app)
        if key in self.cache:
            return self.cache[key]
        command = ps_field(pid, "command", self.run)
        if command is None:
            return False
        if len(self.cache) >= CACHE_LIMIT:
            self.cache.clear()
        self.cache[key] = contains_word(command, self.words)
        return self.cache[key]


def usage(pid: int, run: Runner = subprocess.run) -> tuple[float, float] | None:
    """Read a process's resident memory and CPU share.

    Args:
        pid: The process id.
        run: subprocess.run or a stand-in for tests.

    Returns:
        (RSS in MB, CPU percent), or None when `ps` fails.
    """
    text = ps_field(pid, "rss,%cpu", run)
    parts = (text or "").split()
    try:
        rss_kb, cpu = float(parts[0]), float(parts[1].replace(",", "."))
    except (IndexError, ValueError):
        return None
    return round(rss_kb / 1024, 1), cpu
