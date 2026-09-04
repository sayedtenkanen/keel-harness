"""Outline tool — get a summary of content from the store."""

from __future__ import annotations

from keel.ports.store import StorePort
from keel.tools.runtime import ToolResult

MAX_OUTLINE_LINES = 50


def outline_tool(handle_id: str, *, store: StorePort) -> ToolResult:
    """Get a summary of content from the store."""
    handle = store.handle(handle_id)
    if handle is None:
        return ToolResult(
            ok=False,
            payload=b"",
            tokens=0,
            error=f"handle not found: {handle_id}",
        )

    content = store.get(handle)
    text = content.decode("utf-8", errors="replace")
    lines = text.splitlines()

    if len(lines) <= MAX_OUTLINE_LINES:
        outline = text
    else:
        head = "\n".join(lines[:MAX_OUTLINE_LINES])
        outline = f"{head}\n... ({len(lines) - MAX_OUTLINE_LINES} more lines)"

    return ToolResult(
        ok=True,
        payload=outline.encode("utf-8"),
        tokens=handle.tokens,
    )
