from dataclasses import dataclass

from PyQt6.QtGui import QColor, QFont

from .config import IS_MAC, IS_WINDOWS


@dataclass(frozen=True)
class Palette:
    dark: bool
    window: str
    window_alt: str
    sidebar: str
    surface: str
    surface_hover: str
    surface_pressed: str
    border: str
    border_strong: str
    text: str
    text_secondary: str
    text_tertiary: str
    selection: str
    tile_border: QColor
    tile_border_hover: QColor
    tile_empty: QColor
    backdrop_tint: QColor
    ink: QColor
    card: QColor
    card_border: QColor


DARK = Palette(
    dark=True,
    window="#111113",
    window_alt="#1b1b1e",
    sidebar="#161619",
    surface="rgba(255, 255, 255, 0.05)",
    surface_hover="rgba(255, 255, 255, 0.08)",
    surface_pressed="rgba(255, 255, 255, 0.12)",
    border="rgba(255, 255, 255, 0.08)",
    border_strong="rgba(255, 255, 255, 0.18)",
    text="#ededf0",
    text_secondary="rgba(235, 235, 245, 0.60)",
    text_tertiary="rgba(235, 235, 245, 0.34)",
    selection="rgba(255, 255, 255, 0.09)",
    tile_border=QColor(255, 255, 255, 20),
    tile_border_hover=QColor(255, 255, 255, 74),
    tile_empty=QColor(26, 26, 29),
    backdrop_tint=QColor(14, 14, 16, 205),
    ink=QColor(237, 237, 240),
    card=QColor(255, 255, 255, 10),
    card_border=QColor(255, 255, 255, 20),
)

LIGHT = Palette(
    dark=False,
    window="#f5f5f7",
    window_alt="#ffffff",
    sidebar="#ececef",
    surface="rgba(0, 0, 0, 0.04)",
    surface_hover="rgba(0, 0, 0, 0.065)",
    surface_pressed="rgba(0, 0, 0, 0.10)",
    border="rgba(0, 0, 0, 0.08)",
    border_strong="rgba(0, 0, 0, 0.18)",
    text="#1d1d1f",
    text_secondary="rgba(60, 60, 67, 0.66)",
    text_tertiary="rgba(60, 60, 67, 0.40)",
    selection="rgba(0, 0, 0, 0.065)",
    tile_border=QColor(0, 0, 0, 18),
    tile_border_hover=QColor(0, 0, 0, 64),
    tile_empty=QColor(222, 222, 226),
    backdrop_tint=QColor(245, 245, 247, 195),
    ink=QColor(29, 29, 31),
    card=QColor(255, 255, 255, 200),
    card_border=QColor(0, 0, 0, 16),
)


def current_palette() -> Palette:
    from . import preferences

    return LIGHT if preferences.get("theme") == "light" else DARK


def ui_font_family() -> str:
    if IS_MAC:
        return ".AppleSystemUIFont"
    if IS_WINDOWS:
        return "Segoe UI Variable Text"
    return "Inter"


def font(px: float, weight: QFont.Weight = QFont.Weight.Normal, spacing: float = 0.0) -> QFont:
    f = QFont(ui_font_family())
    f.setPixelSize(max(1, round(px)))
    f.setWeight(weight)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    if spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return f


def stylesheet(p: Palette) -> str:
    return f"""
    * {{
        color: {p.text};
        outline: none;
    }}
    QMainWindow, QWidget#Root, QDialog {{
        background: {p.window};
    }}
    QWidget#Sidebar {{
        background: {p.sidebar};
        border-right: 1px solid {p.border};
    }}
    QLabel#Display {{
        color: {p.text};
    }}
    QWidget#Page, QWidget#GridCanvas, QScrollArea, QScrollArea > QWidget > QWidget {{
        background: transparent;
    }}
    QLabel {{
        background: transparent;
    }}
    QLabel#Footer {{
        color: {p.text_tertiary};
    }}
    QLabel#Secondary {{
        color: {p.text_secondary};
    }}
    QLabel#Tertiary, QLabel#FieldLabel {{
        color: {p.text_tertiary};
    }}
    QLabel#Error {{
        color: {"rgba(255, 180, 170, 0.9)" if p.dark else "rgba(170, 40, 30, 0.85)"};
    }}
    QLabel#Chip {{
        color: {p.text_secondary};
        border: 1px solid {p.border};
        border-radius: 10px;
        padding: 3px 10px;
        background: {p.surface};
    }}
    QPushButton {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 6px 14px;
        min-height: 18px;
    }}
    QPushButton:hover {{
        background: {p.surface_hover};
        border-color: {p.border_strong};
    }}
    QPushButton:pressed {{
        background: {p.surface_pressed};
    }}
    QPushButton:disabled {{
        color: {p.text_tertiary};
    }}
    QPushButton#Primary {{
        background: {p.text};
        color: {p.window};
        border-color: {p.text};
    }}
    QPushButton#Primary:hover {{
        background: {p.text_secondary};
    }}
    QPushButton#Ghost {{
        background: transparent;
        border-color: transparent;
    }}
    QPushButton#Ghost:hover {{
        background: {p.surface};
        border-color: {p.border};
    }}
    QLineEdit, QDoubleSpinBox {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 8px;
        padding: 7px 10px;
        selection-background-color: {p.border_strong};
    }}
    QLineEdit:focus, QDoubleSpinBox:focus {{
        border-color: {p.border_strong};
    }}
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        width: 0px;
        border: none;
    }}
    QListWidget {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 10px;
        padding: 4px;
    }}
    QListWidget::item {{
        padding: 8px 10px;
        border-radius: 6px;
    }}
    QListWidget::item:hover {{
        background: {p.surface};
    }}
    QListWidget::item:selected {{
        background: {p.selection};
        color: {p.text};
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p.border_strong};
        border-radius: 3px;
        min-height: 40px;
        margin: 0 2px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
        background: none;
        height: 0;
        width: 0;
    }}
    QScrollBar:horizontal {{
        height: 0;
    }}
    QToolTip {{
        background: {p.window_alt};
        color: {p.text};
        border: 1px solid {p.border};
        padding: 4px 8px;
    }}
    """


def qcolor(css: str) -> QColor:
    css = css.strip()
    if css.startswith("rgba"):
        r, g, b, a = (part.strip() for part in css[css.index("(") + 1 : css.index(")")].split(","))
        return QColor(int(r), int(g), int(b), round(float(a) * 255))
    return QColor(css)
