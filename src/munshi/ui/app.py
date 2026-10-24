import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from munshi.ui.assets import inline
from munshi.ui.service import Service

log = logging.getLogger(__name__)

BUDDY = 88
CARD_W, CARD_H = 380, 560
MARGIN = 8
CLICK_AFTER_MOVE = 0.4
LAYOUT_JS = """(function () {
  var main = document.querySelector('main');
  main.scrollTop = main.scrollHeight;
  var box = function (s) { return document.querySelector(s).getBoundingClientRect(); };
  return {height: window.innerHeight, main: box('main').bottom, copy: box('#copy').bottom,
          footer_top: box('footer').top, footer_bottom: box('footer').bottom};
})()"""


class Api:
    """Methods the buddy and card call from JavaScript (`window.pywebview.api.*`)."""

    def __init__(self, service: Service, ui: "Windows") -> None:
        """Create the bridge.

        Args:
            service: The card service.
            ui: The windows.
        """
        self._service = service
        self._ui = ui

    def card(self) -> dict[str, Any]:
        """Return the card data.

        Returns:
            The card.
        """
        return self._service.card()

    def refresh(self) -> dict[str, Any]:
        """Run the writer now.

        Returns:
            The card with a message.
        """
        return self._service.refresh()

    def pause(self, choice: str) -> dict[str, Any]:
        """Pause recording.

        Args:
            choice: "30", "60" or "until".

        Returns:
            The card.
        """
        card = self._service.pause(choice)
        self._ui.show_paused(True)
        return card

    def resume(self) -> dict[str, Any]:
        """Resume recording.

        Returns:
            The card.
        """
        card = self._service.resume()
        self._ui.show_paused(False)
        return card

    def forget(self) -> dict[str, Any]:
        """Forget the last hour.

        Returns:
            The card.
        """
        return self._service.forget()

    def set_hours_view(self, view: str) -> dict[str, Any]:
        """Remember the hours tab.

        Args:
            view: "today" or "yesterday".

        Returns:
            The card.
        """
        return self._service.set_hours_view(view)

    def copy_timesheet(self, view: str) -> dict[str, Any]:
        """Copy timesheet lines to the clipboard.

        Args:
            view: "today" or "yesterday".

        Returns:
            {"copied": bool, "empty": bool}.
        """
        from munshi.collect.macos import copy_text

        text = self._service.timesheet(view)
        if text:
            copy_text(text)
        return {"copied": bool(text), "empty": not text}

    def open_journal(self) -> dict[str, Any]:
        """Open the journal folder in Finder.

        Returns:
            {"note": ""}.
        """
        subprocess.run(["/usr/bin/open", str(self._service.journal_dir())], check=False)  # noqa: S603
        return {"note": ""}

    def toggle_card(self) -> None:
        """Show or hide the card next to the buddy."""
        self._ui.toggle_card()

    def hide_card(self) -> None:
        """Hide the card."""
        self._ui.hide_card()

    def buddy_moved(self) -> None:
        """Save the buddy's position after a drag."""
        self._ui.save_position()

    def buddy_state(self) -> dict[str, bool]:
        """Tell the buddy whether to look paused.

        Returns:
            {"paused": bool}.
        """
        return {"paused": self._service.paused()}


class Windows:
    """The buddy and card windows."""

    def __init__(self, service: Service, positions: Any) -> None:
        """Create the windows (not shown until `webview.start`).

        Args:
            service: The card service.
            positions: Object with `get(key)` / `set(key, value)` for the saved position.
        """
        import webview

        self.webview = webview
        self.service = service
        self.positions = positions
        self.card_visible = False
        self.moved_at = 0.0
        self.api = Api(service, self)
        screen = webview.screens[0]
        x, y = positions.get("buddy_pos") or (
            screen.width - BUDDY - 24,
            screen.height - BUDDY - 96,
        )
        self.buddy = webview.create_window(
            "Munshi",
            html=inline("buddy.html"),
            js_api=self.api,
            width=BUDDY,
            height=BUDDY,
            x=int(x),
            y=int(y),
            resizable=False,
            frameless=True,
            easy_drag=True,
            shadow=False,
            on_top=True,
            transparent=True,
            background_color="#000000",
        )
        self.card = webview.create_window(
            "Munshi card",
            html=inline("card.html"),
            js_api=self.api,
            width=CARD_W,
            height=CARD_H,
            hidden=True,
            resizable=False,
            frameless=True,
            easy_drag=False,
            on_top=True,
            background_color="#17181b",
        )
        self.buddy.events.moved += self._on_moved

    def _on_moved(self, x: int, y: int) -> None:
        self.moved_at = time.monotonic()
        self.positions.set("buddy_pos", [int(x), int(y)])

    def save_position(self) -> None:
        """Store the buddy's current position."""
        self.moved_at = time.monotonic()
        self.positions.set("buddy_pos", [self.buddy.x, self.buddy.y])

    def card_position(self) -> tuple[int, int]:
        """Place the card left of the buddy, or right when there is no room.

        Returns:
            (x, y) in screen points, top-left origin.
        """
        screen = self.webview.screens[0]
        bx, by = self.buddy.x, self.buddy.y
        x = bx - CARD_W - MARGIN
        if x < 0:
            x = bx + BUDDY + MARGIN
        y = min(max(0, by + BUDDY - CARD_H), max(0, screen.height - CARD_H))
        return x, y

    def toggle_card(self) -> None:
        """Show the card beside the buddy, or hide it."""
        if time.monotonic() - self.moved_at < CLICK_AFTER_MOVE:
            return
        if self.card_visible:
            self.hide_card()
            return
        self.card.move(*self.card_position())
        self.card.show()
        self.card_visible = True
        self.card.evaluate_js("window.munshiCard && window.munshiCard.reload()")

    def hide_card(self) -> None:
        """Hide the card."""
        self.card.hide()
        self.card_visible = False

    def show_paused(self, on: bool) -> None:
        """Switch the buddy's look.

        Args:
            on: True for the paused look.
        """
        self.buddy.evaluate_js(f"window.setPaused && window.setPaused({str(on).lower()})")


class StateFile:
    """Saved window positions, kept in the store's state table."""

    def __init__(self, home: Path) -> None:
        """Bind to a data home.

        Args:
            home: Data home.
        """
        self.home = home

    def get(self, key: str) -> Any:
        """Read a saved value.

        Args:
            key: State key.

        Returns:
            The value, or None.
        """
        from munshi.store import Store

        store = Store.at_home(self.home)
        try:
            return store.get(key)
        finally:
            store.close()

    def set(self, key: str, value: Any) -> None:
        """Save a value.

        Args:
            key: State key.
            value: JSON-able value.
        """
        from munshi.store import Store

        store = Store.at_home(self.home)
        try:
            store.set(key, value)
        finally:
            store.close()


def run(
    service: Service,
    background: list[threading.Thread],
    stop: threading.Event,
    self_test: bool = False,
    show_card: bool = False,
) -> int:
    """Show the buddy and card on the main thread; background threads run alongside.

    Args:
        service: The card service.
        background: Collector and writer threads, started once the GUI is up.
        stop: Set when the windows close, to stop the threads.
        self_test: Check the JS bridge from the card window, print the result and quit.
        show_card: Open the card once it has loaded (for a window screenshot).

    Returns:
        Exit code.
    """
    import webview
    from PyObjCTools import AppHelper

    from munshi.collect.macos import hide_dock_icon

    windows = Windows(service, StateFile(service.home))
    outcome = {"code": 0}

    def started() -> None:
        AppHelper.callAfter(hide_dock_icon)
        for thread in background:
            thread.start()
        if show_card and windows.card.events.loaded.wait(15):
            windows.toggle_card()
        if self_test:
            outcome["code"] = _self_test(windows)
            for window in (windows.card, windows.buddy):
                window.destroy()

    webview.start(started, private_mode=True)
    stop.set()
    return outcome["code"]


def _wait(check: Any, seconds: float = 5.0) -> Any:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if value := check():
            return value
        time.sleep(0.1)
    return None


def _self_test(windows: Windows) -> int:
    """Drive the real windows through the JS bridge and report; no screenshots."""
    import AppKit
    from PyObjCTools import AppHelper

    windows.card.events.loaded.wait(15)
    windows.buddy.events.loaded.wait(15)
    checks: dict[str, bool] = {}
    windows.card.evaluate_js(
        "window.pywebview.api.card().then(function (c) { window.__munshiTest ="
        " [c.today.length, c.where.text.length, c.hours.today.rows.length]; }); 1"
    )
    result = _wait(lambda: windows.card.evaluate_js("window.__munshiTest || null"))
    checks["card data through js_api"] = bool(result) and all(n > 0 for n in result)
    windows.buddy.evaluate_js("window.pywebview.api.toggle_card(); 1")
    checks["click opens card"] = bool(_wait(lambda: windows.card_visible))
    checks["card filled"] = bool(
        _wait(lambda: windows.card.evaluate_js("document.getElementById('where-text').textContent"))
    )
    layout = windows.card.evaluate_js(LAYOUT_JS) or {}
    print(f"self-test: card layout {layout}")
    checks["card content scrolls clear of the footer"] = bool(layout) and (
        layout["copy"] <= layout["footer_top"] + 0.5
        and layout["main"] <= layout["footer_top"] + 0.5
        and layout["footer_bottom"] <= layout["height"] + 0.5
    )
    windows.card.evaluate_js(
        "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'})); 1"
    )
    checks["Esc hides card"] = bool(_wait(lambda: not windows.card_visible))
    start = windows.buddy.x, windows.buddy.y
    windows.buddy.move(start[0] - 40, start[1] - 30)
    saved = _wait(lambda: windows.positions.get("buddy_pos") != list(start)
                  and windows.positions.get("buddy_pos"))  # fmt: skip
    checks["drag saves position"] = bool(saved)
    windows.buddy.evaluate_js("window.pywebview.api.toggle_card(); 1")
    time.sleep(0.2)
    checks["click right after a drag is ignored"] = not windows.card_visible
    policy: dict[str, int] = {}
    AppHelper.callAfter(
        lambda: policy.update(p=AppKit.NSApplication.sharedApplication().activationPolicy())
    )
    _wait(lambda: "p" in policy)
    checks["no Dock icon (accessory policy)"] = (
        policy.get("p") == AppKit.NSApplicationActivationPolicyAccessory
    )
    windows.buddy.move(*start)
    for name, ok in checks.items():
        print(f"self-test: {'✓' if ok else '✗'} {name}")
    return 0 if all(checks.values()) else 1
