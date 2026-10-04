import time
from collections import deque

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QFontMetricsF, QImage, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import FOOTER_TEXT
from .config import CATEGORY_LABELS, CATEGORY_ORDER, CLASS_LABELS, DETECTION_STALE_SECONDS
from .painting import (
    OVERLAY_TEXT,
    OVERLAY_TEXT_DIM,
    OVERLAY_TEXT_FAINT,
    draw_weather_icon,
    paint_glass,
    rounded_path,
)
from .theme import current_palette, font

STATUS_TEXT = {
    "connecting": "BAĞLANIYOR",
    "live": "CANLI",
    "offline": "YAYIN YOK · YENİDEN DENENİYOR",
}


class Footer(QLabel):
    def __init__(self, parent=None, on_media: bool = False):
        super().__init__(FOOTER_TEXT, parent)
        self.setObjectName("Footer")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(font(10.5, QFont.Weight.Light, 0.5))
        self.setContentsMargins(0, 6, 0, 10)
        if on_media:
            self.setStyleSheet("color: rgba(235, 235, 245, 0.45);")


class FramedDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.body = QWidget()
        self.body.setObjectName("Page")
        outer.addWidget(self.body, 1)
        outer.addWidget(Footer())


class ConfirmDialog(FramedDialog):
    def __init__(self, title: str, message: str, action: str, parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self.body)
        layout.setContentsMargins(28, 26, 28, 12)
        layout.setSpacing(10)
        heading = QLabel(title)
        heading.setFont(font(16, QFont.Weight.DemiBold))
        text = QLabel(message)
        text.setObjectName("Secondary")
        text.setWordWrap(True)
        text.setFont(font(13))
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Vazgeç")
        cancel.clicked.connect(self.reject)
        confirm = QPushButton(action)
        confirm.setObjectName("Primary")
        confirm.setDefault(True)
        confirm.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(confirm)
        layout.addWidget(heading)
        layout.addWidget(text)
        layout.addSpacing(10)
        layout.addLayout(buttons)
        self.setMinimumWidth(380)


class ProgressLine(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 2)
        self._value = 0.0
        self._target = 0.0
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_value(self, value: float) -> None:
        self._target = max(0.0, min(1.0, value))

    def _tick(self) -> None:
        self._value += (self._target - self._value) * 0.08
        self._phase = (self._phase + 0.012) % 1.0
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = current_palette()
        base = QColor(255, 255, 255) if pal.dark else QColor(0, 0, 0)
        track = QColor(base)
        track.setAlpha(28)
        fill = QColor(base)
        fill.setAlpha(170)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, 1, 1)
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(0, 0, r.width() * self._value, r.height()), 1, 1)
        if self._value < 0.999:
            sheen = QLinearGradient(0, 0, r.width(), 0)
            center = self._phase
            glow = QColor(base)
            glow.setAlpha(70)
            clear = QColor(base)
            clear.setAlpha(0)
            sheen.setColorAt(max(0.0, center - 0.12), clear)
            sheen.setColorAt(center, glow)
            sheen.setColorAt(min(1.0, center + 0.12), clear)
            p.setBrush(sheen)
            p.drawRoundedRect(r, 1, 1)


class WeatherBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = None
        self.setFixedHeight(28)
        self.setMinimumWidth(10)

    def set_weather(self, data: dict | None) -> None:
        self._data = data
        self.setToolTip(f"{data['label']} · Rüzgâr {data['wind']:.0f} km/sa" if data else "")
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        if not self._data:
            return QSize(10, 28)
        label_width = QFontMetricsF(font(11, QFont.Weight.Normal, 0.3)).horizontalAdvance(self._data["label"])
        return QSize(int(18 + 8 + 36 + label_width + 6), 28)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event) -> None:
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        h = self.height()
        icon = QRectF(self.width() - self.sizeHint().width(), (h - 18) / 2, 18, 18)
        draw_weather_icon(p, icon, self._data["kind"], self._data["is_day"], OVERLAY_TEXT)
        p.setFont(font(13, QFont.Weight.Medium))
        p.setPen(OVERLAY_TEXT)
        p.drawText(QRectF(icon.right() + 8, 0, 40, h), Qt.AlignmentFlag.AlignVCenter, f"{round(self._data['temperature'])}°")
        p.setFont(font(11, QFont.Weight.Normal, 0.3))
        p.setPen(OVERLAY_TEXT_DIM)
        p.drawText(
            QRectF(icon.right() + 44, 0, self.width() - icon.right() - 40, h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self._data["label"],
        )


class VideoView(QWidget):
    clicked = pyqtSignal()
    lock_changed = pyqtSignal(object)
    roi_changed = pyqtSignal(object)
    lock_target = pyqtSignal(object)

    def __init__(self, compact: bool = True, parent=None):
        super().__init__(parent)
        self.compact = compact
        self.radius = 12.0
        self.top_inset = 0.0
        self.chrome_opacity = 1.0
        self.name = ""
        self.status = "connecting"
        self.image: QImage | None = None
        self.detections: dict | None = None
        self.weather: dict | None = None
        self._zoom = 1.0
        self._tzoom = 1.0
        self._center = [0.5, 0.5]
        self._tcenter = [0.5, 0.5]
        self._lock_id: int | None = None
        self._lock_text = ""
        self._lock_seen = 0.0
        self._lock_box = None
        self._lock_cls = None
        self._lock_since = 0.0
        self._trail: deque = deque(maxlen=90)
        self._velocity = [0.0, 0.0, 0.0]
        self._hover_id: int | None = None
        self.buffered = False
        self._roi = None
        self._roi_sent = 0.0
        self._frames: deque = deque(maxlen=120)
        self._payloads: deque = deque(maxlen=60)
        self._delay = 0.2
        self._returning = False
        self._hover = 0.0
        self._press = None
        self._dragging = False
        self._drag_origin = (0.5, 0.5)
        self._hint_until = 0.0
        self._canvas: QImage | None = None
        self._last_tick = time.monotonic()
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)
        self.setCursor(Qt.CursorShape.PointingHandCursor if compact else Qt.CursorShape.ArrowCursor)
        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(220)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        if not compact:
            self._timer.start()

    # ---------- buffered playback ----------
    def clear_buffer(self) -> None:
        self._frames.clear()
        self._payloads.clear()
        self._delay = 0.2

    def push_frame(self, image: QImage, stamp: float) -> None:
        if not self.buffered:
            self.set_image(image)
            return
        self._frames.append((stamp, image))
        if self.image is None:
            self.set_image(image)

    def push_payload(self, payload: dict) -> None:
        lock = payload.get("lock")
        if lock is not None and lock["state"] == "lost" and self._lock_id is not None:
            self.release_lock()
        if not self.buffered or "ts" not in payload:
            self.set_detections(payload)
            return
        lag = time.monotonic() - payload["ts"]
        self._delay = min(0.8, max(0.1, self._delay * 0.92 + (lag + 0.06) * 0.08))
        self._payloads.append(payload)

    def _advance_playback(self) -> None:
        target = time.monotonic() - self._delay
        chosen = None
        while self._frames and self._frames[0][0] <= target:
            chosen = self._frames.popleft()
        if chosen is None:
            return
        stamp, image = chosen
        self.image = image
        self._clamp_all()
        detections = self._interpolate(stamp)
        if detections is not None:
            self.set_detections(detections)
        else:
            self.update()

    @staticmethod
    def _lerp_box(a, b, f: float):
        return tuple(a[i] + (b[i] - a[i]) * f for i in range(4))

    def _interpolate(self, stamp: float):
        while len(self._payloads) > 2 and self._payloads[1]["ts"] <= stamp:
            self._payloads.popleft()
        if not self._payloads:
            return None
        before = [p for p in self._payloads if p["ts"] <= stamp]
        after = [p for p in self._payloads if p["ts"] > stamp]
        a = before[-1] if before else None
        b = after[0] if after else None
        if a is None:
            base, objects = b, list(b["objects"])
        elif b is None:
            base = a
            if stamp - a["ts"] > 0.6:
                return {"t": time.monotonic(), "objects": [], "counts": a["counts"]}
            previous = before[-2] if len(before) > 1 else None
            objects = list(a["objects"])
            if previous is not None and a["ts"] > previous["ts"]:
                ahead = min(0.25, stamp - a["ts"]) / (a["ts"] - previous["ts"])
                old = {o["id"]: o for o in previous["objects"] if o["id"] is not None}
                objects = [
                    dict(o, box=self._lerp_box(old[o["id"]]["box"], o["box"], 1.0 + ahead)) if o["id"] in old else o
                    for o in objects
                ]
        else:
            fraction = (stamp - a["ts"]) / max(1e-6, b["ts"] - a["ts"])
            base = a if fraction < 0.5 else b
            following = {o["id"]: o for o in b["objects"] if o["id"] is not None}
            objects = []
            for o in a["objects"]:
                if o["id"] is not None and o["id"] in following:
                    objects.append(dict(o, box=self._lerp_box(o["box"], following[o["id"]]["box"], fraction)))
                elif o["id"] is not None or base is a:
                    objects.append(o)
            if base is b:
                objects.extend(o for o in b["objects"] if o["id"] is None)
            current = {o["id"] for o in a["objects"] if o["id"] is not None}
            objects.extend(o for o in b["objects"] if o["id"] is not None and o["id"] not in current and fraction > 0.5)
        return {"t": time.monotonic(), "objects": objects, "counts": base["counts"]}

    # ---------- data ----------
    def set_image(self, image: QImage) -> None:
        self.image = image
        if not self.compact:
            self._clamp_all()
        self.update()

    def set_status(self, status: str) -> None:
        self.status = status
        if status != "live" and self._lock_id is not None:
            self.release_lock()
        self.update()

    def set_weather(self, data: dict | None) -> None:
        self.weather = data
        self.update()

    def set_name(self, name: str) -> None:
        self.name = name
        self.update()

    def set_detections(self, payload: dict) -> None:
        self.detections = payload
        if self._lock_id is not None:
            now = time.monotonic()
            target = next((o for o in payload["objects"] if o["id"] == self._lock_id), None)
            if target is not None:
                self._lock_box = target["box"]
                self._lock_seen = now
                x1, y1, x2, y2 = target["box"]
                self._trail.append((now, (x1 + x2) / 2, (y1 + y2) / 2))
                self._follow(target, self._motion())
            elif now - self._lock_seen < 1.5 and self._lock_box is not None:
                vx, vy = self._motion()
                decay = max(0.0, 1.0 - (now - self._lock_seen) / 1.5)
                cx = self._tcenter[0] + vx * 0.04 * decay
                cy = self._tcenter[1] + vy * 0.04 * decay
                self._tcenter = self._clamp(self._tzoom, [cx, cy])
            elif now - self._lock_seen > 3.5:
                self.release_lock()
        self.update()

    def _motion(self) -> tuple[float, float]:
        if len(self._trail) < 3:
            return 0.0, 0.0
        latest = self._trail[-1]
        oldest = next((p for p in self._trail if latest[0] - p[0] <= 0.6), self._trail[0])
        span = latest[0] - oldest[0]
        if span < 0.15:
            return 0.0, 0.0
        return (latest[1] - oldest[1]) / span, (latest[2] - oldest[2]) / span

    def show_hint(self, seconds: float = 5.0) -> None:
        self._hint_until = time.monotonic() + seconds
        self.update()

    def reset_view(self, immediate: bool = False) -> None:
        self._lock_id = None
        self._tzoom = 1.0
        self._tcenter = [0.5, 0.5]
        if immediate:
            self._zoom = 1.0
            self._center = [0.5, 0.5]
            self._returning = False
        else:
            self._returning = True
        self.update()

    def release_lock(self) -> None:
        had_lock = self._lock_id is not None
        self._lock_id = None
        self._lock_text = ""
        self._lock_box = None
        self._trail.clear()
        self._returning = True
        if had_lock:
            self.lock_target.emit(None)
        self._tzoom = 1.0
        self._tcenter = [0.5, 0.5]
        if had_lock:
            self.lock_changed.emit(None)

    # ---------- geometry ----------
    def _image_size(self) -> tuple[float, float]:
        if self.image is None or self.image.isNull():
            return 16.0, 9.0
        return float(self.image.width()), float(self.image.height())

    def _base_scale(self) -> float:
        iw, ih = self._image_size()
        w, h = max(1, self.width()), max(1, self.height())
        return max(w / iw, h / ih) if self.compact else min(w / iw, h / ih)

    def _mapping(self, zoom: float, center) -> tuple[float, float, float]:
        iw, ih = self._image_size()
        s = self._base_scale() * zoom
        ox = self.width() / 2 - center[0] * iw * s
        oy = self.height() / 2 - center[1] * ih * s
        return s, ox, oy

    def _clamp(self, zoom: float, center) -> list[float]:
        iw, ih = self._image_size()
        s = self._base_scale() * zoom
        result = []
        for value, span, extent in ((center[0], iw, self.width()), (center[1], ih, self.height())):
            half = extent / (2 * span * s)
            result.append(0.5 if half >= 0.5 else min(max(value, half), 1 - half))
        return result

    def _clamp_all(self) -> None:
        self._center = self._clamp(self._zoom, self._center)
        self._tcenter = self._clamp(self._tzoom, self._tcenter)

    def _to_norm(self, pos: QPointF, zoom: float, center) -> tuple[float, float]:
        iw, ih = self._image_size()
        s, ox, oy = self._mapping(zoom, center)
        return (pos.x() - ox) / (iw * s), (pos.y() - oy) / (ih * s)

    def _norm_rect(self, box) -> QRectF:
        iw, ih = self._image_size()
        s, ox, oy = self._mapping(self._zoom, self._center)
        return QRectF(ox + box[0] * iw * s, oy + box[1] * ih * s, (box[2] - box[0]) * iw * s, (box[3] - box[1]) * ih * s)

    def _follow(self, obj: dict, velocity: tuple[float, float] = (0.0, 0.0), initial: bool = False) -> None:
        x1, y1, x2, y2 = obj["box"]
        iw, ih = self._image_size()
        s0 = self._base_scale()
        bw = max(1.0, (x2 - x1) * iw * s0)
        bh = max(1.0, (y2 - y1) * ih * s0)
        zoom = min(4.5, max(1.8, min(0.3 * self.width() / bw, 0.4 * self.height() / bh)))
        self._tzoom = zoom if initial else self._tzoom * 0.9 + zoom * 0.1
        lead = 0.35
        cx = (x1 + x2) / 2 + max(-0.08, min(0.08, velocity[0] * lead))
        cy = (y1 + y2) / 2 + max(-0.08, min(0.08, velocity[1] * lead))
        self._tcenter = self._clamp(self._tzoom, [cx, cy])
        self._returning = False

    def _zoom_at(self, pos: QPointF, factor: float) -> None:
        if self._lock_id is not None:
            self.release_lock()
        new_zoom = min(8.0, max(1.0, self._tzoom * factor))
        nx, ny = self._to_norm(pos, self._tzoom, self._tcenter)
        iw, ih = self._image_size()
        s = self._base_scale() * new_zoom
        center = [nx - (pos.x() - self.width() / 2) / (iw * s), ny - (pos.y() - self.height() / 2) / (ih * s)]
        self._tzoom = new_zoom
        self._tcenter = self._clamp(new_zoom, center)
        self._returning = False

    def _fresh_objects(self) -> list:
        if not self.detections or self.status != "live":
            return []
        if time.monotonic() - self.detections["t"] > DETECTION_STALE_SECONDS:
            return []
        return self.detections["objects"]

    def _publish_roi(self, now: float) -> None:
        roi = None
        zoom = min(self._zoom, self._tzoom)
        if zoom > 1.45 and self.image is not None:
            iw, ih = self._image_size()
            s = self._base_scale() * zoom
            hw = min(0.5, self.width() / (2 * iw * s))
            hh = min(0.5, self.height() / (2 * ih * s))
            cx = (self._center[0] + self._tcenter[0]) / 2
            cy = (self._center[1] + self._tcenter[1]) / 2
            roi = (max(0.0, cx - hw), max(0.0, cy - hh), min(1.0, cx + hw), min(1.0, cy + hh))
        if roi is None and self._roi is None:
            return
        if roi is not None and self._roi is not None and now - self._roi_sent < 0.12:
            return
        self._roi = roi
        self._roi_sent = now
        self.roi_changed.emit(roi)

    @staticmethod
    def _damp(current: float, target: float, velocity: float, smooth: float, dt: float) -> tuple[float, float]:
        omega = 2.0 / max(0.0001, smooth)
        x = omega * dt
        decay = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)
        change = current - target
        temp = (velocity + omega * change) * dt
        velocity = (velocity - omega * temp) * decay
        return target + (change + temp) * decay, velocity

    def _hit(self, pos: QPointF):
        nx, ny = self._to_norm(pos, self._zoom, self._center)
        best = None
        best_area = float("inf")
        for obj in self._fresh_objects():
            if obj["id"] is None:
                continue
            x1, y1, x2, y2 = obj["box"]
            pad = 0.006
            if x1 - pad <= nx <= x2 + pad and y1 - pad <= ny <= y2 + pad:
                area = (x2 - x1) * (y2 - y1)
                if area < best_area:
                    best, best_area = obj, area
        return best

    # ---------- animation ----------
    def _tick(self) -> None:
        now = time.monotonic()
        dt = min(0.05, max(0.0, now - self._last_tick))
        self._last_tick = now
        if self.buffered:
            self._advance_playback()
        if self._dragging:
            return
        smooth = 0.85 if self._returning else (0.32 if self._lock_id is not None else 0.09)
        before = (self._zoom, self._center[0], self._center[1])
        self._zoom, self._velocity[0] = self._damp(self._zoom, self._tzoom, self._velocity[0], smooth, dt)
        self._center[0], self._velocity[1] = self._damp(self._center[0], self._tcenter[0], self._velocity[1], smooth, dt)
        self._center[1], self._velocity[2] = self._damp(self._center[1], self._tcenter[1], self._velocity[2], smooth, dt)
        self._center = self._clamp(self._zoom, self._center)
        if (
            abs(self._zoom - self._tzoom) < 0.001
            and abs(self._center[0] - self._tcenter[0]) < 0.0003
            and abs(self._center[1] - self._tcenter[1]) < 0.0003
        ):
            self._zoom = self._tzoom
            self._center = list(self._tcenter)
            self._velocity = [0.0, 0.0, 0.0]
            self._returning = False
        self._publish_roi(now)
        changed = before != (self._zoom, self._center[0], self._center[1])
        if changed or self._lock_id is not None or now < self._hint_until + 0.6:
            self.update()

    def _on_hover(self, value) -> None:
        self._hover = float(value)
        self.update()

    def showEvent(self, event) -> None:
        self._last_tick = time.monotonic()
        if not self.compact:
            self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._timer.stop()
        super().hideEvent(event)

    # ---------- input ----------
    def enterEvent(self, event) -> None:
        if self.compact:
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover)
            self._hover_anim.setEndValue(1.0)
            self._hover_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self.compact:
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover)
            self._hover_anim.setEndValue(0.0)
            self._hover_anim.start()
        super().leaveEvent(event)

    def wheelEvent(self, event) -> None:
        if self.compact or self.image is None:
            event.ignore()
            return
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta:
            self._zoom_at(event.position(), 1.0015 ** delta)
        event.accept()

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.NativeGesture and not self.compact and self.image is not None:
            if event.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
                self._zoom_at(event.position(), 1.0 + event.value())
                return True
        return super().event(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.position()
            self._dragging = False
            self._drag_origin = tuple(self._center)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        if self.compact:
            return
        if self._press is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            if not self._dragging and (pos - self._press).manhattanLength() > 5 and self._zoom > 1.01:
                self._dragging = True
                if self._lock_id is not None:
                    self.release_lock()
                    self._tzoom = self._zoom
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if self._dragging:
                iw, ih = self._image_size()
                s = self._base_scale() * self._zoom
                center = [
                    self._drag_origin[0] - (pos.x() - self._press.x()) / (iw * s),
                    self._drag_origin[1] - (pos.y() - self._press.y()) / (ih * s),
                ]
                self._center = self._clamp(self._zoom, center)
                self._tcenter = list(self._center)
                self._tzoom = self._zoom
                self._returning = False
                self.update()
            return
        hovered = self._hit(pos)
        hover_id = hovered["id"] if hovered is not None else None
        if hover_id != self._hover_id:
            self._hover_id = hover_id
            self.update()
        if hovered is not None:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        elif self._zoom > 1.01:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        was_drag = self._dragging
        self._press = None
        self._dragging = False
        self._last_tick = time.monotonic()
        if self.compact:
            if self.rect().contains(event.position().toPoint()):
                self.clicked.emit()
            return
        self.setCursor(Qt.CursorShape.OpenHandCursor if self._zoom > 1.01 else Qt.CursorShape.ArrowCursor)
        if was_drag:
            return
        target = self._hit(event.position())
        if target is not None:
            self._lock_id = target["id"]
            self._lock_box = target["box"]
            self._lock_cls = target["cls"]
            self._lock_seen = time.monotonic()
            self._lock_since = self._lock_seen
            self._trail.clear()
            self._lock_text = f"{CLASS_LABELS.get(target['cls'], 'NESNE')} #{target['id']}"
            self._follow(target, initial=True)
            self.lock_target.emit({"id": target["id"], "box": target["box"], "cls": target["cls"]})
            self.lock_changed.emit(self._lock_text)
            self.update()
        elif self._lock_id is not None:
            self.release_lock()
            self.update()

    def mouseDoubleClickEvent(self, event) -> None:
        if self.compact or self.image is None:
            return
        if self._lock_id is None and self._hit(event.position()) is None:
            if self._tzoom > 1.05:
                self.reset_view()
            else:
                self._zoom_at(event.position(), 2.5)
            self.update()

    # ---------- painting ----------
    def _ensure_canvas(self) -> QImage:
        dpr = self.devicePixelRatioF()
        size = QSize(max(1, int(self.width() * dpr)), max(1, int(self.height() * dpr)))
        if self._canvas is None or self._canvas.size() != size:
            self._canvas = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
            self._canvas.setDevicePixelRatio(dpr)
        return self._canvas

    def paintEvent(self, event) -> None:
        w, h = float(self.width()), float(self.height())
        if w < 4 or h < 4:
            return
        pal = current_palette()
        canvas = self._ensure_canvas()
        cp = QPainter(canvas)
        cp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        cp.fillRect(QRectF(0, 0, w, h), QColor(14, 14, 16) if not self.compact or pal.dark else pal.tile_empty.darker(160))
        has_image = self.image is not None and not self.image.isNull()
        if has_image:
            iw, ih = self._image_size()
            s, ox, oy = self._mapping(self._zoom, self._center)
            cp.drawImage(QRectF(ox, oy, iw * s, ih * s), self.image)
        cp.end()

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        clip = rounded_path(QRectF(0, 0, w, h), self.radius)
        p.setClipPath(clip)
        p.drawImage(QPointF(0, 0), canvas)

        if not has_image or self.status != "live":
            self._paint_status_center(p, w, h, has_image)
        if has_image and (self.compact or self.chrome_opacity > 0.5):
            self._paint_boxes(p)
        if self.compact:
            self._paint_compact_overlay(p, canvas, w, h)
        elif self.chrome_opacity > 0.01:
            p.save()
            p.setOpacity(self.chrome_opacity)
            self._paint_focus_overlay(p, canvas, w, h)
            p.restore()

        p.setClipping(False)
        border = QColor(pal.tile_border)
        if self.compact:
            hover = pal.tile_border_hover
            border = QColor(
                int(border.red() + (hover.red() - border.red()) * self._hover),
                int(border.green() + (hover.green() - border.green()) * self._hover),
                int(border.blue() + (hover.blue() - border.blue()) * self._hover),
                int(border.alpha() + (hover.alpha() - border.alpha()) * self._hover),
            )
        p.setPen(QPen(border, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(rounded_path(QRectF(0.5, 0.5, w - 1, h - 1), self.radius))

    def _paint_status_center(self, p: QPainter, w: float, h: float, has_image: bool) -> None:
        if has_image:
            p.fillRect(QRectF(0, 0, w, h), QColor(10, 10, 12, 120))
        text = STATUS_TEXT.get(self.status, "")
        if not has_image and self.status == "live":
            text = "GÖRÜNTÜ BEKLENİYOR"
        p.setFont(font(10.5 if self.compact else 12, QFont.Weight.Medium, 1.6))
        p.setPen(OVERLAY_TEXT_FAINT)
        p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, text)

    def _paint_trail(self, p: QPainter) -> None:
        if len(self._trail) < 2:
            return
        iw, ih = self._image_size()
        sc, ox, oy = self._mapping(self._zoom, self._center)
        points = [QPointF(ox + x * iw * sc, oy + y * ih * sc) for _, x, y in self._trail]
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        total = len(points)
        for i in range(1, total):
            p.setPen(QPen(QColor(245, 245, 247, int(20 + 150 * i / total)), 1.0))
            p.drawLine(points[i - 1], points[i])
        p.restore()

    @staticmethod
    def _brackets(p: QPainter, r: QRectF) -> None:
        k = max(5.0, min(16.0, min(r.width(), r.height()) * 0.28))
        x1, y1, x2, y2 = r.left(), r.top(), r.right(), r.bottom()
        for (ax, ay, dx, dy) in ((x1, y1, 1, 1), (x2, y1, -1, 1), (x1, y2, 1, -1), (x2, y2, -1, -1)):
            p.drawLine(QPointF(ax, ay), QPointF(ax + dx * k, ay))
            p.drawLine(QPointF(ax, ay), QPointF(ax, ay + dy * k))

    def _paint_boxes(self, p: QPainter) -> None:
        objects = self._fresh_objects()
        if not self.compact and self._lock_id is not None:
            self._paint_trail(p)
        if not objects:
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.setFont(font(9.5, QFont.Weight.Medium, 0.8))
        for obj in objects:
            r = self._norm_rect(obj["box"])
            if r.width() < 2 or r.height() < 2:
                continue
            aligned = QRectF(r.toAlignedRect().adjusted(0, 0, -1, -1))
            if self.compact:
                p.setPen(QPen(QColor(245, 245, 247, 95), 1.0))
                p.drawRect(aligned)
                continue
            tracked = obj["id"] is not None
            locked = tracked and obj["id"] == self._lock_id
            hovered = tracked and obj["id"] == self._hover_id
            if locked:
                p.setPen(QPen(QColor(245, 245, 247, 70), 1.0))
                p.drawRect(aligned.adjusted(-3, -3, 3, 3))
                p.setPen(QPen(QColor(250, 250, 252, 245), 1.0))
                self._brackets(p, aligned.adjusted(-3, -3, 3, 3))
            else:
                alpha = 215 if hovered else (125 if tracked else 70)
                p.setPen(QPen(QColor(245, 245, 247, alpha), 1.0))
                p.drawRect(aligned)
            if tracked and (locked or hovered or r.height() > 46):
                label = f"{CLASS_LABELS.get(obj['cls'], '')}  {obj['id']}"
                if hovered or locked:
                    label += f"  ·  %{round(obj['conf'] * 100)}"
                p.setPen(QColor(245, 245, 247, 235 if (locked or hovered) else 140))
                top = aligned.top() - (19 if locked else 15)
                p.drawText(QRectF(aligned.x() - (3 if locked else 0), top, 220, 14), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, label)
        p.restore()

    def _counts(self) -> dict:
        if self.detections and self.status == "live" and time.monotonic() - self.detections["t"] < 4.0:
            return self.detections["counts"]
        return {k: None for k in CATEGORY_ORDER}

    def _paint_compact_overlay(self, p: QPainter, canvas: QImage, w: float, h: float) -> None:
        shade = QLinearGradient(0, h - 64, 0, h)
        shade.setColorAt(0, QColor(0, 0, 0, 0))
        shade.setColorAt(1, QColor(0, 0, 0, 120))
        p.fillRect(QRectF(0, h - 64, w, 64), shade)

        if w >= 230 and h >= 110:
            counts = self._counts()
            cell_w, cell_h, pad = 50.0, 30.0, 7.0
            panel = QRectF(10, 10, pad * 2 + cell_w * 2, pad * 2 + cell_h * 2)
            paint_glass(p, canvas, panel, 9)
            for i, key in enumerate(CATEGORY_ORDER):
                cx = panel.x() + pad + (i % 2) * cell_w
                cy = panel.y() + pad + (i // 2) * cell_h
                value = counts.get(key)
                p.setFont(font(13, QFont.Weight.DemiBold))
                p.setPen(OVERLAY_TEXT)
                p.drawText(QRectF(cx + 4, cy, cell_w - 4, 17), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, "–" if value is None else str(value))
                p.setFont(font(8, QFont.Weight.Medium, 0.9))
                p.setPen(OVERLAY_TEXT_DIM)
                p.drawText(QRectF(cx + 4, cy + 16, cell_w - 4, 11), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, CATEGORY_LABELS[key])

        if self.weather and w >= 200:
            badge = QRectF(w - 10 - 70, 10, 70, 26)
            paint_glass(p, canvas, badge, 13)
            draw_weather_icon(p, QRectF(badge.x() + 10, badge.y() + 5, 16, 16), self.weather["kind"], self.weather["is_day"], OVERLAY_TEXT)
            p.setFont(font(12.5, QFont.Weight.Medium))
            p.setPen(OVERLAY_TEXT)
            p.drawText(QRectF(badge.x() + 32, badge.y(), badge.width() - 38, badge.height()), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, f"{round(self.weather['temperature'])}°")

        dot = QPointF(16, h - 19)
        if self.status == "live":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(245, 245, 247, 225))
        elif self.status == "connecting":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(245, 245, 247, 90))
        else:
            p.setPen(QPen(QColor(245, 245, 247, 140), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(dot, 2.6, 2.6)
        p.setFont(font(11.5, QFont.Weight.DemiBold, 1.2))
        p.setPen(OVERLAY_TEXT)
        name_rect = QRectF(26, h - 30, w - 120, 22)
        p.drawText(name_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, p.fontMetrics().elidedText(self.name, Qt.TextElideMode.ElideRight, int(name_rect.width())))
        if self.status == "live":
            p.setFont(font(8.5, QFont.Weight.Medium, 1.4))
            p.setPen(OVERLAY_TEXT_FAINT)
            p.drawText(QRectF(w - 90, h - 30, 78, 22), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "CANLI")

    def _paint_pill(self, p: QPainter, canvas: QImage, x: float, y: float, text: str, anchor: str, alpha: float = 1.0) -> None:
        p.setFont(font(11, QFont.Weight.Medium, 0.8))
        width = p.fontMetrics().horizontalAdvance(text) + 26
        if anchor == "right":
            x -= width
        elif anchor == "center":
            x -= width / 2
        rect = QRectF(x, y, width, 28)
        p.save()
        p.setOpacity(alpha)
        paint_glass(p, canvas, rect, 14)
        p.setPen(OVERLAY_TEXT)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        p.restore()

    def _paint_focus_overlay(self, p: QPainter, canvas: QImage, w: float, h: float) -> None:
        if self.top_inset > 0:
            paint_glass(p, canvas, QRectF(10, 10, w - 20, self.top_inset - 18), 13)

        counts = self._counts()
        panel = QRectF(16, self.top_inset + 6, 168, 4 * 34 + 12)
        paint_glass(p, canvas, panel, 12)
        for i, key in enumerate(CATEGORY_ORDER):
            row = QRectF(panel.x() + 14, panel.y() + 6 + i * 34, panel.width() - 28, 34)
            p.setFont(font(10, QFont.Weight.Medium, 1.3))
            p.setPen(OVERLAY_TEXT_DIM)
            p.drawText(row, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, CATEGORY_LABELS[key])
            p.setFont(font(17, QFont.Weight.DemiBold))
            p.setPen(OVERLAY_TEXT)
            value = counts.get(key)
            p.drawText(row, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, "–" if value is None else str(value))
            if i < 3:
                p.setPen(QPen(QColor(255, 255, 255, 18), 1.0))
                p.drawLine(QPointF(row.left(), row.bottom()), QPointF(row.right(), row.bottom()))

        if self._lock_id is not None and self._lock_text:
            elapsed = int(time.monotonic() - self._lock_since)
            self._paint_pill(p, canvas, 16, h - 44, f"TAKİP · {self._lock_text} · {elapsed // 60:02d}:{elapsed % 60:02d}", "left")
        if self._zoom > 1.02:
            self._paint_pill(p, canvas, w - 16, h - 44, f"{self._zoom:.1f}×", "right")

        remaining = self._hint_until - time.monotonic()
        if remaining > -0.6:
            alpha = 1.0 if remaining > 0 else max(0.0, 1.0 + remaining / 0.6)
            self._paint_pill(
                p, canvas, w / 2, h - 44,
                "Kaydırarak yakınlaştırın  ·  Takip için nesneye tıklayın  ·  Esc ile geri dönün",
                "center", alpha,
            )
