"""Scan-and-redact — the preventive half of the secret/sensitive-data checks.

Called at every point text is about to be written durably: the event log
(tool-call args, final-answer text) and spill files. Detection over content
already on disk is the verifier's job (verify/ff/secrets.py,
sensitive_data.py) — that is the backstop for whatever this module misses or
a future code path forgets to call.
"""

from __future__ import annotations

from dataclasses import dataclass

from keel.security.patterns import ALL_PATTERNS, Category


@dataclass(frozen=True)
class Match:
    label: str
    category: Category
    start: int
    end: int


def _luhn_valid(candidate: str) -> bool:
    digits = [int(c) for c in candidate if c.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def scan(text: str) -> list[Match]:
    matches: list[Match] = []
    for pattern in ALL_PATTERNS:
        for m in pattern.regex.finditer(text):
            if pattern.label == "credit_card_candidate" and not _luhn_valid(m.group()):
                continue
            matches.append(
                Match(label=pattern.label, category=pattern.category, start=m.start(), end=m.end())
            )
    return matches


def redact(text: str) -> tuple[str, list[Match]]:
    """Return (redacted_text, matches). Redacts right-to-left so earlier spans stay valid."""
    matches = scan(text)
    if not matches:
        return text, []
    result = text
    for m in sorted(matches, key=lambda m: m.start, reverse=True):
        result = result[: m.start] + f"[REDACTED:{m.label}]" + result[m.end :]
    return result, matches
