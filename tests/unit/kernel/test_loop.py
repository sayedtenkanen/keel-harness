from pathlib import Path

from keel.adapters.fake_model import FakeModel, ScriptedFinalAnswer, ScriptedToolCall
from keel.kernel.loop import run
from keel.session.log import EventLog


def test_scripted_run_reads_a_file_then_answers(tmp_path: Path) -> None:
    small = tmp_path / "small.txt"
    small.write_text("hello")
    script = [
        ScriptedToolCall(tool="read", args={"path": str(small)}),
        ScriptedFinalAnswer(text="done"),
    ]
    log_path = tmp_path / "run.jsonl"
    log = EventLog(log_path)

    result = run(
        FakeModel(script), log, session_id="t1", max_turns=10, spill_dir=tmp_path / "spill"
    )

    assert result.reason == "final_answer"
    assert result.final_answer == "done"
    kinds = [e.kind for e in EventLog.read(log_path).events]
    assert kinds[0] == "run_started"
    assert "tool_called" in kinds
    assert "tool_resulted" in kinds
    assert kinds[-1] == "run_ended"


def test_run_stops_at_max_turns_if_the_model_never_answers(tmp_path: Path) -> None:
    small = tmp_path / "small.txt"
    small.write_text("x")
    script = [ScriptedToolCall(tool="read", args={"path": str(small)})] * 3
    log = EventLog(tmp_path / "run.jsonl")

    result = run(FakeModel(script), log, session_id="t2", max_turns=3, spill_dir=tmp_path / "spill")

    assert result.reason == "max_turns"
    assert result.turns == 3


def test_a_large_tool_result_is_spilled_and_logged(tmp_path: Path) -> None:
    big = tmp_path / "big.txt"
    big.write_text("z" * 9_000)
    script = [
        ScriptedToolCall(tool="read", args={"path": str(big)}),
        ScriptedFinalAnswer(text="ok"),
    ]
    log_path = tmp_path / "run.jsonl"
    log = EventLog(log_path)

    run(FakeModel(script), log, session_id="t3", max_turns=10, spill_dir=tmp_path / "spill")

    kinds = [e.kind for e in EventLog.read(log_path).events]
    assert "spilled" in kinds


def test_a_secret_in_a_final_answer_is_redacted_in_the_log_but_not_in_the_result(
    tmp_path: Path,
) -> None:
    secret_answer = "your key is sk-abcdefghijklmnopqrstuvwxyz0123456789"
    script = [ScriptedFinalAnswer(text=secret_answer)]
    log_path = tmp_path / "run.jsonl"
    log = EventLog(log_path)

    result = run(FakeModel(script), log, session_id="t4", max_turns=5, spill_dir=tmp_path / "spill")

    assert result.final_answer == secret_answer  # caller gets the true value
    events = EventLog.read(log_path).events
    final_answer_events = [e for e in events if e.kind == "final_answer"]
    assert "sk-abcdefghijklmnopqrstuvwxyz0123456789" not in final_answer_events[0].text
    assert any(e.kind == "redaction_applied" for e in events)


def test_a_secret_in_tool_args_is_redacted_before_logging(tmp_path: Path) -> None:
    small = tmp_path / "small.txt"
    small.write_text("hello")
    script = [
        ScriptedToolCall(
            tool="read", args={"path": str(small), "note": "token=sk-cccccccccccccccccccccccc"}
        ),
        ScriptedFinalAnswer(text="done"),
    ]
    log_path = tmp_path / "run.jsonl"
    log = EventLog(log_path)

    run(FakeModel(script), log, session_id="t5", max_turns=10, spill_dir=tmp_path / "spill")

    events = EventLog.read(log_path).events
    tool_called = next(e for e in events if e.kind == "tool_called")
    assert "sk-cccccccccccccccccccccccc" not in str(tool_called.args)
