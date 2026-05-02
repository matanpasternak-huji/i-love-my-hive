import sys
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget

from gui_pages.home import HomePage
from gui_pages.pipeline_idle import PipelinePage
from gui_pages.pipeline_running import RunningPage
from gui_pages.update_model import UpdateModelPage
from gui_state import AppState

_OUTPUT_ROOT = Path("output")


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Bee Interaction Detector")
        self.resize(620, 720)
        self.setStyleSheet("QMainWindow { background: #0d1117; } QWidget { color: #f0f6fc; }")

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
        self._home.model_btn.clicked.connect(lambda: self._stack.setCurrentIndex(3))
        self._pipeline.back_requested.connect(lambda: self._stack.setCurrentIndex(0))
        self._running.canceled.connect(lambda: self._stack.setCurrentIndex(1))
        self._running.done.connect(self._on_pipeline_done)
        self._update.back_requested.connect(lambda: self._stack.setCurrentIndex(0))
        self._update.model_updated.connect(self._on_model_updated)
        self._pipeline.run_requested.connect(self._start_run)

    def _start_run(self, params):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = str(_OUTPUT_ROOT / ts)
        params["summary"] = self._pipeline.params_summary()
        self._stack.setCurrentIndex(2)
        self._running.start(params, output_dir)

    def _on_pipeline_done(self, output_dir, show_video):
        QMessageBox.information(
            self, "Done",
            "Pipeline complete.\nOutputs saved to:\n{}".format(output_dir),
        )
        if show_video:
            video_path = Path(output_dir) / "interactions_visualized.mp4"
            if video_path.exists():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(video_path)))
        self._stack.setCurrentIndex(0)

    def _on_model_updated(self):
        self._home.refresh_model_label()
        self._pipeline.refresh_model_badge()
        self._stack.setCurrentIndex(0)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
