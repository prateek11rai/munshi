# Munshi · review 1 (planner)

> Follow-up to `build-brief.md`. Do these in order, then print the stop line. Same rules as the brief.

The planner checked: 110 unit tests pass, ruff clean, leak check clean, noreply only, no `~/.munshi`. The global DevRelay skills you flagged were caused by DevRelay's own self-update (0.1.17 → 0.1.24) when the gateway launched in your window; the planner handles the cleanup with the owner. Don't touch them.

1. **Pin the CI actions to commit SHAs** (looked up by the planner from GitHub, keep the tag as a comment):
   - `actions/checkout@11d5960a326750d5838078e36cf38b85af677262  # v4`
   - `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065  # v5`
2. **CI model job:** run it only when model-facing code or its tests change: a `paths` filter on the `model` job's trigger isn't possible per job, so split it into `.github/workflows/model.yml` with `paths: ["src/munshi/write/**", "tests/test_model_real.py", "pyproject.toml", "uv.lock", ".github/workflows/model.yml"]` plus `workflow_dispatch`. Keep `test.yml` for the unit job.
3. **`docs/design/handover.md`** is new from the planner (for the agent on the owner's personal Mac). Don't edit it; check it against what you built and, if a command, flag or file name in it is wrong, list the fixes in your report instead. Add one line to `AGENTS.md` pointing the next agent at it.
4. **`store.py` is 427 lines:** split it if it's quick and safe (e.g. queries for notes/topics into their own module); otherwise leave it and say so.
5. Commit (one or two commits), run the usual checks and the leak check.

Report: commits, anything wrong in the handover, and confirm `git status` is clean. Then print exactly `DONE-munshi-review1` on its own line and stop.
