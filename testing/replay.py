"""Headless replay: run the backend on an input dictionary captured from the GUI.

    python replay.py results/<session>/<run>/input_dict.json

The GUI driver saves the exact dict that Design hands to ``backend.set_input()``,
so replaying it reproduces the GUI run without the desktop (used by probes/).
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path


def run_design(input_dict: dict, quiet: bool = True):
    import osdagbridge.core.utils.connect  # noqa: F401  (reconfigures sys.stdout at import time)
    from osdagbridge.core.bridge_types.plate_girder.plategirderbridge import PlateGirderBridge
    bridge = PlateGirderBridge()
    bridge.set_input(input_dict)
    sink = io.StringIO() if quiet else sys.stdout
    with contextlib.redirect_stdout(sink):
        bridge.design()
    return bridge


def load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    b = run_design(load(sys.argv[1]))
    print({k: round(v, 2) for k, v in b.output_dict.items() if k.startswith("util.")})
