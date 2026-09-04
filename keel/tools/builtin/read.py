"""The one tool slice 1 needs, and where spill-on-read first happens.

The store proper (content-addressed, path-safe) is slice 2. Here a "Handle" is
provisional: just a content hash and a file under spill_dir. Callers should
not rely on this shape surviving slice 2 — `store/spill.py` replaces it.

Content is redacted (see keel.security.redact) before it is written to a spill
file, since a spilled file is exactly the kind of durable artefact
ff_no_secret_leak / ff_no_sensitive_data_leak treat as a leak if it isn't.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from keel.security.redact import redact

SPILL_THRESHOLD_TOKENS = 2_000
CHARS_PER_TOKEN = 4  # rough approximation; the real tokenizer arrives with a real adapter (slice 5)
PREVIEW_CHARS = 200


@dataclass
class ReadResult:
    ok: bool
    tokens: int
    spilled: bool
    content: str | None
    handle_id: str | None
    path: Path | None
    preview_head: str | None = None
    preview_tail: str | None = None
    redaction_labels: list[str] | None = None


def read_tool(path: str, *, spill_dir: Path) -> ReadResult:
    text = Path(path).read_text(encoding="utf-8")
    tokens = max(1, len(text) // CHARS_PER_TOKEN)
    if tokens <= SPILL_THRESHOLD_TOKENS:
        return ReadResult(
            ok=True, tokens=tokens, spilled=False, content=text, handle_id=None, path=None
        )

    redacted_text, matches = redact(text)
    handle_id = hashlib.sha256(redacted_text.encode("utf-8")).hexdigest()[:16]
    spill_dir.mkdir(parents=True, exist_ok=True)
    dest = spill_dir / f"{handle_id}.txt"
    dest.write_text(redacted_text, encoding="utf-8")
    return ReadResult(
        ok=True,
        tokens=tokens,
        spilled=True,
        content=None,
        handle_id=handle_id,
        path=dest,
        preview_head=redacted_text[:PREVIEW_CHARS],
        preview_tail=redacted_text[-PREVIEW_CHARS:],
        redaction_labels=sorted({m.label for m in matches}) or None,
    )
