"""Heuristics for prompt injection and unsafe tool-call patterns.

Cheap, high-recall, not a guarantee — SPEC.md §2 ("constraints migrate from
prompts to verification") is what this module is in service of: it turns "the
agent should never run a fork bomb" into something ff_no_unsafe_tool_call can
actually check. A hit here means "review this", not "this is compromised".
"""

from __future__ import annotations

import re

INJECTION_PHRASES: list[re.Pattern[str]] = [
    re.compile(r"(?i)ignore (?:all )?(?:previous|prior|above) instructions"),
    re.compile(r"(?i)disregard (?:all )?(?:previous|prior|above) (?:instructions|rules)"),
    re.compile(r"(?i)you are now (?:in )?(?:developer|debug|dan) mode"),
    re.compile(r"(?i)reveal (?:your |the )?(?:system prompt|instructions)"),
    re.compile(r"(?i)act as if you have no (?:restrictions|guidelines|rules)"),
]

UNSAFE_SHELL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"rm\s+-rf\s+/(?:\s|$)"),
    re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),  # fork bomb
    re.compile(r"curl[^|]*\|\s*(?:sh|bash)\b"),
    re.compile(r"chmod\s+777\s+/"),
    re.compile(r">\s*/dev/sd[a-z]\b"),
]


def contains_injection_phrase(text: str) -> list[str]:
    return [p.pattern for p in INJECTION_PHRASES if p.search(text)]


def contains_unsafe_shell(text: str) -> list[str]:
    return [p.pattern for p in UNSAFE_SHELL_PATTERNS if p.search(text)]
