"""Tool registry — register, look up, and dispatch tools.

Tools are plain functions that return a ToolResult (or a compatible dataclass).
The registry maps tool names to their functions and metadata.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from keel.tools.runtime import ToolMeta


@dataclass
class ToolRegistry:
    """Registry of available tools."""

    _tools: dict[str, Callable[..., object]] = field(default_factory=dict)
    _meta: dict[str, ToolMeta] = field(default_factory=dict)

    def register(
        self,
        name: str,
        fn: Callable[..., object],
        *,
        meta: ToolMeta | None = None,
    ) -> None:
        """Register a tool function with optional metadata."""
        self._tools[name] = fn
        if meta is None:
            meta = ToolMeta(name=name, description=fn.__doc__ or "")
        self._meta[name] = meta

    def get(self, name: str) -> Callable[..., object] | None:
        """Get a tool function by name."""
        return self._tools.get(name)

    def meta(self, name: str) -> ToolMeta | None:
        """Get tool metadata by name."""
        return self._meta.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools


# Global registry instance
REGISTRY = ToolRegistry()
