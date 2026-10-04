from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from . import preferences
from .config import WEATHER_REFRESH_SECONDS
from .painting import OVERLAY_TEXT, OVERLAY_TEXT_DIM, draw_weather_icon, paint_glass, rounded_path
from .theme import current_palette, font, qcolor
from .weather import ForecastTask

ROLE = Qt.ItemDataRole.UserRole


def _card(p: QPainter, rect: QRectF) -> None:
    pal = current_palette()
    p.setPen(QPen(pal.card_border, 1.0))
    p.setBrush(pal.card)
    p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)


def _title(p: QPainter, x: float, y: float, text: str) -> None:
    p.setFont(font(10, QFont.Weight.DemiBold, 1.4))
    p.setPen(qcolor(current_palette().text_tertiary))
    p.drawText(QRectF(x, y, 400, 16), Qt.AlignmentFlag.AlignVCenter, text)


class HeroCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(290)
        self.data: dict | None = None
        self.place = ""
        self.region = ""
        self.image: QImage | None = None
        self.message = ""
        self._canvas: QImage | None = None

    def paintEvent(self, event) -> None:
        w, h = float(self.width()), float(self.height())
        dpr = self.devicePixelRatioF()
        canvas = QImage(int(w * dpr), int(h * dpr), QImage.Format.Format_ARGB32_Premultiplied)
        canvas.setDevicePixelRatio(dpr)
        cp = QPainter(canvas)
        cp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self.image is not None and not self.image.isNull():
            iw, ih = self.image.width(), self.image.height()
            s = max(w / iw, h / ih)
            cp.drawImage(QRectF((w - iw * s) / 2, (h - ih * s) / 2, iw * s, ih * s), self.image)
        else:
            gradient = QLinearGradient(0, 0, w, h)
            gradient.setColorAt(0, QColor(58, 60, 66))
            gradient.setColorAt(1, QColor(24, 25, 28))
            cp.fillRect(QRectF(0, 0, w, h), gradient)
        shade = QLinearGradient(0, 0, w, 0)
        shade.setColorAt(0, QColor(0, 0, 0, 120))
        shade.setColorAt(0.6, QColor(0, 0, 0, 30))
        shade.setColorAt(1, QColor(0, 0, 0, 0))
        cp.fillRect(QRectF(0, 0, w, h), shade)
        cp.end()

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setClipPath(rounded_path(QRectF(0, 0, w, h), 16))
        p.drawImage(QPointF(0, 0), canvas)

        p.setPen(OVERLAY_TEXT)
        p.setFont(font(12, QFont.Weight.DemiBold, 1.8))
        p.drawText(QRectF(28, 24, w - 56, 18), Qt.AlignmentFlag.AlignVCenter, self.place)
        p.setFont(font(11.5, QFont.Weight.Normal, 0.3))
        p.setPen(OVERLAY_TEXT_DIM)
        p.drawText(QRectF(28, 44, w - 56, 16), Qt.AlignmentFlag.AlignVCenter, self.region)

        data = self.data
        if data is None:
            p.setFont(font(13, QFont.Weight.Medium, 0.4))
            p.setPen(OVERLAY_TEXT_DIM)
            p.drawText(QRectF(28, 0, w - 56, h), Qt.AlignmentFlag.AlignVCenter, self.message or "Yükleniyor…")
        else:
            p.setPen(OVERLAY_TEXT)
            p.setFont(font(78, QFont.Weight.ExtraLight))
            temp_text = f"{round(data['temperature'])}°"
            p.drawText(QRectF(22, 70, 260, 100), Qt.AlignmentFlag.AlignVCenter, temp_text)
            advance = p.fontMetrics().horizontalAdvance(temp_text)
            draw_weather_icon(p, QRectF(30 + advance + 6, 96, 40, 40), data["kind"], data["is_day"], OVERLAY_TEXT)
            p.setFont(font(17, QFont.Weight.Medium))
            p.drawText(QRectF(28, 168, w - 56, 24), Qt.AlignmentFlag.AlignVCenter, data["label"])
            today = data["days"][0] if data["days"] else None
            if today:
                p.setFont(font(12.5, QFont.Weight.Normal, 0.3))
                p.setPen(OVERLAY_TEXT_DIM)
                p.drawText(
                    QRectF(28, 194, w - 56, 20),
                    Qt.AlignmentFlag.AlignVCenter,
                    f"En yüksek {round(today['max'])}°  ·  En düşük {round(today['min'])}°",
                )

            if w > 640:
                panel = QRectF(w - 268, 24, 244, h - 48)
                paint_glass(p, canvas, panel, 14)
                rows = [
                    ("HİSSEDİLEN", f"{round(data['feels_like'])}°"),
                    ("NEM", f"%{round(data['humidity'])}"),
                    ("RÜZGÂR", f"{round(data['wind'])} km/sa {data['wind_direction']}"),
                    ("BASINÇ", f"{round(data['pressure'])} hPa"),
                ]
                if today:
                    rows.append(("GÜN DOĞUMU", today["sunrise"]))
                    rows.append(("GÜN BATIMI", today["sunset"]))
                row_h = (panel.height() - 20) / len(rows)
                for i, (label, value) in enumerate(rows):
                    r = QRectF(panel.x() + 16, panel.y() + 10 + i * row_h, panel.width() - 32, row_h)
                    p.setFont(font(9.5, QFont.Weight.DemiBold, 1.2))
                    p.setPen(OVERLAY_TEXT_DIM)
                    p.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)
                    p.setFont(font(13.5, QFont.Weight.Medium))
                    p.setPen(OVERLAY_TEXT)
                    p.drawText(r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, value)
                    if i < len(rows) - 1:
                        p.setPen(QPen(QColor(255, 255, 255, 20), 1))
                        p.drawLine(QPointF(r.left(), r.bottom()), QPointF(r.right(), r.bottom()))

        p.setClipping(False)
        p.setPen(QPen(current_palette().tile_border, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(rounded_path(QRectF(0.5, 0.5, w - 1, h - 1), 16))


class HourlyStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(178)
        self.hours: list[dict] = []

    def paintEvent(self, event) -> None:
        pal = current_palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        _card(p, rect)
        _title(p, 20, 14, "SAATLİK TAHMİN")
        hours = self.hours[::2][:12]
        if not hours:
            return
        ink = pal.ink
        dim = qcolor(pal.text_secondary)
        faint = qcolor(pal.text_tertiary)
        left, right = 20.0, rect.width() - 20.0
        step = (right - left) / len(hours)
        temps = [h["temperature"] for h in hours]
        lo, hi = min(temps), max(temps)
        span = max(1.0, hi - lo)
        curve_top, curve_bottom = 104.0, 132.0
        points = []
        for i, hour in enumerate(hours):
            cx = left + step * (i + 0.5)
            p.setFont(font(11.5, QFont.Weight.Medium if i == 0 else QFont.Weight.Normal))
            p.setPen(ink if i == 0 else dim)
            p.drawText(QRectF(cx - step / 2, 38, step, 18), Qt.AlignmentFlag.AlignCenter, hour["label"])
            draw_weather_icon(p, QRectF(cx - 10, 62, 20, 20), hour["kind"], hour["is_day"], ink)
            if hour.get("rain"):
                p.setFont(font(9.5, QFont.Weight.Medium))
                p.setPen(faint)
                p.drawText(QRectF(cx - step / 2, 84, step, 14), Qt.AlignmentFlag.AlignCenter, f"%{hour['rain']}")
            y = curve_bottom - (hour["temperature"] - lo) / span * (curve_bottom - curve_top)
            points.append(QPointF(cx, y))
            p.setFont(font(13, QFont.Weight.DemiBold))
            p.setPen(ink)
            p.drawText(QRectF(cx - step / 2, 142, step, 20), Qt.AlignmentFlag.AlignCenter, f"{round(hour['temperature'])}°")
        path = QPainterPath(points[0])
        for a, b in zip(points, points[1:]):
            mid = (a.x() + b.x()) / 2
            path.cubicTo(QPointF(mid, a.y()), QPointF(mid, b.y()), b)
        line = QColor(ink)
        line.setAlpha(110)
        p.setPen(QPen(line, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ink)
        for point in points:
            p.drawEllipse(point, 2.2, 2.2)


class DailyList(QWidget):
    ROW = 44

    def __init__(self, parent=None):
        super().__init__(parent)
        self.days: list[dict] = []
        self.setMinimumHeight(48 + 7 * self.ROW + 8)

    def paintEvent(self, event) -> None:
        pal = current_palette()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        _card(p, rect)
        _title(p, 20, 14, "7 GÜNLÜK TAHMİN")
        if not self.days:
            return
        ink = pal.ink
        dim = qcolor(pal.text_secondary)
        faint = qcolor(pal.text_tertiary)
        lo = min(d["min"] for d in self.days)
        hi = max(d["max"] for d in self.days)
        span = max(1.0, hi - lo)
        w = rect.width()
        bar_left = max(250.0, w * 0.42)
        bar_right = w - 70
        for i, day in enumerate(self.days):
            y = 42 + i * self.ROW
            row = QRectF(20, y, w - 40, self.ROW)
            p.setFont(font(13.5, QFont.Weight.DemiBold if i == 0 else QFont.Weight.Medium))
            p.setPen(ink)
            p.drawText(QRectF(row.x(), y, 110, self.ROW), Qt.AlignmentFlag.AlignVCenter, day["label"])
            draw_weather_icon(p, QRectF(row.x() + 116, y + 12, 20, 20), day["kind"], True, ink)
            p.setFont(font(11.5))
            p.setPen(dim)
            p.drawText(QRectF(row.x() + 146, y, bar_left - row.x() - 200, self.ROW), Qt.AlignmentFlag.AlignVCenter, day["description"])
            if day.get("rain"):
                p.setPen(faint)
                p.drawText(QRectF(bar_left - 56, y, 44, self.ROW), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"%{day['rain']}")
            p.setFont(font(13, QFont.Weight.Medium))
            p.setPen(dim)
            p.drawText(QRectF(bar_left, y, 40, self.ROW), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"{round(day['min'])}°")
            track = QRectF(bar_left + 52, y + self.ROW / 2 - 2, bar_right - bar_left - 64, 4)
            track_color = QColor(ink)
            track_color.setAlpha(22)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(track_color)
            p.drawRoundedRect(track, 2, 2)
            x1 = track.x() + (day["min"] - lo) / span * track.width()
            x2 = track.x() + (day["max"] - lo) / span * track.width()
            fill = QLinearGradient(x1, 0, x2, 0)
            start = QColor(ink)
            start.setAlpha(90)
            end = QColor(ink)
            end.setAlpha(210)
            fill.setColorAt(0, start)
            fill.setColorAt(1, end)
            p.setBrush(fill)
            p.drawRoundedRect(QRectF(x1, track.y(), max(4.0, x2 - x1), 4), 2, 2)
            p.setPen(ink)
            p.drawText(QRectF(bar_right - 4, y, 44, self.ROW), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, f"{round(day['max'])}°")
            if i < len(self.days) - 1:
                divider = QColor(ink)
                divider.setAlpha(18)
                p.setPen(QPen(divider, 1))
                p.drawLine(QPointF(row.left(), y + self.ROW), QPointF(row.right(), y + self.ROW))


class WeatherPage(QWidget):
    def __init__(self, frame_provider, parent=None):
        super().__init__(parent)
        self.setObjectName("Page")
        self.frame_provider = frame_provider
        self.cameras = []
        self.selection: dict | None = preferences.get("weather_location")
        self._token = 0
        self._tasks: list[ForecastTask] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 12)
        root.setSpacing(18)
        title = QLabel("Hava Durumu")
        title.setObjectName("Display")
        title.setFont(font(24, QFont.Weight.DemiBold))
        subtitle = QLabel("Seçtiğiniz konum için anlık durum, saatlik ve 7 günlük tahmin")
        subtitle.setObjectName("Secondary")
        subtitle.setFont(font(12.5))
        heading = QVBoxLayout()
        heading.setSpacing(3)
        heading.addWidget(title)
        heading.addWidget(subtitle)
        root.addLayout(heading)

        body = QHBoxLayout()
        body.setSpacing(20)
        side = QVBoxLayout()
        side.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Şehir veya ilçe ara…")
        self.search.returnPressed.connect(self._search)
        self.search.textChanged.connect(lambda text: self._search_timer.start() if len(text.strip()) >= 2 else None)
        side.addWidget(self.search)
        self.list = QListWidget()
        self.list.setFont(font(12.5, QFont.Weight.Medium, 0.4))
        self.list.setFixedWidth(260)
        self.list.currentItemChanged.connect(lambda item, _prev: self._on_item(item) if item else None)
        side.addWidget(self.list, 1)
        body.addLayout(side)

        scroll = QScrollArea()
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        holder = QWidget()
        holder.setObjectName("Page")
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 6, 0)
        column.setSpacing(16)
        self.hero = HeroCard()
        self.hourly = HourlyStrip()
        self.daily = DailyList()
        self.status = QLabel("")
        self.status.setObjectName("Tertiary")
        self.status.setFont(font(11.5))
        column.addWidget(self.hero)
        column.addWidget(self.hourly)
        column.addWidget(self.daily)
        column.addWidget(self.status)
        column.addStretch(1)
        scroll.setWidget(holder)
        body.addWidget(scroll, 1)
        root.addLayout(body, 1)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(450)
        self._search_timer.timeout.connect(self._search)
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(500)
        self._frame_timer.timeout.connect(self._refresh_frame)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(WEATHER_REFRESH_SECONDS * 1000)
        self._refresh_timer.timeout.connect(self._load)
        self._loaded_key = None

    # ---------- locations ----------
    def set_cameras(self, cameras) -> None:
        self.cameras = list(cameras)
        self._rebuild_list([])

    def _header_item(self, text: str) -> QListWidgetItem:
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        item.setFont(font(10, QFont.Weight.DemiBold, 1.4))
        return item

    def _rebuild_list(self, places: list[dict]) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        selected_item = None
        if places:
            self.list.addItem(self._header_item("ARAMA SONUÇLARI"))
            for place in places:
                item = QListWidgetItem(f"{place['name']}\n{place['region']}")
                item.setData(ROLE, {"type": "place", **place})
                self.list.addItem(item)
        current = self.selection or {}
        if current.get("type") == "place" and not places:
            self.list.addItem(self._header_item("SEÇİLİ KONUM"))
            item = QListWidgetItem(f"{current['name']}\n{current.get('region', '')}")
            item.setData(ROLE, current)
            self.list.addItem(item)
            selected_item = item
        self.list.addItem(self._header_item("KAMERA KONUMLARI"))
        for cam in self.cameras:
            item = QListWidgetItem(cam.name)
            item.setData(ROLE, {"type": "camera", "id": cam.id})
            self.list.addItem(item)
            if current.get("type") == "camera" and current.get("id") == cam.id:
                selected_item = item
        if selected_item is None and current.get("type") != "place":
            selected_item = next(
                (self.list.item(i) for i in range(self.list.count()) if self.list.item(i).data(ROLE)), None
            )
            if selected_item is not None:
                self.selection = selected_item.data(ROLE)
        if selected_item is not None:
            self.list.setCurrentItem(selected_item)
        self.list.blockSignals(False)

    def _on_item(self, item: QListWidgetItem) -> None:
        data = item.data(ROLE) if item else None
        if not data:
            return
        self.selection = data
        preferences.set_value("weather_location", data)
        self._load()

    def _resolve(self):
        sel = self.selection or {}
        if sel.get("type") == "camera":
            cam = next((c for c in self.cameras if c.id == sel.get("id")), None)
            if cam is None:
                return None
            return cam.name, "Kamera konumu · İstanbul", cam.lat, cam.lon, cam.id
        if sel.get("type") == "place":
            return sel["name"].upper(), sel.get("region", ""), sel["lat"], sel["lon"], None
        return None

    # ---------- network ----------
    def _start(self, kind: str, payload) -> int:
        self._token += 1
        task = ForecastTask(self._token, kind, payload)
        task.forecast_ready.connect(self._on_forecast)
        task.places_ready.connect(self._on_places)
        task.failed.connect(self._on_failed)
        task.finished.connect(lambda t=task: self._tasks.remove(t) if t in self._tasks else None)
        self._tasks.append(task)
        task.start()
        return self._token

    def _load(self) -> None:
        resolved = self._resolve()
        if resolved is None:
            return
        name, region, lat, lon, cam_id = resolved
        key = (round(lat, 4), round(lon, 4))
        if key != self._loaded_key:
            self.hero.data = None
            self.hourly.hours = []
            self.daily.days = []
        self.hero.place = name
        self.hero.region = region
        self.hero.message = "Yükleniyor…"
        self.hero.image = self.frame_provider(cam_id) if cam_id else None
        self.status.setText("")
        self._pending_key = key
        self._forecast_token = self._start("forecast", (lat, lon))
        for widget in (self.hero, self.hourly, self.daily):
            widget.update()

    def _search(self) -> None:
        query = self.search.text().strip()
        self._search_timer.stop()
        if len(query) < 2:
            self._rebuild_list([])
            return
        self._search_token = self._start("search", query)

    def _on_forecast(self, token: int, data: dict) -> None:
        if token != getattr(self, "_forecast_token", -1):
            return
        self._loaded_key = self._pending_key
        self.hero.data = data
        self.hourly.hours = data["hours"]
        self.daily.days = data["days"]
        self.status.setText("Veri kaynağı: Open-Meteo · 10 dakikada bir yenilenir")
        for widget in (self.hero, self.hourly, self.daily):
            widget.update()

    def _on_places(self, token: int, places: list) -> None:
        if token != getattr(self, "_search_token", -1):
            return
        self._rebuild_list(places)
        if not places:
            self.status.setText("Aramayla eşleşen konum bulunamadı.")

    def _on_failed(self, token: int, message: str) -> None:
        if token == getattr(self, "_forecast_token", -1):
            self.hero.message = message
            self.hero.update()
        self.status.setText(message)

    def _refresh_frame(self) -> None:
        resolved = self._resolve()
        if resolved and resolved[4]:
            image = self.frame_provider(resolved[4])
            if image is not None and image is not self.hero.image:
                self.hero.image = image
                self.hero.update()

    def showEvent(self, event) -> None:
        self._frame_timer.start()
        self._refresh_timer.start()
        self._load()
        super().showEvent(event)

    def hideEvent(self, event) -> None:
        self._frame_timer.stop()
        self._refresh_timer.stop()
        super().hideEvent(event)
