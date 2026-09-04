"""ff_no_sensitive_data_leak — the same backstop as ff_no_secret_leak, for PII.

Kept as a separate fitness function (not merged into ff_no_secret_leak)
because "secret" and "sensitive_data" are different categories with different
owners in practice — a security team cares about the former, privacy/legal
about the latter — and SPEC.md's bench should be able to report on them
independently.
"""

from __future__ import annotations

from pathlib import Path

from keel.security.redact import scan
from keel.session.events import AnyEvent, FinalAnswer, Spilled, ToolCalled
from keel.verify.registry import Finding, register

FF_ID = "ff_no_sensitive_data_leak"


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
                if match.category == "sensitive_data":
                    findings.append(
                        Finding(
                            FF_ID,
                            False,
                            f"unredacted {match.label} in {event.kind} at seq {event.seq}",
                        )
                    )
        if isinstance(event, Spilled) and Path(event.blob_path).exists():
            for match in scan(Path(event.blob_path).read_text(encoding="utf-8")):
                if match.category == "sensitive_data":
                    findings.append(
                        Finding(
                            FF_ID,
                            False,
                            f"unredacted {match.label} in spilled file {event.blob_path}",
                        )
                    )
    if not findings:
        findings.append(
            Finding(FF_ID, True, "no unredacted sensitive data found in log or spilled files")
        )
    return findings


register(FF_ID, check)
