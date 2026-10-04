@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
.venv\Scripts\python -m pip install -q -r requirements.txt pyinstaller
if not exist models mkdir models
if not exist models\yolo11s.pt .venv\Scripts\python -c "from ultralytics import YOLO; YOLO('models/yolo11s.pt')"
if not exist models\vittrack.onnx curl -sL -o models\vittrack.onnx "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/object_tracking_vittrack/object_tracking_vittrack_2023sep.onnx"
set QT_QPA_PLATFORM=offscreen
.venv\Scripts\python tools\make_icon.py
set QT_QPA_PLATFORM=
.venv\Scripts\pyinstaller --noconfirm --clean TurkiyeKameralari.spec
echo Hazir: %cd%\dist\TurkiyeKameralari\TurkiyeKameralari.exe
endlocal
