import time

from PyQt6.QtCore import QEasingCurve, QEvent, QPoint, QPropertyAnimation, QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from . import APP_NAME, preferences
from .config import SPLASH_MAX_SECONDS, SPLASH_MIN_SECONDS, bundle_dir
from .dashboard import DashboardPage
from .focus import FocusOverlay
from .manager import CameraManager
from .settings_dialog import SettingsDialog
from .sidebar import Sidebar
from .splash import SplashPage
from .theme import current_palette, stylesheet
from .weather_page import WeatherPage
from .widgets import Footer


def app_icon() -> QIcon:
    bundled = bundle_dir() / "assets" / "icon.png"
    if bundled.exists():
        return QIcon(str(bundled))
    icon = QIcon()
    for size in (16, 32, 64, 128, 256, 512):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(size * 0.06, size * 0.06, size * 0.88, size * 0.88)
        p.setPen(QPen(QColor(255, 255, 255, 40), max(1.0, size / 128)))
        p.setBrush(QColor(28, 28, 30))
        p.drawRoundedRect(r, size * 0.22, size * 0.22)
        p.setPen(QPen(QColor(240, 240, 242, 230), max(1.0, size / 26)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(r.center(), size * 0.2, size * 0.2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(240, 240, 242, 230))
        p.drawEllipse(r.center(), size * 0.06, size * 0.06)
        p.end()
        icon.addPixmap(pixmap)
    return icon


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1360, 860)
        self.setMinimumSize(760, 520)

        self.manager = CameraManager(self)
        self._started = time.monotonic()
        self._splash_done = False
        self._shutdown_clean = True
        self._shut_down = False

        self.latest_frames: dict[str, object] = {}

        root = QWidget()
        root.setObjectName("Root")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.top = QStackedWidget()
        layout.addWidget(self.top, 1)
        layout.addWidget(Footer())
        self.setCentralWidget(root)

        self.splash = SplashPage()
        self.top.addWidget(self.splash)

        self.shell = QWidget()
        self.shell.setObjectName("Page")
        shell_layout = QHBoxLayout(self.shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        self.sidebar = Sidebar(preferences.get("theme"))
        shell_layout.addWidget(self.sidebar)
        self.content = QWidget()
        self.content.setObjectName("Page")
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        content_layout.addWidget(self.pages)
        shell_layout.addWidget(self.content, 1)
        self.top.addWidget(self.shell)

        self.dashboard = DashboardPage()
        self.weather_page = WeatherPage(lambda cid: self.latest_frames.get(cid))
        self.pages.addWidget(self.dashboard)
        self.pages.addWidget(self.weather_page)
        self._page_keys = {"cameras": self.dashboard, "weather": self.weather_page}

        self.overlay = FocusOverlay(self.content)
        self.overlay.closed.connect(self._on_focus_closed)
        self.overlay.view.lock_target.connect(self._on_lock_target)
        self.overlay.view.roi_changed.connect(
            lambda roi: self.manager.detector.set_roi(self.overlay.cam_id, roi) if self.overlay.cam_id else None
        )
        self.content.installEventFilter(self)

        self.sidebar.page_requested.connect(self.show_page)
        self.sidebar.settings_requested.connect(self.open_settings)
        self.sidebar.fullscreen_requested.connect(self._toggle_fullscreen)
        self.sidebar.exit_requested.connect(self.quit_app)
        self.sidebar.theme_changed.connect(self.set_theme)

        self.dashboard.tile_clicked.connect(self.open_focus)
        self.dashboard.set_cameras(self.manager.cameras, self.manager)
        self.weather_page.set_cameras(self.manager.cameras)

        self.manager.frame_ready.connect(self._on_frame)
        self.manager.detections_ready.connect(self._on_detections)
        self.manager.status_changed.connect(self._on_status)
        self.manager.weather_ready.connect(self._on_weather)
        self.manager.cameras_changed.connect(self._on_cameras_changed)

        QShortcut(QKeySequence(QKeySequence.StandardKey.FullScreen), self, self._toggle_fullscreen)
        QShortcut(QKeySequence("F11"), self, self._toggle_fullscreen)
        QShortcut(QKeySequence(QKeySequence.StandardKey.Preferences), self, self.open_settings)
        QShortcut(QKeySequence("Ctrl+,"), self, self.open_settings)
        QShortcut(QKeySequence(QKeySequence.StandardKey.Quit), self, self.quit_app)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._on_escape)

        self.apply_theme()
        self._refresh_summary()

        self._splash_timer = QTimer(self)
        self._splash_timer.timeout.connect(self._check_splash)
        self._splash_timer.start(150)
        self.manager.start()

    # ---------- theme ----------
    def apply_theme(self) -> None:
        app = QApplication.instance()
        app.setStyleSheet(stylesheet(current_palette()))
        for widget in app.allWidgets():
            widget.update()

    def set_theme(self, mode: str) -> None:
        snapshot = QLabel(self)
        snapshot.setPixmap(self.grab())
        snapshot.setGeometry(self.rect())
        snapshot.show()
        snapshot.raise_()
        preferences.set_value("theme", mode)
        self.sidebar.theme.set_mode(mode)
        self.apply_theme()
        effect = QGraphicsOpacityEffect(snapshot)
        snapshot.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", snapshot)
        anim.setDuration(360)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        anim.finished.connect(snapshot.deleteLater)
        anim.start()

    def _fade_in(self, widget: QWidget, duration: int = 420) -> None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def show_page(self, key: str) -> None:
        page = self._page_keys.get(key)
        if page is None:
            return
        if self.overlay.cam_id is not None:
            self.overlay.close_focus()
        self.sidebar.set_current(key)
        if self.pages.currentWidget() is not page:
            self.pages.setCurrentWidget(page)
            self._fade_in(page, 300)

    def quit_app(self) -> None:
        self.close()

    # ---------- splash ----------
    def _check_splash(self) -> None:
        if self._splash_done:
            return
        total = len(self.manager.cameras)
        settled = sum(1 for c in self.manager.cameras if self.manager.statuses.get(c.id) in ("live", "offline"))
        engine_done = self.manager.engine_status[0] in ("ready", "error")
        self.splash.update_progress(settled, total, engine_done)
        elapsed = time.monotonic() - self._started
        if elapsed < SPLASH_MIN_SECONDS:
            return
        if (engine_done and settled >= total) or elapsed > SPLASH_MAX_SECONDS:
            self._splash_done = True
            self._splash_timer.stop()
            QTimer.singleShot(420, self._show_dashboard)

    def _show_dashboard(self) -> None:
        self.top.setCurrentWidget(self.shell)
        self._fade_in(self.shell, 520)

    # ---------- manager events ----------
    def _dashboard_visible(self) -> bool:
        return self.top.currentWidget() is self.shell and self.pages.currentWidget() is self.dashboard

    def _on_frame(self, cam_id: str, image, stamp: float) -> None:
        self.latest_frames[cam_id] = image
        if self.overlay.cam_id == cam_id:
            self.overlay.view.push_frame(image, stamp)
        if self.overlay.cam_id is not None and not self.overlay.is_animating():
            return
        tile = self.dashboard.tiles.get(cam_id)
        if tile is not None and self._dashboard_visible():
            tile.set_image(image)

    def _on_lock_target(self, target) -> None:
        if target is None or self.overlay.cam_id is None:
            self.manager.detector.clear_lock()
        else:
            self.manager.detector.set_lock(self.overlay.cam_id, target["id"], target["box"], target["cls"])

    def _on_detections(self, cam_id: str, payload: dict) -> None:
        tile = self.dashboard.tiles.get(cam_id)
        if tile is not None:
            tile.detections = payload
        if self.overlay.cam_id == cam_id:
            self.overlay.view.push_payload(payload)

    def _on_status(self, cam_id: str, status: str) -> None:
        tile = self.dashboard.tiles.get(cam_id)
        if tile is not None:
            tile.set_status(status)
        if self.overlay.cam_id == cam_id:
            self.overlay.view.set_status(status)
            self.overlay.card.header.set_status(status)
        self._refresh_summary()

    def _refresh_summary(self) -> None:
        self.dashboard.refresh_summary(self.manager)
        live = sum(1 for c in self.manager.cameras if self.manager.statuses.get(c.id) == "live")
        self.sidebar.set_summary(live, len(self.manager.cameras))

    def _on_cameras_changed(self, cameras) -> None:
        for cam_id in list(self.latest_frames):
            if not any(c.id == cam_id for c in cameras):
                del self.latest_frames[cam_id]
        self.dashboard.set_cameras(cameras, self.manager)
        self.weather_page.set_cameras(cameras)
        self._refresh_summary()

    def _on_weather(self, cam_id: str, data: dict) -> None:
        tile = self.dashboard.tiles.get(cam_id)
        if tile is not None:
            tile.set_weather(data)
        if self.overlay.cam_id == cam_id:
            self.overlay.card.header.weather.set_weather(data)

    # ---------- focus ----------
    def _tile_rect(self, cam_id: str) -> QRect | None:
        tile = self.dashboard.tiles.get(cam_id)
        if tile is None or not tile.isVisible():
            return None
        top_left = tile.mapTo(self.content, QPoint(0, 0))
        rect = QRect(top_left, tile.size())
        return rect.intersected(self.content.rect()) if rect.intersects(self.content.rect()) else None

    def open_focus(self, cam_id: str) -> None:
        if self.overlay.cam_id is not None or not self._dashboard_visible():
            return
        cam = self.manager.camera(cam_id)
        tile = self.dashboard.tiles.get(cam_id)
        if cam is None or tile is None:
            return
        start = self._tile_rect(cam_id)
        if start is None:
            center = self.content.rect().center()
            start = QRect(center.x() - 160, center.y() - 90, 320, 180)
        backdrop = self.content.grab().toImage()
        view = self.overlay.view
        view.set_status(tile.status)
        view.detections = None
        view.clear_buffer()
        if tile.image is not None:
            view.set_image(tile.image)
        self.overlay.card.header.set_status(tile.status)
        self.overlay.card.header.weather.set_weather(self.manager.weather.get(cam_id))
        self.manager.set_focus(cam_id)
        self.overlay.open_focus(cam_id, cam.name, start, backdrop, lambda cid=cam_id: self._tile_rect(cid))

    def _on_focus_closed(self) -> None:
        self.manager.set_focus(None)
        self.overlay.view.image = None
        self.overlay.view.detections = None
        self.overlay.view.clear_buffer()

    def _on_escape(self) -> None:
        if self.overlay.cam_id is not None:
            self.overlay.close_focus()
        elif self.isFullScreen():
            self.showNormal()

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ---------- settings ----------
    def open_settings(self) -> None:
        if not self._splash_done or self.overlay.cam_id is not None:
            return
        dialog = SettingsDialog(self.manager.cameras, self)
        if dialog.exec() and dialog.result_cameras is not None:
            self.manager.apply_cameras(dialog.result_cameras)

    # ---------- window ----------
    def eventFilter(self, obj, event) -> bool:
        if obj is self.content and event.type() == QEvent.Type.Resize:
            self.overlay.relayout()
        return super().eventFilter(obj, event)

    def shutdown(self) -> None:
        if self._shut_down:
            return
        self._shut_down = True
        self._shutdown_clean = self.manager.shutdown(3.0)

    def closeEvent(self, event) -> None:
        self.hide()
        self.shutdown()
        event.accept()

    @property
    def shutdown_clean(self) -> bool:
        return self._shutdown_clean
