import subprocess
import sys
import pathlib

SCRIPT = str(pathlib.Path(__file__).parent.parent / "main.py")


def test_main_help_exposes_parameter_flags():
    result = subprocess.run(
        [sys.executable, SCRIPT, "--help"],
        capture_output=True, text=True,
    )
    assert "--touch-thresh"      in result.stdout
    assert "--min-touch-frames"  in result.stdout
    assert "--d-exit-factor"     in result.stdout
    assert "--max-frames"        in result.stdout
    assert "--no-show-live"      in result.stdout
    assert "--no-save-video"     in result.stdout
