import sys
import threading
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="macOS source")

from munshi.collect.macos import MacWindowSource, MainThread  # noqa: E402


class FakeWorkspace:
    """NSWorkspace stand-in: frontmostApplication only refreshes on the main run loop."""

    def __init__(self):
        self.actual = ("Code", 11)
        self.cached = ("Code", 11)

    def pump(self):
        assert threading.current_thread() is threading.main_thread()
        self.cached = self.actual

    def frontmostApplication(self):  # noqa: N802
        name, pid = self.cached
        return SimpleNamespace(localizedName=lambda: name, processIdentifier=lambda: pid)


class MainLoop:
    """Runs posted blocks on the real main thread, pumping the workspace first."""

    def __init__(self, workspace):
        self.workspace = workspace
        self.queue = []
        self.lock = threading.Lock()

    def post(self, fn):
        with self.lock:
            self.queue.append(fn)

    def drain_until(self, done):
        while not done.is_set():
            with self.lock:
                jobs, self.queue = self.queue, []
            for job in jobs:
                self.workspace.pump()
                job()
            done.wait(0.005)


def fake_modules(workspace, trusted=True, titles=None, windows=None):
    titles = titles or {}

    def copy_attr(element, attr, _):
        if attr == "AXFocusedWindow":
            return (0, ("win", element)) if element in titles else (-25212, None)
        return (0, titles[element[1]])

    appkit = SimpleNamespace(NSWorkspace=SimpleNamespace(sharedWorkspace=lambda: workspace))
    ax = SimpleNamespace(
        AXIsProcessTrusted=lambda: trusted,
        AXUIElementCreateApplication=lambda pid: pid,
        AXUIElementSetMessagingTimeout=lambda el, t: 0,
        AXUIElementCopyAttributeValue=copy_attr,
    )
    quartz = SimpleNamespace(
        kCGWindowListOptionOnScreenOnly=1,
        kCGWindowListExcludeDesktopElements=16,
        kCGNullWindowID=0,
        kCGEventSourceStateCombinedSessionState=0,
        kCGAnyInputEventType=0xFFFFFFFF,
        CGWindowListCopyWindowInfo=lambda opts, wid: windows or [],
        CGEventSourceSecondsSinceLastEventType=lambda state, kind: 42.0,
    )
    return appkit, ax, quartz


def test_main_thread_read_is_fresh_while_direct_background_read_is_stale():
    workspace = FakeWorkspace()
    loop = MainLoop(workspace)
    appkit, ax, quartz = fake_modules(workspace)
    source = MacWindowSource(MainThread(loop.post), appkit, ax, quartz)
    workspace.actual = ("Google Chrome", 22)
    out = {}
    done = threading.Event()

    def collector_thread():
        out["direct"] = source._frontmost()
        out["via_main"] = source.front_app()
        done.set()

    threading.Thread(target=collector_thread).start()
    loop.drain_until(done)
    assert out["direct"] == ("Code", 11)
    assert out["via_main"] == ("Google Chrome", 22)


def test_busy_main_thread_falls_back_to_window_list():
    workspace = FakeWorkspace()
    windows = [
        {"kCGWindowLayer": 25, "kCGWindowOwnerPID": 5, "kCGWindowOwnerName": "Dock"},
        {"kCGWindowLayer": 0, "kCGWindowOwnerPID": 22, "kCGWindowOwnerName": "Google Chrome"},
    ]
    appkit, ax, quartz = fake_modules(workspace, windows=windows)
    source = MacWindowSource(MainThread(lambda fn: None), appkit, ax, quartz)
    out = {}
    t = threading.Thread(target=lambda: out.update(app=source.front_app()))
    t.start()
    t.join(5)
    assert out["app"] == ("Google Chrome", 22)


def test_title_needs_accessibility():
    workspace = FakeWorkspace()
    appkit, ax, quartz = fake_modules(workspace, trusted=True, titles={11: "cache.py — tidepool"})
    source = MacWindowSource(MainThread(lambda fn: fn()), appkit, ax, quartz)
    assert source.front_window().title == "cache.py — tidepool"
    assert source.idle_seconds() == 42.0

    appkit, ax, quartz = fake_modules(workspace, trusted=False, titles={11: "secret"})
    source = MacWindowSource(MainThread(lambda fn: fn()), appkit, ax, quartz)
    win = source.front_window()
    assert (win.app, win.title) == ("Code", None)


def test_app_without_window_has_no_title():
    workspace = FakeWorkspace()
    appkit, ax, quartz = fake_modules(workspace, trusted=True, titles={})
    source = MacWindowSource(MainThread(lambda fn: fn()), appkit, ax, quartz)
    assert source.front_window().title is None


def test_front_window_carries_the_bundle_id():
    workspace = FakeWorkspace()
    appkit, ax, quartz = fake_modules(workspace, trusted=False)
    source = MacWindowSource(MainThread(lambda fn: fn()), appkit, ax, quartz)
    assert source.front_window().bundle is None
    running = SimpleNamespace(bundleIdentifier=lambda: "org.mozilla.firefox")
    appkit.NSRunningApplication = SimpleNamespace(
        runningApplicationWithProcessIdentifier_=lambda pid: running if pid == 11 else None
    )
    assert source.front_window().bundle == "org.mozilla.firefox"
    assert source.bundle(99) is None
