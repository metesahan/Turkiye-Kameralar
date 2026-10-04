import threading

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from . import APP_ID, APP_VERSION
from .config import WEATHER_REFRESH_SECONDS

API_URL = "https://api.open-meteo.com/v1/forecast"


def describe(code: int) -> tuple[str, str]:
    if code == 0:
        return "clear", "Açık"
    if code in (1, 2):
        return "partly", "Parçalı bulutlu"
    if code == 3:
        return "cloudy", "Kapalı"
    if code in (45, 48):
        return "fog", "Sisli"
    if 51 <= code <= 57:
        return "rain", "Çisenti"
    if 61 <= code <= 67 or 80 <= code <= 82:
        return "rain", "Yağmurlu"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow", "Karlı"
    if code >= 95:
        return "storm", "Fırtınalı"
    return "cloudy", "Bulutlu"


class WeatherWorker(QThread):
    weather_ready = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._cameras: list[tuple[str, float, float]] = []
        self._running = True
        self._session = requests.Session()
        self._session.headers["User-Agent"] = f"{APP_ID}/{APP_VERSION}"

    def set_cameras(self, cameras) -> None:
        with self._lock:
            self._cameras = [(c.id, c.lat, c.lon) for c in cameras]
        self._wake.set()

    def stop(self) -> None:
        self._running = False
        self._wake.set()

    def _fetch(self, lat: float, lon: float):
        response = self._session.get(
            API_URL,
            params={
                "latitude": f"{lat:.4f}",
                "longitude": f"{lon:.4f}",
                "current": "temperature_2m,weather_code,is_day,wind_speed_10m",
                "timezone": "auto",
            },
            timeout=8,
        )
        response.raise_for_status()
        current = response.json().get("current", {})
        code = int(current.get("weather_code", 3))
        kind, label = describe(code)
        return {
            "temperature": float(current.get("temperature_2m", 0.0)),
            "code": code,
            "kind": kind,
            "label": label,
            "is_day": bool(current.get("is_day", 1)),
            "wind": float(current.get("wind_speed_10m", 0.0)),
        }

    def run(self) -> None:
        while self._running:
            self._wake.clear()
            with self._lock:
                cameras = list(self._cameras)
            cache: dict[tuple[float, float], dict] = {}
            for cam_id, lat, lon in cameras:
                if not self._running or self._wake.is_set():
                    break
                key = (round(lat, 2), round(lon, 2))
                if key not in cache:
                    try:
                        cache[key] = self._fetch(lat, lon)
                    except (requests.RequestException, ValueError, TypeError):
                        continue
                self.weather_ready.emit(cam_id, cache[key])
            if self._wake.is_set():
                continue
            self._wake.wait(WEATHER_REFRESH_SECONDS)
        self._session.close()


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_WEEKDAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
_COMPASS = ("K", "KD", "D", "GD", "G", "GB", "B", "KB")


def compass(degrees: float) -> str:
    return _COMPASS[int((degrees % 360) / 45 + 0.5) % 8]


def fetch_forecast(session: requests.Session, lat: float, lon: float) -> dict:
    from datetime import datetime

    response = session.get(
        API_URL,
        params={
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,is_day,"
            "wind_speed_10m,wind_direction_10m,precipitation,pressure_msl",
            "hourly": "temperature_2m,weather_code,is_day,precipitation_probability",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max",
            "forecast_days": 7,
            "timezone": "auto",
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    current = data.get("current", {})
    kind, label = describe(int(current.get("weather_code", 3)))
    now_key = str(current.get("time", ""))[:13]

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    start = next((i for i, t in enumerate(times) if t[:13] >= now_key), 0)
    hours = []
    for i in range(start, min(start + 24, len(times))):
        h_kind, _ = describe(int(hourly["weather_code"][i]))
        hours.append(
            {
                "label": "Şimdi" if i == start else times[i][11:16],
                "temperature": float(hourly["temperature_2m"][i]),
                "kind": h_kind,
                "is_day": bool(hourly["is_day"][i]),
                "rain": hourly.get("precipitation_probability", [None] * len(times))[i],
            }
        )

    daily = data.get("daily", {})
    days = []
    for i, day in enumerate(daily.get("time", [])):
        d_kind, d_label = describe(int(daily["weather_code"][i]))
        weekday = "Bugün" if i == 0 else _WEEKDAYS[datetime.fromisoformat(day).weekday()]
        days.append(
            {
                "label": weekday,
                "kind": d_kind,
                "description": d_label,
                "min": float(daily["temperature_2m_min"][i]),
                "max": float(daily["temperature_2m_max"][i]),
                "rain": daily.get("precipitation_probability_max", [None] * 7)[i],
                "sunrise": str(daily.get("sunrise", [""] * 7)[i])[11:16],
                "sunset": str(daily.get("sunset", [""] * 7)[i])[11:16],
            }
        )

    return {
        "temperature": float(current.get("temperature_2m", 0.0)),
        "feels_like": float(current.get("apparent_temperature", 0.0)),
        "humidity": float(current.get("relative_humidity_2m", 0.0)),
        "wind": float(current.get("wind_speed_10m", 0.0)),
        "wind_direction": compass(float(current.get("wind_direction_10m", 0.0))),
        "precipitation": float(current.get("precipitation", 0.0)),
        "pressure": float(current.get("pressure_msl", 0.0)),
        "kind": kind,
        "label": label,
        "is_day": bool(current.get("is_day", 1)),
        "hours": hours,
        "days": days,
    }


def search_places(session: requests.Session, query: str) -> list[dict]:
    response = session.get(
        GEOCODING_URL,
        params={"name": query, "count": 8, "language": "tr", "format": "json"},
        timeout=8,
    )
    response.raise_for_status()
    places = []
    for item in response.json().get("results", []) or []:
        region = ", ".join(x for x in (item.get("admin1"), item.get("country")) if x)
        places.append(
            {
                "local": item.get("country_code") == "TR",
                "name": item.get("name", ""),
                "region": region,
                "lat": float(item["latitude"]),
                "lon": float(item["longitude"]),
            }
        )
    places.sort(key=lambda place: not place.pop("local"))
    return places


class ForecastTask(QThread):
    forecast_ready = pyqtSignal(int, object)
    places_ready = pyqtSignal(int, object)
    failed = pyqtSignal(int, str)

    def __init__(self, token: int, kind: str, payload, parent=None):
        super().__init__(parent)
        self.token = token
        self.kind = kind
        self.payload = payload

    def run(self) -> None:
        session = requests.Session()
        session.headers["User-Agent"] = f"{APP_ID}/{APP_VERSION}"
        try:
            for attempt in range(3):
                try:
                    if self.kind == "forecast":
                        lat, lon = self.payload
                        self.forecast_ready.emit(self.token, fetch_forecast(session, lat, lon))
                    else:
                        self.places_ready.emit(self.token, search_places(session, self.payload))
                    return
                except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
                    if attempt == 2:
                        self.failed.emit(self.token, "Hava durumu verisi alınamadı. Bağlantınızı kontrol edin.")
                    else:
                        self.msleep(800)
        finally:
            session.close()
