import re
import subprocess
from collections.abc import Callable

from munshi.config import contains_word

Runner = Callable[..., subprocess.CompletedProcess]
PS = "/bin/ps"
LSOF = "/usr/sbin/lsof"
PS_TIMEOUT = 2
LSOF_TIMEOUT = 5
CACHE_LIMIT = 512
FIREFOX_BUNDLES = {
    "org.mozilla.firefox",
    "org.mozilla.firefoxdeveloperedition",
    "org.mozilla.nightly",
}
PROFILE_RE = re.compile(r"/Firefox/Profiles/([^/]+)/")


def ps_field(pid: int, *fields: str, run: Runner = subprocess.run) -> str | None:
    """Read `ps` columns for a process, without headers.

    Args:
        pid: The process id.
        *fields: `ps -o` keywords, e.g. "command", or "rss" and "%cpu".
        run: subprocess.run or a stand-in for tests.

    Returns:
        The columns' text, or None on any error.
    """
    columns = [arg for field in fields for arg in ("-o", f"{field}=")]
    try:
        result = run(
            [PS, *columns, "-p", str(int(pid))],
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


def is_firefox(app: str, bundle: str | None) -> bool:
    """Tell whether an app is Firefox (any channel).

    Args:
        app: The app's name.
        bundle: Its bundle identifier, when known.

    Returns:
        True for Firefox.
    """
    if bundle:
        return bundle in FIREFOX_BUNDLES
    return app.lower().startswith("firefox")


def profile_folders(pid: int, run: Runner = subprocess.run) -> set[str] | None:
    """Return the Firefox profile folder names a process holds open.

    Args:
        pid: The Firefox process id.
        run: subprocess.run or a stand-in for tests.

    Returns:
        Folder names under `.../Firefox/Profiles/`, or None when `lsof` fails or
        shows none (e.g. the profile is not open yet).
    """
    try:
        result = run(
            [LSOF, "-w", "-a", "-p", str(int(pid)), "-Fn"],
            capture_output=True,
            text=True,
            timeout=LSOF_TIMEOUT,
            check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    folders = {
        match.group(1)
        for line in result.stdout.splitlines()
        if line.startswith("n") and (match := PROFILE_RE.search(line))
    }
    return folders or None


class ProcessWords:
    """Tells whether an app's process holds a blocked word.

    The word may be in its command line or, for Firefox, in the name of the profile
    folder it holds open. Each process is read once and only the yes/no answer is
    kept; a failed read counts as no match and is tried again on the next poll.
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

    def matches(self, pid: int | None, app: str = "", bundle: str | None = None) -> bool:
        """Tell whether the process holds a blocked word.

        Args:
            pid: The front app's process id.
            app: The app's name, part of the cache key so a reused pid is read again.
            bundle: The app's bundle identifier, to recognise Firefox.

        Returns:
            True when a word appears in the command line or the Firefox profile folder.
        """
        if not self.words or pid is None:
            return False
        key = (pid, app)
        if key in self.cache:
            return self.cache[key]
        command = ps_field(pid, "command", run=self.run)
        if command is None:
            return False
        hit = contains_word(command, self.words)
        if not hit and is_firefox(app, bundle):
            folders = profile_folders(pid, self.run)
            if folders is None:
                return False
            hit = any(contains_word(folder, self.words) for folder in folders)
        if len(self.cache) >= CACHE_LIMIT:
            self.cache.clear()
        self.cache[key] = hit
        return hit


def usage(pid: int, run: Runner = subprocess.run) -> tuple[float, float] | None:
    """Read a process's resident memory and CPU share.

    Args:
        pid: The process id.
        run: subprocess.run or a stand-in for tests.

    Returns:
        (RSS in MB, CPU percent), or None when `ps` fails.
    """
    text = ps_field(pid, "rss", "%cpu", run=run)
    parts = (text or "").split()
    try:
        rss_kb, cpu = float(parts[0]), float(parts[1].replace(",", "."))
    except (IndexError, ValueError):
        return None
    return round(rss_kb / 1024, 1), cpu
