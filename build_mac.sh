#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt pyinstaller
mkdir -p models
if [ ! -f models/yolo11s.pt ]; then
  .venv/bin/python -c "from ultralytics import YOLO; YOLO('models/yolo11s.pt')"
fi
if [ ! -f models/vittrack.onnx ]; then
  curl -sL -o models/vittrack.onnx "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/object_tracking_vittrack/object_tracking_vittrack_2023sep.onnx"
fi
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/make_icon.py
.venv/bin/pyinstaller --noconfirm --clean TurkiyeKameralari.spec
rm -rf "Türkiye Kameraları.app"
ditto "dist/Türkiye Kameraları.app" "Türkiye Kameraları.app"
xattr -cr "Türkiye Kameraları.app"
codesign --force --deep --sign - "Türkiye Kameraları.app"
echo "Hazır: $(pwd)/Türkiye Kameraları.app"
