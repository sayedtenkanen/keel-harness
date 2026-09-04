"""Read tool — read content from the store or filesystem.

This replaces the provisional read tool from slice 1 that read from the
filesystem and spilled to a file. Now all reads go through the store.
For backwards compatibility, it also supports reading from the filesystem
and automatically ingesting to the store.
"""

from __future__ import annotations

from pathlib import Path

from keel.ports.store import StorePort
from keel.store.spill import maybe_spill
from keel.tools.runtime import ToolResult


def read_tool(handle_id: str = "", *, store: StorePort, path: str = "") -> ToolResult:
    """Read content from the store by handle, or from filesystem and ingest."""
    if handle_id:
        handle = store.handle(handle_id)
        if handle is None:
            return ToolResult(
                ok=False,
                payload=b"",
                tokens=0,
                error=f"handle not found: {handle_id}",
            )
        content = store.get(handle)
        return ToolResult(
            ok=True,
            payload=content,
            tokens=handle.tokens,
            handle=handle,
        )

    if path:
        text = Path(path).read_text(encoding="utf-8")
        spill_result = maybe_spill(text, store=store, kind="tool_result", label=Path(path).name)
        if spill_result.spilled:
            return ToolResult(
                ok=True,
                payload=b"",
                tokens=spill_result.tokens,
                handle=spill_result.handle,
                redaction_labels=spill_result.redaction_labels,
            )
        return ToolResult(
            ok=True,
            payload=text.encode("utf-8"),
            tokens=spill_result.tokens,
        )

    return ToolResult(
        ok=False,
        payload=b"",
        tokens=0,
        error="no handle_id or path provided",
    )
