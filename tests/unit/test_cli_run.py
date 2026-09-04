import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "s1.yaml"


def test_keel_run_produces_a_log_and_exits_zero(tmp_path: Path) -> None:
    log_path = tmp_path / "run.jsonl"

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "keel",
            "run",
            "--model",
            "fake",
            "--script",
            str(FIXTURE),
            "--log",
            str(log_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )

    assert proc.returncode == 0, proc.stderr
    assert log_path.exists()
    assert "done" in proc.stdout


def test_keel_verify_reports_ok_on_a_clean_log(tmp_path: Path) -> None:
    log_path = tmp_path / "run.jsonl"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "keel",
            "run",
            "--model",
            "fake",
            "--script",
            str(FIXTURE),
            "--log",
            str(log_path),
        ],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
    )

    proc = subprocess.run(
        [sys.executable, "-m", "keel", "verify", str(log_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )

    assert proc.returncode == 0, proc.stderr
    assert "[OK] ff_pointer_integrity" in proc.stdout
