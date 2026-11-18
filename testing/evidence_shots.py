"""GUI and report screenshots for the bug reports (TC01 inputs: Ahmedabad, span 30 m, carriageway 7.5 m).

    python evidence_shots.py          GUI: Output Dock and Design Check tab for girder G3
    python evidence_shots.py --pdf    report pages from results/S1/TC01 (needs `pip install pymupdf`)

Output: results/evidence/*.png
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "results" / "evidence"


def scroll_top(widget, margin=12):
    """Scroll the enclosing QScrollArea so `widget` sits at the top of the viewport."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QScrollArea
    area = widget.parentWidget()
    while area is not None and not isinstance(area, QScrollArea):
        area = area.parentWidget()
    if area is not None:
        area.verticalScrollBar().setValue(widget.mapTo(area.widget(), QPoint(0, 0)).y() - margin)


def gui():
    from gui_driver import Driver
    from osdagbridge.core.utils import common as C
    from osdagbridge.desktop.ui.dialogs.steel_design import SteelDesign
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QLabel

    d = Driver(OUT)
    d.location("Gujarat", "Ahmedabad")
    d.set_text(C.KEY_SPAN, 30)
    d.set_text(C.KEY_CARRIAGEWAY_WIDTH, 7.5)
    print("design:", d.design(), file=sys.__stderr__)

    od = d.win.output_dock
    d.win.output_dock_toggle()
    od._w(C.KEY_OUTPUT_DOCK_MEMBER_ID).setCurrentText("G3")
    od._w(C.KEY_OUTPUT_DOCK_LOAD_COMBINATION).setCurrentText("Design Envelope")
    d.pump(1500)
    scroll_top(od._w(C.KEY_OUTPUT_DOCK_MEMBER_ID), 60)
    d.pump(800)
    od.grab().save(str(OUT / "dock_G3_design_envelope.png"))
    print("dock fatigue bar:", od._w(C.KEY_UTIL_FATIGUE)._pct_label.text(), file=sys.__stderr__)

    def check_tab(dlg):
        dlg.member_combo.setCurrentIndex(2)                                     # Girder 3
        dlg.load_combo.setCurrentIndex(dlg.load_combo.findText("SLS_FREQUENT_1", Qt.MatchStartsWith))
        dlg.tabs.setCurrentIndex(2)
        d.pump(3000)
        title = next(l for l in dlg.check_tab.findChildren(QLabel) if l.text() == "Resistance to Fatigue")
        scroll_top(title, 40)
        d.pump(1200)
        dlg.grab().save(str(OUT / "design_check_G3_SLS_FREQUENT_1.png"))
        print("check card:", dlg.member_combo.currentText(), "|", dlg.load_combo.currentText(), file=sys.__stderr__)
        dlg.reject()
    d.handlers.append((SteelDesign, check_tab))
    od.open_steel_design()


def pdf_pages(pdf=HERE / "results" / "S1" / "TC01" / "report" / "TC01_report.pdf", zoom=2.0):
    import fitz  # PyMuPDF
    wanted = {"report_fatigue_table": "Girder Design Summary (DCR / Utilization Ratio)",
              "report_shear_table": "Applied Shear"}
    doc = fitz.open(pdf)
    for name, phrase in wanted.items():
        page = next(p for p in doc if phrase in p.get_text())
        page.get_pixmap(matrix=fitz.Matrix(zoom, zoom)).save(OUT / f"{name}.png")
        print(f"{name}: page {page.number + 1}", file=sys.__stderr__)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    pdf_pages() if "--pdf" in sys.argv else gui()
