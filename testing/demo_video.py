"""Silent screencast of the test workflow, recorded from the application window itself.

    python demo_video.py   ->  results/demo/osdagbridge_testing_demo.mp4 (+ dialog screenshots)

Shows a custom-material run, two unlock -> edit -> Design cycles, the 3D CAD, plots,
2D views, the Output Dock and the results dialogs. Inputs are typed by gui_driver.
Frames are rendered from the widgets (window + open dialogs + OCC viewport), so the
video does not depend on what else is on the desktop.
"""
import shutil
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).parent / "results" / "demo"
FPS = 4


class Recorder:
    def __init__(self, driver, frames: Path):
        from PySide6.QtCore import QTimer
        self.d, self.frames, self.n, self.caption = driver, frames, 0, ""
        frames.mkdir(parents=True, exist_ok=True)
        self.timer = QTimer()
        self.timer.timeout.connect(self.frame)
        self.timer.start(1000 // FPS)

    def frame(self):
        self.n += 1
        self.d.compose(dialogs=True, caption=self.caption).save(str(self.frames / f"f{self.n:05d}.jpg"), "JPG", 85)

    def hold(self, caption: str, seconds: float):
        self.caption = caption
        self.d.pump(int(seconds * 1000))

    def timelapse(self, on: bool):
        self.timer.setInterval(1500 if on else 1000 // FPS)     # 1 frame per 1.5 s while Design runs


def show_results(d, rec, run: str):
    rec.hold(f"{run}: 3D CAD model rebuilt from this run's design", 4)
    d.win.plots_view_toggle()
    rec.hold(f"{run}: analysis plots (shear force, Vy) for the new model", 3.5)
    d.win.cross_section_toggle()
    rec.hold(f"{run}: 2D cross-section with the solved girder layout", 3)
    d.win.top_view_toggle()
    rec.hold(f"{run}: 2D plan view", 2.5)
    d.win.cad_3d_view_toggle(force_show=True)
    rec.hold(f"{run}: back to 3D CAD", 1.5)


def main():
    from gui_driver import Driver
    from osdagbridge.core.utils import common as C
    from osdagbridge.desktop.ui.dialogs.deck_design import DeckDesign
    from osdagbridge.desktop.ui.dialogs.steel_design import SteelDesign
    from PySide6.QtWidgets import QComboBox

    shutil.rmtree(OUT, ignore_errors=True)
    d = Driver(OUT)
    d.dialog_delay_ms, d.type_delay_ms = 1600, 90
    rec = Recorder(d, OUT / "frames")
    steel = lambda dens, fy, fu, e: {C.KEY_MATERIAL_GIRDER_DENSITY: dens, C.KEY_MATERIAL_GIRDER_FY: fy,
                                     C.KEY_MATERIAL_GIRDER_FU: fu, C.KEY_MATERIAL_GIRDER_E: e}
    deck = {C.KEY_MATERIAL_DECK_DENSITY: 25.5, C.KEY_MATERIAL_DECK_FCK: 42, C.KEY_MATERIAL_DECK_FCTM: 3.2,
            C.KEY_MATERIAL_DECK_ECM: 33.5}

    rec.hold("OsdagBridge short-span plate girder module: automated GUI test (inputs typed by the test driver)", 3)
    rec.caption = "Step 1: project location and basic geometry (span 30 m, carriageway 7.5 m)"
    d.location("Gujarat", "Ahmedabad")
    d.set_text(C.KEY_SPAN, 30)
    d.set_text(C.KEY_CARRIAGEWAY_WIDTH, 7.5)
    rec.caption = "Step 2: custom girder steel (Fy 345 MPa, Fu 480 MPa, E 205 GPa, density 78.5 kN/m3)"
    d.custom_material(C.KEY_GIRDER, steel(78.5, 345, 480, 205))
    rec.caption = "Step 2: custom deck concrete (fck 42 MPa, fctm 3.2 MPa, Ecm 33.5 GPa, density 25.5 kN/m3)"
    d.custom_material(C.KEY_DECK_CONCRETE_GRADE_BASIC, deck)
    rec.hold("Step 2: custom grades are now selected in the input dock", 2.5)

    def design(run):
        rec.caption = f"{run}: Design running (time-lapse)"
        rec.timelapse(True)
        d.design()
        rec.timelapse(False)
        show_results(d, rec, run)

    def snap(dlg, name, tab=None):
        """Handler for a modal results dialog: show it for a few seconds, save it, close it."""
        for combo in dlg.findChildren(QComboBox):
            if combo.findText("Design Envelope") >= 0:
                combo.setCurrentText("Design Envelope")
        if tab is not None:
            dlg.tabs.setCurrentIndex(tab)
        d.pump(3500)
        dlg.grab().save(str(OUT / name))
        dlg.reject()

    design("Run 1")
    d.win.output_dock_toggle()
    rec.hold("Run 1: Output Dock utilisation bars (girder G1, first load case)", 3)
    d.compose().save(str(OUT / "output_dock_run1.png"))
    rec.caption = "Run 1: Girder Design Check tab (Design Envelope)"
    d.handlers.append((SteelDesign, lambda dlg: snap(dlg, "steel_design_check_run1.png", tab=2)))
    d.win.output_dock.open_steel_design()
    rec.caption = "Run 1: Deck Design summary"
    d.handlers.append((DeckDesign, lambda dlg: snap(dlg, "deck_design_run1.png")))
    d.win.output_dock.open_deck_design()
    d.win.output_dock_toggle()

    rec.caption = "Run 2: unlock (results are cleared), span 40 m, footpath on one side"
    d.unlock()
    d.set_text(C.KEY_SPAN, 40)
    d.set_combo(C.KEY_FOOTPATH, "Single Side")
    design("Run 2")

    rec.caption = "Run 3: unlock, span 25 m, girder back to database grade E 250A, no footpath"
    d.unlock()
    d.set_text(C.KEY_SPAN, 25)
    d.set_combo(C.KEY_FOOTPATH, "None")
    d.set_combo(C.KEY_GIRDER, "E 250A")
    design("Run 3")
    d.win.output_dock_toggle()
    rec.hold("Three consecutive runs completed in one session; evidence: testing/results/", 4)
    rec.timer.stop()

    ffmpeg = Path(sys.prefix) / "Library" / "bin" / "ffmpeg.exe"
    subprocess.run([str(ffmpeg), "-y", "-loglevel", "error", "-framerate", str(FPS), "-i",
                    str(OUT / "frames" / "f%05d.jpg"), "-vf", "scale=1600:-2", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-crf", "24", str(OUT / "osdagbridge_testing_demo.mp4")], check=True)
    shutil.rmtree(OUT / "frames")
    print(f"frames={rec.n}  video={OUT / 'osdagbridge_testing_demo.mp4'}", file=sys.__stderr__)


if __name__ == "__main__":
    main()
