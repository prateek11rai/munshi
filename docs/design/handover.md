# Munshi · handover to the personal Mac (phase B)

> For the agent on the owner's personal Mac (M1, 16 GB). Lives at `docs/design/handover.md`. Read `docs/design/spec.md`, `docs/BUILD_LOG.md` and `AGENTS.md` after this file. Don't edit this file; ask in your window if something is unclear.

The base was built on another laptop with demo data and fakes only. **Real collection has never run.** Your job: set the repo up here, turn on real collection, fix what real macOS breaks, tune the model on real data, and get the demo pieces ready. Your session will be published on DEV as the second half of the build ("session B"), so everything you print in this window is public.

Challenge: https://dev.to/challenges/hacktoberfest-week3-2026-10-19, closes **Mon 2026-10-26 12:29 IST**. Stop line: `DONE-munshi-phaseB`.

## The owner does first (before starting you)

1. `brew install python@3.13 uv ollama gh tmux` (skip what's there); Claude Code installed and signed in.
2. `brew services start ollama`, then `ollama pull gemma4:e4b`.
3. `gh auth login`, then `gh repo clone prateek11rai/munshi ~/github/prateek11rai/munshi`.
4. `tmux new -s munshi`, `cd ~/github/prateek11rai/munshi`, `claude`, and send: `Read docs/design/handover.md and do everything in it, in order.` (A fresh session started inside the repo, so the transcript holds only this work.)

## Step 1 · Repo guards

1. `git config user.name prateek11rai` and `git config user.email 165780365+prateek11rai@users.noreply.github.com` (repo-local).
2. `.git/info/exclude` gets: `.agents/skills/devrelay-*/`, `.claude/settings.local.json`, `.env`.
3. Write `.git/info/leak-check.sh` (local only, never committed) that fails when: `git config user.email` isn't the noreply address; any commit's author or committer email isn't the noreply address (or `noreply@github.com`); `.env` is tracked; `uv.lock` mentions a host other than `pypi.org` / `files.pythonhosted.org`; `uv.lock` has no `exclude-newer`; any tracked file or staged line contains `/Users/`, an email address other than noreply ones, or `BEGIN .* PRIVATE KEY`. Print `leak-check: clean` when nothing fails. Run it before every commit.

## Step 2 · DevRelay for this repo only

DevRelay saves agent sessions to DEV. Install it **without** touching any global config:

1. `curl -fsSL https://devrelay.com/install.sh -o "$TMPDIR/devrelay-install.sh"` (download only; never pipe it into a shell). Read it. Confirm it supports `--hosts=none --no-skills --no-auto-update --no-path-update`. If it doesn't, stop and ask the owner.
2. `DO_NOT_TRACK=1 sh "$TMPDIR/devrelay-install.sh" --hosts=none --no-skills --no-auto-update --no-path-update` (the env var only for this one command).
3. The owner logs in: `~/.devrelay/bin/dev_mlh_mcp_server login` (browser).
4. From the repo: `claude mcp add devrelay-gateway --scope local -e DEVRELAY_SKILLS_DIR="$PWD/.agents/skills" -e DEVRELAY_DISABLE_AUTO_UPDATE=1 -- ~/.devrelay/bin/dev_mlh_mcp_server --stdio`. The `DEVRELAY_DISABLE_AUTO_UPDATE=1` matters: on the other laptop, the gateway updated itself on launch (0.1.17 → 0.1.24), installed a LaunchAgent and copied its skills into six global agent folders.
5. `DEVRELAY_SKILLS_DIR="$PWD/.agents/skills" ~/.devrelay/bin/dev_mlh_mcp_server --sync-skills`. `.claude/skills` is already a symlink to `../.agents/skills` in the repo.
6. Check, and check again after the first restart in Step 2.8: `.agents/skills/` has the `devrelay-*` skills and `git status` doesn't show them; none of `~/.claude/skills`, `~/.agents/skills`, `~/.gemini/config/skills`, `~/.codex/skills`, `~/.copilot/skills`, `~/.cursor/skills` has `devrelay-*`; `~/Library/LaunchAgents/com.devrelay.updater.plist` doesn't exist and `launchctl list | grep devrelay` prints nothing; `claude mcp list` from another folder doesn't show `devrelay-gateway`. If anything global appears, stop and tell the owner; don't delete it yourself.
7. Never run `devrelay --doctor` (it re-enables the global updater). Don't submit or publish sessions; the owner does that.
8. Tell the owner to restart `claude` in the repo (`/exit`, then `claude --continue`) so the DevRelay tools load, then go on.

## Step 3 · The base works here

1. `uv sync --frozen`; `uv run ruff check`; `uv run ruff format --check`; `uv run pytest` (the model test included).
2. `uv run munshi doctor`.
3. `uv run munshi demo load`, `uv run munshi start --demo`: ask the owner to confirm the buddy, the click, the card, Esc, and the drag. Fix what's broken, with tests.

## Step 4 · Real collection

1. Ask the owner which folders go in `allowed_roots` and whether `apps.mode` is `all` or `only`. Write `~/.munshi/config.toml` with their answer.
2. Ask the owner to grant Accessibility to the terminal app that runs Munshi (System Settings → Privacy & Security → Accessibility). `doctor` must then show ✓.
3. `uv run munshi start`, and let it run while the owner works. Work through every item on the "untested on real macOS" list in `docs/BUILD_LOG.md` (front app freshness, window titles, idle/away, git scan, Spotlight files, ignore list, private windows, pause, forget, the buddy window, the Dock icon). Fix with tests; one commit per fix.
4. **Privacy in this window:** never print raw events, window titles, file names, paths or commit subjects from `~/.munshi`. Report counts, durations and pass/fail. If you need to look at one real title to debug, ask the owner first and show only that one, redacted.

## Step 5 · Tune on real data

1. Add a mode to `eval` (or a `munshi stats`) that runs over the owner's real day and prints only numbers: slots written, blocks accepted, rejected by which check, fallback rate, seconds per slot, memory and CPU of the running app.
2. Improve the prompt and checks until the fallback rate is low without loosening a check. Record before/after numbers in `docs/BUILD_LOG.md`.
3. Keep the M1 / 16 GB budget: one model, `keep_alive` 5m, the collector near-idle between polls.

## Step 6 · Demo pieces

1. Screenshots for the README use **demo mode** on a clean desktop (`start --demo`); ask the owner before every screenshot, and only of the buddy and the card.
2. The owner records the desktop video (Shift-Cmd-5). You can prepare a short script of clicks for it in `docs/demo/script.md`.
3. Update the README with real, owner-approved numbers (e.g. hours journaled, fallback rate, seconds per slot, memory).
4. Push to `origin main` only when the owner says so. The repo stays private until the owner makes it public.

## Step 7 · Session B (owner decides when)

When the owner asks, prepare the session for DevRelay: from this session's Claude Code transcript, keep the owner's messages, your visible replies and short tool calls; drop thinking, system reminders and long tool output; redact home paths, usernames, the machine name, emails (except noreply), hosts, keys and anything from `~/.munshi`. Show the owner a summary of what was redacted, then submit with `--tool claude_code` only when they say so.

## Rules

- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never `--no-verify`.
- Network: PyPI, the local Ollama, DevRelay/DEV (only for Step 2 and when the owner asks), GitHub through `git`/`gh`. No other downloads, no `curl | sh`, no global installs beyond the owner's list.
- Never read or print secrets, keychains, `.env`, other projects' files, or the owner's activity data (see Step 4).
- Demo data and examples stay made up.

## Report when done

What you fixed (commits), the real-data numbers, what's still rough, and what the owner needs to do for the video and the post. Then print `DONE-munshi-phaseB` on its own line and stop.
