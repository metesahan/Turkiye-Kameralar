import json
import re
import shutil
import time
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field

from .config import DEFAULT_CAMERAS, DEFAULT_LATITUDE, DEFAULT_LONGITUDE, cameras_file


def tr_upper(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper().strip()


def _slug(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.replace("ı", "i").replace("İ", "I"))
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-") or uuid.uuid4().hex[:8]


@dataclass
class Camera:
    name: str
    url: str
    lat: float = DEFAULT_LATITUDE
    lon: float = DEFAULT_LONGITUDE
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])

    def normalized(self) -> "Camera":
        return Camera(
            name=tr_upper(self.name),
            url=self.url.strip(),
            lat=float(self.lat),
            lon=float(self.lon),
            id=self.id,
        )


def default_cameras() -> list[Camera]:
    return [Camera(name=n, url=u, lat=la, lon=lo, id=_slug(n)) for n, u, la, lo in DEFAULT_CAMERAS]


def save_cameras(cameras: list[Camera]) -> None:
    path = cameras_file()
    payload = {"version": 1, "cameras": [asdict(c.normalized()) for c in cameras]}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _parse(raw) -> list[Camera]:
    items = raw.get("cameras", []) if isinstance(raw, dict) else raw
    cameras: list[Camera] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or not item.get("url") or not item.get("name"):
            continue
        cam_id = str(item.get("id") or _slug(item["name"]))
        while cam_id in seen:
            cam_id = f"{cam_id}-{uuid.uuid4().hex[:4]}"
        seen.add(cam_id)
        try:
            lat = float(item.get("lat", DEFAULT_LATITUDE))
            lon = float(item.get("lon", DEFAULT_LONGITUDE))
        except (TypeError, ValueError):
            lat, lon = DEFAULT_LATITUDE, DEFAULT_LONGITUDE
        cameras.append(Camera(name=str(item["name"]), url=str(item["url"]), lat=lat, lon=lon, id=cam_id).normalized())
    return cameras


def load_cameras() -> list[Camera]:
    path = cameras_file()
    if not path.exists():
        cameras = default_cameras()
        save_cameras(cameras)
        return cameras
    try:
        cameras = _parse(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        backup = path.with_name(f"cameras.corrupt-{int(time.time())}.json")
        shutil.copyfile(path, backup)
        cameras = default_cameras()
        save_cameras(cameras)
    return cameras
