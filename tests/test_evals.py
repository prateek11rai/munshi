from helpers import DAY, FakeModel, window

from munshi.config import Config
from munshi.evals import day_slots, run_real_eval
from munshi.store import Store
from munshi.timefmt import FakeClock, at, day_bounds
from munshi.write.writer import Writer

GOOD = {
    "blocks": [
        {
            "evidence": ["e1"],
            "project": "tidepool",
            "topic": "tide-chart caching",
            "summary": "Cached the tide chart per station",
        }
    ]
}


def real_home(tmp_path):
    store = Store.at_home(tmp_path)
    store.set("known_repos", ["tidepool"])
    window(store, "14:00", "14:12", "Code", "cache.py — station tide chart")
    window(store, "14:16", "14:40", "Code", "cache.py — station tide chart")
    now = at(DAY, "14:50")
    Writer(store, Config(), FakeClock(now), FakeModel(GOOD, GOOD, GOOD)).run()
    store.close()
    return tmp_path / "munshi.db", now


def test_real_eval_uses_a_scratch_copy_and_prints_numbers_only(tmp_path, capsys):
    db, now = real_home(tmp_path)
    before = db.read_bytes()
    model = FakeModel(GOOD, {"blocks": [{"evidence": ["e7"]}]}, GOOD)
    report = run_real_eval(Config(), model, db, DAY, now)
    assert len(model.calls) == 3
    assert "tide-chart caching" not in model.calls[0][1]
    assert (report.result.slots, report.result.accepted, report.result.rejected) == (3, 2, 1)
    text = "\n".join(report.lines()) + capsys.readouterr().out
    assert "over 3 real slots" in text and "fallback rate" in text
    assert report.model_seconds == 22 * 60 and report.fallback_seconds == 14 * 60
    assert "active time labelled by the model 61% · by code 39%" in text
    assert not any(word in text for word in ("tidepool", "cache.py", "station", "Code"))
    assert db.read_bytes() == before
    store = Store(db)
    assert len(store.blocks(*day_bounds(DAY))) == 3


def test_day_slots_skip_the_unfinished_slot():
    store = Store(":memory:")
    window(store, "14:00", "14:40", "Code", "x")
    assert day_slots(store, DAY, at(DAY, "14:35")) == [at(DAY, "14:00"), at(DAY, "14:15")]
