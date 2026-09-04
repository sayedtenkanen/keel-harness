"""Tool runtime — ToolResult envelope and tool metadata.

Every tool call returns a ToolResult. The spill layer wraps large payloads.
Tools declare `large_by_nature` so the runtime spills before the model sees
the payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PermissionTier = Literal["read", "write", "exec", "admin"]


@dataclass
class ToolResult:
    """Envelope for tool execution results."""

    tool: str
    ok: bool
    payload: bytes
    tokens: int
    large_by_nature: bool = False
    permission_tier: PermissionTier = "read"
    error: str | None = None


@dataclass
class ToolMeta:
    """Metadata about a registered tool."""

    name: str
    description: str
    args_schema: dict[str, object] = field(default_factory=dict)
    large_by_nature: bool = False
    default_tier: PermissionTier = "read"
