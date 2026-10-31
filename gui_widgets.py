from pathlib import Path
from typing import Optional, Sequence

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QFrame, QLabel, QPushButton, QVBoxLayout

_STYLE_IDLE = "DropZone { background: #0d1117; border: 1px dashed #30363d; border-radius: 4px; }"
_STYLE_HOVER = "DropZone { background: #0d1a2b; border: 1px dashed #58a6ff; border-radius: 4px; }"
_STYLE_SET = "DropZone { background: #0d1117; border: 1px solid #238636; border-radius: 4px; }"


class DropZone(QFrame):
    """File/folder drop zone with a Browse button. Emits path_selected(str)."""

    path_selected = pyqtSignal(str)

    def __init__(self, label, filter="", folder=False, extensions=None, parent=None):
        # type: (str, str, bool, Optional[Sequence[str]], object) -> None
        super(DropZone, self).__init__(parent)
        self._folder = folder
        self._filter = filter
        self._extensions = tuple(e.lower() for e in extensions) if extensions else ()
        self._path = None  # type: Optional[str]
        self._setup_ui(label)
        self.setAcceptDrops(True)
        self.setMinimumHeight(80)
        self.setStyleSheet(_STYLE_IDLE)

    def _setup_ui(self, label):
        # type: (str) -> None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self._hint = QLabel(label)
        self._hint.setAlignment(Qt.AlignCenter)
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color: #8b949e; border: none; background: transparent;")

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

    def accepts(self, path):
        # type: (str) -> bool
        p = Path(path)
        if self._folder:
            return p.is_dir()
        if p.is_dir():
            return False
        return not self._extensions or p.suffix.lower() in self._extensions

    def _set_path(self, path):
        # type: (str) -> None
        self._path = path
        self._hint.setText(Path(path).name)
        self._hint.setToolTip(path)
        self._hint.setStyleSheet("color: #f0f6fc; border: none; background: transparent;")
        self.setStyleSheet(_STYLE_SET)
        self.path_selected.emit(path)

    def _drop_path(self, event):
        # type: (object) -> Optional[str]
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if urls:
            local = urls[0].toLocalFile()
            if local and self.accepts(local):
                return local
        return None

    def dragEnterEvent(self, event):
        if self._drop_path(event):
            event.acceptProposedAction()
            self.setStyleSheet(_STYLE_HOVER)
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setStyleSheet(_STYLE_SET if self._path else _STYLE_IDLE)
        super(DropZone, self).dragLeaveEvent(event)

    def dropEvent(self, event):
        local = self._drop_path(event)
        if local:
            self._set_path(local)
            event.acceptProposedAction()
        else:
            self.setStyleSheet(_STYLE_SET if self._path else _STYLE_IDLE)

    def path(self):
        # type: () -> Optional[str]
        return self._path
