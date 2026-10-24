from datetime import date

import pytest

from munshi import demo
from munshi.store import Block, Store
from munshi.timefmt import at, day_bounds
from munshi.write import journal
from munshi.write.blocks import ReplyBlock, check
from munshi.write.hours import ProjectHours, clip, day_hours, day_totals, timesheet, to_csv
from munshi.write.notes import check_day, check_where, facts, facts_text
from munshi.write.slots import compact

TODAY = date(2026, 10, 24)
YESTERDAY = date(2026, 10, 23)

JOURNAL = """\
# Friday 23 October 2026

Active 6 h 45 min · away 2 h 10 min

## Summary
- tidepool: tide-chart caching and a CI fix (3 h 30 min)
- lantern: docs navigation in the sidebar (1 h 45 min)
- Reading: SQLite WAL and fsync (1 h 30 min)

## Timeline
- 09:15–10:25 · tidepool · CI fix
- 10:40–12:10 · tidepool · tide-chart caching
- 12:10–13:00 · Other · SQLite WAL reading
- 14:00–15:45 · lantern · docs navigation
- 16:10–17:00 · tidepool · tide-chart caching
- 17:00–17:40 · Other · SQLite WAL reading

## Hours
| Project | Hours | Topics |
|---|---|---|
| tidepool | 3.5 | tide-chart caching, CI fix |
| lantern | 1.75 | docs navigation |
| Other | 1.5 | SQLite WAL reading |

## Left open
- tidepool: 2 uncommitted files
"""


@pytest.fixture
def store(tmp_path):
    demo.load(tmp_path, TODAY)
    s = Store.at_home(tmp_path)
    yield s
    s.close()


def test_demo_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    demo.load(a, TODAY)
    demo.load(b, TODAY)
    sa, sb = Store.at_home(a), Store.at_home(b)
    lo, hi = day_bounds(YESTERDAY)[0], day_bounds(TODAY)[1]
    assert [(e.kind, e.start, e.end, e.app, e.title, e.detail) for e in sa.events(lo, hi)] == [
        (e.kind, e.start, e.end, e.app, e.title, e.detail) for e in sb.events(lo, hi)
    ]
    assert demo.clock(sa).now() == pytest.approx(at(TODAY, "16:05"), abs=5)
    assert not demo.is_stale(sa)


def test_demo_clear(tmp_path):
    demo.load(tmp_path / "d", TODAY)
    demo.clear(tmp_path / "d")
    assert not (tmp_path / "d").exists()


def test_journal_matches_spec_format(store, tmp_path):
    assert journal.render(store, YESTERDAY) == JOURNAL
    page, sheet = journal.write(store, tmp_path, YESTERDAY)
    assert page.name == "2026-10-23.md" and page.read_text() == JOURNAL
    assert sheet.read_text().splitlines() == [
        "date,project,topic,hours",
        "2026-10-23,tidepool,tide-chart caching,2.25",
        "2026-10-23,tidepool,CI fix,1.25",
        "2026-10-23,lantern,docs navigation,1.75",
        "2026-10-23,Other,SQLite WAL reading,1.5",
    ]


def test_hours_and_totals(store):
    rows = day_hours(store, YESTERDAY)
    assert [(r.project, r.hours) for r in rows] == [
        ("tidepool", 3.5),
        ("lantern", 1.75),
        ("Other", 1.5),
    ]
    active, away = day_totals(store, YESTERDAY)
    assert (active, away) == (405 * 60, 130 * 60)
    assert timesheet(rows).splitlines()[0] == "tidepool · 3.5 h · tide-chart caching, CI fix"


def test_rounding_to_quarter_hours():
    row = ProjectHours("x", 7 * 60, {"t": 7 * 60})
    assert row.hours == 0
    assert ProjectHours("x", 8 * 60).hours == 0.25
    assert ProjectHours("x", 52 * 60 + 31).hours == 1.0
    assert timesheet([row]) == ""
    assert to_csv(YESTERDAY, [row]) == "date,project,topic,hours\n"


def test_block_crossing_midnight_is_split():
    s = Store(":memory:")
    start = at(YESTERDAY, "23:30")
    s.add_block(Block(start, start, start + 3600, 3600, "tidepool", "late fix", "s", "model"))
    assert clip(s.blocks(0, 4e9)[0], *day_bounds(YESTERDAY)) == 1800
    assert [r.seconds for r in day_hours(s, YESTERDAY)] == [1800]
    assert [r.seconds for r in day_hours(s, TODAY)] == [1800]
    page = journal.render(s, TODAY)
    assert "- 00:00–00:30 · tidepool · late fix" in page


def test_demo_blocks_pass_the_code_checks(store):
    lo, hi = day_bounds(YESTERDAY)[0], day_bounds(TODAY)[1]
    projects = ["lantern", "tidepool", "Other"]
    for block in store.blocks(lo, hi):
        slot = compact(
            store.events(block.slot, block.slot + 900), block.slot, block.slot + 900, projects
        )
        ids = [i.id for i in slot.items if set(i.event_ids) & set(block.evidence)]
        reply = ReplyBlock(
            evidence=ids, project=block.project, topic=block.topic, summary=block.summary
        )
        made, reason = check(reply, slot, projects, [], set())
        assert reason == "ok", (block.topic, block.summary, reason)
        assert made.project == block.project


def test_demo_notes_pass_the_code_checks(store):
    lo, hi = day_bounds(YESTERDAY)
    by_id = {f"b{b.id}": b for b in store.blocks(lo, hi)}
    note = store.note("day", YESTERDAY.isoformat())
    answer = {
        "bullets": [
            {"text": b["text"], "cites": [f"b{c}" for c in b["cites"]]}
            for b in note.facts["bullets"]
        ]
    }
    assert len(check_day(answer, by_id)) == 3
    where = store.note("where")
    blocks = {f"b{b.id}": b for b in store.blocks(where.span_start, where.span_end)}
    assert (
        check_where({"text": where.text, "cites": [f"b{c}" for c in where.cites]}, blocks)
        == where.text
    )


def test_where_facts(store):
    f = facts(store, at(TODAY, "15:59"))
    assert facts_text(f) == (
        "Left open: 3 uncommitted files in tidepool · last file: cache.py"
        " · last page: SQLite WAL mode"
    )
    assert facts_text({"open": [], "last_file": None, "last_page": None}) == ""
