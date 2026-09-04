"""Tool runtime — ToolResult envelope and tool metadata.

Every tool call returns a ToolResult. The spill layer wraps large payloads.
Tools declare `large_by_nature` on ToolMeta so the runtime can decide
whether to spill before the model sees the payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from keel.store.handles import Handle

PermissionTier = Literal["read", "write", "exec", "admin"]


@dataclass
class ToolResult:
    """Envelope for tool execution results."""

    ok: bool
    payload: bytes
    tokens: int
    error: str | None = None
    # Spill metadata: set when content was spilled to the store
    handle: Handle | None = None
    redaction_labels: list[str] | None = None


@dataclass
class ToolMeta:
    """Metadata about a registered tool."""

    name: str
    description: str
    args_schema: dict[str, object] = field(default_factory=dict)
    large_by_nature: bool = False
    default_tier: PermissionTier = "read"
