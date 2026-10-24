from munshi.store import Block, Event, Note, Store


def make_store():
    return Store(":memory:")


def test_schema_version():
    assert make_store().schema_version() == 1


def test_events_roundtrip_and_extend():
    store = make_store()
    eid = store.add_event(Event("window", 100, 110, app="Code", title="cache.py — tidepool"))
    store.extend_event(eid, 130)
    [event] = store.events(0, 1000)
    assert (event.app, event.end, event.seconds) == ("Code", 130, 30)
    store.add_event(Event("git", 120, 120, repo="tidepool", detail={"dirty": 3}))
    assert [e.kind for e in store.events(0, 1000, ("git",))] == ["git"]
    assert store.repos() == ["tidepool"]
    assert store.last_event(("git",), repo="tidepool").detail == {"dirty": 3}


def test_prune_events():
    store = make_store()
    store.add_event(Event("window", 0, 10, app="A"))
    store.add_event(Event("window", 100, 110, app="B"))
    assert store.prune_events(50) == 1
    assert [e.app for e in store.events(0, 1000)] == ["B"]


def test_blocks_topics_slots():
    store = make_store()
    store.add_block(Block(0, 0, 600, 600, "tidepool", "tide-chart caching", "s", "model", [1]))
    store.mark_slot(0, 900, accepted=1)
    assert store.written_slots(0, 1000) == {0}
    assert store.topics() == ["tide-chart caching"]
    [block] = store.blocks(0, 1000)
    assert block.evidence == [1]


def test_note_replaces_same_kind_and_day():
    store = make_store()
    store.add_note(Note("where", "2026-10-24", 10, 0, 10, "first", "model"))
    store.add_note(Note("where", "2026-10-24", 20, 0, 20, "second", "model", facts={"a": 1}))
    note = store.note("where")
    assert (note.text, note.facts) == ("second", {"a": 1})


def test_forget_overlapping_and_orphan_topics():
    store = make_store()
    store.add_event(Event("window", 0, 100, app="A"))
    store.add_event(Event("window", 3000, 3700, app="B"))
    store.add_block(Block(0, 0, 100, 100, "Other", "old topic", "s", "model"))
    store.add_block(Block(3000, 3000, 3700, 700, "Other", "secret topic", "s", "model"))
    store.add_note(Note("where", "d", 3700, 0, 3700, "t", "model"))
    counts = store.forget(3600, 7200)
    assert counts == {"events": 1, "blocks": 1, "notes": 1}
    assert store.topics() == ["old topic"]
    assert [e.app for e in store.events(0, 10_000)] == ["A"]


def test_state():
    store = make_store()
    assert store.get("paused_until") is None
    store.set("paused_until", 123.0)
    assert store.get("paused_until") == 123.0
    store.set("paused_until", None)
    assert store.get("paused_until", "x") == "x"


def test_db_file_private(tmp_path):
    store = Store.at_home(tmp_path)
    store.close()
    assert oct((tmp_path / "munshi.db").stat().st_mode & 0o777) == "0o600"
