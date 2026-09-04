from __future__ import annotations

from keel.adapters.local_store import LocalStore
from keel.store.index import StoreIndex


def test_resolve_existing_handle(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    index = StoreIndex(store)
    handle = store.put(b"content", kind="file", label="test", tokens=1)
    resolved = index.resolve(handle.id)
    assert resolved is not None
    assert resolved.id == handle.id


def test_resolve_nonexistent_handle(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    index = StoreIndex(store)
    assert index.resolve("nonexistent") is None


def test_get_returns_content(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    index = StoreIndex(store)
    handle = store.put(b"hello", kind="file", label="test", tokens=1)
    content = index.get(handle)
    assert content == b"hello"


def test_exists(tmp_path: object) -> None:
    store = LocalStore(path=tmp_path)  # type: ignore[arg-type]
    index = StoreIndex(store)
    handle = store.put(b"content", kind="file", label="test", tokens=1)
    assert index.exists(handle.id) is True
    assert index.exists("nonexistent") is False
