---
# Title candidates (pick one):
# 1. Rewind stopped recording. My 4B munshi keeps my daily register without a single screenshot
# 2. My timesheet now writes itself every 15 minutes, from a 4B model that never leaves my Mac
# 3. One click gives me yesterday and my hours: Gemma 4 e4b keeps the register, code checks every word
title: My hours now write themselves every 15 minutes, from a 4B model that never leaves my Mac
published: false
tags: devchallenge, hf26challenge, opensource, python
cover_image:
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*

## What I Built

A munshi is the clerk who keeps the register: spectacles, a cap, a ledger, and a quiet record of what happened today. Munshi is that clerk as a small buddy on my Mac's desktop.

> At the end of every week I couldn't say where my hours went. My timesheet was guesswork, and I didn't want a cloud app watching my screen to fix that.

It saves three chores I am bad at: writing down what I did, rebuilding yesterday from memory, and guessing where my hours went. Anyone who keeps a log, bills by the hour, studies, writes or ships side projects gets to be lazier. So does anyone who sits down after lunch and wonders what they were doing before it.

The deal is that I do nothing. Every 10 seconds Munshi notes the front app and its window title. Every 5 minutes it reads the git branch, commit subjects and changed file names, only in folders I listed. Every 15 minutes Gemma 4 e4b, running in Ollama on the same Mac, turns each finished slot into blocks of work: a project, a topic and a short summary. When I click the munshi, one card answers four questions: where was I, what did I do today, what did I do yesterday, and how many hours went where. **Copy for timesheet** puts lines like `tidepool · 2.5 h · tide-chart caching, CI fix` on the clipboard. When a day ends, it writes a Markdown journal page and an hours CSV.

No screenshots, no keystrokes, no clipboard reading, no browser history, no file contents. Nothing leaves my Mac.

## Demo

The munshi sits on the desktop at its real size, ![the munshi](https://raw.githubusercontent.com/prateek11rai/munshi/main/docs/img/buddy.png), and one click opens the card beside it:

![The card window: where was I, today's blocks and the actions](https://raw.githubusercontent.com/prateek11rai/munshi/main/docs/img/card-window.png)

The card, on the made-up demo data (the projects tidepool and lantern do not exist):

![The Munshi card: where was I, today, yesterday and hours](https://raw.githubusercontent.com/prateek11rai/munshi/main/docs/img/card.png)

Paused, with yesterday's hours:

![The card while paused, showing yesterday's hours](https://raw.githubusercontent.com/prateek11rai/munshi/main/docs/img/card-paused.png)

## Code

{% github prateek11rai/munshi %}

The demo records nothing, so you can try it in a minute:

```sh
ollama pull gemma4:e4b
git clone https://github.com/prateek11rai/munshi && cd munshi
uv sync
uv run munshi demo load
uv run munshi start --demo
```

## How I Built It

It is one Python 3.13 project managed with uv: pywebview for the two windows (the 88-pixel buddy and the card), PyObjC for the macOS calls, SQLite for the store, and Ollama with `gemma4:e4b` for the words. Dependencies are pinned exactly, and uv's `exclude-newer` keeps new releases out until they have aged.

![How Munshi works: collector, events, writer with Gemma 4 and code checks, blocks, notes, card, journal and hours, all inside the Mac](https://raw.githubusercontent.com/prateek11rai/munshi/main/docs/img/diagrams/architecture.png)

**The collector** reads the front app from NSWorkspace and the focused window's title through the Accessibility API. Three minutes without input starts an "away" stretch. Two details needed care. macOS only refreshes the front app while the main run loop runs, and pywebview owns the main thread, so the read is posted to the main thread and falls back to the window server's list when that is busy. And a terminal titled just "tmux" tells you nothing, so Munshi asks tmux for the active pane's command and repo name (never the path), only inside the folders I listed.

**The writer** takes each finished 15-minute slot, merges repeats, drops away time and gives every item a stable id (`e1`, `e2`, ...). It sends them to Gemma with the list of known projects and existing topics, asks for JSON under a schema at temperature 0, and gets back blocks of `evidence`, `project`, `topic` and `summary`.

Then code checks every block. The evidence ids must exist in that slot. The project must be one I have, and when code already detected the project from an editor title, a terminal or a git event, code wins. The topic is at most four words, must name a subject rather than an app, and must share a word with the evidence or the summary. The summary is at most 14 words and must use words that appear in the evidence. Digits are stripped from anything the model writes.

![One writer run: compact the slot, prompt Gemma, check each block, accept or fall back, then the where-note](https://raw.githubusercontent.com/prateek11rai/munshi/main/docs/img/diagrams/writer-run.png)

A block that fails, a model error or a timeout becomes a plain code-made line such as `Preview · tide-tables-2026.pdf`, so the timeline is never empty. Start, end and minutes always come from the evidence. **Every number on the card comes from code**: durations, hours, counts, "updated 6 min ago". The model only names things.

The privacy rules are code too, and they run before anything is written to disk:

![Where private things are dropped: pause, own window, ignored apps, title words, process words, private windows, redaction, allowed roots, local-only model](https://raw.githubusercontent.com/prateek11rai/munshi/main/docs/img/diagrams/privacy-gates.png)

I run it on the Mac I use for everything, so those gates are not theory. One chat app is on my ignore list. A word I never want in my register is a title word, so any window whose title contains it is never recorded, and repos, branches, commits or file names containing it are dropped. One of my two browser profiles is kept out by a process word: Munshi checks the browser's command line and, for Firefox, the profile folder it has open, so that profile stays out while the other one is recorded.

The last piece was measuring without looking. `munshi stats` and `munshi eval --real` print numbers only: blocks accepted, rejected by which check, fallback rate, seconds per slot, memory. The eval reruns a real day in a scratch copy of the store. The rule for the agent tuning Munshi on my real days was the same: numbers only, never a window title.

The tables are small and plain; the [data model diagram](https://raw.githubusercontent.com/prateek11rai/munshi/main/docs/img/diagrams/data-model.png) shows how blocks cite events and notes cite blocks.

## Why Does Open Innovation Matter?

A log of every window you open is the most private data on your computer. It holds who you talk to, what you read, what you are worried about and what you are paid to do.

Rewind, the Mac app that remembered everything, [stopped capturing on 19 December 2025 after Meta bought its maker](https://9to5mac.com/2025/12/05/rewind-limitless-meta-acquisition/). The record it kept depended on a company, and the company changed hands. That is the risk whenever this kind of record lives on someone else's server or inside someone else's business.

With an open model on my own Mac, the record and the model both stay mine. I can read every line that decides what is recorded, and I can add the rules my situation needs, like a title word for something I never want recorded. No company can change the terms later.

I can also swap the model. Any Ollama model works: `MUNSHI_MODEL=<name>`, then `munshi eval --demo --model <name>` to compare. The checks are the same for every model, so a weaker model means more code-made lines, never wrong numbers.

## My Agent Session

Munshi was built in two halves.

**Session A** is the base: collector, writer, card, journal, tests and docs, built in one evening with made-up demo data and fakes only. Real collection never ran in that session.

{% agent_session 1177 %}

**Session B** turned on real collection behind the privacy filters above and tuned the prompt and the checks, looking only at numbers.

{% agent_session 1182 %}

In both halves one agent session acted as planner, writing the spec and the briefs and reviewing every diff, while builder sessions in other tmux windows wrote the code.

One fix came from elsewhere: commit `cba1f1e`, which retries without constrained JSON when Homebrew's Ollama returns 501, was made by Cursor with Grok on a second Mac.

## The Lazy Payoff

In its first night Munshi journaled 40 minutes of my active time, and 31 minutes away, in 13 blocks. After tuning, Gemma labels about 80 % of the active time and code labels the rest. With the model loaded a slot takes about 9 seconds; the app itself sits at 16 to 45 MB of memory and close to 0 % CPU.

What I did not do: write a note about what I did, scroll back through chat to rebuild Friday, or round my hours to whatever felt right. On Monday I click the munshi and read.

## Prize Categories

**Best Use of Gemma.** Gemma 4 e4b runs locally through Ollama and does the one job a model is good at here: reading a messy slot of window titles, commits and file names and naming what I worked on. Everything around it is deliberately strict. It answers JSON under a schema at temperature 0, it has no tools, window titles are treated as data and never as instructions, and code checks every word it writes before anything reaches the card. A 4B model is enough to label a workday, and small enough that it never has to leave my Mac.
