"""OsdagBridge GUI test campaign — consecutive design runs driven through the real desktop UI.

    python campaign.py S1 [S2 ...]

Each session starts a fresh application; its cases run back to back in that window
(unlock -> edit -> Design), so state carried between runs is exercised. Evidence for
every case lands in results/<session>/<case>/ (see gui_driver.py) and the case
definitions in results/<session>/cases.json.
"""
import json
import sys
import traceback
from pathlib import Path

RESULTS = Path(__file__).parent / "results"


def sessions():
    from osdagbridge.core.utils import common as C

    def steel(density, fy, fu, e, nu, thermal):
        return {C.KEY_MATERIAL_GIRDER_DENSITY: density, C.KEY_MATERIAL_GIRDER_FY: fy, C.KEY_MATERIAL_GIRDER_FU: fu,
                C.KEY_MATERIAL_GIRDER_E: e, C.KEY_MATERIAL_GIRDER_POISSON: nu, C.KEY_MATERIAL_GIRDER_THERMAL: thermal}

    def deck(density, fck, fctm, ecm, thermal):
        return {C.KEY_MATERIAL_DECK_DENSITY: density, C.KEY_MATERIAL_DECK_FCK: fck, C.KEY_MATERIAL_DECK_FCTM: fctm,
                C.KEY_MATERIAL_DECK_ECM: ecm, C.KEY_MATERIAL_DECK_THERMAL: thermal}

    S, CW, SK = C.KEY_SPAN, C.KEY_CARRIAGEWAY_WIDTH, C.KEY_SKEW_ANGLE
    G, CB, ED, DK = C.KEY_GIRDER, C.KEY_CROSS_BRACING, C.KEY_END_DIAPHRAGM, C.KEY_DECK_CONCRETE_GRADE_BASIC
    girder = {  # Custom-mode section (mm), applied to every girder with the two "Apply" buttons
        C.KEY_MP_GIRDER_SYMMETRY: "Girder Unsymmetric", C.KEY_MP_GIRDER_DEPTH: 1800,
        C.KEY_MP_GIRDER_TOP_FLANGE_WIDTH: 450, C.KEY_MP_GIRDER_TOP_FLANGE_THICKNESS: 25,
        C.KEY_MP_GIRDER_BOTTOM_FLANGE_WIDTH: 550, C.KEY_MP_GIRDER_BOTTOM_FLANGE_THICKNESS: 32,
        C.KEY_MP_GIRDER_WEB_THICKNESS: 14,
    }
    apply_all = ("Apply changes to exterior girders", "Apply changes to interior girders")
    stiff = {C.KEY_MP_STIFFENER_INTERMEDIATE: "Yes", C.KEY_MP_STIFFENER_INTERMEDIATE_SPACING: 1800,
             C.KEY_MP_STIFFENER_INTERMEDIATE_THICKNESS: 12, C.KEY_MP_STIFFENER_INTERMEDIATE_OUTSTAND: 150,
             C.KEY_MP_STIFFENER_BEARING_THICKNESS: 16, C.KEY_MP_STIFFENER_BEARING_OUTSTAND: 200}
    deck_opts = {C.KEY_TS_DECK_THICKNESS: 230, C.KEY_WC_THICKNESS: 65, C.KEY_DS_STUD_DIAMETER: 22,
                 C.KEY_DS_STUD_HEIGHT: 120, C.KEY_DS_BOTTOM_CLEAR_COVER: 40}

    return {
        "S1": dict(title="Basic geometry sweep with database grades, 4 consecutive runs",
                   location=("Gujarat", "Ahmedabad"), cases=[
            dict(id="TC01", title="Baseline: 30 m span, 7.5 m carriageway, defaults",
                 text={S: 30, CW: 7.5, SK: 0}, report=True),
            dict(id="TC02", title="Unlock: span 40 m, skew 10 deg, footpath on one side", unlock=True,
                 text={S: 40, SK: 10}, combo={C.KEY_FOOTPATH: "Single Side"}),
            dict(id="TC03", title="Unlock: 11 m carriageway each way, median, footpaths both sides, skew -12",
                 unlock=True, text={CW: 11, SK: -12},
                 combo={C.KEY_INCLUDE_MEDIAN: "Yes", C.KEY_FOOTPATH: "Both Sides"}),
            dict(id="TC04", title="Unlock: limits span 20 m / skew 15 deg; grades E 250A/E 300A/E 410A, M30",
                 unlock=True, text={S: 20, CW: 7.5, SK: 15},
                 combo={C.KEY_INCLUDE_MEDIAN: "No", C.KEY_FOOTPATH: "None",
                        G: "E 250A", CB: "E 300A", ED: "E 410A", DK: "M30"}),
        ]),
        "S2": dict(title="Custom materials for girder, cross bracing, end diaphragm and deck, 4 consecutive runs",
                   location=("Tamil Nadu", "Chennai (Minambakkam) (A)"), cases=[
            dict(id="TC05", title="Custom steel for all three steel members + custom deck concrete",
                 text={S: 25, CW: 7.5, SK: 5},
                 material={G: steel(78.5, 345, 480, 205, 0.3, 12.0), CB: steel(77.0, 260, 410, 200, 0.3, 11.7),
                           ED: steel(76.9, 300, 440, 200, 0.3, 11.7), DK: deck(25.5, 42, 3.2, 33.5, 10.5)}),
            dict(id="TC06", title="Unlock: new custom girder steel (410/540, E 210), deck back to M35",
                 unlock=True, material={G: steel(80.0, 410, 540, 210, 0.3, 12.0)}, combo={DK: "M35"}),
            dict(id="TC07", title="Unlock: girder from custom back to database grade E 350A",
                 unlock=True, combo={G: "E 350A"}),
            dict(id="TC08", title="Unlock: re-select custom_steel_410_540 for girder; new cross-bracing custom "
                                  "steel with the same Fy/Fu but E 200, density 77",
                 unlock=True, combo={G: "custom_steel_410_540"},
                 material={CB: steel(77.0, 410, 540, 200, 0.3, 11.7)}),
        ]),
        "S3": dict(title="Custom design mode, custom girder section, stiffeners, deck and stud inputs, 3 runs",
                   location=("Assam", "Guwahati (Bhorjar) (A)"), cases=[
            dict(id="TC09", title="Custom section D1800 450x25/550x32 tw14, stiffeners, deck 230 mm, stud 22 mm",
                 text={S: 35, CW: 9, SK: 0}, mode="Custom",
                 additional={**girder, **stiff, **deck_opts},
                 buttons=apply_all + ("Apply changes to all custom",), report=True),
            dict(id="TC10", title="Unlock: Additional Inputs only (D 1600, deck 260 mm, stiffener spacing 1500)",
                 unlock=True, additional={C.KEY_MP_GIRDER_DEPTH: 1600, C.KEY_TS_DECK_THICKNESS: 260,
                                          C.KEY_MP_STIFFENER_INTERMEDIATE_SPACING: 1500}, buttons=apply_all),
            dict(id="TC11", title="Unlock: change only span to 38 m (Additional Inputs untouched)",
                 unlock=True, text={S: 38}),
        ]),
        "S5": dict(title="Control: girder layout when the deck width changes between runs",
                   location=("Gujarat", "Ahmedabad"), cases=[
            dict(id="TC17", title="Fresh session with the TC03 inputs (wide deck: 11 m each way, median, "
                                  "footpaths both sides, span 40, skew -12)",
                 text={S: 40, CW: 11, SK: -12}, combo={C.KEY_INCLUDE_MEDIAN: "Yes", C.KEY_FOOTPATH: "Both Sides"}),
            dict(id="TC18", title="Unlock: narrow deck with the TC01 inputs (7.5 m, no median/footpath, span 30)",
                 unlock=True, text={S: 30, CW: 7.5, SK: 0},
                 combo={C.KEY_INCLUDE_MEDIAN: "No", C.KEY_FOOTPATH: "None"}),
        ]),
        "S6": dict(title="Control: girder count seeded on a wide deck, then the deck is narrowed",
                   location=("Gujarat", "Ahmedabad"), cases=[
            dict(id="TC19", title="Median and both footpaths selected first, then span 40, carriageway 11",
                 first_combo={C.KEY_INCLUDE_MEDIAN: "Yes", C.KEY_FOOTPATH: "Both Sides"},
                 text={S: 40, CW: 11, SK: 0}),
            dict(id="TC20", title="Unlock: narrow deck (7.5 m, no median/footpath, span 30) and Design",
                 unlock=True, text={S: 30, CW: 7.5},
                 combo={C.KEY_INCLUDE_MEDIAN: "No", C.KEY_FOOTPATH: "None"}),
        ]),
        "S4": dict(title="Input validation (no design runs)", location=None, cases=[
            dict(id="TC12", title="Design with empty required fields"),
            dict(id="TC13", title="Span below/above limits: 19, 46", probe_text=[(S, 19), (S, 46)], design=False),
            dict(id="TC14", title="Carriageway below/above limits: 4.0, 24; 7.0 with median",
                 probe_text=[(CW, 4.0), (CW, 24)], probe_median=7.0, design=False),
            dict(id="TC15", title="Skew beyond +/-15: 20, -20", probe_text=[(SK, 20), (SK, -20)], design=False),
            dict(id="TC16", title="Custom steel out of range: Fy 1300, density 30",
                 material={G: steel(30, 1300, 1400, 200, 0.3, 11.7)}, design=False),
        ]),
    }


def run_session(name: str, spec: dict):
    from gui_driver import Driver
    from osdagbridge.core.utils import common as C

    out = RESULTS / name
    d = Driver(out)
    (out / "cases.json").write_text(json.dumps(spec, indent=1, default=str), encoding="utf-8")
    if spec["location"]:
        d.location(*spec["location"])
    for case in spec["cases"]:
        actions = {}
        try:
            if case.get("unlock"):
                d.unlock()
            for key, value in case.get("first_combo", {}).items():
                d.set_combo(key, value)
            for key, value in case.get("text", {}).items():
                d.set_text(key, value)
            for key, value in case.get("probe_text", []):          # validation probes: value -> corrected
                d.set_text(key, value)
                actions.setdefault("probe", []).append({"key": key, "typed": value, "shown": d.w(key).text()})
            if "probe_median" in case:
                d.set_combo(C.KEY_INCLUDE_MEDIAN, "Yes")
                d.set_text(C.KEY_CARRIAGEWAY_WIDTH, case["probe_median"])
                actions.setdefault("probe", []).append({"key": C.KEY_CARRIAGEWAY_WIDTH, "typed": case["probe_median"],
                                                        "median": "Yes", "shown": d.w(C.KEY_CARRIAGEWAY_WIDTH).text()})
            for key, value in case.get("combo", {}).items():
                d.set_combo(key, value)
            for key, props in case.get("material", {}).items():
                actions.setdefault("custom_material", {})[key] = d.custom_material(key, props)
            if case.get("mode"):
                d.set_combo(C.KEY_DESIGN_MODE, case["mode"])          # opens Additional Inputs by design
                if not case.get("additional"):
                    d.win._additional_inputs_dialog.close()
            if case.get("additional"):
                actions["additional"] = d.additional(case["additional"], case.get("buttons", ()))
            if case.get("design", True):
                actions["design"] = d.design()
        except Exception:
            actions["driver_error"] = traceback.format_exc()
        run_dir = d.capture(case["id"], actions)
        if case.get("report") and d.win.backend.output_dict:
            actions["report"] = d.report(run_dir / "report" / f"{case['id']}_report.pdf")
            (run_dir / "meta.json").write_text(json.dumps(actions, indent=1, default=str), encoding="utf-8")
        print(f"[{name}] {case['id']}: {json.dumps(actions.get('design', actions.get('probe', '-')), default=str)[:300]}",
              file=sys.__stderr__, flush=True)


def main():
    all_sessions = sessions()
    for name in sys.argv[1:] or list(all_sessions):
        run_session(name, all_sessions[name])


if __name__ == "__main__":
    main()
