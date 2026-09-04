"""Read tool — read content from the store or filesystem.

This replaces the provisional read tool from slice 1 that read from the
filesystem and spilled to a file. Now all reads go through the store.
For backwards compatibility, it also supports reading from the filesystem
and automatically ingesting to the store.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from keel.ports.store import StorePort
from keel.store.handles import Handle
from keel.store.spill import maybe_spill


@dataclass
class ReadResult:
    ok: bool
    content: str | None
    tokens: int
    handle: Handle | None
    spilled: bool = False
    redaction_labels: list[str] | None = None
    error: str | None = None


def read_tool(handle_id: str = "", *, store: StorePort, path: str = "") -> ReadResult:
    """Read content from the store by handle, or from filesystem and ingest."""
    if handle_id:
        handle = store.handle(handle_id)
        if handle is None:
            return ReadResult(
                ok=False,
                content=None,
                tokens=0,
                handle=None,
                error=f"handle not found: {handle_id}",
            )
        content = store.get(handle)
        text = content.decode("utf-8", errors="replace")
        return ReadResult(ok=True, content=text, tokens=handle.tokens, handle=handle)

    if path:
        text = Path(path).read_text(encoding="utf-8")
        spill_result = maybe_spill(text, store=store, kind="tool_result", label=Path(path).name)
        if spill_result.spilled:
            return ReadResult(
                ok=True,
                content=None,
                tokens=spill_result.tokens,
                handle=spill_result.handle,
                spilled=True,
                redaction_labels=spill_result.redaction_labels,
            )
        return ReadResult(ok=True, content=text, tokens=spill_result.tokens, handle=None)

    return ReadResult(
        ok=False, content=None, tokens=0, handle=None, error="no handle_id or path provided"
    )
