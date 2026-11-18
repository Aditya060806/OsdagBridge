"""Probe: Custom design mode keeps two different girders in one input dictionary.

After a required basic field (e.g. Span) changes, solve_extend_basic_input_dict()
re-seeds the *base* girder keys (member_properties.girder_details.*, no .G{n}.M1
suffix) with the initial-sizing section, while the per-girder keys keep the user's
Custom section. Consumers that call resolve_girder_value(..., i=None) read the base
key first. This replays the GUI input dict twice: as captured, and with the base
keys set equal to the user's G1.M1 values.

    python probes/probe_custom_base_keys.py results/S3/TC11/input_dict.json
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay import load, run_design  # noqa: E402

GD = "member_properties.girder_details."
gui = load(sys.argv[1])
synced = dict(gui)
for k in [k for k in gui if k.startswith(GD) and f"{k}.G1.M1" in gui]:
    synced[k] = gui[f"{k}.G1.M1"]

rows = []
for label, d in (("as captured (base keys re-seeded)", gui), ("base keys = user's G1.M1", synced)):
    b = run_design(d)
    cad, dr = b.get_3d_cad_parameters(), b.design_results
    edge = b.grillage_model.edge_longitudinal_props
    rows.append((label, {
        "base depth key (mm)": d[GD + "section_input.depth"],
        "G1.M1 depth key (mm)": d[GD + "section_input.depth.G1.M1"],
        "girder check: D x bf_top x tf_top / bf_bot x tf_bot, tw (mm)":
            f"{dr['D_mm']:.0f} x {dr['bf_top_mm']:.0f} x {dr['tf_top_mm']:.0f} / {dr['bf_bot_mm']:.0f} x {dr['tf_bot_mm']:.0f}, {dr['tw_mm']:.0f}",
        "3D CAD girder (mm)": f"{cad.girder_section_d:.0f} x {cad.girder_section_bf:.0f} x {cad.girder_section_tf:.0f} / "
                              f"{cad.girder_section_bf_b:.0f} x {cad.girder_section_tf_b:.0f}, {cad.girder_section_tw:.0f}",
        "grillage edge-beam section A (m2) / Iz (m4)": f"{edge.A:.4f} / {edge.Iz:.4f}",
        "grillage girder G1 section A (m2) / Iz (m4)":
            f"{b.grillage_model.girder_props[0].A:.4f} / {b.grillage_model.girder_props[0].Iz:.4f}",
        "output_dict girder mass (kg/m)": b.output_dict.get(GD + "section_properties.mass"),
        **{k: round(v, 2) for k, v in b.output_dict.items() if k.startswith("util.")},
    }))

w = max(len(k) for k in rows[0][1])
print(f"{'':{w}}  {rows[0][0]:>36}  {rows[1][0]:>28}")
for k in rows[0][1]:
    print(f"{k:{w}}  {rows[0][1][k]!s:>36}  {rows[1][1][k]!s:>28}")
