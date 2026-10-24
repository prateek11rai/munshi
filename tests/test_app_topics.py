from helpers import DAY, FakeModel, window

from munshi.store import Block, Store
from munshi.timefmt import at
from munshi.write.blocks import ReplyBlock, check, fallback_subject, only_app_words
from munshi.write.notes import check_where, code_where_note, where_note
from munshi.write.slots import compact

PROJECTS = ["tidepool", "Other"]


def terminal_slot():
    store = Store(":memory:")
    window(store, "14:00", "14:12", "WezTerm", "tmux")
    return compact(store.events(at(DAY, "14:00"), at(DAY, "14:15")), at(DAY, "14:00"),
                   at(DAY, "14:15"), PROJECTS)  # fmt: skip


def test_a_topic_made_of_app_names_is_rejected():
    slot = terminal_slot()
    reply = ReplyBlock(evidence=["e1"], project="Other", topic="WezTerm tmux", summary="tmux")
    assert check(reply, slot, PROJECTS, [], set()) == (None, "topic is an app")
    assert only_app_words("Google Chrome tabs") and only_app_words("wezterm", ["WezTerm"])
    assert not only_app_words("wezterm config") and not only_app_words("tide-chart caching")


def fallback(label, minutes=2, project="Other", start="14:00"):
    t = at(DAY, start)
    return Block(t, t, t + minutes * 60, minutes * 60, project, label, label, "fallback", [1])


def test_fallback_subjects_name_the_window_or_just_the_app():
    assert fallback_subject(fallback("WezTerm · tmux")) == "in WezTerm"
    assert fallback_subject(fallback("Finder")) == "in Finder"
    assert fallback_subject(fallback("Code · nav.md")) == "nav.md in Code"


def stored(*blocks):
    store = Store(":memory:")
    for block in blocks:
        store.add_block(block)
    return store


def test_code_where_note_says_in_the_app_plainly():
    store = stored(fallback("WezTerm · tmux"))
    assert code_where_note(store, at(DAY, "14:20")).text == "Mostly in WezTerm for 2 min."
    store = stored(
        fallback("Code · cache.py", 30, "tidepool"),
        fallback("WezTerm · tmux", 5, start="14:30"),
    )
    assert code_where_note(store, at(DAY, "14:40")).text == (
        "Mostly tidepool for 30 min, then in WezTerm for 5 min."
    )


def test_where_note_skips_the_model_when_only_apps_are_known():
    store = stored(fallback("WezTerm · tmux"))
    model = FakeModel({"text": "You were in the WezTerm tmux topic.", "cites": ["b1"]})
    note = where_note(store, at(DAY, "14:20"), model)
    assert model.calls == [] and note.text == "Mostly in WezTerm for 2 min."


def test_where_sentences_must_name_more_than_apps():
    t = at(DAY, "14:00")
    blocks = {
        "b1": fallback("WezTerm · tmux"),
        "b2": Block(
            t, t, t + 600, 600, "tidepool", "tide-chart caching", "Cached the chart", "model", [2]
        ),  # fmt: skip
    }
    for text in ("You were working on WezTerm and tmux.", "This involved the WezTerm tmux topic."):
        assert check_where({"text": text, "cites": ["b1"]}, blocks) is None
    good = {"text": "You were caching the tide chart in tidepool.", "cites": ["b2"]}
    assert check_where(good, blocks) == "You were caching the tide chart in tidepool."
