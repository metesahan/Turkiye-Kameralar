import os
import platform
import subprocess
import sys
from dataclasses import dataclass

from .config import FOCUS_IMGSZ_CPU, FOCUS_IMGSZ_GPU, GRID_IMGSZ_CPU, GRID_IMGSZ_GPU


def chip_name() -> str:
    if sys.platform == "darwin":
        try:
            output = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=2, check=False,
            ).stdout.strip()
            if output:
                return output
        except (OSError, subprocess.SubprocessError):
            pass
    return platform.processor() or platform.machine()


@dataclass(frozen=True)
class DeviceInfo:
    device: str
    label: str
    half: bool
    imgsz: int
    focus_imgsz: int
    accelerated: bool


def select_device() -> DeviceInfo:
    import torch

    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return DeviceInfo("mps", f"{chip_name()} · Metal (MPS)", False, GRID_IMGSZ_GPU, FOCUS_IMGSZ_GPU, True)

    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
        name = torch.cuda.get_device_name(0)
        return DeviceInfo("cuda:0", f"{name} · CUDA", True, GRID_IMGSZ_GPU, FOCUS_IMGSZ_GPU, True)

    threads = max(1, (os.cpu_count() or 4) - 2)
    torch.set_num_threads(threads)
    return DeviceInfo("cpu", f"CPU · {threads} çekirdek", False, GRID_IMGSZ_CPU, FOCUS_IMGSZ_CPU, False)
