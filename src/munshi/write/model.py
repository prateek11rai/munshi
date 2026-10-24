import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any, Protocol

from munshi.config import Config

TIMEOUT = 60
NUM_CTX = 8192
KEEP_ALIVE = "5m"


class ModelError(RuntimeError):
    """The model could not be reached or did not answer valid JSON."""


class JsonModel(Protocol):
    """Anything that answers a chat with JSON matching a schema."""

    name: str

    def chat_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Ask for a JSON answer.

        Args:
            system: Instructions.
            user: The data, as text.
            schema: JSON schema the answer must follow.

        Returns:
            The decoded answer.
        """
        ...


class Ollama:
    """A local Ollama model over HTTP (standard library only), temperature 0."""

    def __init__(
        self,
        url: str,
        name: str,
        timeout: float = TIMEOUT,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        """Create the client.

        Args:
            url: Ollama base URL; check it with Config.check_model_url first.
            name: Model name, e.g. "gemma4:e4b".
            timeout: Seconds per request.
            opener: urllib.request.urlopen or a stand-in for tests.
        """
        self.url = url.rstrip("/")
        self.name = name
        self.timeout = timeout
        self.opener = opener

    @classmethod
    def from_config(cls, config: Config, name: str | None = None) -> "Ollama":
        """Create a client from settings, refusing a remote URL unless allowed.

        Args:
            config: Munshi settings.
            name: Model name overriding the config.

        Returns:
            The client.
        """
        config.check_model_url()
        return cls(config.ollama_url, name or config.model)

    def _request(self, path: str, body: dict[str, Any] | None, timeout: float) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(  # noqa: S310 (URL checked to be local)
            self.url + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST" if data else "GET",
        )
        try:
            with self.opener(request, timeout=timeout) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ModelError(f"Ollama request failed: {type(exc).__name__}") from exc

    def chat_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Ask the model for JSON that follows a schema.

        Args:
            system: Instructions.
            user: The data, as text.
            schema: JSON schema passed as Ollama's `format`.

        Returns:
            The decoded answer.

        Raises:
            ModelError: On a network error, timeout or invalid JSON.
        """
        body = {
            "model": self.name,
            "stream": False,
            "think": False,
            "format": schema,
            "keep_alive": KEEP_ALIVE,
            "options": {"temperature": 0, "num_ctx": NUM_CTX},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        reply = self._request("/api/chat", body, self.timeout)
        try:
            answer = json.loads(reply["message"]["content"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ModelError("model answer is not JSON") from exc
        if not isinstance(answer, dict):
            raise ModelError("model answer is not a JSON object")
        return answer

    def status(self) -> tuple[bool, bool]:
        """Check that Ollama answers and has the model.

        Returns:
            (reachable, model present).
        """
        try:
            tags = self._request("/api/tags", None, 3)
        except ModelError:
            return False, False
        names = {m.get("name") for m in tags.get("models", [])} | {
            m.get("model") for m in tags.get("models", [])
        }
        return True, self.name in names or f"{self.name}:latest" in names
