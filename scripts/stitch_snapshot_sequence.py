#!/usr/bin/env python
"""Stitch a runtime-rewrite simulation's snapshots into one sequence figure.

Composes the three loom renders of a place-graph rewrite (produced by the
matching build_*_snapshots.py + render_loom_svgs.mjs) into a single left-to-right
sequence with stage labels and arrows — a faithful time series of the running
simulation. Shared by the Fig 9b division and Fig 10b biofilm figures.

    python scripts/stitch_snapshot_sequence.py [division|biofilm|all]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
STUDIES = ROOT / "workspace" / "studies"

FIGURES = {
    "division": {
        "study": "fig-09",
        "out": "fig09b-division-sequence.png",
        "panels": [
            ("fig09b-division-1-onecell.png",    "1 — One cell",              "t = 0"),
            ("fig09b-division-2-replicated.png", "2 — Chromosome replicates", "t = 1 cycle"),
            ("fig09b-division-3-divided.png",    "3 — Cell divides",          "t = 2 cycles"),
        ],
        "caption": (
            "A genuine runtime place-graph rewrite: the composition starts as one cell and, on "
            "running, rewrites its own topology — nodes are added at simulation time, not "
            "pre-declared. Frames captured from the fig09-rewrite simulation."),
    },
    "biofilm": {
        "study": "fig-10",
        "out": "fig10-biofilm-sequence.png",
        "panels": [
            ("fig10-biofilm-1-planktonic.png",  "1 — Free motile bacteria",     "t = 0"),
            ("fig10-biofilm-2-microcolony.png", "2 — Attachment & aggregation", "t = attach"),
            ("fig10-biofilm-3-mature.png",      "3 — Mature biofilm (ECM)",     "t = mature"),
        ],
        "caption": (
            "Biofilm emergence as a genuine runtime place-graph rewrite: free motile bacteria "
            "attach to the surface and aggregate into a nested microcolony (losing motility), then "
            "the sessile community secretes extracellular matrix. Frames captured from the "
            "fig10-emergence simulation."),
    },
}

INK = (24, 32, 40)
ARROW = (90, 100, 110)
SUBTLE = (110, 120, 130)
PANEL_H = 900
PAD = 90
TITLE_GAP = 210
ARROW_W = 150


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


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def _center(draw, x0, colw, y, text, font, fill):
    draw.text((x0 + (colw - draw.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)


def stitch(cfg):
    viz = STUDIES / cfg["study"] / "visualizations"
    panels = []
    for fn, _, _ in cfg["panels"]:
        im = _trim(Image.open(viz / fn).convert("RGB"))
        panels.append(im.resize((int(im.width * PANEL_H / im.height), PANEL_H), Image.LANCZOS))

    title_f, time_f, cap_f = _font(44, bold=True), _font(34), _font(32)
    col_w = max(p.width for p in panels) + 40
    n = len(panels)
    total_w = col_w * n + ARROW_W * (n - 1) + 2 * PAD
    total_h = TITLE_GAP + PANEL_H + PAD + 120 + PAD

    canvas = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    for i, ((fn, title, tlabel), p) in enumerate(zip(cfg["panels"], panels)):
        x0 = PAD + i * (col_w + ARROW_W)
        lines = _wrap(draw, title, title_f, col_w)
        for j, line in enumerate(lines):
            _center(draw, x0, col_w, 24 + j * 52, line, title_f, INK)
        _center(draw, x0, col_w, 24 + len(lines) * 52 + 6, tlabel, time_f, SUBTLE)
        canvas.paste(p, (x0 + (col_w - p.width) // 2, TITLE_GAP))

    ay = TITLE_GAP + PANEL_H // 2
    for i in range(n - 1):
        gx = PAD + (i + 1) * col_w + i * ARROW_W
        x0, x1 = gx + 30, gx + ARROW_W - 40
        draw.line([(x0, ay), (x1, ay)], fill=ARROW, width=8)
        draw.polygon([(x1, ay - 22), (x1, ay + 22), (x1 + 30, ay)], fill=ARROW)

    cy = TITLE_GAP + PANEL_H + PAD
    for line in _wrap(draw, cfg["caption"], cap_f, total_w - 2 * PAD):
        draw.text((PAD, cy), line, font=cap_f, fill=SUBTLE)
        cy += 44

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
