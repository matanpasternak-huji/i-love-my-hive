from pathlib import Path
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QFrame, QLabel, QPushButton, QVBoxLayout


class DropZone(QFrame):
    """File/folder drop zone with a Browse button. Emits path_selected(str)."""

    path_selected = pyqtSignal(str)

    def __init__(self, label, filter="", folder=False, parent=None):
        # type: (str, str, bool, object) -> None
        super(DropZone, self).__init__(parent)
        self._folder = folder
        self._filter = filter
        self._path = None  # type: Optional[str]
        self._setup_ui(label)
        self.setAcceptDrops(True)
        self.setStyleSheet(
            "DropZone { background: #0d1117; border: 1px dashed #30363d; border-radius: 4px; }"
        )

    def _setup_ui(self, label):
        # type: (str) -> None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._hint = QLabel(label)
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setStyleSheet("color: #484f58; border: none;")

        browse_btn = QPushButton("Browse…")
        browse_btn.setStyleSheet(
            "color: #58a6ff; background: transparent; border: none; text-decoration: underline;"
        )
        browse_btn.setCursor(Qt.PointingHandCursor)
        browse_btn.clicked.connect(self._browse)

        layout.addWidget(self._hint)
        layout.addWidget(browse_btn, alignment=Qt.AlignCenter)

    def _browse(self):
        # type: () -> None
        if self._folder:
            chosen = QFileDialog.getExistingDirectory(self, "Select folder")
        else:
            chosen, _ = QFileDialog.getOpenFileName(self, "Select file", filter=self._filter)
        if chosen:
            self._set_path(chosen)

    def _set_path(self, path):
        # type: (str) -> None
        self._path = path
        self._hint.setText(Path(path).name)
        self._hint.setStyleSheet("color: #f0f6fc; border: none;")
        self.path_selected.emit(path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self._set_path(urls[0].toLocalFile())

    def path(self):
        # type: () -> Optional[str]
        return self._path