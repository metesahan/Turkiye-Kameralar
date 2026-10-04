import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QLinearGradient, QPainter, QPen, QRadialGradient
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"


def render(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    inset = size * 0.1
    rect = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
    radius = rect.width() * 0.225
    body = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    body.setColorAt(0, QColor(46, 46, 50))
    body.setColorAt(1, QColor(18, 18, 20))
    p.setPen(QPen(QColor(255, 255, 255, 46), max(1.0, size / 256)))
    p.setBrush(body)
    p.drawRoundedRect(rect, radius, radius)
    sheen = QLinearGradient(rect.topLeft(), rect.center())
    sheen.setColorAt(0, QColor(255, 255, 255, 30))
    sheen.setColorAt(1, QColor(255, 255, 255, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(sheen)
    p.drawRoundedRect(rect, radius, radius)
    c = rect.center()
    lens = rect.width() * 0.26
    glass = QRadialGradient(QPointF(c.x() - lens * 0.3, c.y() - lens * 0.3), lens * 1.4)
    glass.setColorAt(0, QColor(90, 92, 98))
    glass.setColorAt(1, QColor(14, 14, 16))
    p.setBrush(glass)
    p.setPen(QPen(QColor(236, 236, 240, 235), rect.width() * 0.035))
    p.drawEllipse(c, lens, lens)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(236, 236, 240, 235))
    p.drawEllipse(c, lens * 0.28, lens * 0.28)
    p.setBrush(QColor(255, 255, 255, 120))
    p.drawEllipse(QPointF(c.x() - lens * 0.42, c.y() - lens * 0.42), lens * 0.1, lens * 0.1)
    p.end()
    return image


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    ASSETS.mkdir(exist_ok=True)
    render(1024).save(str(ASSETS / "icon.png"))
    render(256).save(str(ASSETS / "icon.ico"))
    if sys.platform == "darwin" and shutil.which("iconutil"):
        iconset = ASSETS / "icon.iconset"
        iconset.mkdir(exist_ok=True)
        for base in (16, 32, 128, 256, 512):
            render(base).save(str(iconset / f"icon_{base}x{base}.png"))
            render(base * 2).save(str(iconset / f"icon_{base}x{base}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(ASSETS / "icon.icns")], check=True)
        shutil.rmtree(iconset)
    del app


if __name__ == "__main__":
    main()
