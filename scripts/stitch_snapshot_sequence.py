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
# Two compact snapshots per figure, arranged to pack tightly beside the a-panel.
# Orientation is chosen by frame shape: tall-narrow frames sit side-by-side
# (horizontal); wide-short frames stack top-to-bottom (vertical) to stay narrow.
FIGURES = {
    "division": {
        "study": "fig-09",
        "out": "fig09b-division-sequence.png",
        "stack": "horizontal",   # tall, narrow cell/chromosome trees
        "panels": [
            ("fig09b-division-1-onecell.png",    "t = 0"),   # one cell, one chromosome
            ("fig09b-division-2-replicated.png", "t = 1"),   # one cell, chromosome replicated → two
            ("fig09b-division-3-divided.png",    "t = 2"),   # divided into two daughter cells
        ],
    },
    "biofilm": {
        "study": "fig-10",
        "out": "fig10-biofilm-sequence.png",
        "stack": "vertical",     # wide frames → stack to keep the block narrow
        "panels": [
            ("fig10-biofilm-1-planktonic.png", "t = 0"),
            ("fig10-biofilm-3-mature.png",     "t = 1"),
        ],
    },
    "evolution": {
        "study": "fig-11",
        "out": "fig11-evolution-sequence.png",
        "stack": "vertical",     # wide population rows → stack top-to-bottom
        "panels": [
            ("fig11-evo-1-founder.png",  "t = 0"),
            ("fig11-evo-2-adapted.png",  "t = 40"),
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


def stitch_vertical(cfg):
    """Top-to-bottom stack — for wide, short frames (e.g. a population row) that
    would be squeezed side-by-side. Each frame is normalized to a common WIDTH,
    with its time label to the left and down-arrows between panels."""
    viz = STUDIES / cfg["study"] / "visualizations"
    panel_w = 2600
    raw = [_trim(Image.open(viz / fn).convert("RGB")) for fn, _ in cfg["panels"]]
    # ONE scale factor for all frames (widest frame fills panel_w) so a cell is
    # the SAME size in every snapshot — you watch 1 node grow into a full row,
    # not each frame rescaled to the column width.
    scale = panel_w / max(im.width for im in raw)
    panels = [im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS) for im in raw]

    label_f = _font(46, bold=True)
    label_col = 180                      # left gutter for the t = … label
    row_gap = 200                        # room for a clear arrow fully inside the gap
    n = len(panels)
    total_w = PAD + label_col + panel_w + PAD
    total_h = PAD + sum(p.height for p in panels) + row_gap * (n - 1) + PAD

    canvas = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    y = PAD
    x0 = PAD + label_col
    for i, ((fn, tlabel), p) in enumerate(zip(cfg["panels"], panels)):
        draw.text((PAD, y + p.height // 2 - 24), tlabel, font=label_f, fill=INK)
        canvas.paste(p, (x0 + (panel_w - p.width) // 2, y))   # centered in the column
        if i < n - 1:
            # A clear down-arrow centered in the gap between the two snapshots —
            # fully contained so it never clips into the panel below.
            ax = x0 + panel_w // 2
            gap_top = y + p.height
            head_w, head_h = 34, 46
            ay0 = gap_top + 44                          # shaft start
            tip = gap_top + row_gap - 44                # arrow tip
            ay1 = tip - head_h                          # shaft end / head base
            draw.line([(ax, ay0), (ax, ay1)], fill=ARROW, width=11)
            draw.polygon([(ax - head_w, ay1), (ax + head_w, ay1), (ax, tip)], fill=ARROW)
        y += p.height + row_gap

    out = viz / cfg["out"]
    canvas.save(out)
    print(f"wrote {out.relative_to(ROOT)}  ({canvas.width}x{canvas.height})")


def stitch(cfg):
    if cfg.get("stack") == "vertical":
        return stitch_vertical(cfg)
    # Horizontal: side-by-side with ONE scale factor (tallest frame fills the
    # target height) so a node is the same size in every frame — the population/
    # cell grows between panels rather than each frame being rescaled to fit.
    viz = STUDIES / cfg["study"] / "visualizations"
    target_h = 1500
    raw = [_trim(Image.open(viz / fn).convert("RGB")) for fn, _ in cfg["panels"]]
    scale = target_h / max(im.height for im in raw)
    panels = [im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS) for im in raw]

    label_f = _font(46, bold=True)
    label_h = 80
    col_w = max(p.width for p in panels) + 40
    row_h = max(p.height for p in panels)
    n = len(panels)
    total_w = col_w * n + GAP * (n - 1) + 2 * PAD
    total_h = PAD + label_h + row_h + PAD

    canvas = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    for i, ((fn, tlabel), p) in enumerate(zip(cfg["panels"], panels)):
        x0 = PAD + i * (col_w + GAP)
        tw = draw.textlength(tlabel, font=label_f)
        draw.text((x0 + (col_w - tw) / 2, PAD + 16), tlabel, font=label_f, fill=INK)
        canvas.paste(p, (x0 + (col_w - p.width) // 2, PAD + label_h))

    ay = PAD + label_h + row_h // 2
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
