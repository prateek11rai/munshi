# Build log · base

Built on 2026-10-24 on the owner's work laptop, demo data and fakes only. Real collection was never run here: no `munshi start` without `--demo`, no real window/idle/git/Spotlight calls outside mocked tests, no `allowed_roots`, no desktop screenshots. `~/.munshi` does not exist on this machine.

## Decisions

- **Front app freshness (the main-thread gotcha).** `NSWorkspace.frontmostApplication` is refreshed by the main run loop, which pywebview owns. The collector thread posts the read to the main thread (`PyObjCTools.AppHelper.callAfter`) and waits up to 2 s (`collect/macos.py: MainThread`). If the main thread is busy, it falls back to the window server's on-screen window list (`CGWindowListCopyWindowInfo`, first layer-0 window not owned by Munshi), which is always current and needs no run loop. Window titles come from Accessibility (`AXFocusedWindow` → `AXTitle`) in the collector thread with a 1 s messaging timeout, so a hung app cannot freeze the UI. `tests/test_collect_macos.py` proves the choice with a fake workspace whose value only refreshes on the main thread: a direct background read is stale, the main-thread read is fresh, and a busy main thread falls back to the window list.
- **No pywebview HTTP server.** The windows load `card.html` and `buddy.html` with their CSS, JS and SVG inlined (`ui/assets.py`), so pywebview never starts its local server (whose JS-API endpoint allows any origin). The same `card.html` + `card.js` files are served by `munshi preview`; `card.js` uses `window.pywebview.api` in the app and a small fetch shim when the preview server sets `window.MUNSHI_PREVIEW`.
- **Preview server hardening.** Binds 127.0.0.1 only; refuses a wrong `Host` (DNS rebinding), a foreign `Origin`, non-JSON posts (so a web page cannot fire a simple cross-site POST at "forget"), and bodies over 4 KB; strict CSP with a per-response nonce.
- **Click vs drag.** pywebview's `easy_drag` moves the frameless buddy natively. JS compares the mouse's screen position on mousedown and mouseup (more than 4 px = drag → save position; else click → toggle card), and Python ignores a toggle within 0.4 s of a move event as a second guard.
- **No Dock icon.** pywebview sets the regular activation policy at import; Munshi switches to "accessory" on the main thread right after the GUI starts. Checked by the self-test (see below).
- **Demo clock.** The demo always opens at 16:05 on its day and runs in real time from the moment of `demo load` (offset stored in the demo store), so the card looks the same whenever it is loaded. The last three slots of the demo's today (15:15–16:00) are left unwritten, so **Refresh now** / `write --demo` has real work for the model. `--demo` commands reload the demo automatically when it is missing or its day has passed.
- **Fixed demo texts are checked.** `tests/test_demo_journal_hours.py` runs every prewritten demo block, the where note and the day note through the same code checks the model faces.
- **Model call.** `/api/chat` with `format` = a JSON schema whose `evidence` ids and `project` names are enums for that slot, `temperature 0`, `num_ctx 8192`, `keep_alive 5m`, `think: false`, 60 s timeout. Each item carries a `project` hint when code already knows it. Homebrew Ollama on Apple Silicon (MLX) returns HTTP 501 `structured output is unavailable` because the formula does not ship `libollama_xgrammar.dylib`. On that 501 the client retries once without `format`, puts the schema in the prompt, and parses the JSON object in code (including a markdown fence). Official Ollama builds still get constrained decoding.
- **One more check than the spec.** A *reused* topic must share a word (or a 3-letter prefix such as "nav" for "navigation") with the evidence or the summary. The model liked to file a PDF under "docs navigation"; this rejects that, and the fallback takes over.
- **Fallback labels are not topics.** A code-made block is labelled `<app> · <shortened title>` (spec) and that label is not added to the topic list the model sees.
- **Evidence ownership.** Each slot item can belong to one accepted block; window items no accepted block covers become fallback blocks, so the timeline always covers all active time. Block time = sum of its window items (overlapping blocks never double count).
- **Merge at read time.** Adjacent blocks with the same project and topic merge for the card and journal (gap ≤ 5 min); stored blocks stay per slot, which keeps forget and citations simple.
- **Away rows** on the card are shown from 5 minutes up.
- **Forget** cuts events that started before the cutoff at the cutoff (instead of deleting a long event whole), deletes events that start inside, deletes overlapping blocks and notes and orphaned topics, and marks the cut slot unwritten so the part before the cutoff is written again. The collector notices its current event was trimmed (conditional update on the last end it wrote) and starts a new one. Today's where note is rewritten by code at once; the next writer run replaces it.
- **Pause** also moves the git "last scan" mark forward while paused, so commits made during a pause are not picked up afterwards.
- **Git** runs with `GIT_OPTIONAL_LOCKS=0`, a 10 s timeout and list arguments (no shell); `git log --since` uses committer time and is re-filtered in code. Only branch, commit subjects and changed file *names* are read. Spotlight results skip hidden folders and anything inside a git repo; at most 20 files per scan.
- **Redaction tokens.** A 24+ run of letters/digits counts as a token (spec); for runs with `_` or `-`, only when one segment is 16+ mixed letters and digits, so long snake_case file names survive while `ghp_…`/`sk_live_…` keys do not.
- **Doctor creates nothing.** It reads the config only if it exists, then prints booleans and versions (and the config path).
- **Day note size.** 3–5 bullets, but a day with fewer than three project/topic groups may have fewer.

## Deviations from the spec (and why)

- `pause`, `resume` and `forget` also accept `--demo`, so they can be tried here without creating `~/.munshi`.
- `eval` also takes `--slots N` for a quick run; `start` has a hidden `--self-test` (below).
- `hours` defaults to today (the spec does not say); `journal` defaults to yesterday as specified.
- Files: all under 400 lines (the SQL schema lives in `schema.py`, the record types in `records.py`).
- `.gitignore` also lists `.claude/skills`, `.claude/settings.local.json` (the planner's local DevRelay setup) and `.playwright-mcp/`, so `git status` stays clean.

## Eval (gemma4:e4b, this laptop)

`uv run munshi eval --demo` (all 53 finished demo slots of both days, model warm after the first call, Apple Silicon work laptop):

```
model gemma4:e4b over 53 demo slots
blocks accepted 64 · rejected 0 · fallback 9
acceptance 100% of model blocks
fallback rate 12% of blocks
seconds per slot: mean 3.8 · max 8.1 · total 200
```

- All 64 model blocks passed every code check. The 9 fallback blocks are window items the model left out of every block (short Preview/Finder/YouTube stretches), which code then labels.
- Before the prompt and topic-check changes, a 3-slot run accepted 4 of 5 blocks but mislabelled topics (a PDF under "docs navigation"); the reused-topic check and the per-item project hints fixed that.
- The where note was rejected once during the click-through (a vague second sentence citing nothing real) and fell back to the code note; after asking for "each sentence names the project and topic of a block" it passed.
- First call after a cold start also loads the model: about 17 s extra.

## Memory and CPU in demo mode

Measured on this laptop with `munshi start --demo` (buddy + hidden card, writer thread idle, no collector):

- App process (Python + pywebview + pyobjc): **61 MB** physical footprint (`footprint`), `ps` RSS 17–33 MB; **0.0 % CPU** when idle, about 1.1 s of CPU in total for start-up over 70 s.
- WebKit runs the two pages in its own helper processes (WebContent ×2, GPU, Networking); the GPU helper was 14 MB. The WebContent helpers could not be measured without extra privileges here.
- Collector cost, estimated with the real loop, the AppKit/Quartz/ApplicationServices bindings loaded and the scripted fake source: **0.6 ms CPU per poll** (a poll every 10 s) and 67 MB peak RSS for a process doing nothing else. Real Accessibility and NSWorkspace reads will add a few milliseconds per poll; check on the personal Mac.
- The model is separate: Ollama keeps `gemma4:e4b` loaded for 5 minutes after a writer run (`keep_alive 5m`), then frees it. Only one model is used.

## Checks run here

- `uv run ruff check`, `uv run ruff format --check`, `uv run pytest` (all tests including the real-model test) pass; `bash .git/info/leak-check.sh` clean.
- `uv run munshi start --demo --self-test` drives the real windows through the JS bridge, no screenshots:

```
self-test: ✓ card data through js_api
self-test: ✓ click opens card
self-test: ✓ card filled
self-test: ✓ Esc hides card
self-test: ✓ drag saves position
self-test: ✓ click right after a drag is ignored
self-test: ✓ no Dock icon (accessory policy)
```

  The "click" and "drag" here are the bridge calls and a programmatic window move; a real mouse drag is on the owner's list below.

## Click-through checklist (`munshi preview --demo`, Playwright, 380 px wide)

| Part or button | Result |
|---|---|
| Where was I: model text, facts line, "updated 6 min ago" | ✓ |
| Today: blocks newest first, away gaps ("away 50 min", "away 15 min") | ✓ |
| Yesterday: three day-note lines, "Active 6 h 45 min" | ✓ |
| Hours: bars for today, switch to Yesterday (3.5 / 1.75 / 1.5 h); choice stored and kept after reload | ✓ |
| Copy for timesheet: shows "Copied" | ✓ |
| Refresh now: "Writing…", then "Wrote 6 blocks."; timeline gains 15:40–16:00; store has the new blocks | ✓ |
| Pause → 30 min / 1 h / Until I resume: badge "Paused until 16:38", Resume shown; kept after reload; `paused_until` in store | ✓ |
| Resume: badge gone, Pause back; kept after reload | ✓ |
| Forget last hour: asks once ("Forget the last hour?"), then deletes; timeline ends 14:10–15:00, where note rewritten by code; kept after reload | ✓ |
| Open journal: preview shows "In the app this opens the journal folder in Finder." | ✓ |
| Close (×): preview shows "In the app this hides the card." | ✓ |
| Console errors | none (after adding the favicon) |

Screenshots of the Playwright page only: `docs/img/card.png`, `docs/img/card-paused.png`.

Note: the Copy check ran in a headed browser, so the made-up demo timesheet text was written to this laptop's clipboard twice.

## Untested on real macOS (first run happens on the personal Mac)

1. `MacWindowSource` against real apps: NSWorkspace via the main thread, the window-list fallback, Accessibility titles (VS Code, Ghostty, Chrome, Safari private windows, an app with no window), the 1 s AX timeout with a hung app.
2. `CGEventSourceSecondsSinceLastEventType` idle values and the 3-minute away switch, including sleep/wake gaps.
3. `GitScanner` on real repos under real allowed roots (depth ≤ 2, worktrees with a `.git` file, a repo with thousands of untracked files, detached HEAD, `--since` across time zones).
4. `FileScanner` with real Spotlight (`mdfind` query syntax with `$time.now(-300)` and `kMDItemContentType != public.folder`, folders excluded from Spotlight, iCloud folders).
5. The collector loop running for hours alongside pywebview: extend vs insert, ignored apps, "only" mode, our own windows ignored by pid.
6. A real mouse: click toggles the card, drag moves the buddy without opening it, position restored after restart; card placement near screen edges and on a second display (only the first screen is used); Esc with the card focused.
7. Transparent buddy background and the paused look on a real desktop (light and dark wallpaper).
8. Clipboard copy from the app window (NSPasteboard) and Open journal in Finder.
9. Accessibility permission flow: which binary needs the grant (Terminal/Ghostty running `uv run`), and doctor's ✗ when it is missing.
10. A day closing at midnight with the app running (journal and CSV written by the first run after midnight).

**What the personal-laptop agent should try first:** `uv sync`, `uv run munshi doctor`, then `uv run munshi start --demo --self-test`; then set `allowed_roots` to one small test folder with a throwaway git repo, `apps.mode = "only"` with two apps, run `uv run munshi start`, switch between those apps for ten minutes, and compare `~/.munshi` events with what happened before turning everything on.

## Open questions

- Resolved in review 1: CI actions are pinned to commit SHAs (looked up by the planner), and the model job moved to `.github/workflows/model.yml`, which runs only when `src/munshi/write/**`, the model test, `pyproject.toml`, `uv.lock` or the workflow itself change, or by hand (`workflow_dispatch`).
- The global `devrelay-*` skills on this laptop came from DevRelay's self-update when the gateway launched; the planner handles the cleanup with the owner.

# Build log · phase B

Real collection on the owner's work laptop, under the owner's rules: every app except Slack and any window of the work browser profile is recorded, and any window whose title contains the work word is dropped. The work word lives only in `~/.munshi/config.toml`; code, tests and docs use `acme`. Nobody reads raw Munshi data here: everything below about the real run comes from `munshi stats` (numbers only) or from the owner's eyes.

## Decisions

- **Title words** (`ignore_title_words`) are checked on the raw title, before redaction, and also on the app name. A hit is handled exactly like an ignored app: the current event is closed and nothing is added. Git repos, branches, commit subjects and changed file names, and Spotlight file names and folders, that contain a word are dropped too (a repo or file event whose name holds the word is dropped whole), so the word cannot reach the store through the scanners.
- **Process words** (`ignore_process_words`): `ps -o command= -p <pid>` with list arguments, no shell, 2 s timeout. Only the yes/no answer is cached, keyed by (pid, app name), so a reused pid with another app is read again; the command line itself is never kept. A failed `ps` counts as no match and is *not* cached, so it is tried again on the next poll rather than letting a work profile through for the rest of the run.
- **Firefox profile folders.** On this laptop both Firefox processes (one per profile) were started with no profile in the command line (the profiles come from Firefox's own switcher) and neither profile folder holds the work word. So for Firefox (bundle `org.mozilla.firefox`, Developer Edition or Nightly; by name when the bundle is unknown) the process check also runs `lsof -w -a -p <pid> -Fn` and matches the words against the profile folder names under `…/Firefox/Profiles/`; the owner's work profile folder name went into `ignore_process_words`. Only yes/no is cached; a failed `lsof`, or no profile folder open yet, is no match and is retried. The front window's bundle id comes from `NSRunningApplication` by pid, which is safe off the main thread.
- **Config is strict now.** Unknown keys are refused (a misspelt `ignore_title_word` must fail loudly, not silently record everything), and config errors name the key, never the value, because the values are private.
- **Skip counters.** Every poll is counted per day by outcome: recorded, private, ignored app, title word, process word, own window, no window, paused, away. They live in a `counters` table (numbers only) and `munshi stats` reads them. Schema version 2 also adds `seconds` and `reasons` to `slots`; a version-1 database gains the columns in place.
- **App status.** `munshi start` stores its pid, the Accessibility flag, RSS and CPU% (`ps -o rss=,%cpu=`) at launch and every 10 minutes; `stats` shows them and whether that pid is still running.
- **501 remembered.** After Homebrew's MLX Ollama answers 501 to `format`, the client never sends `format` again; the card service keeps one client per model so Refresh keeps that knowledge too.
- **`eval --real`** copies the store with SQLite's backup API into a temporary folder, deletes that day's blocks, slot marks and topics first seen since, and rewrites the day's finished slots. The real store is opened read-only and never written. It prints the same numbers as the demo eval.
- **Demo:** `demo load` also writes the made-up yesterday's journal page, so Open journal shows a file. `docs/demo/script.md` is the click script for the screen recording.
- **Terminals in tmux.** WezTerm's title is only `tmux`, so terminal time said nothing ("You were working on WezTerm and tmux"). When a terminal's title is `tmux` or empty, the collector asks tmux for the active pane of the most recently used client and records `<command> — <repo>` (repo = the git root's folder name, only inside an allowed root; the path is never stored). The word checks run on that text. A tab titled by its shell or folder is a plain shell, not tmux, so it is left alone (narrower than "a bare shell name" in the brief, on purpose: such a tab would be misattributed to whatever tmux pane was used last).
- **A topic is a subject, never an app.** A model topic made only of app words is rejected (`topic is an app`); code-made blocks reach the note model as an app (plus their window part when it names something), not as a topic; a note sentence or day bullet must be grounded by a word that is not an app name; when the last two hours hold only app names, the model is not asked and the code says "Mostly in WezTerm for 2 min.".

## First real run (2026-10-25, from 00:40 IST)

What `munshi stats` showed, and what it changed:

- **Profile check:** 2 Firefox app processes, 0 matching on the command line (no profile flag in either), 0 on the folder name. After the folder check and the owner's folder name in the config: 2 processes, exactly 1 matching; the owner confirmed it is the work profile.
- **No memory in stats:** `ps -o rss,%cpu=` keeps the first header, so parsing failed; one `-o name=` per column fixed it (with a test on the real `ps`).
- **A blocked repo name in the project list:** 13 repos under the root, 12 git events: one repo's name holds the work word, so its events were dropped, but `known_projects` still offered its folder name to the model. Fixed before the writer wrote a single real slot.
- **Card footer:** the owner saw Copy for timesheet under the footer buttons. It did not reproduce at 380 × 560 in the browser or in the app window (measured through the JS bridge), so the layout was made defensive and the self-test now measures it.
- **Screenshots by window id** need Screen Recording permission for the terminal on this macOS (`could not create image from window`); the owner chose to skip them and take window shots while recording the demo video.
- Accessibility was already granted to WezTerm; titles are read.
- **Git noise at start-up:** each start of the app reported every repo as changed (the scanner had no memory), and the slot then held a dozen git items for repos nobody was working in; the model answered with a block per git item (12 `no window time` rejections in one slot). The scanner now starts from the last stored git event of each repo.
- **tmux context works:** after the restart at 01:04, `stats` counted 45 polls in 35 minutes whose terminal title came from the tmux pane.
- **Memory and CPU:** right after start RSS 79–91 MB and 34–41 % CPU (start-up, ps's decaying average); at the 10-minute mark 32 MB and 1.1 % CPU.

## Tuning on real data (numbers only)

`uv run munshi eval --real` rewrites today's finished slots in a scratch copy of the store. The real day was young (2–3 slots, two of them holding the start-up git burst), so the real numbers are small and noisy; every change was also checked on the 53 demo slots. No code check was loosened.

| Step | Real slots: accepted · rejected · fallback | Real time labelled by the model | Real s/slot (mean) | Demo: accepted · rejected · fallback | Demo time by model | Demo s/slot |
|---|---|---|---|---|---|---|
| Before (phase-A prompt and schema) | 2 slots: 3 · 4 · 3 | 19 % | 10.7 | 64 · 0 · 9 | 96 % | 3.2 |
| Topic from the block's own words, never an app name | 2 slots: 3 · 14 · 2 | 74 % | 19.3 | n/a | n/a | n/a |
| Window ids as `evidence` (≥ 1), git/file ids as `extra` | 2 slots: 4 · 6 · 3 | 73 % | 9.6 | 61 · 6 · 11 | 95 % | 3.6 |
| Git items only with commits or a repo the windows were in, "never repeat a window id" | 3 slots: 4 · 7 · 6 | 65 % | 6.7 | 60 · 3 · 12 | 95 % | 3.1 |

- The rejections that remain are `no window time` (a block that re-cites a window already taken by an earlier block) and `topic is an app` (terminal stretches recorded before the tmux fix, titled only `tmux`, where no honest topic exists); both fall back to code, which is the point.
- Dropping unrelated git items lowered the model's share on the burst slots (78 % → 65 % with the third slot): those git items gave the model repo words to label terminal windows with, but a repo none of the windows were in cannot truthfully label them. Correctness over coverage; the numbers cannot show which labels were right, so the owner's eyes on the card decide.
- Seconds per slot fell from 19.3 (one block per git item) to 6.7 on real slots.

## The "untested on real macOS" list, on the real run

| Item | How it was checked | Result |
|---|---|---|
| Front app from the main thread | `stats` polls follow the owner's app switches; a 1 s probe through `MacWindowSource` saw each switch within a second | ✓ |
| Window titles (Accessibility) | WezTerm already had Accessibility; the 45 `tmux context` polls only happen when the title `tmux` was read through AX | ✓ |
| Idle and away | away events after 3 min idle, including the owner's 4-minute check | ✓ |
| Git scan of the root | 13 repos read, 0 failures, 0 detached HEAD; the one repo whose name holds the work word is dropped; start-up burst fixed | ✓ (fixed) |
| Spotlight files | the real `mdfind` query runs and finds recent files; all of them sat inside git repos, so 0 file events, as designed | ✓ |
| Collector next to pywebview for hours | polls are continuous: the counters add up to the wall-clock time since start | ✓ |
| Ignore list (Slack) | `ignored app` polls when the owner used Slack; owner: no Slack in the card | ✓ |
| Title words | unit tests with `acme`; no real page with the word was opened | tests only |
| Process words (work Firefox) | profile folder check: 1 of 2 Firefox processes matches, owner confirmed it is the work one | see below |
| Private windows | unit tests only (not asked of the owner) | tests only |
| Buddy, card, Esc, drag, no Dock icon | owner by hand; `start --demo --self-test` in the real window server | ✓ |
| Pause and resume from the card | owner: greyed buddy with the pause mark; `paused` polls stopped recording | ✓ |
| Forget last hour | git and window event counts dropped between two `stats` runs while the counters kept counting | ✓ (inferred) |
| Writer every 15 min | `last writer run` and `slots written` advance every 15 min | ✓ |
| Midnight split | end-to-end test with fakes (`tests/test_midnight.py`) | ✓ |
