from pathlib import Path

from keel.tools.builtin.read import SPILL_THRESHOLD_TOKENS, read_tool


def test_small_file_is_returned_inline(tmp_path: Path) -> None:
    f = tmp_path / "small.txt"
    f.write_text("hello world")

    result = read_tool(str(f), spill_dir=tmp_path / "spill")

    assert not result.spilled
    assert result.content == "hello world"
    assert result.handle_id is None


def test_large_file_is_spilled_with_a_resolvable_handle(tmp_path: Path) -> None:
    f = tmp_path / "big.txt"
    text = "x" * (SPILL_THRESHOLD_TOKENS * 4 + 100)
    f.write_text(text)

    result = read_tool(str(f), spill_dir=tmp_path / "spill")

    assert result.spilled
    assert result.content is None
    assert result.path is not None and result.path.exists()
    assert result.path.read_text() == text
    assert result.preview_head == text[:200]
    assert result.preview_tail == text[-200:]


def test_identical_content_yields_identical_handle_id(tmp_path: Path) -> None:
    text = "y" * (SPILL_THRESHOLD_TOKENS * 4 + 100)
    f1, f2 = tmp_path / "a.txt", tmp_path / "b.txt"
    f1.write_text(text)
    f2.write_text(text)

    r1 = read_tool(str(f1), spill_dir=tmp_path / "spill")
    r2 = read_tool(str(f2), spill_dir=tmp_path / "spill")

    assert r1.handle_id == r2.handle_id


def test_a_secret_in_a_large_file_is_redacted_before_it_is_spilled(tmp_path):
    f = tmp_path / "big.txt"
    padding = "x" * (SPILL_THRESHOLD_TOKENS * 4)
    f.write_text(f"{padding}\nAPI_KEY=sk-abcdefghijklmnopqrstuvwxyz0123456789\n")

    result = read_tool(str(f), spill_dir=tmp_path / "spill")

    assert result.spilled
    assert result.path is not None
    on_disk = result.path.read_text()
    assert "sk-abcdefghijklmnopqrstuvwxyz0123456789" not in on_disk
    assert "[REDACTED:" in on_disk
    assert result.redaction_labels
