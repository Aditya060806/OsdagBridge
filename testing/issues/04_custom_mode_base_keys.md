[Bug] Custom design mode: after a Span change the 3D CAD, edge lines and deck design use the initial-sizing girder, not the user's custom section

### What happens
In **Custom** design mode, the input dictionary holds two girder definitions once a required homepage field changes after the section was entered. I reproduced it by changing the span. Carriageway, median and footpath edits run the same code path (`solve_extend_basic_input_dict()`).

* the per-girder keys `member_properties.girder_details.*.G{n}.M1` keep the user's section (1600 x 450 x 25 / 550 x 32, tw 14);
* the legacy base keys `member_properties.girder_details.*` are re-seeded with the **initial-sizing** section for the new span (2120 x 640 x 28 / 750 x 32, tw 12).

Every consumer that resolves a girder without an index reads the base key first, so they use a girder the user never entered:

| Consumer (same run, TC11) | Uses |
|---|---|
| Girder design checks G1-G4 (`girder_index` given) | custom 1600 x 450 x 25 / 550 x 32, 14 |
| **3D CAD** (`get_3d_cad_parameters`) | **2120 x 640 x 28 / 750 x 32, 12** |
| Grillage edge lines, transverse and end-transverse members | initial-sizing section A = 0.0666 m², Iz = 0.0539 m⁴ (girders: 0.0505 / 0.0216) |
| Design lines 5-6 (no `.G5/.G6` keys exist) | initial-sizing section: Md = 25 549 kN·m (lines 1-4: 15 626 kN·m) |
| Deck design `bf_top_mm`, `output_dict` girder mass | 640 mm, 523 kg/m (custom: 450 mm, 396 kg/m) |

The design results move with it. With the base keys set equal to the user's section, the same input gives flexure 22.7 % instead of 37.7 %, LTB 50.4 % instead of 83.9 %, and deflection 68.3 % instead of 54.3 %.

It works in the first Custom run (TC09) and when only Additional Inputs change (TC10). There, saving the dialog writes the base keys too, and both sets agree. It fails from the first Design after a homepage field changes (TC11).

### Environment
Windows 11, Python 3.12.16 (conda env from `environment.yml`), `dev` @ `d74f56d`, source unmodified. The GUI was driven by [`testing/gui_driver.py`]({REPO}/testing/gui_driver.py). Session S3 (Guwahati), consecutive runs TC09 to TC11.

### Steps to reproduce (one session)
1. Span 35, Carriageway 9, Design Type **Custom**. Additional Inputs > Member Properties: Girder Unsymmetric, D 1800, top flange 450 x 25, bottom flange 550 x 32, web 14. Apply to exterior and interior girders, Save. Design (TC09): CAD and checks agree.
2. Unlock, Additional Inputs: D 1600, Apply, Save. Design (TC10): CAD and checks agree.
3. Unlock, change only **Span to 38**. Design (TC11): the CAD shows a 2120 mm deep girder, while the girder checks use D 1600.

### Evidence
* Per-run dictionaries and CAD parameters: [`S3/TC10/backend_input.json`]({REPO}/testing/results/S3/TC10/backend_input.json), [`S3/TC11/backend_input.json`]({REPO}/testing/results/S3/TC11/backend_input.json), [`S3/TC11/cad_params.json`]({REPO}/testing/results/S3/TC11/cad_params.json), [`S3/TC11/output_dict.json`]({REPO}/testing/results/S3/TC11/output_dict.json).
* Replay of the captured TC11 dict, as captured and with base keys = `.G1.M1`: [`probe_custom_base_keys.py`]({REPO}/testing/probes/probe_custom_base_keys.py), output [`custom_base_keys_S3_TC11.txt`]({REPO}/testing/probes/output/custom_base_keys_S3_TC11.txt):

```text
                                                       as captured (base keys re-seeded)   base keys = user's G1.M1
base depth key (mm)                                                         2120                        1600
girder check: D x bf_top x tf_top / bf_bot x tf_bot, tw    1600 x 450 x 25 / 550 x 32, 14   1600 x 450 x 25 / 550 x 32, 14
3D CAD girder (mm)                                          2120 x 640 x 28 / 750 x 32, 12   1600 x 450 x 25 / 550 x 32, 14
grillage edge-beam section A (m2) / Iz (m4)                              0.0666 / 0.0539             0.0505 / 0.0216
util.flexure / util.ltb / util.deflection_crack                    37.7 / 83.91 / 54.3     22.67 / 50.4 / 68.28
```

| TC10 (D 1600, CAD correct) | TC11 (only span changed, CAD shows the initial-sizing girder) |
|---|---|
| ![TC10]({RAW}/testing/results/S3/TC10/cad3d.png) | ![TC11]({RAW}/testing/results/S3/TC11/cad3d.png) |

### Root cause
* [`defaults.py#L644-L650`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/defaults.py#L644-L650) (`_on_no_of_girders_changed`, run by `solve_extend_basic_input_dict()` after a required-field edit and on Design). It keeps existing per-girder values in Custom mode, but then overwrites **all base keys unconditionally** with the initial-sizing values (`working_input_dict[base_key] = value`).
* [`plategirderbridge.py#L289-L314`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py#L289-L314) (`resolve_girder_value`): with `i=None` it tries the base key **before** `.G1.M1`. Index-less callers include `get_3d_cad_parameters` ([L3321](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py#L3321)), `setup_grillage` edge/transverse sections ([L1115-L1117](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py#L1115-L1117)), `design_deck_slab` ([L3195](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py#L3195)) and `store_design_results` ([L4164](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py#L4164)). Lines beyond the girder count (`.G5/.G6`) also fall back to the base key.

### Suggested fix
Keep the base keys in step with the first girder instead of re-seeding them in Custom mode:

```python
# defaults.py, _on_no_of_girders_changed(), replace the unconditional base-key sync
for base_key, value in MP_GIRDER_PROPS:
    g1 = working_input_dict.get(f"{base_key}.G1.M1")
    working_input_dict[base_key] = value if design_mode == "Optimized" or g1 in (None, "", "All") else g1
```

Also make the documented "representative girder" lookup prefer `.G1.M1` over the legacy key:

```python
# plategirderbridge.py, resolve_girder_value()
candidates = ([f"{base_key}.G{i + 1}.M1"] if i is not None else []) + [f"{base_key}.G1.M1", base_key]
```

Either change alone removes the TC11 mismatch. The second also covers callers that never go through `defaults.py`, such as OSI files and scripts.

### Duplicate check
I checked all open and closed issues on 17 Nov 2026. #71 (and its comment) covers Additional Inputs values being reset to defaults. #113 covers edge lines receiving a girder section at all. #116 covers Optimized-mode section properties not being recomputed. None covers base and per-girder girder keys diverging in Custom mode, or the CAD drawing a different girder from the one designed.
