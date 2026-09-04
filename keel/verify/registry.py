"""The verifier's registry: fitness functions with stable IDs, over the event log only.

Nothing an agent does can reach this module. It is imported by the CLI and by
tests, never by keel/kernel, keel/tools, or keel/orchestrate (slice 13 adds a
test that enforces this import boundary).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from keel.session.events import AnyEvent
from keel.session.log import EventLog


@dataclass
class Finding:
    ff_id: str
    ok: bool
    message: str


FitnessFunction = Callable[[list[AnyEvent]], list[Finding]]

_REGISTRY: dict[str, FitnessFunction] = {}


def register(ff_id: str, fn: FitnessFunction) -> None:
    _REGISTRY[ff_id] = fn


def run_all(events: list[AnyEvent]) -> list[Finding]:
    findings: list[Finding] = []
    for fn in _REGISTRY.values():
        findings.extend(fn(events))
    return findings


def run_on_log(path: Path) -> list[Finding]:
    result = EventLog.read(path)
    findings = run_all(result.events)
    if result.torn:
        findings.append(
            Finding(ff_id="_log_integrity", ok=False, message=f"log {path} ends with a torn line")
        )
    return findings
