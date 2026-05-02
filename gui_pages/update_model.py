import shutil
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from gui_widgets import DropZone


class UpdateModelPage(QWidget):
    model_updated  = pyqtSignal()
    back_requested = pyqtSignal()

    def __init__(self, app_state, parent=None):
        super(UpdateModelPage, self).__init__(parent)
        self._app_state = app_state
        self._staged_path = None  # type: Optional[str]
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        back = QLabel("← Back to home")
        back.setStyleSheet("color:#58a6ff; font-size:9pt;")
        back.setCursor(Qt.PointingHandCursor)
        back.mousePressEvent = lambda _: self.back_requested.emit()
        layout.addWidget(back, alignment=Qt.AlignLeft)

        self._cur_box = QLabel("Current model:\n{}".format(self._app_state.model_name))
        self._cur_box.setStyleSheet(
            "background:#0d1117; border:1px solid #21262d; border-radius:4px;"
            " color:#8b949e; padding:8px;"
        )
        layout.addWidget(self._cur_box)

        sec = QLabel("NEW MODEL")
        sec.setStyleSheet("font-size:8pt; font-weight:bold; color:#58a6ff; letter-spacing:1px;")
        layout.addWidget(sec)

        self._drop = DropZone("🧠  Drop model folder here", folder=True, parent=self)
        self._drop.path_selected.connect(self._on_folder_selected)
        layout.addWidget(self._drop)

        warn = QLabel(
            "⚠  Permanently replaces the active model. "
            "Previous model will be removed."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(
            "background:#1c1106; border:1px solid #9e6a03; border-radius:4px;"
            " color:#d29922; padding:8px;"
        )
        layout.addWidget(warn)

        self._replace_btn = QPushButton("🧠   REPLACE MODEL")
        self._replace_btn.setEnabled(False)
        self._replace_btn.setStyleSheet(
            "QPushButton { background:#1f6feb; color:white; padding:8px;"
            " border-radius:4px; font-weight:bold; }"
            "QPushButton:disabled { background:#162032; color:#555; }"
            "QPushButton:hover:!disabled { background:#388bfd; }"
        )
        self._replace_btn.clicked.connect(self._do_replace)
        layout.addWidget(self._replace_btn)

        note = QLabel("(activates once a valid model folder is dropped)")
        note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet("font-size:8pt; color:#484f58;")
        layout.addWidget(note)

        layout.addStretch()

    def _on_folder_selected(self, path):
        # type: (str) -> None
        folder = Path(path)
        has_weights = any(folder.rglob("*.pb")) or any(folder.rglob("*.h5"))
        if has_weights:
            self._staged_path = path
            self._replace_btn.setEnabled(True)
        else:
            self._staged_path = None
            self._replace_btn.setEnabled(False)
            QMessageBox.warning(
                self, "Invalid model",
                "No .pb or .h5 files found in the selected folder.",
            )

    def _do_replace(self):
        if self._staged_path is None:
            return

        old = Path(self._app_state.model_path)
        new = Path(self._staged_path)
        dest_parent = old.parent if old.exists() else new.parent
        dest = dest_parent / new.name

        # Prevent silent data loss when old and new point to the same directory
        if dest.resolve() == old.resolve() and old.exists():
            QMessageBox.warning(
                self, "Invalid operation",
                "The new model folder has the same name as the current model.",
            )
            return

        try:
            if old.exists() and old.is_dir():
                shutil.rmtree(old)
            # Only copy if new is not already in the destination location
            if new != dest:
                shutil.copytree(str(new), str(dest))
        except OSError as exc:
            QMessageBox.critical(self, "Replace failed", str(exc))
            return

        self._app_state.model_path = str(dest)
        self._app_state.model_name = new.name
        self._app_state.save()

        self._cur_box.setText("Current model:\n{}".format(self._app_state.model_name))
        self._staged_path = None
        self._replace_btn.setEnabled(False)

        QMessageBox.information(
            self, "Model updated",
            "Active model is now:\n{}".format(self._app_state.model_name),
        )
        self.model_updated.emit()

    def refresh(self):
        self._cur_box.setText("Current model:\n{}".format(self._app_state.model_name))
