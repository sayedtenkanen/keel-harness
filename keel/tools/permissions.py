"""Permission tiers — control what tools can do.

Tiers are over normalised calls (tool + argument pattern), not tools.
The shipped rule table provides defaults; a per-project extension file
can override or add rules.
"""

from __future__ import annotations

import json
from pathlib import Path

from keel.tools.runtime import PermissionTier

# Shipped default rule table: normalised call pattern -> required tier
# Pattern format: "tool" or "tool:arg_pattern"
# arg_pattern uses wildcards: * matches any value
DEFAULT_RULES: dict[str, PermissionTier] = {
    # Read-only tools
    "read": "read",
    "outline": "read",
    "grep": "read",
    # Write tools
    "write": "write",
    # Exec tools - different tiers for different commands
    "exec:pytest": "exec",
    "exec:python": "exec",
    "exec:pip": "exec",
    "exec:uv": "exec",
    "exec:*": "exec",
    # Dangerous exec patterns
    "exec:rm -rf *": "admin",
    "exec:rm -rf /": "admin",
    "exec:curl * | sh": "admin",
    "exec:* > /etc/*": "admin",
}

TIER_ORDER: list[PermissionTier] = ["read", "write", "exec", "admin"]


def normalise_call(tool: str, args: dict[str, object]) -> str:
    """Normalise a tool call to a pattern for tier lookup.

    For exec-like tools, extracts the command to match against patterns.
    """
    if tool == "exec" and "cmd" in args:
        cmd = str(args["cmd"])
        return f"exec:{cmd}"
    return tool


def load_rule_table(project_path: Path | None = None) -> dict[str, PermissionTier]:
    """Load the rule table, merging project overrides on top of defaults."""
    rules = dict(DEFAULT_RULES)

    if project_path is not None:
        override_file = project_path / ".keel" / "permissions.json"
        if override_file.exists():
            data = json.loads(override_file.read_text())
            for key, value in data.items():
                if value in TIER_ORDER:
                    rules[key] = value

    return rules


def check_permission(
    tool: str,
    args: dict[str, object],
    *,
    allowed_tier: PermissionTier,
    rules: dict[str, PermissionTier] | None = None,
) -> tuple[bool, PermissionTier, str]:
    """Check if a tool call is allowed under the given tier.

    Returns (allowed, required_tier, reason).
    """
    if rules is None:
        rules = DEFAULT_RULES

    pattern = normalise_call(tool, args)

    # Try exact match first, then wildcard patterns
    required = rules.get(pattern)
    if required is None:
        # Check for wildcard patterns (e.g., "exec:*" matches "exec:echo hello")
        for rule_pattern, rule_tier in rules.items():
            if rule_pattern.endswith(":*") and pattern.startswith(rule_pattern[:-1]):
                required = rule_tier
                break

    if required is None:
        # Fall back to tool name without args
        required = rules.get(tool, "read")

    allowed_idx = TIER_ORDER.index(allowed_tier)
    required_idx = TIER_ORDER.index(required)

    if allowed_idx >= required_idx:
        return True, required, ""

    return False, required, f"tier {allowed_tier!r} < required {required!r} for {pattern!r}"
