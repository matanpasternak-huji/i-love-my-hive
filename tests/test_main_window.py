import pytest

def test_mainwindow_starts_on_home(qtbot):
    from gui import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    assert win._stack.currentIndex() == 0

def test_run_btn_navigates_to_pipeline(qtbot):
    from gui import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    win._home.run_btn.click()
    assert win._stack.currentIndex() == 1

def test_model_btn_navigates_to_update(qtbot):
    from gui import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    win._home.model_btn.click()
    assert win._stack.currentIndex() == 3

def test_back_from_pipeline_returns_home(qtbot):
    from gui import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    win._stack.setCurrentIndex(1)
    win._pipeline.back_requested.emit()
    assert win._stack.currentIndex() == 0

def test_back_from_update_returns_home(qtbot):
    from gui import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    win._stack.setCurrentIndex(3)
    win._update.back_requested.emit()
    assert win._stack.currentIndex() == 0

def test_pipeline_cancel_returns_to_pipeline_idle(qtbot):
    from gui import MainWindow
    win = MainWindow()
    qtbot.addWidget(win)
    win._stack.setCurrentIndex(2)
    win._running.canceled.emit()
    assert win._stack.currentIndex() == 1
