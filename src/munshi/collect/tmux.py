import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

Runner = Callable[..., subprocess.CompletedProcess]
TMUX_TIMEOUT = 1
MAX_COMMAND = 32


def bare_title(title: str | None) -> bool:
    """Tell whether a terminal's title says nothing beyond "tmux".

    A plain shell tab is titled by its shell or folder, so only an empty title or
    tmux's own name sends the collector to ask tmux.

    Args:
        title: The terminal window's title.

    Returns:
        True for an empty title or one that is just tmux.
    """
    text = (title or "").strip().lower()
    return not text or text == "tmux" or text.startswith("tmux ")


def repo_name(path: Path, roots: list[Path]) -> tuple[bool, str | None]:
    """Find the git repo holding a folder, only inside the allowed roots.

    Args:
        path: An absolute folder.
        roots: Allowed roots, resolved.

    Returns:
        (inside a root, the repo folder's name or None).
    """
    root = next((r for r in roots if path.is_relative_to(r)), None)
    if root is None:
        return False, None
    for folder in (path, *path.parents):
        if (folder / ".git").exists():
            return True, folder.name
        if folder == root:
            break
    return True, None


class TmuxPane:
    """Names what the active tmux pane is doing: its command and repo, never its path."""

    def __init__(
        self, roots: list[Path], run: Runner = subprocess.run, tmux: str | None = None
    ) -> None:
        """Create the reader.

        Args:
            roots: Allowed roots, resolved; outside them nothing is reported.
            run: subprocess.run or a stand-in for tests.
            tmux: Path of the tmux binary; found on PATH when None.
        """
        self.roots = roots
        self.run = run
        self.tmux = tmux if tmux is not None else shutil.which("tmux")

    def _tmux(self, *args: str) -> str | None:
        try:
            result = self.run(
                [self.tmux, *args],
                capture_output=True,
                text=True,
                timeout=TMUX_TIMEOUT,
                check=False,
            )
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
        return result.stdout if result.returncode == 0 else None

    def context(self) -> str | None:
        """Describe the active pane of the most recently used tmux client.

        Returns:
            "<command> — <repo>", or "<command>" outside a repo, when the pane's folder
            is inside an allowed root; None otherwise or on any error.
        """
        if not self.tmux or not self.roots:
            return None
        clients = self._tmux("list-clients", "-F", "#{client_activity}\t#{session_name}")
        rows = []
        for line in (clients or "").splitlines():
            activity, _, session = line.partition("\t")
            if activity.isdigit() and session:
                rows.append((int(activity), session))
        if not rows:
            return None
        session = max(rows)[1]
        out = self._tmux(
            "display-message", "-p", "-t", f"={session}:",
            "#{pane_current_path}\t#{pane_current_command}",
        )  # fmt: skip
        path, sep, command = (out or "").rstrip("\n").partition("\t")
        if not sep or not path.startswith("/"):
            return None
        inside, repo = repo_name(Path(path).resolve(), self.roots)
        if not inside:
            return None
        parts = [part for part in (command.strip()[:MAX_COMMAND], repo) if part]
        return " — ".join(parts) or None
