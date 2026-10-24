SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('window', 'away', 'git', 'file')),
    start REAL NOT NULL,
    end REAL NOT NULL,
    app TEXT,
    title TEXT,
    repo TEXT,
    detail TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS events_time ON events (start, end);
CREATE TABLE IF NOT EXISTS blocks (
    id INTEGER PRIMARY KEY,
    slot REAL NOT NULL,
    start REAL NOT NULL,
    end REAL NOT NULL,
    active REAL NOT NULL,
    project TEXT NOT NULL,
    topic TEXT NOT NULL,
    summary TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('model', 'fallback', 'demo')),
    evidence TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS blocks_time ON blocks (start, end);
CREATE TABLE IF NOT EXISTS slots (
    start REAL PRIMARY KEY,
    written REAL NOT NULL,
    accepted INTEGER NOT NULL DEFAULT 0,
    rejected INTEGER NOT NULL DEFAULT 0,
    fallback INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS topics (
    name TEXT PRIMARY KEY COLLATE NOCASE,
    project TEXT NOT NULL,
    first_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('where', 'day')),
    day TEXT NOT NULL,
    created REAL NOT NULL,
    span_start REAL NOT NULL,
    span_end REAL NOT NULL,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    cites TEXT NOT NULL DEFAULT '[]',
    facts TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""
