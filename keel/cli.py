"""Command-line entry point.

`run` executes a scripted FakeModel session end-to-end (slice 1's walking
skeleton). `verify` reads a session's event log and reports fitness-function
findings. Both grow substantially as later slices land.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from keel import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="keel", description="Keel agent harness")
    parser.add_argument("--version", action="version", version=f"keel {__version__}")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run a scripted session against a model")
    run_p.add_argument("--model", choices=["fake"], default="fake")
    run_p.add_argument("--script", type=Path, required=True, help="YAML script of steps")
    run_p.add_argument(
        "--log",
        type=Path,
        default=None,
        help="Event log path (default: .keel/logs/<session>.jsonl)",
    )
    run_p.add_argument("--max-turns", type=int, default=20)
    run_p.add_argument(
        "--store", type=Path, default=None, help="Store directory (default: .keel/store)"
    )
    run_p.add_argument(
        "--tier",
        choices=["read", "write", "exec", "admin"],
        default="read",
        help="Permission tier for tool calls (default: read)",
    )

    verify_p = sub.add_parser("verify", help="Run fitness functions over an event log")
    verify_p.add_argument("log", type=Path)

    return parser


def _load_script(path: Path) -> tuple[str, list[Any]]:
    from keel.adapters.fake_model import ScriptedFinalAnswer, ScriptedToolCall

    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps: list[Any] = []
    for item in data["steps"]:
        if item["step"] == "tool_call":
            steps.append(ScriptedToolCall(tool=item["tool"], args=item.get("args", {})))
        elif item["step"] == "final_answer":
            steps.append(ScriptedFinalAnswer(text=item["text"]))
        else:
            raise ValueError(f"unknown step kind {item['step']!r} in {path}")
    return str(data.get("session_id", "session")), steps


def _cmd_run(args: argparse.Namespace) -> int:
    from keel.adapters.fake_model import FakeModel
    from keel.kernel.loop import run
    from keel.session.log import EventLog

    session_id, steps = _load_script(args.script)
    log_path: Path = args.log or Path(".keel/logs") / f"{session_id}.jsonl"
    store_dir: Path = args.store or Path(".keel/store")
    log = EventLog(log_path)
    result = run(
        FakeModel(steps),
        log,
        session_id,
        max_turns=args.max_turns,
        store_dir=store_dir,
        allowed_tier=args.tier,
    )

    print(f"session={result.session_id} turns={result.turns} reason={result.reason}")
    if result.final_answer:
        print(result.final_answer)
    print(f"log: {log_path}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    import keel.verify.ff  # noqa: F401  (registers every fitness function)
    from keel.verify.registry import run_on_log

    findings = run_on_log(args.log)
    for finding in findings:
        status = "OK" if finding.ok else "FAIL"
        print(f"[{status}] {finding.ff_id}: {finding.message}")
    return 0 if all(f.ok for f in findings) else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.command == "run":
        return _cmd_run(args)
    if args.command == "verify":
        return _cmd_verify(args)

    parser.print_help()
    return 0
