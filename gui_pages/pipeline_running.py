import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QProcess, QProcessEnvironment, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from gui_state import PROJECT_DIR

# Top-level steps printed by main.py: "Step N/3 — description"
_STEP_RE  = re.compile(r"^\s*Step\s+(\d+)/3\s+—\s*(.*)$")
# Sub-stages of step 1 printed by video_to_csv.py: "Stage N/3 — description"
_STAGE_RE = re.compile(r"^\s*Stage\s+(\d+)/3\s+—\s*(.*)$")
_OK_RE    = re.compile(r"\[OK\]")
_ERR_RE   = re.compile(r"\[ERROR\]|Traceback|Error:|Exception:")
_RUN_FOLDER_RE = re.compile(r"Run folder\s*:\s*(.+)")
# Per-frame progress printed by find_interactions_by_antennation.py
_FRAME_RE = re.compile(r"Frame\s+(\d+)/(\d+)")
# Percentages from progress bars (sleap-track / naps-track)
_PCT_RE   = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
# Frame count printed by video_to_csv.py before SLEAP starts
_LAST_FRAME_RE = re.compile(r"Last valid frame\s*:\s*(\d+)")

# sleap-track only prints its progress bar at the very end when its output is
# piped, so during SLEAP inference the bar is advanced by a time-based estimate.
# ~6 FPS is what CPU inference achieves on Apple Silicon for this model.
_SLEAP_NOMINAL_FPS = 6.0

# Share of the progress bar given to each step, as (start, end) percentages.
# Step 1 (SLEAP + NAPS) dominates the runtime.
_STEP_RANGES  = {1: (0, 80), 2: (80, 98), 3: (98, 100)}
_STAGE_RANGES = {1: (0, 55), 2: (55, 77), 3: (77, 80)}

_COLOR_OUT   = "#c9d1d9"
_COLOR_DIM   = "#6e7681"
_COLOR_OK    = "#3fb950"
_COLOR_ERR   = "#f85149"
_COLOR_STEP  = "#58a6ff"

_BAR_STYLE = (
    "QProgressBar {{ background:#21262d; border:none; border-radius:4px;"
    " height:10px; text-align:center; color:#f0f6fc; font-size:8pt; }}"
    "QProgressBar::chunk {{ background:{}; border-radius:4px; }}"
)


def _fmt_elapsed(seconds):
    # type: (float) -> str
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return "{:d}:{:02d}:{:02d}".format(h, m, s) if h else "{:d}:{:02d}".format(m, s)


def _python_executable():
    # type: () -> str
    """Interpreter for the pipeline: python.exe even if the GUI runs under pythonw.exe
    (pythonw has no usable stdout, so the log would stay empty)."""
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        console = exe.with_name("python.exe")
        if console.exists():
            return str(console)
    return str(exe)


def _script_dirs():
    # type: () -> list
    """Where this environment's console scripts (sleap-track, …) live:
    next to the interpreter (venv), or in Scripts\\ (Windows conda env)."""
    exe_dir = Path(sys.executable).parent
    return [str(d) for d in (exe_dir, exe_dir / "Scripts") if d.is_dir()]


def _kill_tree(pid):
    # type: (int) -> None
    """Terminate a process and all of its descendants (sleap-track, naps-track, ...)."""
    try:
        import psutil
    except ImportError:
        return
    try:
        parent = psutil.Process(pid)
        procs = parent.children(recursive=True) + [parent]
    except psutil.Error:
        return
    for p in procs:
        try:
            p.terminate()
        except psutil.Error:
            pass
    _, alive = psutil.wait_procs(procs, timeout=3)
    for p in alive:
        try:
            p.kill()
        except psutil.Error:
            pass


class RunningPage(QWidget):
    done     = pyqtSignal(str, bool)   # (output_dir, show_video)
    canceled = pyqtSignal()            # user left the page (cancel or back after failure)

    def __init__(self, parent=None):
        super(RunningPage, self).__init__(parent)
        self._process = None  # type: Optional[QProcess]
        self._output_dir = ""
        self._show_video = False
        self._current_step = 0
        self._current_stage = 0
        self._canceled = False
        self._finished = False
        self._start_time = 0.0
        self._stage_start = 0.0
        self._n_frames = 0
        self._buffers = {"out": "", "err": ""}
        self._setup_ui()
        self._clock = QTimer(self)
        self._clock.setInterval(1000)
        self._clock.timeout.connect(self._update_elapsed)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet(
            "font-size: 9pt; color: #8b949e; background:#161b22;"
            " border:1px solid #21262d; border-radius:4px; padding:6px 8px;"
        )
        layout.addWidget(self._summary)

        status_row = QHBoxLayout()
        self._step_lbl = QLabel("Starting…")
        self._step_lbl.setWordWrap(True)
        self._step_lbl.setStyleSheet("font-size: 10pt; color: #f0f6fc; font-weight: bold;")
        self._elapsed_lbl = QLabel("0:00")
        self._elapsed_lbl.setStyleSheet("font-size: 9pt; color: #8b949e;")
        status_row.addWidget(self._step_lbl, 1)
        status_row.addWidget(self._elapsed_lbl, 0, Qt.AlignRight | Qt.AlignTop)
        layout.addLayout(status_row)

        self._sub_lbl = QLabel("")
        self._sub_lbl.setStyleSheet("font-size: 9pt; color: #8b949e;")
        layout.addWidget(self._sub_lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setFormat("%p%")
        self._bar.setStyleSheet(_BAR_STYLE.format("#e94560"))
        layout.addWidget(self._bar)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(5000)
        self._log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._log.setStyleSheet(
            "QPlainTextEdit { background:#010409; color:#c9d1d9; border:1px solid #21262d;"
            " border-radius:4px; font-family:Menlo, Monaco, Consolas, monospace; font-size:9pt; }"
        )
        layout.addWidget(self._log, 1)

        self._cancel_btn = QPushButton("■   CANCEL")
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(self._cancel_btn)
        self._set_button_mode("cancel")

    def _set_button_mode(self, mode):
        # type: (str) -> None
        if mode == "cancel":
            self._cancel_btn.setText("■   CANCEL")
            self._cancel_btn.setStyleSheet(
                "QPushButton { background:#6e2020; color:white; padding:8px;"
                " border-radius:4px; font-weight:bold; border:1px solid #8b2020; }"
                "QPushButton:hover { background:#8b2020; }"
            )
        else:
            self._cancel_btn.setText("←   BACK")
            self._cancel_btn.setStyleSheet(
                "QPushButton { background:#21262d; color:#f0f6fc; padding:8px;"
                " border-radius:4px; font-weight:bold; border:1px solid #30363d; }"
                "QPushButton:hover { background:#30363d; }"
            )

    # ── Process control ───────────────────────────────────────────────────────
    def build_command(self, params, output_dir):
        # type: (dict, str) -> list
        """Arguments passed to the Python interpreter to run the pipeline."""
        cmd_args = [
            "-u", str(PROJECT_DIR / "main.py"),
            "--input",  str(Path(params["video_path"]).resolve()),
            "--output", str(Path(output_dir).resolve()),
            "--touch-thresh",     str(params["touch_thresh"]),
            "--min-touch-frames", str(params["min_touch_frames"]),
            "--d-exit-factor",    str(params["d_exit_factor"]),
            "--max-frames",       str(params["max_frames"]),
            "--no-show-live",
        ]
        if params.get("model_path"):
            cmd_args += ["--model", str(params["model_path"])]
        if not params.get("save_video", True):
            cmd_args.append("--no-save-video")
        return cmd_args

    def start(self, params, output_dir):
        # type: (dict, str) -> None
        self.stop_process()
        self._canceled = False
        self._finished = False
        self._output_dir = output_dir
        self._show_video = params.get("show_video", False) and params.get("save_video", True)
        self._current_step = 0
        self._current_stage = 0
        self._n_frames = 0
        self._buffers = {"out": "", "err": ""}
        self._log.clear()
        self._bar.setValue(0)
        self._bar.setStyleSheet(_BAR_STYLE.format("#e94560"))
        self._step_lbl.setText("Starting…")
        self._sub_lbl.setText("")
        self._summary.setText(params.get("summary", ""))
        self._set_button_mode("cancel")

        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        env.insert("PYTHONIOENCODING", "utf-8")
        # Make the environment's console scripts (sleap-track, naps-track…)
        # resolvable even when the GUI was started without activating it.
        env.insert("PATH", os.pathsep.join(_script_dirs() + [env.value("PATH", "")]))

        self._process = QProcess(self)
        self._process.setProcessEnvironment(env)
        self._process.setWorkingDirectory(str(PROJECT_DIR))
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        self._start_time = time.monotonic()
        self._elapsed_lbl.setText("0:00")
        self._clock.start()
        self._process.start(_python_executable(), self.build_command(params, output_dir))

    def is_running(self):
        # type: () -> bool
        return self._process is not None and self._process.state() != QProcess.NotRunning

    def stop_process(self):
        # type: () -> None
        """Stop the pipeline and every subprocess it spawned."""
        if not self.is_running():
            return
        pid = int(self._process.processId())
        if pid:
            _kill_tree(pid)
        if self._process.state() != QProcess.NotRunning:
            self._process.kill()
            self._process.waitForFinished(3000)

    # ── Output handling ───────────────────────────────────────────────────────
    def _on_stdout(self):
        self._consume("out", self._process.readAllStandardOutput().data())

    def _on_stderr(self):
        self._consume("err", self._process.readAllStandardError().data())

    def _consume(self, stream, raw):
        # type: (str, bytes) -> None
        text = self._buffers[stream] + raw.decode("utf-8", errors="replace")
        lines = text.split("\n")
        self._buffers[stream] = lines.pop()  # keep incomplete trailing line
        for line in lines:
            self._handle_line(line, stream)
        # Progress bars redraw with \r and no newline: parse their latest state
        # without logging every redraw.
        pending = self._buffers[stream]
        if "\r" in pending:
            self._parse_progress(pending.rstrip("\r").split("\r")[-1])

    def _flush_buffers(self):
        for stream in ("out", "err"):
            if self._buffers[stream]:
                self._handle_line(self._buffers[stream], stream)
                self._buffers[stream] = ""

    def _handle_line(self, line, stream="out"):
        # type: (str, str) -> None
        # A \r-redrawn progress bar: only the final state is worth showing.
        line = line.rstrip("\r").split("\r")[-1].rstrip()
        if not line.strip():
            if stream == "out":
                self._append_line("")
            return
        color = None
        if stream == "err" and not _ERR_RE.search(line):
            color = _COLOR_DIM   # warnings / progress chatter from TF, SLEAP, NAPS
        self._append_line(line, color=color)
        self._parse_progress(line)

    def _append_line(self, line, color=None):
        # type: (str, Optional[str]) -> None
        if color is None:
            if _OK_RE.search(line):
                color = _COLOR_OK
            elif _ERR_RE.search(line):
                color = _COLOR_ERR
            elif _STEP_RE.search(line) or _STAGE_RE.search(line):
                color = _COLOR_STEP
            else:
                color = _COLOR_OUT
        sb = self._log.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        cursor = QTextCursor(self._log.document())
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if not self._log.document().isEmpty():
            cursor.insertBlock()
        cursor.insertText(line, fmt)
        if at_bottom:
            sb.setValue(sb.maximum())

    def _set_progress(self, value):
        # type: (float) -> None
        value = int(max(0, min(100, value)))
        if value > self._bar.value():
            self._bar.setValue(value)

    def _parse_progress(self, line):
        # type: (str) -> None
        mf = _RUN_FOLDER_RE.search(line)
        if mf:
            self._output_dir = mf.group(1).strip()
            return
        ml = _LAST_FRAME_RE.search(line)
        if ml:
            self._n_frames = int(ml.group(1)) + 1
            return

        m = _STEP_RE.search(line)
        if m:
            step = int(m.group(1))
            self._current_step = step
            self._current_stage = 0
            self._step_lbl.setText("Step {}/3 — {}".format(step, m.group(2).strip()))
            self._sub_lbl.setText("")
            self._set_progress(_STEP_RANGES.get(step, (0, 0))[0])
            return

        m = _STAGE_RE.search(line)
        if m and self._current_step == 1:
            stage = int(m.group(1))
            self._current_stage = stage
            self._stage_start = time.monotonic()
            self._sub_lbl.setText("Stage {}/3 — {}".format(stage, m.group(2).strip()))
            self._set_progress(_STAGE_RANGES.get(stage, (0, 0))[0])
            return

        if _OK_RE.search(line):
            if "Stage" in line and self._current_stage in _STAGE_RANGES:
                self._set_progress(_STAGE_RANGES[self._current_stage][1])
            elif self._current_step in _STEP_RANGES:
                self._set_progress(_STEP_RANGES[self._current_step][1])
            return

        # Fine-grained progress inside a step / stage
        lo_hi = None
        if self._current_step == 1 and self._current_stage in _STAGE_RANGES:
            lo_hi = _STAGE_RANGES[self._current_stage]
        elif self._current_step in _STEP_RANGES:
            lo_hi = _STEP_RANGES[self._current_step]
        if lo_hi is None:
            return
        frac = None
        mf = _FRAME_RE.search(line)
        if mf and int(mf.group(2)) > 0:
            frac = int(mf.group(1)) / float(int(mf.group(2)))
        else:
            mp = _PCT_RE.search(line)
            if mp:
                frac = float(mp.group(1)) / 100.0
        if frac is not None and 0.0 <= frac <= 1.0:
            lo, hi = lo_hi
            self._set_progress(lo + (hi - lo) * frac)

    def _update_elapsed(self):
        self._elapsed_lbl.setText(_fmt_elapsed(time.monotonic() - self._start_time))
        if self._current_step == 1 and self._current_stage == 1 and self._n_frames:
            # Asymptotic estimate: ~63% at the expected duration, never reaches the end.
            expected = self._n_frames / _SLEAP_NOMINAL_FPS
            frac = 0.95 * (1.0 - math.exp(-(time.monotonic() - self._stage_start) / expected))
            lo, hi = _STAGE_RANGES[1]
            self._set_progress(lo + (hi - lo) * frac)

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    def _cancel(self):
        if self._finished:
            self.canceled.emit()
            return
        self._canceled = True
        self._clock.stop()
        self.stop_process()
        self.canceled.emit()

    def _fail(self, message):
        # type: (str) -> None
        self._finished = True
        self._clock.stop()
        self._update_elapsed()
        self._step_lbl.setText("✗  Pipeline failed")
        self._sub_lbl.setText(message)
        self._bar.setStyleSheet(_BAR_STYLE.format("#da3633"))
        self._append_line("")
        self._append_line("[ERROR] " + message, color=_COLOR_ERR)
        self._set_button_mode("back")

    def _on_error(self, error):
        if self._canceled or error != QProcess.FailedToStart:
            return
        self._fail("Could not start Python ({}): {}".format(
            _python_executable(), self._process.errorString()))

    def _on_finished(self, exit_code, exit_status):
        self._flush_buffers()
        if self._canceled or self._finished:
            return
        if exit_status == QProcess.NormalExit and exit_code == 0:
            self._finished = True
            self._clock.stop()
            self._update_elapsed()
            self._bar.setValue(100)
            self._bar.setStyleSheet(_BAR_STYLE.format("#238636"))
            self._step_lbl.setText("✓  Pipeline complete")
            self._sub_lbl.setText("")
            self._set_button_mode("back")
            self.done.emit(self._output_dir, self._show_video)
        elif exit_status == QProcess.CrashExit:
            self._fail("Pipeline process crashed.")
        else:
            self._fail("Pipeline exited with code {} — see the log above.".format(exit_code))
