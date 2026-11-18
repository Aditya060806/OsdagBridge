Another GUI reproduction with a trigger outside the ones listed above (dev @ `d74f56d`, Windows 11, GUI driven by my test driver): span 40 m, carriageway **11 m**, median Yes, footpath Both Sides, skew 0, Ahmedabad, 7 girders (the count carried over from typing, see #112). Session S6, run TC19.

* Console: `UserWarning: Envelope-based governing LL detection failed`, then `skipping LL creation.`, followed by 10 `'live_load' load case not available` warnings.
* Every one of the 9 grillage lines has `Mu = Vu = M_sls = stress range = 0.0`. The only non-zero utilisations are LTB (39 %) and longitudinal shear (28 %). Status: PASS.
* `output_dict` writes `util.flexure`, `util.shear`, `util.fatigue` and `util.deflection_crack` as **0.0**. The Output Dock (*Design Envelope*) shows up to 64 % shear, 16 % flexure and 23 % stress from the dead-load cases, and hides Fatigue and Deflection. The dock and the dictionary contradict each other for the same run (compare #45).

Evidence: [`S6/TC19/output_dict.json`]({REPO}/testing/results/S6/TC19/output_dict.json), [`S6/TC19/dock.json`]({REPO}/testing/results/S6/TC19/dock.json), console [`S6/console.txt`]({REPO}/testing/results/S6/console.txt) (search "governing LL detection failed").
