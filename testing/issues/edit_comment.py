"""Replace the body of an already-posted comment with the current text of its draft.

    python edit_comment.py comment_93_cad_sections.md
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from publish import HERE, LOG, UPSTREAM, render

name = sys.argv[1]
comment_id = json.loads(LOG.read_text())[name].rsplit("issuecomment-", 1)[1]
_, body = render(HERE / name)
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
    json.dump({"body": body}, f)
try:
    subprocess.run(["gh", "api", "-X", "PATCH", f"repos/{UPSTREAM}/issues/comments/{comment_id}", "--input", f.name,
                    "--jq", ".html_url"], check=True)
finally:
    Path(f.name).unlink()
