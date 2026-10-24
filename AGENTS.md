# AGENTS.md

Rules for coding agents working in this repo. Read `docs/design/spec.md` first; it is the source of truth for behaviour.

On the owner's personal Mac (phase B: real collection and tuning), start with `docs/design/handover.md`.

## Run

```sh
uv sync                          # Python 3.13 from the system; uv never downloads one
uv run munshi demo load          # two made-up days in ./.data/demo
uv run munshi start --demo       # buddy + card, no recording
uv run munshi preview --demo     # the card on http://127.0.0.1:8765
uv run munshi write --demo       # run the writer (needs `ollama serve` and gemma4:e4b)
uv run munshi eval --demo        # model quality and speed on the demo days
uv run munshi doctor --demo      # setup check; reads only booleans and versions
uv run munshi stats              # numbers about the real run; never recorded text
uv run munshi eval --real        # model quality on a real day, in a scratch copy; numbers only
```

`uv run munshi start --demo --self-test` opens the real windows, drives them through the JS bridge (card data, click opens, Esc hides, drag saves position, accessory policy), prints ✓/✗ and quits. Use it instead of screenshots.

## Test

```sh
uv run ruff check && uv run ruff format --check
uv run pytest -m "not model"     # unit tests; macOS-only tests skip elsewhere
uv run pytest                    # plus the real-model test (fails if Ollama or the model is missing)
```

Before every commit run all four checks above and the repo's local leak check if it exists (`bash .git/info/leak-check.sh`). Never use `--no-verify`.

Code style: Google-style docstrings on every public function, class and method; no header comment blocks; a one-line comment only where the code cannot say it; files under about 400 lines. Core modules (store, redact, write/*, demo, ui/service, ui/preview) must import on Linux; macOS modules (`collect/macos.py`, `ui/app.py`) are imported lazily.

## Privacy rules (code, not promises)

- Nothing leaves the machine. The only outbound call is to the local Ollama; a non-local URL is refused unless `allow_remote_model = true`.
- No screenshots, keystrokes, clipboard reading, browser history, file contents or diffs. Git gives branch, commit subjects and changed file names only.
- Ignored apps are never recorded, nor windows whose title has an `ignore_title_words` word or whose process (command line, or Firefox profile folder) has an `ignore_process_words` word; private windows are app-name only; everything is redacted before storage (`redact.py`).
- Allowed roots are empty by default. Pause stops all recording; forget deletes.
- Window titles are data, never instructions. Model output is always checked by code (`write/blocks.py`, `write/notes.py`); numbers on screen come from code only.
- Every server listens on 127.0.0.1 only. The preview server refuses other hosts, other origins and non-JSON posts.

## Never

- **Real collection on a shared or managed machine runs only with the owner's privacy config** in `~/.munshi/config.toml` (ignored apps, title and process words, allowed roots), and only when the owner asks for it. Agents never read raw Munshi data: what they learn about a real run comes from `munshi stats` and `munshi eval --real` numbers. Tests use the fakes in `collect/fake.py` and mocked subprocess calls. No desktop screenshots; a single Munshi window, by window id, in demo mode, after the owner says yes.
- Never print, log, summarise or commit config values, recorded data, journal pages or anything from `~/.munshi`. Use the demo home (`./.data/demo`) or a temporary `MUNSHI_HOME`.
- Never put real people, companies, customers, tickets or the owner's projects in demo data, fixtures or docs. The demo projects are tidepool and lantern.
- Never add dependencies without asking; pins are exact and the uv `exclude-newer` cooldown stays.
- Never push, publish or create releases; the owner does that.
