import json
import pytest

def test_appstate_save_and_load(tmp_path, monkeypatch):
    import gui_state
    monkeypatch.setattr(gui_state, "CONFIG_PATH", tmp_path / "config.json")

    state = gui_state.AppState(
        model_path="Current Model/my_model.n=100",
        model_name="my_model",
    )
    state.save()

    loaded = gui_state.AppState.load()
    assert loaded.model_path == "Current Model/my_model.n=100"
    assert loaded.model_name == "my_model"

def test_appstate_load_missing_returns_defaults(tmp_path, monkeypatch):
    import gui_state
    monkeypatch.setattr(gui_state, "CONFIG_PATH", tmp_path / "nonexistent.json")

    state = gui_state.AppState.load()
    assert state.model_name == "(no model)"
    assert state.model_path == ""

def test_appstate_save_writes_valid_json(tmp_path, monkeypatch):
    import gui_state
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(gui_state, "CONFIG_PATH", config_path)

    gui_state.AppState(model_path="p", model_name="n").save()

    data = json.loads(config_path.read_text())
    assert data["model_path"] == "p"
    assert data["model_name"] == "n"
