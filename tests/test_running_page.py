import sys


def _page(qtbot):
    from gui_pages.pipeline_running import RunningPage

    page = RunningPage()
    qtbot.addWidget(page)
    return page


def test_progress_bar_advances_on_step_line(qtbot):
    from gui_pages.pipeline_running import _STEP_RANGES

    page = _page(qtbot)
    page._parse_progress("  Step 2/3 — Interaction detection (antennation-based)")

    assert page._current_step == 2
    assert page._bar.value() == _STEP_RANGES[2][0]
    assert "Interaction detection" in page._step_lbl.text()


def test_progress_bar_advances_on_ok_line(qtbot):
    from gui_pages.pipeline_running import _STEP_RANGES

    page = _page(qtbot)
    page._current_step = 1
    page._parse_progress("[OK] Step 1/3 — SLEAP inference + NAPS identity correction completed.")

    assert page._bar.value() == _STEP_RANGES[1][1]


def test_stage_lines_do_not_change_top_level_step(qtbot):
    from gui_pages.pipeline_running import _STAGE_RANGES

    page = _page(qtbot)
    page._parse_progress("  Step 1/3 — SLEAP inference + NAPS identity correction")
    page._parse_progress("  Stage 2/3 — NAPS identity correction (ArUco barcode tracking)")

    assert page._current_step == 1
    assert page._current_stage == 2
    assert page._bar.value() == _STAGE_RANGES[2][0]

    page._parse_progress("[OK] Stage 2/3 — NAPS identity correction completed successfully.")
    assert page._current_step == 1
    assert page._bar.value() == _STAGE_RANGES[2][1]


def test_frame_progress_within_step(qtbot):
    from gui_pages.pipeline_running import _STEP_RANGES

    page = _page(qtbot)
    page._parse_progress("  Step 2/3 — Interaction detection")
    page._parse_progress("  Frame 50/100 | active: 0")

    lo, hi = _STEP_RANGES[2]
    assert page._bar.value() == int(lo + (hi - lo) * 0.5)


def test_progress_never_goes_backwards(qtbot):
    page = _page(qtbot)
    page._parse_progress("  Step 2/3 — Interaction detection")
    before = page._bar.value()
    page._parse_progress("  Stage 1/3 — something")   # ignored outside step 1
    page._parse_progress("  Frame 1/1000")
    assert page._bar.value() == before


def test_sleap_stage_time_estimate_advances(qtbot):
    from gui_pages.pipeline_running import _STAGE_RANGES

    page = _page(qtbot)
    page._parse_progress("  Last valid frame : 599 (auto-detected)")
    page._parse_progress("  Step 1/3 — SLEAP inference + NAPS identity correction")
    page._parse_progress("  Stage 1/3 — SLEAP multi-instance inference")
    assert page._n_frames == 600

    page._stage_start -= 100   # pretend 100 s passed (expected ≈ 600 / 6 = 100 s)
    page._update_elapsed()
    lo, hi = _STAGE_RANGES[1]
    assert lo < page._bar.value() < hi


def test_run_folder_is_captured(qtbot):
    page = _page(qtbot)
    page._parse_progress("Run folder : /tmp/out/20260101_000000")
    assert page._output_dir == "/tmp/out/20260101_000000"


def test_partial_lines_are_buffered(qtbot):
    page = _page(qtbot)
    page._consume("out", b"hello wo")
    assert "hello" not in page._log.toPlainText()
    page._consume("out", b"rld\nnext")
    assert "hello world" in page._log.toPlainText()
    page._flush_buffers()
    assert "next" in page._log.toPlainText()


def test_carriage_return_progress_keeps_last_state(qtbot):
    page = _page(qtbot)
    page._consume("err", b"Predicting 10%\rPredicting 50%\rPredicting 100%\n")
    text = page._log.toPlainText()
    assert "Predicting 100%" in text
    assert "10%" not in text


def test_log_appends_text(qtbot):
    page = _page(qtbot)
    page._append_line("hello world")

    assert "hello world" in page._log.toPlainText()


def test_cancel_emits_signal(qtbot):
    page = _page(qtbot)

    received = []
    page.canceled.connect(lambda: received.append(True))
    # No process running, so just check signal fires
    page._process = None
    page._cancel()
    assert received == [True]


def test_build_command_includes_model_and_flags(qtbot, tmp_path):
    page = _page(qtbot)
    video = tmp_path / "v.mp4"
    video.touch()
    args = page.build_command({
        "video_path": str(video), "touch_thresh": 40, "min_touch_frames": 6,
        "d_exit_factor": 1.0, "max_frames": 1500, "save_video": False,
        "model_path": "/models/m",
    }, str(tmp_path / "out"))

    assert args[0] == "-u" and args[1].endswith("main.py")
    assert args[args.index("--model") + 1] == "/models/m"
    assert args[args.index("--input") + 1] == str(video.resolve())
    assert "--no-save-video" in args
    assert "--no-show-live" in args


def test_failed_run_shows_error_and_back_button(qtbot):
    from PyQt5.QtCore import QProcess

    page = _page(qtbot)
    page._process = QProcess(page)
    page._on_finished(3, QProcess.NormalExit)

    assert "failed" in page._step_lbl.text().lower()
    assert "BACK" in page._cancel_btn.text()
    assert "exited with code 3" in page._log.toPlainText()


def test_real_process_success_emits_done(qtbot, tmp_path, monkeypatch):
    """Drive a real QProcess through start() with a stand-in pipeline script."""
    import gui_pages.pipeline_running as rp

    fake = tmp_path / "main.py"
    fake.write_text(
        "import sys, time\n"
        "print('Run folder : ' + sys.argv[sys.argv.index('--output') + 1] + '/run1')\n"
        "print('  Step 1/3 — fake tracking'); sys.stdout.flush()\n"
        "sys.stderr.write('Predicting 40%\\rPredicting 90%\\n')\n"
        "print('[OK] Step 1/3 — fake tracking completed.')\n"
        "print('  Step 2/3 — fake detection')\n"
        "print('  Step 3/3 — fake split')\n"
        "print('[OK] Step 3/3 — fake split completed.')\n"
    )
    monkeypatch.setattr(rp, "PROJECT_DIR", tmp_path)
    page = _page(qtbot)
    video = tmp_path / "v.mp4"
    video.touch()

    with qtbot.waitSignal(page.done, timeout=15000) as blocker:
        page.start({
            "video_path": str(video), "touch_thresh": 40, "min_touch_frames": 6,
            "d_exit_factor": 1.0, "max_frames": 1500, "save_video": True,
            "show_video": True, "summary": "s",
        }, str(tmp_path / "out"))

    out_dir, show = blocker.args
    assert out_dir == str((tmp_path / "out").resolve()) + "/run1"
    assert show is True
    assert page._bar.value() == 100
    assert "Predicting 90%" in page._log.toPlainText()
    assert "BACK" in page._cancel_btn.text()


def test_cancel_kills_child_processes(qtbot, tmp_path, monkeypatch):
    """Cancel must also stop grandchildren (sleap-track etc.), not just main.py."""
    import psutil
    import gui_pages.pipeline_running as rp

    pidfile = tmp_path / "child.pid"
    fake = tmp_path / "main.py"
    fake.write_text(
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "open({!r}, 'w').write(str(child.pid))\n"
        "print('  Step 1/3 — waiting', flush=True)\n"
        "child.wait()\n".format(str(pidfile))
    )
    monkeypatch.setattr(rp, "PROJECT_DIR", tmp_path)
    page = _page(qtbot)
    video = tmp_path / "v.mp4"
    video.touch()
    page.start({
        "video_path": str(video), "touch_thresh": 40, "min_touch_frames": 6,
        "d_exit_factor": 1.0, "max_frames": 1500,
    }, str(tmp_path / "out"))

    qtbot.waitUntil(lambda: pidfile.exists() and pidfile.read_text().strip() != "", timeout=15000)
    child_pid = int(pidfile.read_text())
    assert psutil.pid_exists(child_pid)

    with qtbot.waitSignal(page.canceled, timeout=10000):
        page._cancel()

    qtbot.waitUntil(lambda: not page.is_running(), timeout=10000)
    try:
        proc = psutil.Process(child_pid)
        gone = proc.status() == psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        gone = True
    assert gone
