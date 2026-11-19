"""File the drafted issues and comments on the upstream repository with `gh`.

    python publish.py --dry-run     print titles and check placeholders
    python publish.py               create issues NN_*.md, then post comment_<number>_*.md

Evidence links are pinned to the commit that holds the evidence (EVIDENCE_SHA).
Results are appended to published.json; already-published files are skipped.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

UPSTREAM = "Nidhikhare12/OsdagBridge"
EVIDENCE_SHA = "60781ab7e84cd319b97efbe594fb31169d1aadd2"
FORK = "Aditya060806/OsdagBridge"
URLS = {"{REPO}": f"https://github.com/{FORK}/blob/{EVIDENCE_SHA}",
        "{TREE}": f"https://github.com/{FORK}/tree/{EVIDENCE_SHA}",
        "{RAW}": f"https://raw.githubusercontent.com/{FORK}/{EVIDENCE_SHA}"}
HERE = Path(__file__).parent
LOG = HERE / "published.json"


def render(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    for key, url in URLS.items():
        text = text.replace(key, url)
    if re.search(r"\{(REPO|TREE|RAW)\}", text):
        raise ValueError(f"unresolved placeholder in {path.name}")
    if path.name.startswith("comment_"):
        return "", text
    title, _, body = text.partition("\n")
    return title.strip(), body.strip() + "\n"


def gh(*args, body: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(body)
    try:
        out = subprocess.run(["gh", *args, "-R", UPSTREAM, "--body-file", f.name], capture_output=True, text=True,
                             encoding="utf-8", check=True).stdout
    finally:
        Path(f.name).unlink()
    return out.strip().splitlines()[-1]


def main(dry: bool):
    done = json.loads(LOG.read_text()) if LOG.exists() else {}
    files = sorted(HERE.glob("[0-9][0-9]_*.md")) + sorted(HERE.glob("comment_*.md"))
    for path in files:
        title, body = render(path)
        target = re.match(r"comment_(\d+)_", path.name)
        label = f"comment on #{target.group(1)}" if target else title
        if path.name in done:
            print(f"skip  {path.name}: {done[path.name]}")
            continue
        if dry:
            print(f"ready {path.name}: {label[:100]}  ({len(body)} chars)")
            continue
        url = (gh("issue", "comment", target.group(1), body=body) if target
               else gh("issue", "create", "--title", title, body=body))
        done[path.name] = url
        LOG.write_text(json.dumps(done, indent=1), encoding="utf-8")
        print(f"done  {path.name}: {url}")


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
