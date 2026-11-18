Additional finding in the same function: besides the 3 m spacing, `get_3d_cad_parameters()` also hard-codes every cross-bracing and end-diaphragm **section**, so the CAD never shows the designed or selected members.

[`plategirderbridge.py#L3356-L3369`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py#L3356-L3369) and [`L3590-L3625`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py#L3590-L3625):

| Member (default bridge, TC01) | Input dict (Additional Inputs) | Design result (`crossbracing_design_results`) | Drawn in 3D CAD |
|---|---|---|---|
| CB diagonal | Double Angle (Long Leg) IS 100 x 100 x 10 | 40 x 40 x 3 | ANGLE 100 x 50, t 8 (`_angle_dims`) |
| CB top chord | Double Angle (Long Leg) IS 100 x 100 x 10 | 40 x 40 x 3 | DOUBLE_CHANNEL 80 x 40, t 8 (`_small_dims`) |
| CB bottom chord | Double Angle (Long Leg) IS 100 x 100 x 10 | 40 x 40 x 3 | ANGLE 80 x 40, t 8 |
| Bracing type | X-Bracing (per pair) | | always `"X"`, `x_bracket_option="BOTH"` |
| End diaphragm | Cross Bracing, Double Angle IS 100 x 100 x 10 | | fixed ANGLE 100 x 50 / CHANNEL 80 x 40, t 8 (plus an `I_SECTION` 0.6 D x B_top) |

The 2D plan view shows a third spacing: "Bracing Spacing = 3.50 m". With `KEY_MP_CB_SPACING` unset, [`cad_dual_view.py#L298-L302`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/desktop/ui/docks/cad_dual_view.py#L298-L302) falls back to 3.5 m, while the per-pair keys hold 15.0 m and the design uses 3.0 m (see also #111).

Suggested fix: build the bracing DTO fields from the per-pair input keys (`member_properties.cross_bracing_details.*.G1G2.B1M1`) or from the designed section in `crossbracing_design_results`. Look up the angle legs and thickness with `get_angle_section_properties()`, as `defaults.py` already does for the end diaphragm.

Evidence (dev @ `d74f56d`, Windows 11): [`S1/TC01/input_dict.json`]({REPO}/testing/results/S1/TC01/input_dict.json), [`S1/TC01/cad_params.json`]({REPO}/testing/results/S1/TC01/cad_params.json) (the DTO passed to the 3D viewer), [`S1/TC01/output_dict.json`]({REPO}/testing/results/S1/TC01/output_dict.json), plan view [`S1/TC01/top_view.png`]({RAW}/testing/results/S1/TC01/top_view.png).
