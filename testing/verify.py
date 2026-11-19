"""Cross-check the evidence captured by campaign.py and emit report tables.

    python verify.py            # reads results/S*/TC*/, writes results/verification.json
                                # and report/generated/*.tex

Checks per design case
  ui      : input-dock text == GUI input_dict == backend input_dict == output_dict
  mat     : material values in input_dict == values the analysis/design used
  dock    : output_dict util.* == Output Dock bars ("Design Envelope", worst girder)
  cad     : 3D CAD parameters == designed girder / input stiffeners / input bracing spacing
  layout  : girder count == count a fresh session derives from the same basic inputs
  report  : report .tex values == output_dict (cases with a report)
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
RESULTS, GEN = HERE / "results", HERE / "report" / "generated"
UI_KEYS = ["geometry.span", "geometry.carriageway_width", "geometry.skew_angle", "geometry.include_median",
           "geometry.footpath", "geometry.design_mode", "material.girder", "material.cross_bracing",
           "material.end_diaphragm", "material.deck"]
UTIL = ["flexure", "shear", "interaction", "ltb", "long_trans_shear", "fatigue", "stress_limitation",
        "deflection_crack"]
GD = "member_properties.girder_details.section_input."
WET_CONCRETE_DENSITY = 25.0   # analyser default when create_deck_load() gets no density (see #41)


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def same(a, b, tol=1e-6):
    fa, fb = num(a), num(b)
    if fa is not None and fb is not None:
        return abs(fa - fb) <= tol * max(1.0, abs(fa), abs(fb))
    norm = lambda v: "" if v in (None, "None") else str(v).strip()
    return norm(a) == norm(b)


def fresh_girder_count(ui: dict) -> int | None:
    """Girder count a fresh session derives from these basic inputs (no editing history)."""
    from osdagbridge.core.bridge_types.plate_girder.defaults import BASIC_INPUT_DICT, solve_extend_basic_input_dict
    d = dict(BASIC_INPUT_DICT)
    d.update({k: v for k, v in ui.items() if v not in ("", None)})
    try:
        solve_extend_basic_input_dict(d)
        return int(d["typical_section.no_of_girders"])
    except Exception:
        return None


def report_values(tex: Path) -> dict:
    t = tex.read_text(encoding="utf-8")
    grab = lambda pat: [float(x) for x in re.findall(pat, t)]
    return {
        "overall_ur": grab(r"Overall Utilization Ratio \(max\)\} & ([\d.]+)")[:1],
        "Mu_rows": grab(r"Applied Moment, \$M_u\$ & Governing LC \(ULS\) & ([\d.]+) kN-m"),
        "Vu_rows": grab(r"Applied Shear, \$V_u\$ & Governing LC \(ULS\) & ([\d.]+) kN"),
        "shear_ur_rows": grab(r"Utilization Ratio, \$V_u / V_d\$ & \$V_u / V_d\$ & ([\d.]+)"),
        "fatigue_ur_rows": grab(r"Fatigue Normal Stress & [\d.]+ MPa & [\d.]+ MPa & ([\d.]+)"),
    }


def digest(p: Path) -> str | None:
    import hashlib
    return hashlib.md5(p.read_bytes()).hexdigest() if p.exists() else None


def check_case(d: Path) -> dict:
    ui, inp, be, out = (load(d / f"{n}.json") for n in ("ui", "input_dict", "backend_input", "output_dict"))
    meta, dock, mp, cad = (load(d / f"{n}.json") for n in ("meta", "dock", "material_props", "cad_params"))
    info = load(d / "cad_info_table.json")
    r = {"case": d.name, "session": d.parent.name, "designed": bool(out), "meta": meta,
         "popups_seen": load(d / "popups.json") or [],
         "images": {n: digest(d / f"{n}.png") for n in ("cad3d", "plots", "cross_section", "top_view")},
         "ui_mismatch": [k for k in UI_KEYS if k in ui and not (same(ui[k], inp.get(k)) or
                                                              (ui[k] == "" and inp.get(k) is None))]}
    if not out:
        return r
    r["dict_mismatch"] = [k for k in UI_KEYS if not (same(inp.get(k), be.get(k)) and same(be.get(k), out.get(k)))]
    n = int(out["typical_section.no_of_girders"])
    dr = out.get("design_results", {})
    r["layout"] = {"girders": n, "spacing_m": out["typical_section.girder_spacing"],
                   "overhang_m": out["typical_section.deck_overhang"], "fresh_session_girders": fresh_girder_count(ui),
                   "lines_checked": len(dr.get("per_girder", {})), "controlling": dr.get("controlling_girder")}

    # Materials: dictionary value vs value the analysis / design used (SI in material_props).
    s, c = mp.get("steel_prop", {}), mp.get("concrete_prop", {})
    pairs = [("girder E (GPa)", inp.get("material.girder.e"), s.get("E", 0) / 1e9),
             ("girder Fy (MPa)", inp.get("material.girder.fy"), s.get("Fy", 0) / 1e6),
             ("girder Fu (MPa)", inp.get("material.girder.fu"), s.get("Fu", 0) / 1e6),
             ("girder density (kN/m3)", inp.get("material.girder.density"), s.get("rho", 0) / 1e3),
             ("deck fck (MPa)", inp.get("material.deck.fck"), c.get("fck")),
             ("deck Ecm (GPa)", inp.get("material.deck.ecm"), c.get("Ecm")),
             # add_dead_loads() calls create_deck_load() without a density, so the analyser constant applies.
             ("deck density (kN/m3)", inp.get("material.deck.density"), WET_CONCRETE_DENSITY)]
    r["materials"] = [{"property": p, "input_dict": a, "used": round(b, 3) if b is not None else None,
                       "ok": same(a, b, 1e-3)} for p, a, b in pairs]

    # Output dictionary vs Output Dock (worst girder, "Design Envelope").
    r["util"] = {}
    for u in UTIL:
        raw = [g["get_dcr_for_selection"].get(f"util.{u}") for g in dock.values()]
        raw = [v for v in raw if v is not None]
        r["util"][u] = {"output_dict": round(out.get(f"util.{u}", 0.0), 2), "dock_max": round(max(raw), 2) if raw else None}
    r["util_mismatch"] = [u for u, v in r["util"].items()
                          if v["dock_max"] is not None and abs(v["output_dict"] - v["dock_max"]) > 1.0]

    # 3D CAD parameters vs design.
    if cad:
        designed = (dr.get("D_mm"), dr.get("bf_top_mm"), dr.get("tf_top_mm"), dr.get("bf_bot_mm"), dr.get("tf_bot_mm"), dr.get("tw_mm"))
        drawn = (cad["girder_section_d"], cad["girder_section_bf"], cad["girder_section_tf"], cad["girder_section_bf_b"],
                 cad["girder_section_tf_b"], cad["girder_section_tw"])
        cb_in = out.get("member_properties.cross_bracing_details.spacing.G1G2.B1M1")
        cb_design = (out.get("crossbracing_design_results", {}).get("G1-G2", {}).get("diagonal", {})
                     .get("tension", {}).get("section_size.designation"))
        r["cad"] = {"girder_designed_mm": designed, "girder_drawn_mm": drawn, "girder_ok": all(same(a, b) for a, b in zip(designed, drawn)),
                    "span_ok": same(cad["span_length_L"] / 1e3, out["geometry.span"]),
                    "girders_ok": same(cad["num_girders"], n),
                    "cb_spacing_input_m": cb_in, "cb_spacing_drawn_m": cad["cross_bracing_spacing"] / 1e3,
                    "cb_designed_section": cb_design,
                    "cb_drawn": f"{cad['diagonal_section_type']} {cad['diagonal_section_dims']['leg_h']:.0f}x"
                                f"{cad['diagonal_section_dims']['leg_w']:.0f}x{cad['diagonal_thickness']:.0f}",
                    "info_span_ok": same(info.get("span_length"), out["geometry.span"], 1e-3),
                    "info_width_m": num(info.get("bridge_width")),
                    "layout_width_m": round(out["typical_section.girder_spacing"] * (n - 1) + 2 * out["typical_section.deck_overhang"], 3)}

    tex = next((d / "report").glob("*.tex"), None) if (d / "report").exists() else None
    if tex:
        rv = report_values(tex)
        pg = dr.get("per_girder", {})
        r["report"] = {**rv, "per_girder_Vu": {g: v["demand"]["Vu_kN"] for g, v in pg.items()},
                       "per_girder_Mu": {g: v["demand"]["Mu_kNm"] for g, v in pg.items()},
                       "output_max_util": round(max(out.get(f"util.{u}", 0) for u in UTIL) / 100, 2)}
    return r


# ── LaTeX emitters ───────────────────────────────────────────────────────────
def esc(v) -> str:
    s = "--" if v in (None, "") else (f"{v:.4g}" if isinstance(v, float) else str(v))
    return re.sub(r"([_%&#$])", r"\\\1", s)


def tabular(cols: str, head: list, rows: list) -> str:
    """Booktabs tabular. Header cells are raw LaTeX; body cells are escaped."""
    body = "\n".join(" & ".join(esc(c) for c in row) + r" \\" for row in rows)
    return (f"\\begin{{tabular}}{{{cols}}}\n\\toprule\n" + " & ".join(rf"\textbf{{{h}}}" for h in head)
            + " \\\\\n\\midrule\n" + body + "\n\\bottomrule\n\\end{tabular}\n")


SHORT = {"geometry.span": "span", "geometry.carriageway_width": "cw", "geometry.skew_angle": "skew",
         "geometry.include_median": "median", "geometry.footpath": "footpath", "material.girder": "girder",
         "material.cross_bracing": "CB", "material.end_diaphragm": "ED", "material.deck": "deck",
         "density": "rho", "fy": "Fy", "fu": "Fu", "e": "E", "g": "G", "poisson": "nu", "thermal": "alpha", "ecm": "Ecm"}
# Analyst notes per case (issue numbers); #89/#112/#147 tags are added automatically from the data.
NOTES = {
    "TC01": "#148 deck SLS; #151 report tables; #66 Table 2.7 units",
    "TC03": "27.85 m deck on 4 girders, shear 188 %; CAD legend width 26.45 m (#124)",
    "TC04": "span/skew limits 20 m / 15 deg accepted",
    "TC05": "custom Fy/Fu/E reach analysis; densities not used (#20, #41); CB/ED grades unused (#43)",
    "TC06": "density 80 ignored (#20)", "TC07": "custom to database grade: OK",
    "TC08": "name collision: girder E 210 to 200, rho 80 to 77 (#149)",
    "TC09": "custom section, stiffeners, deck, studs reach design and CAD; #148, #151",
    "TC10": "Additional Inputs survive unlock; design and CAD agree",
    "TC11": "deck 260 to 250, stud 22 to 20, cover 40 to 50 (#71); CAD draws 2120 mm girder (#150)",
    "TC12": "blocked, empty fields listed (expected)", "TC13": "clamped with warning (expected)",
    "TC14": "clamped with warning (expected)", "TC15": "clamped with warning (expected)",
    "TC16": "clamped with warning (expected)",
    "TC19": "live load dropped, all demands 0, PASS (#134); util 0.0 (#45)",
}


def short(key: str) -> str:
    return SHORT.get(key, SHORT.get(key.split(".")[-1], key.split(".")[-1].replace("_", " ")))


def parameters(case: dict) -> str:
    p = []
    for group in ("first_combo", "text", "combo"):
        p += [f"{short(k)} {v}" for k, v in case.get(group, {}).items()]
    for k, props in case.get("material", {}).items():
        p.append(f"{short(k)} custom (" + ", ".join(f"{short(pk)} {v}" for pk, v in props.items()) + ")")
    p += [f"mode {case['mode']}"] if case.get("mode") else []
    p += [f"{short(k)} {v}" for k, v in case.get("additional", {}).items()]
    p += [f"typed {short(k)} {v}" for k, v in case.get("probe_text", [])]
    p += [f"median Yes, typed cw {case['probe_median']}"] if "probe_median" in case else []
    return ("after unlock: " if case.get("unlock") else "") + (", ".join(p) or "nothing entered")


def outcome(c: dict) -> str:
    if c["designed"]:
        return f"designed: {c['layout']['girders']} girders at {c['layout']['spacing_m']:.4g} m"
    probes = c["meta"].get("probe", [])
    if probes:
        return "; ".join(f"{p['typed']} shown as {p['shown']}" for p in probes)
    if c["meta"].get("custom_material"):
        names = ", ".join(v["name"] for v in c["meta"]["custom_material"].values())
        return f"saved as {names} after {len(c['popups_seen'])} range warnings"
    pops = c["meta"].get("design", {}).get("popups", []) or c["popups_seen"]
    return "no design: " + (", ".join(p["title"] for p in pops) or "--")


def findings(c: dict) -> str:
    tags = [NOTES.get(c["case"], "")]
    if c["designed"]:
        f = c["util"]["fatigue"]
        if f["dock_max"] and abs(f["output_dict"] / f["dock_max"] - 2) < 0.05:
            tags.append("#147")
        if c["layout"]["girders"] != c["layout"]["fresh_session_girders"]:
            tags.append(f"#112 (fresh: {c['layout']['fresh_session_girders']})")
        if c["layout"]["lines_checked"] == 1:
            tags.append("#89")
    return "; ".join(t for t in tags if t)


def emit_cases(cases: list):
    rows = []
    for s in sorted({c["session"] for c in cases}):
        spec = load(RESULTS / s / "cases.json")
        loc = f" ({esc(', '.join(reversed(spec['location'])))})" if spec.get("location") else ""
        rows.append(rf"\multicolumn{{4}}{{@{{}}L{{0.97\textwidth}}@{{}}}}{{\textbf{{{s}}}: {esc(spec['title'])}{loc}}} \\*")
        by_id = {k["id"]: k for k in spec["cases"]}
        for c in (c for c in cases if c["session"] == s):
            rows.append(" & ".join(esc(x) for x in (c["case"], parameters(by_id[c["case"]]), outcome(c), findings(c))) + r" \\")
    head = (r"\toprule" "\n" r"\textbf{Case} & \textbf{Exact inputs (in entry order)} & \textbf{Run} & \textbf{Findings} \\"
            "\n" r"\midrule")
    (GEN / "cases.tex").write_text(
        r"\begin{longtable}{@{}L{0.06\textwidth}L{0.42\textwidth}L{0.19\textwidth}L{0.27\textwidth}@{}}" "\n"
        r"\caption{Test cases: exact inputs in entry order, outcome of the run and findings.}\label{tab:cases}\\" "\n"
        + head + r"\endfirsthead" "\n" + head + r"\endhead" "\n"
        + "\n".join(rows) + "\n" r"\bottomrule" "\n" r"\end{longtable}" "\n", encoding="utf-8")


def emit_side_by_side():
    """UI / dialog value vs dictionaries vs value used, for one basic, one material and one custom case."""
    d = lambda s, c, n: load(RESULTS / s / c / f"{n}.json")
    # TC01: input dock vs dictionaries (plus the derived layout).
    ui, inp, be, out = (d("S1", "TC01", n) for n in ("ui", "input_dict", "backend_input", "output_dict"))
    keys = UI_KEYS + ["typical_section.no_of_girders", "typical_section.girder_spacing", "typical_section.deck_overhang",
                      "typical_section.deck_thickness"]
    (GEN / "sbs_tc01.tex").write_text(tabular("@{}llllll@{}", ["Key", "Input dock", "GUI input\\_dict", "backend input", "output\\_dict", ""],
        [[k, ui.get(k, "(derived)"), inp.get(k), be.get(k), out.get(k), "OK" if same(be.get(k), out.get(k)) else "DIFF"]
         for k in keys]), encoding="utf-8")
    # TC05: custom-material dialog vs dictionaries vs analysis.
    meta, inp, out, mp = (d("S2", "TC05", n) for n in ("meta", "input_dict", "output_dict", "material_props"))
    s, c = mp["steel_prop"], mp["concrete_prop"]
    used = {"girder": {"density": s["rho"] / 1e3, "fy": s["Fy"] / 1e6, "fu": s["Fu"] / 1e6, "e": s["E"] / 1e9,
                       "poisson": s["v"], "g": s["E"] / 1e9 / (2 * (1 + s["v"]))},   # isotropic G from E, nu
            "deck": {"fck": c["fck"], "fctm": c["fctm"], "ecm": c["Ecm"], "density": WET_CONCRETE_DENSITY}}
    rows = []
    for key, info in meta["custom_material"].items():
        member = key.split(".")[1]
        for fk, typed in info["typed"].items():
            prop = fk.split(".")[-1]
            u = used.get(member, {}).get(prop, "not used")
            rows.append([f"{member} {short(prop)}", typed, inp.get(f"material.{member}.{prop}"),
                         out.get(f"material.{member}.{prop}"), round(u, 3) if isinstance(u, float) else u,
                         "OK" if same(typed, u, 1e-3) else "DIFF"])
    (GEN / "sbs_tc05.tex").write_text(tabular("@{}llllll@{}", ["Property", "Dialog", "input\\_dict", "output\\_dict",
                                                         "Used by analysis", ""], rows), encoding="utf-8")
    # TC09: Additional Inputs (Custom mode) vs dictionaries vs designer vs 3D CAD.
    meta, inp, be, out, cad = (d("S3", "TC09", n) for n in ("meta", "input_dict", "backend_input", "output_dict", "cad_params"))
    dr, st = out["design_results"], cad["stiffeners_dict"]["0"]
    target = {"depth": (dr["D_mm"], cad["girder_section_d"]), "top flange width": (dr["bf_top_mm"], cad["girder_section_bf"]),
              "top flange thickness": (dr["tf_top_mm"], cad["girder_section_tf"]),
              "bottom flange width": (dr["bf_bot_mm"], cad["girder_section_bf_b"]),
              "bottom flange thickness": (dr["tf_bot_mm"], cad["girder_section_tf_b"]),
              "web thickness": (dr["tw_mm"], cad["girder_section_tw"]),
              "intermediate stiffener spacing": (dr.get("is_c_mm"), st["intermediate_stiffener_spacing"]),
              "intermediate stiffener thickness": (dr.get("is_tq_mm"), st["intermediate_stiffener_thickness"]),
              "bearing stiffener plate thickness": (dr.get("bs_tq_mm"), st["end_stiffener_thickness"]),
              "deck thickness": (dr["slab_thickness_mm"], cad["deck_thickness"]),
              "diameter": (dr["stud_dia_mm"], cad["shear_stud_params"]["base_diameter"]),
              "height": (dr["stud_height_mm"], cad["shear_stud_params"]["base_height"])}
    rows = []
    for k, typed in meta["additional"].items():
        name = short(k)
        if name not in target:
            continue
        gk = f"{k}.G1.M1" if f"{k}.G1.M1" in inp else k
        rows.append([name, typed, inp.get(gk), be.get(gk), out.get(gk), *target[name]])
    (GEN / "sbs_tc09.tex").write_text(tabular("@{}lllllll@{}", ["Field (mm)", "Entered", "GUI input\\_dict", "backend (SI)",
                                                          "output\\_dict", "Designer", "3D CAD"], rows), encoding="utf-8")


def emit(cases: list):
    GEN.mkdir(parents=True, exist_ok=True)
    emit_cases(cases)
    emit_side_by_side()
    designed = [c for c in cases if c["designed"]]
    flag = lambda ok: "OK" if ok else "DIFF"
    util_short = dict(zip(UTIL, ["flex", "shear", "inter", "LTB", "long.sh", "fatigue", "stress", "defl"]))
    (GEN / "dict_consistency.tex").write_text(tabular(
        "@{}llllll@{}", ["Case", "UI = input", "in = backend = out", "Not used as entered", "Output $\\ne$ Dock", "CAD girder"],
        [[c["case"], flag(not c["ui_mismatch"]), flag(not c["dict_mismatch"]),
          ", ".join(m["property"].split(" (")[0].replace("density", "rho") for m in c["materials"] if not m["ok"]) or "OK",
          ", ".join(util_short[u] for u in c["util_mismatch"]) or "OK", flag(c.get("cad", {}).get("girder_ok", True))]
         for c in designed]), encoding="utf-8")
    (GEN / "layout.tex").write_text(tabular(
        "@{}lrrrrrl@{}", ["Case", "Girders", "Spacing (m)", "Overhang (m)", "Fresh session", "Lines checked", "Controlling"],
        [[c["case"], c["layout"]["girders"], c["layout"]["spacing_m"], c["layout"]["overhang_m"],
          c["layout"]["fresh_session_girders"], c["layout"]["lines_checked"], c["layout"]["controlling"]] for c in designed]),
        encoding="utf-8")
    (GEN / "util.tex").write_text(tabular(
        "@{}l" + "r" * 8 + "@{}", ["Case"] + ["Flex", "Shear", "Inter", "LTB", "LongSh", "Fatigue", "Stress", "Defl"],
        [[c["case"]] + [f"{c['util'][u]['output_dict']:.1f} / {c['util'][u]['dock_max']:.1f}"
                        if c["util"][u]["dock_max"] is not None else f"{c['util'][u]['output_dict']:.1f} / --"
                        for u in UTIL] for c in designed]), encoding="utf-8")
    dims = lambda v: r"\texttimes ".join(f"{x:.0f}" for x in v)
    section = lambda s: str(s).replace(" x ", "x").replace("ANGLE ", "L").replace("x", r"\texttimes ")
    two = lambda a, b: rf"\makecell[l]{{{a}\\{b}}}"
    (GEN / "cad.tex").write_text(tabular(
        "@{}llllll@{}",
        ["Case", two("Girder designed", "(mm)"), two("Girder drawn", "(mm)"), two("CB spacing (m)", "input / drawn"),
         two("CB section", "designed / drawn"), two("Width (m)", "legend / layout")],
        [[c["case"], dims(c["cad"]["girder_designed_mm"]),
          "same" if c["cad"]["girder_ok"] else dims(c["cad"]["girder_drawn_mm"]),
          f"{esc(c['cad']['cb_spacing_input_m'])} / {c['cad']['cb_spacing_drawn_m']:.1f}",
          f"{section(c['cad']['cb_designed_section'])} / {section(c['cad']['cb_drawn'])}",
          f"{c['cad']['info_width_m']} / {c['cad']['layout_width_m']}"] for c in designed if "cad" in c]),
        encoding="utf-8")


def multirun(cases: list) -> list:
    """Consecutive runs in one session: did every graphical output change, and is the CAD
    info table showing this run's span?"""
    def geometry(c):           # CAD DTO without the material grades
        p = load(RESULTS / c["session"] / c["case"] / "cad_params.json")
        return {k: v for k, v in p.items() if k not in ("steel_grade", "concrete_grade")}

    rows = []
    for prev, cur in zip(cases, cases[1:]):
        if prev["session"] != cur["session"] or not (prev["designed"] and cur["designed"]):
            continue
        changed = {n: cur["images"][n] is not None and cur["images"][n] != prev["images"][n] for n in cur["images"]}
        rows.append({"session": cur["session"], "from": prev["case"], "to": cur["case"], **changed,
                     "geometry_changed": geometry(prev) != geometry(cur),
                     "info_span_ok": cur.get("cad", {}).get("info_span_ok"),
                     "cad_rendered": (RESULTS / cur["session"] / cur["case"] / "cad3d.png").stat().st_size > 20_000})
    return rows


def main():
    cases = [check_case(d) for s in sorted(RESULTS.glob("S*")) for d in sorted(s.glob("TC*")) if d.is_dir()]
    runs = multirun(cases)
    (RESULTS / "multirun.json").write_text(json.dumps(runs, indent=1), encoding="utf-8")
    (GEN / "multirun.tex").parent.mkdir(parents=True, exist_ok=True)
    yn = lambda v: "yes" if v else "NO"
    refreshed = lambda r, ok: ("yes" if ok else "NO") if r["geometry_changed"] else ("same*" if not ok else "yes")
    (GEN / "multirun.tex").write_text(tabular(
        "@{}lllllll@{}", ["Session", "Run", "Geometry changed", "3D shown", "Legend span OK", "Plots", "2D views"],
        [[r["session"], f"{r['from']} to {r['to']}", "yes" if r["geometry_changed"] else "no",
          yn(r["cad_rendered"]), yn(r["info_span_ok"]),
          refreshed(r, r["plots"]), refreshed(r, r["cross_section"] and r["top_view"])] for r in runs]), encoding="utf-8")
    (RESULTS / "verification.json").write_text(json.dumps(cases, indent=1, default=str), encoding="utf-8")
    emit(cases)
    for c in cases:
        if not c["designed"]:
            print(f"{c['session']}/{c['case']}: no design ({[p['title'] for p in c['meta'].get('design', {}).get('popups', [])]})")
            continue
        bad = {k: v for k, v in {"ui": c["ui_mismatch"], "dicts": c["dict_mismatch"],
                                 "materials": [m["property"] for m in c["materials"] if not m["ok"]],
                                 "dock": c["util_mismatch"], "cad_girder": not c.get("cad", {}).get("girder_ok", True),
                                 "layout": c["layout"]["girders"] != c["layout"]["fresh_session_girders"]}.items() if v}
        print(f"{c['session']}/{c['case']}: {c['layout']['girders']} girders @ {c['layout']['spacing_m']} m  issues={bad}")


if __name__ == "__main__":
    main()
