from pathlib import Path

from keel.session.log import EventLog


def test_emit_and_read_roundtrip(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "run.jsonl")
    log.emit("s1", "run_started", model="fake", max_turns=5)
    log.emit("s1", "run_ended", reason="max_turns", turns=1)

    result = EventLog.read(tmp_path / "run.jsonl")

    assert not result.torn
    assert [e.kind for e in result.events] == ["run_started", "run_ended"]
    assert result.events[0].seq == 0
    assert result.events[1].seq == 1


def test_torn_last_line_is_detected_not_crashed_on(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    log = EventLog(path)
    log.emit("s1", "run_started", model="fake", max_turns=5)
    with path.open("a", encoding="utf-8") as f:
        f.write('{"seq": 1, "kind": "run_end')  # torn: no closing brace, no newline

    result = EventLog.read(path)

    assert result.torn
    assert len(result.events) == 1


def test_reading_a_missing_log_returns_empty(tmp_path: Path) -> None:
    result = EventLog.read(tmp_path / "missing.jsonl")

    assert result.events == []
    assert not result.torn


def test_resuming_an_existing_log_continues_the_sequence(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    EventLog(path).emit("s1", "run_started", model="fake", max_turns=5)

    resumed = EventLog(path)
    event = resumed.emit("s1", "run_ended", reason="max_turns", turns=1)

    assert event.seq == 1


def test_a_corrupt_line_that_is_not_the_last_one_raises(tmp_path: Path) -> None:
    path = tmp_path / "run.jsonl"
    log = EventLog(path)
    log.emit("s1", "run_started", model="fake", max_turns=5)
    with path.open("a", encoding="utf-8") as f:
        f.write("not json at all\n")
        f.write('{"seq": 2, "session_id": "s1", "kind": "run_ended", ')
        f.write('"reason": "max_turns", "turns": 1}\n')

    try:
        EventLog.read(path)
        raise AssertionError("expected ValueError for a mid-file corrupt line")
    except ValueError as exc:
        assert "not at boundary" in str(exc)
