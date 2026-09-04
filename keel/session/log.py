"""The event log — append-only JSONL, the one artefact everything else derives from.

A torn last line (partial write from a killed process) is detected and
reported, never raised as a crash: SPEC.md §3.10 makes that boundary the
resume point, so a reader has to be able to say exactly where truth ends.
A non-boundary parse failure is a different, harder problem and does raise.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from pydantic import ValidationError

from keel.session.events import EVENT_TYPES, AnyEvent


@dataclass
class ReadResult:
    events: list[AnyEvent]
    torn: bool


class EventLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seq = len(EventLog.read(path).events) if path.exists() else 0

    def emit(self, session_id: str, kind: str, **fields: object) -> AnyEvent:
        event_cls = EVENT_TYPES[kind]
        event = cast(
            AnyEvent,
            event_cls.model_validate({"seq": self._seq, "session_id": session_id, **fields}),
        )
        self._seq += 1
        self._append_raw(event)
        return event

    def _append_raw(self, event: AnyEvent) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())

    @staticmethod
    def read(path: Path) -> ReadResult:
        if not path.exists():
            return ReadResult(events=[], torn=False)
        lines = path.read_text(encoding="utf-8").split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        events: list[AnyEvent] = []
        torn = False
        for i, line in enumerate(lines):
            is_last = i == len(lines) - 1
            try:
                raw = json.loads(line)
                event_cls = EVENT_TYPES[raw["kind"]]
                events.append(cast(AnyEvent, event_cls.model_validate(raw)))
            except (json.JSONDecodeError, KeyError, ValidationError) as exc:
                if is_last:
                    torn = True
                    break
                raise ValueError(f"corrupt event log line {i} in {path} (not at boundary)") from exc
        return ReadResult(events=events, torn=torn)
