from pathlib import Path

import keel.verify.ff  # noqa: F401  (registers ff_pointer_integrity)
from keel.session.log import EventLog
from keel.verify.registry import run_on_log


def test_passes_when_every_spilled_handle_resolves(tmp_path: Path) -> None:
    log_path = tmp_path / "run.jsonl"
    log = EventLog(log_path)
    spill_file = tmp_path / "h1.txt"
    spill_file.write_text("content")
    log.emit("s1", "run_started", model="fake", max_turns=5)
    log.emit("s1", "spilled", turn=0, handle_id="h1", tokens=10, path=str(spill_file))
    log.emit("s1", "run_ended", reason="final_answer", turns=1)

    findings = run_on_log(log_path)

    assert findings
    assert all(f.ok for f in findings)


def test_fails_when_a_spilled_handle_does_not_resolve(tmp_path: Path) -> None:
    log_path = tmp_path / "run.jsonl"
    log = EventLog(log_path)
    log.emit(
        "s1", "spilled", turn=0, handle_id="ghost", tokens=10, path=str(tmp_path / "missing.txt")
    )

    findings = run_on_log(log_path)

    assert any(not f.ok and f.ff_id == "ff_pointer_integrity" for f in findings)
