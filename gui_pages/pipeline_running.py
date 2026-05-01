import re
import sys
from typing import Optional

from PyQt5.QtCore import QProcess, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QLabel, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

_STEP_RE = re.compile(r"Step\s+(\d+)/3\s+")
_OK_RE   = re.compile(r"\[OK\]")
_ERR_RE  = re.compile(r"\[ERROR\]")


class RunningPage(QWidget):
    done     = pyqtSignal(str, bool)   # (output_dir, show_video)
    canceled = pyqtSignal()

    def __init__(self, parent=None):
        super(RunningPage, self).__init__(parent)
        self._process = None  # type: Optional[QProcess]
        self._output_dir = ""
        self._show_video = False
        self._current_step = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("font-size: 8pt; color: #3d444d;")
        layout.addWidget(self._summary)

        self._step_lbl = QLabel("Starting…")
        self._step_lbl.setStyleSheet("font-size: 9pt; color: #8b949e;")
        layout.addWidget(self._step_lbl)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setStyleSheet(
            "QProgressBar { background:#21262d; border-radius:3px; height:6px; text-align:center; }"
            "QProgressBar::chunk { background:#e94560; border-radius:3px; }"
        )
        layout.addWidget(self._bar)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(
            "background:#0d0d1a; color:#7fba00; font-family:monospace; font-size:9pt;"
        )
        layout.addWidget(self._log)

        self._cancel_btn = QPushButton("■   CANCEL")
        self._cancel_btn.setStyleSheet(
            "QPushButton { background:#6e2020; color:white; padding:7px;"
            " border-radius:4px; font-weight:bold; }"
            "QPushButton:hover { background:#8b2020; }"
        )
        self._cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(self._cancel_btn)

    def start(self, params, output_dir):
        # type: (dict, str) -> None
        self._output_dir = output_dir
        self._show_video = params.get("show_video", False) and params.get("save_video", True)
        self._current_step = 0
        self._log.clear()
        self._bar.setValue(0)
        self._step_lbl.setText("Step 1/3 — Starting…")
        self._summary.setText(params.get("summary", ""))

        cmd_args = [
            "main.py",
            "--input",  params["video_path"],
            "--output", output_dir,
            "--touch-thresh",     str(params["touch_thresh"]),
            "--min-touch-frames", str(params["min_touch_frames"]),
            "--d-exit-factor",    str(params["d_exit_factor"]),
            "--max-frames",       str(params["max_frames"]),
            "--no-show-live",
        ]
        if not params.get("save_video", True):
            cmd_args.append("--no-save-video")

        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)
        self._process.start(sys.executable, cmd_args)

    def _on_stdout(self):
        text = self._process.readAllStandardOutput().data().decode("utf-8", errors="replace")
        for line in text.splitlines():
            self._append_line(line)
            self._parse_progress(line)

    def _on_stderr(self):
        text = self._process.readAllStandardError().data().decode("utf-8", errors="replace")
        for line in text.splitlines():
            self._append_line(line, color="#da3633")

    def _append_line(self, line, color=None):
        # type: (str, Optional[str]) -> None
        if color is None:
            if _OK_RE.search(line):
                color = "#3fb950"
            elif _ERR_RE.search(line):
                color = "#da3633"
            else:
                color = "#7fba00"
        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(line + "\n", fmt)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def _parse_progress(self, line):
        # type: (str) -> None
        m = _STEP_RE.search(line)
        if m:
            step = int(m.group(1))
            self._current_step = step
            self._step_lbl.setText(line.strip())
            self._bar.setValue((step - 1) * 100 // 3)
        elif _OK_RE.search(line) and self._current_step > 0:
            self._bar.setValue(self._current_step * 100 // 3)

    def _cancel(self):
        if self._process and self._process.state() == QProcess.Running:
            self._process.terminate()
        self.canceled.emit()

    def _on_finished(self, exit_code, _exit_status):
        if exit_code == 0:
            self._bar.setValue(100)
            self.done.emit(self._output_dir, self._show_video)
        else:
            self._append_line(
                "\n[ERROR] Pipeline exited with code {}".format(exit_code), color="#da3633"
            )
