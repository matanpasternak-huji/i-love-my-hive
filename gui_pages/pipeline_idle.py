from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDoubleSpinBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from gui_widgets import DropZone

_TOOLTIPS = {
    "Exit Radius": (
        "How far a bee's head must move from the interaction centre "
        "(as a multiple of the average bee body length) before the interaction ends."
    ),
    "Cancel Time": (
        "Maximum interaction duration in frames. Interactions still active "
        "after this many frames are marked 'canceled'."
    ),
    "Touch Frames": (
        "How many consecutive frames both bees must have their antenna tips "
        "within Touch Distance before an interaction is counted as started."
    ),
    "Touch Distance": (
        "Maximum pixel distance between antenna tips to be considered touching."
    ),
}


class _ParamCell(QFrame):
    def __init__(self, name, spinbox, unit, tooltip, parent=None):
        # type: (str, object, str, str, object) -> None
        super(_ParamCell, self).__init__(parent)
        self._tooltip_text = tooltip
        self.spinbox = spinbox

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)
        self.setStyleSheet("_ParamCell { background: #0d1117; border-radius: 4px; }")

        top = QHBoxLayout()
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet("font-size: 9pt; color: #ccc; border: none;")
        q_btn = QPushButton("?")
        q_btn.setFixedSize(18, 18)
        q_btn.setStyleSheet(
            "QPushButton { background:#da3633; color:white; border-radius:9px;"
            " font-size:7pt; padding:0; border:none; }"
        )
        q_btn.clicked.connect(self._show_popup)
        top.addWidget(name_lbl)
        top.addStretch()
        top.addWidget(q_btn)

        spinbox.setStyleSheet("background:#161b22; color:#f0f6fc; border:none; padding:2px;")
        unit_lbl = QLabel(unit)
        unit_lbl.setStyleSheet("font-size: 8pt; color: #484f58; border: none;")

        layout.addLayout(top)
        layout.addWidget(spinbox)
        layout.addWidget(unit_lbl)

    def _show_popup(self):
        # type: () -> None
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.Popup)
        dlg.setStyleSheet("background:#161b22; color:#f0f6fc;")
        lbl = QLabel(self._tooltip_text, dlg)
        lbl.setWordWrap(True)
        lbl.setMargin(12)
        lbl.setMaximumWidth(280)
        v = QVBoxLayout(dlg)
        v.addWidget(lbl)
        dlg.adjustSize()
        dlg.exec_()


class PipelinePage(QWidget):
    run_requested  = pyqtSignal(dict)
    back_requested = pyqtSignal()

    def __init__(self, app_state, parent=None):
        # type: (object, object) -> None
        super(PipelinePage, self).__init__(parent)
        self._app_state = app_state
        self._video_path = None  # type: Optional[str]
        self._setup_ui()

    def _sec_label(self, text):
        # type: (str) -> QLabel
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 8pt; font-weight: bold; color: #58a6ff; letter-spacing: 1px;")
        return lbl

    def _setup_ui(self):
        # type: () -> None
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 14, 14, 14)

        # Back arrow
        back = QLabel("← Back")
        back.setStyleSheet("color:#58a6ff; font-size:9pt;")
        back.setCursor(Qt.PointingHandCursor)
        back.mousePressEvent = lambda _: self.back_requested.emit()
        layout.addWidget(back, alignment=Qt.AlignLeft)

        # Video
        layout.addWidget(self._sec_label("VIDEO FILE"))
        self._drop = DropZone("🎬  Drop .mp4 here", filter="Video (*.mp4)", parent=self)
        self._drop.path_selected.connect(self._on_video_selected)
        layout.addWidget(self._drop)

        # Active model badge
        layout.addWidget(self._sec_label("ACTIVE MODEL"))
        self._model_badge = QLabel("●  {}".format(self._app_state.model_name))
        self._model_badge.setStyleSheet(
            "color:#3fb950; background:#0d1117; border:1px solid #238636;"
            " border-radius:4px; padding:5px 8px;"
        )
        layout.addWidget(self._model_badge)

        # Parameters
        layout.addWidget(self._sec_label("PARAMETERS"))
        self._exit_radius  = QDoubleSpinBox()
        self._exit_radius.setRange(0.1, 10.0)
        self._exit_radius.setSingleStep(0.1)
        self._exit_radius.setValue(1.0)
        self._cancel_time  = QSpinBox()
        self._cancel_time.setRange(1, 9999)
        self._cancel_time.setValue(1500)
        self._touch_frames = QSpinBox()
        self._touch_frames.setRange(1, 100)
        self._touch_frames.setValue(1)
        self._touch_dist   = QSpinBox()
        self._touch_dist.setRange(1, 500)
        self._touch_dist.setValue(50)

        grid = QGridLayout()
        grid.setSpacing(5)
        cells = [
            ("Exit Radius",    self._exit_radius,  "× avg body length", _TOOLTIPS["Exit Radius"]),
            ("Cancel Time",    self._cancel_time,  "frames",             _TOOLTIPS["Cancel Time"]),
            ("Touch Frames",   self._touch_frames, "frames to enter",    _TOOLTIPS["Touch Frames"]),
            ("Touch Distance", self._touch_dist,   "pixels",             _TOOLTIPS["Touch Distance"]),
        ]
        for idx, (name, widget, unit, tip) in enumerate(cells):
            grid.addWidget(_ParamCell(name, widget, unit, tip), idx // 2, idx % 2)
        layout.addLayout(grid)

        # Visualization
        layout.addWidget(self._sec_label("VISUALIZATION"))
        self._save_video = QCheckBox("Save annotated video")
        self._save_video.setChecked(True)
        self._show_video = QCheckBox("Show video when done")
        self._show_video.setChecked(True)
        for cb in (self._save_video, self._show_video):
            cb.setStyleSheet("color:#ccc;")
            layout.addWidget(cb)

        # Run button
        self._run_btn = QPushButton("▶   RUN PIPELINE")
        self._run_btn.setEnabled(False)
        self._run_btn.setStyleSheet(
            "QPushButton { background:#238636; color:white; padding:8px;"
            " border-radius:4px; font-weight:bold; }"
            "QPushButton:disabled { background:#1a3a1a; color:#555; }"
            "QPushButton:hover:!disabled { background:#2ea043; }"
        )
        self._run_btn.clicked.connect(self._on_run)
        layout.addWidget(self._run_btn)

    def _on_video_selected(self, path):
        # type: (str) -> None
        self._video_path = path
        self._run_btn.setEnabled(True)

    def _on_run(self):
        # type: () -> None
        self.run_requested.emit({
            "video_path":       self._video_path,
            "touch_thresh":     self._touch_dist.value(),
            "min_touch_frames": self._touch_frames.value(),
            "d_exit_factor":    self._exit_radius.value(),
            "max_frames":       self._cancel_time.value(),
            "save_video":       self._save_video.isChecked(),
            "show_video":       self._show_video.isChecked(),
        })

    def refresh_model_badge(self):
        # type: () -> None
        self._model_badge.setText("●  {}".format(self._app_state.model_name))

    def params_summary(self):
        # type: () -> str
        vname = Path(self._video_path).name if self._video_path else "—"
        return (
            "📹 {}\n"
            "🧠 {}\n"
            "⚙ Exit ×{} · Cancel {}f · Touch {}f · {}px · Save {}".format(
                vname,
                self._app_state.model_name,
                self._exit_radius.value(),
                self._cancel_time.value(),
                self._touch_frames.value(),
                self._touch_dist.value(),
                "✓" if self._save_video.isChecked() else "✗",
            )
        )
