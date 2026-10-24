# Munshi · spec

Munshi is a small buddy that sits on your Mac's desktop and keeps your daily register. It quietly notes what you work on (which app, which window, which repo, which files), and a local open-weight model (Gemma 4 e4b through Ollama) turns that into a plain journal. Click the munshi and you get one card: **where you were**, **what you did today and yesterday**, and **your hours per project**, ready to paste into a timesheet. Nothing leaves the laptop: no screenshots, no keystrokes, no network except the local model.

Built for the DEV Hacktoberfest Open-Source AI Challenge, Week 3 "Slow and Steady" (build something with open-weight AI "that rewards laziness"). Closes **Mon 2026-10-26 12:29 IST**.

The lazy promise: you do nothing. You never write a status update, you never rebuild yesterday from memory, you never guess your hours.

Why it has to be open and local: a log of every window you open is the most private data on your computer. Rewind (the Mac app that remembered everything) stopped capturing on 2025-12-19 after Meta bought its parent company; this kind of record should never depend on someone else's server or business. A 4B model on your own laptop is enough to label it.

## What the person sees

### The buddy

- A small munshi (spectacles, cap, a ledger) in a frameless, transparent, always-on-top window, about 88 × 88 px, bottom-right by default. Drag it anywhere; the position is remembered.
- A plain click toggles the card. A drag never opens the card.
- Two looks for now: normal, and paused (greyed, with a small pause mark). Animations and moods come later; keep the image swappable (one SVG file).
- No Dock icon if it can be done cleanly (activation policy "accessory"); otherwise note it.

### The card

Opens next to the buddy (left of it, or right if there's no room), about 380 × 560 px, frameless, on top. Esc or the close button hides it. Four parts, top to bottom, all visible without tabs (scroll if needed):

1. **Where was I.** Two lines written by the model about the last ~2 hours, e.g. "You were tightening the tide-chart caching in tidepool, then reading SQLite WAL docs." Under it, facts from code, not the model: "Left open: 3 uncommitted files in tidepool · last file: cache.py · last page: SQLite WAL mode". Updated in the background after every writer run, so the click is instant. Shows "updated 6 min ago".
2. **Today.** The blocks so far, newest first: `14:10–15:40 · tidepool · tide-chart caching`. Away time shown as a thin gap line ("away 45 min").
3. **Yesterday.** 3–5 short lines by topic, written by the model, plus the total active time. If there's no yesterday yet: "Nothing from yesterday yet."
4. **Hours.** Bars per project for today and yesterday (switch with two buttons), rounded to 15 min. **Copy for timesheet** puts lines like `tidepool · 2.5 h · tide-chart caching, CI fix` on the clipboard and shows "Copied".

Footer actions: **Refresh now** (runs the writer), **Pause** / **Resume** (pause offers 30 min, 1 h, until I resume), **Forget last hour**, **Open journal** (opens the journal folder in Finder).

Copy is short and plain. No emoji, no exclamation marks, no AI-speak.

### The journal

One Markdown file per day in `<home>/journal/YYYY-MM-DD.md`, written when the day closes (first writer run after midnight local time) and on demand. Obsidian-friendly:

```
# Saturday 24 October 2026

Active 6 h 45 min · away 2 h 10 min

## Summary
- tidepool: tide-chart caching and a CI fix (3 h 30 min)
- lantern: docs navigation (1 h 45 min)
- Reading: SQLite WAL and fsync (1 h 30 min)

## Timeline
- 09:40–10:25 · tidepool · CI fix
- …

## Hours
| Project | Hours | Topics |
|---|---|---|
| tidepool | 3.5 | tide-chart caching, CI fix |

## Left open
- tidepool: 3 uncommitted files
```

Plus `<home>/hours/YYYY-MM-DD.csv` with `date,project,topic,hours`.

## How it works

```
collector (every 10 s) ─▶ events ─▶ writer (every 15 min) ─▶ blocks ─▶ notes (where / day) ─▶ card, journal, hours
            git + files (every 5 min) ─┘          local Gemma 4, checked by code
```

### Collector (macOS)

- **Window:** the front app (NSWorkspace) and the focused window's title (Accessibility API, `AXFocusedWindow` → `AXTitle`). Without Accessibility permission it records the app name only and `doctor` says so. Every 10 s; same app + title within 15 s extends the current event instead of adding a row.
- **Idle:** seconds since the last input (Quartz `CGEventSourceSecondsSinceLastEventType`). Idle ≥ 3 min closes the current event at the last input and starts an `away` event.
- **Git (every 5 min):** for each repo directly under the allowed roots (depth ≤ 2): branch, commits since the last scan (hash, subject), count of uncommitted files and their names (no contents, no diffs).
- **Files (every 5 min):** files changed in the last 5 min under allowed roots that aren't in a git repo, via Spotlight (`mdfind -onlyin <root> 'kMDItemFSContentChangeDate >= $time.now(-300)'`). Names only.
- Nothing else: no screenshots, no keystrokes, no clipboard, no browser history, no network.
- macOS gotcha: `frontmostApplication` only refreshes while a run loop runs on the main thread, and pywebview owns the main thread. Poll from a main-thread timer or use another source that's always fresh; prove it in a test with a fake and write down what you chose.

### Privacy rules (code, not promises)

- **Ignored apps** (never recorded): 1Password, Bitwarden, Keychain Access, System Settings, loginwindow, ScreenSaverEngine, plus whatever the config adds.
- **Only mode:** `apps.mode = "only"` records just the listed apps (for a work laptop or a demo).
- **Private windows:** titles containing "Private Browsing", "Incognito" or "InPrivate" are recorded as the app name only.
- **Title words** (`ignore_title_words`): a front window whose title or app name contains one (case-insensitive) is not recorded at all, exactly like an ignored app; checked before redaction. Git repos, branches, commit subjects and file names containing one are dropped too.
- **Process words** (`ignore_process_words`): the front app's command line (`ps -o command= -p <pid>`, read once per process, only the yes/no kept) containing one means its windows are not recorded at all. This is how one browser profile (launched with a profile path or name) is skipped while another is recorded. A failed `ps` counts as no match and is retried on the next poll.
- **Redaction before storage:** emails → `[email]`; URLs → host only; tokens (≥ 24 chars of hex/base64/alnum) → `[token]`; runs of ≥ 6 digits → `[number]`. Tested.
- **Allowed roots** for git and files are empty by default: nothing is scanned until the person lists folders.
- **Pause** stops all recording (window, git, files) until the time ends or Resume. **Forget last hour** deletes events, blocks and notes that overlap the last 60 min and rewrites today's note.
- **Model must be local:** the Ollama URL must be localhost/127.0.0.1 unless `allow_remote_model = true` is set on purpose.
- Data dir is created with mode 700. Raw events kept 14 days (configurable); blocks, notes, journal and hours kept.
- Window titles are data, never instructions. The model has no tools and its output is checked (below), so a page titled "ignore your instructions" can at most produce a rejected block.

### Writer and the model

- Every 15 min (and on Refresh / `munshi write`), for each finished 15-min slot not yet written: compact the slot's events (merge repeats, durations in minutes, drop away time) and send them with stable ids (`e1`, `e2`, …), the list of known projects (repo names under allowed roots + "Other") and the existing topic names.
- The model answers JSON (Ollama `format` with a JSON schema; temperature 0): `blocks: [{evidence: [ids], project, topic, summary}]`.
- **Code checks every block:** evidence ids exist and belong to the slot; `project` is in the known list; `topic` is an existing topic or a new one of ≤ 4 words; `summary` ≤ 14 words and at least one of its content words (≥ 4 letters, not a stop word) appears in the evidence titles, file names, repo names or commit subjects. Start/end come from the evidence, never from the model. Adjacent blocks with the same project + topic merge.
- **Anything rejected** (or a model error/timeout) falls back to a code-made block: `<app> · <shortened title>`, project from code detection, `source = "fallback"`. The timeline is never empty because the model failed.
- **Project detection in code first:** VS Code / Cursor / Zed / JetBrains titles ending in a repo name, terminal titles with a path, git events, file paths. The model only fills `project` when code found none, and only from the known list.
- **Notes:** after each writer run, a "where" note (≤ 2 sentences, ≤ 40 words) from the last ~2 h of blocks; at day close, a "day" note (3–5 bullets, each ≤ 14 words, each citing block ids). Same checks: cited ids exist, content words appear in the cited blocks. Rejected → a code-made fallback ("Mostly tidepool (3 h 30 min), then lantern (1 h 45 min).").
- **Numbers are code only:** durations, hours, counts, "updated N min ago". The model never writes a number that ends up on screen; strip or reject digits in model text.
- Model settings: `gemma4:e4b` by default, any Ollama model by name (`MUNSHI_MODEL` or config). `num_ctx` 8192, `keep_alive` 5m, 60 s timeout.

### Hours

- Active time = sum of block durations (away excluded) per project and topic per day, rounded to the nearest 0.25 h for display and CSV; the card's total uses minutes.
- A day is local midnight to midnight; a block crossing midnight is split.

## Commands

`uv run munshi <command>` (console script `munshi`):

| Command | What it does |
|---|---|
| `start [--demo]` | Collector + writer in background threads, buddy and card windows on the main thread. `--demo` uses the demo home and runs **no collectors**. |
| `doctor [--demo]` | ✓/✗ for Python, macOS, Ollama reachable, model present, Accessibility granted, allowed roots, data dir, config path. |
| `demo load` / `demo clear` | Two made-up days into the demo home (`./.data/demo`, git-ignored). |
| `write [--demo]` | Run the writer once now; print blocks written, rejected, fallback. |
| `journal [--date D] [--demo]` | Write and print the journal for a day (default yesterday). |
| `hours [--date D] [--csv] [--demo]` | Hours per project and topic. |
| `pause [--for 30m\|1h]` / `resume` | Pause or resume recording. |
| `forget --last 60m` | Forget recent time. |
| `preview [--demo]` | Serve the card on http://127.0.0.1:8765 with the same data, for a browser (and Playwright). |
| `stats [--demo] [--day D]` | Numbers only, never recorded text: events by kind and minutes; polls recorded vs skipped by reason; slots written; blocks accepted, rejected by check, fallback; seconds per slot; last writer run; the running app's Accessibility flag, RSS and CPU (stored by `start` at launch and every 10 min). |
| `eval [--model M] (--demo | --real [--day D])` | Run the writer over the demo days, or over a real day in a scratch copy of the store (the real store is untouched); print numbers only: blocks accepted vs rejected by check, fallback rate, seconds per slot. |

## Config

`<home>/config.toml`, created with comments on first run. Home is `~/.munshi` (override `MUNSHI_HOME`); demo home is `./.data/demo`.

```toml
model = "gemma4:e4b"
ollama_url = "http://127.0.0.1:11434"
allowed_roots = []            # e.g. ["~/github/prateek11rai", "~/Documents/notes"]
keep_events_days = 14
ignore_title_words = []       # e.g. ["acme"]
ignore_process_words = []     # e.g. ["acme"]

[apps]
mode = "all"                  # or "only"
only = []
ignore = []                   # added to the built-in list
```

Unknown keys are refused (a misspelt privacy key must not be silently ignored), and config errors name the key, never its value.

Env overrides: `MUNSHI_HOME`, `MUNSHI_MODEL`, `MUNSHI_OLLAMA_URL`. No `.env`, no secrets anywhere.

## Demo data

Two made-up days of one solo developer, generated by code (deterministic), for every screen, the tests and `eval`:

- Projects: **tidepool** (a made-up open-source tide-chart app), **lantern** (a made-up docs site), plus reading with no project.
- Apps and titles: VS Code (`cache.py — tidepool`), Ghostty (`~/code/tidepool — pytest`), Chrome (`Issue #18 · tidepool`, `SQLite WAL mode`, `Hacker News`, `lo-fi beats - YouTube`), Finder, Preview (`tide-tables-2026.pdf`), a lunch gap and a short break.
- Git: commits like `fix: cache tide chart per station`, 3 uncommitted files at the end of today.
- Never real people, companies, customers, tickets or the owner's projects.

## Out of scope for the base

Animations and moods, topic merging across days with embeddings, browser history, autostart at login, Windows/Linux collectors, charts beyond simple bars, any cloud service.
