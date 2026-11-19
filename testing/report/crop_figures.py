"""Crop screenshots and report pages to the regions shown in report.tex  ->  report/figures/."""
from pathlib import Path

from PySide6.QtGui import QImage

R = Path(__file__).resolve().parents[1] / "results"
OUT = Path(__file__).parent / "figures"
CROPS = {  # name: (source, x, y, width, height) in source pixels
    "report_fatigue_table": ("evidence/report_fatigue_table.png", 135, 140, 985, 660),
    "report_moment_table": ("evidence/report_shear_table.png", 135, 140, 985, 975),
    "tc03_cross_section": ("S1/TC03/cross_section.png", 600, 85, 1100, 280),
    "tc01_plots": ("S1/TC01/plots_view.png", 790, 120, 780, 620),
    "tc01_plan_view": ("S1/TC01/cross_section.png", 590, 600, 1200, 390),
    "dock_fatigue": ("evidence/dock_G3_design_envelope.png", 0, 160, 443, 680),
    "design_check_fatigue": ("evidence/design_check_G3_SLS_FREQUENT_1.png", 640, 240, 600, 460),
}
OUT.mkdir(exist_ok=True)
for name, (src, x, y, w, h) in CROPS.items():
    img = QImage(str(R / src))
    img.copy(x, y, min(w, img.width() - x), min(h, img.height() - y)).save(str(OUT / f"{name}.png"))
    print(name, img.width(), img.height())
