import math

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

# (cx_frac, cy_frac, amplitude_x, amplitude_y, frequency, phase_x, phase_y)
_BEE_CONFIGS = [
    (0.12, 0.15, 40, 25, 0.70, 0.00, 1.10),
    (0.75, 0.20, 30, 35, 0.50, 0.80, 0.30),
    (0.18, 0.60, 50, 20, 0.90, 1.50, 2.00),
    (0.80, 0.70, 25, 40, 0.60, 2.30, 0.70),
    (0.50, 0.45, 35, 30, 0.80, 0.40, 1.80),
    (0.40, 0.08, 20, 15, 1.00, 1.00, 0.50),
    (0.60, 0.85, 30, 25, 0.65, 1.70, 2.50),
]


class HomePage(QWidget):
    def __init__(self, app_state, parent=None):
        super(HomePage, self).__init__(parent)
        self._app_state = app_state
        self._t = 0.0
        self._bees = []  # list of (QLabel, config_tuple)
        self._setup_ui()
        self._setup_bees()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("background: #0d1117;")
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(14)

        title = QLabel("🐝  Bee Interaction Detector")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 22pt; font-weight: bold; color: #f0f6fc;")

        subtitle = QLabel("SLEAP · NAPS · Antennation")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 10pt; color: #8b949e;")

        self.run_btn = QPushButton("▶   Run Pipeline")
        self.run_btn.setFixedWidth(220)
        self.run_btn.setStyleSheet(
            "QPushButton { background:#238636; color:white; padding:12px;"
            " border-radius:8px; font-size:11pt; border:1px solid #3fb950; }"
            "QPushButton:hover { background:#2ea043; }"
        )

        self.model_btn = QPushButton("🧠   Update Model")
        self.model_btn.setFixedWidth(220)
        self.model_btn.setStyleSheet(
            "QPushButton { background:#1f2937; color:#f0f6fc; padding:12px;"
            " border-radius:8px; font-size:11pt; border:1px solid #4a5568; }"
            "QPushButton:hover { background:#2d3748; }"
        )

        self._model_label = QLabel("Active model: {}".format(self._app_state.model_name))
        self._model_label.setAlignment(Qt.AlignCenter)
        self._model_label.setStyleSheet("font-size: 8pt; color: #3d444d;")

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(10)
        layout.addWidget(self.run_btn, alignment=Qt.AlignCenter)
        layout.addWidget(self.model_btn, alignment=Qt.AlignCenter)
        layout.addWidget(self._model_label)

    def _setup_bees(self):
        for cfg in _BEE_CONFIGS:
            label = QLabel("🐝", self)
            label.setStyleSheet("font-size: 18pt; background: transparent;")
            label.setFixedSize(36, 36)
            label.setAttribute(Qt.WA_TransparentForMouseEvents)
            label.lower()
            self._bees.append((label, cfg))

    def _tick(self):
        self._t += 0.016
        w, h = self.width(), self.height()
        if w == 0 or h == 0:
            return
        for label, (cx_f, cy_f, ax, ay, freq, px, py) in self._bees:
            x = cx_f * w + ax * math.sin(freq * self._t + px)
            y = cy_f * h + ay * math.cos(freq * self._t + py)
            label.move(int(x - 18), int(y - 18))

    def showEvent(self, event):
        super(HomePage, self).showEvent(event)
        self._timer.start(16)

    def hideEvent(self, event):
        super(HomePage, self).hideEvent(event)
        self._timer.stop()

    def refresh_model_label(self):
        self._model_label.setText("Active model: {}".format(self._app_state.model_name))
