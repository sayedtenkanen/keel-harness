"""ff_pointer_integrity — every handle that entered a window must resolve.

Slice 1 scope: every `spilled` event's path exists on disk. Slice 2 widens
this to check handles pulled from the real store, not just read-tool spills.
"""

from __future__ import annotations

from pathlib import Path

from keel.session.events import AnyEvent, Spilled
from keel.verify.registry import Finding, register

FF_ID = "ff_pointer_integrity"


def check(events: list[AnyEvent]) -> list[Finding]:
    findings: list[Finding] = []
    for event in events:
        if isinstance(event, Spilled) and not Path(event.path).exists():
            findings.append(
                Finding(
                    ff_id=FF_ID,
                    ok=False,
                    message=(
                        f"handle {event.handle_id} spilled to {event.path} but the file is gone"
                    ),
                )
            )
    if not findings:
        findings.append(Finding(ff_id=FF_ID, ok=True, message="all spilled handles resolve"))
    return findings


register(FF_ID, check)
