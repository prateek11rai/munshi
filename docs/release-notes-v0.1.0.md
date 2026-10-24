# Munshi v0.1.0

The first release of Munshi: a small munshi (a clerk with spectacles, a cap and a ledger) that sits on your Mac's desktop and keeps your daily register. A local open-weight model, Gemma 4 e4b through Ollama, writes it. Nothing leaves your Mac.

![Munshi](https://raw.githubusercontent.com/prateek11rai/munshi/main/docs/img/banner.png)

## What it does

You do nothing. Munshi notes which app, window, repo and files you work on, and every 15 minutes the local model turns that into plain blocks of work. Click the munshi and one card shows:

- **Where was I.** Two sentences about the last two hours, plus facts from code: uncommitted files, the last file, the last page.
- **Today.** Blocks newest first (`14:10–15:15 · tidepool · tide-chart caching`), with away gaps.
- **Yesterday.** Three to five lines by topic and the total active time.
- **Hours.** Bars per project for today or yesterday, rounded to 15 minutes, and **Copy for timesheet** (`tidepool · 2.5 h · tide-chart caching, CI fix`).

Footer buttons: **Refresh now**, **Pause** (30 min, 1 h, until you resume), **Forget last hour**, **Open journal**.

When a day ends, Munshi writes a Markdown journal page (`~/.munshi/journal/YYYY-MM-DD.md`, Obsidian-friendly) and an hours CSV (`~/.munshi/hours/YYYY-MM-DD.csv`).

## Try it in demo mode (records nothing)

Needs macOS, [uv](https://docs.astral.sh/uv/), Python 3.13 and [Ollama](https://ollama.com).

```sh
ollama pull gemma4:e4b
git clone https://github.com/prateek11rai/munshi && cd munshi
uv sync
uv run munshi demo load        # two made-up days (projects tidepool and lantern)
uv run munshi start --demo     # the buddy appears bottom-right; click it
```

**Refresh now** on the card asks the model to write the last three demo slots. Without a Mac, `uv run munshi preview --demo` serves the same card on <http://127.0.0.1:8765>. `uv run munshi eval --demo` runs the writer over both demo days and prints how many blocks the model got right.

To record for real: `uv run munshi doctor`, give your terminal Accessibility permission (so window titles can be read), list your code folders under `allowed_roots` in `~/.munshi/config.toml`, then `uv run munshi start`.

## Privacy, in plain words

- Everything stays on your Mac. The only network call goes to Ollama on your own computer; a remote model address is refused unless you set `allow_remote_model = true` on purpose.
- Munshi records the front app's name, the window title and, for folders you list, the git branch, commit subjects and changed file names. No screenshots, no keystrokes, no clipboard, no browser history, no file contents, no diffs.
- Password managers, Keychain Access, System Settings and the lock screen are never recorded, nor any app you add. Private and incognito windows are recorded as the app name only.
- **Title words:** a window whose title or app name has one of your `ignore_title_words` (a client's name, a private project's codename) is not recorded at all. Repos, branches, commit subjects and file names with one are dropped too.
- **Process words:** an app started with one of your `ignore_process_words` in its command line is not recorded. For Firefox, the name of the open profile folder counts too, so one browser profile stays out while another is recorded.
- Emails, links (only the site name is kept), tokens and long numbers are removed before anything is saved.
- No folder is scanned until you list it. **Pause** stops all recording; **Forget last hour** deletes it.
- Raw window events are deleted after 14 days. The data folder is readable only by you.
- Window titles are data, never instructions. The model has no tools, and code checks every line it writes; anything that fails becomes a plain code-made line.

The diagram of where each thing is dropped: [`docs/img/diagrams/privacy-gates.png`](https://raw.githubusercontent.com/prateek11rai/munshi/main/docs/img/diagrams/privacy-gates.png).

## How the model is kept honest

Every block the model writes is checked by code before it is stored: the evidence ids must exist in that slot, the project must be one you have (the one code detected wins), the topic is at most four words, names a subject rather than an app, and shares a word with the evidence or the summary; the summary is at most 14 words built from words in the evidence. Digits are stripped from model text, and start, end and minutes always come from the evidence. A rejected block, a model error or a timeout becomes a code-made block (`<app> · <title>`), so the timeline is never empty. Every number on screen comes from code.

## What's measured

Commands that print numbers only, never a title or a label:

- `munshi stats`: events by kind, polls recorded or skipped by reason, blocks accepted, rejected by check and fallback, seconds per slot, the running app's memory and CPU.
- `munshi eval --demo` and `munshi eval --real [--day D]` (the real run works on a scratch copy of the store).

On the two demo days (gemma4:e4b, Apple Silicon, from `docs/BUILD_LOG.md`): 64 model blocks accepted, 0 rejected, 9 fallback; 3.8 s per slot on average, 8.1 s at most; the first call after a cold start adds about 17 s to load the model. The app itself: 61 MB and 0.0 % CPU when idle in demo mode.

On the first real night:

| Measure | Value |
|---|---|
| Active time journaled | 40 min (plus 31 min away) |
| Blocks written | 13 |
| Active time labelled by the model | about 80 % (after tuning) |
| Seconds per slot | about 9 with the model loaded; about 24 live, with a cold load |
| App memory | 16 to 45 MB, close to 0 % CPU at rest |

## Known limits

- macOS only for recording; the card preview runs anywhere.
- Window titles need Accessibility permission; without it Munshi records app names only.
- Browser tabs are known only by their window title; there is no browser history.
- Topics are not merged across days yet, there are no animations, and nothing starts at login.
- The card opens on the first screen only.
- Homebrew's Ollama build on Apple Silicon has no constrained JSON output; Munshi then puts the schema in the prompt and parses the reply in code (same checks).
- The model is small. It labels well enough, and the checks keep it honest, but summaries are plain.

## Credits

- [Gemma 4](https://ai.google.dev/gemma) (`gemma4:e4b`), run locally through [Ollama](https://ollama.com).
- [pywebview](https://pywebview.flowrl.com), [PyObjC](https://pyobjc.readthedocs.io), [Pydantic](https://docs.pydantic.dev) and [uv](https://docs.astral.sh/uv/).
- Built with Claude Code. One fix (`cba1f1e`, the retry when Homebrew's Ollama returns 501 for structured output) came from Cursor with Grok on a second Mac.
- Built for the [DEV Hacktoberfest Open-Source AI Challenge, Week 3 "Slow and Steady"](https://dev.to/challenges/hacktoberfest-week3-2026-10-19).

MIT licence.
