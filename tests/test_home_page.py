def test_homepage_shows_model_name(qtbot):
    from gui_state import AppState
    from gui_pages.home import HomePage

    state = AppState(model_path="models/v1", model_name="v1_model")
    page = HomePage(state)
    qtbot.addWidget(page)

    assert "v1_model" in page._model_label.text()

def test_homepage_refresh_model_label(qtbot):
    from gui_state import AppState
    from gui_pages.home import HomePage

    state = AppState(model_path="models/v1", model_name="v1_model")
    page = HomePage(state)
    qtbot.addWidget(page)

    state.model_name = "v2_model"
    page.refresh_model_label()

    assert "v2_model" in page._model_label.text()

def test_homepage_has_run_and_model_buttons(qtbot):
    from gui_state import AppState
    from gui_pages.home import HomePage

    state = AppState(model_path="", model_name="test")
    page = HomePage(state)
    qtbot.addWidget(page)
    page.show()

    assert page.run_btn.isVisible()
    assert page.model_btn.isVisible()
