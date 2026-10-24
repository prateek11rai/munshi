# Munshi · phase B on this laptop (real collection, privately)

> Brief for the build agent in tmux `mlh:1`. The planner (`mlh:0`) appends answers at the bottom. Don't edit this file. This window is **session B** (it may be published after curation), so what you print matters.

Repo `~/github/prateek11rai/munshi`, branch `main`. Closes **Mon 2026-10-26 12:29 IST**; aim to finish this brief by **Sun 2026-10-25 06:00 IST**.

## Where things stand

- The base (`build-brief.md`, `review-1.md`) is done: 12 commits by the first build window (session A).
- One commit came from Cursor (Grok) on the owner's personal Mac before its free plan ran out: `cba1f1e`, a retry without Ollama's `format` when Homebrew's MLX Ollama answers HTTP 501. That's why `handover.md` exists; it is **superseded by this brief** (leave it as history).
- Phase B moves back to this laptop. **This is the owner's work laptop**, so real collection now runs here under strict rules (below). The owner chose: record every app except **Slack** and **any Firefox window of the work profile**, and drop any window whose title contains the **work word** (the employer's name). The work word must never appear in the repo, a commit, a test or this window's output: it is a leak-check pattern. The planner has written it into `~/.munshi/config.toml` (the only place it lives); in code, tests and docs use the placeholder `acme`.

## Privacy rules for this window (read twice)

1. **Never read raw Munshi data.** No `cat`, `sqlite3`, `grep`, `head`, editor opens or Python prints of `~/.munshi/**` (events, titles, app lists, file names, paths, commit subjects, blocks, notes, journal, hours). Everything you learn about the real run comes from `munshi stats` (numbers only; you build it in step 2) or from asking the owner.
2. Never print process command lines, Firefox profile names or paths. When you check the profile rule on real processes, print only booleans and counts.
3. **Screenshots:** never the whole screen. Only `munshi preview --demo` pages through Playwright, or a single Munshi window captured by window id (`screencapture -l <id> -o`), and only after the owner says yes for that shot.
4. Demo data and examples stay made up.

## Step 0 · Checks

1. `claude mcp list` here shows `devrelay-gateway`, and its registration has `DEVRELAY_DISABLE_AUTO_UPDATE=1` (in `~/.claude.json` for this project only; print just that key's value). None of `~/.claude/skills`, `~/.agents/skills`, `~/.cursor/skills`, `~/.codex/skills`, `~/.gemini/config/skills`, `~/.copilot/skills` has `devrelay-*`; `~/Library/LaunchAgents/com.devrelay.updater.plist` doesn't exist. Don't call DevRelay tools.
2. `git config user.email` is the noreply address; `bash .git/info/leak-check.sh` is clean; `uv run pytest -q` passes (113); `ollama list` shows `gemma4:e4b` (Ollama 0.35.1 here; **don't upgrade it**).
3. `~/.munshi/config.toml` exists (written by the planner). Don't print it; print only its key names. It may not load until step 1 adds the two new keys.

If something fails: print `BLOCKED-setup: <what>` and wait.

## Step 1 · Privacy features (code + tests, fakes only)

1. **Title words that block recording:** config `ignore_title_words` (list; case-insensitive, contains; tests use `acme`). A front window whose title contains one is **not recorded at all**: treat it exactly like an ignored app (close the current event, add nothing). Checked before redaction. Tests.
2. **Process words that block recording:** config `ignore_process_words` (list; tests use `acme`). For the front app's pid, read its command line once and cache it per pid (`ps -o command= -p <pid>` with list arguments, no shell; any error = no match), and if it contains a word (case-insensitive), the window is not recorded at all. This is how the work Firefox profile (launched with a profile path or name containing the work word) is skipped. Tests with fakes for: a Firefox pid with an `acme` profile path, a Firefox pid without, cache hit, `ps` failure.
3. **Remember the 501:** in `write/model.py`, once Ollama answers 501 for `format`, the client stops sending `format` for its lifetime (one wasted request per process, not per slot). Test.
4. **`munshi stats [--demo] [--day D]`:** numbers only, no text from the data: events by kind and minutes; windows recorded vs skipped by reason (ignored app, title word, process word, private, paused, own window) as counters kept by the collector in the store; slots written; blocks accepted / rejected by which check / fallback; seconds per slot (mean, max); last writer run time; whether the running app has Accessibility (the running `start` stores this flag at launch and every 10 minutes); the running app's RSS and CPU% (`ps` on its pid, stored by the app). Tests.
5. Commit. Usual checks; leak check.

## Step 2 · Real config and first run

1. The planner wrote `~/.munshi/config.toml` (mode 600): `allowed_roots = ["~/github/prateek11rai"]`, `[apps] mode = "all"`, `ignore = ["Slack"]`, and the work word in `ignore_title_words` and `ignore_process_words`. `uv run munshi doctor` must load it. Print key names only, never the word lists.
2. Profile check on real processes: for each running Firefox process, print only `firefox pid-hidden: matches-word=<true|false>`, and the totals. Ask the owner to confirm that the count of matching processes equals the number of work-profile windows they have open. If the work profile doesn't match, stop and ask; don't print command lines to find out why.
3. Ask the owner to grant **Accessibility to WezTerm** (System Settings → Privacy & Security → Accessibility). Then `uv run munshi doctor`. If the managed Mac doesn't allow it, carry on without titles (app names only) and say so.
4. Start the real app in a **new tmux window that you open**, `mlh:munshi` (`tmux new-window -d -t mlh -n munshi -c <repo>`, then send `uv run munshi start`). Never type into any other window. After 2 minutes, `uv run munshi stats` must show window events, the skip counters working, Accessibility as reported, and the app's memory.
5. Ask the owner to check by hand: the buddy appears, click opens the card with their real data, Esc hides it, drag moves it, the Dock has no Munshi icon, and **no Slack or work-Firefox time appears anywhere in the card**. Fix what's broken, with tests.

## Step 3 · Real macOS list

Work through the "untested on real macOS" list in `docs/BUILD_LOG.md` using `stats`, the owner's eyes and tests with fakes: front-app freshness, titles, idle/away (owner leaves the laptop 4 minutes once), git scan of `~/github/prateek11rai`, Spotlight files, ignore list, title and process words, private windows, pause/resume from the card, forget last hour, writer every 15 minutes, the midnight split (unit test is enough). One commit per fix. Restart `mlh:munshi` after code changes (Ctrl-C in that window, then start again).

## Step 4 · Tune on real data (numbers only)

1. Add `munshi eval --real [--day D]`: reruns the writer on the owner's real slots into a scratch copy of the store and prints only numbers (accepted, rejected by check, fallback rate, seconds per slot). Never prints a label, summary or title.
2. Improve the prompt and checks until the fallback rate is low without loosening any check. Record before/after numbers in `docs/BUILD_LOG.md`.

## Step 5 · Demo pieces

1. README screenshots: `docs/img/card.png` and `card-paused.png` already exist from preview. Add `docs/img/buddy.png`: the buddy window alone in demo mode, by window id, after the owner says yes. Optionally the card window by window id in demo mode.
2. `docs/demo/script.md`: a 60–90 s click script for the owner's screen recording in demo mode (clean desktop, other windows hidden): buddy, click, scroll the card, Copy for timesheet, Pause, Resume, Forget last hour, the journal file opening in Finder/Obsidian.
3. README: real, owner-approved numbers (hours journaled so far, accepted/fallback, seconds per slot, memory), the privacy rules in plain words including the new title/process words, the Cursor commit credited in one line ("one fix came from Cursor with Grok on a second Mac").
4. `docs/BUILD_LOG.md`: phase-B section.

## Rules

- No `git push`, publishing or session submission; the owner and planner do those.
- Commits: small, noreply identity, end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never `--no-verify`.
- Network: PyPI and the local Ollama only. No `ollama pull`, no `brew upgrade`, no global installs.
- Write only to your own window and `mlh:munshi`.

## Report when done

Commits, `stats` numbers, before/after tuning numbers, what the owner confirmed by hand, what's still rough. Then print exactly `DONE-munshi-phaseB` on its own line and stop.

## Answers

(The planner adds answers here.)

**A1 (planner) · The work Firefox profile isn't in the command line, so match its profile folder.** Your check showed 2 Firefox app processes (one per profile), no profile flag in either command line, and no folder name containing the work word. So:
- Extend the process check: for a Firefox pid (bundle `org.mozilla.firefox`), find the profile folder that process holds open (`lsof -p <pid> -Fn` with list arguments, no shell; the path under `.../Firefox/Profiles/<folder>/`, e.g. its `.parentlock`), and treat a match of any `ignore_process_words` entry against that **folder name** like a command-line match. Cache only the yes/no per (pid, app). A failed `lsof` = no match, not cached. Never print the path or folder name. Tests with fakes (`acme` folder names).
- The owner will tell the planner the work profile's folder name; the planner adds it to `ignore_process_words` in `~/.munshi/config.toml`. Then rerun your Firefox check (booleans and counts only); the owner confirms exactly one of the two matches.
- **Don't start real collection (step 2.4) until that check shows one match and the planner says go here.** Accessibility is already granted (your doctor ✓), so the owner doesn't need to do anything for that.

**A2 (planner) · The work profile's folder name is now in `~/.munshi/config.toml`** (`ignore_process_words` has 2 entries). Once the folder check from A1 is built and committed, rerun your Firefox check (booleans and counts only). Expected: 2 Firefox app processes, exactly 1 matching. Report that, then continue with step 2.4 (start the real app in `mlh:munshi`) without waiting for another answer, and ask the owner for the hand checks in 2.5.

**A3 (planner, from the owner) · Go.**
- The owner confirms: of the two Firefox instances, the matching one is work and the other is personal (fine to record). **Start step 2.4 now** (`mlh:munshi`, `uv run munshi start`), then `stats` after 2 minutes, then ask the owner for the hand checks in 2.5.
- Screenshots: yes to both, in **demo mode**, each captured by window id only: the buddy window → `docs/img/buddy.png`, the demo card window → `docs/img/card-window.png`. Use a separate demo instance (`MUNSHI_HOME` demo / `start --demo`) so the real app's card is never captured; stop the demo instance afterwards.
- AGENTS.md: yes, update the line. Real collection on a work machine only with the owner's privacy config (ignored apps, title and process words, allowed roots); agents never read raw Munshi data, only `munshi stats` and `eval --real` numbers.
- Note: text in your input box that you didn't receive as a message (e.g. a greyed suggestion) is not an owner answer. Owner answers come through this section.

**A4 (planner, from the owner's screenshots of the real card) · Hand checks pass; two fixes.**
- Seen working: the buddy on screen, click opens the real card, Pause from the card (greyed buddy with the pause mark, "Paused until 01:22"). The owner says things work. Screenshots: **option (c), skip for now**; the README keeps the preview images, and the owner takes window shots in demo mode when recording the video. Don't ask again.
- **Fix 1 · footer covers content.** Scrolled to the bottom, the Hours section's "Copy for timesheet" button sits under the footer buttons. The scroll area must end above the footer (or the footer must not overlap). Check in `preview --demo` with Playwright at the card's real size.
- **Fix 2 · terminals say nothing useful.** WezTerm's title is just `tmux`, so the where-note reads "You were working on WezTerm and tmux. This involved the WezTerm tmux topic." Two changes:
  - When the front app is a terminal and its title is `tmux` (or empty / a bare shell name), ask tmux for the active pane: `tmux display-message -p '#{pane_current_path}'` and `#{pane_current_command}` (list arguments, short timeout, any error = nothing). Keep it only if the path is inside `allowed_roots`, and store the **repo name** (the git root folder name under the root) as the window's context, plus the command name (e.g. `claude`, `uv`, `git`, `vim`); never store the path, and never if the repo name holds a title word. Tests with fakes.
  - Writer and notes: a topic is what was worked on (a repo, a feature, a page), never an app name. Fallback labels such as `WezTerm · tmux` must not be called a topic in the where-note; when only app names are known, the code fallback says it plainly ("Mostly in WezTerm for 2 min") instead of the model inventing a topic.
- Then continue with step 3 (counters as the owner works normally; ask the owner only for the Slack / work-Firefox / 4-minute-away checks, in one short message) and step 4.

**A5 (planner, from the owner) · The owner did the Slack, work-Firefox and 4-minutes-away checks and says they're fine.** Verify them from the skip counters and away events (numbers only), restart the real app in `mlh:munshi` so the new code runs, and continue with step 4 (tuning with `eval --real`, before/after numbers) and the rest. A second agent starts in `mlh:2` on a separate git worktree (`../munshi-ship`, branch `ship`) for the banner, cover, diagrams, release notes and post draft; it doesn't touch `src/`, `tests/`, `README.md` or `docs/BUILD_LOG.md`, so carry on as before. Don't touch that worktree or window.

**A6 (planner, from the owner) · Don't edit `README.md` any more.** The owner wants the README generic (Munshi is multi-purpose: no "work", "employer", "work laptop" or "work profile" wording there). A docs agent in `mlh:3` (worktree `.worktrees/docs`, branch `docs`) now owns the README and will use your `docs/BUILD_LOG.md` numbers; the planner merges it. Skip step 5.3. Keep your numbers and wording in `docs/BUILD_LOG.md` only. The work-Firefox check is still pending with the owner; keep watching the counter, finish everything else, then report and print the stop line (list the check as pending if it hasn't moved). Commit `docs/design/phase-b.md` with your next commit.

**A7 (planner) · Two strings in your files still say "work register".** Make them generic, like the README now is: `pyproject.toml` `description` and the argparse description in `src/munshi/cli.py` (e.g. "A desktop buddy that keeps your daily register with a local open-weight model."). The docs branch is merged into `main` (README, brand images, AGENTS.md wording, handover note); pull nothing, it's the same checkout. Commit this with your next commit.
