from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Handle(BaseModel):
    """Content-addressed blob reference. Frozen at the end of S2."""

    id: str
    kind: Literal["file", "tool_result", "paste", "handoff", "map", "memory"]
    tokens: int
    sha256: str
    label: str
    preview_head: str
    preview_tail: str
