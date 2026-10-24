# Build Munshi · base (this laptop, demo data and fakes)

> The prompt the build agent gets. Lives at `docs/design/build-brief.md`; the planner appends answers at the bottom. Don't edit this file.

Planner: tmux `mlh:0`. You: tmux `mlh:1`. Repo: `~/github/prateek11rai/munshi`, branch `main`.
Challenge: https://dev.to/challenges/hacktoberfest-week3-2026-10-19, closes **Mon 2026-10-26 12:29 IST**. Finish the base **tonight**, aim for about 2.5 hours.

## Goal

Build the whole of `docs/design/spec.md` as one Python project managed with uv: the collector, the writer with a local Gemma 4 and code checks, the buddy and card windows (pywebview), the journal and hours, the CLI, demo data, tests and docs. `uv run munshi start --demo` shows the buddy; a click shows a filled card.

## Two machines, read this twice

- **This laptop is a work laptop. Real collection must never run here.** Never run `munshi start` without `--demo`, never call the macOS window/idle/git/file collectors outside tests, never point `allowed_roots` at a real folder, never take screenshots of the desktop (`screencapture` or similar). Test the collectors with fakes and mocks only.
- The owner then clones the repo onto a personal Mac, where another agent turns on real collection, grants permissions and tunes on real data. So write the macOS collectors fully and carefully now; they get their first real run there. List everything that is untested on real macOS in `docs/BUILD_LOG.md`.

## Read first

1. `docs/design/spec.md` (what it does, rules, commands, config, demo data). **Follow it. If you must deviate, write why in `docs/BUILD_LOG.md`.**

## Step 0 · Check the setup before anything else

1. **DevRelay is scoped to this repo:** `claude mcp list` here shows `devrelay-gateway`; `.agents/skills/` has nine `devrelay-*` skills; `.claude/skills` is a symlink to `../.agents/skills`; `~/.claude/skills` and `~/.agents/skills` have no `devrelay-*`; your tool list includes DevRelay's tools. Don't call any DevRelay tool.
2. **Guards:** `git config user.email` is `165780365+prateek11rai@users.noreply.github.com`; `bash .git/info/leak-check.sh` prints `leak-check: clean`.
3. **Local tools:** `uv --version`, `/opt/homebrew/bin/python3.13 --version`, `ollama list` shows `gemma4:e4b` (the planner started `ollama serve`).

If a check fails, print `BLOCKED-setup: <what>` and wait for the planner. Don't fix setup yourself.

## Already done by the planner

- `git init` on `main`, noreply identity, `.git/info/leak-check.sh` + `.git/info/leak-patterns` (local only; they never get committed).
- DevRelay registered for this repo only; skills in `.agents/skills/devrelay-*` (git-ignored through `.git/info/exclude`); `.claude/skills` → `../.agents/skills`.
- `docs/design/spec.md` and this brief. Commit them in your first commit.

## Dependencies

- Python 3.13 from Homebrew (`.python-version` = `3.13`); uv must never download a Python.
- `pyproject.toml` must have:

  ```toml
  [[tool.uv.index]]
  name = "pypi"
  url = "https://pypi.org/simple"
  default = true

  [tool.uv]
  exclude-newer = "2026-10-17T00:00:00Z"
  python-downloads = "never"
  python-preference = "only-system"
  ```

  (The laptop's user-level uv config points at a private mirror; this block forces public PyPI. `uv.lock` may only mention `pypi.org` and `files.pythonhosted.org`; the leak check enforces it.)
- Runtime, exact pins, stable releases only: `pywebview`, `pyobjc-framework-Cocoa`, `pyobjc-framework-Quartz`, `pyobjc-framework-ApplicationServices` (all with the marker `sys_platform == 'darwin'`), `pydantic`. Dev: `pytest`, `ruff`. Ollama over HTTP with the standard library (`urllib.request`), no client library. TOML with `tomllib`. CLI with `argparse`. SQLite with `sqlite3`.
- Anything else: ask in this window first. No Node, npm, build step, CDN or web fonts (system font stack).

## Code layout (suggested; keep files under ~400 lines)

```
src/munshi/
  cli.py            config.py        store.py (SQLite schema + queries)     redact.py
  collect/  loop.py  macos.py (window, title, idle)  git.py  files.py  fake.py
  write/    slots.py (compact events)  model.py (Ollama + JSON schema)  blocks.py (prompt, checks, fallback)
            notes.py (where / day)  hours.py  journal.py
  ui/       app.py (pywebview windows, js_api)  preview.py (http.server on 127.0.0.1:8765)
            static/  buddy.html  card.html  card.js  theme.css  munshi.svg
  demo.py   evals.py
tests/
```

- Core logic (store, redact, slots, blocks, notes, hours, journal, demo, preview) must import and test on Linux too; macOS modules are imported lazily, only by `start`, `doctor` and their tests (with mocks).
- `card.html` + `card.js` are the same files in the pywebview card and in `munshi preview`: in pywebview they call `window.pywebview.api.*`; in preview a tiny shim calls the preview server's JSON endpoints. One code path for rendering.
- Theme: dark, plain, CSS variables in `theme.css` only (the owner will theme it later). `munshi.svg`: a simple flat munshi (round face, round spectacles, small cap, a ledger), under ~3 KB, made by you, plus a greyed paused variant via CSS.

## Code style (enforced)

- Google-style docstrings on every public function, class and method (Args / Returns / Raises where they apply). ruff: `select = ["E", "F", "W", "I", "B", "UP", "D", "S", "SIM"]`, `[tool.ruff.lint.pydocstyle] convention = "google"`, `D100`/`D104` ignored, tests exempt from `D` and `S101`.
- No header comment blocks at the top of files. A one-line inline comment only where the code can't say it.
- Before every commit: `uv run ruff check`, `uv run ruff format --check`, `uv run pytest -q`, `bash .git/info/leak-check.sh`. Never `--no-verify`; the machine's git hooks stay on.
- Small commits with plain messages; each ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Build, in order

1. **Skeleton:** pyproject (above), `.python-version`, `.gitignore` (`.venv/`, `.data/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.env`), MIT `LICENSE` (2026 prateek11rai), `src/munshi`, console script `munshi`, `uv sync`, `munshi doctor` stub. Commit with the design docs.
2. **Config + store + redact:** config.toml created with comments, env overrides, home mode 700; SQLite schema (events, blocks, topics, notes, state for pause/last-scan) with a schema version; redaction with tests (emails, URLs → host, tokens, long digit runs; PR numbers like `#42` survive).
3. **Collector:** the loop (window every 10 s, git and files every 5 min, idle/away, extend-or-insert, ignore list, only mode, private windows, pause) driven by an injectable clock and source. `fake.py` = scripted source. `macos.py`, `git.py`, `files.py` written for real use and tested with mocks (subprocess calls mocked; no real `git` over real folders, no real `mdfind`). Solve the main-thread/`frontmostApplication` freshness issue and test the choice with a fake.
4. **Writer:** slots, prompt, JSON schema, checks, fallback, merge, project detection, notes (where/day), digit stripping; unit tests with recorded model replies (good, bad ids, invented project, long summary, digits, prompt-injection title). Then one `@pytest.mark.model` test that calls the real local `gemma4:e4b` on one demo slot and asserts the checks hold.
5. **Hours + journal:** code-only numbers, rounding, midnight split, Markdown exactly as in the spec, CSV.
6. **Demo:** `demo load/clear` with the two made-up days (deterministic), already written blocks and notes (from fixed, checked texts so `start --demo` is instant), plus raw events so `write --demo` and `eval` can run the model.
7. **UI:** pywebview buddy (frameless, transparent, on top, draggable, click vs drag, position saved) + card window (hidden until click, placed beside the buddy, Esc hides) + js_api (card data, refresh, pause/resume, forget, copy for timesheet, open journal folder). `munshi preview --demo` serves the same card for a browser.
8. **Eval:** `munshi eval --demo` prints accepted / rejected / fallback counts and seconds per slot for the model; record the real numbers for `gemma4:e4b` in `docs/BUILD_LOG.md`.
9. **CI:** `.github/workflows/test.yml`: job `unit` on `ubuntu-latest` (uv, ruff, pytest without the model marker); job `model` on `ubuntu-latest` installs Ollama with the runner's Homebrew (`/home/linuxbrew/.linuxbrew/bin/brew install ollama`), pulls `gemma4:e4b`, runs `pytest -m model`. `paths-ignore` for `docs/**`, `**/*.md`, images. Never `curl | sh`.
10. **Docs:** `README.md` (what it is in two lines, the lazy promise, privacy in plain words, 60-second start with `--demo`, how it works with a small mermaid diagram, commands, config, swapping the model, limits, license, "built for …" line with the challenge link), `AGENTS.md` at the root (how to run, test, the privacy rules, never run real collection on a work machine, never print config or data), `docs/BUILD_LOG.md` (decisions, eval numbers, the untested-on-real-macOS list, the click-through checklist).

## Acceptance (check these yourself before saying done)

1. Fresh clone: `uv sync --frozen` works; `uv run ruff check`, `uv run ruff format --check`, `uv run pytest` (model test included) pass.
2. `uv run munshi demo load`, then `uv run munshi start --demo`: the buddy appears, a click opens the card filled with demo data, Esc hides it, a drag moves the buddy without opening the card. (Check the process starts and the js_api answers; the planner and owner look at the windows. No desktop screenshots.)
3. `uv run munshi preview --demo`: with Playwright, open http://127.0.0.1:8765, check every part of the card and every button (Refresh, Pause options, Resume, Forget last hour, Copy for timesheet, Open journal is a no-op in preview with a note) changes the page and the demo store, and survives a reload. Screenshot only the Playwright page into `docs/img/` (`card.png`, `card-paused.png`). Write the checklist with ✓/✗ in `docs/BUILD_LOG.md`.
4. `uv run munshi write --demo`, `journal --demo`, `hours --demo --csv`, `eval --demo` work and print sensible output; the journal for the demo's yesterday matches the spec's format.
5. `uv run munshi doctor` runs on this laptop and reports honestly (Accessibility may show ✗; that's fine). `doctor` reads nothing but booleans and versions.
6. Pause and forget work against the demo home and are covered by tests.
7. `bash .git/info/leak-check.sh` says clean; `git log --format='%ae %ce' | sort -u` shows only the noreply address; `git status` is clean; nothing in `~/.munshi` was created by you (demo home only).

## Rules

- No `git push`, no GitHub repo creation, no publishing, no session submission; the planner does those with the owner.
- **Network:** PyPI and the local Ollama only. No `ollama pull`, no other downloads, no global installs, no `curl | sh`, no Docker.
- Never run real collection here (see "Two machines"). Every server listens on 127.0.0.1 only.
- Never read, print or summarise secrets, `.env` files, keychains or other projects' files. Demo data is made up; never real people, companies, customers, tickets or the owner's projects.
- UI copy follows the spec: short and plain.

## Report when done

- Commits (hash + one line), files by area, tests with results, the click-through checklist, the eval numbers.
- The untested-on-real-macOS list, and exactly what the personal-laptop agent must try first.
- Decisions you made alone and why. Open questions, each with your recommendation.

## Stop line

When everything above is done and checked, print exactly `DONE-munshi-base` on its own line and stop. Don't start real collection, push or publish.

## Answers

(The planner adds answers to your questions here.)

**A0 (from the owner, before you start) · The personal laptop is an M1 Mac with 16 GB.** Real collection and the model run there, so keep the running app light: one model (`gemma4:e4b`, `keep_alive` 5m), no second model, the collector itself well under 100 MB and near-zero CPU between polls. Note the memory and CPU you measure in demo mode in `docs/BUILD_LOG.md`.
