"""Grep tool — search content in the store."""

from __future__ import annotations

import re
from dataclasses import dataclass

from keel.ports.store import StorePort

MAX_MATCHES = 100


@dataclass
class GrepMatch:
    line: int
    text: str


@dataclass
class GrepResult:
    ok: bool
    matches: list[GrepMatch] | None
    total: int
    error: str | None = None


def grep_tool(pattern: str, handle_id: str, *, store: StorePort) -> GrepResult:
    """Search content in the store for a pattern."""
    handle = store.handle(handle_id)
    if handle is None:
        return GrepResult(ok=False, matches=None, total=0, error=f"handle not found: {handle_id}")

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return GrepResult(ok=False, matches=None, total=0, error=f"invalid pattern: {e}")

    content = store.get(handle)
    text = content.decode("utf-8", errors="replace")
    lines = text.splitlines()

    matches = []
    for i, line in enumerate(lines, 1):
        if regex.search(line):
            matches.append(GrepMatch(line=i, text=line))
            if len(matches) >= MAX_MATCHES:
                break

    return GrepResult(ok=True, matches=matches, total=len(matches))
