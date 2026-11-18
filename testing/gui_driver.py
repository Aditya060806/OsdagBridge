"""In-process driver for the OsdagBridge desktop GUI.

Drives the real ``CustomWindow`` through its widgets and signals (typed keystrokes,
combo selections, button clicks), answers modal dialogs, waits for the threaded
design run and captures evidence for every run:

    ui.json            values shown in the input dock widgets
    input_dict.json    the GUI's input dictionary (what Design hands to the backend)
    backend_input.json backend.input_dict after design (normalised + unit-converted)
    output_dict.json   backend.output_dict (frozen output dictionary)
    dock.json          output-dock utilisation bars per girder ("Design Envelope")
    popups.json        every message box shown during the step
    log.txt            log-dock text
    window.png / cad3d.png / plots.png / cross_section.png / top_view.png
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QLineEdit, QPushButton, QTabWidget,
                               QWidget)

import osdagbridge.desktop.__main__ as launcher  # same DB bootstrap as `python -m osdagbridge.desktop`
from osdagbridge.core.bridge_types.plate_girder.plategirderbridge import PlateGirderBridge
from osdagbridge.core.utils import common as C
from osdagbridge.desktop.ui.dialogs.additional_input.ui_builder.common_ui_builder import AdaptiveWidget
from osdagbridge.desktop.ui.dialogs.custom_messagebox import CustomMessageBox
from osdagbridge.desktop.ui.dialogs.material_properties import MaterialPropertiesDialog
from osdagbridge.desktop.ui.dialogs.project_location import ProjectLocationDialog
from osdagbridge.desktop.ui.template_page import CustomWindow

UTIL_KEYS = [C.KEY_UTIL_FLEXURE, C.KEY_UTIL_SHEAR, C.KEY_UTIL_INTERACTION, C.KEY_UTIL_LTB,
             C.KEY_UTIL_LONG_TRANS_SHEAR, C.KEY_UTIL_FATIGUE, C.KEY_UTIL_STRESS_LIMITATION,
             C.KEY_UTIL_DEFLECTION_CRACK]


def jsonable(value, depth=0):
    """Best-effort JSON conversion (numpy scalars, DTOs, nested containers)."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "item") and not hasattr(value, "__len__"):
        return value.item()
    if depth > 6:
        return str(value)[:300]
    if isinstance(value, dict) or hasattr(value, "items"):
        return {str(k): jsonable(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v, depth + 1) for v in value]
    return str(value)[:300]


class Driver:
    def __init__(self, out_dir: Path):
        self.out = Path(out_dir)
        self.out.mkdir(parents=True, exist_ok=True)
        self.app = QApplication.instance() or QApplication(sys.argv)
        self.app.setStyleSheet(launcher.load_stylesheet())
        self.win = CustomWindow("OsdagBridge", PlateGirderBridge)
        self.win.showMaximized()
        self.popups: list[dict] = []
        self.handlers: list[tuple[type, callable]] = []   # one-shot handlers for expected dialogs
        self.dialog_delay_ms = 150                         # how long a dialog stays up before it is answered
        self.type_delay_ms = 0                             # per-character delay (0 = instant)
        self._watchdog = QTimer()
        self._watchdog.timeout.connect(self._watch)
        self._watchdog.start(150)
        self.pump(4000)

    # ── event loop helpers ───────────────────────────────────────────────────
    def pump(self, ms: int = 100):
        end = time.time() + ms / 1000
        while time.time() < end:
            self.app.processEvents()
            time.sleep(0.01)

    def _watch(self):
        """Answer the active modal dialog: registered handler first, else close message boxes."""
        dlg = QApplication.activeModalWidget()
        if dlg is None or getattr(dlg, "_drv_seen", False):
            return
        for i, (cls, fn) in enumerate(self.handlers):
            if isinstance(dlg, cls):
                dlg._drv_seen = True
                self.handlers.pop(i)
                QTimer.singleShot(self.dialog_delay_ms, lambda d=dlg, f=fn: f(d))
                return
        if isinstance(dlg, CustomMessageBox):
            dlg._drv_seen = True
            QTimer.singleShot(self.dialog_delay_ms, lambda d=dlg: self._close_msg(d))

    def _close_msg(self, box: CustomMessageBox):
        info = getattr(box, "informativeLabel", None)
        title = " ".join(l.text() for l in box.titleBar.findChildren(type(box.textLabel)) if l.text())
        entry = {"title": title, "text": box.textLabel.text(), "info": info.text() if info else ""}
        self.popups.append(entry)
        box.grab().save(str(self.out / f"popup_{len(self.popups):02d}.png"))
        buttons = box.buttonMap
        (buttons.get("Continue") or buttons.get("OK") or next(iter(buttons.values()))).click()

    # ── input dock ───────────────────────────────────────────────────────────
    def w(self, key: str, cls=QWidget, root=None):
        """Widget named `key`, skipping copies on the inactive page of an AdaptiveWidget
        (Optimized/Custom variants of the same field share one objectName)."""
        root = root or self.win.input_dock.input_widget

        def live(x):
            child, parent = x, x.parentWidget()
            while parent is not None and child is not root:
                if isinstance(parent, AdaptiveWidget) and parent.currentWidget() is not child:
                    return False
                child, parent = parent, parent.parentWidget()
            return True
        found = [x for x in root.findChildren(cls, key) if live(x)]
        return next((x for x in found if x.isEnabled()), found[0] if found else None)

    def type_into(self, widget: QLineEdit, value):
        widget.setFocus()
        widget.selectAll()
        QTest.keyClick(widget, Qt.Key_Backspace)
        if self.type_delay_ms:                     # visible typing for the screencast
            for ch in str(value):
                QTest.keyClicks(widget, ch)
                self.pump(self.type_delay_ms)
        else:
            QTest.keyClicks(widget, str(value))
        QTest.keyClick(widget, Qt.Key_Return)

    def set_text(self, key, value):
        self.type_into(self.w(key, QLineEdit), value)
        self.pump(150)

    def set_combo(self, key, text, root=None):
        combo = self.w(key, QComboBox, root)
        idx = combo.findText(str(text))
        if idx < 0:
            raise ValueError(f"{key}: option {text!r} not in {[combo.itemText(i) for i in range(combo.count())]}")
        combo.setCurrentIndex(idx)
        self.pump(200)

    def location(self, state: str, district: str):
        def fill(dlg: ProjectLocationDialog):
            dlg.method_radio_location.setChecked(True)
            dlg.state_combo.setCurrentText(state)
            dlg.district_combo.setCurrentText(district)
            self.pump(self.dialog_delay_ms)
            dlg.validate_and_save()
        self.handlers.append((ProjectLocationDialog, fill))
        self.w(C.KEY_PROJECT_LOCATION, QPushButton).click()
        self.pump(300)

    def custom_material(self, key: str, props: dict) -> str:
        """Select 'Custom' in a material combo and type `props` into the real dialog."""
        result = {}

        def fill(dlg: MaterialPropertiesDialog):
            for field_key, value in props.items():
                self.type_into(dlg.field_inputs[field_key], value)
            result["name"] = dlg.material_input.text()
            result["typed"] = {k: dlg.field_inputs[k].text() for k in dlg.field_inputs}
            self.pump(self.dialog_delay_ms)
            next(b for b in dlg.findChildren(QPushButton) if b.text() == "Add").click()
        self.handlers.append((MaterialPropertiesDialog, fill))
        self.set_combo(key, "Custom")
        self.pump(300)
        return result

    @staticmethod
    def reveal(widget: QWidget):
        """Switch every enclosing tab page to the one holding `widget` (as a user would)."""
        child, parent = widget, widget.parentWidget()
        while parent is not None:
            tabs = parent.parentWidget()
            if isinstance(tabs, QTabWidget) and tabs.indexOf(child) >= 0:
                tabs.setCurrentIndex(tabs.indexOf(child))
            child, parent = parent, parent.parentWidget()

    def additional(self, values: dict, buttons: tuple = ()):
        """Open Additional Inputs ('Modify Here'), set fields by key, click `buttons`, Save, close."""
        self.win.input_dock.show_additional_inputs()
        self.pump(800)
        dlg = self.win._additional_inputs_dialog
        for key, value in values.items():
            combo, line, box = (self.w(key, cls, dlg) for cls in (QComboBox, QLineEdit, QCheckBox))
            target = combo or line or box
            if target is None:
                raise KeyError(f"Additional Inputs has no live widget named {key!r}")
            self.reveal(target)
            self.pump(150)
            if combo is not None:
                self.set_combo(key, value, dlg)
            elif line is not None:
                self.type_into(line, value)
            else:
                box.setChecked(bool(value))
            self.pump(150)
        for text in buttons:
            self.click(text, dlg)
        dlg.save_button.click()
        self.pump(400)
        dlg.close()
        self.pump(300)
        return {k: dlg.working_input_dict.get(k) for k in values}

    def click(self, text: str, root: QWidget):
        btn = next(b for b in root.findChildren(QPushButton) if b.text().strip() == text)
        self.reveal(btn)
        btn.click()
        self.pump(300)

    def report(self, pdf_path: Path, timeout_s: int = 600) -> dict:
        """Generate the design report from the Output Dock with 'Save PDF' (file dialog stubbed)."""
        from PySide6.QtWidgets import QFileDialog
        from osdagbridge.desktop.ui.dialogs.report_options import ReportOptionsDialog
        pdf_path = Path(pdf_path)
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        original = QFileDialog.getSaveFileName
        QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: (str(pdf_path), "PDF Files (*.pdf)"))

        def fill(dlg: ReportOptionsDialog):
            dlg.project_name.setText("OsdagBridge screening test")
            dlg.designer.setText("Aditya Pandey")
            dlg.save_pdf()
        self.handlers.append((ReportOptionsDialog, fill))
        n_popups, t0 = len(self.popups), time.time()
        try:
            self.win.output_dock._on_report_clicked()
            while time.time() - t0 < timeout_s and not any(
                    "Report" in p["title"] for p in self.popups[n_popups:]):
                self.pump(500)
        finally:
            QFileDialog.getSaveFileName = original
        return {"pdf": str(pdf_path), "exists": pdf_path.exists(), "seconds": round(time.time() - t0, 1),
                "popups": self.popups[n_popups:]}

    # ── actions ──────────────────────────────────────────────────────────────
    def design(self, timeout_s: int = 1200) -> dict:
        t0, n_popups = time.time(), len(self.popups)
        self.win.input_dock.design_btn.click()
        started = bool(getattr(self.win, "_design_running", False))
        while getattr(self.win, "_design_running", False) and time.time() - t0 < timeout_s:
            self.pump(250)
        self.pump(2500)                                   # CAD render + plot draw
        return {"started": started, "seconds": round(time.time() - t0, 1),
                "locked_after": self.win.input_dock.is_locked,
                "popups": self.popups[n_popups:]}

    def unlock(self):
        self.win.input_dock.lock_btn.click()              # "Clear Results" answered "Continue"
        self.pump(800)

    # ── evidence ─────────────────────────────────────────────────────────────
    def ui_values(self) -> dict:
        root = self.win.input_dock.input_widget
        vals = {w.objectName(): w.text() for w in root.findChildren(QLineEdit) if w.objectName()}
        vals.update({w.objectName(): w.currentText() for w in root.findChildren(QComboBox) if w.objectName()})
        return vals

    def dock_bars(self) -> dict:
        od, backend = self.win.output_dock, self.win.backend
        member, lc = od._w(C.KEY_OUTPUT_DOCK_MEMBER_ID), od._w(C.KEY_OUTPUT_DOCK_LOAD_COMBINATION)
        if member is None or member.count() == 0:
            return {}
        rows = {}
        for m in [member.itemText(i) for i in range(member.count())]:
            member.setCurrentText(m)
            lc.setCurrentText("Design Envelope")
            self.pump(100)
            shown = {k: (None if od._w(k).isHidden() else od._w(k)._pct_label.text()) for k in UTIL_KEYS}
            raw = jsonable(backend.get_dcr_for_selection(m, "Design Envelope"))
            rows[m] = {"dock": shown, "get_dcr_for_selection": raw}
        member.setCurrentIndex(0)
        lc.setCurrentIndex(0)
        return rows

    def compose(self, dialogs: bool = False, caption: str = ""):
        """Render the window itself (immune to other windows covering it).

        The OCC viewport is a native OpenGL surface that QWidget.grab() cannot read,
        so its own offscreen dump is painted over that region. With `dialogs`, visible
        top-level dialogs are painted at their on-screen offset (message boxes last).
        """
        pix = self.win.grab()
        painter = QPainter(pix)
        cad = self.win.cad_3d_widget
        viewer = getattr(cad, "viewer", None)
        if viewer is not None and viewer.isVisible() and cad.display is not None:
            dump = self.out / "_occ_tmp.png"
            try:
                cad.display.View.Dump(str(dump))
                painter.drawImage(QRect(viewer.mapTo(self.win, QPoint(0, 0)), viewer.size()), QImage(str(dump)))
            finally:
                dump.unlink(missing_ok=True)
        w, h = self.win.width(), self.win.height()         # logical px (painter units under display scaling)
        if dialogs:
            tops = [t for t in QApplication.topLevelWidgets()
                    if isinstance(t, QDialog) and t.isVisible() and t is not self.win]
            for dlg in sorted(tops, key=lambda t: isinstance(t, CustomMessageBox)):
                at = dlg.mapToGlobal(QPoint(0, 0)) - self.win.mapToGlobal(QPoint(0, 0))
                if not QRect(0, 0, w, h).contains(at):
                    at = QPoint((w - dlg.width()) // 2, (h - dlg.height()) // 2)
                painter.drawPixmap(at, dlg.grab())
        if caption:
            painter.fillRect(0, h - 46, w, 46, QColor(30, 30, 30, 215))
            painter.setPen(QColor("white"))
            painter.setFont(QFont("Segoe UI", 15))
            painter.drawText(QRect(16, h - 46, w - 32, 46), Qt.AlignVCenter | Qt.AlignLeft, caption)
        painter.end()
        return pix

    def screenshot(self, path: Path):
        self.pump(400)
        self.compose().save(str(path))

    def grab_dialog(self, opener, cls, path: Path, tab: int | None = None, hold_ms: int = 600):
        """Open a modal results dialog, optionally switch tab, save a picture of it, close it."""
        def snap(dlg):
            if tab is not None:
                dlg.tabs.setCurrentIndex(tab)
            self.pump(hold_ms)
            dlg.grab().save(str(path))
            dlg.reject()
        self.handlers.append((cls, snap))
        opener()
        self.pump(300)

    def capture(self, tag: str, extra: dict | None = None) -> Path:
        d = self.out / tag
        d.mkdir(parents=True, exist_ok=True)
        b = self.win.backend
        cad = self.win.cad_3d_widget
        files = {
            "ui": self.ui_values(),
            "input_dict": self.win.input_dict,
            "backend_input": b.input_dict,
            "output_dict": dict(b.output_dict),
            "dock": self.dock_bars() if b.output_dict else {},
            "material_props": asdict(b.material_props) if getattr(b, "material_props", None) else {},
            "cad_params": asdict(b.get_3d_cad_parameters()) if b.output_dict else {},
            "cad_info_table": {k: l.text() for k, l in getattr(cad, "_info_value_labels", {}).items()},
            "popups": self.popups,
            "meta": extra or {},
        }
        for name, data in files.items():
            (d / f"{name}.json").write_text(json.dumps(jsonable(data), indent=1), encoding="utf-8")
        (d / "log.txt").write_text(self.win.logs_dock.log_display.toPlainText(), encoding="utf-8")
        self.screenshot(d / "window.png")
        if b.output_dict:
            try:
                self.win.cad_3d_widget.display.View.Dump(str(d / "cad3d.png"))
            except Exception as exc:  # evidence only — never abort the run
                (d / "cad3d_error.txt").write_text(repr(exc))
            self.win.plots_view_toggle()
            self.pump(1500)
            self.win.plots_widget._fig.savefig(d / "plots.png", dpi=110)
            self.screenshot(d / "plots_view.png")
            for view, fn in (("cross_section", self.win.cross_section_toggle), ("top_view", self.win.top_view_toggle)):
                fn()
                self.pump(1200)
                self.screenshot(d / f"{view}.png")
            self.win.cad_3d_view_toggle(force_show=True)
            self.pump(1000)
        self.popups = []
        return d
