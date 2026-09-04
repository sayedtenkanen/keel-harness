"""A deterministic model for tests and the walking skeleton.

Replays a fixed script of steps regardless of what it is asked. It never reads
`request` — that is the point: FakeModel proves the kernel/log/tool wiring
without any of the nondeterminism a real vendor call would introduce.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from keel.ports.model import Capabilities, ModelRequest, ModelResponse, ToolCallRequest


class ScriptedToolCall(BaseModel):
    step: Literal["tool_call"] = "tool_call"
    tool: str
    args: dict[str, object] = {}


class ScriptedFinalAnswer(BaseModel):
    step: Literal["final_answer"] = "final_answer"
    text: str


ScriptedStep = ScriptedToolCall | ScriptedFinalAnswer


class FakeModel:
    def __init__(self, script: list[ScriptedStep]) -> None:
        self._script = list(script)
        self._pos = 0

    def capabilities(self) -> Capabilities:
        return Capabilities(
            max_context_tokens=32_000,
            cache_prefix_semantics="none",
            tool_call_encoding="fake",
            reasoning_blocks_echo=False,
            supported_stop_reasons=["tool_call", "final_answer"],
        )

    def complete(self, request: ModelRequest) -> ModelResponse:
        del request  # FakeModel is scripted, not reactive.
        if self._pos >= len(self._script):
            return ModelResponse(final_answer="")
        step = self._script[self._pos]
        self._pos += 1
        if isinstance(step, ScriptedToolCall):
            return ModelResponse(tool_calls=[ToolCallRequest(tool=step.tool, args=step.args)])
        return ModelResponse(final_answer=step.text)
