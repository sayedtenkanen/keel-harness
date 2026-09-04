"""ff_no_secret_leak — no unredacted secret should reach the event log or a spilled file.

Backstop for keel.security.redact, which does the actual prevention at write
time. A failure here means some code path wrote content to the log or store
without going through redact() first — a harness bug to fix, not a finding to
suppress.
"""

from __future__ import annotations

from pathlib import Path

from keel.security.redact import scan
from keel.session.events import AnyEvent, FinalAnswer, Spilled, ToolCalled
from keel.verify.registry import Finding, register

FF_ID = "ff_no_secret_leak"


def _logged_texts(event: AnyEvent) -> list[str]:
    if isinstance(event, ToolCalled):
        return [v for v in event.args.values() if isinstance(v, str)]
    if isinstance(event, FinalAnswer):
        return [event.text]
    return []


def check(events: list[AnyEvent]) -> list[Finding]:
    findings: list[Finding] = []
    for event in events:
        for text in _logged_texts(event):
            for match in scan(text):
                if match.category == "secret":
                    findings.append(
                        Finding(
                            FF_ID,
                            False,
                            f"unredacted {match.label} in {event.kind} at seq {event.seq}",
                        )
                    )
        if isinstance(event, Spilled) and Path(event.blob_path).exists():
            for match in scan(Path(event.blob_path).read_text(encoding="utf-8")):
                if match.category == "secret":
                    findings.append(
                        Finding(
                            FF_ID,
                            False,
                            f"unredacted {match.label} in spilled file {event.blob_path}",
                        )
                    )
    if not findings:
        findings.append(Finding(FF_ID, True, "no unredacted secrets found in log or spilled files"))
    return findings


register(FF_ID, check)
