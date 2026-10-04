from PyQt6.QtCore import QEasingCurve, QRect, QRectF, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QImage, QPainter
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton, QWidget

from .painting import blur_image
from .theme import current_palette, font
from .widgets import STATUS_TEXT, VideoView, WeatherBadge

CARD_MARGIN = 12
TOP_INSET = 72


class FocusHeader(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 16, 0)
        layout.setSpacing(12)
        back = QPushButton("‹  Geri")
        back.setCursor(Qt.CursorShape.PointingHandCursor)
        back.setFont(font(13, QFont.Weight.Medium))
        back.setStyleSheet(
            "QPushButton { color: rgba(245,245,247,0.92); background: rgba(255,255,255,0.06);"
            " border: 1px solid rgba(255,255,255,0.12); border-radius: 8px; padding: 5px 12px; }"
            "QPushButton:hover { background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.22); }"
        )
        back.clicked.connect(self.back_requested)
        layout.addWidget(back)
        self.title = QLabel("")
        self.title.setFont(font(14, QFont.Weight.DemiBold, 1.6))
        self.title.setStyleSheet("color: rgba(245,245,247,0.95);")
        layout.addWidget(self.title)
        self.status = QLabel("")
        self.status.setFont(font(10, QFont.Weight.Medium, 1.4))
        self.status.setStyleSheet("color: rgba(235,235,245,0.5);")
        layout.addWidget(self.status)
        layout.addStretch(1)
        self.weather = WeatherBadge()
        layout.addWidget(self.weather)

    def set_status(self, status: str) -> None:
        self.status.setText(STATUS_TEXT.get(status, ""))


class FocusCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = VideoView(compact=False, parent=self)
        self.view.buffered = True
        self.view.radius = 14
        self.view.top_inset = TOP_INSET
        self.header = FocusHeader(self)
        self.header_effect = QGraphicsOpacityEffect(self.header)
        self.header.setGraphicsEffect(self.header_effect)

    def resizeEvent(self, event) -> None:
        self.view.setGeometry(self.rect())
        self.header.setGeometry(QRect(10, 10, self.width() - 20, TOP_INSET - 18))
        super().resizeEvent(event)


class FocusOverlay(QWidget):
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cam_id: str | None = None
        self.card = FocusCard(self)
        self.card.header.back_requested.connect(self.close_focus)
        self._progress = 0.0
        self._start_rect = QRect()
        self._backdrop: QImage | None = None
        self._closing = False
        self._anim = QVariantAnimation(self)
        self._anim.valueChanged.connect(self._on_progress)
        self._anim.finished.connect(self._on_finished)
        self._source_rect_fn = None
        self.hide()

    @property
    def view(self) -> VideoView:
        return self.card.view

    def is_animating(self) -> bool:
        return self._anim.state() == QVariantAnimation.State.Running

    def open_focus(self, cam_id: str, name: str, start_rect: QRect, backdrop: QImage, source_rect_fn) -> None:
        self.cam_id = cam_id
        self._closing = False
        self._start_rect = start_rect
        self._source_rect_fn = source_rect_fn
        self._backdrop = blur_image(backdrop, 18) if backdrop is not None and not backdrop.isNull() else None
        self.card.header.title.setText(name)
        self.view.set_name(name)
        self.view.reset_view(immediate=True)
        self.setGeometry(self.parentWidget().rect())
        self.raise_()
        self.show()
        self._run(0.0, 1.0, 460, QEasingCurve.Type.OutCubic)
        self.view.show_hint()
        self.setFocus()

    def close_focus(self) -> None:
        if self.cam_id is None or self._closing:
            return
        self._closing = True
        if self._source_rect_fn is not None:
            rect = self._source_rect_fn()
            if rect is not None:
                self._start_rect = rect
        self.view.release_lock()
        self._run(self._progress, 0.0, 380, QEasingCurve.Type.InOutCubic)

    def _run(self, start: float, end: float, duration: int, curve: QEasingCurve.Type) -> None:
        self._anim.stop()
        self._anim.setStartValue(float(start))
        self._anim.setEndValue(float(end))
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(curve)
        self._anim.start()

    def _target_rect(self) -> QRect:
        return self.rect().adjusted(CARD_MARGIN, CARD_MARGIN, -CARD_MARGIN, -CARD_MARGIN)

    def _on_progress(self, value) -> None:
        self._progress = float(value)
        a, b = self._start_rect, self._target_rect()
        t = self._progress
        rect = QRect(
            round(a.x() + (b.x() - a.x()) * t),
            round(a.y() + (b.y() - a.y()) * t),
            round(a.width() + (b.width() - a.width()) * t),
            round(a.height() + (b.height() - a.height()) * t),
        )
        self.card.setGeometry(rect)
        self.card.view.radius = 12 + 2 * t
        chrome = max(0.0, (t - 0.6) / 0.4)
        self.card.header_effect.setOpacity(chrome)
        self.card.view.chrome_opacity = chrome
        self.update()

    def _on_finished(self) -> None:
        if self._closing:
            self._closing = False
            self.hide()
            self.cam_id = None
            self._backdrop = None
            self.closed.emit()

    def relayout(self) -> None:
        if self.isVisible():
            self.setGeometry(self.parentWidget().rect())
            if not self.is_animating():
                self.card.setGeometry(self._target_rect())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close_focus()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if not self.card.geometry().contains(event.position().toPoint()):
            self.close_focus()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        t = self._progress
        p.setOpacity(t)
        if self._backdrop is not None:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawImage(QRectF(self.rect()), self._backdrop)
        tint = QColor(current_palette().backdrop_tint)
        p.fillRect(self.rect(), tint)
