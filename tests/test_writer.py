from datetime import date, timedelta

from helpers import DAY, FakeModel, git, window

from munshi.config import Config
from munshi.control import forget
from munshi.store import Store
from munshi.timefmt import FakeClock, at
from munshi.write.model import ModelError
from munshi.write.notes import check_where
from munshi.write.writer import Writer, known_projects


def setup(model, now="14:31"):
    store = Store(":memory:")
    store.set("known_repos", ["tidepool", "lantern"])
    window(store, "14:00", "14:09", "Code", "cache.py — tidepool")
    window(store, "14:09", "14:14", "Google Chrome", "SQLite WAL mode")
    window(store, "14:15", "14:29", "Code", "nav.md — lantern")
    git(
        store,
        "14:05",
        "tidepool",
        commits=["fix: cache tide chart per station"],
        dirty=2,
        files=["cache.py"],
    )
    clock = FakeClock(at(DAY, now))
    return store, Writer(store, Config(), clock, model), clock


GOOD_SLOT_1 = {
    "blocks": [
        {
            "evidence": ["e1", "e2"],
            "project": "tidepool",
            "topic": "tide-chart caching",
            "summary": "Cached the tide chart per station",
        },
        {
            "evidence": ["e3"],
            "project": "Other",
            "topic": "SQLite WAL reading",
            "summary": "Read about SQLite WAL mode",
        },
    ]
}
GOOD_SLOT_2 = {
    "blocks": [
        {
            "evidence": ["e1"],
            "project": "lantern",
            "topic": "docs navigation",
            "summary": "Edited lantern nav",
        }
    ]
}
WHERE = {
    "text": "You were caching the tide chart in tidepool, then editing lantern nav.",
    "cites": [],
}


def where_reply(system, user, schema):
    ids = schema["properties"]["cites"]["items"]["enum"]
    return {**WHERE, "cites": ids}


def test_writer_writes_slots_with_model_and_notes():
    model = FakeModel(GOOD_SLOT_1, GOOD_SLOT_2, where_reply)
    store, writer, clock = setup(model)
    result = writer.run()
    assert (result.slots, result.accepted, result.rejected, result.fallback) == (2, 3, 0, 0)
    blocks = store.blocks(0, 4e9)
    assert [(b.project, b.topic, b.source) for b in blocks] == [
        ("tidepool", "tide-chart caching", "model"),
        ("Other", "SQLite WAL reading", "model"),
        ("lantern", "docs navigation", "model"),
    ]
    assert blocks[0].start == at(DAY, "14:00") and blocks[0].end == at(DAY, "14:09")
    note = store.note("where")
    assert note.source == "model" and note.text.startswith("You were caching")
    assert "tidepool" in note.facts["open"][0]["repo"]
    assert writer.run().slots == 0


def test_writer_falls_back_on_rejection_and_model_errors():
    bad = {"blocks": [{"evidence": ["e9"], "project": "moonbase", "topic": "x", "summary": "y"}]}
    model = FakeModel(bad, ModelError("timeout"), ModelError("timeout"))
    store, writer, clock = setup(model)
    result = writer.run()
    assert (result.accepted, result.rejected, result.fallback, result.model_errors) == (0, 1, 3, 1)
    assert result.reasons == {"unknown evidence id": 1}
    assert {b.source for b in store.blocks(0, 4e9)} == {"fallback"}
    assert store.note("where").source == "fallback"
    assert "3 slots" not in result.line() and "1 rejected" in result.line()


def test_writer_without_model_is_code_only():
    store, writer, clock = setup(None)
    result = writer.run()
    assert result.fallback == 3 and result.accepted == 0
    assert [b.topic for b in store.blocks(0, 4e9)][:2] == [
        "Code · cache.py",
        "Google Chrome · SQLite WAL mode",
    ]


def test_unfinished_slot_waits():
    store, writer, clock = setup(None, now="14:20")
    assert writer.run().slots == 1


def test_day_close_writes_note_journal_and_csv(tmp_path):
    model = FakeModel(GOOD_SLOT_1, GOOD_SLOT_2, where_reply)
    store, writer, clock = setup(model)
    writer.run()
    writer.home = tmp_path
    next_day = DAY + timedelta(days=1)
    clock.t = at(next_day, "09:00")

    def day_reply(system, user, schema):
        ids = schema["properties"]["bullets"]["items"]["properties"]["cites"]["items"]["enum"]
        texts = [
            "tidepool: cached the tide chart",
            "Reading: SQLite WAL mode",
            "lantern: docs navigation",
        ]
        return {"bullets": [{"text": t, "cites": [i]} for t, i in zip(texts, ids, strict=True)]}

    writer.model = FakeModel(day_reply)
    result = writer.run()
    assert result.days_closed == [DAY.isoformat()]
    note = store.note("day", DAY.isoformat())
    assert note.source == "model" and len(note.facts["bullets"]) == 3
    page = (tmp_path / "journal" / f"{DAY.isoformat()}.md").read_text()
    assert (
        page.startswith("# Friday 23 October 2026")
        and "- tidepool: cached the tide chart (9 min)" in page
    )
    assert (tmp_path / "hours" / f"{DAY.isoformat()}.csv").exists()
    assert writer.run().days_closed == []


def test_day_note_falls_back_when_model_rambles(tmp_path):
    store, writer, clock = setup(None)
    writer.run()
    clock.t = at(DAY + timedelta(days=1), "09:00")
    writer.model = FakeModel({"bullets": [{"text": "Planned budgets", "cites": ["b999"]}]})
    writer.run()
    note = store.note("day", DAY.isoformat())
    assert note.source == "fallback"
    assert note.text.splitlines() == [
        "lantern: Code · nav.md",
        "tidepool: Code · cache.py",
        "Other: Google Chrome · SQLite WAL mode",
    ]


def test_prunes_old_events():
    store, writer, clock = setup(None)
    old_day = date(2026, 10, 1)
    window(store, "10:00", "10:05", "Code", "old", day=old_day)
    clock.t = at(DAY, "14:31")
    writer.run()
    assert all(e.title != "old" for e in store.events(0, 4e9))


def test_forget_last_hour_rewrites_note():
    store, writer, clock = setup(None)
    writer.run()
    counts = forget(store, at(DAY, "14:31"), 60)
    assert counts["events"] == 4 and counts["blocks"] == 3
    assert store.blocks(0, 4e9) == [] and store.topics() == []
    assert store.note("where").text == "Nothing recorded in the last two hours."


def test_known_projects():
    store, writer, clock = setup(None)
    assert known_projects(store, Config()) == ["lantern", "tidepool", "Other"]


def test_check_where_rejects():
    store, writer, clock = setup(None)
    writer.run()
    blocks = {f"b{b.id}": b for b in store.blocks(0, 4e9)}
    ids = list(blocks)
    assert check_where({"text": "You were caching tidepool.", "cites": ["b999"]}, blocks) is None
    long = "You were caching tidepool. " * 3
    assert check_where({"text": long, "cites": ids}, blocks) is None
    assert check_where({"text": "You were planning a holiday.", "cites": ids}, blocks) is None
    assert (
        check_where({"text": "You were caching tidepool at 14:05", "cites": ids}, blocks)
        == "You were caching tidepool at."
    )
