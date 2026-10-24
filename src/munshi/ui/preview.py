import json
import logging
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from munshi.ui.assets import TYPES, read
from munshi.ui.service import Service

log = logging.getLogger(__name__)

HOST = "127.0.0.1"
PORT = 8765
FILES = {"/card.js", "/theme.css", "/munshi.svg"}
MAX_BODY = 4096


def call(service: Service, name: str, args: list[Any]) -> dict[str, Any]:
    """Run one card action for the preview.

    Args:
        service: The card service.
        name: Action name, as card.js calls it.
        args: Positional arguments.

    Returns:
        The JSON answer.

    Raises:
        KeyError: For an unknown action.
    """
    if name == "card":
        return service.card()
    if name == "refresh":
        return service.refresh()
    if name == "pause":
        return service.pause(str(args[0]))
    if name == "resume":
        return service.resume()
    if name == "forget":
        return service.forget()
    if name == "set_hours_view":
        return service.set_hours_view(str(args[0]))
    if name == "copy_timesheet":
        text = service.timesheet(str(args[0]))
        return {"text": text, "empty": not text}
    if name == "open_journal":
        return {"note": "In the app this opens the journal folder in Finder."}
    raise KeyError(name)


def make_handler(service: Service, port: int) -> type[BaseHTTPRequestHandler]:
    """Build the request handler bound to a service.

    Args:
        service: The card service.
        port: The port served, for the Host check.

    Returns:
        The handler class.
    """
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        server_version = "munshi"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """Keep request logs out of the terminal."""

        def _send(self, status: int, body: bytes, kind: str, nonce: str = "") -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            script = f"'self' 'nonce-{nonce}'" if nonce else "'self'"
            self.send_header(
                "Content-Security-Policy",
                f"default-src 'self'; img-src 'self' data:; style-src 'self'; script-src {script}",
            )
            self.end_headers()
            self.wfile.write(body)

        def _host_ok(self) -> bool:
            return self.headers.get("Host", "") in allowed_hosts

        def do_GET(self) -> None:  # noqa: N802
            """Serve the card page and its files."""
            if not self._host_ok():
                self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
                return
            path = self.path.split("?", 1)[0]
            if path in {"/", "/card.html"}:
                nonce = secrets.token_urlsafe(16)
                flag = f'<script nonce="{nonce}">window.MUNSHI_PREVIEW = true;</script>'
                page = read("card.html").replace("</head>", flag + "\n</head>", 1)
                self._send(HTTPStatus.OK, page.encode(), TYPES[".html"], nonce)
            elif path in FILES:
                name = path[1:]
                self._send(HTTPStatus.OK, read(name).encode(), TYPES["." + name.rsplit(".", 1)[1]])
            else:
                self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            """Run a card action; JSON only, same origin only."""
            origin = self.headers.get("Origin")
            if (
                not self._host_ok()
                or (origin and origin.split("//", 1)[-1] not in allowed_hosts)
                or self.headers.get("Content-Type", "").split(";")[0] != "application/json"
                or not self.path.startswith("/api/")
            ):
                self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
                return
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > MAX_BODY:
                self._send(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, b"too large", "text/plain")
                return
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
                args = body.get("args", []) if isinstance(body, dict) else []
                answer = call(service, self.path[len("/api/") :], list(args))
            except (KeyError, IndexError, ValueError, TypeError):
                self._send(HTTPStatus.BAD_REQUEST, b'{"error": "bad request"}', "application/json")
                return
            self._send(HTTPStatus.OK, json.dumps(answer).encode(), "application/json")

    return Handler


def serve(service: Service, port: int = PORT) -> ThreadingHTTPServer:
    """Create the preview server on 127.0.0.1.

    Args:
        service: The card service.
        port: TCP port.

    Returns:
        The server (call serve_forever on it).
    """
    return ThreadingHTTPServer((HOST, port), make_handler(service, port))
