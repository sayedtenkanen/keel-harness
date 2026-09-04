from __future__ import annotations

from keel.adapters.local_store import LocalStore
from keel.tools.builtin.outline import outline_tool


def test_outline_small_content(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    content = b"line 1\nline 2\nline 3"
    handle = store.put(content, kind="file", label="test.txt", tokens=1)
    result = outline_tool(handle.id, store=store)
    assert result.ok is True
    assert result.outline is not None
    assert "line 1" in result.outline


def test_outline_large_content(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    content = "\n".join([f"line {i}" for i in range(100)]).encode()
    handle = store.put(content, kind="file", label="big.txt", tokens=25)
    result = outline_tool(handle.id, store=store)
    assert result.ok is True
    assert result.outline is not None
    assert "more lines" in result.outline


def test_outline_unknown_handle(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    result = outline_tool("nonexistent", store=store)
    assert result.ok is False
    assert result.error is not None
