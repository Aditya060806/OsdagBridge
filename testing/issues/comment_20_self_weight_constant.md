Additional finding: reading the density in `_build_material_props()` will not be enough on its own. The girder self-weight load never uses `steel_prop.rho`.

[`analyser.py#L416`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/analyser.py#L416) computes `girder_self_weight_kN_m(A_girder_m2, STEEL_UNIT_WEIGHT_kN_m3)`, where `STEEL_UNIT_WEIGHT_kN_m3 = DEFAULT_STEEL_DENSITY = 78.5` is a module constant. In one GUI session (S2, span 25 m, same section in all four runs) the applied line load stayed identical while the dictionary density changed:

| Run | `material.girder` | `material.girder.density` (input/output dict) | SW line load from analyser log |
|---|---|---:|---:|
| TC05 | custom_steel_345_480 | 78.5 | 1874.59 N/m (A = 0.02388 m²) |
| TC06 | custom_steel_410_540 | **80.0** | 1874.59 N/m |
| TC07 | E 350A | **76.4** | 1874.59 N/m |
| TC08 | custom_steel_410_540 | **77.0** | 1874.59 N/m |

1874.59 / 0.02388 = 78.5 kN/m³ in every run. This also affects **database grades**. The Material dialog, the input dict and report Chapter 3 ("Steel Self-Weight Applied: **76.4** kN/m³", which is IRC 6 7.8 t/m³ x 9.8) all state a value that the analysis does not apply (78.5).

The fix therefore needs both parts: read `material.girder.density` in `_build_material_props()` (as suggested above), and pass it to the load:

```python
# analyser.py, create_self_weight_load()
rho_kN_m3 = self.material_props.steel_prop.rho / 1e3          # N/m3 -> kN/m3
beam_mag = girder_self_weight_kN_m(A_girder_m2, rho_kN_m3) * kN / m
```
(`self.material_props` is whatever `create_material()` received; store it there if it is not kept yet.)

Evidence (dev @ `d74f56d`, Windows 11, GUI driven by my test driver): dictionaries [`S2/TC06/input_dict.json`]({REPO}/testing/results/S2/TC06/input_dict.json), [`S2/TC08/input_dict.json`]({REPO}/testing/results/S2/TC08/input_dict.json); analyser log lines in [`S2/console.txt`]({REPO}/testing/results/S2/console.txt) (search "Self weight line load"); report [`S1/TC01/report/TC01_report.pdf`]({REPO}/testing/results/S1/TC01/report/TC01_report.pdf), Chapter 3.
