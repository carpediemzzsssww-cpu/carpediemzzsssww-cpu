#!/usr/bin/env python3
"""Write preview-light.html / preview-dark.html: the README as GitHub would lay it out.

GitHub picks the <picture> source from its own theme setting; here each page
simply points every image at one theme, inside a column as wide as a profile README.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
readme = (ROOT / "README.md").read_text(encoding="utf-8")

PAGE = """<!doctype html><meta charset="utf-8"><title>profile preview ({theme})</title>
<style>
body{{margin:0;background:{bg};color:{fg};font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
main{{width:{width}px;max-width:calc(100% - 32px);margin:24px auto;padding:24px;border:1px solid {line};border-radius:6px;box-sizing:border-box}}
img{{max-width:100%;height:auto;vertical-align:middle}} a{{color:{link};text-decoration:none}} p{{margin:0 0 16px}} sub{{font-size:12px}}
</style><main>{body}</main>
"""
LOOK = {
    "light": dict(bg="#ffffff", fg="#1f2328", line="#d1d9e0", link="#0969da"),
    "dark": dict(bg="#0d1117", fg="#f0f6fc", line="#3d444d", link="#4493f8"),
}

for theme, look in LOOK.items():
    body = re.sub(r"<source[^>]*>", "", readme)
    body = re.sub(r'src="assets/([\w-]+)-light\.svg"', rf'src="../assets/\1-{theme}.svg"', body)
    for width, suffix in ((896, ""), (390, "-phone")):
        (ROOT / "scripts" / f"preview-{theme}{suffix}.html").write_text(
            PAGE.format(theme=theme, body=body, width=width, **look), encoding="utf-8"
        )
print("wrote scripts/preview-*.html")
