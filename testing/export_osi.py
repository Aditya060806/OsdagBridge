"""Write every captured test case as an .osi file (the dict Design handed to the backend).

    python export_osi.py   ->  osi/<session>_<case>.osi, each re-checked with validate_osi_inputs()
"""
import json
from pathlib import Path

import yaml

from osdagbridge.core.utils.osi_validator import validate_osi_inputs

HERE = Path(__file__).parent
OUT = HERE / "osi"
OUT.mkdir(exist_ok=True)
for case in sorted(HERE.glob("results/S*/TC*/input_dict.json")):
    data = json.loads(case.read_text(encoding="utf-8"))
    name = f"{case.parent.parent.name}_{case.parent.name}.osi"
    (OUT / name).write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    check = validate_osi_inputs(yaml.safe_load((OUT / name).read_text(encoding="utf-8")))
    print(f"{name:14s} keys={len(data):4d} valid={check.is_valid}"
          + ("" if check.is_valid else f"  {check.error_text(limit=3)}"))
