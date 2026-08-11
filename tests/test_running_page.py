def test_progress_bar_advances_on_step_line(qtbot):
    from gui_pages.pipeline_running import RunningPage

    page = RunningPage()
    qtbot.addWidget(page)
    page._parse_progress("Step 2/3 — Interaction detection")

    assert page._current_step == 2
    assert page._bar.value() == 33   # (2-1)*100//3

def test_progress_bar_advances_on_ok_line(qtbot):
    from gui_pages.pipeline_running import RunningPage

    page = RunningPage()
    qtbot.addWidget(page)
    page._current_step = 1
    page._parse_progress("[OK] Step 1 completed.")

    assert page._bar.value() == 33   # 1*100//3

def test_log_appends_text(qtbot):
    from gui_pages.pipeline_running import RunningPage

    page = RunningPage()
    qtbot.addWidget(page)
    page._append_line("hello world")

    assert "hello world" in page._log.toPlainText()

def test_cancel_emits_signal(qtbot):
    from gui_pages.pipeline_running import RunningPage

    page = RunningPage()
    qtbot.addWidget(page)

    received = []
    page.canceled.connect(lambda: received.append(True))
    # No process running, so just check signal fires
    page._process = None
    page._cancel()
    assert received == [True]
