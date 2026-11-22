"""Submission screencast: GUI test run + root-cause probes + the fix for #148, silent.

    python demo_submission.py   ->  results/demo/osdagbridge_submission_demo.mp4

Part 1 is the GUI recording made by demo_video.py (results/demo/osdagbridge_testing_demo.mp4).
Part 2 runs every command shown live in PowerShell, exactly as displayed, and draws the
terminal frames from the real output: the three root-cause probes, the regression test of
pull request #235 against the dev code and against the fix, and the issues on GitHub.
Long waits (each probe re-runs a full design) are shortened; the caption then shows the
real elapsed time. Needs Windows, the osdagbridge-env conda environment, gh, ffmpeg,
Pillow and PyMuPDF.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont

TESTING = Path(__file__).resolve().parent
REPO = TESTING.parent
DEMO = TESTING / "results" / "demo"
GUI_VIDEO = DEMO / "osdagbridge_testing_demo.mp4"
OUT = DEMO / "osdagbridge_submission_demo.mp4"
REPORT = TESTING / "report" / "report.pdf"
ENV = Path(r"D:\miniconda3\envs\osdagbridge-env") if not os.environ.get("CONDA_PREFIX") else Path(os.environ["CONDA_PREFIX"])
PR_DIR = REPO.parent / "OsdagBridge-pr235"
PR_BRANCH = "origin/fix/148-deck-ecm-mpa"
PGB = "src/osdagbridge/core/bridge_types/plate_girder/plategirderbridge.py"
UPSTREAM = "Nidhikhare12/OsdagBridge"

W, H, CAP_H = 1600, 900, 64
FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
MONO = ImageFont.truetype(str(FONTS / "consola.ttf"), 19)
MONO_B = ImageFont.truetype(str(FONTS / "consolab.ttf"), 19)
SANS = ImageFont.truetype(str(FONTS / "segoeui.ttf"), 24)
SANS_B = ImageFont.truetype(str(FONTS / "segoeuib.ttf"), 26)
TITLE = ImageFont.truetype(str(FONTS / "segoeuib.ttf"), 52)
SUB = ImageFont.truetype(str(FONTS / "segoeui.ttf"), 29)
LINE_H = 24
CHAR_W = MONO.getlength("M")
COLS = int((W - 40) // CHAR_W)
ROWS = (H - CAP_H - 60) // LINE_H
BG, FG, CMD = (12, 12, 12), (204, 204, 204), (249, 241, 165)
GREEN = (133, 168, 0)          # Osdag accent


class Film:
    """Unique frames plus how long each one stays on screen."""

    def __init__(self, folder: Path):
        self.folder, self.items = folder, []

    def add(self, img: Image.Image, seconds: float):
        if seconds <= 0:
            return
        raw = img.tobytes()
        if self.items and self.items[-1][2] == raw:
            self.items[-1][1] += seconds
            return
        path = self.folder / f"f{len(self.items):05d}.png"
        img.save(path)
        self.items.append([path, seconds, raw])

    def encode(self, out: Path):
        lst = self.folder / "list.txt"
        with lst.open("w", encoding="utf-8") as f:
            for path, sec, _ in self.items:
                f.write(f"file '{path.as_posix()}'\nduration {sec:.3f}\n")
            f.write(f"file '{self.items[-1][0].as_posix()}'\n")
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-vf", "fps=25,format=yuv420p",
               "-c:v", "libx264", "-crf", "20", str(out))

    @property
    def length(self):
        return sum(s for _, s, _ in self.items)


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def caption_bar(d: ImageDraw.ImageDraw, caption: str):
    d.rectangle([0, H - CAP_H, W, H], fill=(32, 32, 32))
    d.text((24, H - CAP_H + 16), caption, font=SANS, fill=(240, 240, 240))


class Terminal:
    def __init__(self, film: Film):
        self.film, self.lines, self.prompt = film, [], ""

    def push(self, text: str, colour=FG):
        for part in text.expandtabs(4).split("\n"):
            while len(part) > COLS:                            # wrap at a space where possible
                cut = part.rfind(" ", COLS // 2, COLS)
                cut = cut if cut > 0 else COLS
                self.lines.append((part[:cut], colour))
                part = "    " + part[cut:].lstrip()
            self.lines.append((part, colour))

    def render(self, caption: str, cursor: bool = False) -> Image.Image:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W, 32], fill=(40, 40, 40))
        d.text((16, 4), "Windows PowerShell  -  OsdagBridge testing", font=SANS, fill=(200, 200, 200))
        y, shown = 42, self.lines[-ROWS:]
        for i, (text, colour) in enumerate(shown):
            if colour == CMD and text.startswith(("(osdagbridge-env) PS ", "PS ")) and "> " in text:
                p = text.index("> ") + 2
                d.text((20, y), text[:p], font=MONO, fill=FG)
                d.text((20 + MONO.getlength(text[:p]), y), text[p:], font=MONO_B, fill=CMD)
            else:
                d.text((20, y), text, font=MONO, fill=colour)
            if cursor and i == len(shown) - 1:
                x = 20 + MONO.getlength(text)
                d.rectangle([x + 1, y + 3, x + CHAR_W, y + LINE_H - 3], fill=FG)
            y += LINE_H
        caption_bar(d, caption)
        return img


def card(film: Film, title: str, lines: list[str], seconds: float, image: Image.Image | None = None,
         caption: str | None = None):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=GREEN)
    if image is None:
        d.text((W / 2, 320), title, font=TITLE, fill=(30, 30, 30), anchor="mm")
        for i, line in enumerate(lines):
            d.text((W / 2, 410 + i * 50), line, font=SUB, fill=(60, 60, 60), anchor="mm")
    else:
        d.text((40, 26), title, font=SANS_B, fill=(30, 30, 30))
        image.thumbnail((W - 80, H - CAP_H - 100))
        img.paste(image, ((W - image.width) // 2, 76))
    if caption:
        caption_bar(d, caption)
    film.add(img, seconds)


def report_figure(label: str, top_word: str) -> Image.Image:
    for page in fitz.open(REPORT):
        hits = page.search_for(label)
        if hits:
            top = page.search_for(top_word)[0].y0 - 14
            clip = fitz.Rect(page.rect.x0 + 30, top, page.rect.x1 - 30, hits[0].y0 - 4)
            pix = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=clip)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    raise SystemExit(f"{label} not found in {REPORT}")


class Shell:
    """Runs PowerShell commands with the conda environment active (PATH, as `conda activate` sets it)."""

    def __init__(self, pytest_dir: Path):
        self.env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
                        PYTHONDONTWRITEBYTECODE="1", CONDA_DEFAULT_ENV="osdagbridge-env")
        self.env["PATH"] = os.pathsep.join([str(ENV), str(ENV / "Scripts"), str(ENV / "Library" / "bin"),
                                            self.env["PATH"]])
        self.pytest_dir = pytest_dir

    def run(self, command: str, cwd: Path) -> list[tuple[float, str]]:
        env = dict(self.env)
        if cwd == PR_DIR:            # the PR checkout: its own sources, plus pytest
            env["PYTHONPATH"] = os.pathsep.join([str(PR_DIR / "src"), str(self.pytest_dir)])
        setup = "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
        t0 = time.monotonic()
        proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", setup + command], cwd=cwd, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", bufsize=1)
        out = [(time.monotonic() - t0, line.rstrip("\r\n")) for line in proc.stdout]
        proc.wait()
        while out and not out[-1][1].strip():
            out.pop()
        while out and not out[0][1].strip():
            out.pop(0)
        return out


def fmt(sec: float) -> str:
    return f"{int(sec // 60)} min {int(sec % 60):02d} s" if sec >= 60 else f"{sec:.0f} s"


def scene(term: Terminal, shell: Shell | None, cwd: Path, command: str, caption: str, clear: bool = True,
          hold: float | None = None, wait: str | None = None, prompt_env: bool = True):
    film = term.film
    if clear:
        term.lines = []
    prompt = ("(osdagbridge-env) " if prompt_env else "") + f"PS {cwd}> "
    base = len(term.lines)
    for i in list(range(0, len(command), 2)) + [len(command)]:   # typing; long commands wrap
        del term.lines[base:]
        term.push(prompt + command[:i], CMD)
        film.add(term.render(caption, cursor=i < len(command)), 0.045 if i < len(command) else 0.4)
    lines = shell.run(command, cwd) if shell else []
    last = 0.0
    for t, text in lines:
        gap = t - last
        if gap > 2.5 and wait:
            for k in range(1, 17):
                film.add(term.render(wait.format(elapsed=fmt(last + gap * k / 16))), 0.25)
        else:
            film.add(term.render(caption), min(max(gap, 0.03), 0.6))
        term.push(text)
        last = t
    film.add(term.render(caption), hold if hold is not None else min(3.0 + 0.2 * len(lines), 9.0))
    return lines


def require(lines, needle: str, what: str):
    if not any(needle in t for _, t in lines):
        raise SystemExit(f"{what}: expected '{needle}' in the output; no video written.\n"
                         + "\n".join(t for _, t in lines[-15:]))


def pytest_available(tmp: Path) -> Path:
    target = tmp / "pytest"
    subprocess.run([str(ENV / "python.exe"), "-m", "pip", "install", "-q", "--target", str(target), "pytest"],
                   check=True)
    return target


def main():
    if not GUI_VIDEO.exists():
        raise SystemExit(f"{GUI_VIDEO} is missing: run demo_video.py first")
    tmp = Path(tempfile.mkdtemp(prefix="osdag-demo-"))
    shell = Shell(pytest_available(tmp))
    subprocess.run(["git", "-C", str(REPO), "fetch", "-q", "origin", "fix/148-deck-ecm-mpa"], check=True)
    if PR_DIR.exists():
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(PR_DIR)], check=False)
    subprocess.run(["git", "-C", str(REPO), "worktree", "add", "-q", "--detach", str(PR_DIR), PR_BRANCH], check=True)
    try:
        # ---- opening cards
        (tmp / "a").mkdir()
        intro = Film(tmp / "a")
        card(intro, "OsdagBridge: Software Testing & Issue Reporting",
             ["Short-span steel girder bridge module  ·  FOSSEE Osdag Winter Internship 2026",
              "Aditya Pandey  (GitHub: Aditya060806)",
              "Silent screencast: Part 1 GUI test run  ·  Part 2 root causes and the fix for #148"], 6)
        card(intro, "Where the defects sit", [], 8, report_figure("Figure 1:", "Input Dock"),
             "Data flow of the plate girder module; black tags mark the six issues filed (#147 to #152)")
        card(intro, "How the tests are run", [], 7, report_figure("Figure 3:", "campaign.py"),
             "The test harness drives the real GUI and captures dictionaries, dock values and CAD after every run")
        card(intro, "Part 1: GUI test run", ["Custom material run, consecutive unlock / edit / Design cycles,",
                                             "3D CAD, plots, 2D views and result dialogs (recorded from the app)"], 4)
        intro.encode(tmp / "a.mp4")

        # ---- part 2, live terminal
        (tmp / "c").mkdir()
        film = Film(tmp / "c")
        card(film, "Part 2: root causes and the fix", ["Each probe replays a captured GUI input dictionary headless",
                                                       "and isolates one defect; then the regression test of PR #235"], 4)
        term = Terminal(film)
        scene(term, None, TESTING, "conda activate osdagbridge-env",
              "The environment created from environment.yml", hold=1.5, prompt_env=False)
        out = scene(term, shell, TESTING,
                    "python probes/probe_fatigue_range.py results/S1/TC01/input_dict.json 2>$null | Select-Object -Last 17",
                    "#147: the designer's fatigue 'range' is exactly 2.000 x the largest moment on every girder line",
                    wait="#147 probe: re-running the TC01 design headless, {elapsed} elapsed (shortened)", clear=False)
        require(out, "ratio", "fatigue probe")
        out = scene(term, shell, TESTING,
                    "python probes/probe_deck_ecm_units.py results/S1/TC01/input_dict.json 2>$null | Select-Object -Last 20",
                    "#148: Ecm passed in GPa gives alpha_e = 6061 instead of 6.06; concrete stress 2.49 vs 9.84 MPa",
                    wait="#148 probe: re-running the TC01 design, then the deck with Ecm in MPa, {elapsed} elapsed (shortened)")
        require(out, "alpha_e", "deck probe")
        out = scene(term, shell, TESTING,
                    "python probes/probe_custom_base_keys.py results/S3/TC11/input_dict.json 2>$null | Select-Object -Last 15",
                    "#150: after a span change the 3D CAD and edge lines use 2120 mm, the checks use the user's 1600 mm",
                    wait="#150 probe: replaying TC11 twice (as captured, and with base keys = G1.M1), {elapsed} elapsed (shortened)")
        require(out, "3D CAD girder", "base-key probe")

        scene(term, shell, PR_DIR, "git log -1 --stat --oneline",
              "Pull request #235 (branch fix/148-deck-ecm-mpa): one-line fix plus a regression test")
        scene(term, shell, PR_DIR, f"git checkout HEAD~1 -- {PGB}",
              "Put back the dev version of plategirderbridge.py (without the fix)", clear=False, hold=1.5)
        out = scene(term, shell, PR_DIR, "python -m pytest -q --tb=line tests/unit/test_deck_ecm_units.py",
                    "On the dev code the regression test fails: Ecm reaches deckdesign as 33.0 (GPa)", clear=False)
        require(out, "1 failed", "pytest on dev code")
        scene(term, shell, PR_DIR, f"git checkout HEAD -- {PGB}",
              "Restore the fix: Ecm * 1000.0 at the deckdesign call", clear=False, hold=1.5)
        out = scene(term, shell, PR_DIR, "python -m pytest -q --tb=line tests/unit/test_deck_ecm_units.py",
                    "With the fix the test passes", clear=False)
        require(out, "1 passed", "pytest on the fix")

        scene(term, shell, TESTING, f"gh issue list -R {UPSTREAM} --author Aditya060806 --state all",
              "The six issues filed on Nidhikhare12/OsdagBridge, each with root cause and proposed fix",
              prompt_env=False)
        scene(term, shell, TESTING, f"gh pr list -R {UPSTREAM} --author Aditya060806 --state all",
              "and the pull request with the fix for #148", clear=False, prompt_env=False)
        card(film, "Thank you",
             ["Report, test logs, probes and .osi files:",
              "github.com/Aditya060806/OsdagBridge  (branch screening-testing, folder testing/)",
              f"Issues #147 to #152 and pull request #235 on {UPSTREAM}"], 6)
        film.encode(tmp / "c.mp4")

        # ---- join: cards + GUI recording (scaled and padded to 1600x900) + terminal part
        ffmpeg("-i", str(tmp / "a.mp4"), "-i", str(GUI_VIDEO), "-i", str(tmp / "c.mp4"), "-filter_complex",
               f"[1:v]fps=25,scale={W}:-2,pad={W}:{H}:0:(oh-ih)/2:color=white,setsar=1,format=yuv420p[g];"
               "[0:v]setsar=1[a];[2:v]setsar=1[c];[a][g][c]concat=n=3:v=1:a=0[v]",
               "-map", "[v]", "-c:v", "libx264", "-crf", "21", "-movflags", "+faststart", str(OUT))
    finally:
        subprocess.run(["git", "-C", str(REPO), "worktree", "remove", "--force", str(PR_DIR)], check=False)
        shutil.rmtree(tmp, ignore_errors=True)
    print(OUT)


if __name__ == "__main__":
    main()
