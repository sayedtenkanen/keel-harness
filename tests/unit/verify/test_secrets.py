from pathlib import Path

import keel.verify.ff  # noqa: F401  (registers ff_no_secret_leak)
from keel.session.log import EventLog
from keel.verify.registry import run_on_log


def test_passes_on_a_clean_log(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "run.jsonl")
    log.emit("s1", "final_answer", turn=0, text="the sky is blue")

    findings = [f for f in run_on_log(tmp_path / "run.jsonl") if f.ff_id == "ff_no_secret_leak"]

    assert findings and all(f.ok for f in findings)


def test_fails_when_an_unredacted_secret_reaches_the_log(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "run.jsonl")
    # bypasses redact() on purpose, simulating a code path that forgot to call it
    log.emit("s1", "final_answer", turn=0, text="key: sk-abcdefghijklmnopqrstuvwxyz0123456789")

    findings = [f for f in run_on_log(tmp_path / "run.jsonl") if f.ff_id == "ff_no_secret_leak"]

    assert any(not f.ok for f in findings)


def test_fails_when_an_unredacted_secret_is_in_a_spilled_file(tmp_path: Path) -> None:
    spill_file = tmp_path / "h1.txt"
    spill_file.write_text("token=sk-abcdefghijklmnopqrstuvwxyz0123456789")
    log = EventLog(tmp_path / "run.jsonl")
    log.emit("s1", "spilled", turn=0, handle_id="h1", tokens=10, path=str(spill_file))

    findings = [f for f in run_on_log(tmp_path / "run.jsonl") if f.ff_id == "ff_no_secret_leak"]

    assert any(not f.ok for f in findings)
