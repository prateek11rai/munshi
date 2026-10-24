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
- **Model call.** `/api/chat` with `format` = a JSON schema whose `evidence` ids and `project` names are enums for that slot, `temperature 0`, `num_ctx 8192`, `keep_alive 5m`, `think: false`, 60 s timeout. Each item carries a `project` hint when code already knows it.
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
- Files: `store.py` is 427 lines (mostly docstrings); everything else is under 400.
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

- CI uses `actions/checkout@v4` and `actions/setup-python@v5` by tag; pinning them to commit SHAs needs a lookup I could not do here (network limited to PyPI and the local Ollama). Recommendation: pin to SHAs before the repo goes public.
- The CI model job pulls a multi-GB model on every run (about 10 minutes on a hosted runner). Recommendation: keep it, but trigger it only on changes under `src/munshi/write/` or on a schedule if minutes become a concern.
- `~/.claude/skills` and `~/.agents/skills` on this laptop also hold the nine `devrelay-*` skills (created 22:17, after the repo-scoped copies), which the setup brief says should not be there. I did not touch them and did not call DevRelay.
