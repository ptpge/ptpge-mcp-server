"""0.40.2 — every inline script on /check must parse. A Python-escaped apostrophe (\\'s) inside a JS string
broke the whole page silently on 23 Oct (the form fell back to a plain GET)."""
import re, shutil, subprocess, tempfile, pathlib
from ptpge_mcp import checkpage


def test_check_page_scripts_parse():
    node = shutil.which("node")
    if not node:
        import pytest; pytest.skip("node not installed")
    scripts = re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", checkpage.CHECK_HTML, re.S)
    assert scripts, "no inline scripts found on /check"
    for i, js in enumerate(scripts):
        f = pathlib.Path(tempfile.mkdtemp()) / f"check{i}.js"
        f.write_text(js)
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, f"script {i}: {r.stderr[:300]}"
