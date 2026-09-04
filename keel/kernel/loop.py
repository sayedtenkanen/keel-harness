"""The kernel — deliberately thin: plan -> assemble -> call -> dispatch -> observe.

Slice 1's "assemble" step is trivial (a growing list of dicts); the real
assembler with layout policy and budget lands in slices 7-8. Tools are now
registered via the tool registry and checked against permission tiers.

Every value written to the event log passes through keel.security.redact
first (tool-call args, final-answer text). The value returned to the caller
(RunResult.final_answer) is the true, unredacted one — redaction guards what
becomes durable, not what the caller does with the answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from keel.adapters.fake_model import FakeModel
from keel.adapters.local_store import LocalStore
from keel.ports.model import ModelRequest
from keel.security.redact import Match, redact
from keel.session.log import EventLog
from keel.store.errors import PathTraversalError
from keel.tools.builtin.grep import grep_tool
from keel.tools.builtin.outline import outline_tool
from keel.tools.builtin.read import read_tool
from keel.tools.permissions import check_permission
from keel.tools.registry import REGISTRY, ToolRegistry
from keel.tools.runtime import PermissionTier, ToolResult

# Register built-in tools
REGISTRY.register("read", read_tool)
REGISTRY.register("outline", outline_tool)
REGISTRY.register("grep", grep_tool)

DEFAULT_STORE_DIR = Path(".keel/store")

# Typed dispatch table: tool name -> expected argument names
TOOL_ARGS: dict[str, list[str]] = {
    "read": ["handle_id", "path"],
    "outline": ["handle_id"],
    "grep": ["pattern", "handle_id"],
}


@dataclass
class RunResult:
    session_id: str
    turns: int
    final_answer: str | None
    reason: Literal["final_answer", "max_turns"]


def _redact_args_for_log(args: dict[str, object]) -> tuple[dict[str, object], list[Match]]:
    logged: dict[str, object] = {}
    all_matches: list[Match] = []
    for key, value in args.items():
        if isinstance(value, str):
            redacted_value, matches = redact(value)
            logged[key] = redacted_value
            all_matches.extend(matches)
        else:
            logged[key] = value
    return logged, all_matches


def _extract_tool_args(
    tool: str, call_args: dict[str, object]
) -> tuple[dict[str, object], str | None]:
    """Extract valid arguments for a tool, returning error if unknown args present."""
    expected = TOOL_ARGS.get(tool)
    if expected is None:
        return {}, f"unknown tool {tool!r}"

    unknown = set(call_args.keys()) - set(expected)
    if unknown:
        return {}, f"unexpected argument(s) {unknown} for tool {tool!r}"

    valid = {k: v for k, v in call_args.items() if k in expected}
    return valid, None


def run(
    model: FakeModel,
    log: EventLog,
    session_id: str,
    *,
    max_turns: int = 20,
    store_dir: Path = DEFAULT_STORE_DIR,
    allowed_tier: PermissionTier = "read",
    registry: ToolRegistry | None = None,
) -> RunResult:
    store = LocalStore(store_dir)
    if registry is None:
        registry = REGISTRY

    log.emit(session_id, "run_started", model=type(model).__name__, max_turns=max_turns)
    history: list[dict[str, object]] = []
    turn = 0
    final_answer: str | None = None
    reason: Literal["final_answer", "max_turns"] = "max_turns"

    while turn < max_turns:
        log.emit(session_id, "model_called", turn=turn)
        response = model.complete(ModelRequest(messages=history, tools=[]))
        log.emit(
            session_id,
            "model_responded",
            turn=turn,
            tool_calls=[c.tool for c in response.tool_calls],
            final_answer=response.final_answer,
        )

        if response.tool_calls:
            for call in response.tool_calls:
                logged_args, arg_matches = _redact_args_for_log(call.args)
                log.emit(session_id, "tool_called", turn=turn, tool=call.tool, args=logged_args)
                if arg_matches:
                    log.emit(
                        session_id,
                        "redaction_applied",
                        turn=turn,
                        where="tool_called.args",
                        labels=sorted({m.label for m in arg_matches}),
                    )

                # Check permission
                allowed, required_tier, reason_msg = check_permission(
                    call.tool, call.args, allowed_tier=allowed_tier
                )
                if not allowed:
                    log.emit(
                        session_id,
                        "tool_denied",
                        turn=turn,
                        tool=call.tool,
                        args=logged_args,
                        tier=required_tier,
                        reason=reason_msg,
                    )
                    log.emit(
                        session_id,
                        "tool_resulted",
                        turn=turn,
                        tool=call.tool,
                        ok=False,
                        tokens=0,
                        spilled=False,
                    )
                    history.append({"tool": call.tool, "content": f"ERROR: {reason_msg}"})
                    continue

                # Dispatch tool
                tool_fn = registry.get(call.tool)
                if tool_fn is None:
                    log.emit(
                        session_id,
                        "tool_resulted",
                        turn=turn,
                        tool=call.tool,
                        ok=False,
                        tokens=0,
                        spilled=False,
                    )
                    history.append(
                        {"tool": call.tool, "content": f"ERROR: unknown tool {call.tool}"}
                    )
                    continue

                # Extract and validate arguments
                valid_args, arg_error = _extract_tool_args(call.tool, call.args)
                if arg_error:
                    log.emit(
                        session_id,
                        "tool_resulted",
                        turn=turn,
                        tool=call.tool,
                        ok=False,
                        tokens=0,
                        spilled=False,
                    )
                    history.append({"tool": call.tool, "content": f"ERROR: {arg_error}"})
                    continue

                try:
                    result = cast(ToolResult, tool_fn(**valid_args, store=store))
                except PathTraversalError as e:
                    log.emit(
                        session_id,
                        "path_traversal_rejected",
                        turn=turn,
                        attempted_path=str(e),
                        tool=call.tool,
                    )
                    log.emit(
                        session_id,
                        "tool_resulted",
                        turn=turn,
                        tool=call.tool,
                        ok=False,
                        tokens=0,
                        spilled=False,
                    )
                    history.append({"tool": call.tool, "content": f"ERROR: {e}"})
                    continue

                # Handle ToolResult envelope
                if result.handle is not None:
                    # Content was spilled to the store
                    log.emit(
                        session_id,
                        "tool_resulted",
                        turn=turn,
                        tool=call.tool,
                        ok=result.ok,
                        tokens=result.tokens,
                        spilled=True,
                    )
                    log.emit(
                        session_id,
                        "spilled",
                        turn=turn,
                        handle_id=result.handle.id,
                        tokens=result.handle.tokens,
                        blob_path=str(store_dir / "blobs" / result.handle.id),
                    )
                    if result.redaction_labels:
                        log.emit(
                            session_id,
                            "redaction_applied",
                            turn=turn,
                            where=f"spilled:{result.handle.id}",
                            labels=result.redaction_labels,
                        )
                    history.append({"tool": call.tool, "handle_id": result.handle.id})
                else:
                    # Inline content
                    log.emit(
                        session_id,
                        "tool_resulted",
                        turn=turn,
                        tool=call.tool,
                        ok=result.ok,
                        tokens=result.tokens,
                        spilled=False,
                    )
                    if result.payload:
                        content = result.payload.decode("utf-8", errors="replace")
                    else:
                        content = ""
                    if result.error:
                        content = f"ERROR: {result.error}"
                    history.append({"tool": call.tool, "content": content})
            turn += 1
            continue

        if response.final_answer is not None:
            logged_text, text_matches = redact(response.final_answer)
            log.emit(session_id, "final_answer", turn=turn, text=logged_text)
            if text_matches:
                log.emit(
                    session_id,
                    "redaction_applied",
                    turn=turn,
                    where="final_answer.text",
                    labels=sorted({m.label for m in text_matches}),
                )
            final_answer = response.final_answer
            reason = "final_answer"
            turn += 1
            break

        turn += 1

    log.emit(session_id, "run_ended", reason=reason, turns=turn)
    return RunResult(session_id=session_id, turns=turn, final_answer=final_answer, reason=reason)
