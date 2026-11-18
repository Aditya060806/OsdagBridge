# OsdagBridge GUI test campaign: short-span plate girder module

Tested build: `Nidhikhare12/OsdagBridge` `dev` @ `d74f56d`, unmodified, on Windows 11 with
Python 3.12.16 (conda env from `environment.yml`). Everything here lives in `testing/`; no
production source was changed.

## How the tests drive the application
`gui_driver.py` starts the real desktop window (`CustomWindow` + `PlateGirderBridge`, the same
objects `python -m osdagbridge.desktop` creates) and operates it through its widgets: it types into
the input dock, selects combos, fills the project-location, custom-material and Additional
Inputs dialogs, clicks Design and Unlock, and answers message boxes. After every run it captures
the evidence listed below. Designs run on the application's own worker thread.

| File | Purpose |
|---|---|
| `gui_driver.py` | GUI driver and evidence capture |
| `campaign.py` | test sessions S1-S6 (cases TC01-TC20), `python campaign.py S1 S2 ...` |
| `verify.py` | cross-checks: UI vs input dict vs backend vs output dict, materials used, output dict vs Output Dock, CAD vs design, girder layout vs a fresh session, report vs output dict |
| `replay.py` | runs the backend headless on a captured `input_dict.json` |
| `probes/` | root-cause probes for the reported bugs (outputs in `probes/output/`) |
| `export_osi.py` | writes every case as an `.osi` file to `osi/` and re-validates it |
| `evidence_shots.py`, `demo_video.py` | issue screenshots; silent screencast `results/demo/osdagbridge_testing_demo.mp4` |
| `issues/` | text of the GitHub issues and comments that were filed |
| `report/` | LaTeX source and PDF of the testing report |

## Evidence per case: `results/<session>/<case>/`
`ui.json` (widget values) · `input_dict.json` (dict handed to `set_input`) · `backend_input.json` ·
`output_dict.json` · `material_props.json` (what the analysis used) · `dock.json` (Output Dock bars,
*Design Envelope*, every member) · `cad_params.json` (DTO given to the 3D viewer) ·
`cad_info_table.json` · `meta.json` (actions, popups, timings) · `log.txt` (log dock) ·
`window.png`, `cad3d.png`, `plots.png`, `cross_section.png`, `top_view.png`. Each session folder also
holds `cases.json` and the full `console.txt`.

## Sessions
| Session | Cases | What it exercises |
|---|---|---|
| S1 | TC01-TC04 | 4 consecutive runs: span 30/40/40/20 m, skew 0/10/-12/15, footpath, median, DB grades E 250A/E 300A/E 410A/M30, report |
| S2 | TC05-TC08 | custom steel for girder, cross bracing and end diaphragm, custom deck concrete, custom -> DB -> custom switching |
| S3 | TC09-TC11 | Custom design mode: unsymmetric girder, stiffeners, deck 230/260 mm, studs, covers, report |
| S4 | TC12-TC16 | validation: empty required fields, span/carriageway/skew limits, out-of-range custom steel |
| S5, S6 | TC17-TC20 | controls for girder-layout carry-over between runs |

Run everything: `python campaign.py S1 S2 S3 S4 S5 S6 && python verify.py && python export_osi.py`.
