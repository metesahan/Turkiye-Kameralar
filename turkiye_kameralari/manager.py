import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .config import (
    BACKGROUND_DISPLAY_FPS,
    FOCUS_DISPLAY_FPS,
    GRID_DISPLAY_FPS,
    GRID_DISPLAY_WIDTH,
)
from .detection import DetectionEngine
from .store import Camera, load_cameras, save_cameras
from .streaming import StreamWorker
from .weather import WeatherWorker


class CameraManager(QObject):
    frame_ready = pyqtSignal(str, object, float)
    detections_ready = pyqtSignal(str, object)
    status_changed = pyqtSignal(str, str)
    weather_ready = pyqtSignal(str, object)
    engine_state = pyqtSignal(str, str)
    cameras_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cameras: list[Camera] = load_cameras()
        self.workers: dict[str, StreamWorker] = {}
        self.statuses: dict[str, str] = {}
        self.weather: dict[str, dict] = {}
        self.engine_status = ("loading", "Başlatılıyor")
        self.focus_id: str | None = None
        self._retired: list = []

        self.detector = DetectionEngine()
        self.detector.detections_ready.connect(self.detections_ready)
        self.detector.state_changed.connect(self._on_engine_state)

        self.weather_worker = WeatherWorker()
        self.weather_worker.weather_ready.connect(self._on_weather)

    def camera(self, cam_id: str) -> Camera | None:
        return next((c for c in self.cameras if c.id == cam_id), None)

    def start(self) -> None:
        self.detector.start()
        self.weather_worker.set_cameras(self.cameras)
        self.weather_worker.start()
        for index, cam in enumerate(self.cameras):
            QTimer.singleShot(120 * index, lambda c=cam: self._spawn(c))

    def _spawn(self, cam: Camera) -> None:
        if cam.id in self.workers or self.camera(cam.id) is None:
            return
        worker = StreamWorker(cam.id, cam.url, self.detector)
        worker.frame_ready.connect(self.frame_ready)
        worker.status_changed.connect(self._on_status)
        self._apply_profile(worker)
        self.workers[cam.id] = worker
        self.statuses[cam.id] = "connecting"
        worker.start()

    def _retire(self, cam_id: str) -> None:
        worker = self.workers.pop(cam_id, None)
        self.detector.forget(cam_id)
        if worker is None:
            return
        try:
            worker.frame_ready.disconnect()
            worker.status_changed.disconnect()
        except TypeError:
            pass
        worker.stop()
        self._retired.append(worker)
        worker.finished.connect(lambda w=worker: self._retired.remove(w) if w in self._retired else None)

    def _apply_profile(self, worker: StreamWorker) -> None:
        if self.focus_id is None:
            worker.configure(GRID_DISPLAY_WIDTH, GRID_DISPLAY_FPS)
        elif worker.cam_id == self.focus_id:
            worker.configure(0, FOCUS_DISPLAY_FPS, focused=True)
        else:
            worker.configure(GRID_DISPLAY_WIDTH, BACKGROUND_DISPLAY_FPS)

    def set_focus(self, cam_id: str | None) -> None:
        self.focus_id = cam_id
        self.detector.set_focus(cam_id)
        for worker in self.workers.values():
            self._apply_profile(worker)

    def _on_status(self, cam_id: str, status: str) -> None:
        self.statuses[cam_id] = status
        self.status_changed.emit(cam_id, status)

    def _on_weather(self, cam_id: str, data: dict) -> None:
        self.weather[cam_id] = data
        self.weather_ready.emit(cam_id, data)

    def _on_engine_state(self, state: str, info: str) -> None:
        self.engine_status = (state, info)
        self.engine_state.emit(state, info)

    def apply_cameras(self, cameras: list[Camera]) -> None:
        cameras = [c.normalized() for c in cameras]
        previous = {c.id: c for c in self.cameras}
        incoming = {c.id for c in cameras}
        for cam_id in list(previous):
            if cam_id not in incoming:
                self._retire(cam_id)
                self.statuses.pop(cam_id, None)
                self.weather.pop(cam_id, None)
        self.cameras = cameras
        save_cameras(cameras)
        for cam in cameras:
            old = previous.get(cam.id)
            if old is not None and old.url != cam.url:
                self._retire(cam.id)
            if old is not None and (old.lat, old.lon) != (cam.lat, cam.lon):
                self.weather.pop(cam.id, None)
            if cam.id not in self.workers:
                self._spawn(cam)
        if self.focus_id and self.focus_id not in incoming:
            self.set_focus(None)
        self.weather_worker.set_cameras(cameras)
        self.cameras_changed.emit(list(cameras))

    def shutdown(self, timeout: float = 3.0) -> bool:
        threads = list(self.workers.values()) + list(self._retired) + [self.detector, self.weather_worker]
        for worker in self.workers.values():
            worker.stop()
        self.detector.stop()
        self.weather_worker.stop()
        deadline = time.monotonic() + timeout
        clean = True
        for thread in threads:
            remaining = max(0.0, deadline - time.monotonic())
            if not thread.wait(int(remaining * 1000)):
                clean = False
        return clean
