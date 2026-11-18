"""Probe: deck-slab SLS checks receive Ecm in GPa where MPa is expected.

PlateGirderBridge.design_deck_slab() forwards material_props.concrete_prop.Ecm
(GPa, e.g. 33.0 for M40) to deckdesign.design_deck_slab(), whose docstring and
formulas expect MPa. This replays a GUI input dictionary, then re-runs the deck
design with the same inputs and Ecm converted to MPa, and compares the results.

    python probes/probe_deck_ecm_units.py results/<session>/<run>/input_dict.json
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay import load, run_design  # noqa: E402

from osdagbridge.core.bridge_types.plate_girder import deckdesign as dd  # noqa: E402
from osdagbridge.core.bridge_types.plate_girder.plategirderbridge import resolve_girder_value  # noqa: E402
from osdagbridge.core.utils.common import (KEY_DS_REINF_MATERIAL, KEY_DS_STUD_HEIGHT,  # noqa: E402
                                           KEY_MP_GIRDER_TOP_FLANGE_WIDTH)

b = run_design(load(sys.argv[1]))
c = b.material_props.concrete_prop
rebar = str(b.input_dict[KEY_DS_REINF_MATERIAL]).strip()
fy, Es = b._lookup_material(rebar, "fy"), b._lookup_material(rebar, "Es")
print(f"concrete {c.grade}: fck={c.fck} MPa, fctm={c.fctm} MPa, Ecm passed = {c.Ecm}  (DB/DTO unit: GPa)")
print(f"rebar {rebar}: fy={fy} MPa, Es={Es} MPa  ->  alpha_e = Es/Ecm = {Es / c.Ecm:.1f} "
      f"(with Ecm in MPa: {Es / (c.Ecm * 1000):.2f})\n")

def deck(ecm):
    return dd.design_deck_slab(
        b.input_dict, fck=c.fck, fctm=c.fctm, fy=fy, Ecm=ecm, Es=Es, design_results=None,
        bf_top_mm=resolve_girder_value(b.input_dict, KEY_MP_GIRDER_TOP_FLANGE_WIDTH) * 1000.0,
        stud_height_mm=float(b.input_dict[KEY_DS_STUD_HEIGHT]))[0]

as_run, corrected = b.output_dict["deck_design_results"], deck(c.Ecm * 1000.0)
rows = ["rebar_bottom_dia", "rebar_bottom_spacing", "rebar_bottom_area", "rebar_top_spacing", "rebar_top_area",
        "rebar_overhang_spacing", "rebar_overhang_area", "deckdesign.stress.concrete.bottom",
        "deckdesign.stress.concrete.top", "deckdesign.stress.reinf.bottom", "deckdesign.stress.reinf.top",
        "deckdesign.crack.wk.bottom", "deckdesign.crack.wk.top", "ur_bot_sls_c", "ur_bot_sls_s", "ur_bot_crack"]
print(f"{'deck_design_results key':36} {'as designed (Ecm GPa)':>22} {'Ecm in MPa':>12}")
for k in rows:
    print(f"{k:36} {as_run.get(k)!s:>22} {corrected.get(k)!s:>12}")

# Section-level view of the bottom mat as designed: neutral axis vs effective depth.
d_mm = float(as_run["deck_thickness"]) - float(as_run["rebar_bottom_cover"]) - float(as_run["rebar_bottom_dia"]) / 2
As = float(as_run["rebar_bottom_area"])
for label, ecm in (("GPa value (as run)", c.Ecm), ("MPa value", c.Ecm * 1000.0)):
    x, _, ae = dd._cracked_section(As, d_mm, Es, ecm)
    print(f"bottom mat, {label:18}: alpha_e={ae:9.2f}  x={x:6.1f} mm  d={d_mm:.1f} mm  x/d={x / d_mm:.3f}")
