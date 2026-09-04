import subprocess
import sys

from keel import __version__
from keel.cli import main


def test_version_flag_prints_version(capsys):
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert out.strip() == f"keel {__version__}"


def test_no_args_prints_help_and_exits_zero(capsys):
    assert main([]) == 0
    assert "Keel agent harness" in capsys.readouterr().out


def test_module_is_runnable_as_subprocess():
    proc = subprocess.run(
        [sys.executable, "-m", "keel", "--version"], capture_output=True, text=True, check=False
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == f"keel {__version__}"
