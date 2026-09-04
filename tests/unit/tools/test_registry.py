from __future__ import annotations

from keel.tools.registry import ToolRegistry
from keel.tools.runtime import ToolMeta


def test_register_and_get() -> None:
    registry = ToolRegistry()

    def my_tool() -> None:
        pass

    registry.register("my_tool", my_tool)
    assert registry.get("my_tool") is my_tool


def test_get_nonexistent_returns_none() -> None:
    registry = ToolRegistry()
    assert registry.get("nonexistent") is None


def test_meta_from_docstring() -> None:
    registry = ToolRegistry()

    def my_tool() -> None:
        """My tool description."""

    registry.register("my_tool", my_tool)
    meta = registry.meta("my_tool")
    assert meta is not None
    assert meta.description == "My tool description."


def test_meta_explicit() -> None:
    registry = ToolRegistry()

    def my_tool() -> None:
        pass

    meta = ToolMeta(name="my_tool", description="Explicit description", large_by_nature=True)
    registry.register("my_tool", my_tool, meta=meta)
    assert registry.meta("my_tool") is meta
    assert registry.meta("my_tool").large_by_nature is True


def test_list_tools() -> None:
    registry = ToolRegistry()
    registry.register("a", lambda: None)
    registry.register("b", lambda: None)
    assert sorted(registry.list_tools()) == ["a", "b"]


def test_has() -> None:
    registry = ToolRegistry()
    registry.register("a", lambda: None)
    assert registry.has("a") is True
    assert registry.has("b") is False
