import os
import plistlib
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_long_windows_path_is_rejected_without_long_path_support():
    from installer.setup_app import location_problem

    long_dir = "C:\\Users\\Someone With A Long Name\\OneDrive - Hebrew University\\Downloads\\BeeInteractionDetector-v1.0.0"
    assert location_problem(long_dir, is_windows=True, long_paths_enabled=False)
    assert location_problem(long_dir, is_windows=True, long_paths_enabled=True) is None
    assert location_problem("C:\\BeeDetector", is_windows=True, long_paths_enabled=False) is None
    # v1.0.2 accepted this 77-char folder and then failed inside TensorFlow's files.
    real = "C:\\Users\\matan\\Downloads\\BeeInteractionDetector-v1.0.2\\BeeInteractionDetector"
    assert location_problem(real, is_windows=True, long_paths_enabled=False)
    # Typical "Extract All" to the Desktop / Downloads with a normal user name still fits.
    assert location_problem("C:\\Users\\dana\\Desktop\\BeeDetector", is_windows=True,
                            long_paths_enabled=False) is None
    assert location_problem("/Users/x/" + "a" * 200, is_windows=False, long_paths_enabled=False) is None


def test_onedrive_location_warns():
    from installer.setup_app import location_warning

    assert location_warning("C:\\Users\\dana\\OneDrive\\Desktop\\Bee")
    assert location_warning("C:\\BeeDetector") is None


def test_model_path_resolves_relative_to_app(tmp_path):
    from installer.setup_app import model_path

    (tmp_path / "config.json").write_text('{"model_path": "Current Model/m", "model_name": "m"}')
    assert model_path(tmp_path) == tmp_path / "Current Model" / "m"


def test_mac_app_bundle(tmp_path):
    from installer.setup_app import APP_NAME, create_mac_app

    app_dir = tmp_path / "My Programs" / "Bee 'Detector'"   # spaces and quotes
    app_dir.mkdir(parents=True)
    icns = tmp_path / "icon.icns"
    icns.write_bytes(b"icns")

    app = create_mac_app(tmp_path / "Desktop", icns=icns, app_dir=app_dir)

    assert app.name == APP_NAME + ".app"
    info = plistlib.loads((app / "Contents" / "Info.plist").read_bytes())
    assert info["CFBundleExecutable"] == "launcher"
    assert info["CFBundleIconFile"] == "app_icon"
    launcher = app / "Contents" / "MacOS" / "launcher"
    assert launcher.stat().st_mode & stat.S_IXUSR
    # The quoted path must survive bash: print APP_DIR as the launcher sees it.
    script = launcher.read_text().split("\n")
    assign = next(line for line in script if line.startswith("APP_DIR="))
    out = subprocess.run(["bash", "-c", assign + '; printf %s "$APP_DIR"'],
                         capture_output=True, text=True, check=True).stdout
    assert out == str(app_dir)

    # Re-running the installer replaces the bundle cleanly.
    assert create_mac_app(tmp_path / "Desktop", app_dir=app_dir) == app


def test_icons_can_be_built(tmp_path, monkeypatch):
    from installer import setup_app

    monkeypatch.setattr(setup_app, "TOOLS_DIR", tmp_path)
    ico = setup_app.make_icon("ico")
    icns = setup_app.make_icon("icns")
    assert ico.read_bytes()[:4] == b"\x00\x00\x01\x00"
    assert icns.read_bytes()[:4] == b"icns"


def test_installer_scripts_have_correct_form():
    for name in ("Install-Mac.command", "Start-Mac.command"):
        path = ROOT / name
        assert path.stat().st_mode & stat.S_IXUSR, name + " must be executable"
        assert b"\r\n" not in path.read_bytes(), name + " must use LF line endings"
    for name in ("Install-Windows.bat", "Start-Windows.bat"):
        data = (ROOT / name).read_bytes()
        assert all(b < 128 for b in data), name + " must be plain ASCII"


def test_requirements_avoid_sleap_pypi_extra():
    """sleap[pypi] 1.4.1 pins PySide2 5.13-5.14 on Windows/Intel Macs, which has no
    Python 3.10 build, so installing it fails there (seen on Windows in v1.0.0)."""
    lines = [l.split("#")[0].strip().lower()
             for l in (ROOT / "requirements.txt").read_text().splitlines()]
    lines = [l for l in lines if l]
    assert not any(l.startswith("sleap[") for l in lines)
    assert not any(l.startswith("pyside2") for l in lines)
    assert "sleap==1.4.1" in lines
    assert any(l.startswith("tensorflow>=") and 'platform_machine != "arm64"' in l for l in lines)


def test_failing_commands_reports_broken_programs():
    from installer.setup_app import failing_commands

    failures = failing_commands([
        ("works", [sys.executable, "-c", "print('hi')"]),
        ("broken", [sys.executable, "-c", "import pkg_that_does_not_exist"]),
        ("missing", [str(ROOT / "no-such-program.exe")]),
    ])
    names = [name for name, _ in failures]
    assert names == ["broken", "missing"]
    assert "pkg_that_does_not_exist" in failures[0][1]


def test_pipeline_commands_cover_every_step():
    from installer.setup_app import pipeline_commands

    cmds = dict(pipeline_commands(ROOT))
    assert set(cmds) == {"SLEAP inference", "NAPS identity correction", "SLEAP CSV export",
                         "Interaction detection", "Group split"}
    assert all(cmd[-1] == "--help" for cmd in cmds.values())


def test_pkg_resources_available():
    """tensorflow-hub 0.14 (Windows / Intel Mac) imports pkg_resources at startup;
    setuptools >= 82 no longer ships it (v1.0.1 failed on Windows this way)."""
    import importlib.util

    assert importlib.util.find_spec("pkg_resources") is not None, \
        "pkg_resources missing - run: python install_requirements.py  (setuptools<81)"


def test_mac_scripts_are_valid_bash():
    for name in ("Install-Mac.command", "Start-Mac.command"):
        subprocess.run(["bash", "-n", str(ROOT / name)], check=True)
