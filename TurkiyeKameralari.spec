# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, get_package_paths

ROOT = Path(SPECPATH)
APP_NAME = "Türkiye Kameraları"
IS_MAC = sys.platform == "darwin"

datas = [
    (str(ROOT / "models" / "yolo11s.pt"), "models"),
    (str(ROOT / "models" / "vittrack.onnx"), "models"),
    (str(ROOT / "assets" / "icon.png"), "assets"),
]
datas += collect_data_files("ultralytics")
datas += collect_data_files("supervision")
datas += collect_data_files("trackers")

binaries = collect_dynamic_libs("torchvision")
_, torchvision_dir = get_package_paths("torchvision")
for pattern in ("*.so", "*.pyd", "*.dll"):
    for lib in Path(torchvision_dir).glob(pattern):
        binaries.append((str(lib), "torchvision"))
for lib in (Path(torchvision_dir) / ".dylibs").glob("*.dylib"):
    binaries.append((str(lib), "torchvision/.dylibs"))

hiddenimports = collect_submodules("turkiye_kameralari")
hiddenimports += collect_submodules("ultralytics.nn")
hiddenimports += collect_submodules("trackers")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "IPython", "jupyter", "notebook", "pytest", "tensorboard"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="TurkiyeKameralari",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    icon=str(ROOT / "assets" / ("icon.icns" if IS_MAC else "icon.ico")),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="TurkiyeKameralari",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=str(ROOT / "assets" / "icon.icns"),
        bundle_identifier="com.metesahan.turkiyekameralari",
        version="1.0.0",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": "1.0.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "LSMinimumSystemVersion": "12.0",
            "LSApplicationCategoryType": "public.app-category.utilities",
            "NSHumanReadableCopyright": "Mete Şahan Tarafından Geliştirilmiştir 2026",
        },
    )
