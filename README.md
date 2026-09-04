# Keel

A context-managed, provider-agnostic agent harness in Python.

A keel does nothing visible and is not what moves the boat. It is what makes
holding a course possible when the wind pushes sideways. That is this project's
relationship to the model it wraps.

**Status:** pre-alpha. The design is settled ([docs/SPEC.md](docs/SPEC.md)); the
implementation follows the slice plan in [docs/SLICE_PLAN.md](docs/SLICE_PLAN.md).
Slices S1, S1a, S2, S3, and S1b are implemented.

## The idea in four sentences

The context window is a cache over an addressable store, never the store
itself. What enters the window, in what order, and under what budget is a fixed
policy the harness owns — not something the model improvises turn by turn.
Everything the harness does is an event in an append-only log, and every claim
about quality ("forgets less", "never lies green") is a function over that log
that runs after the fact. The provider behind the model is a detail; its
declared capabilities are not.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

    git clone https://github.com/sayedtenkanen/keel-harness
    cd keel-harness
    uv sync --extra dev

Vendor adapters are extras: `uv sync --extra anthropic`, `--extra openai`.

## Run

    uv run keel --version
    uv run python -m keel --version

### Available commands

    uv run keel run --model fake --script tests/fixtures/s1.yaml   # run a scripted session
    uv run keel verify <log.jsonl>                                  # run fitness functions on a log
    uv run keel inspect sessions                                    # list all sessions
    uv run keel inspect timeline <session_id>                       # event timeline for a session
    uv run keel inspect store                                       # list store handles
    uv run keel inspect verify <session_id>                         # verify a session by ID

All `keel inspect` subcommands accept `--json` for machine-readable output and
`--dir` to override the default `.keel/logs` or `.keel/store` directory.

## Develop

    uv run pytest                 # unit tests
    uv run pytest -m learning     # learning tests (may need network/credentials)
    uv run ruff check . && uv run ruff format --check .
    uv run mypy

    uv run pre-commit install --hook-type pre-commit --hook-type pre-push  # once

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Layout

    keel/        the package — grows one module per slice, see docs/SPEC.md §5
    keel/inspector/  read-only views over session artifacts (S1b)
    tests/unit   fast, deterministic; run in CI
    tests/learning  pins external dependency behavior; local only
    tests/corpus    task corpus fixtures for the bench
    bench/       baseline harness, tasks, hidden oracles — the thing Keel must beat
    docs/        SPEC.md (design), SLICE_PLAN.md (order of work)

## License

MIT — see [LICENSE](LICENSE).
