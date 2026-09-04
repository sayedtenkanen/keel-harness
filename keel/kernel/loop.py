"""The kernel — deliberately thin: plan -> assemble -> call -> dispatch -> observe.

Slice 1's "assemble" step is trivial (a growing list of dicts); the real
assembler with layout policy and budget lands in slices 7-8. `TOOLS` is a
placeholder for `tools/registry.py` (slice 3), which will also add permission
tiers before anything execs.

Every value written to the event log passes through keel.security.redact
first (tool-call args, final-answer text). The value returned to the caller
(RunResult.final_answer) is the true, unredacted one — redaction guards what
becomes durable, not what the caller does with the answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from keel.adapters.fake_model import FakeModel
from keel.adapters.local_store import LocalStore
from keel.ports.model import ModelRequest
from keel.security.redact import Match, redact
from keel.session.log import EventLog
from keel.tools.builtin.grep import grep_tool
from keel.tools.builtin.outline import outline_tool
from keel.tools.builtin.read import read_tool

TOOLS = {"read": read_tool, "outline": outline_tool, "grep": grep_tool}

DEFAULT_STORE_DIR = Path(".keel/store")


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


def run(
    model: FakeModel,
    log: EventLog,
    session_id: str,
    *,
    max_turns: int = 20,
    store_dir: Path = DEFAULT_STORE_DIR,
) -> RunResult:
    store = LocalStore(store_dir)
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

                tool_fn = TOOLS[call.tool]
                # Filter out extra args that the tool doesn't expect
                import inspect

                sig = inspect.signature(tool_fn)  # type: ignore[arg-type]
                valid_args = {k: v for k, v in call.args.items() if k in sig.parameters}
                result = tool_fn(**valid_args, store=store)  # type: ignore[operator]

                if hasattr(result, "spilled") and result.spilled:
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
                        path=str(store_dir / "blobs" / result.handle.id),
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
                elif hasattr(result, "content"):
                    log.emit(
                        session_id,
                        "tool_resulted",
                        turn=turn,
                        tool=call.tool,
                        ok=result.ok,
                        tokens=result.tokens,
                        spilled=False,
                    )
                    history.append({"tool": call.tool, "content": result.content})
                else:
                    log.emit(
                        session_id,
                        "tool_resulted",
                        turn=turn,
                        tool=call.tool,
                        ok=result.ok,
                        tokens=0,
                        spilled=False,
                    )
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
