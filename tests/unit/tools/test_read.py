from __future__ import annotations

from keel.adapters.local_store import LocalStore
from keel.tools.builtin.read import read_tool


def test_read_returns_content(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    content = b"hello world"
    handle = store.put(content, kind="tool_result", label="test", tokens=1)
    result = read_tool(handle.id, store=store)
    assert result.ok is True
    assert result.payload == b"hello world"
    assert result.tokens == 1


def test_read_unknown_handle(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    result = read_tool("nonexistent", store=store)
    assert result.ok is False
    assert result.error is not None
