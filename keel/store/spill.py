"""Spill — store large tool results as content-addressed blobs.

Replaces the provisional spill logic in tools/builtin/read.py.
Content is redacted before it reaches the store.
"""

from __future__ import annotations

from dataclasses import dataclass

from keel.ports.store import HandleKind, StorePort
from keel.security.redact import redact
from keel.store.handles import Handle

SPILL_THRESHOLD_TOKENS = 2_000
CHARS_PER_TOKEN = 4


@dataclass
class SpillResult:
    spilled: bool
    handle: Handle | None
    content: str | None
    tokens: int
    redaction_labels: list[str] | None = None


def maybe_spill(content: str, *, store: StorePort, kind: HandleKind, label: str) -> SpillResult:
    """Spill content to the store if it exceeds the threshold."""
    tokens = max(1, len(content) // CHARS_PER_TOKEN)

    if tokens <= SPILL_THRESHOLD_TOKENS:
        return SpillResult(spilled=False, handle=None, content=content, tokens=tokens)

    redacted, matches = redact(content)
    handle = store.put(redacted.encode("utf-8"), kind=kind, label=label, tokens=tokens)

    return SpillResult(
        spilled=True,
        handle=handle,
        content=None,
        tokens=tokens,
        redaction_labels=sorted({m.label for m in matches}) or None,
    )
