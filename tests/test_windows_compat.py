"""Windows-layout behaviour, simulated with fake interpreter directories so it
runs on any OS."""
import sys


def _touch(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def test_tool_finds_exe_in_conda_scripts_dir(tmp_path, monkeypatch):
    import video_to_csv

    # Windows conda env: <env>\python.exe and <env>\Scripts\sleap-track.exe
    python = _touch(tmp_path / "env" / "python.exe")
    exe = _touch(tmp_path / "env" / "Scripts" / "sleap-track.exe")
    monkeypatch.setattr(sys, "executable", str(python))

    assert video_to_csv.tool("sleap-track") == str(exe)


def test_tool_finds_exe_next_to_venv_python(tmp_path, monkeypatch):
    import video_to_csv

    # Windows venv: <venv>\Scripts\python.exe and <venv>\Scripts\naps-track.exe
    python = _touch(tmp_path / "venv" / "Scripts" / "python.exe")
    exe = _touch(tmp_path / "venv" / "Scripts" / "naps-track.exe")
    monkeypatch.setattr(sys, "executable", str(python))

    assert video_to_csv.tool("naps-track") == str(exe)


def test_tool_finds_posix_script(tmp_path, monkeypatch):
    import video_to_csv

    python = _touch(tmp_path / "venv" / "bin" / "python")
    script = _touch(tmp_path / "venv" / "bin" / "sleap-convert")
    monkeypatch.setattr(sys, "executable", str(python))

    assert video_to_csv.tool("sleap-convert") == str(script)


def test_tool_falls_back_to_bare_name(tmp_path, monkeypatch):
    import video_to_csv

    python = _touch(tmp_path / "bin" / "python")
    monkeypatch.setattr(sys, "executable", str(python))

    assert video_to_csv.tool("sleap-track") == "sleap-track"


def test_gui_runs_pipeline_with_python_not_pythonw(tmp_path, monkeypatch):
    from gui_pages import pipeline_running as rp

    pythonw = _touch(tmp_path / "Scripts" / "pythonw.exe")
    python = _touch(tmp_path / "Scripts" / "python.exe")
    monkeypatch.setattr(sys, "executable", str(pythonw))

    assert rp._python_executable() == str(python)


def test_gui_path_includes_conda_scripts_dir(tmp_path, monkeypatch):
    from gui_pages import pipeline_running as rp

    python = _touch(tmp_path / "env" / "python.exe")
    (tmp_path / "env" / "Scripts").mkdir()
    monkeypatch.setattr(sys, "executable", str(python))

    assert rp._script_dirs() == [str(tmp_path / "env"), str(tmp_path / "env" / "Scripts")]


def test_model_path_saved_with_forward_slashes(qtbot, tmp_path, monkeypatch):
    import gui_state
    from gui_state import AppState
    from gui_pages import update_model

    monkeypatch.setattr(gui_state, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(update_model, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(gui_state, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(update_model.QMessageBox, "information", lambda *a, **k: None)

    new_dir = tmp_path / "incoming" / "my_model"
    _touch(new_dir / "best_model.h5")
    _touch(new_dir / "training_config.json")

    state = AppState(model_path="", model_name="(no model)")
    page = update_model.UpdateModelPage(state)
    qtbot.addWidget(page)
    page._on_folder_selected(str(new_dir))
    page._do_replace()

    assert state.model_path == "Current Model/my_model"
    assert "\\" not in (tmp_path / "config.json").read_text().replace("\\n", "")
