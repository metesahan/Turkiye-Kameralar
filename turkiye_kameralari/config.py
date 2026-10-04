import os
import sys
from pathlib import Path

from . import APP_ID

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform.startswith("win")
IS_FROZEN = bool(getattr(sys, "frozen", False))

FRAME_SKIP = 3
GRID_DISPLAY_WIDTH = 640
GRID_DISPLAY_FPS = 15
FOCUS_DISPLAY_FPS = 30
BACKGROUND_DISPLAY_FPS = 4
DETECTION_CONFIDENCE = 0.20
COUNT_CONFIDENCE = 0.30
TRACK_ACTIVATION = 0.35
TRACK_HIGH_CONFIDENCE = 0.45
GRID_IMGSZ_GPU = 960
FOCUS_IMGSZ_GPU = 1280
GRID_IMGSZ_CPU = 640
FOCUS_IMGSZ_CPU = 960
BACKGROUND_DETECT_INTERVAL = 2.0
DETECTION_STALE_SECONDS = 1.25
WEATHER_REFRESH_SECONDS = 600
STREAM_TIMEOUT_MS = 10000
SPLASH_MIN_SECONDS = 1.6
SPLASH_MAX_SECONDS = 15.0
MODEL_NAME = "yolo11s.pt"

COCO_CATEGORIES = {
    0: "person",
    2: "vehicle",
    3: "vehicle",
    5: "vehicle",
    7: "vehicle",
    8: "boat",
    15: "animal",
    16: "animal",
}
DETECTION_CLASSES = sorted(COCO_CATEGORIES.keys())
CLASS_LABELS = {
    0: "İNSAN",
    2: "ARAÇ",
    3: "MOTOSİKLET",
    5: "OTOBÜS",
    7: "KAMYON",
    8: "TEKNE",
    15: "KEDİ",
    16: "KÖPEK",
}
CATEGORY_ORDER = ("person", "vehicle", "boat", "animal")
CATEGORY_LABELS = {
    "person": "İNSAN",
    "vehicle": "ARAÇ",
    "boat": "GEMİ",
    "animal": "HAYVAN",
}

DEFAULT_LATITUDE = 41.0082
DEFAULT_LONGITUDE = 28.9784

DEFAULT_CAMERAS = [
    ("ANADOLU HİSARI", "https://kamerayayin.ibb.istanbul/turistikcam/anadoluhisari.stream/playlist.m3u8", 41.0823, 29.0669),
    ("BEYAZIT KULESİ", "https://kamerayayin.ibb.istanbul/turistikcam/beyazitkulesi2.stream/chunklist_w1670320938.m3u8", 41.0122, 28.9636),
    ("BEYAZIT MEYDANI", "https://kamerayayin.ibb.istanbul/turistikcam/beyazitmeydan.stream/chunklist_w325056687.m3u8", 41.0105, 28.9640),
    ("BÜYÜK ÇAMLICA", "https://kamerayayin.ibb.istanbul/turistikcam/buyukcamlica.stream/chunklist_w1610757817.m3u8", 41.0272, 29.0686),
    ("EMİNÖNÜ", "https://kamerayayin.ibb.istanbul/turistikcam/eminonu.stream/playlist.m3u8", 41.0171, 28.9706),
    ("EMİRGAN", "https://kamerayayin.ibb.istanbul/turistikcam/emirgan.stream/playlist.m3u8", 41.1086, 29.0553),
    ("EYÜP SULTAN", "https://kamerayayin.ibb.istanbul/turistikcam/eyupsultan.stream/chunklist_w965134970.m3u8", 41.0479, 28.9339),
    ("HİDİV KASRI", "https://kamerayayin.ibb.istanbul/turistikcam/hidivkasri.stream/chunklist_w891731548.m3u8", 41.1092, 29.0647),
    ("KIZ KULESİ", "https://kamerayayin.ibb.istanbul/turistikcam/kizkulesi.stream/playlist.m3u8", 41.0211, 29.0041),
    ("PIERRE LOTI", "https://kamerayayin.ibb.istanbul/turistikcam/pierreloti.stream/playlist.m3u8", 41.0537, 28.9336),
    ("SALACAK", "https://kamerayayin.ibb.istanbul/turistikcam/salacak.stream/playlist.m3u8", 41.0228, 29.0083),
    ("SARAÇHANE", "https://kamerayayin.ibb.istanbul/turistikcam/sarachane.stream/playlist.m3u8", 41.0145, 28.9550),
    ("SULTANAHMET", "https://kamerayayin.ibb.istanbul/turistikcam/sultanahmet2.stream/playlist.m3u8", 41.0054, 28.9768),
    ("TAKSİM MEYDAN", "https://kamerayayin.ibb.istanbul/turistikcam/taksim.stream/playlist.m3u8", 41.0370, 28.9850),
    ("ULUS PARKI", "https://kamerayayin.ibb.istanbul/turistikcam/ulusparki.stream/playlist.m3u8", 41.0623, 29.0360),
]


def _user_data_dir() -> Path:
    home = Path.home()
    if IS_MAC:
        return home / "Library" / "Application Support" / APP_ID
    if IS_WINDOWS:
        base = os.environ.get("APPDATA")
        return (Path(base) if base else home / "AppData" / "Roaming") / APP_ID
    base = os.environ.get("XDG_DATA_HOME")
    return (Path(base) if base else home / ".local" / "share") / APP_ID


def data_dir() -> Path:
    if IS_FROZEN:
        path = _user_data_dir()
    else:
        path = Path(__file__).resolve().parent.parent
    path.mkdir(parents=True, exist_ok=True)
    return path


def bundle_dir() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    if IS_FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def tracker_model_path() -> Path | None:
    for base in (bundle_dir() / "models", data_dir() / "models"):
        candidate = base / "vittrack.onnx"
        if candidate.exists():
            return candidate
    return None


def cameras_file() -> Path:
    return data_dir() / "cameras.json"


def model_path() -> Path:
    bundled = bundle_dir() / "models" / MODEL_NAME
    if bundled.exists():
        return bundled
    folder = data_dir() / "models"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / MODEL_NAME


def prepare_environment() -> None:
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rw_timeout;10000000")
    os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")
    os.environ.setdefault("YOLO_VERBOSE", "False")
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
