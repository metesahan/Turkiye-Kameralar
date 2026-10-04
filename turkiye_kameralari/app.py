import os
import sys
import warnings

from .config import IS_WINDOWS, prepare_environment


def run() -> int:
    prepare_environment()
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
