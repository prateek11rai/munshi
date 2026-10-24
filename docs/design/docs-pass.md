# Munshi · docs pass (README and repo layout)

> Brief for the agent in tmux `mlh:3`. The planner (`mlh:0`) appends answers at the bottom. Don't edit this file.

**Where you work:** only `~/github/prateek11rai/munshi/.worktrees/docs`, a git worktree on branch `docs`. The phase-B agent works on `main` in the parent folder at the same time, and the real Munshi app runs in tmux `mlh:2`: never touch the parent checkout, `~/.munshi`, `src/`, `tests/`, or any other window. Never use `git stash`. Finish by **Sun 2026-10-25 04:00 IST**.

## The owner's rule for the README

**Munshi is multi-purpose.** The README must not say or imply that it is for work, a job, an employer, an office, a work laptop, a work browser profile, standups or a company. It's a personal daily register for anyone: personal projects, study, writing, freelancing, open source, any kind of work or none. Timesheets and invoices can appear only as one example among others ("hours per project, ready to paste wherever you need them"). Don't say "laptop"; say "your Mac" (recording is macOS-only) or "your computer".

Privacy examples become generic: `ignore_title_words` = "a client's name, a private project's codename"; `ignore_process_words` = "keep one browser profile out while another is recorded". Use `acme` in config examples.

## Review against the previous projects

The owner's earlier entries (e.g. `~/github/prateek11rai/overheard`, read-only for you) use this README shape. Read its README once for structure and tone, then rewrite Munshi's README in the same shape:

1. Banner as the first line: `![Munshi: your daily register, kept by a 4B model on your Mac](docs/img/banner.png)` (local relative paths for every image and file in the README, never GitHub URLs).
2. `# Munshi`, then one tagline line, then one short paragraph on what it does.
3. `## Demo`: leave the line `<!-- demo video: the owner drags docs/demo/munshi-demo.mp4 in on github.com -->`, then the two card images (`docs/img/card.png`, `docs/img/card-paused.png`).
4. `## Why`: a log of every window you open is the most private data on a computer; Rewind stopped capturing on 2025-12-19 after Meta bought its maker (link https://9to5mac.com/2025/12/05/rewind-limitless-meta-acquisition/); so a record like this should live on your Mac with a model you can read and swap. No prices or competitor claims you can't source from the repo.
5. `## How it works`: `docs/img/diagrams/architecture.png`, a few bullets (collector, writer + code checks, notes, numbers only from code), links to `writer-run.png`, `privacy-gates.png` and `data-model.png`. Replace the Mermaid block with the PNG.
6. `## Privacy`: the current bullets, made generic as above; embed `docs/img/diagrams/privacy-gates.png` or link it.
7. `## Quick start` (demo first, then real recording: Accessibility, `allowed_roots`, `munshi start`).
8. `## Commands` and `## Config` (keep the tables; generic examples).
9. `## Models` (swap any Ollama model, `eval --demo --model`, the checks are the same for every model; measured numbers from `docs/BUILD_LOG.md`: demo 95 % of active time labelled by the model, about 3 s per slot; real use about 65 % and 6.7 s per slot; about 32 MB of memory and 1 % CPU at rest; say "on an M-series Mac", no other context).
10. `## Honest limits`.
11. `## Built for Hacktoberfest 2026`: the challenge link; `<!-- DEV post link -->`; the two agent sessions (session A: `https://dev.to/agent_sessions/munshi-session-a-building-a-desktop-buddy-that-keeps-a-local-work-journal-work-laptop-demo-data-6bkq8d` is private for now, so write `<!-- session links -->` instead of a URL); the planner/builder split in one line; `docs/BUILD_LOG.md` and `docs/design/`.
12. `## After the deadline`: "Nothing yet." (commits after the deadline get listed here).
13. `## Credits and licence`: MIT; Gemma 4 via Ollama (the model has its own licence, link the Ollama model page `https://ollama.com/library/gemma4`); pywebview and PyObjC; one fix (`cba1f1e`) came from Cursor with Grok on a second Mac; the munshi character was drawn for this project.

Also check the repo layout against the earlier projects and fix only what's clearly off:
- `docs/design/handover.md` was superseded by `phase-b.md`: add one line at its top saying so (keep the file as history).
- `AGENTS.md`: if it repeats work-specific wording, make it generic too (it may keep "a work machine" in the privacy rule only if you can't say it generically; prefer "a shared or managed machine").
- `docs/release-notes-v0.1.0.md` and `docs/devto-post.md`: **don't edit** (the planner handles the post with the owner).
- Brand text: in `docs/brand/*.html`, change "Nothing leaves the laptop." to "Nothing leaves your Mac." and re-render the three images with `docs/brand/render.cjs` exactly as before (same sizes; no downloads). Look at each PNG after rendering.

## Rules

- Leak check before every commit: `bash "$(git rev-parse --git-dir)/info/leak-check.sh"`. Never write the owner's employer's name (a leak pattern).
- Small commits, noreply identity, each ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No push, no network beyond PyPI.
- Every claim in the README must match the code, `docs/BUILD_LOG.md` or the spec; check commands and flags against `src/munshi/cli.py`.

## Report when done

Commits, the final README section list, what you changed in the layout, the re-rendered images. Then print exactly `DONE-munshi-docs` on its own line and stop.

## Answers

(The planner adds answers here.)

**A1 (planner) · One more word.** The brand images still say "Your daily work register". Per the owner's rule, drop "work": "Your daily register, kept by a 4B model on your Mac." Change it in every `docs/brand/*.html` (and anywhere else in your files that says "work register"), re-render the three images the same way, look at each, and commit.
