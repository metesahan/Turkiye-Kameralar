from PyQt6.QtCore import QEasingCurve, QRectF, QSize, Qt, QVariantAnimation, pyqtSignal
from PyQt6.QtGui import QFont, QPainter
from PyQt6.QtWidgets import QAbstractButton, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .painting import draw_nav_icon
from .theme import current_palette, font, qcolor

SIDEBAR_WIDTH = 224


class NavButton(QAbstractButton):
    def __init__(self, icon: str, text: str, checkable: bool = True, parent=None):
        super().__init__(parent)
        self.icon_name = icon
        self.setText(text)
        self.setCheckable(checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._hover = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._set_hover)

    def _set_hover(self, value) -> None:
        self._hover = float(value)
        self.update()

    def _animate(self, end: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(end)
        self._anim.start()

    def enterEvent(self, event) -> None:
        self._animate(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate(0.0)
        super().leaveEvent(event)

    def sizeHint(self) -> QSize:
        return QSize(180, 38)

    def paintEvent(self, event) -> None:
        pal = current_palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self.isChecked():
            p.setPen(qcolor(pal.border))
            p.setBrush(qcolor(pal.selection))
            p.drawRoundedRect(rect, 9, 9)
        elif self._hover > 0.01:
            fill = qcolor(pal.surface)
            fill.setAlphaF(fill.alphaF() * self._hover)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(rect, 9, 9)
        color = qcolor(pal.text) if self.isChecked() or self._hover > 0.5 else qcolor(pal.text_secondary)
        draw_nav_icon(p, QRectF(13, (self.height() - 17) / 2, 17, 17), self.icon_name, color)
        p.setPen(color)
        p.setFont(font(13.5, QFont.Weight.DemiBold if self.isChecked() else QFont.Weight.Medium))
        p.drawText(QRectF(42, 0, self.width() - 48, self.height()), Qt.AlignmentFlag.AlignVCenter, self.text())


class IconButton(QAbstractButton):
    def __init__(self, icon: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.icon_name = icon
        self.setToolTip(tooltip)
        self.setFixedSize(38, 38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(160)
        self._anim.valueChanged.connect(self._set_hover)

    def _set_hover(self, value) -> None:
        self._hover = float(value)
        self.update()

    def _animate(self, end: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(end)
        self._anim.start()

    def enterEvent(self, event) -> None:
        self._animate(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate(0.0)
        super().leaveEvent(event)

    def _paint_frame(self, p: QPainter) -> None:
        pal = current_palette()
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        fill = qcolor(pal.surface_hover) if self._hover > 0.5 else qcolor(pal.surface)
        p.setPen(qcolor(pal.border_strong) if self._hover > 0.5 else qcolor(pal.border))
        p.setBrush(fill)
        p.drawRoundedRect(rect, 10, 10)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_frame(p)
        draw_nav_icon(p, QRectF(11, 11, 16, 16), self.icon_name, qcolor(current_palette().text))


class ThemeToggle(IconButton):
    changed = pyqtSignal(str)

    def __init__(self, mode: str, parent=None):
        super().__init__("moon", "", parent)
        self.mode = mode
        self._turn = 0.0 if mode == "dark" else 1.0
        self._spin = QVariantAnimation(self)
        self._spin.setDuration(420)
        self._spin.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._spin.valueChanged.connect(self._set_turn)
        self.clicked.connect(self._toggle)
        self._update_tooltip()

    def _set_turn(self, value) -> None:
        self._turn = float(value)
        self.update()

    def _update_tooltip(self) -> None:
        self.setToolTip("Aydınlık moda geç" if self.mode == "dark" else "Karanlık moda geç")

    def set_mode(self, mode: str) -> None:
        if mode == self.mode:
            return
        self.mode = mode
        self._spin.stop()
        self._spin.setStartValue(self._turn)
        self._spin.setEndValue(0.0 if mode == "dark" else 1.0)
        self._spin.start()
        self._update_tooltip()

    def _toggle(self) -> None:
        mode = "light" if self.mode == "dark" else "dark"
        self.set_mode(mode)
        self.changed.emit(mode)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_frame(p)
        color = qcolor(current_palette().text)
        center = QRectF(self.rect()).center()
        for icon, weight in (("moon", 1.0 - self._turn), ("sun", self._turn)):
            if weight <= 0.01:
                continue
            p.save()
            p.setOpacity(weight)
            p.translate(center)
            p.rotate((1.0 - weight) * (90 if icon == "sun" else -90))
            scale = 0.6 + 0.4 * weight
            p.scale(scale, scale)
            p.translate(-center)
            draw_nav_icon(p, QRectF(center.x() - 8, center.y() - 8, 16, 16), icon, color)
            p.restore()


class Sidebar(QWidget):
    page_requested = pyqtSignal(str)
    settings_requested = pyqtSignal()
    fullscreen_requested = pyqtSignal()
    exit_requested = pyqtSignal()
    theme_changed = pyqtSignal(str)

    def __init__(self, theme_mode: str, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(SIDEBAR_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 22, 14, 16)
        layout.setSpacing(4)

        brand = QLabel("TÜRKİYE\nKAMERALARI")
        brand.setObjectName("Display")
        brand.setFont(font(13, QFont.Weight.DemiBold, 3.2))
        brand.setContentsMargins(8, 0, 0, 0)
        layout.addWidget(brand)
        tagline = QLabel("Canlı şehir yayınları")
        tagline.setObjectName("Tertiary")
        tagline.setFont(font(11.5, QFont.Weight.Normal, 0.3))
        tagline.setContentsMargins(8, 2, 0, 0)
        layout.addWidget(tagline)
        layout.addSpacing(26)

        layout.addWidget(self._section("GEZİNTİ"))
        self.nav = {
            "cameras": NavButton("grid", "Kameralar"),
            "weather": NavButton("weather", "Hava Durumu"),
        }
        for key, button in self.nav.items():
            button.clicked.connect(lambda _=False, k=key: self.page_requested.emit(k))
            layout.addWidget(button)
        settings = NavButton("settings", "Ayarlar", checkable=False)
        settings.clicked.connect(self.settings_requested)
        layout.addWidget(settings)

        layout.addStretch(1)

        self.summary = QLabel("")
        self.summary.setObjectName("Tertiary")
        self.summary.setFont(font(11.5, QFont.Weight.Normal, 0.3))
        self.summary.setContentsMargins(8, 0, 0, 8)
        layout.addWidget(self.summary)

        tools = QHBoxLayout()
        tools.setContentsMargins(4, 0, 4, 4)
        tools.setSpacing(8)
        self.theme = ThemeToggle(theme_mode)
        self.theme.changed.connect(self.theme_changed)
        tools.addWidget(self.theme)
        fullscreen = IconButton("fullscreen", "Tam ekran")
        fullscreen.clicked.connect(self.fullscreen_requested)
        tools.addWidget(fullscreen)
        tools.addStretch(1)
        layout.addLayout(tools)
        layout.addSpacing(4)
        quit_button = NavButton("exit", "Çıkış", checkable=False)
        quit_button.clicked.connect(self.exit_requested)
        layout.addWidget(quit_button)

        self.set_current("cameras")

    def _section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Tertiary")
        label.setFont(font(10, QFont.Weight.DemiBold, 1.4))
        label.setContentsMargins(8, 8, 0, 6)
        return label

    def set_current(self, key: str) -> None:
        for name, button in self.nav.items():
            button.setChecked(name == key)

    def set_summary(self, live: int, total: int) -> None:
        self.summary.setText(f"●  {live} / {total} yayın canlı")
