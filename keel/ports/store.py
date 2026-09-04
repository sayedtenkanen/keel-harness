"""StorePort — the seam between the kernel and content-addressed storage.

The store is the source of truth; the context window is a cache over it.
All paths resolve through the store, never the raw filesystem — that is
where path-traversal safety lives.
"""

from __future__ import annotations

from typing import Literal, Protocol

from keel.store.handles import Handle

HandleKind = Literal["file", "tool_result", "paste", "handoff", "map", "memory"]


class StorePort(Protocol):
    def put(self, content: bytes, *, kind: HandleKind, label: str, tokens: int) -> Handle: ...

    def get(self, handle: Handle) -> bytes: ...

    def handle(self, id: str) -> Handle | None: ...
