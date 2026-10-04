import copy

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from .config import DEFAULT_LATITUDE, DEFAULT_LONGITUDE, cameras_file
from .store import Camera, default_cameras, tr_upper
from .theme import font
from .widgets import ConfirmDialog, FramedDialog


def _spacer() -> QSpacerItem:
    return QSpacerItem(0, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)


def _field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    label.setFont(font(10, QFont.Weight.Medium, 1.2))
    return label


class SettingsDialog(FramedDialog):
    def __init__(self, cameras: list[Camera], parent=None):
        super().__init__("Ayarlar", parent)
        self.cameras = [copy.copy(c) for c in cameras]
        self.result_cameras: list[Camera] | None = None
        self._loading = False
        self.resize(820, 560)
        self.setMinimumSize(700, 480)

        root = QVBoxLayout(self.body)
        root.setContentsMargins(28, 24, 28, 10)
        root.setSpacing(16)

        heading = QVBoxLayout()
        heading.setSpacing(3)
        title = QLabel("Ayarlar")
        title.setFont(font(20, QFont.Weight.DemiBold))
        subtitle = QLabel("Kamera yayınlarını ekleyin, düzenleyin veya kaldırın.")
        subtitle.setObjectName("Secondary")
        subtitle.setFont(font(12.5))
        heading.addWidget(title)
        heading.addWidget(subtitle)
        root.addLayout(heading)

        content = QHBoxLayout()
        content.setSpacing(20)

        left = QVBoxLayout()
        left.setSpacing(8)
        self.list = QListWidget()
        self.list.setFont(font(12.5, QFont.Weight.Medium, 0.6))
        self.list.setMinimumWidth(250)
        self.list.currentRowChanged.connect(self._on_select)
        left.addWidget(self.list, 1)
        list_buttons = QHBoxLayout()
        add = QPushButton("Yeni Kamera")
        add.clicked.connect(self._add)
        self.remove = QPushButton("Sil")
        self.remove.clicked.connect(self._remove)
        list_buttons.addWidget(add)
        list_buttons.addWidget(self.remove)
        list_buttons.addStretch(1)
        left.addLayout(list_buttons)
        content.addLayout(left, 4)

        form_host = QWidget()
        form_host.setObjectName("Page")
        form = QGridLayout(form_host)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(6)
        self.name = QLineEdit()
        self.name.setPlaceholderText("ÖRN. GALATA KULESİ")
        self.name.textEdited.connect(self._on_edit)
        self.name.editingFinished.connect(self._normalize_name)
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://…/playlist.m3u8")
        self.url.textEdited.connect(self._on_edit)
        self.lat = QDoubleSpinBox()
        self.lat.setRange(-90.0, 90.0)
        self.lat.setDecimals(4)
        self.lat.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.lat.valueChanged.connect(self._on_edit)
        self.lon = QDoubleSpinBox()
        self.lon.setRange(-180.0, 180.0)
        self.lon.setDecimals(4)
        self.lon.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.lon.valueChanged.connect(self._on_edit)

        form.addWidget(_field_label("KAMERA ADI"), 0, 0, 1, 2)
        form.addWidget(self.name, 1, 0, 1, 2)
        form.addItem(_spacer(), 2, 0)
        form.addWidget(_field_label("YAYIN ADRESİ (M3U8)"), 3, 0, 1, 2)
        form.addWidget(self.url, 4, 0, 1, 2)
        form.addItem(_spacer(), 5, 0)
        form.addWidget(_field_label("ENLEM"), 6, 0)
        form.addWidget(_field_label("BOYLAM"), 6, 1)
        form.addWidget(self.lat, 7, 0)
        form.addWidget(self.lon, 7, 1)
        hint = QLabel("Konum, Open-Meteo hava durumu bilgisi için kullanılır.")
        hint.setObjectName("Tertiary")
        hint.setFont(font(11.5))
        form.addWidget(hint, 8, 0, 1, 2)
        self.error = QLabel("")
        self.error.setObjectName("Error")
        self.error.setFont(font(12))
        self.error.setWordWrap(True)
        form.addWidget(self.error, 9, 0, 1, 2)
        form.setRowStretch(10, 1)
        self.form_host = form_host
        content.addWidget(form_host, 6)
        root.addLayout(content, 1)

        path_label = QLabel(str(cameras_file()))
        path_label.setObjectName("Tertiary")
        path_label.setFont(font(10.5))
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        bottom = QHBoxLayout()
        reset = QPushButton("Varsayılanlara Dön")
        reset.setObjectName("Ghost")
        reset.clicked.connect(self._reset_defaults)
        bottom.addWidget(reset)
        bottom.addWidget(path_label, 1)
        cancel = QPushButton("Vazgeç")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Kaydet")
        save.setObjectName("Primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        bottom.addWidget(cancel)
        bottom.addWidget(save)
        root.addLayout(bottom)

        self._populate(0)

    def _populate(self, row: int) -> None:
        self.list.blockSignals(True)
        self.list.clear()
        for cam in self.cameras:
            self.list.addItem(QListWidgetItem(cam.name or "ADSIZ KAMERA"))
        self.list.blockSignals(False)
        if self.cameras:
            self.list.setCurrentRow(max(0, min(row, len(self.cameras) - 1)))
        self._on_select(self.list.currentRow())

    def _current(self) -> Camera | None:
        row = self.list.currentRow()
        return self.cameras[row] if 0 <= row < len(self.cameras) else None

    def _on_select(self, row: int) -> None:
        cam = self._current()
        enabled = cam is not None
        self.form_host.setEnabled(enabled)
        self.remove.setEnabled(enabled)
        self._loading = True
        self.name.setText(cam.name if cam else "")
        self.url.setText(cam.url if cam else "")
        self.lat.setValue(cam.lat if cam else DEFAULT_LATITUDE)
        self.lon.setValue(cam.lon if cam else DEFAULT_LONGITUDE)
        self._loading = False
        self.error.setText("")

    def _on_edit(self, *_args) -> None:
        if self._loading:
            return
        cam = self._current()
        if cam is None:
            return
        cam.name = self.name.text()
        cam.url = self.url.text().strip()
        cam.lat = self.lat.value()
        cam.lon = self.lon.value()
        item = self.list.currentItem()
        if item is not None:
            item.setText(tr_upper(cam.name) or "ADSIZ KAMERA")
        self.error.setText("")

    def _normalize_name(self) -> None:
        upper = tr_upper(self.name.text())
        if upper != self.name.text():
            position = self.name.cursorPosition()
            self.name.setText(upper)
            self.name.setCursorPosition(min(position, len(upper)))
            self._on_edit()

    def _add(self) -> None:
        self.cameras.append(Camera(name="YENİ KAMERA", url="", lat=DEFAULT_LATITUDE, lon=DEFAULT_LONGITUDE))
        self._populate(len(self.cameras) - 1)
        self.name.setFocus()
        self.name.selectAll()

    def _remove(self) -> None:
        cam = self._current()
        if cam is None:
            return
        dialog = ConfirmDialog(
            "Kamerayı sil",
            f"“{tr_upper(cam.name)}” listeden kaldırılacak. Bu işlem kaydedildiğinde kalıcı olur.",
            "Sil",
            self,
        )
        if dialog.exec():
            row = self.list.currentRow()
            del self.cameras[row]
            self._populate(row)

    def _reset_defaults(self) -> None:
        dialog = ConfirmDialog(
            "Varsayılanlara dön",
            "Kamera listesi ilk kurulumdaki 15 yayına geri döndürülecek.",
            "Geri Döndür",
            self,
        )
        if dialog.exec():
            self.cameras = default_cameras()
            self._populate(0)

    def _validate(self) -> str | None:
        for index, cam in enumerate(self.cameras):
            label = tr_upper(cam.name) or f"{index + 1}. kamera"
            if not tr_upper(cam.name):
                return f"{index + 1}. kameranın adı boş olamaz."
            url = cam.url.strip()
            if not url.lower().startswith(("http://", "https://", "rtsp://", "rtmp://")):
                return f"{label}: geçerli bir yayın adresi girin (http/https)."
        return None

    def _save(self) -> None:
        self._normalize_name()
        problem = self._validate()
        if problem:
            self.error.setText(problem)
            return
        self.result_cameras = [c.normalized() for c in self.cameras]
        self.accept()
