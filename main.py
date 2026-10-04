import multiprocessing
import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from turkiye_kameralari.app import run  # noqa: E402

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(run())
