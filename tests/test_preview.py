import json
import socket
import threading
import urllib.error
import urllib.request
from datetime import date

import pytest

from munshi import demo
from munshi.ui.preview import serve
from munshi.ui.service import Service


@pytest.fixture
def server(tmp_path):
    demo.load(tmp_path, date.today())
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = serve(Service(tmp_path, True, model=lambda c: None), port)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield port
    srv.shutdown()
    srv.server_close()


def post(port, name, args=(), headers=None):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/{name}",
        data=json.dumps({"args": list(args)}).encode(),
        headers=headers or {"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def test_page_and_files(server):
    with urllib.request.urlopen(f"http://127.0.0.1:{server}/", timeout=5) as r:
        page = r.read().decode()
        csp = r.headers["Content-Security-Policy"]
    assert "window.MUNSHI_PREVIEW = true" in page and '<script src="card.js">' in page
    assert "nonce-" in csp and "unsafe-inline" not in csp
    for name in ("card.js", "theme.css", "munshi.svg"):
        with urllib.request.urlopen(f"http://127.0.0.1:{server}/{name}", timeout=5) as r:
            assert r.status == 200
    with pytest.raises(urllib.error.HTTPError):
        urllib.request.urlopen(f"http://127.0.0.1:{server}/../pyproject.toml", timeout=5)


def test_api_actions(server):
    assert post(server, "card")["where"]["updated"] == "updated 6 min ago"
    assert post(server, "pause", ["60"])["paused"]["on"]
    assert not post(server, "resume")["paused"]["on"]
    assert post(server, "copy_timesheet", ["yesterday"])["text"].startswith("tidepool · 3.5 h")
    assert "Finder" in post(server, "open_journal")["note"]
    with pytest.raises(urllib.error.HTTPError) as err:
        post(server, "drop_tables")
    assert err.value.code == 400


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Type": "text/plain"},
        {"Content-Type": "application/json", "Origin": "https://evil.example"},
        {"Content-Type": "application/json", "Host": "evil.example:8765"},
    ],
)
def test_cross_site_requests_refused(server, headers):
    with pytest.raises(urllib.error.HTTPError) as err:
        post(server, "forget", headers=headers)
    assert err.value.code == 403
