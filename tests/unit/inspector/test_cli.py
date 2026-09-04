"""Integration tests for keel inspect subcommands — subprocess-based."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "tests" / "fixtures"


def _run_inspect(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "keel", "inspect", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd or REPO_ROOT,
    )


def _copy_fixture(name: str, dest: Path) -> Path:
    src = FIXTURES / name
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / name
    shutil.copy2(src, target)
    return target


# ── sessions ────────────────────────────────────────────────────────────────


def test_sessions_lists_sessions(tmp_path: Path) -> None:
    _copy_fixture("inspect_clean.jsonl", tmp_path)
    proc = _run_inspect("sessions", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "sess-clean" in proc.stdout
    assert "clean" in proc.stdout


def test_sessions_json_output(tmp_path: Path) -> None:
    _copy_fixture("inspect_clean.jsonl", tmp_path)
    proc = _run_inspect("sessions", "--json", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert len(data) == 1
    assert data[0]["session_id"] == "sess-clean"
    assert data[0]["torn"] is False
    assert data[0]["turns"] == 2


def test_sessions_marks_torn(tmp_path: Path) -> None:
    _copy_fixture("inspect_torn.jsonl", tmp_path)
    proc = _run_inspect("sessions", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "TORN" in proc.stdout


def test_sessions_empty_dir(tmp_path: Path) -> None:
    proc = _run_inspect("sessions", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "No sessions" in proc.stdout


# ── timeline ────────────────────────────────────────────────────────────────


def test_timeline_shows_events(tmp_path: Path) -> None:
    _copy_fixture("inspect_clean.jsonl", tmp_path)
    proc = _run_inspect("timeline", "sess-clean", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "tool_called" in proc.stdout
    assert "tool_resulted" in proc.stdout
    assert "final_answer" in proc.stdout


def test_timeline_json_output(tmp_path: Path) -> None:
    _copy_fixture("inspect_clean.jsonl", tmp_path)
    proc = _run_inspect("timeline", "sess-clean", "--json", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert isinstance(data, list)
    assert len(data) == 9
    kinds = [e["kind"] for e in data]
    assert "tool_called" in kinds


def test_timeline_denial_shows_denied(tmp_path: Path) -> None:
    _copy_fixture("inspect_denial.jsonl", tmp_path)
    proc = _run_inspect("timeline", "sess-denial", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "DENIED" in proc.stdout
    assert "admin" in proc.stdout


def test_timeline_torn_warns(tmp_path: Path) -> None:
    _copy_fixture("inspect_torn.jsonl", tmp_path)
    proc = _run_inspect("timeline", "sess-torn", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "torn" in proc.stderr.lower()


def test_timeline_not_found(tmp_path: Path) -> None:
    proc = _run_inspect("timeline", "no-such-session", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 1
    assert "not found" in proc.stderr


def test_timeline_spill_session(tmp_path: Path) -> None:
    _copy_fixture("inspect_spill.jsonl", tmp_path)
    proc = _run_inspect("timeline", "sess-spill", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "spilled" in proc.stdout.lower()
    assert "aws_access_key" in proc.stdout


# ── store ───────────────────────────────────────────────────────────────────


def test_store_lists_handles(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    index = {
        "abc123def456": {
            "id": "abc123def456",
            "kind": "tool_result",
            "tokens": 12,
            "sha256": "abcdef1234567890abcdef",
            "label": "test.txt",
            "preview_head": "hello world",
            "preview_tail": "hello world",
        }
    }
    (store_dir / "index.json").write_text(json.dumps(index))
    proc = _run_inspect("store", "--dir", str(store_dir), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "abc123def456" in proc.stdout
    assert "tool_result" in proc.stdout


def test_store_show_handle(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    index = {
        "abc123def456": {
            "id": "abc123def456",
            "kind": "tool_result",
            "tokens": 12,
            "sha256": "abcdef1234567890abcdef",
            "label": "test.txt",
            "preview_head": "hello world",
            "preview_tail": "hello world",
        }
    }
    (store_dir / "index.json").write_text(json.dumps(index))
    proc = _run_inspect("store", "show", "abc123def456", "--dir", str(store_dir), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "hello world" in proc.stdout
    assert "tool_result" in proc.stdout


def test_store_show_not_found(tmp_path: Path) -> None:
    store_dir = tmp_path / "store"
    store_dir.mkdir()
    (store_dir / "index.json").write_text("{}")
    proc = _run_inspect("store", "show", "nope", "--dir", str(store_dir), cwd=tmp_path)
    assert proc.returncode == 1
    assert "not found" in proc.stderr


def test_store_empty(tmp_path: Path) -> None:
    proc = _run_inspect("store", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "No handles" in proc.stdout


# ── verify ──────────────────────────────────────────────────────────────────


def test_verify_clean_session(tmp_path: Path) -> None:
    _copy_fixture("inspect_clean.jsonl", tmp_path)
    proc = _run_inspect("verify", "sess-clean", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "[OK]" in proc.stdout


def test_verify_torn_session(tmp_path: Path) -> None:
    _copy_fixture("inspect_torn.jsonl", tmp_path)
    proc = _run_inspect("verify", "sess-torn", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 1  # torn line is a finding
    assert "FAIL" in proc.stdout or "OK" in proc.stdout


def test_verify_json_output(tmp_path: Path) -> None:
    _copy_fixture("inspect_clean.jsonl", tmp_path)
    proc = _run_inspect("verify", "sess-clean", "--json", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    assert isinstance(data, list)
    assert all(isinstance(f, dict) for f in data)
    assert all("ff_id" in f and "ok" in f and "message" in f for f in data)


def test_verify_not_found(tmp_path: Path) -> None:
    proc = _run_inspect("verify", "no-such-session", "--dir", str(tmp_path), cwd=tmp_path)
    assert proc.returncode == 1
    assert "not found" in proc.stderr
