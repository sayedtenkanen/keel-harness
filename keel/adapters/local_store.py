"""LocalStore — filesystem-backed, content-addressed blob store.

Implements StorePort. Blobs are stored by their SHA-256 hash; the handle
index is a simple JSON file alongside the blobs directory.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from keel.ports.store import HandleKind
from keel.security.redact import redact
from keel.store.errors import PathTraversalError
from keel.store.handles import Handle

CHARS_PER_TOKEN = 4
PREVIEW_CHARS = 200


def _is_safe_label(label: str) -> bool:
    """Reject path traversal attempts in labels."""
    if label.startswith("/") or label.startswith("\\"):
        return False
    return ".." not in label.split("/") and ".." not in label.split("\\")


class LocalStore:
    """Content-addressed blob store on the local filesystem."""

    def __init__(self, path: Path) -> None:
        self._root = path
        self._blobs = path / "blobs"
        self._index = path / "index.json"
        self._blobs.mkdir(parents=True, exist_ok=True)
        self._handles: dict[str, Handle] = self._load_index()

    def _load_index(self) -> dict[str, Handle]:
        if self._index.exists():
            data = json.loads(self._index.read_text())
            return {k: Handle.model_validate(v) for k, v in data.items()}
        return {}

    def _save_index(self) -> None:
        data = {k: v.model_dump() for k, v in self._handles.items()}
        self._index.write_text(json.dumps(data, indent=2))

    def put(self, content: bytes, *, kind: HandleKind, label: str, tokens: int) -> Handle:
        if not _is_safe_label(label):
            raise PathTraversalError(f"path traversal detected in label: {label}")

        # Guard against binary content that can't be decoded as UTF-8
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as e:
            raise NotImplementedError(
                "binary content is not yet supported; only UTF-8 text can be stored"
            ) from e

        redacted, _ = redact(text)
        raw = redacted.encode("utf-8")

        sha = hashlib.sha256(raw).hexdigest()
        handle_id = sha[:16]

        blob_path = self._blobs / handle_id
        if not blob_path.exists():
            blob_path.write_bytes(raw)

        preview_head = raw[:PREVIEW_CHARS].decode("utf-8", errors="replace")
        if len(raw) > PREVIEW_CHARS:
            preview_tail = raw[-PREVIEW_CHARS:].decode("utf-8", errors="replace")
        else:
            preview_tail = raw.decode("utf-8", errors="replace")

        handle = Handle(
            id=handle_id,
            kind=kind,
            tokens=tokens,
            sha256=sha,
            label=label,
            preview_head=preview_head,
            preview_tail=preview_tail,
        )

        existing = self._handles.get(handle_id)
        if existing is None:
            self._handles[handle_id] = handle
            self._save_index()

        return self._handles[handle_id]

    def get(self, handle: Handle) -> bytes:
        blob_path = self._blobs / handle.id
        if not blob_path.exists():
            raise FileNotFoundError(f"blob not found: {handle.id}")
        return blob_path.read_bytes()

    def handle(self, id: str) -> Handle | None:
        return self._handles.get(id)
