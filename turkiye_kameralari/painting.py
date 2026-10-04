import math

from PyQt6.QtCore import QPointF, QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen

GLASS_TINT = QColor(20, 20, 22, 112)
GLASS_BORDER = QColor(255, 255, 255, 34)
GLASS_HIGHLIGHT = QColor(255, 255, 255, 16)
OVERLAY_TEXT = QColor(245, 245, 247, 235)
OVERLAY_TEXT_DIM = QColor(235, 235, 245, 150)
OVERLAY_TEXT_FAINT = QColor(235, 235, 245, 95)


def blur_image(image: QImage, factor: int = 10) -> QImage:
    if image.isNull():
        return image
    w, h = image.width(), image.height()
    small = image.scaled(
        max(1, w // factor), max(1, h // factor),
        Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )
    middle = small.scaled(
        max(1, w // 3), max(1, h // 3),
        Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )
    return middle.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)


def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect, radius, radius)
    return path


def paint_glass(
    painter: QPainter,
    canvas: QImage | None,
    rect: QRectF,
    radius: float,
    tint: QColor = GLASS_TINT,
    border: QColor = GLASS_BORDER,
) -> None:
    path = rounded_path(rect, radius)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    if canvas is not None and not canvas.isNull():
        dpr = canvas.devicePixelRatio()
        source = QRect(
            int(rect.x() * dpr), int(rect.y() * dpr),
            int(math.ceil(rect.width() * dpr)), int(math.ceil(rect.height() * dpr)),
        ).intersected(canvas.rect())
        if source.width() > 2 and source.height() > 2:
            piece = blur_image(canvas.copy(source), 12)
            target = QRectF(source.x() / dpr, source.y() / dpr, source.width() / dpr, source.height() / dpr)
            painter.setClipPath(path)
            painter.drawImage(target, piece)
            painter.setClipping(False)
    painter.fillPath(path, tint)
    sheen = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    sheen.setColorAt(0.0, GLASS_HIGHLIGHT)
    sheen.setColorAt(0.5, QColor(255, 255, 255, 0))
    painter.fillPath(path, sheen)
    painter.setPen(QPen(border, 1.0))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(rounded_path(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius))
    painter.restore()


def _cloud(painter: QPainter, r: QRectF) -> None:
    path = QPainterPath()
    w, h = r.width(), r.height()
    path.addEllipse(QRectF(r.x() + w * 0.05, r.y() + h * 0.42, w * 0.42, h * 0.42))
    path.addEllipse(QRectF(r.x() + w * 0.24, r.y() + h * 0.18, w * 0.48, h * 0.52))
    path.addEllipse(QRectF(r.x() + w * 0.52, r.y() + h * 0.38, w * 0.42, h * 0.46))
    path.addRoundedRect(QRectF(r.x() + w * 0.18, r.y() + h * 0.55, w * 0.64, h * 0.29), h * 0.1, h * 0.1)
    painter.drawPath(path.simplified())


def _sun(painter: QPainter, center: QPointF, radius: float, rays: bool = True) -> None:
    painter.drawEllipse(center, radius, radius)
    if rays:
        for i in range(8):
            angle = math.pi / 4 * i
            inner = radius * 1.55
            outer = radius * 2.1
            painter.drawLine(
                QPointF(center.x() + math.cos(angle) * inner, center.y() + math.sin(angle) * inner),
                QPointF(center.x() + math.cos(angle) * outer, center.y() + math.sin(angle) * outer),
            )


def _moon(painter: QPainter, center: QPointF, radius: float) -> None:
    outer = QPainterPath()
    outer.addEllipse(center, radius, radius)
    cut = QPainterPath()
    cut.addEllipse(QPointF(center.x() + radius * 0.55, center.y() - radius * 0.35), radius * 0.85, radius * 0.85)
    painter.drawPath(outer.subtracted(cut))


def draw_weather_icon(painter: QPainter, rect: QRectF, kind: str, is_day: bool, color: QColor) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, max(1.0, rect.width() / 14.0))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    c = rect.center()
    s = rect.width()
    if kind == "clear":
        if is_day:
            _sun(painter, c, s * 0.2)
        else:
            _moon(painter, c, s * 0.34)
    elif kind == "partly":
        small = QPointF(rect.x() + s * 0.36, rect.y() + s * 0.32)
        if is_day:
            _sun(painter, small, s * 0.13)
        else:
            _moon(painter, small, s * 0.2)
        painter.setBrush(QColor(28, 28, 30, 230))
        _cloud(painter, QRectF(rect.x() + s * 0.12, rect.y() + s * 0.22, s * 0.86, s * 0.7))
    elif kind == "fog":
        for i, (a, b) in enumerate(((0.15, 0.85), (0.08, 0.72), (0.25, 0.92))):
            y = rect.y() + s * (0.32 + i * 0.18)
            painter.drawLine(QPointF(rect.x() + s * a, y), QPointF(rect.x() + s * b, y))
    else:
        cloud_rect = QRectF(rect.x() + s * 0.04, rect.y() + s * 0.02, s * 0.92, s * 0.72)
        if kind == "cloudy":
            cloud_rect = QRectF(rect.x() + s * 0.04, rect.y() + s * 0.12, s * 0.92, s * 0.76)
        _cloud(painter, cloud_rect)
        base = rect.y() + s * 0.74
        if kind == "rain":
            for x in (0.3, 0.5, 0.7):
                painter.drawLine(QPointF(rect.x() + s * x, base), QPointF(rect.x() + s * (x - 0.06), base + s * 0.18))
        elif kind == "snow":
            painter.setBrush(color)
            for x in (0.3, 0.5, 0.7):
                painter.drawEllipse(QPointF(rect.x() + s * x, base + s * 0.1), s * 0.035, s * 0.035)
        elif kind == "storm":
            bolt = QPainterPath()
            bolt.moveTo(rect.x() + s * 0.54, base - s * 0.04)
            bolt.lineTo(rect.x() + s * 0.42, base + s * 0.12)
            bolt.lineTo(rect.x() + s * 0.54, base + s * 0.12)
            bolt.lineTo(rect.x() + s * 0.44, base + s * 0.26)
            painter.drawPath(bolt)
    painter.restore()


def draw_nav_icon(painter: QPainter, rect: QRectF, name: str, color: QColor) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    pen = QPen(color, 1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    x, y, s = rect.x(), rect.y(), rect.width()
    c = rect.center()
    if name == "grid":
        g = s * 0.36
        gap = s * 0.1
        for i in range(2):
            for j in range(2):
                painter.drawRoundedRect(QRectF(x + s * 0.09 + i * (g + gap), y + s * 0.09 + j * (g + gap), g, g), 2.2, 2.2)
    elif name == "weather":
        draw_weather_icon(painter, rect, "partly", True, color)
    elif name == "settings":
        r = s * 0.1
        for i, level in enumerate((0.26, 0.5, 0.74)):
            yy = y + s * level
            knob = x + s * (0.68, 0.32, 0.56)[i]
            painter.drawLine(QPointF(x + s * 0.1, yy), QPointF(knob - r, yy))
            painter.drawLine(QPointF(knob + r, yy), QPointF(x + s * 0.9, yy))
            painter.drawEllipse(QPointF(knob, yy), r, r)
    elif name == "sun":
        _sun(painter, c, s * 0.16)
    elif name == "moon":
        _moon(painter, c, s * 0.32)
    elif name == "exit":
        painter.drawLine(QPointF(x + s * 0.55, y + s * 0.15), QPointF(x + s * 0.2, y + s * 0.15))
        painter.drawLine(QPointF(x + s * 0.2, y + s * 0.15), QPointF(x + s * 0.2, y + s * 0.85))
        painter.drawLine(QPointF(x + s * 0.2, y + s * 0.85), QPointF(x + s * 0.55, y + s * 0.85))
        painter.drawLine(QPointF(x + s * 0.42, c.y()), QPointF(x + s * 0.9, c.y()))
        painter.drawLine(QPointF(x + s * 0.74, y + s * 0.34), QPointF(x + s * 0.9, c.y()))
        painter.drawLine(QPointF(x + s * 0.74, y + s * 0.66), QPointF(x + s * 0.9, c.y()))
    elif name == "fullscreen":
        k = s * 0.22
        for (px, py, dx, dy) in ((0.12, 0.12, 1, 1), (0.88, 0.12, -1, 1), (0.12, 0.88, 1, -1), (0.88, 0.88, -1, -1)):
            ox, oy = x + s * px, y + s * py
            painter.drawLine(QPointF(ox, oy), QPointF(ox + dx * k, oy))
            painter.drawLine(QPointF(ox, oy), QPointF(ox, oy + dy * k))
    painter.restore()
