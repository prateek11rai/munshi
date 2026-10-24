from datetime import date

from munshi.store import Event, Store
from munshi.timefmt import at
from munshi.write.model import ModelError

DAY = date(2026, 10, 23)


class FakeModel:
    """Plays back recorded replies; a reply may be an exception to raise or a callable."""

    name = "fake"

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def chat_json(self, system, user, schema):
        self.calls.append((system, user, schema))
        reply = self.replies.pop(0) if self.replies else ModelError("no more replies")
        if callable(reply) and not isinstance(reply, dict):
            reply = reply(system, user, schema)
        if isinstance(reply, Exception):
            raise reply
        return reply


def window(store: Store, start: str, end: str, app: str, title: str | None, day=DAY) -> Event:
    event = Event("window", at(day, start), at(day, end), app=app, title=title)
    store.add_event(event)
    return event


def git(store: Store, when: str, repo: str, commits=(), dirty=0, files=(), day=DAY) -> Event:
    detail = {
        "branch": "main",
        "commits": [{"hash": f"c{i}", "subject": s} for i, s in enumerate(commits)],
        "dirty": dirty,
        "files": list(files),
    }
    event = Event("git", at(day, when), at(day, when), repo=repo, detail=detail)
    store.add_event(event)
    return event
