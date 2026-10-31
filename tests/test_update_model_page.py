def test_replace_btn_disabled_by_default(qtbot):
    from gui_state import AppState
    from gui_pages.update_model import UpdateModelPage

    page = UpdateModelPage(AppState(model_path="", model_name="v1"))
    qtbot.addWidget(page)
    assert not page._replace_btn.isEnabled()

def test_replace_btn_enabled_for_valid_model_folder(qtbot, tmp_path):
    from gui_state import AppState
    from gui_pages.update_model import UpdateModelPage

    model_dir = tmp_path / "new_model"
    model_dir.mkdir()
    (model_dir / "best_model.h5").touch()
    (model_dir / "training_config.json").touch()

    page = UpdateModelPage(AppState(model_path="", model_name="v1"))
    qtbot.addWidget(page)
    page._on_folder_selected(str(model_dir))
    assert page._replace_btn.isEnabled()

def test_replace_btn_disabled_for_folder_without_weights(qtbot, tmp_path, monkeypatch):
    from gui_state import AppState
    from gui_pages.update_model import UpdateModelPage

    bad_dir = tmp_path / "bad_model"
    bad_dir.mkdir()
    (bad_dir / "readme.txt").touch()

    monkeypatch.setattr(
        "gui_pages.update_model.QMessageBox.warning", lambda *a, **kw: None,
    )
    page = UpdateModelPage(AppState(model_path="", model_name="v1"))
    qtbot.addWidget(page)
    page._on_folder_selected(str(bad_dir))
    assert not page._replace_btn.isEnabled()

def test_replace_updates_app_state(qtbot, tmp_path, monkeypatch):
    import gui_state
    from gui_state import AppState
    from gui_pages.update_model import UpdateModelPage

    monkeypatch.setattr(gui_state, "CONFIG_PATH", tmp_path / "config.json")

    # Old model lives in tmp_path/old_model
    old_dir = tmp_path / "models" / "old_model"
    old_dir.mkdir(parents=True)
    (old_dir / "best_model.h5").touch()

    # New model to stage, outside the models folder
    new_dir = tmp_path / "incoming" / "new_model"
    new_dir.mkdir(parents=True)
    (new_dir / "best_model.h5").touch()
    (new_dir / "training_config.json").touch()

    state = AppState(model_path=str(old_dir), model_name="old_model")
    page = UpdateModelPage(state)
    qtbot.addWidget(page)
    page._on_folder_selected(str(new_dir))

    emitted = []
    page.model_updated.connect(lambda: emitted.append(True))

    # Suppress QMessageBox during test
    monkeypatch.setattr(
        "gui_pages.update_model.QMessageBox.information",
        lambda *a, **kw: None,
    )
    from PyQt5.QtWidgets import QMessageBox
    monkeypatch.setattr(
        "gui_pages.update_model.QMessageBox.question",
        lambda *a, **kw: QMessageBox.Yes,
    )
    page._do_replace()

    dest = tmp_path / "models" / "new_model"
    assert state.model_name == "new_model"
    assert dest.is_dir() and (dest / "best_model.h5").exists()   # copied next to old
    assert not old_dir.exists()                                   # old removed
    assert new_dir.exists()                                       # source untouched
    assert state.resolved_model_path() == dest
    assert emitted == [True]


def test_replace_cancelled_keeps_old_model(qtbot, tmp_path, monkeypatch):
    import gui_state
    from gui_state import AppState
    from gui_pages.update_model import UpdateModelPage
    from PyQt5.QtWidgets import QMessageBox

    monkeypatch.setattr(gui_state, "CONFIG_PATH", tmp_path / "config.json")
    old_dir = tmp_path / "models" / "old_model"
    old_dir.mkdir(parents=True)
    new_dir = tmp_path / "incoming" / "new_model"
    new_dir.mkdir(parents=True)
    (new_dir / "best_model.h5").touch()
    (new_dir / "training_config.json").touch()

    state = AppState(model_path=str(old_dir), model_name="old_model")
    page = UpdateModelPage(state)
    qtbot.addWidget(page)
    page._on_folder_selected(str(new_dir))
    monkeypatch.setattr(
        "gui_pages.update_model.QMessageBox.question",
        lambda *a, **kw: QMessageBox.Cancel,
    )
    page._do_replace()

    assert old_dir.exists()
    assert state.model_name == "old_model"
    assert not (tmp_path / "models" / "new_model").exists()
