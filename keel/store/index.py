"""Store index — resolve handles from the store.

The index provides a clean interface for tools to resolve handles without
directly accessing the store's internal data structures.
"""

from __future__ import annotations

from keel.ports.store import StorePort
from keel.store.handles import Handle


class StoreIndex:
    """Resolve handles from a store."""

    def __init__(self, store: StorePort) -> None:
        self._store = store

    def resolve(self, id: str) -> Handle | None:
        """Resolve a handle ID to a Handle."""
        return self._store.handle(id)

    def get(self, handle: Handle) -> bytes:
        """Get content for a handle."""
        return self._store.get(handle)

    def exists(self, id: str) -> bool:
        """Check if a handle exists."""
        return self._store.handle(id) is not None
