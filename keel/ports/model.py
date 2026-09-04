"""ModelPort — the seam between the kernel and a vendor.

Slice 1 keeps this synchronous (one ModelResponse per call) rather than the
streamed-events shape SPEC.md §3.1 describes for the finished port. Streaming
is deferred to slice 5, where a real adapter has something worth streaming;
FakeModel has nothing to gain from it and a sync return keeps slice 1 legible.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel

CachePrefixSemantics = Literal["none", "explicit_breakpoints", "automatic"]


class Capabilities(BaseModel):
    """What a provider can do, declared rather than assumed.

    The assembler (slice 7) branches on this in exactly one place. Nothing
    downstream should special-case a vendor name directly.
    """

    max_context_tokens: int
    cache_prefix_semantics: CachePrefixSemantics
    tool_call_encoding: str
    reasoning_blocks_echo: bool
    supported_stop_reasons: list[str]


class ToolCallRequest(BaseModel):
    tool: str
    args: dict[str, object] = {}


class ModelResponse(BaseModel):
    """Either tool calls to dispatch, or a final answer. Never both."""

    tool_calls: list[ToolCallRequest] = []
    final_answer: str | None = None


class ModelRequest(BaseModel):
    """Assembled input for one model call.

    `messages` is a placeholder for the typed block list SPEC.md §3.5
    describes; slice 7 replaces it with the real assembler output.
    """

    messages: list[dict[str, object]] = []
    tools: list[dict[str, object]] = []


class ModelPort(Protocol):
    def capabilities(self) -> Capabilities: ...

    def complete(self, request: ModelRequest) -> ModelResponse: ...
