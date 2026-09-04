from pathlib import Path

import keel.verify.ff  # noqa: F401
from keel.session.log import EventLog
from keel.verify.registry import run_on_log


def test_passes_on_a_clean_log(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "run.jsonl")
    log.emit("s1", "final_answer", turn=0, text="no personal data here")

    findings = [
        f for f in run_on_log(tmp_path / "run.jsonl") if f.ff_id == "ff_no_sensitive_data_leak"
    ]

    assert findings and all(f.ok for f in findings)


def test_fails_when_an_email_reaches_the_log_unredacted(tmp_path: Path) -> None:
    log = EventLog(tmp_path / "run.jsonl")
    log.emit("s1", "final_answer", turn=0, text="reach out to jane.doe@example.com")

    findings = [
        f for f in run_on_log(tmp_path / "run.jsonl") if f.ff_id == "ff_no_sensitive_data_leak"
    ]

    assert any(not f.ok for f in findings)
