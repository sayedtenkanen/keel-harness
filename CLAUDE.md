# Keel — working notes for agents

Read docs/SPEC.md before touching architecture. Read docs/SLICE_PLAN.md before
writing code; work only on the current slice.

## What this is
A provider-agnostic agent harness where the context window is a cache over an
addressable store. Eleven components, three ports (ModelPort, SandboxPort,
StorePort). Package layout is in SPEC.md §5; modules appear as slices land.

## Invariants (do not break)
- Event log is append-only JSONL; SQLite is a rebuildable projection.
- Verifier is human-authored and immutable from any agent path.
- Compaction/handoff records are typed; no free-text summary fields.
- Permission tiers are defined over normalised calls (tool + arg pattern), not tools.
- Children inherit parent permission tiers capped, never widened.
- Live instruction is always the last block in an assembled window.
- Anything written to the event log or spilled to disk passes through
  keel.security.redact first (see keel/kernel/loop.py, keel/tools/builtin/read.py).
  A new write site that skips this is a bug, not a style choice.

## Commands
    uv sync --extra dev
    uv run pytest                       # must be green before any commit
    uv run ruff check . && uv run ruff format .
    uv run mypy
    uv run bandit -c pyproject.toml -r keel   # security static analysis

## Where things live
- Design: docs/SPEC.md   Order of work: docs/SLICE_PLAN.md
- Tests mirror package: keel/context/budget.py -> tests/unit/context/test_budget.py
- Learning tests (external contracts): tests/learning/, marker `learning`, not in CI
- Bench (baseline + corpus + oracles): bench/
- Inspector CLI: keel/inspector/ (read-only views over session artifacts)

## Style
Python 3.11+, pydantic v2, ruff (line 100), mypy strict. Concrete type hints.
No dead code: a helper with no caller does not get merged.
