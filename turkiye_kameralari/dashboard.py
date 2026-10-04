from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .theme import font
from .widgets import VideoView

MARGIN = 22
SPACING = 14
MIN_TILE_WIDTH = 300


class GridCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("GridCanvas")
        self.tiles: list[VideoView] = []
        self.empty = QLabel("Henüz kamera yok. Ayarlar üzerinden yeni bir yayın ekleyebilirsiniz.", self)
        self.empty.setObjectName("Tertiary")
        self.empty.setFont(font(13))
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.hide()

    def set_tiles(self, tiles: list[VideoView]) -> None:
        self.tiles = tiles
        for tile in tiles:
            tile.setParent(self)
            tile.show()
        self.empty.setVisible(not tiles)
        self.relayout()

    def relayout(self) -> None:
        width = max(1, self.width())
        usable = width - 2 * MARGIN
        cols = max(1, (usable + SPACING) // (MIN_TILE_WIDTH + SPACING))
        if self.tiles:
            cols = min(cols, len(self.tiles))
        tile_w = (usable - (cols - 1) * SPACING) / cols
        tile_h = tile_w * 9 / 16
        for index, tile in enumerate(self.tiles):
            row, col = divmod(index, cols)
            x = MARGIN + col * (tile_w + SPACING)
            y = 6 + row * (tile_h + SPACING)
            tile.setGeometry(QRect(round(x), round(y), round(tile_w), round(tile_h)))
        rows = (len(self.tiles) + cols - 1) // cols
        height = 6 + rows * tile_h + max(0, rows - 1) * SPACING + MARGIN
        self.setMinimumHeight(int(height))
        self.empty.setGeometry(0, 0, width, max(200, self.height()))

    def resizeEvent(self, event) -> None:
        self.relayout()
        super().resizeEvent(event)


class DashboardPage(QWidget):
    tile_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.tiles: dict[str, VideoView] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("Page")
        bar = QHBoxLayout(header)
        bar.setContentsMargins(MARGIN, 22, MARGIN, 16)
        bar.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(3)
        title = QLabel("Kameralar")
        title.setObjectName("Display")
        title.setFont(font(24, QFont.Weight.DemiBold))
        self.summary = QLabel("")
        self.summary.setObjectName("Secondary")
        self.summary.setFont(font(12.5))
        titles.addWidget(title)
        titles.addWidget(self.summary)
        bar.addLayout(titles)
        bar.addStretch(1)
        hint = QLabel("Büyütmek için bir kameraya tıklayın")
        hint.setObjectName("Tertiary")
        hint.setFont(font(11.5, QFont.Weight.Normal, 0.3))
        bar.addWidget(hint, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.canvas = GridCanvas()
        self.scroll.setWidget(self.canvas)
        layout.addWidget(self.scroll, 1)

    def set_cameras(self, cameras, manager) -> None:
        existing = self.tiles
        self.tiles = {}
        ordered = []
        for cam in cameras:
            tile = existing.pop(cam.id, None)
            if tile is None:
                tile = VideoView(compact=True)
                tile.clicked.connect(lambda cid=cam.id: self.tile_clicked.emit(cid))
                tile.set_status(manager.statuses.get(cam.id, "connecting"))
                tile.set_weather(manager.weather.get(cam.id))
            tile.set_name(cam.name)
            self.tiles[cam.id] = tile
            ordered.append(tile)
        for tile in existing.values():
            tile.hide()
            tile.deleteLater()
        self.canvas.set_tiles(ordered)
        self.refresh_summary(manager)

    def refresh_summary(self, manager) -> None:
        total = len(manager.cameras)
        live = sum(1 for c in manager.cameras if manager.statuses.get(c.id) == "live")
        self.summary.setText(f"{total} kamera · {live} canlı yayın")
