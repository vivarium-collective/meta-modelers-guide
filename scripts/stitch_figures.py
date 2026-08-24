#!/usr/bin/env python
"""Stitch publication figures: keep the paper's BioRender illustration panel(s)
and replace the hand-drawn bigraph diagram(s) with bigraph-loom renders, adding
bold panel labels (a., b., …) in the paper's style.

Panels compose recursively as row/col groups, so a figure can be a simple pair
(fig 5), a vertical stack (fig 4), a biorender beside two stacked looms (fig 9),
or a grid (fig 10).

Output per figure: ``workspace/studies/<study>/visualizations/figure_<N>.{png,svg}``
— the workbench's "final figures" (Figures tab + ``↓ figures`` download).

Run:  python scripts/stitch_figures.py [--only 5]
"""
from __future__ import annotations

import argparse
import base64
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
STUDIES = ROOT / "workspace" / "studies"
PAPER_FIGS = ROOT / "assets" / "biorender"  # source BioRender illustration PDFs (in-repo)

DPI = 300
LOOM_MARGIN = 0.012     # white padding around a loom panel (fraction of its min dim)
LOOM_RASTER_W = 3600   # px width for rsvg rasterization (unused; loom uses browser PNG)


# ── panel constructors ────────────────────────────────────────────────────
# `scale` (0<scale<=1) shrinks a panel within its row/col cell — e.g. a single
# store node that would otherwise stretch to the row height.
def bio(stem, box, label=None, scale=1.0):
    return {"kind": "biorender", "stem": stem, "box": box, "label": label, "scale": scale}


def loom(study, stem, label=None, scale=1.0):
    return {"kind": "loom", "study": study, "stem": stem, "label": label, "scale": scale}


def group(layout, panels, label=None, scale=1.0):
    return {"kind": "group", "layout": layout, "panels": panels, "label": label, "scale": scale}


def rawimg(path, label=None, scale=1.0, rotate=0, crop=None):
    """A finished figure image used as-is (e.g. a hand-created orchestration
    figure with its own a./b./c. labels already baked in). `rotate` is degrees
    clockwise (90/180/270); `crop` is (x0,y0,x1,y1) fractions, applied first."""
    return {"kind": "rawimg", "path": path, "label": label, "scale": scale, "rotate": rotate, "crop": crop}


PANELS = ROOT / "assets" / "biorender" / "panels"


def panel(name, label=None, scale=1.0, rotate=0, crop=None):
    """A clean, pre-cropped BioRender illustration panel (no baked labels)."""
    return rawimg(str(PANELS / name), label, scale, rotate, crop)


# ── figure recipes ────────────────────────────────────────────────────────
# Numbering follows the paper AFTER the overview (old Fig 1) was dropped:
# process bigraph is now Fig 1, orchestration Fig 2, … evolution Fig 11.
FIGURES: dict[int, dict] = {
    1: {"study": "fig-02", "root": group("col", [
        group("row", [
            loom("fig-02", "fig02a-process", "a"),           # a generic process (full contract)
            loom("fig-02", "fig02b-store-hierarchy", "b"),   # a biological store hierarchy w/ units
        ]),
        loom("fig-02", "fig02c-bio-bigraph", "c"),           # a biological process bigraph
    ])},
    2: {"study": "fig-03", "root":   # orchestration — hand-created figure (a/b/c baked in)
        rawimg(str(ROOT / "assets" / "orchestration.tif")),
    },
    3: {"study": "fig-04", "root": group("row", [   # a (illustration) left of b (loom card)
        panel("fig04a.png", "a"),
        loom("fig-04", "fig04b-cellular-interface", "b"),
    ])},
    4: {"study": "fig-05", "root": group("row", [
        panel("fig05a.png", "a"),
        loom("fig-05", "fig05-cell-environment", "b"),
    ])},
    5: {"study": "fig-06", "root": group("row", [   # a rotated vertical (healthy top→disintegrated bottom), b to its right
        panel("fig06a.png", "a", rotate=90),
        loom("fig-06", "fig06b-grain-swap", "b"),
    ])},
    6: {"study": "fig-07", "root": group("row", [   # a (illustration) left of b (loom card)
        panel("fig07a.png", "a"),
        loom("fig-07", "fig07-molecular-mechanism", "b"),
    ])},
    7: {"study": "fig-08", "root": group("col", [   # 8a a wide banner on top, 8b full-width across below
        panel("fig08a.png", "a", crop=(0.0, 0.296, 1.0, 0.704)),  # ~6/5 taller banner band
        loom("fig-08", "fig08-nested-hierarchy", "b"),
    ])},
    8: {"study": "fig-09", "root": group("row", [
        panel("fig09a.png", "a"),
        group("col", [
            loom("fig-09", "fig09b-minimal-cell"),
            loom("fig-09", "fig09a-coarse-graining"),
        ], "b"),
    ])},
    # growth/division, development, evolution
    9: {"study": "fig-10-1", "root": group("row", [
        panel("fig10a.png", "a", scale=0.65),
        loom("fig-10-1", "fig10-1-division", "b"),
    ])},
    10: {"study": "fig-10-2", "root": group("row", [
        panel("fig10c.png", "a", scale=0.9),
        loom("fig-10-2", "fig10-2-development", "b"),
    ])},
    11: {"study": "fig-10-3", "root": group("row", [
        panel("fig10e.png", "a"),
        loom("fig-10-3", "fig10-3-evolution", "b"),
    ])},
}


def _font(pt: int) -> ImageFont.FreeTypeFont:
    for cand in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial Bold.ttf"):
        try:
            return ImageFont.truetype(cand, pt)
        except Exception:
            continue
    return ImageFont.load_default()


def _trim(im: Image.Image) -> Image.Image:
    bg = Image.new("RGBA", im.size, (255, 255, 255, 0))
    bbox = ImageChops.difference(im.convert("RGBA"), bg).getbbox()
    return im.crop(bbox) if bbox else im


def _biorender_panel(stem: str, box) -> Image.Image:
    pdf = PAPER_FIGS / f"{stem}.pdf"
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "p"
        subprocess.run(["pdftoppm", "-png", "-r", str(DPI), "-singlefile", str(pdf), str(out)],
                       check=True, capture_output=True)
        full = Image.open(out.with_suffix(".png")).convert("RGBA")
    w, h = full.size
    x0, y0, x1, y1 = box
    return _trim(full.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h))))


def _loom_panel(study: str, stem: str) -> Image.Image:
    """Browser-rendered loom PNG (react-flow nodes are HTML foreignObject — rsvg
    can't render them), trimmed + white padding so nothing touches the edge."""
    im = _trim(Image.open(STUDIES / study / "visualizations" / f"{stem}.png").convert("RGBA"))
    pad = int(min(im.width, im.height) * LOOM_MARGIN)
    canvas = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (255, 255, 255, 255))
    canvas.alpha_composite(im, (pad, pad))
    return canvas


def _rawimg_panel(path, rotate=0, crop=None) -> Image.Image:
    """Load a finished figure image (TIFF/PNG, possibly transparent), flatten
    onto white, optionally crop (fractions) then rotate (deg cw), trim, pad."""
    im = Image.open(path).convert("RGBA")
    flat = Image.new("RGBA", im.size, (255, 255, 255, 255))
    flat.alpha_composite(im)
    im = flat
    if crop:
        w, h = im.size
        x0, y0, x1, y1 = crop
        im = im.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    if rotate % 360:
        tr = {90: Image.ROTATE_270, 180: Image.ROTATE_180, 270: Image.ROTATE_90}.get(rotate % 360)
        if tr is not None:
            im = im.transpose(tr)
    im = _trim(im)
    pad = int(min(im.width, im.height) * LOOM_MARGIN)
    canvas = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (255, 255, 255, 255))
    canvas.alpha_composite(im, (pad, pad))
    return canvas


def _render(item) -> tuple[Image.Image, str | None, float]:
    sc = item.get("scale", 1.0)
    if item["kind"] == "biorender":
        return _biorender_panel(item["stem"], item["box"]), item.get("label"), sc
    if item["kind"] == "loom":
        return _loom_panel(item["study"], item["stem"]), item.get("label"), sc
    if item["kind"] == "rawimg":
        return _rawimg_panel(item["path"], item.get("rotate", 0), item.get("crop")), item.get("label"), sc
    kids = [_render(p) for p in item["panels"]]
    return _compose(kids, item["layout"]), item.get("label"), sc


def _compose(children: list[tuple[Image.Image, str | None, float]], layout: str) -> Image.Image:
    """Compose children in a row/col. `unit` is the common extent (row height /
    col width); a child with scale<1 is shrunk to `unit*scale` and centred in a
    full `unit` cell, so a small panel doesn't get stretched to the giants."""
    if layout == "row":
        unit = max(im.height for im, _, _ in children)
        cells = []
        for im, lb, sc in children:
            th = max(1, int(unit * sc))
            r = im if im.height == th else im.resize((max(1, int(im.width * th / im.height)), th), Image.LANCZOS)
            cells.append((r, lb, unit))          # cell height = unit
    elif layout == "coln":
        # native column: stack children WITHOUT matching widths (each keeps its
        # own scale), so sibling loom panels retain identical font sizes. Only a
        # per-panel `scale` shrinks a child; narrower children are centred.
        scaled = [(im if sc == 1 else im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.LANCZOS), lb)
                  for im, lb, sc in children]
        unit = max(im.width for im, _ in scaled)
        cells = [(im, lb, unit) for im, lb in scaled]      # cell width = unit (canvas); image at native
    else:
        unit = max(im.width for im, _, _ in children)
        cells = []
        for im, lb, sc in children:
            tw = max(1, int(unit * sc))
            r = im if im.width == tw else im.resize((tw, max(1, int(im.height * tw / im.width))), Image.LANCZOS)
            cells.append((r, lb, unit))          # cell width = unit

    label_pt = max(40, int(unit * (0.055 if layout == "row" else 0.032)))
    gap = int(unit * 0.008)
    margin = int(unit * 0.005)
    labelled = any(lb for _, lb, _ in cells)
    header = int(label_pt * 1.0) if labelled else 0   # label band, only where labels exist
    font = _font(label_pt)

    if layout == "row":
        # one shared header band across the row (labels sit on the same baseline)
        total_w = margin * 2 + sum(r.width for r, _, _ in cells) + gap * (len(cells) - 1)
        total_h = margin * 2 + header + unit
        canvas = Image.new("RGBA", (total_w, total_h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        x = margin
        for r, label, cell_h in cells:
            if label:
                draw.text((x, margin), f"{label}.", fill=(0, 0, 0, 255), font=font)
            canvas.alpha_composite(r, (x, margin + header + (cell_h - r.height) // 2))
            x += r.width + gap
    else:
        # per-cell header: only a labelled cell reserves label space above it
        hdrs = [header if lb else 0 for _, lb, _ in cells]
        total_w = margin * 2 + unit
        total_h = margin * 2 + sum(h + r.height for h, (r, _, _) in zip(hdrs, cells)) + gap * (len(cells) - 1)
        canvas = Image.new("RGBA", (total_w, total_h), (255, 255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        y = margin
        for h, (r, label, cell_w) in zip(hdrs, cells):
            if label:
                draw.text((margin, y), f"{label}.", fill=(0, 0, 0, 255), font=font)
            canvas.alpha_composite(r, (margin + (cell_w - r.width) // 2, y + h))
            y += h + r.height + gap
    return canvas


# Cap the stored figure resolution. The panels render at very high res; at the
# paper's column width (or on the web) anything past a few thousand px is
# invisible, but the base64-in-SVG files blow past GitHub's 100 MB limit. 5000 px
# on the long edge is ~2× a full-column figure at 300 dpi — plenty.
MAX_DIM = 5000


def stitch(n: int, recipe: dict) -> None:
    img, _, _ = _render(recipe["root"])
    if max(img.size) > MAX_DIM:
        s = MAX_DIM / max(img.size)
        img = img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)
    viz = STUDIES / recipe["study"] / "visualizations"
    viz.mkdir(parents=True, exist_ok=True)
    png = viz / f"figure_{n}.png"
    img.convert("RGB").save(png, "PNG")
    b64 = base64.b64encode(png.read_bytes()).decode()
    (viz / f"figure_{n}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{img.width}" height="{img.height}" '
        f'viewBox="0 0 {img.width} {img.height}"><image width="{img.width}" height="{img.height}" '
        f'href="data:image/png;base64,{b64}"/></svg>', encoding="utf-8")
    print(f"figure_{n}: {png.relative_to(ROOT)}  ({img.width}x{img.height})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, default=None)
    a = ap.parse_args()
    for n, recipe in FIGURES.items():
        if a.only and n != a.only:
            continue
        stitch(n, recipe)


if __name__ == "__main__":
    main()
