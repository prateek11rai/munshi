from datetime import timedelta

from helpers import DAY

from munshi.collect.fake import ScriptedWindows
from munshi.collect.loop import Collector
from munshi.config import Config
from munshi.stats import counters
from munshi.store import Store
from munshi.timefmt import FakeClock, at, day_bounds
from munshi.write.hours import day_hours
from munshi.write.writer import Writer

NEXT = DAY + timedelta(days=1)


def test_work_across_midnight_is_split_and_the_day_closes(tmp_path):
    clock = FakeClock(at(DAY, "23:50"))
    store = Store.at_home(tmp_path)
    store.set("known_repos", ["tidepool"])
    source = ScriptedWindows(clock, [(clock.now(), "Code", "cache.py — tidepool")])
    collector = Collector(store, Config(), source, clock, own_pid=1)
    while clock.now() < at(NEXT, "00:16"):
        collector.tick()
        clock.advance(10)
    [event] = store.events(0, 4e9)
    assert event.start == at(DAY, "23:50") and event.end >= at(NEXT, "00:15")
    assert counters(store, DAY) == {"recorded": 60}
    assert counters(store, NEXT)["recorded"] >= 96

    result = Writer(store, Config(), clock, None, tmp_path).run()
    assert result.slots == 2 and result.days_closed == [DAY.isoformat()]
    blocks = store.blocks(*day_bounds(DAY)) + store.blocks(*day_bounds(NEXT))
    assert {(b.start, b.end) for b in blocks} == {
        (at(DAY, "23:50"), at(NEXT, "00:00")),
        (at(NEXT, "00:00"), at(NEXT, "00:15")),
    }
    assert [(r.project, r.seconds) for r in day_hours(store, DAY)] == [("tidepool", 600)]
    assert [(r.project, r.seconds) for r in day_hours(store, NEXT)] == [("tidepool", 900)]
    page = (tmp_path / "journal" / f"{DAY.isoformat()}.md").read_text()
    assert "Active 10 min" in page and "23:50–00:00 · tidepool" in page
    csv = (tmp_path / "hours" / f"{DAY.isoformat()}.csv").read_text()
    assert csv.splitlines()[1].startswith(f"{DAY.isoformat()},tidepool,")
