# Contributing

## Setup

    uv sync --extra dev
    uv run pre-commit install --hook-type pre-commit --hook-type pre-push
    uv run pytest

The pre-commit hook runs ruff, mypy, bandit, and a best-effort gitleaks scan on
every commit; pytest runs on push instead, since it's the one check slow enough
to be worth deferring. All of it mirrors `.github/workflows/ci.yml` exactly — see
`.pre-commit-config.yaml` if a hook and CI ever disagree, that file is the bug.

## How work is organised

Keel is built in vertical TDD slices ([docs/SLICE_PLAN.md](docs/SLICE_PLAN.md)).
A slice is done when its listed tests pass, its fitness functions are registered,
and the events it introduces are documented in `docs/SPEC.md`. Slices are
sequenced; do not start slice N+1 while slice N has red tests.

## Rules that are not negotiable

- Anything about to become durable (an event log line, a spilled file) is
  scanned and redacted by `keel.security.redact` before the write. If you add a
  new write site for tool args, model output, or store content, redact it there
  too — don't rely on the verifier's `ff_no_secret_leak` / `ff_no_sensitive_data_leak`
  to catch it after the fact; those exist as a backstop, not a substitute.

- The verifier (`keel/verify/`) is human-authored. No code path reachable from an
  agent may write to it.
- The event log is append-only JSONL. Nothing reads the SQLite index to make a
  decision the JSONL could not reconstruct.
- Compaction and handoff produce typed records. No free-text summary fields.
- Every schema lives under `keel/schemas/vN/`; a version bump ships with a
  migration test.

## Before opening a PR

    uv run ruff check . && uv run ruff format .
    uv run mypy
    uv run bandit -c pyproject.toml -r keel
    uv run pytest

Learning tests (`tests/learning/`) are excluded from CI. If you touched an
adapter, run them locally and say so in the PR.

## Commits

Conventional-ish: `slice-03: permission tiers over normalised calls`. One slice
may span several commits; one commit never spans two slices.
