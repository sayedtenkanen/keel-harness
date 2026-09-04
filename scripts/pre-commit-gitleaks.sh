#!/usr/bin/env bash
# Best-effort local secret scan. gitleaks is a Go binary, not a pip package,
# and this environment's proxy can't reliably fetch pre-commit's own hosted
# mirror of it (reproducible "Proxy CONNECT aborted" as of Sept 2026 — plain
# git clone/fetch of the same repo works fine outside pre-commit's own
# subprocess invocation; not chased further). CI runs the real gitleaks
# Action on every push regardless, so that stays the authoritative gate.
#
# Install locally for the extra pre-commit speed: `brew install gitleaks`
# (macOS) or see https://github.com/gitleaks/gitleaks#installing.
set -euo pipefail

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "[pre-commit] gitleaks not found on PATH — skipping local secret scan (CI still runs it). Install: brew install gitleaks" >&2
  exit 0
fi

gitleaks protect --staged --redact --config .gitleaks.toml -v
