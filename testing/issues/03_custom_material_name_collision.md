[Bug] Two custom steels with the same Fy/Fu share one name: creating the second silently overwrites the first member's E and density at the next Design

### What happens
Custom steel names are built only from Fy and Fu (`custom_steel_410_540`). Suppose the girder and the cross bracing get custom steels with the same Fy/Fu but different E or density. Both are stored under one name in `InputDock._material_custom_fields`, and the second entry replaces the first. On the next Design, `_prime_material_inputs()` re-applies the stored entry to every member showing that name, so the **girder silently takes the cross bracing's E and density**. The UI shows no warning, and both combos show the same name.

It works when every custom steel has a distinct Fy/Fu pair. It fails as soon as two pairs coincide. A modulus of 200 vs 210 GPa at the same strength is a realistic case.

### Environment
Windows 11, Python 3.12.16 (conda env from `environment.yml`), `dev` @ `d74f56d`, source unmodified. The GUI was driven by [`testing/gui_driver.py`]({REPO}/testing/gui_driver.py), which types into the real *Enter Custom Properties* dialog. Session S2, consecutive runs TC06 to TC08.

### Steps to reproduce (one session)
1. Location Chennai (Minambakkam), Span 25, Carriageway 7.5. Girder > **Custom**: Fy 410, Fu 540, **E 210**, **density 80**. The dialog names it `custom_steel_410_540`. Design (TC06).
2. Unlock, set the girder to E 350A, Design (TC07).
3. Unlock, select `custom_steel_410_540` for the girder again. Cross Bracing > **Custom**: Fy 410, Fu 540, **E 200**, **density 77**. The dialog again names it `custom_steel_410_540`. Design (TC08).

### Expected / actual (input dict after Design, and what the analysis used)
| | Expected (girder) | Actual TC08 girder | TC08 cross bracing |
|---|---:|---:|---:|
| `material.girder.e` / analysis `steel_prop.E` | 210 GPa | **200 GPa** | 200 GPa |
| `material.girder.density` | 80 | **77.0** | 77.0 |
| `material.girder.g` | 80.8 | **76.9** | 76.9 |
| combo text | | `custom_steel_410_540` | `custom_steel_410_540` |

In TC06 the same girder material gave E = 210 GPa in both the input dict and `material_props`. In TC08 the girder analysis ran with E = 200 GPa, so its stiffness and deflection changed without any input change on the girder.

### Evidence
* Material values typed in the dialog vs dictionaries vs `material_props`, per run: [`S2/TC06/meta.json`]({REPO}/testing/results/S2/TC06/meta.json), [`S2/TC06/input_dict.json`]({REPO}/testing/results/S2/TC06/input_dict.json), [`S2/TC06/material_props.json`]({REPO}/testing/results/S2/TC06/material_props.json), [`S2/TC08/meta.json`]({REPO}/testing/results/S2/TC08/meta.json), [`S2/TC08/input_dict.json`]({REPO}/testing/results/S2/TC08/input_dict.json), [`S2/TC08/material_props.json`]({REPO}/testing/results/S2/TC08/material_props.json).
* Case definitions: [`S2/cases.json`]({REPO}/testing/results/S2/cases.json). Full console: [`S2/console.txt`]({REPO}/testing/results/S2/console.txt).

```text
TC06 girder  input_dict={'density': '80.0', 'fy': '410', 'fu': '540', 'e': '210', 'g': '80.8', ...}  steel_prop E=210 GPa
TC08 girder  input_dict={'density': '77.0', 'fy': '410', 'fu': '540', 'e': '200', 'g': '76.9', ...}  steel_prop E=200 GPa
```

### Root cause
* [`material_properties.py#L672-L689`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/desktop/ui/dialogs/material_properties.py#L672-L689) (`_update_custom_material_name`): the name depends on Fy and Fu only.
* [`input_dock.py#L736`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/desktop/ui/docks/input_dock.py#L736): `self._material_custom_fields[mat] = ...` is keyed by that name, so the second material replaces the first.
* [`input_dock.py#L324-L345`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/desktop/ui/docks/input_dock.py#L324-L345) (`_prime_material_inputs`, called on every Design at [`template_page.py#L636`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/desktop/ui/template_page.py#L636)) re-exports `_material_custom_fields[selected]` into every member's `material.<member>.*` keys.

### Suggested fix
Give a material with different properties a distinct name instead of overwriting the stored one:

```python
# input_dock.py, _on_material_changed(), after the dialog is accepted
fields = dict(fd.get("fields") or {})
stored = self._material_custom_fields.get(mat)
if stored is not None and stored != fields:          # same Fy/Fu, different E / density / ...
    n = 2
    while f"{mat}_{n}" in self._material_custom_fields:
        n += 1
    mat = f"{mat}_{n}"                               # e.g. custom_steel_410_540_2
self._material_custom_fields[mat] = fields
```

Then let the name-parsing regex in `MaterialPropertiesDialog._load_material_info_for_view()` accept the optional suffix (`...([0-9.]+)_([0-9.]+)(?:_\d+)?$`). An alternative is to warn and ask before overwriting an existing name.

### Duplicate check
I checked all open and closed issues on 17 Nov 2026. #19 covers `_material_custom_fields` not being rebuilt after OSI load, #118 the missing cross-field validation, and #125 custom grades kept on cross bracing and end diaphragm. None covers two members colliding under one generated name within a session.
