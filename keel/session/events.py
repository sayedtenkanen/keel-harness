"""Event schema v1 — frozen at the end of slice 1.

Later slices add new event *kinds*; they do not change these. Every event
carries a monotonic `seq` within its log and the `session_id` that produced
it, so a log can be read on its own without external bookkeeping.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class EventBase(BaseModel):
    seq: int
    ts: datetime = Field(default_factory=lambda: datetime.now(UTC))
    session_id: str


class RunStarted(EventBase):
    kind: Literal["run_started"] = "run_started"
    model: str
    max_turns: int


class ModelCalled(EventBase):
    kind: Literal["model_called"] = "model_called"
    turn: int


class ModelResponded(EventBase):
    kind: Literal["model_responded"] = "model_responded"
    turn: int
    tool_calls: list[str]
    final_answer: str | None


class ToolCalled(EventBase):
    kind: Literal["tool_called"] = "tool_called"
    turn: int
    tool: str
    args: dict[str, object]


class ToolResulted(EventBase):
    kind: Literal["tool_resulted"] = "tool_resulted"
    turn: int
    tool: str
    ok: bool
    tokens: int
    spilled: bool


class Spilled(EventBase):
    kind: Literal["spilled"] = "spilled"
    turn: int
    handle_id: str
    tokens: int
    path: str


class FinalAnswer(EventBase):
    kind: Literal["final_answer"] = "final_answer"
    turn: int
    text: str


class RunEnded(EventBase):
    kind: Literal["run_ended"] = "run_ended"
    reason: Literal["final_answer", "max_turns"]
    turns: int


class RedactionApplied(EventBase):
    """Emitted whenever keel.security.redact found and masked something before a write.

    `where` names the write site (e.g. "tool_called.args", "final_answer.text",
    "spilled:<handle_id>"); `labels` are the pattern labels that matched, never the
    matched text itself.
    """

    kind: Literal["redaction_applied"] = "redaction_applied"
    turn: int
    where: str
    labels: list[str]


AnyEvent = (
    RunStarted
    | ModelCalled
    | ModelResponded
    | ToolCalled
    | ToolResulted
    | Spilled
    | FinalAnswer
    | RunEnded
    | RedactionApplied
)

EVENT_TYPES: dict[str, type[EventBase]] = {
    "run_started": RunStarted,
    "model_called": ModelCalled,
    "model_responded": ModelResponded,
    "tool_called": ToolCalled,
    "tool_resulted": ToolResulted,
    "spilled": Spilled,
    "final_answer": FinalAnswer,
    "run_ended": RunEnded,
    "redaction_applied": RedactionApplied,
}
