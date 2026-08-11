def test_run_button_disabled_without_video(qtbot):
    from gui_state import AppState
    from gui_pages.pipeline_idle import PipelinePage

    page = PipelinePage(AppState(model_path="", model_name="m"))
    qtbot.addWidget(page)
    assert not page._run_btn.isEnabled()


def test_run_button_enabled_after_video_selected(qtbot, tmp_path):
    from gui_state import AppState
    from gui_pages.pipeline_idle import PipelinePage

    page = PipelinePage(AppState(model_path="", model_name="m"))
    qtbot.addWidget(page)
    video = tmp_path / "test.mp4"
    video.touch()
    page._on_video_selected(str(video))
    assert page._run_btn.isEnabled()


def test_run_emits_correct_params(qtbot, tmp_path):
    from gui_state import AppState
    from gui_pages.pipeline_idle import PipelinePage

    page = PipelinePage(AppState(model_path="", model_name="m"))
    qtbot.addWidget(page)
    video = tmp_path / "test.mp4"
    video.touch()
    page._on_video_selected(str(video))

    emitted = []
    page.run_requested.connect(emitted.append)
    page._run_btn.click()

    assert len(emitted) == 1
    p = emitted[0]
    assert p["video_path"] == str(video)
    assert p["touch_thresh"]     == 50    # default
    assert p["min_touch_frames"] == 1    # default
    assert p["d_exit_factor"]    == 1.0  # default
    assert p["max_frames"]       == 1500 # default
    assert p["save_video"]       is True
    assert p["show_video"]       is True


def test_params_summary_contains_video_name(qtbot, tmp_path):
    from gui_state import AppState
    from gui_pages.pipeline_idle import PipelinePage

    page = PipelinePage(AppState(model_path="", model_name="mymodel"))
    qtbot.addWidget(page)
    video = tmp_path / "myvideo.mp4"
    video.touch()
    page._on_video_selected(str(video))

    summary = page.params_summary()
    assert "myvideo.mp4" in summary
    assert "mymodel" in summary