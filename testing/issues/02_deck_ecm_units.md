[Bug] Deck slab SLS checks use Ecm in GPa as if it were MPa: modular ratio 6061 instead of 6.06, concrete stress under-estimated 4x, crack width 25 % low

### What happens
`PlateGirderBridge.design_deck_slab()` passes the concrete modulus to `deckdesign.design_deck_slab()` in **GPa** (33.0 for M40). `deckdesign` documents and uses it as **MPa**. The modular ratio therefore becomes αe = Es/Ecm = 200000/33 = **6060.6** instead of 6.06. The cracked-section neutral axis lands almost on the reinforcement (x/d = 0.976 instead of 0.182), and every deck SLS result is wrong.

The girder design is not affected, because `designer.py` converts the same value with `* 1000` ([`L336-L337`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/designer.py#L336-L337)). Only the deck slab path is wrong, and it is wrong for database grades and custom concrete alike.

### Environment
Windows 11, Python 3.12.16 (conda env from `environment.yml`), `dev` @ `d74f56d`, source unmodified. The GUI was driven by [`testing/gui_driver.py`]({REPO}/testing/gui_driver.py), with dictionaries captured after each run.

### Steps to reproduce
Ahmedabad, Span 30, Carriageway 7.5, defaults (M40, Fe 500, deck 250 mm). Design, then open Deck Design > Design Summary, or look at `output_dict["deck_design_results"]`.

### Expected / actual (TC01; same inputs with Ecm converted to MPa)
| `deck_design_results` | As designed (Ecm = 33 "MPa") | Ecm = 33 000 MPa |
|---|---:|---:|
| Neutral axis x / d (bottom mat) | 189.4 / 194 = **0.976** | 35.3 / 194 = **0.182** |
| Concrete stress bottom σc (MPa), UR | **2.49**, 0.13 | **9.84**, 0.51 |
| Steel stress bottom σs (MPa), UR | 365.3, 0.913 | 276.9, 0.692 |
| Crack width bottom / top (mm) | **0.198 / 0.213** | **0.263 / 0.281** |
| Bottom reinforcement | Ø12 @ 175 (646 mm²/m) | Ø12 @ 185 (611 mm²/m) |

The concrete stress and the crack width come out unconservative. The steel stress is over-estimated, and `_tighten_for_sls_stress()` then adds reinforcement on that basis. I got the same pattern with a custom concrete (TC05, Ecm 33.5 GPa) and with the custom-mode deck of 230 mm (TC09).

### Evidence
* Probe: [`probe_deck_ecm_units.py`]({REPO}/testing/probes/probe_deck_ecm_units.py) replays the GUI input dict, then reruns only the deck design with `Ecm * 1000`. Outputs: [`deck_ecm_S1_TC01.txt`]({REPO}/testing/probes/output/deck_ecm_S1_TC01.txt), [`deck_ecm_S2_TC05.txt`]({REPO}/testing/probes/output/deck_ecm_S2_TC05.txt), [`deck_ecm_S3_TC09.txt`]({REPO}/testing/probes/output/deck_ecm_S3_TC09.txt).

```text
concrete M40: fck=40.0 MPa, fctm=3.0 MPa, Ecm passed = 33.0  (DB/DTO unit: GPa)
rebar Fe 500: fy=500.0 MPa, Es=200000.0 MPa  ->  alpha_e = Es/Ecm = 6060.6 (with Ecm in MPa: 6.06)
bottom mat, GPa value (as run): alpha_e=  6060.61  x= 189.4 mm  d=194.0 mm  x/d=0.976
bottom mat, MPa value         : alpha_e=     6.06  x=  35.3 mm  d=194.0 mm  x/d=0.182
```
* GUI dictionaries of the run: [`S1/TC01/output_dict.json`]({REPO}/testing/results/S1/TC01/output_dict.json) (`deck_design_results`, `deck_report_values`).

### Root cause
* [`plategirderbridge.py#L3185-L3196`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py#L3185-L3196): `Ecm = self.material_props.concrete_prop.Ecm`. `ConcreteProperties.Ecm` is in GPa ([`dto.py#L146`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/dto.py#L146)), as are the database and the material dialog.
* [`deckdesign.py#L429-L430`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/deckdesign.py#L429-L430) documents `Ecm` in MPa. [`_cracked_section()` L211](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/deckdesign.py#L211) computes `alpha_e = Es_MPa / Ecm_MPa`.

### Suggested fix
```python
# plategirderbridge.py, design_deck_slab()
Ecm  = self.material_props.concrete_prop.Ecm * 1000.0   # GPa -> MPa (deckdesign expects MPa)
```
A regression check: for M40/Fe 500, `_cracked_section()` should give αe ≈ 6.06 and x/d ≈ 0.18 for the default deck.

### Duplicate check
I checked all open and closed issues on 17 Nov 2026. #41 (deck density), #42 (Gs) and #82 (Excel unit labels) concern other properties. No issue covers the Ecm unit in the deck design.
