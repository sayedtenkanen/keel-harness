"""Outline tool — get a summary of content from the store."""

from __future__ import annotations

from dataclasses import dataclass

from keel.ports.store import StorePort

MAX_OUTLINE_LINES = 50


@dataclass
class OutlineResult:
    ok: bool
    outline: str | None
    error: str | None = None


def outline_tool(handle_id: str, *, store: StorePort) -> OutlineResult:
    """Get a summary of content from the store."""
    handle = store.handle(handle_id)
    if handle is None:
        return OutlineResult(ok=False, outline=None, error=f"handle not found: {handle_id}")

    content = store.get(handle)
    text = content.decode("utf-8", errors="replace")
    lines = text.splitlines()

    if len(lines) <= MAX_OUTLINE_LINES:
        outline = text
    else:
        head = "\n".join(lines[:MAX_OUTLINE_LINES])
        outline = f"{head}\n... ({len(lines) - MAX_OUTLINE_LINES} more lines)"

    return OutlineResult(ok=True, outline=outline)
