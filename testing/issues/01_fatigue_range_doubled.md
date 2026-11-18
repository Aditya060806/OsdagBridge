[Bug] Girder fatigue stress range is doubled: report/output dict say FAIL (1.58) while Output Dock and Design Check show the same check as PASS (0.79)

### What happens
For the same girder and the same fatigue check, the GUI and the report disagree by a factor of 2:

| Where | Girder G3, Fatigue Normal Stress (default bridge) |
|---|---|
| Output Dock, *Design Envelope* | **79 %** |
| Analysis and Design Results Summary > Design Check, SLS_FREQUENT_1 | Δσ = **72.93 MPa** / 92.49 MPa = **0.79 PASS** |
| `output_dict["util.fatigue"]` | **157.70** |
| Report Table 5.12 (G3) | Δσ = **145.86 MPa** / 92.49 MPa = **1.577 FAIL** |
| Report Executive Summary | *Overall Design Status: Fail (Fatigue Normal Stress, ...)*, UR 1.58 |

The report value is exactly twice the GUI value. All 14 of my GUI design runs that produced a fatigue check show a ratio of 2.00 (spans 20 to 40 m, database and custom grades, Optimized and Custom modes), so every default design is reported as a fatigue failure. Example: span 20 m gives 211.9 % in the report against 105.9 % in the dock.

This explains the >100 % fatigue values reported in #44 and #65; neither identifies the doubling.

### Environment
Windows 11, Python 3.12.16 (conda env from `environment.yml`), `dev` @ `d74f56d`, source unmodified. The desktop GUI was driven by my test driver ([`testing/gui_driver.py`]({REPO}/testing/gui_driver.py)), which runs the real `CustomWindow` and types into its widgets. Dictionaries were captured after each run.

### Steps to reproduce
1. `python -m osdagbridge.desktop`. Location Ahmedabad (Gujarat), Span 30, Carriageway 7.5, everything else default (E 350A, M40, Optimized). Design.
2. Output Dock > Girder Design > Member G3, Load Case *Design Envelope*: Resistance to Fatigue = 79 %.
3. Generate Report: Table 5.12 shows UR 1.537 to 1.577 FAIL for G1-G4.

### Evidence
* Inputs/outputs of this run (TC01): [`input_dict.json`]({REPO}/testing/results/S1/TC01/input_dict.json), [`output_dict.json`]({REPO}/testing/results/S1/TC01/output_dict.json), dock bar values [`dock.json`]({REPO}/testing/results/S1/TC01/dock.json), report [`TC01_report.pdf`]({REPO}/testing/results/S1/TC01/report/TC01_report.pdf).
* Probe that replays the captured input dict and recomputes the range exactly as the designer does: [`probe_fatigue_range.py`]({REPO}/testing/probes/probe_fatigue_range.py), output [`fatigue_S1_TC01.txt`]({REPO}/testing/probes/output/fatigue_S1_TC01.txt). For every girder line the "range" is 2.000 x the largest moment:

```text
girder   max Mz_i   min Mz_i   max Mz_j   min Mz_j  designer range  max |M| per LC  ratio   (kN.m)
G3         2115.4        0.0       -0.0    -2115.4          4230.8          2115.4  2.000
       check 8: stress range 145.86 MPa / f_fd 92.49 MPa = UR 1.577   with internal sign: 72.93 MPa, UR 0.789
girder  Mz range now  Mz per-section  Vy range now  Vy per-section  max|Vy| per LC
G3            4230.8          2115.4         548.2           274.1           274.1
```

| GUI (dock + Design Check) | Report |
|---|---|
| ![dock]({RAW}/testing/results/evidence/dock_G3_design_envelope.png) | ![report]({RAW}/testing/results/evidence/report_fatigue_table.png) |

![design check]({RAW}/testing/results/evidence/design_check_G3_SLS_FREQUENT_1.png)

### Root cause
[`designer.py#L2970-L2994`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/designer.py#L2970-L2994) (`_extract_demands_from_analysis_results`, step 4) concatenates the `Mz_i` and `Mz_j` element end forces and takes `max - min`. The two ends use opposite signs for the same internal moment (`Mz_i` runs 0 to +2115 kN·m and `Mz_j` runs -2115 to 0), so `max - min` is 2 x |M|. `Vy_i`/`Vy_j` give the shear range the same way, so it is doubled too.

The per-load-case path ([`L3082-L3083`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/designer.py#L3082-L3083)) uses `max(|Mz_i|, |Mz_j|)` instead. That path feeds the Output Dock and the Design Check tab. The doubled envelope value feeds `category_urs`, then `store_design_results()` and `util.fatigue`, and from there the report.

### Suggested fix
Convert the j-end forces to the i-end (internal-force) sign before taking the range, and take the range per section:

```python
# designer.py, _extract_demands_from_analysis_results(), step (4)
f = analysis_results.ds.forces.sel(Loadcase=_sls_frequent_lcs, Element=elements)

def _section_range(comp):
    """max - min over the frequent combinations at the worst section (internal-force sign)."""
    sec = np.concatenate([np.asarray(f.sel(Component=f"{comp}_i").values, float),
                          -np.asarray(f.sel(Component=f"{comp}_j").values, float)], axis=1)  # (LC, section)
    return float(np.nanmax(np.maximum(np.nanmax(sec, 0), 0.0) - np.minimum(np.nanmin(sec, 0), 0.0)))

stress_range_MPa = _section_range("Mz") * 1000.0 / Ze_comp_bot_mm3
shear_range_MPa  = _section_range("Vy") / Aw_mm2
```

With this change the envelope gives 72.93 MPa / UR 0.789 for TC01, the same as the dock and the Design Check card. The probe prints both values.

Separately, both paths currently use the total frequent-SLS moment (DL + 0.75 LL + 0.5 WL) as the "range". It would be worth confirming that against the live-load fatigue range intended by IRC 22 Cl. 605.

### Duplicate check
I checked all open and closed issues on 17 Nov 2026. #44 and #65 report `util.fatigue` above 100 % and its consequences for `design()` and the Executive Summary. No issue covers the sign-convention doubling or the dock/report disagreement.
