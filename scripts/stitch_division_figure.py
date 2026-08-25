#!/usr/bin/env python
"""Stitch the three division snapshots into one sequence figure.

Composes the three loom renders produced by build_division_snapshots.py +
render_loom_svgs.mjs into a single left-to-right sequence with stage labels and
arrows — the runtime place-graph rewrite of Fig 9b (one cell -> chromosome
replicates -> cell divides), read as a time series of the running simulation.

Output: workspace/studies/fig-09/visualizations/fig09b-division-sequence.png

    python scripts/stitch_division_figure.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
VIZ = ROOT / "workspace" / "studies" / "fig-09" / "visualizations"

PANELS = [
    ("fig09b-division-1-onecell.png",    "1 — One cell",             "t = 0"),
    ("fig09b-division-2-replicated.png", "2 — Chromosome replicates", "t = 1 cycle"),
    ("fig09b-division-3-divided.png",    "3 — Cell divides",          "t = 2 cycles"),
]

INK = (24, 32, 40)
ARROW = (90, 100, 110)
SUBTLE = (110, 120, 130)
PANEL_H = 900          # px height each loom panel is scaled to
PAD = 90              # white padding around/between panels
TITLE_GAP = 210       # space above panels for stage titles (fits 2-line titles + time)
ARROW_W = 150         # horizontal gap reserved for the → between panels


def _font(size, bold=False):
    for p in ([
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _trim(im: Image.Image) -> Image.Image:
    bg = Image.new("RGB", im.size, (255, 255, 255))
    diff = ImageChops.difference(im.convert("RGB"), bg)
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
    tw = draw.textlength(text, font=font)
    draw.text((x0 + (colw - tw) / 2, y), text, font=font, fill=fill)


def main() -> None:
    panels = []
    for fn, _, _ in PANELS:
        im = _trim(Image.open(VIZ / fn).convert("RGB"))
        w = int(im.width * PANEL_H / im.height)
        panels.append(im.resize((w, PANEL_H), Image.LANCZOS))

    title_f = _font(44, bold=True)
    time_f = _font(34)
    cap_f = _font(32)

    col_w = max(p.width for p in panels) + 40           # equal columns, no title collisions
    n = len(panels)
    total_w = col_w * n + ARROW_W * (n - 1) + 2 * PAD
    total_h = TITLE_GAP + PANEL_H + PAD + 120 + PAD

    canvas = Image.new("RGB", (total_w, total_h), (255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    for i, ((fn, title, tlabel), p) in enumerate(zip(PANELS, panels)):
        x0 = PAD + i * (col_w + ARROW_W)
        lines = _wrap(draw, title, title_f, col_w)
        for j, line in enumerate(lines):
            _center(draw, x0, col_w, 24 + j * 52, line, title_f, INK)
        _center(draw, x0, col_w, 24 + len(lines) * 52 + 6, tlabel, time_f, SUBTLE)
        canvas.paste(p, (x0 + (col_w - p.width) // 2, TITLE_GAP))

    # arrows centered in the reserved gaps, vertically centered on the panels
    ay = TITLE_GAP + PANEL_H // 2
    for i in range(n - 1):
        gx = PAD + (i + 1) * col_w + i * ARROW_W
        x0, x1 = gx + 30, gx + ARROW_W - 40
        draw.line([(x0, ay), (x1, ay)], fill=ARROW, width=8)
        draw.polygon([(x1, ay - 22), (x1, ay + 22), (x1 + 30, ay)], fill=ARROW)

    caption = ("A genuine runtime place-graph rewrite: the composition starts as one cell and, on "
               "running, rewrites its own topology — nodes are added at simulation time, not "
               "pre-declared. Frames captured from the fig09-rewrite simulation.")
    cy = TITLE_GAP + PANEL_H + PAD
    for line in _wrap(draw, caption, cap_f, total_w - 2 * PAD):
        draw.text((PAD, cy), line, font=cap_f, fill=SUBTLE)
        cy += 44

    out = VIZ / "fig09b-division-sequence.png"
    canvas.save(out)
    print(f"wrote {out.relative_to(ROOT)}  ({canvas.width}x{canvas.height})")


if __name__ == "__main__":
    main()
