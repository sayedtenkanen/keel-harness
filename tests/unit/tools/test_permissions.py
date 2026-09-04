from __future__ import annotations

from pathlib import Path

from keel.tools.permissions import (
    check_permission,
    load_rule_table,
    normalise_call,
)


def test_normalise_call_read() -> None:
    assert normalise_call("read", {"path": "/etc/passwd"}) == "read"


def test_normalise_call_exec_with_cmd() -> None:
    assert normalise_call("exec", {"cmd": "pytest"}) == "exec:pytest"


def test_normalise_call_exec_without_cmd() -> None:
    assert normalise_call("exec", {}) == "exec"


def test_check_permission_read_allowed() -> None:
    allowed, tier, reason = check_permission("read", {}, allowed_tier="read")
    assert allowed is True
    assert tier == "read"


def test_check_permission_exec_denied_for_read_tier() -> None:
    allowed, tier, reason = check_permission("exec", {"cmd": "rm -rf /"}, allowed_tier="read")
    assert allowed is False
    assert tier == "admin"
    assert "admin" in reason


def test_check_permission_exec_allowed_for_exec_tier() -> None:
    allowed, tier, reason = check_permission("exec", {"cmd": "pytest"}, allowed_tier="exec")
    assert allowed is True
    assert tier == "exec"


def test_check_permission_admin_required_for_dangerous() -> None:
    allowed, tier, reason = check_permission("exec", {"cmd": "rm -rf /"}, allowed_tier="exec")
    assert allowed is False
    assert tier == "admin"


def test_load_rule_table_defaults() -> None:
    rules = load_rule_table()
    assert rules["read"] == "read"
    assert rules["exec:pytest"] == "exec"
    assert rules["exec:rm -rf *"] == "admin"


def test_load_rule_table_with_project_overrides(tmp_path: Path) -> None:
    keel_dir = tmp_path / ".keel"
    keel_dir.mkdir()
    permissions_file = keel_dir / "permissions.json"
    permissions_file.write_text('{"read": "write"}')

    rules = load_rule_table(tmp_path)
    assert rules["read"] == "write"
    # Other defaults should still be present
    assert rules["exec:pytest"] == "exec"


def test_exec_pytest_and_exec_rm_rf_different_tiers() -> None:
    _, pytest_tier, _ = check_permission("exec", {"cmd": "pytest"}, allowed_tier="admin")
    _, rm_tier, _ = check_permission("exec", {"cmd": "rm -rf /"}, allowed_tier="admin")
    assert pytest_tier != rm_tier
