Additional findings from consecutive GUI runs (dev @ `d74f56d`, Windows 11, GUI driven by my test driver). **Median** and **Footpath** changes do not re-seed the girder count either. The resulting layouts are accepted without any warning, even at a girder spacing of 7 m.

| Session / run | How the inputs were reached | Final homepage inputs | Girders | Spacing / overhang (m) | A fresh dict gives |
|---|---|---|---:|---|---:|
| S1 TC01 to TC03 | Design at 7.5 m, unlock, carriageway 11, median Yes, footpath Both | span 40, cw 11, median, footpaths both, skew -12 | **4** | **6.96 / 3.48** | 12 |
| S5 TC17 | fresh session, carriageway typed before median/footpath | same as above | 5 | 5.57 / 2.79 | 12 |
| S6 TC19 | fresh session, median/footpath selected before carriageway | same (skew 0) | 7 | 3.98 / 1.99 | 12 |
| S6 TC20 | after TC19: unlock, cw 7.5, no median/footpath | span 30, cw 7.5 | **7** | **1.20 / 0.60** | 4 |

"A fresh dict gives" is `solve_extend_basic_input_dict()` applied to `BASIC_INPUT_DICT` plus only the final homepage values.

* TC03 is a 27.85 m deck carried by 4 girders at 6.96 m. The 2D cross-section shows "Girder Spacing = 6.96 m, Overhang = 3.48 m" ([`cross_section.png`]({RAW}/testing/results/S1/TC03/cross_section.png)). The design completes with shear 187.8 % and fatigue 296.7 %, and the deck design sizes a 250 mm slab for a 6.96 m span.
* TC20 designs a 30 m, 8.4 m wide bridge with 7 girders at 1.2 m. The same inputs in a fresh session give 4 girders at 2.1 m (TC01).

Evidence: per-run dictionaries [`S1/TC03`]({TREE}/testing/results/S1/TC03), [`S5/TC17`]({TREE}/testing/results/S5/TC17), [`S6/TC19`]({TREE}/testing/results/S6/TC19), [`S6/TC20`]({TREE}/testing/results/S6/TC20), and the layout comparison in [`verification.json`]({REPO}/testing/results/verification.json) (`layout.fresh_session_girders`).
