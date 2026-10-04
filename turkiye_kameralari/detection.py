import threading
import time
import traceback
from collections import deque

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from .config import (
    BACKGROUND_DETECT_INTERVAL,
    COCO_CATEGORIES,
    COUNT_CONFIDENCE,
    DETECTION_CLASSES,
    DETECTION_CONFIDENCE,
    TRACK_ACTIVATION,
    TRACK_HIGH_CONFIDENCE,
    data_dir,
    model_path,
    tracker_model_path,
)


def iou_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    x1 = np.maximum(a[:, None, 0], b[None, :, 0])
    y1 = np.maximum(a[:, None, 1], b[None, :, 1])
    x2 = np.minimum(a[:, None, 2], b[None, :, 2])
    y2 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    area_a = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    area_b = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(area_a[:, None] + area_b[None, :] - inter, 1e-6)


def match_one_to_one(a: np.ndarray, b: np.ndarray, threshold: float) -> list[tuple[int, int]]:
    scores = iou_matrix(a, b)
    pairs: list[tuple[int, int]] = []
    used_a: set[int] = set()
    used_b: set[int] = set()
    for flat in np.argsort(-scores, axis=None):
        i, j = (int(v) for v in np.unravel_index(flat, scores.shape))
        if scores[i, j] <= threshold:
            break
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        pairs.append((i, j))
    return pairs


class IoUTracker:
    def __init__(self, max_age: float = 1.5, threshold: float = 0.3):
        self.max_age = max_age
        self.threshold = threshold
        self.tracks: dict[int, tuple[np.ndarray, int, float]] = {}
        self.next_id = 1

    def update(self, boxes: np.ndarray, classes: np.ndarray, now: float) -> np.ndarray:
        self.tracks = {k: v for k, v in self.tracks.items() if now - v[2] <= self.max_age}
        ids = np.zeros(len(boxes), dtype=int)
        track_ids = list(self.tracks.keys())
        if track_ids and len(boxes):
            previous = np.array([self.tracks[t][0] for t in track_ids])
            for i, j in match_one_to_one(boxes, previous, self.threshold):
                if self.tracks[track_ids[j]][1] == classes[i]:
                    ids[i] = track_ids[j]
        for i in range(len(boxes)):
            if not ids[i]:
                ids[i] = self.next_id
                self.next_id += 1
            self.tracks[int(ids[i])] = (boxes[i], int(classes[i]), now)
        return ids


class FocusTracker:
    """BoT-SORT: Kalman filtresi + kamera hareketi telafisi (CMC) ile kimlik koruyan takip."""

    def __init__(self, frame_rate: float):
        self._sv = None
        self._tracker = None
        self._fallback = IoUTracker()
        try:
            import supervision as sv
            from trackers import BoTSORTTracker

            self._sv = sv
            self._tracker = BoTSORTTracker(
                lost_track_buffer=int(frame_rate * 2),
                frame_rate=frame_rate,
                track_activation_threshold=TRACK_ACTIVATION,
                minimum_consecutive_frames=2,
                high_conf_det_threshold=TRACK_HIGH_CONFIDENCE,
                enable_cmc=True,
                cmc_downscale=4,
            )
        except Exception:
            self._tracker = None

    def update(self, xyxy: np.ndarray, conf: np.ndarray, cls: np.ndarray, frame: np.ndarray, timestamp: float) -> np.ndarray:
        ids = np.zeros(len(xyxy), dtype=int)
        if self._tracker is not None:
            try:
                detections = self._sv.Detections(xyxy=xyxy, confidence=conf, class_id=cls)
                tracked = self._tracker.update(detections, frame=frame, timestamp=timestamp)
                if len(tracked) and tracked.tracker_id is not None:
                    valid = tracked.tracker_id >= 0
                    t_boxes = tracked.xyxy[valid].astype(np.float32)
                    t_ids = tracked.tracker_id[valid]
                    for i, j in match_one_to_one(xyxy, t_boxes, 0.6):
                        ids[i] = int(t_ids[j]) + 1
                return ids
            except Exception:
                self._tracker = None
        return self._fallback.update(xyxy, cls, timestamp)


def _iou(a: np.ndarray, b: np.ndarray) -> float:
    return float(iou_matrix(a[None, :], b[None, :])[0, 0])


class TargetLock:
    """Kilitlenilen hedef için hibrit takip: ViT tek-nesne takipçisi + dedektör doğrulaması."""

    REINIT_EVERY = 8
    LOST_AFTER = 2.6

    def __init__(self, display_id: int, box: np.ndarray, cls: int, timestamp: float):
        self.display_id = display_id
        self.cls = cls
        self.category = COCO_CATEGORIES.get(cls)
        self.box = box.astype(np.float32)
        self.velocity = np.zeros(2, dtype=np.float32)
        self.track_id = display_id
        self.last_confirm = timestamp
        self.last_time = timestamp
        self.since_init = 0
        self.sot = None
        self.score = 0.0

    @staticmethod
    def _create_sot():
        path = tracker_model_path()
        if path is None:
            return None
        try:
            import cv2

            params = cv2.TrackerVit_Params()
            params.net = str(path)
            return cv2.TrackerVit.create(params)
        except Exception:
            return None

    def _init_sot(self, frame: np.ndarray) -> None:
        x1, y1, x2, y2 = self.box
        if x2 - x1 < 2 or y2 - y1 < 2:
            return
        self.sot = self._create_sot()
        if self.sot is None:
            return
        try:
            self.sot.init(frame, (int(x1), int(y1), int(round(x2 - x1)), int(round(y2 - y1))))
            self.since_init = 0
        except Exception:
            self.sot = None

    def _sot_box(self, frame: np.ndarray):
        if self.sot is None:
            return None
        try:
            ok, (x, y, w, h) = self.sot.update(frame)
            self.score = float(self.sot.getTrackingScore())
        except Exception:
            self.sot = None
            return None
        if not ok or self.score < 0.32 or w < 2 or h < 2:
            return None
        box = np.array([x, y, x + w, y + h], dtype=np.float32)
        ref_w = max(2.0, self.box[2] - self.box[0])
        ref_h = max(2.0, self.box[3] - self.box[1])
        ratio = (w * h) / (ref_w * ref_h)
        shift = np.hypot((box[0] + box[2] - self.box[0] - self.box[2]) / 2, (box[1] + box[3] - self.box[1] - self.box[3]) / 2)
        if not 0.4 < ratio < 2.5 or shift > 3.0 * max(ref_w, ref_h):
            return None
        return box

    def update(self, frame: np.ndarray, xyxy: np.ndarray, cls: np.ndarray, ids: np.ndarray, timestamp: float) -> dict:
        dt = max(1e-3, timestamp - self.last_time)
        self.last_time = timestamp
        sot_box = self._sot_box(frame)
        if sot_box is not None:
            reference = sot_box
        else:
            reference = self.box.copy()
            reference[[0, 2]] += self.velocity[0] * dt
            reference[[1, 3]] += self.velocity[1] * dt
        ref_w = max(2.0, reference[2] - reference[0])
        ref_h = max(2.0, reference[3] - reference[1])
        ref_c = np.array([(reference[0] + reference[2]) / 2, (reference[1] + reference[3]) / 2])

        best, best_score = -1, 0.18
        for i, box in enumerate(xyxy):
            if COCO_CATEGORIES.get(int(cls[i])) != self.category:
                continue
            overlap = _iou(reference, box)
            center = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
            distance = np.hypot((center[0] - ref_c[0]) / ref_w, (center[1] - ref_c[1]) / ref_h)
            score = overlap + max(0.0, 0.35 - 0.25 * distance)
            if ids[i] and ids[i] == self.track_id:
                score += 0.3
            if score > best_score:
                best, best_score = i, score

        state = "lost"
        if best >= 0:
            box = xyxy[best].astype(np.float32)
            old_c = np.array([(self.box[0] + self.box[2]) / 2, (self.box[1] + self.box[3]) / 2])
            new_c = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
            self.velocity = self.velocity * 0.6 + ((new_c - old_c) / max(dt, timestamp - self.last_confirm + 1e-3)) * 0.4
            self.box = box
            self.track_id = int(ids[best]) if ids[best] else self.track_id
            self.last_confirm = timestamp
            for j in range(len(ids)):
                if j != best and ids[j] == self.display_id:
                    ids[j] = 0
            ids[best] = self.display_id
            if self.sot is None or self.since_init >= self.REINIT_EVERY or sot_box is None or _iou(sot_box, box) < 0.45:
                self._init_sot(frame)
            state = "detected"
        elif sot_box is not None and timestamp - self.last_confirm < self.LOST_AFTER:
            self.box = sot_box
            state = "tracking"
        elif timestamp - self.last_confirm < self.LOST_AFTER:
            self.box = reference
            state = "predicted"
        self.since_init += 1
        return {"state": state, "box": self.box.copy(), "index": best}


class DetectionEngine(QThread):
    detections_ready = pyqtSignal(str, object)
    state_changed = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cond = threading.Condition()
        self._slots: dict[str, tuple[np.ndarray, float]] = {}
        self._last_run: dict[str, float] = {}
        self._history: dict[str, deque] = {}
        self._focus: str | None = None
        self._focus_tracker: FocusTracker | None = None
        self._roi: tuple[float, float, float, float] | None = None
        self._lock_request = None
        self._target: TargetLock | None = None
        self._focus_jobs = 0
        self._full_cost = 0.0
        self._full_counts: dict[str, dict] = {}
        self._running = True
        self.device_label = ""
        self.ready = False

    def submit(self, cam_id: str, frame: np.ndarray, timestamp: float) -> None:
        if not self.ready:
            return
        with self._cond:
            self._slots[cam_id] = (frame, timestamp)
            self._cond.notify()

    def set_focus(self, cam_id: str | None) -> None:
        with self._cond:
            self._focus = cam_id
            self._focus_tracker = None
            self._roi = None
            self._focus_jobs = 0
            self._lock_request = None
            self._target = None
            if cam_id is not None:
                self._slots.pop(cam_id, None)
                self._history.pop(cam_id, None)

    def set_lock(self, cam_id: str, display_id: int, box, cls: int) -> None:
        with self._cond:
            if cam_id == self._focus:
                self._lock_request = (display_id, tuple(box), int(cls))

    def clear_lock(self) -> None:
        with self._cond:
            self._lock_request = None
            self._target = None

    def set_roi(self, cam_id: str, roi) -> None:
        with self._cond:
            if cam_id == self._focus:
                self._roi = roi

    def forget(self, cam_id: str) -> None:
        with self._cond:
            self._slots.pop(cam_id, None)
            self._last_run.pop(cam_id, None)
            self._history.pop(cam_id, None)

    def stop(self) -> None:
        self._running = False
        with self._cond:
            self._cond.notify_all()

    def _next_job(self):
        with self._cond:
            while self._running and not self._slots:
                self._cond.wait(0.25)
            if not self._running:
                return None, None, 0.0
            now = time.monotonic()
            focus = self._focus
            if focus and focus in self._slots:
                cam_id = focus
            else:
                candidates = list(self._slots.keys())
                if focus:
                    candidates = [c for c in candidates if now - self._last_run.get(c, 0.0) > BACKGROUND_DETECT_INTERVAL]
                    if not candidates:
                        self._cond.wait(0.01)
                        return "", None, 0.0
                cam_id = min(candidates, key=lambda c: self._last_run.get(c, 0.0))
            frame, timestamp = self._slots.pop(cam_id)
            self._last_run[cam_id] = now
            return cam_id, frame, timestamp

    def _smoothed_counts(self, cam_id: str, counts: dict) -> dict:
        history = self._history.setdefault(cam_id, deque(maxlen=4))
        history.append(counts)
        return {k: int(round(sum(h[k] for h in history) / len(history))) for k in counts}

    def _build_payload(self, cam_id: str, frame: np.ndarray, xyxy, conf, cls, ids, partial: bool = False) -> dict:
        h, w = frame.shape[:2]
        raw = {"person": 0, "vehicle": 0, "boat": 0, "animal": 0}
        objects = []
        for box, score, k, tid in zip(xyxy, conf, cls, ids):
            category = COCO_CATEGORIES.get(int(k))
            if category is None:
                continue
            tracked = bool(tid)
            if not tracked and score < COUNT_CONFIDENCE:
                continue
            if score > 0.0:
                raw[category] += 1
            objects.append(
                {
                    "id": int(tid) if tracked else None,
                    "cls": int(k),
                    "category": category,
                    "conf": float(score),
                    "box": (float(box[0]) / w, float(box[1]) / h, float(box[2]) / w, float(box[3]) / h),
                }
            )
        return {
            "t": time.monotonic(),
            "w": w,
            "h": h,
            "objects": objects,
            "counts": self._full_counts.get(cam_id, raw) if partial else self._remember_counts(cam_id, raw),
            "partial": partial,
        }

    def _update_target(self, frame, xyxy, conf, cls, ids, timestamp, request):
        if request is not None:
            display_id, norm_box, lock_cls = request
            h, w = frame.shape[:2]
            box = np.array([norm_box[0] * w, norm_box[1] * h, norm_box[2] * w, norm_box[3] * h], dtype=np.float32)
            self._target = TargetLock(display_id, box, lock_cls, timestamp)
        target = self._target
        if target is None:
            return None
        info = target.update(frame, xyxy, cls, ids, timestamp)
        if info["state"] == "lost":
            self._target = None
        return info

    def _remember_counts(self, cam_id: str, raw: dict) -> dict:
        counts = self._smoothed_counts(cam_id, raw)
        self._full_counts[cam_id] = counts
        return counts

    @staticmethod
    def _roi_crop(frame: np.ndarray, roi) -> tuple[np.ndarray, int, int]:
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = roi
        mx, my = (x2 - x1) * 0.15, (y2 - y1) * 0.15
        left = max(0, int((x1 - mx) * w))
        top = max(0, int((y1 - my) * h))
        right = min(w, int((x2 + mx) * w))
        bottom = min(h, int((y2 + my) * h))
        return frame[top:bottom, left:right], left, top

    def run(self) -> None:
        self.state_changed.emit("loading", "Donanım algılanıyor")
        try:
            from .hardware import select_device

            info = select_device()
            self.device_label = info.label
            self.state_changed.emit("loading", f"Model yükleniyor · {info.label}")
            from ultralytics import YOLO

            model = YOLO(str(model_path()))
            for size in sorted({info.imgsz, info.focus_imgsz}):
                warmup = np.zeros((size * 9 // 16, size, 3), dtype=np.uint8)
                model.predict(warmup, imgsz=size, device=info.device, half=info.half, verbose=False)
        except Exception as exc:
            try:
                (data_dir() / "error.log").write_text(traceback.format_exc(), encoding="utf-8")
            except OSError:
                pass
            self.state_changed.emit("error", f"Yapay zekâ devre dışı · {type(exc).__name__}")
            return

        self.ready = True
        self.state_changed.emit("ready", info.label)

        while self._running:
            cam_id, frame, timestamp = self._next_job()
            if cam_id is None:
                break
            if frame is None:
                continue
            with self._cond:
                is_focus = cam_id == self._focus
                if is_focus and self._focus_tracker is None:
                    self._focus_tracker = FocusTracker(25.0)
                tracker = self._focus_tracker if is_focus else None
                roi = self._roi if is_focus else None
                request = self._lock_request if is_focus else None
                if request is not None:
                    self._lock_request = None
                if is_focus:
                    self._focus_jobs += 1
            use_roi = roi is not None and self._focus_jobs % 8 != 0
            if use_roi:
                source, offset_x, offset_y = self._roi_crop(frame, roi)
                if source.shape[0] < 32 or source.shape[1] < 32:
                    source, offset_x, offset_y, use_roi = frame, 0, 0, False
            else:
                source, offset_x, offset_y = frame, 0, 0
            if use_roi:
                imgsz = info.imgsz
            elif is_focus:
                imgsz = info.focus_imgsz if self._full_cost < 0.09 else info.imgsz
            else:
                imgsz = info.imgsz
            started = time.perf_counter()
            try:
                boxes = model.predict(
                    source,
                    imgsz=imgsz,
                    conf=DETECTION_CONFIDENCE,
                    classes=DETECTION_CLASSES,
                    device=info.device,
                    half=info.half,
                    verbose=False,
                )[0].boxes
                xyxy = boxes.xyxy.cpu().numpy().astype(np.float32)
                if offset_x or offset_y:
                    xyxy[:, [0, 2]] += offset_x
                    xyxy[:, [1, 3]] += offset_y
                conf = boxes.conf.cpu().numpy().astype(np.float32)
                cls = boxes.cls.cpu().numpy().astype(int)
                inferred = time.perf_counter()
                if is_focus and not use_roi:
                    self._full_cost = self._full_cost * 0.8 + (inferred - started) * 0.2
                ids = tracker.update(xyxy, conf, cls, frame, timestamp) if tracker is not None else np.zeros(len(xyxy), dtype=int)
                lock_info = None
                if is_focus:
                    lock_info = self._update_target(frame, xyxy, conf, cls, ids, timestamp, request)
                    if lock_info is not None and lock_info["state"] in ("tracking", "predicted"):
                        xyxy = np.vstack([xyxy, lock_info["box"][None, :]])
                        conf = np.append(conf, np.float32(0.0))
                        cls = np.append(cls, self._target.cls)
                        ids = np.append(ids, self._target.display_id)
                payload = self._build_payload(cam_id, frame, xyxy, conf, cls, ids, partial=use_roi)
                if lock_info is not None:
                    payload["lock"] = {"id": self._target.display_id if self._target else None, "state": lock_info["state"]}
                payload["ts"] = timestamp
                payload["infer_ms"] = (inferred - started) * 1000
                payload["track_ms"] = (time.perf_counter() - inferred) * 1000
            except Exception:
                continue

            self.detections_ready.emit(cam_id, payload)
