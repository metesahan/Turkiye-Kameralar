from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .theme import font
from .widgets import ProgressLine


class SplashPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.addStretch(5)

        title = QLabel("TÜRKİYE KAMERALARI")
        title.setObjectName("Display")
        title.setFont(font(30, QFont.Weight.Light, 9))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Canlı şehir yayınları")
        subtitle.setObjectName("Secondary")
        subtitle.setFont(font(13, QFont.Weight.Normal, 0.6))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(8)
        layout.addWidget(subtitle)

        layout.addSpacing(38)
        self.progress = ProgressLine()
        layout.addWidget(self.progress, 0, Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(14)
        self.status = QLabel("Başlatılıyor")
        self.status.setObjectName("Tertiary")
        self.status.setFont(font(11.5, QFont.Weight.Normal, 0.4))
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)
        layout.addStretch(6)

    def update_progress(self, settled: int, total: int, engine_done: bool) -> None:
        total_steps = max(1, total + 1)
        done = settled + (1 if engine_done else 0)
        self.progress.set_value(done / total_steps)
        self.status.setText(f"Kamera bağlantıları başlatılıyor · {settled} / {total}")
