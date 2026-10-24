# Munshi · ship pieces (banner, cover, diagrams, release notes, post draft)

> Brief for the agent in tmux `mlh:2`. The planner (`mlh:0`) appends answers at the bottom. Don't edit this file.

**Where you work:** only `~/github/prateek11rai/munshi-ship`, a git worktree on branch `ship`. Another agent is working on `main` in `~/github/prateek11rai/munshi` (phase B, real data) at the same time: never `cd` there, never touch its files, `~/.munshi`, or any other tmux window. Never use `git stash`.

Challenge: https://dev.to/challenges/hacktoberfest-week3-2026-10-19, closes **Mon 2026-10-26 12:29 IST**. Finish by **Sun 2026-10-25 06:00 IST**.

## Read first

`docs/design/spec.md`, `README.md`, `docs/BUILD_LOG.md`, `src/munshi/ui/static/theme.css`, `src/munshi/ui/static/munshi.svg`, `docs/img/card.png`, `docs/img/card-paused.png`, and the challenge template below.

## You own these files (nothing else)

`docs/brand/**` (HTML sources), `docs/img/banner.png`, `docs/img/devto-cover.png`, `docs/img/social-preview.png`, `docs/img/diagrams/**`, `docs/release-notes-v0.1.0.md`, `docs/devto-post.md`. **Don't edit** `src/`, `tests/`, `README.md`, `AGENTS.md`, `docs/BUILD_LOG.md` or `docs/design/*` (the planner wires the banner into the README at merge time).

## The look: "dark ledger" (owner's choice)

- The app's own colours from `theme.css` (`--bg #17181b`, `--panel #1f2024`, `--line #2e3036`, `--text #e8e6e1`, `--muted #9a9a9f`, `--accent #e0b25c`, `--bar #4f7fb3`), with **faint ruled ledger lines** across the background (like a register's rows, very low contrast) and one thin accent margin rule.
- The munshi character from `munshi.svg`, drawn large and crisp (vector), holding his register.
- System fonts only (`-apple-system`/SF Pro for text, `ui-monospace`/SF Mono for small labels). No web fonts, no CDNs, no network.
- Calm and readable: one name, one tagline, one small supporting line. No emoji, no exclamation marks, no gradients-for-the-sake-of-it.
- Copy (pick the best, keep it short): name **Munshi**; tagline along the lines of "Your daily work register, kept by a 4B model on your Mac"; supporting line "No screenshots. No keystrokes. Nothing leaves the laptop."

## Make, in order

Build each as an HTML file in `docs/brand/`, render to PNG with Playwright at the exact size (device scale 1 for the final file; check a 2x render for crispness), and look at every PNG yourself before committing.

1. **README banner** `docs/img/banner.png`, 1280 × 400: character left, name + tagline right, ledger lines behind.
2. **DEV cover** `docs/img/devto-cover.png`, 1000 × 420. DEV shows it at 1000 × 420, but link previews crop the same file to 1200 × 627 proportions, cutting about 10 % off each side: keep the character, name and tagline inside the middle 80 % of the width.
3. **GitHub social preview** `docs/img/social-preview.png`, 1280 × 640 (the owner uploads it in the repo settings): like the banner plus a small, slightly tilted crop of `docs/img/card.png` (the demo card) on the right.
4. **Diagrams** in `docs/img/diagrams/` (DEV can't render Mermaid, so PNGs), same look, 1600 px wide, readable at 800 px:
   - `architecture.png`: collector (window, idle, git, files, tmux pane) → SQLite events → writer every 15 min (slot → Gemma 4 e4b via Ollama → code checks → accepted block or code fallback) → notes → card, journal, hours CSV. Mark the machine boundary: nothing crosses it.
   - `writer-run.png`: a UML-style sequence of one writer run (compact slot with ids e1…; prompt with known projects and topics; JSON reply; checks: evidence ids exist, project known, topic grounded, summary words in evidence, no digits; accept or fallback; where-note).
   - `privacy-gates.png`: where each thing is dropped before it can be stored: ignored apps, own window, private windows, title words, process / browser-profile words, redaction (emails, URLs → host, tokens, long numbers), allowed roots only for git/files/tmux, local-only model URL. Use `acme` for the example word.
   - `data-model.png`: a UML class-style view of the tables (events, slots, blocks, topics, notes, counters, state) and what links them.
5. **Release notes** `docs/release-notes-v0.1.0.md`: what Munshi does, how to try it in demo mode, privacy in plain words, what's measured (placeholders for numbers), known limits, credits (Gemma 4 via Ollama; one fix from Cursor with Grok on a second Mac).
6. **Post draft** `docs/devto-post.md` (see below).
7. Commit on `ship` in small commits (noreply identity, each ending `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`), after the leak check: `bash "$(git rev-parse --git-dir)/info/leak-check.sh"`.

## The post draft

Front matter: `title:` (put three candidate titles in a comment above it; each names one concrete outcome or number, like the past winners: e.g. "Rewind stopped recording. My 4B munshi keeps my work register without a single screenshot"), `published: false`, `tags: devchallenge, hf26challenge, opensource, python`, `cover_image:` left empty (the planner sets it).

First line: `*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 3: Slow and Steady](https://dev.to/challenges/hacktoberfest-week3-2026-10-19)*`

Sections, in this order: **What I Built** (what effort it saves and who gets to be lazier) · **Demo** (video placeholder `{{VIDEO}}`, plus the card images) · **Code** (`{% github prateek11rai/munshi %}`) · **How I Built It** (Gemma 4 e4b on Ollama, the collector, the writer and its code checks, numbers come only from code, the diagrams) · **Why Does Open Innovation Matter?** (a log of every window you open is the most private data on a computer; Rewind stopped capturing on 2025-12-19 after Meta bought its maker, link https://9to5mac.com/2025/12/05/rewind-limitless-meta-acquisition/; with an open model the record and the model both stay yours; you can swap the model) · **My Agent Session** (two halves: `{% agent_session 1177 %}` for session A, the base built on demo data only, and `{% agent_session {{SESSION_B}} %}` for session B, real collection and tuning; one sentence on the planner/builder split; one line crediting the Cursor commit `cba1f1e`) · **The Lazy Payoff** (real numbers as placeholders: `{{HOURS_JOURNALED}}`, `{{BLOCKS}}`, `{{MODEL_SHARE}}`, `{{SECONDS_PER_SLOT}}`, `{{MEMORY_MB}}`; what it saved this weekend) · **Prize Categories** (Best Use of Gemma).

Voice and rules:
- First person, plain and specific, short paragraphs; about 1,000–1,400 words. No AI-speak ("delve", "seamless", "game-changer", "leverage"), no emoji, no exclamation marks, no em-dash chains.
- It was built on a work laptop: say "my work laptop" and "my employer's name" **without ever naming the employer**. The privacy filters (Slack and a work browser profile never recorded, any window whose title has the employer's name dropped) are a strong, honest part of the story.
- Leave `{{OWNER_WHY}}` where one or two sentences in the owner's own words about why they wanted this belong (near the top).
- Images: reference `https://raw.githubusercontent.com/prateek11rai/munshi/main/docs/img/<file>` (they work once the repo is public and merged).
- Every claim must match the code and `docs/BUILD_LOG.md`; no invented numbers.

## Rules

- No push, no publishing, no DevRelay or DEV calls, no session submission.
- Network: none needed (PyPI only if `uv sync` is required). No downloads.
- Never write the owner's employer's name anywhere; it's a leak-check pattern.
- Screenshots only of your own local HTML pages through Playwright; never the screen.

## Report when done

Commits, every PNG with its size, the three title candidates, the placeholders left, and anything you'd change with more time. Then print exactly `DONE-munshi-ship` on its own line and stop.

## Answers

(The planner adds answers here.)

**A1 (planner, from the owner) · Brand images approved as they are. `{{OWNER_WHY}}`** is this, in the owner's voice (use it verbatim, near the top of the post):

> At the end of every week I couldn't say where my hours went. My timesheet was guesswork, and I didn't want a cloud app watching my screen to fix that.
