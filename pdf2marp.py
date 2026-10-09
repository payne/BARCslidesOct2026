#!/usr/bin/env python3
"""Convert a Google-Slides-exported PDF (e.g. kc0wih.pdf) into a Marp presentation.

Usage: python3 pdf2marp.py kc0wih.pdf kc0wih.md

Requires poppler-utils (pdftotext, pdfimages). Uses the word/line bounding
boxes from `pdftotext -bbox-layout` to recover:
  * slide titles      (taller lines at the top of the page)
  * bullet levels     (●, ○, ■ glyphs)
  * soft-wrapped text (lines that only broke because they hit the right margin)
  * URLs split across lines by the wrap
The shared slide background image is extracted and used as the Marp background.
"""
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

NS = {"x": "http://www.w3.org/1999/xhtml"}
BULLETS = {"●": 0, "○": 1, "■": 2}
TITLE_MIN_HEIGHT = 38      # body lines are ~29pt tall, titles ~46pt
PARA_GAP = 8               # vertical gap (pt) that marks a new paragraph
URL_RE = re.compile(r"https?://\S+")
NUMBERED_RE = re.compile(r"^\d+[.)]$")


@dataclass
class Line:
    x0: float
    y0: float
    x1: float
    y1: float
    words: list  # [(x0, x1, text)]

    @property
    def height(self):
        return self.y1 - self.y0

    @property
    def text(self):
        return " ".join(w[2] for w in self.words)


def read_pages(pdf):
    xml = subprocess.run(["pdftotext", "-bbox-layout", pdf, "-"],
                         check=True, capture_output=True, text=True).stdout
    root = ET.fromstring(xml)
    pages = []
    for page in root.iter(f"{{{NS['x']}}}page"):
        lines = []
        for ln in page.iter(f"{{{NS['x']}}}line"):
            words = [(float(w.get("xMin")), float(w.get("xMax")), w.text or "")
                     for w in ln.findall("x:word", NS)]
            if words:
                lines.append(Line(float(ln.get("xMin")), float(ln.get("yMin")),
                                  float(ln.get("xMax")), float(ln.get("yMax")), words))
        pages.append(merge_rows(lines))
    return pages


def merge_rows(lines):
    """Merge line fragments sharing a visual row (e.g. a bullet glyph exported separately)."""
    rows = []
    for ln in sorted(lines, key=lambda l: (l.y0 + l.y1) / 2):
        mid = (ln.y0 + ln.y1) / 2
        r = rows[-1] if rows else None
        if r and abs((r.y0 + r.y1) / 2 - mid) < 6 and (ln.x0 > r.x1 or ln.x1 < r.x0):
            r.words = sorted(r.words + ln.words)
            r.x0, r.x1 = min(r.x0, ln.x0), max(r.x1, ln.x1)
            r.y0, r.y1 = min(r.y0, ln.y0), max(r.y1, ln.y1)
        else:
            rows.append(Line(ln.x0, ln.y0, ln.x1, ln.y1, list(ln.words)))
    return rows


def escape_md(text):
    """Escape Markdown/Marp-significant characters, but leave URLs intact as autolinks."""
    out, pos = [], 0
    for m in URL_RE.finditer(text):
        out.append(_esc(text[pos:m.start()]))
        url = m.group(0).rstrip(".,;:)")
        out.append(f"<{url}>" + m.group(0)[len(url):])
        pos = m.end()
    out.append(_esc(text[pos:]))
    return "".join(out)


def _esc(s):
    s = re.sub(r"([\\`*_\[\]<>$|])", r"\\\1", s)   # $ would trigger Marp math
    return s


def join_wrapped(text, line, prev_line, right_margin):
    """Join a soft-wrapped continuation `line` onto the accumulated `text`."""
    last = text.rstrip().split(" ")[-1]
    # A URL that ran into the right margin was broken mid-token: join without space.
    if URL_RE.match(last) and prev_line.x1 >= right_margin - 20:
        return text + line.text.lstrip()
    return text + " " + line.text.lstrip()


def is_soft_wrap(prev, cur, right_margin):
    """True if `cur` only starts a new line because its first word didn't fit on `prev`."""
    if cur.y0 - prev.y1 > PARA_GAP:
        return False
    if cur.words[0][2] in BULLETS or NUMBERED_RE.match(cur.words[0][2]):
        return False
    # A line starting with a URL, or "Label:", is a deliberate new line.
    if URL_RE.match(cur.words[0][2]) or cur.words[0][2].endswith(":"):
        return False
    # Parallel "Thing - description" lines are separate items, not a wrapped sentence.
    if " - " in cur.text and " - " in prev.text and cur.x0 <= prev.x0 + 2:
        return False
    first_w = cur.words[0][1] - cur.words[0][0]
    space = 8
    return prev.x1 + space + first_w > right_margin


def convert_page(lines, right_margin):
    title_lines = []
    while lines and lines[0].height >= TITLE_MIN_HEIGHT and (
            not title_lines or lines[0].y0 - title_lines[-1].y1 <= PARA_GAP):
        title_lines.append(lines.pop(0))
    title = " ".join(l.text for l in title_lines).strip()

    blocks = []   # each: {"kind": "bullet"/"para", "level": n, "lines": [str], "last": Line}
    prev = None
    for ln in lines:
        first = ln.words[0][2]
        if first in BULLETS:
            text = " ".join(w[2] for w in ln.words[1:])
            blocks.append({"kind": "bullet", "level": BULLETS[first],
                           "lines": [text], "last": ln, "gap": _gap(prev, ln)})
        elif NUMBERED_RE.match(first):
            text = " ".join(w[2] for w in ln.words[1:])
            blocks.append({"kind": "number", "level": 0, "num": first,
                           "lines": [text], "last": ln, "gap": _gap(prev, ln)})
        elif prev is not None and blocks and ln.y0 - prev.y1 <= PARA_GAP and (
                blocks[-1]["kind"] in ("bullet", "number") and ln.x0 > blocks[-1]["last"].x0 + 10
                or is_soft_wrap(prev, ln, right_margin)):
            # continuation of the previous bullet / paragraph line
            b = blocks[-1]
            b["lines"][-1] = join_wrapped(b["lines"][-1], ln, prev, right_margin)
            b["last"] = ln
        elif prev is not None and blocks and blocks[-1]["kind"] == "para" \
                and ln.y0 - prev.y1 <= PARA_GAP:
            # same paragraph, but a deliberate (hard) line break
            blocks[-1]["lines"].append(ln.text)
            blocks[-1]["last"] = ln
        else:
            blocks.append({"kind": "para", "level": 0, "lines": [ln.text],
                           "last": ln, "gap": _gap(prev, ln)})
        prev = ln
    return title, blocks


def _gap(prev, ln):
    return prev is not None and ln.y0 - prev.y1 > PARA_GAP


def render_blocks(blocks):
    out = []
    for i, b in enumerate(blocks):
        prev = blocks[i - 1] if i else None
        if b["kind"] in ("bullet", "number"):
            if prev is not None and prev["kind"] != b["kind"]:
                out.append("")
            marker = "- " if b["kind"] == "bullet" else b["num"].rstrip(".)") + ". "
            out.append("  " * b["level"] + marker + escape_md(b["lines"][0]))
        else:
            if out:
                out.append("")
            out.append("\\\n".join(escape_md(t) for t in b["lines"]))
    return "\n".join(out)


FRONT_MATTER = """---
marp: true
title: {title}
size: 4:3
paginate: true
backgroundImage: url('{bg}')
style: |
  @import url('https://fonts.googleapis.com/css2?family=Comic+Neue:wght@400;700&display=swap');
  section {{
    font-family: 'Comic Sans MS', 'Comic Neue', 'Chalkboard SE', cursive;
    color: #f4f4f4;
    font-size: 28px;
    padding: 40px 50px;
    place-content: start !important;
  }}
  h1 {{ color: #ffffff; font-size: 44px; margin-bottom: 0.6em; }}
  a {{ color: #9fd3ff; word-break: break-all; }}
  section.lead {{ place-content: safe center !important; text-align: center; }}
  section.lead h1 {{ font-size: 56px; }}
  section::after {{ color: #cccccc; }}
---
"""


def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else "kc0wih.pdf"
    out = Path(sys.argv[2] if len(sys.argv) > 2 else Path(pdf).with_suffix(".md"))
    assets = out.parent / f"{out.stem}-assets"
    assets.mkdir(exist_ok=True)

    # All 50 pages share one background image; extract it from page 1.
    subprocess.run(["pdfimages", "-j", "-f", "1", "-l", "1", pdf, str(assets / "bg")], check=True)
    bg_src = next(assets.glob("bg-000.*"))
    bg = assets / f"chalkboard{bg_src.suffix}"
    bg_src.rename(bg)

    title = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout
    m = re.search(r"^Title:\s*(.+)$", title, re.M)
    doc_title = m.group(1).strip() if m else out.stem

    pages = read_pages(pdf)
    right_margin = max(l.x1 for p in pages for l in p if l.height < TITLE_MIN_HEIGHT)

    slides = []
    for n, lines in enumerate(pages, 1):
        title, blocks = convert_page(list(lines), right_margin)
        parts = []
        if n == 1:
            # Title slide: large centred text, no explicit heading split in the PDF
            parts.append("<!-- _class: lead -->\n<!-- _paginate: false -->")
        if title:
            parts.append("# " + escape_md(title))
        body = render_blocks(blocks)
        if body:
            parts.append(body)
        slides.append("\n\n".join(parts))

    md = FRONT_MATTER.format(title=doc_title, bg=bg.relative_to(out.parent)) + "\n" + \
        "\n\n---\n\n".join(slides) + "\n"
    out.write_text(md, encoding="utf-8")
    print(f"Wrote {out} ({len(slides)} slides), background {bg}")


if __name__ == "__main__":
    main()
