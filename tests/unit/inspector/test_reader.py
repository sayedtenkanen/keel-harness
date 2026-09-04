"""Unit tests for keel.inspect.reader — uses real fixture JSONL logs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from keel.inspector.reader import (
    build_timeline,
    discover_sessions,
    find_session_log,
    load_store_index,
    read_session,
)

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def _copy_fixture(name: str, dest: Path) -> Path:
    src = FIXTURES / name
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / name
    shutil.copy2(src, target)
    return target


# ── discover_sessions ───────────────────────────────────────────────────────


def test_discover_sessions_lists_all(tmp_path: Path) -> None:
    _copy_fixture("inspect_clean.jsonl", tmp_path)
    _copy_fixture("inspect_denial.jsonl", tmp_path)
    sessions = discover_sessions(tmp_path)
    ids = {s.session_id for s in sessions}
    assert "sess-clean" in ids
    assert "sess-denial" in ids


def test_discover_sessions_empty_dir(tmp_path: Path) -> None:
    assert discover_sessions(tmp_path) == []


def test_discover_sessions_nonexistent_dir() -> None:
    assert discover_sessions(Path("/nonexistent")) == []


def test_discover_sessions_marks_torn(tmp_path: Path) -> None:
    _copy_fixture("inspect_torn.jsonl", tmp_path)
    sessions = discover_sessions(tmp_path)
    assert len(sessions) == 1
    assert sessions[0].torn is True
    assert sessions[0].session_id == "sess-torn"


def test_discover_sessions_counts_tools(tmp_path: Path) -> None:
    _copy_fixture("inspect_clean.jsonl", tmp_path)
    sessions = discover_sessions(tmp_path)
    assert len(sessions) == 1
    assert sessions[0].tool_calls == 1  # one tool_called event in clean fixture


def test_discover_sessions_extracts_turns(tmp_path: Path) -> None:
    _copy_fixture("inspect_clean.jsonl", tmp_path)
    sessions = discover_sessions(tmp_path)
    assert sessions[0].turns == 2


# ── read_session ────────────────────────────────────────────────────────────


def test_read_session_clean(tmp_path: Path) -> None:
    path = _copy_fixture("inspect_clean.jsonl", tmp_path)
    result = read_session(path)
    assert result.torn is False
    assert len(result.events) == 9
    assert result.events[0].kind == "run_started"
    assert result.events[-1].kind == "run_ended"


def test_read_session_torn(tmp_path: Path) -> None:
    path = _copy_fixture("inspect_torn.jsonl", tmp_path)
    result = read_session(path)
    assert result.torn is True
    # Torn line (run_ended) is discarded; 8 complete events remain
    assert len(result.events) == 8
    assert result.events[-1].kind == "final_answer"


def test_read_session_missing() -> None:
    result = read_session(Path("/nonexistent.jsonl"))
    assert result.events == []
    assert result.torn is False


# ── build_timeline ──────────────────────────────────────────────────────────


def test_build_timeline_clean(tmp_path: Path) -> None:
    path = _copy_fixture("inspect_clean.jsonl", tmp_path)
    result = read_session(path)
    entries = build_timeline(result.events)
    assert len(entries) == 9
    kinds = [e.kind for e in entries]
    assert "tool_called" in kinds
    assert "tool_resulted" in kinds
    assert "final_answer" in kinds


def test_build_timeline_denial(tmp_path: Path) -> None:
    path = _copy_fixture("inspect_denial.jsonl", tmp_path)
    result = read_session(path)
    entries = build_timeline(result.events)
    denial_entries = [e for e in entries if e.kind == "tool_denied"]
    assert len(denial_entries) == 1
    assert "DENIED" in denial_entries[0].detail
    assert "admin" in denial_entries[0].detail


def test_build_timeline_spill(tmp_path: Path) -> None:
    path = _copy_fixture("inspect_spill.jsonl", tmp_path)
    result = read_session(path)
    entries = build_timeline(result.events)
    spill_entries = [e for e in entries if e.kind == "spilled"]
    assert len(spill_entries) == 1
    redact_entries = [e for e in entries if e.kind == "redaction_applied"]
    assert len(redact_entries) == 1
    assert "aws_access_key" in redact_entries[0].detail


# ── find_session_log ────────────────────────────────────────────────────────


def test_find_session_log_found(tmp_path: Path) -> None:
    _copy_fixture("inspect_clean.jsonl", tmp_path)
    found = find_session_log(tmp_path, "sess-clean")
    assert found is not None
    assert found.name == "inspect_clean.jsonl"


def test_find_session_log_not_found(tmp_path: Path) -> None:
    _copy_fixture("inspect_clean.jsonl", tmp_path)
    assert find_session_log(tmp_path, "no-such-session") is None


# ── load_store_index ────────────────────────────────────────────────────────


def test_load_store_index(tmp_path: Path) -> None:
    index = {
        "abc123": {
            "id": "abc123",
            "kind": "tool_result",
            "tokens": 10,
            "sha256": "abcdef1234567890",
            "label": "test.txt",
            "preview_head": "hello",
            "preview_tail": "hello",
        }
    }
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    (store_dir / "index.json").write_text(json.dumps(index))
    handles = load_store_index(store_dir)
    assert "abc123" in handles
    assert handles["abc123"].kind == "tool_result"


def test_load_store_index_missing(tmp_path: Path) -> None:
    assert load_store_index(tmp_path) == {}
