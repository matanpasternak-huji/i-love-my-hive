import shutil
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from gui_state import PROJECT_DIR
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
        has_config = (folder / "training_config.json").exists()
        if has_weights and has_config:
            self._staged_path = path
            self._replace_btn.setEnabled(True)
        else:
            self._staged_path = None
            self._replace_btn.setEnabled(False)
            missing = []
            if not has_weights:
                missing.append("model weights (.h5 / .pb)")
            if not has_config:
                missing.append("training_config.json")
            QMessageBox.warning(
                self, "Invalid model",
                "This doesn't look like a SLEAP model folder.\nMissing: {}".format(
                    ", ".join(missing)),
            )

    def _do_replace(self):
        if self._staged_path is None:
            return

        old = self._app_state.resolved_model_path() if self._app_state.model_path else None
        old_exists = old is not None and old.is_dir()
        new = Path(self._staged_path).resolve()
        dest_parent = old.parent if old_exists else PROJECT_DIR / "Current Model"
        dest = dest_parent / new.name

        if old_exists and new == old.resolve():
            QMessageBox.information(self, "Nothing to do", "That folder is already the active model.")
            return
        if old_exists and dest.resolve() == old.resolve():
            QMessageBox.warning(
                self, "Invalid operation",
                "The new model folder has the same name as the current model.\n"
                "Rename the new folder and try again.",
            )
            return
        if dest.exists() and dest.resolve() != new:
            QMessageBox.warning(
                self, "Invalid operation",
                "A different folder named “{}” already exists in:\n{}".format(new.name, dest_parent),
            )
            return

        if old_exists:
            answer = QMessageBox.question(
                self, "Replace model?",
                "This permanently deletes the current model:\n{}\n\n"
                "and replaces it with:\n{}".format(old, new),
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel,
            )
            if answer != QMessageBox.Yes:
                return

        # Copy the new model first, so a failed copy never leaves us without a model.
        try:
            if dest.resolve() != new:
                dest_parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(str(new), str(dest))
        except OSError as exc:
            QMessageBox.critical(self, "Replace failed", str(exc))
            return
        try:
            if old_exists:
                shutil.rmtree(str(old))
        except OSError as exc:
            QMessageBox.warning(
                self, "Old model not removed",
                "The new model is active, but the old one could not be deleted:\n{}".format(exc),
            )

        try:
            stored = dest.resolve().relative_to(PROJECT_DIR)
        except ValueError:
            stored = dest.resolve()
        # Forward slashes so config.json stays valid on every OS.
        self._app_state.model_path = stored.as_posix()
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
