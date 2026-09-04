"""Shared reading helpers for the inspector.

All functions are pure readers: they open files, parse JSON, and return
dataclasses.  No writes, no side effects beyond filesystem reads.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from keel.session.events import AnyEvent
from keel.session.log import EventLog, ReadResult
from keel.store.handles import Handle


@dataclass
class SessionInfo:
    """Summary metadata for a single session."""

    session_id: str
    log_path: Path
    start_time: str
    turns: int
    tool_calls: int
    torn: bool


@dataclass
class TimelineEntry:
    """One event in a human-readable timeline."""

    seq: int
    kind: str
    turn: int | None
    detail: str


def discover_sessions(log_dir: Path) -> list[SessionInfo]:
    """Find all .jsonl logs under *log_dir* and return summary info for each."""
    if not log_dir.is_dir():
        return []
    sessions: list[SessionInfo] = []
    for path in sorted(log_dir.glob("*.jsonl")):
        result = EventLog.read(path)
        if not result.events:
            continue
        first = result.events[0]
        tool_count = sum(1 for e in result.events if e.kind == "tool_called")
        turns = 0
        for e in reversed(result.events):
            if e.kind == "run_ended":
                turns = getattr(e, "turns", 0)
                break
        sessions.append(
            SessionInfo(
                session_id=first.session_id,
                log_path=path,
                start_time=first.ts.isoformat(),
                turns=turns,
                tool_calls=tool_count,
                torn=result.torn,
            )
        )
    return sessions


def read_session(log_path: Path) -> ReadResult:
    """Read a single session log. Thin wrapper around EventLog.read."""
    return EventLog.read(log_path)


def build_timeline(events: list[AnyEvent]) -> list[TimelineEntry]:
    """Convert a list of events into a chronological timeline of entries."""
    entries: list[TimelineEntry] = []
    for event in events:
        entries.append(_event_to_entry(event))
    return entries


def _event_to_entry(event: AnyEvent) -> TimelineEntry:
    from keel.session.events import (
        FinalAnswer,
        ModelCalled,
        ModelResponded,
        PathTraversalRejected,
        RedactionApplied,
        RunEnded,
        RunStarted,
        Spilled,
        ToolCalled,
        ToolDenied,
        ToolResulted,
    )

    kind = event.kind
    seq = event.seq
    turn: int | None = getattr(event, "turn", None)

    if isinstance(event, RunStarted):
        detail = f"session started (model={event.model}, max_turns={event.max_turns})"
    elif isinstance(event, ModelCalled):
        detail = f"model called (turn {event.turn})"
    elif isinstance(event, ModelResponded):
        parts: list[str] = []
        if event.tool_calls:
            parts.append(f"tool_calls={event.tool_calls}")
        if event.final_answer:
            parts.append(f"final_answer={event.final_answer!r}")
        detail = "model responded: " + ", ".join(parts) if parts else "model responded (empty)"
    elif isinstance(event, ToolCalled):
        args_str = ", ".join(f"{k}={v!r}" for k, v in event.args.items())
        detail = f"{event.tool}({args_str})"
    elif isinstance(event, ToolResulted):
        status = "ok" if event.ok else "ERROR"
        spill = ", spilled" if event.spilled else ""
        detail = f"{event.tool} -> {status} ({event.tokens} tokens{spill})"
    elif isinstance(event, Spilled):
        detail = f"spilled to {event.handle_id} ({event.tokens} tokens)"
    elif isinstance(event, FinalAnswer):
        detail = f"final_answer: {event.text!r}"
    elif isinstance(event, RunEnded):
        detail = f"session ended (reason={event.reason}, turns={event.turns})"
    elif isinstance(event, RedactionApplied):
        detail = f"redaction at {event.where}: labels={event.labels}"
    elif isinstance(event, PathTraversalRejected):
        detail = f"path traversal rejected: {event.attempted_path} (tool={event.tool})"
    elif isinstance(event, ToolDenied):
        detail = f"DENIED {event.tool} (required={event.tier}, reason={event.reason})"
    else:
        detail = str(event)

    return TimelineEntry(seq=seq, kind=kind, turn=turn, detail=detail)


def load_store_index(store_dir: Path) -> dict[str, Handle]:
    """Load handle index from a store directory."""
    index_path = store_dir / "index.json"
    if not index_path.exists():
        return {}
    data = json.loads(index_path.read_text(encoding="utf-8"))
    return {k: Handle.model_validate(v) for k, v in data.items()}


def find_session_log(log_dir: Path, session_id: str) -> Path | None:
    """Find the log file for a given session_id."""
    for path in log_dir.glob("*.jsonl"):
        result = EventLog.read(path)
        if result.events and result.events[0].session_id == session_id:
            return path
    return None
