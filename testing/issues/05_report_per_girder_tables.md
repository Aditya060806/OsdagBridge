[Bug] Report per-girder tables (5.1-5.6) repeat the controlling girder's values for every girder; util.* report only that girder, hiding a 32 % higher shear

### What happens
Chapter 5 of the design report has one block per girder (G1-G4) in Tables 5.1-5.6. Every block prints the **same numbers**: those of the single "controlling girder", which is the line with the highest overall DCR (fatigue for the default bridge). The `util.*` values in the output dictionary, the Executive Summary and the Ch. 5 utilisation ratios also describe only that girder, category by category.

For any check other than the governing one, a different girder can be worse. The report never shows it:

| Default bridge (TC01) | Report Table 5.4 | `design_results.per_girder` | Output Dock (*Design Envelope*) |
|---|---|---|---|
| Applied shear Vu, exterior girder | 288.29 kN (all four rows) | **379.98 kN** (G2/G5 lines) | Shear **53 %** for G2 |
| Shear UR | 0.40 (all four rows) | | 40 % for G3 |
| `util.shear` | 40.03 % | | worst girder 52.76 % |
| Applied moment Mu (Table 5.3) | 2224.95 kN·m (all rows) | 2181.62 / 2224.95 / 2224.95 / 2181.62 (girder lines 2-5) | |

So the report understates the worst shear demand by 32 % (379.98 / 288.29), while the dock shows it correctly for the same run. Custom mode (TC09) shows the same pattern: report Vu 383.37 kN in every row against 517.22 kN on the exterior lines. Report shear UR is 0.16 against a dock worst of 22 %.

### Environment
Windows 11, Python 3.12.16 (conda env from `environment.yml`), `dev` @ `d74f56d`, source unmodified. The GUI was driven by [`testing/gui_driver.py`]({REPO}/testing/gui_driver.py), and the report was generated through Output Dock > Generate Report > Save PDF.

### Steps to reproduce
Ahmedabad, Span 30, Carriageway 7.5, defaults. Design, then Generate Report. In Chapter 5 compare the G1-G4 blocks of Tables 5.3 and 5.4 with each other and with `output_dict["design_results"]["per_girder"][g]["demand"]`, or with the Output Dock for each member under *Design Envelope*.

### Evidence
* Report and TeX: [`TC01_report.pdf`]({REPO}/testing/results/S1/TC01/report/TC01_report.pdf), [`TC01_report.tex`]({REPO}/testing/results/S1/TC01/report/TC01_report.tex) (lines 1160-1255). Output dict: [`S1/TC01/output_dict.json`]({REPO}/testing/results/S1/TC01/output_dict.json). Dock values for every member: [`S1/TC01/dock.json`]({REPO}/testing/results/S1/TC01/dock.json).
* Comparison of report rows vs `per_girder` for TC01 and TC09: [`verification.json`]({REPO}/testing/results/verification.json) (`report` entries), produced by [`verify.py`]({REPO}/testing/verify.py).

![report Table 5.3/5.4]({RAW}/testing/results/evidence/report_shear_table.png)

### Root cause
* [`chap5.py#L170-L260`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/reports/chap5.py#L170-L260): the per-girder loops (`for lbl, _ in girder_entries:`) render scalar keys such as `KEY_SD_MU_APPLIED`, `KEY_SD_SHEAR_VU`, `KEY_SD_TOTAL_DEPTH` and `KEY_UTIL_SHEAR`, which do not depend on `lbl`.
* Those scalars are written once by `store_design_results()` from the controlling girder ([`plategirderbridge.py#L4102-L4109`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py#L4102-L4109), [`L4196`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py#L4196), [`L4209`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py#L4209)). The controlling girder is chosen by overall max DCR ([`designer.py#L3363`](https://github.com/Nidhikhare12/OsdagBridge/blob/d74f56dd7f22925fb8148cabf5740ed8d1e39ff3/src/osdagbridge/core/bridge_types/plate_girder/designer.py#L3363)).

### Suggested fix
1. Build each per-girder row from that girder's own results, which already exist in `design_results["per_girder"]` (demand plus checks with id, demand, capacity and dcr):

```python
# chap5.py, e.g. Table 5.4
pg = bridge.output_dict["design_results"]["per_girder"]
for lbl, line in girder_lines(girder_entries):          # physical girder -> grillage line (see #113)
    g = pg[line]
    shear = max((c for c in g["checks"] if c["check_id"] == 2), key=lambda c: c["dcr"])
    vu, ur = g["demand"]["Vu_kN"], shear["dcr"]
    ...
```
2. Write `util.<category>` as the maximum over girders of each category, and keep the controlling girder for the governing check only:

```python
# plategirderbridge.py, store_design_results()
per = dr["per_girder"].values()
worst = lambda cat: max((g["category_urs"].get(cat, {}).get("max_dcr", 0.0) for g in per), default=0.0)
out[KEY_UTIL_SHEAR] = worst(2) * 100   # likewise for categories 1 and 3-8
```

The per-girder label mapping has to account for the deck-edge lines described in #113: `per_girder` has n + 2 entries when the overhang is positive.

### Duplicate check
I checked all open and closed issues on 17 Nov 2026. #103 covers the Material Take-off using G1's area for every girder (Chapter 7), #113 the edge lines being designed as girders, and #114 the two deflection sets. None covers the Chapter 5 per-girder tables repeating the controlling girder, or `util.*` understating non-governing categories.
