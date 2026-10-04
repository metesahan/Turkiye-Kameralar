import re
import time

import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from .config import FRAME_SKIP, GRID_DISPLAY_FPS, GRID_DISPLAY_WIDTH, STREAM_TIMEOUT_MS

cv2.setNumThreads(2)

_CHUNKLIST = re.compile(r"chunklist_[^/]*\.m3u8$")


def candidate_urls(url: str) -> list[str]:
    urls = [url]
    if _CHUNKLIST.search(url):
        urls.append(_CHUNKLIST.sub("playlist.m3u8", url))
    return urls


def bgr_to_qimage(frame, max_width: int) -> QImage:
    h, w = frame.shape[:2]
    if max_width and w > max_width:
        nh = max(1, int(round(h * max_width / w)))
        frame = cv2.resize(frame, (max_width, nh), interpolation=cv2.INTER_AREA)
        h, w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


class StreamWorker(QThread):
    frame_ready = pyqtSignal(str, object, float)
    status_changed = pyqtSignal(str, str)

    def __init__(self, cam_id: str, url: str, detector=None, parent=None):
        super().__init__(parent)
        self.cam_id = cam_id
        self.url = url
        self.detector = detector
        self.display_width = GRID_DISPLAY_WIDTH
        self.display_fps = GRID_DISPLAY_FPS
        self.detect_enabled = True
        self.focused = False
        self._running = True
        self._status = ""

    def stop(self) -> None:
        self._running = False

    def configure(self, display_width: int, display_fps: int, focused: bool = False) -> None:
        self.display_width = int(display_width)
        self.display_fps = max(1, int(display_fps))
        self.focused = focused

    def _set_status(self, status: str) -> None:
        if status != self._status:
            self._status = status
            self.status_changed.emit(self.cam_id, status)

    def _sleep(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while self._running and time.monotonic() < end:
            time.sleep(min(0.1, max(0.0, end - time.monotonic())))

    def _open(self):
        for url in candidate_urls(self.url):
            if not self._running:
                return None
            cap = None
            try:
                params = [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, STREAM_TIMEOUT_MS,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC, STREAM_TIMEOUT_MS,
                    cv2.CAP_PROP_N_THREADS, 2,
                ]
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)
            except (cv2.error, TypeError, AttributeError):
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if cap is not None and cap.isOpened():
                return cap
            if cap is not None:
                cap.release()
        return None

    def run(self) -> None:
        backoff = 2.0
        while self._running:
            self._set_status("connecting")
            cap = self._open()
            if cap is None:
                self._set_status("offline")
                self._sleep(backoff)
                backoff = min(backoff * 1.6, 30.0)
                continue

            fps = cap.get(cv2.CAP_PROP_FPS)
            if not fps or fps < 1 or fps > 120:
                fps = 25.0
            interval = 1.0 / fps
            origin = time.monotonic()
            index = 0
            failures = 0
            last_emit = 0.0
            live = False

            while self._running:
                detector = self.detector
                upcoming = index + 1
                want_detect = (
                    detector is not None
                    and detector.ready
                    and self.detect_enabled
                    and (self.focused or upcoming % FRAME_SKIP == 0)
                )
                want_display = (
                    not live
                    or self.focused
                    or time.monotonic() - last_emit >= 1.0 / self.display_fps - interval / 2
                )
                if want_detect or want_display:
                    ok, frame = cap.read()
                else:
                    ok, frame = cap.grab(), None
                if not ok:
                    failures += 1
                    if failures > 25:
                        break
                    time.sleep(0.04)
                    continue
                failures = 0
                if not live:
                    live = True
                    backoff = 2.0
                    self._set_status("live")
                    origin = time.monotonic()
                    index = 0

                index += 1
                target = origin + index * interval
                now = time.monotonic()
                if target > now:
                    time.sleep(min(target - now, 0.5))
                elif now - target > 2.0:
                    origin = now
                    index = 0

                if frame is None:
                    continue
                stamp = time.monotonic()
                if want_detect:
                    detector.submit(self.cam_id, frame, stamp)
                if want_display:
                    last_emit = stamp
                    self.frame_ready.emit(self.cam_id, bgr_to_qimage(frame, self.display_width), stamp)

            cap.release()
            if self._running:
                self._set_status("offline")
                self._sleep(backoff)
                backoff = min(backoff * 1.6, 30.0)
