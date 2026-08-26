#!/usr/bin/env python
"""Stitch a runtime-rewrite simulation's snapshots into one side-by-side sequence.

Composes the three loom renders of a place-graph rewrite (produced by the
matching build_*_snapshots.py + render_loom_svgs.mjs) into a single left-to-right
sequence with a time label over each panel and arrows between them — a faithful
time series of the running simulation. Shared by the Fig 9b division and Fig 10b
biofilm figures.

    python scripts/stitch_snapshot_sequence.py [division|biofilm|all]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
STUDIES = ROOT / "workspace" / "studies"

# Each panel is (image filename, time label). No stage titles, no caption —
# just the topology snapshots with t=0, t=1, t=2 … over them.
FIGURES = {
    "division": {
        "study": "fig-09",
        "out": "fig09b-division-sequence.png",
        "panels": [
            ("fig09b-division-1-onecell.png",    "t = 0"),
            ("fig09b-division-2-replicated.png", "t = 1"),
            ("fig09b-division-3-divided.png",    "t = 2"),
        ],
    },
    "biofilm": {
        "study": "fig-10",
        "out": "fig10-biofilm-sequence.png",
        "panels": [
            ("fig10-biofilm-1-planktonic.png",  "t = 0"),
            ("fig10-biofilm-2-microcolony.png", "t = 1"),
            ("fig10-biofilm-3-mature.png",      "t = 2"),
        ],
    },
}

INK = (24, 32, 40)
ARROW = (90, 100, 110)
PANEL_H = 640
GAP = 90
PAD = 40
LABEL_H = 70          # band above each panel for the time label


def _font(size, bold=False):
    for p in ["/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
              "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _trim(im):
    diff = ImageChops.difference(im.convert("RGB"), Image.new("RGB", im.size, (255, 255, 255)))
    bbox = diff.getbbox()
    return im.crop(bbox) if bbox else im


def stitch(cfg):
    viz = STUDIES / cfg["study"] / "visualizations"
    panels = []
    for fn, _ in cfg["panels"]:
        im = _trim(Image.open(viz / fn).convert("RGB"))
        panels.append(im.resize((int(im.width * PANEL_H / im.height), PANEL_H), Image.LANCZOS))

    label_f = _font(40, bold=True)
    col_w = max(p.width for p in panels) + 40
    n = len(panels)
    total_w = col_w * n + GAP * (n - 1) + 2 * PAD
    total_h = PAD + LABEL_H + PANEL_H + PAD

    canvas = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    for i, ((fn, tlabel), p) in enumerate(zip(cfg["panels"], panels)):
        x0 = PAD + i * (col_w + GAP)
        tw = draw.textlength(tlabel, font=label_f)
        draw.text((x0 + (col_w - tw) / 2, PAD + 14), tlabel, font=label_f, fill=INK)
        canvas.paste(p, (x0 + (col_w - p.width) // 2, PAD + LABEL_H))

    ay = PAD + LABEL_H + PANEL_H // 2
    for i in range(n - 1):
        gx = PAD + (i + 1) * col_w + i * GAP
        x0, x1 = gx + 30, gx + GAP - 40
        draw.line([(x0, ay), (x1, ay)], fill=ARROW, width=8)
        draw.polygon([(x1, ay - 22), (x1, ay + 22), (x1 + 30, ay)], fill=ARROW)

    out = viz / cfg["out"]
    canvas.save(out)
    print(f"wrote {out.relative_to(ROOT)}  ({canvas.width}x{canvas.height})")


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    keys = list(FIGURES) if which == "all" else [which]
    for k in keys:
        stitch(FIGURES[k])


if __name__ == "__main__":
    main()
