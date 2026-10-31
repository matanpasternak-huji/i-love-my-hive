import sys
from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QColor, QDesktopServices, QIcon, QPalette
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget

from gui_pages.home import HomePage
from gui_pages.pipeline_idle import PipelinePage
from gui_pages.pipeline_running import RunningPage
from gui_pages.update_model import UpdateModelPage
from gui_state import PROJECT_DIR, AppState

_OUTPUT_ROOT = PROJECT_DIR / "output"


def dark_palette():
    # type: () -> QPalette
    """GitHub-dark palette so native-ish widgets (dialogs, spin boxes…) match the app."""
    p = QPalette()
    bg, base, alt, text, dim = "#0d1117", "#161b22", "#21262d", "#f0f6fc", "#6e7681"
    p.setColor(QPalette.Window, QColor(bg))
    p.setColor(QPalette.WindowText, QColor(text))
    p.setColor(QPalette.Base, QColor(base))
    p.setColor(QPalette.AlternateBase, QColor(alt))
    p.setColor(QPalette.ToolTipBase, QColor(base))
    p.setColor(QPalette.ToolTipText, QColor(text))
    p.setColor(QPalette.Text, QColor(text))
    p.setColor(QPalette.Button, QColor(alt))
    p.setColor(QPalette.ButtonText, QColor(text))
    p.setColor(QPalette.BrightText, QColor("#f85149"))
    p.setColor(QPalette.Highlight, QColor("#1f6feb"))
    p.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    p.setColor(QPalette.Link, QColor("#58a6ff"))
    p.setColor(QPalette.PlaceholderText, QColor(dim))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        p.setColor(QPalette.Disabled, role, QColor(dim))
    return p


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Bee Interaction Detector")
        self.resize(640, 760)
        self.setMinimumSize(560, 640)
        self.setStyleSheet("QMainWindow { background: #0d1117; }")

        self._state = AppState.load()

        self._stack = QStackedWidget(self)
        self.setCentralWidget(self._stack)

        self._home     = HomePage(self._state)
        self._pipeline = PipelinePage(self._state)
        self._running  = RunningPage()
        self._update   = UpdateModelPage(self._state)

        self._stack.addWidget(self._home)      # 0
        self._stack.addWidget(self._pipeline)  # 1
        self._stack.addWidget(self._running)   # 2
        self._stack.addWidget(self._update)    # 3

        self._home.run_btn.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        self._home.model_btn.clicked.connect(self._open_update_page)
        self._pipeline.back_requested.connect(lambda: self._stack.setCurrentIndex(0))
        self._running.canceled.connect(lambda: self._stack.setCurrentIndex(1))
        self._running.done.connect(self._on_pipeline_done)
        self._update.back_requested.connect(lambda: self._stack.setCurrentIndex(0))
        self._update.model_updated.connect(self._on_model_updated)
        self._pipeline.run_requested.connect(self._start_run)

    def _open_update_page(self):
        self._update.refresh()
        self._stack.setCurrentIndex(3)

    def _start_run(self, params):
        if not self._state.model_exists():
            QMessageBox.warning(
                self, "Model not found",
                "The active model folder does not exist:\n{}\n\n"
                "Use “Update Model” to select a SLEAP model folder.".format(
                    self._state.resolved_model_path()),
            )
            return
        run_params = dict(params)
        run_params["model_path"] = str(self._state.resolved_model_path())
        run_params["summary"] = self._pipeline.params_summary()
        self._stack.setCurrentIndex(2)
        self._running.start(run_params, str(_OUTPUT_ROOT))

    def _on_pipeline_done(self, output_dir, show_video):
        video_path = Path(output_dir) / "interactions_visualized.mp4"
        if show_video and video_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(video_path)))

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("Done")
        box.setText("Pipeline complete.")
        box.setInformativeText("Outputs saved to:\n{}".format(output_dir))
        open_btn = box.addButton("Open Folder", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.exec_()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output_dir)))

    def _on_model_updated(self):
        self._home.refresh_model_label()
        self._pipeline.refresh_model_badge()
        self._stack.setCurrentIndex(0)

    def closeEvent(self, event):
        if self._running.is_running():
            answer = QMessageBox.question(
                self, "Pipeline running",
                "The pipeline is still running. Stop it and quit?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            self._running.stop_process()
        super(MainWindow, self).closeEvent(event)


def _log_to_file_if_windowless():
    """Under pythonw.exe (Desktop shortcut on Windows) there is no stdout/stderr:
    send them to .tools/gui.log so errors are not lost."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_dir = PROJECT_DIR / ".tools"
    log_dir.mkdir(exist_ok=True)
    log = open(str(log_dir / "gui.log"), "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log


def main():
    _log_to_file_if_windowless()
    if sys.platform == "win32":
        # Own taskbar entry/icon instead of being grouped under pythonw.exe.
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "huji.BeeInteractionDetector")
        except Exception:
            pass
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Bee Interaction Detector")
    icon_path = PROJECT_DIR / "media" / "app_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    app.setStyle("Fusion")
    app.setPalette(dark_palette())
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
