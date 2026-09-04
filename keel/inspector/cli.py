"""Inspector CLI — read-only views over session logs, store handles, and fitness findings.

All commands are read-only: they open files, parse JSON, and print.  No writes
to the store, the event log, or any other durable surface.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from keel.inspector.reader import (
    build_timeline,
    discover_sessions,
    find_session_log,
    load_store_index,
    read_session,
)


def register_inspect(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``inspect`` subcommand and its sub-subcommands."""
    inspect_p = sub.add_parser("inspect", help="Read-only views over session artifacts")
    insub = inspect_p.add_subparsers(dest="inspect_command")

    # --- sessions ---
    sess_p = insub.add_parser("sessions", help="List all sessions found under a log directory")
    sess_p.add_argument(
        "--dir",
        type=Path,
        default=Path(".keel/logs"),
        help="Directory containing .jsonl logs (default: .keel/logs)",
    )
    sess_p.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit JSON instead of a table",
    )

    # --- timeline ---
    tl_p = insub.add_parser("timeline", help="Show a chronological timeline of a session")
    tl_p.add_argument("session_id", help="Session id to inspect")
    tl_p.add_argument(
        "--dir",
        type=Path,
        default=Path(".keel/logs"),
        help="Directory containing .jsonl logs (default: .keel/logs)",
    )
    tl_p.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit JSON instead of human-readable text",
    )

    # --- store ---
    store_p = insub.add_parser("store", help="List or inspect handles in the store")
    store_p.add_argument(
        "--dir",
        type=Path,
        default=Path(".keel/store"),
        help="Store directory (default: .keel/store)",
    )
    store_sub = store_p.add_subparsers(dest="store_command")
    show_p = store_sub.add_parser("show", help="Show full metadata for a handle")
    show_p.add_argument("handle_id", help="Handle id to inspect")
    show_p.add_argument(
        "--dir",
        type=Path,
        default=Path(".keel/store"),
        help="Store directory (default: .keel/store)",
    )

    # --- verify ---
    verify_p = insub.add_parser("verify", help="Run fitness functions against a session")
    verify_p.add_argument("session_id", help="Session id to verify")
    verify_p.add_argument(
        "--dir",
        type=Path,
        default=Path(".keel/logs"),
        help="Directory containing .jsonl logs (default: .keel/logs)",
    )
    verify_p.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit JSON instead of a table",
    )


def cmd_inspect(args: argparse.Namespace) -> int:
    """Dispatch to the correct inspect sub-subcommand."""
    command = getattr(args, "inspect_command", None)
    if command == "sessions":
        return _cmd_sessions(args)
    if command == "timeline":
        return _cmd_timeline(args)
    if command == "store":
        return _cmd_store(args)
    if command == "verify":
        return _cmd_verify(args)
    print("usage: keel inspect {sessions,timeline,store,verify} ...", file=sys.stderr)
    return 1


# ── sessions ────────────────────────────────────────────────────────────────


def _cmd_sessions(args: argparse.Namespace) -> int:
    log_dir: Path = args.dir
    as_json: bool = args.as_json
    sessions = discover_sessions(log_dir)
    if not sessions:
        print(f"No sessions found in {log_dir}")
        return 0

    if as_json:
        records = [
            {
                "session_id": s.session_id,
                "log_path": str(s.log_path),
                "start_time": s.start_time,
                "turns": s.turns,
                "tool_calls": s.tool_calls,
                "torn": s.torn,
            }
            for s in sessions
        ]
        print(json.dumps(records, indent=2))
        return 0

    # Human-readable table
    header = f"{'SESSION':<20} {'STARTED':<28} {'TURNS':>5} {'TOOLS':>5} {'STATUS':<10}"
    print(header)
    print("-" * len(header))
    for s in sessions:
        status = "TORN" if s.torn else "clean"
        print(f"{s.session_id:<20} {s.start_time:<28} {s.turns:>5} {s.tool_calls:>5} {status:<10}")
    return 0


# ── timeline ────────────────────────────────────────────────────────────────


def _cmd_timeline(args: argparse.Namespace) -> int:
    log_dir: Path = args.dir
    session_id: str = args.session_id
    as_json: bool = args.as_json

    log_path = find_session_log(log_dir, session_id)
    if log_path is None:
        print(f"session {session_id!r} not found in {log_dir}", file=sys.stderr)
        return 1

    result = read_session(log_path)
    entries = build_timeline(result.events)

    if result.torn:
        print(
            "WARNING: log ends with a torn last line (partial write)\n",
            file=sys.stderr,
        )

    if as_json:
        records = [
            {"seq": e.seq, "kind": e.kind, "turn": e.turn, "detail": e.detail} for e in entries
        ]
        print(json.dumps(records, indent=2))
        return 0

    for entry in entries:
        turn_str = f"[t{entry.turn}]" if entry.turn is not None else "     "
        print(f"  {entry.seq:>3}  {turn_str} {entry.kind:<24} {entry.detail}")

    return 0


# ── store ───────────────────────────────────────────────────────────────────


def _cmd_store(args: argparse.Namespace) -> int:
    store_dir: Path = args.dir
    sub_command = getattr(args, "store_command", None)

    if sub_command == "show":
        return _cmd_store_show(store_dir, args.handle_id)

    # List all handles
    handles = load_store_index(store_dir)
    if not handles:
        print(f"No handles found in {store_dir / 'index.json'}")
        return 0

    header = f"{'ID':<18} {'KIND':<12} {'TOKENS':>7} {'SHA256':<14} {'LABEL'}"
    print(header)
    print("-" * len(header))
    for _hid, h in sorted(handles.items()):
        print(f"{h.id:<18} {h.kind:<12} {h.tokens:>7} {h.sha256[:12]:<14} {h.label}")
    return 0


def _cmd_store_show(store_dir: Path, handle_id: str) -> int:
    handles = load_store_index(store_dir)
    h = handles.get(handle_id)
    if h is None:
        print(f"handle {handle_id!r} not found in {store_dir / 'index.json'}", file=sys.stderr)
        return 1

    print(f"  id:          {h.id}")
    print(f"  kind:        {h.kind}")
    print(f"  tokens:      {h.tokens}")
    print(f"  sha256:      {h.sha256}")
    print(f"  label:       {h.label}")
    print(f"  preview_head: {h.preview_head}")
    print(f"  preview_tail: {h.preview_tail}")
    return 0


# ── verify ──────────────────────────────────────────────────────────────────


def _cmd_verify(args: argparse.Namespace) -> int:
    import keel.verify.ff  # noqa: F401  (side-effect: registers every fitness function)
    from keel.verify.registry import run_on_log

    log_dir: Path = args.dir
    session_id: str = args.session_id
    as_json: bool = args.as_json

    log_path = find_session_log(log_dir, session_id)
    if log_path is None:
        print(f"session {session_id!r} not found in {log_dir}", file=sys.stderr)
        return 1

    findings = run_on_log(log_path)

    if as_json:
        records = [{"ff_id": f.ff_id, "ok": f.ok, "message": f.message} for f in findings]
        print(json.dumps(records, indent=2))
        return 0 if all(f.ok for f in findings) else 1

    # Human-readable table
    for finding in findings:
        status = "OK" if finding.ok else "FAIL"
        print(f"  [{status}] {finding.ff_id}: {finding.message}")

    return 0 if all(f.ok for f in findings) else 1
