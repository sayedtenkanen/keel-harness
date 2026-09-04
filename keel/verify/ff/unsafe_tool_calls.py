"""ff_no_unsafe_tool_call — flags tool calls and model output matching known
unsafe-shell or prompt-injection patterns.

Heuristic, not proof (see keel/security/injection.py): a hit means "review
this," not "this is compromised." Scans tool-call args now so the check is
already in place before slice 4 adds the exec tool it matters most for.
"""

from __future__ import annotations

from keel.security.injection import contains_injection_phrase, contains_unsafe_shell
from keel.session.events import AnyEvent, FinalAnswer, ToolCalled
from keel.verify.registry import Finding, register

FF_ID = "ff_no_unsafe_tool_call"


def check(events: list[AnyEvent]) -> list[Finding]:
    findings: list[Finding] = []
    for event in events:
        if isinstance(event, ToolCalled):
            for value in event.args.values():
                if not isinstance(value, str):
                    continue
                for pattern in contains_unsafe_shell(value):
                    msg = (
                        f"unsafe shell pattern {pattern!r} in {event.tool} args at seq {event.seq}"
                    )
                    findings.append(Finding(FF_ID, False, msg))
                for pattern in contains_injection_phrase(value):
                    msg = f"injection phrase in {event.tool} args at seq {event.seq}: {pattern!r}"
                    findings.append(Finding(FF_ID, False, msg))
        elif isinstance(event, FinalAnswer):
            for pattern in contains_injection_phrase(event.text):
                findings.append(
                    Finding(
                        FF_ID,
                        False,
                        f"injection phrase in final answer at seq {event.seq}: {pattern!r}",
                    )
                )
    if not findings:
        findings.append(Finding(FF_ID, True, "no unsafe tool-call or injection patterns found"))
    return findings


register(FF_ID, check)
