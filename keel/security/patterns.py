"""Pattern definitions for secret and sensitive-data detection.

Deliberately conservative in one direction: a false positive (over-redaction,
a flagged finding that turns out fine) is cheap here. A false negative — a
real secret that slips through — is the failure mode this module exists to
avoid, so patterns lean broad. Not a substitute for a real DLP product; this
is the harness's own backstop over its own logs and store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Category = Literal["secret", "sensitive_data"]


@dataclass(frozen=True)
class Pattern:
    label: str
    regex: re.Pattern[str]
    category: Category


SECRET_PATTERNS: list[Pattern] = [
    Pattern("aws_access_key_id", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "secret"),
    Pattern(
        "aws_secret_access_key",
        re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?"),
        "secret",
    ),
    Pattern("openai_api_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"), "secret"),
    Pattern("anthropic_api_key", re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{20,}\b"), "secret"),
    Pattern("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"), "secret"),
    Pattern("bearer_token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-_.]{20,}\b"), "secret"),
    Pattern(
        "private_key_block",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
        "secret",
    ),
    Pattern("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"), "secret"),
    Pattern(
        "generic_assignment_secret",
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*"
            r"['\"]?[A-Za-z0-9\-_/+=]{8,}['\"]?"
        ),
        "secret",
    ),
]

SENSITIVE_DATA_PATTERNS: list[Pattern] = [
    Pattern(
        "email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "sensitive_data"
    ),
    Pattern("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "sensitive_data"),
    Pattern("credit_card_candidate", re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "sensitive_data"),
    Pattern(
        "phone_number",
        re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "sensitive_data",
    ),
]

ALL_PATTERNS: list[Pattern] = SECRET_PATTERNS + SENSITIVE_DATA_PATTERNS
