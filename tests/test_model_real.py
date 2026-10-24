from datetime import date

import pytest

from munshi import demo
from munshi.config import Config
from munshi.store import Store
from munshi.timefmt import FakeClock, at
from munshi.write.blocks import MAX_SUMMARY_WORDS, MAX_TOPIC_WORDS
from munshi.write.model import Ollama
from munshi.write.writer import Result, Writer

pytestmark = pytest.mark.model


def test_real_model_on_one_demo_slot():
    model = Ollama(Config().ollama_url, Config().model, timeout=600)
    reachable, present = model.status()
    assert reachable and present, (
        "start `ollama serve` and pull gemma4:e4b, or run pytest -m 'not model'"
    )
    today = date(2026, 10, 24)
    store = Store(":memory:")
    store.set("known_repos", ["lantern", "tidepool"])
    demo.add_day(store, today, demo.TODAY, demo.GIT["today"])
    writer = Writer(store, Config(), FakeClock(at(today, "16:05")), model)
    slot = at(today, "15:00")
    result = Result()
    writer.write_slot(slot, result)
    assert result.model_errors == 0 and result.slots == 1
    blocks = store.blocks(slot, slot + 900)
    assert blocks and result.accepted + result.fallback == len(blocks)
    assert sum(b.active for b in blocks) == pytest.approx(15 * 60, abs=1)
    for block in blocks:
        assert slot <= block.start <= block.end <= slot + 900
        assert block.project in {"tidepool", "lantern", "Other"}
        if block.source == "model":
            assert len(block.summary.split()) <= MAX_SUMMARY_WORDS
            assert not any(c.isdigit() for c in block.summary + block.topic)
            assert len(block.topic.split()) <= MAX_TOPIC_WORDS or block.topic in store.topics()
