from __future__ import annotations

from keel.adapters.local_store import LocalStore
from keel.tools.builtin.grep import grep_tool


def test_grep_finds_matches(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    content = b"foo\nbar\nbaz"
    handle = store.put(content, kind="file", label="test.txt", tokens=1)
    result = grep_tool("bar", handle.id, store=store)
    assert result.ok is True
    assert result.matches is not None
    assert len(result.matches) == 1
    assert result.matches[0].line == 2


def test_grep_no_matches(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    content = b"foo\nbar\nbaz"
    handle = store.put(content, kind="file", label="test.txt", tokens=1)
    result = grep_tool("qux", handle.id, store=store)
    assert result.ok is True
    assert result.matches is not None
    assert len(result.matches) == 0


def test_grep_unknown_handle(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    result = grep_tool("pattern", "nonexistent", store=store)
    assert result.ok is False
    assert result.error is not None


def test_grep_invalid_pattern(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    content = b"test"
    handle = store.put(content, kind="file", label="test.txt", tokens=1)
    result = grep_tool("[invalid", handle.id, store=store)
    assert result.ok is False
    assert result.error is not None
