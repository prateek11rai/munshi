from datetime import date

import pytest
from helpers import FakeModel

from munshi import demo
from munshi.store import Store
from munshi.ui.service import Service


@pytest.fixture
def service(tmp_path):
    demo.load(tmp_path, date.today())
    return Service(tmp_path, True, model=lambda config: None)


def test_card_parts(service):
    card = service.card()
    assert card["where"]["text"].startswith("You were tightening the tide-chart caching")
    assert card["where"]["facts"].startswith("Left open: 3 uncommitted files in tidepool")
    assert card["where"]["updated"] == "updated 6 min ago"
    first = card["today"][0]
    assert first == {
        "kind": "block",
        "time": "14:10–15:15",
        "project": "tidepool",
        "topic": "tide-chart caching",
    }
    assert {"kind": "away", "text": "away 50 min"} in card["today"]
    assert card["yesterday"]["lines"][0] == "tidepool: tide-chart caching and a CI fix"
    assert card["yesterday"]["total"] == "Active 6 h 45 min"
    rows = card["hours"]["yesterday"]["rows"]
    assert [(r["project"], r["hours"], r["pct"]) for r in rows] == [
        ("tidepool", "3.5 h", 100),
        ("lantern", "1.75 h", 50),
        ("Other", "1.5 h", 43),
    ]
    assert card["paused"] == {"on": False, "text": ""} and card["demo"] is True


def test_pause_resume_forget_and_view_persist(service, tmp_path):
    card = service.pause("30")
    assert card["paused"]["on"] and card["paused"]["text"].startswith("Paused until ")
    assert service.paused()
    assert service.pause("until")["paused"]["text"] == "Paused until you resume"
    assert not service.resume()["paused"]["on"]
    with pytest.raises(ValueError):
        service.pause("forever")
    before = len(service.card()["today"])
    card = service.forget()
    assert card["where"]["text"].startswith("Mostly ")
    assert len(card["today"]) <= before
    assert service.set_hours_view("yesterday")["hours_view"] == "yesterday"
    assert Store.at_home(tmp_path).get("hours_view") == "yesterday"


def test_timesheet(service):
    assert service.timesheet("yesterday").splitlines() == [
        "tidepool · 3.5 h · tide-chart caching, CI fix",
        "lantern · 1.75 h · docs navigation",
        "Other · 1.5 h · SQLite WAL reading",
    ]


def test_refresh_writes_remaining_demo_slots(service):
    before = service.card()["today"][0]["time"]
    card = service.refresh()
    assert card["message"].startswith("Wrote ") and "code wrote them" in card["message"]
    assert card["today"][0]["time"] != before
    assert service.refresh()["message"] == "Up to date."


def test_refresh_uses_model(tmp_path):
    demo.load(tmp_path, date.today())
    reply = lambda s, u, schema: {"blocks": []}  # noqa: E731
    model = FakeModel(*([reply] * 10))
    service = Service(tmp_path, True, model=lambda config: model)
    assert service.refresh()["message"].startswith("Wrote ")
    assert len(model.calls) >= 3


def test_journal_dir(service, tmp_path):
    assert service.journal_dir() == tmp_path / "journal"
