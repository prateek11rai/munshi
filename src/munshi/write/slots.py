import re
from dataclasses import dataclass, field
from typing import Any

from munshi.store import Event

EDITORS = {
    "code",
    "visual studio code",
    "cursor",
    "zed",
    "pycharm",
    "intellij idea",
    "webstorm",
    "goland",
    "rustrover",
    "clion",
    "phpstorm",
    "rider",
    "rubymine",
    "android studio",
}
TERMINALS = {"terminal", "iterm2", "ghostty", "wezterm", "alacritty", "kitty", "warp", "hyper"}
BROWSERS = {"google chrome", "safari", "firefox", "arc", "microsoft edge", "brave browser"}
SEGMENT_SPLIT = re.compile(r"\s+[—–\-·|:]\s+")
PATH_RE = re.compile(r"(?:~|/)[\w.\-/]+")
MIN_SECONDS = 5


@dataclass
class Item:
    """One compacted line of a slot: repeats of the same window merged, or a git/file fact."""

    id: str
    kind: str
    start: float
    end: float
    seconds: float = 0.0
    app: str | None = None
    title: str | None = None
    repo: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    event_ids: list[int] = field(default_factory=list)
    project: str | None = None

    def words(self) -> str:
        """Return the text the model's words are checked against.

        Returns:
            Title, repo, file names and commit subjects joined.
        """
        parts = [self.title or "", self.repo or ""]
        parts += [c.get("subject", "") for c in self.detail.get("commits", [])]
        parts += self.detail.get("files", [])
        parts.append(self.detail.get("folder", ""))
        return " ".join(p for p in parts if p)

    def prompt(self) -> dict[str, Any]:
        """Return the item as the model sees it.

        Returns:
            A small JSON-able dict.
        """
        if self.kind == "window":
            out: dict[str, Any] = {"id": self.id, "app": self.app, "title": self.title or ""}
            out["minutes"] = max(1, round(self.seconds / 60))
        elif self.kind == "git":
            out = {"id": self.id, "git_repo": self.repo}
            commits = [c["subject"] for c in self.detail.get("commits", [])]
            if commits:
                out["commits"] = commits
            if self.detail.get("files"):
                out["uncommitted_files"] = self.detail["files"][:10]
        else:
            out = {"id": self.id, "changed_file": self.title, "folder": self.detail.get("folder")}
        if self.project:
            out["project"] = self.project
        return out


@dataclass
class Slot:
    """A finished 15-minute slot, compacted for the writer."""

    start: float
    end: float
    items: list[Item]

    def get(self, item_id: str) -> Item | None:
        """Look up an item by id.

        Args:
            item_id: An id like "e3".

        Returns:
            The item, or None.
        """
        return next((item for item in self.items if item.id == item_id), None)

    def window_items(self) -> list[Item]:
        """Return the items that carry active time.

        Returns:
            Window items in order.
        """
        return [item for item in self.items if item.kind == "window"]


def segments(title: str) -> list[str]:
    """Split a window title into its parts.

    Args:
        title: The title, e.g. "cache.py — tidepool".

    Returns:
        Stripped parts, e.g. ["cache.py", "tidepool"].
    """
    return [part.strip() for part in SEGMENT_SPLIT.split(title) if part.strip()]


def detect_project(item: Item, known: list[str]) -> str | None:
    """Find the project of an item from code alone.

    Uses the repo of git events, the folder of file events, the first or last part
    of editor titles, path parts in terminal titles, and any title part that equals
    a known project.

    Args:
        item: The item.
        known: Known project names (repo names), without "Other".

    Returns:
        The canonical project name, or None.
    """
    by_lower = {name.lower(): name for name in known if name != "Other"}
    if item.repo and item.repo.lower() in by_lower:
        return by_lower[item.repo.lower()]
    folder = item.detail.get("folder")
    if folder and folder.lower() in by_lower:
        return by_lower[folder.lower()]
    title = item.title or ""
    if not title:
        return None
    parts = segments(title)
    app = (item.app or "").lower()
    if app in EDITORS and parts:
        for part in (parts[-1], parts[0]):
            name = re.sub(r"\s*\[.*\]$", "", part).lower()
            if name in by_lower:
                return by_lower[name]
    if app in TERMINALS:
        for path in PATH_RE.findall(title):
            for piece in reversed(path.split("/")):
                if piece.lower() in by_lower:
                    return by_lower[piece.lower()]
    for part in parts:
        if part.lower() in by_lower:
            return by_lower[part.lower()]
    return None


def compact(events: list[Event], start: float, end: float, known: list[str]) -> Slot:
    """Compact a slot's events into items with stable ids.

    Window events are clipped to the slot and merged by (app, title); away time is
    dropped; git and file events become their own items.

    Args:
        events: Events overlapping the slot.
        start: Slot start, epoch seconds.
        end: Slot end, epoch seconds.
        known: Known project names.

    Returns:
        The compacted slot.
    """
    windows: dict[tuple[str | None, str | None], Item] = {}
    items: list[Item] = []
    for event in events:
        if event.kind == "away":
            continue
        lo, hi = max(event.start, start), min(event.end, end)
        if event.kind == "window":
            if hi <= lo:
                continue
            key = (event.app, event.title)
            item = windows.get(key)
            if item is None:
                item = Item("", "window", lo, hi, app=event.app, title=event.title)
                windows[key] = item
                items.append(item)
            item.start, item.end = min(item.start, lo), max(item.end, hi)
            item.seconds += hi - lo
            item.event_ids.append(event.id or 0)
        elif start <= event.start < end:
            items.append(
                Item(
                    "",
                    event.kind,
                    event.start,
                    event.start,
                    title=event.title,
                    repo=event.repo,
                    detail=event.detail,
                    event_ids=[event.id or 0],
                )
            )
    items = [i for i in items if i.kind != "window" or i.seconds >= MIN_SECONDS]
    items.sort(key=lambda item: item.start)
    for n, item in enumerate(items, 1):
        item.id = f"e{n}"
        item.project = detect_project(item, known)
    return Slot(start, end, items)
