"""Grep tool — search content in the store."""

from __future__ import annotations

import json
import re

from keel.ports.store import StorePort
from keel.tools.runtime import ToolResult

MAX_MATCHES = 100


def grep_tool(pattern: str, handle_id: str, *, store: StorePort) -> ToolResult:
    """Search content in the store for a pattern."""
    handle = store.handle(handle_id)
    if handle is None:
        return ToolResult(
            tool="grep",
            ok=False,
            payload=b"",
            tokens=0,
            error=f"handle not found: {handle_id}",
        )

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return ToolResult(
            tool="grep",
            ok=False,
            payload=b"",
            tokens=0,
            error=f"invalid pattern: {e}",
        )

    content = store.get(handle)
    text = content.decode("utf-8", errors="replace")
    lines = text.splitlines()

    matches = []
    for i, line in enumerate(lines, 1):
        if regex.search(line):
            matches.append({"line": i, "text": line})
            if len(matches) >= MAX_MATCHES:
                break

    return ToolResult(
        tool="grep",
        ok=True,
        payload=json.dumps(matches).encode("utf-8"),
        tokens=handle.tokens,
    )
