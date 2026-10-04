import os
import sys
import warnings

from .config import IS_WINDOWS, prepare_environment


def self_test(report_path: str) -> int:
    lines = []
    code = 0
    try:
        import numpy as np

        from .config import model_path
        from .detection import FocusTracker, TargetLock
        from .hardware import select_device

        info = select_device()
        lines.append(f"device {info.device} {info.label}")
        from ultralytics import YOLO

        model = YOLO(str(model_path()))
        frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        result = model.predict(frame, imgsz=info.imgsz, device=info.device, verbose=False)[0]
        lines.append(f"yolo ok {len(result.boxes)}")
        tracker = FocusTracker(25.0)
        tracker.update(np.zeros((0, 4), np.float32), np.zeros(0, np.float32), np.zeros(0, int), frame, 0.0)
        lines.append(f"botsort {tracker._tracker is not None}")
        lines.append(f"vit {TargetLock._create_sot() is not None}")
        import cv2

        lines.append(f"opencv {cv2.__version__}")
        if tracker._tracker is None or TargetLock._create_sot() is None:
            code = 2
    except Exception:
        import traceback

        lines.append(traceback.format_exc())
        code = 1
    lines.append(f"exit {code}")
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return code


def run() -> int:
    prepare_environment()
    if "--self-test" in sys.argv:
        index = sys.argv.index("--self-test")
        report = sys.argv[index + 1] if index + 1 < len(sys.argv) else "self-test.txt"
        warnings.filterwarnings("ignore")
        return self_test(report)
    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=UserWarning, module="torch")

    if IS_WINDOWS:
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MeteSahan.TurkiyeKameralari")
        except (AttributeError, OSError):
            pass

    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtWidgets import QApplication

    from . import APP_ID, APP_NAME, APP_VERSION, DEVELOPER
    from .main_window import MainWindow
    from .theme import font

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(DEVELOPER)
    app.setStyle("Fusion")
    app.setFont(font(13))

    window = MainWindow()
    app.aboutToQuit.connect(window.shutdown)
    if os.environ.get("TK_DEBUG"):
        def report(state, info):
            print("engine", state, info, flush=True)
            if state == "ready":
                from .detection import FocusTracker, TargetLock

                print("botsort", FocusTracker(25.0)._tracker is not None, "vit", TargetLock._create_sot() is not None, flush=True)

        window.manager.engine_state.connect(report)
        window.manager.detections_ready.connect(lambda cam, payload: print("detections", cam, payload["counts"], flush=True))
    window.show()
    code = app.exec()
    if not window.shutdown_clean:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(code)
    return code
