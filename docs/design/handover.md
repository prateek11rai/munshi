# Munshi · handover to the personal Mac (phase B, in Cursor)

> For the agent in **Cursor desktop** on the owner's personal Mac (M1, 16 GB). Lives at `docs/design/handover.md`. Read `docs/design/spec.md`, `docs/BUILD_LOG.md` and `AGENTS.md` after this file. Don't edit this file; ask in the chat if something is unclear.

The base was built on another laptop with demo data and fakes only (that build is **session A**, DEV agent session `1177`, private for now). **Real collection has never run.** Your job: set the repo up here, wire DevRelay into this workspace only, turn on real collection, fix what real macOS breaks, tune the model on real data, and get the demo pieces ready. This chat is **session B**; everything you read, run or print may be shared.

Challenge: https://dev.to/challenges/hacktoberfest-week3-2026-10-19, closes **Mon 2026-10-26 12:29 IST**. Stop line: `DONE-munshi-phaseB`.

## The owner does first (before the first chat message)

1. `brew install python@3.13 uv ollama gh` (skip what's there). Cursor desktop installed and signed in. Recommended: Cursor Settings → General → Privacy Mode on.
2. `brew services start ollama`, then `ollama pull gemma4:e4b`.
3. `gh auth login`, then `gh repo clone prateek11rai/munshi ~/github/prateek11rai/munshi`.
4. In Cursor: File → Open Folder → `~/github/prateek11rai/munshi` (this folder is the workspace). Open a new Agent chat and send: `Read docs/design/handover.md and do everything in it, in order.`

## Step 1 · Repo guards

1. `git config user.name prateek11rai` and `git config user.email 165780365+prateek11rai@users.noreply.github.com` (repo-local).
2. `.git/info/exclude` gets: `.agents/skills/devrelay-*/`, `.cursor/mcp.json`, `.claude/settings.local.json`, `.env`.
3. Write `.git/info/leak-check.sh` (local only, never committed) that fails when: `git config user.email` isn't the noreply address; any commit's author or committer email isn't the noreply address (or `noreply@github.com`); `.env` or `.cursor/mcp.json` is tracked; `uv.lock` mentions a host other than `pypi.org` / `files.pythonhosted.org`; `uv.lock` has no `exclude-newer`; any tracked file or staged line contains `/Users/`, an email address other than noreply ones and the reserved test domains (`example.com`, `example.org`, `example.net`, used by the redaction tests), or `BEGIN .* PRIVATE KEY`. Print `leak-check: clean` when nothing fails. Run it before every commit.

## Step 2 · DevRelay: installed globally, running only in this workspace

DevRelay is the MCP gateway (plus skills) that saves agent sessions to DEV. The program lives in `~/.devrelay`; it must never be wired into Cursor globally, never copy skills into global folders, and never update itself in the background. It runs only when this workspace's chat uses it.

1. `curl -fsSL https://devrelay.com/install.sh -o "$TMPDIR/devrelay-install.sh"` (download only; never pipe it into a shell). Read it. Confirm it supports `--hosts=none --no-skills --no-auto-update --no-path-update`. If it doesn't, stop and ask the owner.
2. `DO_NOT_TRACK=1 sh "$TMPDIR/devrelay-install.sh" --hosts=none --no-skills --no-auto-update --no-path-update` (the env var only for this one command).
3. The owner logs in: `~/.devrelay/bin/dev_mlh_mcp_server login` (browser).
4. Skills into this repo only: `DEVRELAY_SKILLS_DIR="$PWD/.agents/skills" DEVRELAY_DISABLE_AUTO_UPDATE=1 ~/.devrelay/bin/dev_mlh_mcp_server --sync-skills`. Cursor reads project skills from `.agents/skills/` itself; don't create a `.claude/skills` or `.cursor/skills` link (Cursor would load them twice).
5. Wire the gateway into this workspace only: create `.cursor/mcp.json` (git-ignored by step 1.2):

   ```json
   {
     "mcpServers": {
       "devrelay-gateway": {
         "command": "${userHome}/.devrelay/bin/dev_mlh_mcp_server",
         "args": ["--stdio"],
         "env": {
           "DEVRELAY_SKILLS_DIR": "${workspaceFolder}/.agents/skills",
           "DEVRELAY_DISABLE_AUTO_UPDATE": "1"
         }
       }
     }
   }
   ```

   `DEVRELAY_DISABLE_AUTO_UPDATE=1` matters: on the other laptop the gateway updated itself on launch (0.1.17 → 0.1.24), installed a LaunchAgent and copied its skills into six global agent folders.
6. **Make it take effect in this same chat** (it may have been running for a while): ask the owner to (a) open Cursor Settings → MCP / Tools and switch `devrelay-gateway` on, (b) run Cmd-Shift-P → "Developer: Reload Window", (c) reopen this chat from the chat history and say "continue". Chats survive the reload, so this stays one session. Then check that the DevRelay tools (e.g. `list_agent_sessions`) are listed for this chat and that the `devrelay-*` skills show up. Don't call any DevRelay tool beyond that check.
7. Check, now and again after the reload: `.agents/skills/` has the `devrelay-*` skills and `git status` doesn't show them; none of `~/.cursor/skills`, `~/.agents/skills`, `~/.claude/skills`, `~/.codex/skills`, `~/.gemini/config/skills`, `~/.copilot/skills` has `devrelay-*`; `~/.cursor/mcp.json` has no `devrelay`; `~/Library/LaunchAgents/com.devrelay.updater.plist` doesn't exist and `launchctl list | grep devrelay` prints nothing. If anything global appears, stop and tell the owner; don't delete it yourself.
8. Never run `devrelay --doctor` (it re-enables the global updater). Don't submit or publish sessions; the owner decides (Step 7).

## Step 3 · The base works here

1. `uv sync --frozen`; `uv run ruff check`; `uv run ruff format --check`; `uv run pytest` (the model test included).
2. `uv run munshi doctor`.
3. `uv run munshi demo load`, then `uv run munshi start --demo --self-test` (checks card data, click, card fill, Esc, drag saves the position, click after drag, no Dock icon on the real window server), then `uv run munshi start --demo` and ask the owner to confirm the buddy, the click, the card, Esc and the drag by hand. Fix what's broken, with tests.

## Step 4 · Real collection

1. Ask the owner which folders go in `allowed_roots` and whether `apps.mode` is `all` or `only`. Write `~/.munshi/config.toml` with their answer.
2. **Accessibility goes to the app that runs `munshi start`.** Recommended: the owner starts the real Munshi from macOS Terminal (Terminal gets Accessibility in System Settings → Privacy & Security → Accessibility), so Cursor itself never needs it. `munshi doctor` reports the permission of the app it runs in, so for the running Munshi rely on what it records (add a `munshi stats` that reads counts from the store, and have the running app store whether it is trusted).
3. Let it run while the owner works. Work through every item on the "untested on real macOS" list in `docs/BUILD_LOG.md` (front-app freshness, window titles, idle/away, git scan, Spotlight files, ignore list, private windows, pause, forget, the buddy window, the Dock icon, which binary needs the grant). Fix with tests; one commit per fix.
4. **Privacy in this chat:** Cursor sends what you read and what commands print to its model provider. Never open, read, `cat` or query raw data under `~/.munshi` (events, titles, file names, paths, commit subjects, journal text). Use `munshi stats` style numbers: counts, durations, pass/fail. If one real title is needed to debug, ask the owner first; they decide whether to show it, redacted.

## Step 5 · Tune on real data

1. Add a mode to `eval` (or to `munshi stats`) that runs over the owner's real day and prints only numbers: slots written, blocks accepted, rejected by which check, fallback rate, seconds per slot, memory and CPU of the running app.
2. Improve the prompt and checks until the fallback rate is low without loosening a check. Record before/after numbers in `docs/BUILD_LOG.md`.
3. Keep the M1 / 16 GB budget: one model, `keep_alive` 5m, the collector near-idle between polls.

## Step 6 · Demo pieces

1. Screenshots for the README use **demo mode** on a clean desktop (`start --demo`); ask the owner before every screenshot, and only of the buddy and the card.
2. The owner records the desktop video (Shift-Cmd-5). Prepare a short click script for it in `docs/demo/script.md`.
3. Update the README with real, owner-approved numbers (hours journaled, fallback rate, seconds per slot, memory).
4. Push to `origin main` only when the owner says so. The repo stays private until the owner makes it public.

## Step 7 · Session B (owner decides when)

- DEV accepts agent sessions only from these tools: `antigravity_cli`, `claude_code`, `codex`, `gemini_cli`, `github_copilot`, `opencode`, `pi` (DEV's `AgentSession::TOOL_NAMES`). Cursor isn't one of them, so a submit with `tool_name: "cursor"` will most likely be refused. **Never label this chat as another tool.**
- When the owner asks: they export this chat from Cursor (chat menu → Export) to a Markdown file outside the repo. Turn it into DevRelay's normalized JSON (owner messages, your visible replies, short tool calls; drop long tool output; redact home paths, usernames, the machine name, emails except noreply, hosts, keys and anything from `~/.munshi`), show the owner a summary of what was redacted, and only on their word try `submit_agent_session` with `tool_name: "cursor"`. If DEV refuses it, keep the curated Markdown for the owner to link from the post.
- Session A (`1177`) is already on DEV, private. The post embeds it with `{% agent_session 1177 %}`.

## Rules

- Plain, small commits with the noreply identity. Never `--no-verify`.
- Network: PyPI, the local Ollama, DevRelay/DEV (only for Step 2 and when the owner asks), GitHub through `git`/`gh`. No other downloads, no `curl | sh`, no global installs beyond the owner's list.
- Never read or print secrets, keychains, `.env`, other projects' files, or the owner's activity data (Step 4.4).
- Demo data and examples stay made up.

## Report when done

What you fixed (commits), the real-data numbers, what's still rough, and what the owner needs for the video and the post. Then print `DONE-munshi-phaseB` on its own line and stop.
