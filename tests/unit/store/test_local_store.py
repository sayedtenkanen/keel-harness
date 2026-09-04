from __future__ import annotations

import pytest

from keel.adapters.local_store import LocalStore


def test_put_and_get_round_trip(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    content = b"hello world"
    handle = store.put(content, kind="tool_result", label="test", tokens=3)
    assert handle.id
    assert handle.kind == "tool_result"
    assert handle.tokens == 3
    assert handle.label == "test"
    retrieved = store.get(handle)
    assert retrieved == content


def test_identical_content_yields_identical_handle_id(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    content = b"duplicate content"
    h1 = store.put(content, kind="file", label="a", tokens=2)
    h2 = store.put(content, kind="file", label="b", tokens=2)
    assert h1.id == h2.id
    assert h1.sha256 == h2.sha256


def test_different_content_yields_different_handle_id(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    h1 = store.put(b"content A", kind="file", label="a", tokens=1)
    h2 = store.put(b"content B", kind="file", label="b", tokens=1)
    assert h1.id != h2.id


def test_handle_not_found_returns_none(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    assert store.handle("nonexistent") is None


def test_preview_head_and_tail(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    content = b"a" * 1000
    handle = store.put(content, kind="file", label="big", tokens=250)
    assert len(handle.preview_head) > 0
    assert len(handle.preview_tail) > 0


def test_path_traversal_dot_dot_rejected(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="path traversal"):
        store.put(b"evil", kind="file", label="../etc/passwd", tokens=1)


def test_absolute_path_label_rejected(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="path traversal"):
        store.put(b"evil", kind="file", label="/etc/passwd", tokens=1)


def test_backslash_traversal_rejected(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="path traversal"):
        store.put(b"evil", kind="file", label="..\\windows\\system32", tokens=1)
