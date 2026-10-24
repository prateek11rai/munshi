import io
import json
import urllib.error

import pytest

from munshi.config import Config, ConfigError
from munshi.write.model import ModelError, Ollama


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_returning(payload, seen):
    def opener(request, timeout):
        seen.append((request, timeout))
        return Response(json.dumps(payload).encode())

    return opener


def test_chat_json_request_shape():
    seen = []
    model = Ollama(
        "http://127.0.0.1:11434/",
        "gemma4:e4b",
        opener=opener_returning({"message": {"content": '{"blocks": []}'}}, seen),
    )
    assert model.chat_json("sys", "user", {"type": "object"}) == {"blocks": []}
    request, timeout = seen[0]
    body = json.loads(request.data)
    assert request.full_url == "http://127.0.0.1:11434/api/chat" and timeout == 60
    assert body["format"] == {"type": "object"} and body["stream"] is False
    assert body["options"] == {"temperature": 0, "num_ctx": 8192}
    assert body["keep_alive"] == "5m" and body["think"] is False


@pytest.mark.parametrize("content", ["not json", "[1, 2]"])
def test_bad_answers_raise(content):
    model = Ollama(
        "http://127.0.0.1:1", "m", opener=opener_returning({"message": {"content": content}}, [])
    )
    with pytest.raises(ModelError):
        model.chat_json("s", "u", {})


def test_network_error_raises():
    def opener(request, timeout):
        raise urllib.error.URLError("refused")

    with pytest.raises(ModelError):
        Ollama("http://127.0.0.1:1", "m", opener=opener).chat_json("s", "u", {})
    assert Ollama("http://127.0.0.1:1", "m", opener=opener).status() == (False, False)


def test_status_finds_model():
    payload = {"models": [{"name": "gemma4:e4b", "model": "gemma4:e4b"}]}
    assert Ollama("http://x", "gemma4:e4b", opener=opener_returning(payload, [])).status() == (
        True,
        True,
    )
    assert Ollama("http://x", "other", opener=opener_returning(payload, [])).status() == (
        True,
        False,
    )


def test_remote_url_refused():
    with pytest.raises(ConfigError):
        Ollama.from_config(Config(ollama_url="http://10.0.0.5:11434"))
