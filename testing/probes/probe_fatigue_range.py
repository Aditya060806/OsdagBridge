"""Probe: girder fatigue stress range is doubled by the end-force sign convention.

Replays a GUI input dictionary and recomputes the fatigue moment range exactly the
way designer._extract_demands_from_analysis_results() does (max - min over the
concatenated Mz_i and Mz_j end forces of every SLS-frequent case), next to the
per-load-case value the Output Dock "Design Envelope" uses.

    python probes/probe_fatigue_range.py results/<session>/<run>/input_dict.json
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay import load, run_design  # noqa: E402

from osdagbridge.core.bridge_types.plate_girder.analysis_results import PlateGirderAnalysisResults  # noqa: E402

b = run_design(load(sys.argv[1]))
res = PlateGirderAnalysisResults(dataset=b.get_results_dataset(), bridge=b.grillage_model)
girders, _ = res.build_girders(verbose=False)
sls_freq = [str(lc) for lc in res.classify_loadcases()["sls_frequent"]]
dr = b.design_results
print(f"SLS frequent cases: {len(sls_freq)}   controlling girder: {dr.get('controlling_girder', '?')}")
print(f"{'girder':6} {'max Mz_i':>10} {'min Mz_i':>10} {'max Mz_j':>10} {'min Mz_j':>10} "
      f"{'designer range':>15} {'max |M| per LC':>15} {'ratio':>6}   (kN.m)")
for g, info in girders.items():
    if g.startswith("EB"):
        continue
    f = res.ds.forces.sel(Loadcase=sls_freq, Element=list(info["elements"]))
    mz_i = np.asarray(f.sel(Component="Mz_i").values, float) / 1e3
    mz_j = np.asarray(f.sel(Component="Mz_j").values, float) / 1e3
    both = np.concatenate([mz_i.ravel(), mz_j.ravel()])
    designer_range = max(both.max(), 0.0) - min(both.min(), 0.0)          # designer.py step (4)
    per_lc_max = np.maximum(np.abs(mz_i), np.abs(mz_j)).max()              # per-LC path (_fmax)
    print(f"{g:6} {mz_i.max():10.1f} {mz_i.min():10.1f} {mz_j.max():10.1f} {mz_j.min():10.1f} "
          f"{designer_range:15.1f} {per_lc_max:15.1f} {designer_range / per_lc_max:6.3f}")

    # Same range with the j-end converted to the i-end sign (internal moment convention).
    internal = np.concatenate([mz_i.ravel(), -mz_j.ravel()])
    fixed_range = max(internal.max(), 0.0) - min(internal.min(), 0.0)
    pg = dr["per_girder"][g]
    chk = next((c for c in pg["checks"] if c["check_id"] == 8), None)
    if chk:
        scale = pg["demand"]["stress_range_MPa"] / designer_range       # MPa per kN.m (1 / Ze_comp)
        print(f"{'':6} check 8: stress range {chk['demand']:.2f} MPa / f_fd {chk['capacity']:.2f} MPa = "
              f"UR {chk['dcr']:.3f}   with internal sign: {fixed_range * scale:.2f} MPa, "
              f"UR {fixed_range * scale / chk['capacity']:.3f}")

def section_range(f, comp):
    """Proposed fix: range per section (element end) across the SLS-frequent cases,
    with the j-end force converted to the internal-force sign."""
    a = np.asarray(f.sel(Component=f"{comp}_i").values, float)
    b_ = -np.asarray(f.sel(Component=f"{comp}_j").values, float)
    sec = np.concatenate([a, b_], axis=1)                       # (load case, section)
    return float(np.nanmax(np.maximum(np.nanmax(sec, 0), 0) - np.minimum(np.nanmin(sec, 0), 0)))


print(f"\n{'girder':6} {'Mz range now':>13} {'Mz per-section':>15} {'Vy range now':>13} {'Vy per-section':>15} "
      f"{'max|Vy| per LC':>15}   (kN.m / kN)")
for g, info in girders.items():
    f = res.ds.forces.sel(Loadcase=sls_freq, Element=list(info["elements"]))
    both = lambda c: np.concatenate([np.asarray(f.sel(Component=f"{c}_{e}").values, float).ravel() for e in "ij"])
    now = lambda c: max(both(c).max(), 0.0) - min(both(c).min(), 0.0)
    vmax = np.abs(both("Vy")).max()
    print(f"{g:6} {now('Mz') / 1e3:13.1f} {section_range(f, 'Mz') / 1e3:15.1f} {now('Vy') / 1e3:13.1f} "
          f"{section_range(f, 'Vy') / 1e3:15.1f} {vmax / 1e3:15.1f}")

env = b.get_dcr_for_selection(None, "Design Envelope")
print(f"\noutput_dict util.fatigue (report)        = {b.output_dict['util.fatigue']:.2f} %")
print(f"Output Dock / Design Check 'Envelope'     = {env['util.fatigue']:.2f} %")
print(f"ratio                                     = {b.output_dict['util.fatigue'] / env['util.fatigue']:.3f}")
