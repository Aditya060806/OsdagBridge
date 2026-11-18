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
    body = "\n".join(" & ".join(esc(c) for c in row) + r" \\" for row in rows)
    return (f"\\begin{{tabular}}{{{cols}}}\n\\toprule\n" + " & ".join(rf"\textbf{{{h}}}" for h in head)
            + " \\\\\n\\midrule\n" + body + "\n\\bottomrule\n\\end{tabular}\n")


def emit(cases: list):
    GEN.mkdir(parents=True, exist_ok=True)
    designed = [c for c in cases if c["designed"]]
    flag = lambda ok: "OK" if ok else "MISMATCH"
    (GEN / "dict_consistency.tex").write_text(tabular(
        "llllll", ["Case", "UI = input\\_dict", "input = backend = output", "Materials used", "Output = Dock", "CAD girder"],
        [[c["case"], flag(not c["ui_mismatch"]), flag(not c["dict_mismatch"]),
          ", ".join(m["property"].split(" (")[0] for m in c["materials"] if not m["ok"]) or "OK",
          ", ".join(c["util_mismatch"]) or "OK", flag(c.get("cad", {}).get("girder_ok", True))] for c in designed]),
        encoding="utf-8")
    (GEN / "layout.tex").write_text(tabular(
        "lrrrrrl", ["Case", "Girders", "Spacing (m)", "Overhang (m)", "Fresh session", "Lines checked", "Controlling"],
        [[c["case"], c["layout"]["girders"], c["layout"]["spacing_m"], c["layout"]["overhang_m"],
          c["layout"]["fresh_session_girders"], c["layout"]["lines_checked"], c["layout"]["controlling"]] for c in designed]),
        encoding="utf-8")
    (GEN / "util.tex").write_text(tabular(
        "l" + "r" * 8, ["Case"] + ["Flex", "Shear", "Inter", "LTB", "LongSh", "Fatigue", "Stress", "Defl"],
        [[c["case"]] + [f"{c['util'][u]['output_dict']:.1f} / {c['util'][u]['dock_max']:.1f}"
                        if c["util"][u]["dock_max"] is not None else f"{c['util'][u]['output_dict']:.1f} / --"
                        for u in UTIL] for c in designed]), encoding="utf-8")
    (GEN / "cad.tex").write_text(tabular(
        "llllll", ["Case", "Girder designed (mm)", "Girder drawn (mm)", "CB spacing in/drawn (m)", "CB section designed / drawn",
                   "Width info/layout (m)"],
        [[c["case"], "x".join(f"{v:.0f}" for v in c["cad"]["girder_designed_mm"]),
          "x".join(f"{v:.0f}" for v in c["cad"]["girder_drawn_mm"]),
          f"{esc(c['cad']['cb_spacing_input_m'])} / {c['cad']['cb_spacing_drawn_m']:.1f}",
          f"{c['cad']['cb_designed_section']} / {c['cad']['cb_drawn']}",
          f"{c['cad']['info_width_m']} / {c['cad']['layout_width_m']}"] for c in designed if "cad" in c]),
        encoding="utf-8")


def multirun(cases: list) -> list:
    """Consecutive runs in one session: did every graphical output change, and is the CAD
    info table showing this run's span?"""
    rows = []
    for prev, cur in zip(cases, cases[1:]):
        if prev["session"] != cur["session"] or not (prev["designed"] and cur["designed"]):
            continue
        changed = {n: cur["images"][n] is not None and cur["images"][n] != prev["images"][n] for n in cur["images"]}
        rows.append({"session": cur["session"], "from": prev["case"], "to": cur["case"], **changed,
                     "info_span_ok": cur.get("cad", {}).get("info_span_ok"),
                     "cad_rendered": (RESULTS / cur["session"] / cur["case"] / "cad3d.png").stat().st_size > 20_000})
    return rows


def main():
    cases = [check_case(d) for s in sorted(RESULTS.glob("S*")) for d in sorted(s.glob("TC*")) if d.is_dir()]
    runs = multirun(cases)
    (RESULTS / "multirun.json").write_text(json.dumps(runs, indent=1), encoding="utf-8")
    (GEN / "multirun.tex").parent.mkdir(parents=True, exist_ok=True)
    yn = lambda v: "yes" if v else "NO"
    (GEN / "multirun.tex").write_text(tabular(
        "lllllll", ["Session", "Run", "3D CAD shown", "3D changed", "Plots changed", "2D views changed", "CAD span = input"],
        [[r["session"], f"{r['from']} to {r['to']}", yn(r["cad_rendered"]), yn(r["cad3d"]), yn(r["plots"]),
          yn(r["cross_section"] and r["top_view"]), yn(r["info_span_ok"])] for r in runs]), encoding="utf-8")
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
