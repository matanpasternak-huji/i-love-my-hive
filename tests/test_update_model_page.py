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
    (model_dir / "saved_model.pb").touch()

    page = UpdateModelPage(AppState(model_path="", model_name="v1"))
    qtbot.addWidget(page)
    page._on_folder_selected(str(model_dir))
    assert page._replace_btn.isEnabled()

def test_replace_btn_disabled_for_folder_without_weights(qtbot, tmp_path):
    from gui_state import AppState
    from gui_pages.update_model import UpdateModelPage

    bad_dir = tmp_path / "bad_model"
    bad_dir.mkdir()
    (bad_dir / "readme.txt").touch()

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
    old_dir = tmp_path / "old_model"
    old_dir.mkdir()
    (old_dir / "weights.pb").touch()

    # New model to stage
    new_dir = tmp_path / "new_model"
    new_dir.mkdir()
    (new_dir / "weights.pb").touch()

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
    page._do_replace()

    assert state.model_name == "new_model"
    assert emitted == [True]
