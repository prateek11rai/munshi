import json
import re
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


def decode_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from a model reply, including fenced or padded text.

    Args:
        text: Raw model content.

    Returns:
        The decoded object.

    Raises:
        ModelError: If no JSON object can be read.
    """
    blob = text.strip()
    if blob.startswith("```"):
        blob = re.sub(r"^```(?:json)?\s*", "", blob)
        blob = re.sub(r"\s*```$", "", blob)
    try:
        answer = json.loads(blob)
    except ValueError:
        start, end = blob.find("{"), blob.rfind("}")
        if start < 0 or end <= start:
            raise ModelError("model answer is not JSON") from None
        try:
            answer = json.loads(blob[start : end + 1])
        except ValueError as exc:
            raise ModelError("model answer is not JSON") from exc
    if not isinstance(answer, dict):
        raise ModelError("model answer is not a JSON object")
    return answer


def _structured_output_unavailable(exc: BaseException) -> bool:
    """Return True when Ollama refused the `format` field (Homebrew MLX 501)."""
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, urllib.error.HTTPError) and current.code == 501:
            return True
        if isinstance(current, ModelError) and "HTTPError 501" in str(current):
            return True
        current = current.__cause__
    return False


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
        self.structured = True

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
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode()[:300]
            except (OSError, ValueError, AttributeError):
                detail = ""
            label = f"Ollama request failed: HTTPError {exc.code} {detail}".rstrip()
            raise ModelError(label) from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise ModelError(f"Ollama request failed: {type(exc).__name__}") from exc

    def chat_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Ask the model for JSON that follows a schema.

        Tries Ollama's constrained `format` first. Homebrew's MLX build returns
        HTTP 501 ("structured output is unavailable"); then the schema goes in
        the prompt and the reply is parsed in code, and this client stops
        sending `format` for the rest of its life.

        Args:
            system: Instructions.
            user: The data, as text.
            schema: JSON schema passed as Ollama's `format` when the runtime can.

        Returns:
            The decoded answer.

        Raises:
            ModelError: On a network error, timeout or invalid JSON.
        """
        body = {
            "model": self.name,
            "stream": False,
            "think": False,
            "keep_alive": KEEP_ALIVE,
            "options": {"temperature": 0, "num_ctx": NUM_CTX},
        }
        reply = None
        if self.structured:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ]
            try:
                reply = self._request(
                    "/api/chat", {**body, "format": schema, "messages": messages}, self.timeout
                )
            except ModelError as exc:
                if not _structured_output_unavailable(exc):
                    raise
                self.structured = False
        if reply is None:
            messages = [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": (
                        f"{user}\n\nReply with a JSON object only, matching this schema:\n"
                        f"{json.dumps(schema, ensure_ascii=False)}"
                    ),
                },
            ]
            reply = self._request("/api/chat", {**body, "messages": messages}, self.timeout)
        try:
            content = reply["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ModelError("model answer is not JSON") from exc
        if not isinstance(content, str):
            raise ModelError("model answer is not JSON")
        return decode_json_object(content)

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
