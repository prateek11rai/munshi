import logging
import os
import threading
from collections.abc import Callable
from typing import Any

from munshi.collect.loop import Window

log = logging.getLogger(__name__)

AX_TIMEOUT = 1.0
MAIN_TIMEOUT = 2.0


class MainThread:
    """Runs a callable on the AppKit main thread and waits for its result.

    `NSWorkspace.frontmostApplication` is only refreshed by the main run loop, and
    pywebview owns that loop. Reading it from the collector thread is a data race
    and can return a stale app, so the read is posted to the main thread instead.
    """

    def __init__(self, post: Callable[[Callable[[], None]], None] | None = None) -> None:
        """Create the caller.

        Args:
            post: Schedules a callable on the main thread; defaults to
                `PyObjCTools.AppHelper.callAfter`.
        """
        if post is None:
            from PyObjCTools import AppHelper

            post = AppHelper.callAfter
        self.post = post

    def call(self, fn: Callable[[], Any], timeout: float = MAIN_TIMEOUT) -> Any:
        """Run `fn` on the main thread.

        Args:
            fn: The callable.
            timeout: Seconds to wait for the main thread.

        Returns:
            Whatever `fn` returns.

        Raises:
            TimeoutError: If the main thread did not run it in time.
        """
        if threading.current_thread() is threading.main_thread():
            return fn()
        done = threading.Event()
        box: dict[str, Any] = {}

        def run() -> None:
            try:
                box["value"] = fn()
            except Exception as exc:  # handed back to the caller's thread
                box["error"] = exc
            finally:
                done.set()

        self.post(run)
        if not done.wait(timeout):
            raise TimeoutError("main thread busy")
        if "error" in box:
            raise box["error"]
        return box.get("value")


class MacWindowSource:
    """Front app (NSWorkspace on the main thread), window title (Accessibility) and idle time."""

    def __init__(
        self,
        main: MainThread | None = None,
        appkit: Any = None,
        ax: Any = None,
        quartz: Any = None,
    ) -> None:
        """Create the source. The framework modules can be replaced in tests.

        Args:
            main: Main-thread caller.
            appkit: The AppKit module.
            ax: The ApplicationServices module.
            quartz: The Quartz module.
        """
        if appkit is None:
            import AppKit as appkit
        if ax is None:
            import ApplicationServices as ax
        if quartz is None:
            import Quartz as quartz
        self.appkit, self.ax, self.quartz = appkit, ax, quartz
        self.main = main or MainThread()
        self.own_pid = os.getpid()

    def trusted(self) -> bool:
        """Tell whether this process has Accessibility permission.

        Returns:
            True when window titles can be read.
        """
        return bool(self.ax.AXIsProcessTrusted())

    def _frontmost(self) -> tuple[str, int] | None:
        app = self.appkit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        return str(app.localizedName() or ""), int(app.processIdentifier())

    def _frontmost_from_windows(self) -> tuple[str, int] | None:
        q = self.quartz
        options = q.kCGWindowListOptionOnScreenOnly | q.kCGWindowListExcludeDesktopElements
        for info in q.CGWindowListCopyWindowInfo(options, q.kCGNullWindowID) or []:
            pid = int(info.get("kCGWindowOwnerPID", 0))
            if info.get("kCGWindowLayer") == 0 and pid != self.own_pid:
                return str(info.get("kCGWindowOwnerName", "")), pid
        return None

    def front_app(self) -> tuple[str, int] | None:
        """Return the front app's name and pid.

        Reads NSWorkspace on the main thread; if the main thread is busy, falls back
        to the window server's on-screen window list (always current, no run loop).

        Returns:
            (name, pid), or None.
        """
        try:
            return self.main.call(self._frontmost)
        except TimeoutError:
            return self._frontmost_from_windows()

    def title(self, pid: int) -> str | None:
        """Read the focused window's title of an app through Accessibility.

        Args:
            pid: The app's process id.

        Returns:
            The title, or None without permission or when the app has no window.
        """
        ax = self.ax
        app = ax.AXUIElementCreateApplication(pid)
        ax.AXUIElementSetMessagingTimeout(app, AX_TIMEOUT)
        err, window = ax.AXUIElementCopyAttributeValue(app, "AXFocusedWindow", None)
        if err != 0 or window is None:
            return None
        err, title = ax.AXUIElementCopyAttributeValue(window, "AXTitle", None)
        if err != 0 or not title:
            return None
        return str(title)

    def front_window(self) -> Window | None:
        """Return the front app and, with Accessibility permission, its window title.

        Returns:
            The window, or None.
        """
        front = self.front_app()
        if front is None or not front[0]:
            return None
        name, pid = front
        title = self.title(pid) if self.trusted() else None
        return Window(app=name, title=title, pid=pid)

    def idle_seconds(self) -> float:
        """Return seconds since the last keyboard, mouse or trackpad input.

        Returns:
            Idle seconds.
        """
        q = self.quartz
        return float(
            q.CGEventSourceSecondsSinceLastEventType(
                q.kCGEventSourceStateCombinedSessionState, q.kCGAnyInputEventType
            )
        )


def accessibility_granted() -> bool:
    """Tell whether this process may read window titles.

    Returns:
        The Accessibility permission flag.
    """
    import ApplicationServices

    return bool(ApplicationServices.AXIsProcessTrusted())


def hide_dock_icon() -> None:
    """Make the app an accessory (no Dock icon). Must run on the main thread."""
    import AppKit

    AppKit.NSApplication.sharedApplication().setActivationPolicy_(
        AppKit.NSApplicationActivationPolicyAccessory
    )


def copy_text(text: str) -> None:
    """Put plain text on the clipboard.

    Args:
        text: The text.
    """
    import AppKit

    board = AppKit.NSPasteboard.generalPasteboard()
    board.clearContents()
    board.setString_forType_(text, AppKit.NSPasteboardTypeString)
