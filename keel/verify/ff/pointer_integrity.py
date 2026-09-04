"""ff_pointer_integrity — every handle that entered a window must resolve.

Slice 2: checks that every Spilled event's handle_id exists in the store's
blob directory. The store path is derived from the Spilled event's blob_path field.
"""

from __future__ import annotations

from pathlib import Path

from keel.session.events import AnyEvent, Spilled
from keel.verify.registry import Finding, register

FF_ID = "ff_pointer_integrity"


def check(events: list[AnyEvent]) -> list[Finding]:
    findings: list[Finding] = []

    for event in events:
        if isinstance(event, Spilled):
            # The blob_path field contains the full path to the blob file
            blob_path = Path(event.blob_path)
            if not blob_path.exists():
                findings.append(
                    Finding(
                        ff_id=FF_ID,
                        ok=False,
                        message=(
                            f"handle {event.handle_id} spilled but blob not found at {blob_path}"
                        ),
                    )
                )

    if not findings:
        findings.append(Finding(ff_id=FF_ID, ok=True, message="all spilled handles resolve"))
    return findings


register(FF_ID, check)
