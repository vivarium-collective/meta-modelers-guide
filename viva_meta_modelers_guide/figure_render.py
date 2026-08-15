"""Paper-styled SVG renderer for the meta-modeler's-guide figure composites.

Renders a process-bigraph composite spec as a figure in the visual language of
*A meta-modeler's guide to the cellular interface*: nested rounded **compartment
panels** hold typed **store** nodes drawn with a glyph + name + unit; **process**
boxes list their ports (with units) and wire to the stores they read (dashed,
arrow into the process) and write (arrow out to the store).

Self-contained: emits an SVG string with hand-drawn vector glyphs (no external
fonts/emoji, so it rasterizes identically everywhere). Build a composite's core
with :func:`viva_meta_modelers_guide.core.build_core` and pass the spec's
``state`` dict.

    from viva_meta_modelers_guide.core import build_core
    from viva_meta_modelers_guide.figure_render import render_composite
    svg = render_composite(spec["state"], build_core(), title=spec["name"])
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field

from ._types import UNITS

# ── palette ──────────────────────────────────────────────────────────────────
INK = "#233"
MUTED = "#6b7785"
PAGE_BG = "#ffffff"
PROC_FILL = "#ffffff"
PROC_STROKE = "#33404d"
WIRE_IN = "#3a7ca5"     # store → process (read)
WIRE_OUT = "#c65b34"    # process → store (write)

# quantity family → accent colour (used for the store glyph)
FAMILY = {
    "chemical_flux": "#2a9d8f", "concentration": "#2a9d8f", "ph": "#2a9d8f",
    "force": "#e8863c", "mass": "#8a6d3b", "area": "#e8863c", "volume": "#e8863c",
    "length": "#e8863c",
    "current": "#8e6bb0", "voltage": "#8e6bb0",
    "heat_flux": "#d1495b", "temperature": "#d1495b", "energy": "#e6a817",
    "entropy": "#d1495b",
    "growth_rate": "#4c956c", "viability": "#4c956c", "objective": "#4c956c",
    "rate": "#4c956c", "time": "#6b7785", "fraction": "#6b7785",
    "signaling_rate": "#5a7d9a", "information": "#5a7d9a",
    "count": "#7a8794", "cell_count": "#7a8794",
    "structure": "#3d6fb0", "sequence": "#3d6fb0", "identity": "#3d6fb0",
}
DEFAULT_ACCENT = "#7a8794"

# compartment name keyword → panel tint (fill, stroke)
COMPARTMENT_TINT = [
    (("environ", "environment"), ("#eef5fb", "#b9d4e8")),
    (("membrane",), ("#fdf1dc", "#e7c896")),
    (("nucleus", "chromosome", "chromatin", "nucleosome"), ("#f3ecfa", "#cdb6e6")),
    (("cytoplasm",), ("#eef2f5", "#c2ccd6")),
    (("matrix", "ecm", "extracellular"), ("#eaf5ec", "#b6dcc0")),
    (("organelle", "mitochond", "ribosom", "secretory"), ("#e8f4f2", "#a9d8d0")),
    (("biofilm", "colony", "community"), ("#eaf5ec", "#b6dcc0")),
    (("interface", "ports", "subports"), ("#f2f4f7", "#cfd7e0")),
    (("cell", "daughter", "variant"), ("#eef2f5", "#c2ccd6")),
]
DEFAULT_TINT = ("#f6f7f9", "#d8dee5")

# ── geometry constants ───────────────────────────────────────────────────────
PAD = 14                 # page margin
PANEL_PAD = 12           # inside a compartment panel
PANEL_GAP = 10           # between siblings
LEAF_W, LEAF_H = 150, 30
HEADER_H = 20            # compartment title band
PROC_W = 210
PROC_HEADER = 34
PORT_H = 17
PROC_GAP = 16
RAIL_GAP = 70            # gap between process rail and store panels
FONT = "Helvetica, Arial, sans-serif"


def _tint(name: str):
    n = name.lower()
    for keys, tint in COMPARTMENT_TINT:
        if any(k in n for k in keys):
            return tint
    return DEFAULT_TINT


def _accent(leaf_type: str) -> str:
    return FAMILY.get(leaf_type, DEFAULT_ACCENT)


def _unit(leaf_type: str) -> str:
    return UNITS.get(leaf_type, "")


def _tw(text: str, size: float) -> float:
    return len(text) * size * 0.58


# ── model ────────────────────────────────────────────────────────────────────
@dataclass
class Leaf:
    name: str
    ltype: str
    path: tuple
    x: float = 0
    y: float = 0
    w: float = LEAF_W
    h: float = LEAF_H


@dataclass
class Panel:
    name: str
    path: tuple
    children: list = field(default_factory=list)   # Panel | Leaf
    x: float = 0
    y: float = 0
    w: float = 0
    h: float = 0


@dataclass
class Proc:
    name: str
    cls: str
    inputs: dict          # port -> path (tuple)
    outputs: dict         # port -> path (tuple)
    ptypes: dict          # port -> type
    summary: str
    x: float = 0
    y: float = 0
    w: float = PROC_W
    h: float = 0


def _is_leaf(v) -> bool:
    return isinstance(v, dict) and "_type" in v


def _build_stores(state: dict, path=()) -> list:
    """Return a forest of Panel/Leaf for the non-process entries of ``state``."""
    nodes = []
    for key, val in state.items():
        if isinstance(val, dict) and val.get("_type") == "process":
            continue
        p = path + (key,)
        if _is_leaf(val):
            nodes.append(Leaf(key, val["_type"], p))
        elif isinstance(val, dict):
            nodes.append(Panel(key, p, _build_stores(val, p)))
        else:  # bare scalar
            nodes.append(Leaf(key, "float", p))
    return nodes


def _build_procs(state: dict, core) -> list:
    procs = []
    for key, val in state.items():
        if not (isinstance(val, dict) and val.get("_type") == "process"):
            continue
        cls = str(val.get("address", "")).split(":")[-1]
        ptypes, summary = {}, ""
        reg = getattr(core, "link_registry", {})
        klass = reg.get(cls)
        if klass is not None:
            try:
                ptypes.update({p: t for p, t in klass.inputs(klass).items()})
                ptypes.update({p: t for p, t in klass.outputs(klass).items()})
            except Exception:
                pass
            try:
                summary = klass.__new__(klass).describe()
            except Exception:
                summary = ""
        summary = summary.replace("DRAFT —", "").split("·")[0].strip()
        to_tuple = lambda v: tuple(v) if isinstance(v, list) else (v,)
        procs.append(Proc(
            name=key, cls=cls,
            inputs={p: to_tuple(v) for p, v in (val.get("inputs") or {}).items()},
            outputs={p: to_tuple(v) for p, v in (val.get("outputs") or {}).items()},
            ptypes=ptypes, summary=summary,
        ))
    return procs


# ── layout ───────────────────────────────────────────────────────────────────
def _measure(node) -> None:
    if isinstance(node, Leaf):
        node.w, node.h = LEAF_W, LEAF_H
        return
    # panel: measure children, pack in a grid of up to `cols` columns
    for c in node.children:
        _measure(c)
    n = len(node.children)
    cols = 1 if n <= 4 else (2 if n <= 10 else 3)
    rows = [node.children[i:i + cols] for i in range(0, n, cols)]
    col_w = max((c.w for c in node.children), default=LEAF_W)
    inner_w = cols * col_w + (cols - 1) * PANEL_GAP if n else LEAF_W
    inner_h = 0
    for row in rows:
        inner_h += max(c.h for c in row) + PANEL_GAP
    inner_h = max(inner_h - PANEL_GAP, 0)
    node._cols = cols
    node._col_w = col_w
    node.w = inner_w + 2 * PANEL_PAD
    node.h = HEADER_H + inner_h + 2 * PANEL_PAD if n else HEADER_H + 2 * PANEL_PAD


def _place(node, x, y) -> None:
    node.x, node.y = x, y
    if isinstance(node, Leaf):
        return
    cols = getattr(node, "_cols", 1)
    col_w = getattr(node, "_col_w", LEAF_W)
    cx0 = x + PANEL_PAD
    cy = y + HEADER_H + PANEL_PAD
    for i in range(0, len(node.children), cols):
        row = node.children[i:i + cols]
        rh = max(c.h for c in row)
        for j, c in enumerate(row):
            _place(c, cx0 + j * (col_w + PANEL_GAP), cy)
        cy += rh + PANEL_GAP


def _anchor(path, forest_index):
    node = forest_index.get(tuple(path))
    if node is None and len(path) > 1:      # wire may target a compartment
        node = forest_index.get(tuple(path[:-1]))
    if node is None:
        return None
    return node


def _index(nodes, idx):
    for n in nodes:
        idx[n.path] = n
        if isinstance(n, Panel):
            _index(n.children, idx)


# ── svg emit ─────────────────────────────────────────────────────────────────
def _glyph(ltype, cx, cy, accent):
    """A small vector icon for a store type (rasterizes without fonts)."""
    a = accent
    if ltype in ("chemical_flux", "concentration", "ph"):
        return (f'<circle cx="{cx-3}" cy="{cy-2}" r="2.4" fill="{a}"/>'
                f'<circle cx="{cx+3}" cy="{cy-3}" r="1.8" fill="{a}"/>'
                f'<circle cx="{cx}" cy="{cy+3}" r="2.1" fill="{a}"/>')
    if ltype in ("force", "mass", "area", "volume", "length"):
        return (f'<path d="M{cx-5},{cy} L{cx+3},{cy} M{cx},{cy-4} L{cx+4},{cy} '
                f'L{cx},{cy+4}" stroke="{a}" stroke-width="2.2" fill="none" '
                f'stroke-linecap="round" stroke-linejoin="round"/>')
    if ltype in ("current", "voltage"):
        return (f'<path d="M{cx+1},{cy-5} L{cx-4},{cy+1} L{cx},{cy+1} '
                f'L{cx-1},{cy+5} L{cx+4},{cy-1} L{cx},{cy-1} Z" fill="{a}"/>')
    if ltype in ("heat_flux", "temperature", "energy", "entropy"):
        return (f'<path d="M{cx},{cy-5} L{cx+1.4},{cy-1.4} L{cx+5},{cy} '
                f'L{cx+1.4},{cy+1.4} L{cx},{cy+5} L{cx-1.4},{cy+1.4} '
                f'L{cx-5},{cy} L{cx-1.4},{cy-1.4} Z" fill="{a}"/>')
    if ltype in ("sequence", "structure", "identity"):
        return (f'<path d="M{cx-4},{cy-5} q4,3 0,5 q-4,3 0,5 M{cx+4},{cy-5} '
                f'q-4,3 0,5 q4,3 0,5" stroke="{a}" stroke-width="1.6" '
                f'fill="none" stroke-linecap="round"/>')
    if ltype in ("count", "cell_count"):
        return (f'<circle cx="{cx-2}" cy="{cy+1}" r="3" fill="none" stroke="{a}" stroke-width="1.6"/>'
                f'<circle cx="{cx+2}" cy="{cy-1}" r="3" fill="none" stroke="{a}" stroke-width="1.6"/>')
    if ltype in ("growth_rate", "viability", "objective", "rate"):
        return (f'<path d="M{cx},{cy+5} L{cx},{cy-5} M{cx-3},{cy-1} L{cx},{cy-5} '
                f'L{cx+3},{cy-1}" stroke="{a}" stroke-width="2" fill="none" '
                f'stroke-linecap="round" stroke-linejoin="round"/>')
    if ltype in ("signaling_rate", "information"):
        return (f'<path d="M{cx-5},{cy+2} q2.5,-7 5,0 q2.5,7 5,0" stroke="{a}" '
                f'stroke-width="1.8" fill="none" stroke-linecap="round"/>')
    return f'<circle cx="{cx}" cy="{cy}" r="3.2" fill="{a}"/>'


def _esc(s):
    return html.escape(str(s), quote=True)


def _draw_node(node, out):
    if isinstance(node, Panel):
        fill, stroke = _tint(node.name)
        out.append(
            f'<rect x="{node.x:.1f}" y="{node.y:.1f}" width="{node.w:.1f}" '
            f'height="{node.h:.1f}" rx="12" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="1.3"/>')
        out.append(
            f'<text x="{node.x+12:.1f}" y="{node.y+14:.1f}" font-family="{FONT}" '
            f'font-size="11.5" font-weight="600" fill="{INK}" '
            f'letter-spacing="0.3">{_esc(node.name.replace("_"," ").upper())}</text>')
        for c in node.children:
            _draw_node(c, out)
    else:  # Leaf
        accent = _accent(node.ltype)
        unit = _unit(node.ltype)
        out.append(
            f'<rect x="{node.x:.1f}" y="{node.y:.1f}" width="{node.w:.1f}" '
            f'height="{node.h:.1f}" rx="8" fill="#ffffff" stroke="{accent}" '
            f'stroke-width="1.3"/>')
        out.append(_glyph(node.ltype, node.x + 15, node.y + node.h / 2, accent))
        label = node.name.replace("_", " ")
        out.append(
            f'<text x="{node.x+28:.1f}" y="{node.y+13:.1f}" font-family="{FONT}" '
            f'font-size="10.5" font-weight="600" fill="{INK}">{_esc(label)}</text>')
        if unit:
            out.append(
                f'<text x="{node.x+28:.1f}" y="{node.y+24:.1f}" font-family="{FONT}" '
                f'font-size="8.5" fill="{MUTED}">{_esc(unit)}</text>')


def _wrap(text, width_chars):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= width_chars:
            cur = f"{cur} {w}".strip()
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines[:3]


def _draw_proc(proc, out):
    ports = list(proc.inputs) + [p for p in proc.outputs if p not in proc.inputs]
    out.append(
        f'<rect x="{proc.x:.1f}" y="{proc.y:.1f}" width="{proc.w:.1f}" '
        f'height="{proc.h:.1f}" rx="7" fill="{PROC_FILL}" stroke="{PROC_STROKE}" '
        f'stroke-width="1.7"/>')
    out.append(
        f'<rect x="{proc.x:.1f}" y="{proc.y:.1f}" width="{proc.w:.1f}" '
        f'height="{PROC_HEADER}" rx="7" fill="{PROC_STROKE}"/>')
    out.append(
        f'<rect x="{proc.x:.1f}" y="{proc.y+PROC_HEADER-7:.1f}" width="{proc.w:.1f}" '
        f'height="7" fill="{PROC_STROKE}"/>')
    out.append(
        f'<text x="{proc.x+10:.1f}" y="{proc.y+15:.1f}" font-family="{FONT}" '
        f'font-size="11" font-weight="700" fill="#ffffff">{_esc(proc.cls)}</text>')
    out.append(
        f'<text x="{proc.x+10:.1f}" y="{proc.y+27:.1f}" font-family="{FONT}" '
        f'font-size="7.5" fill="#c7d0d8">DRAFT · mechanism unspecified</text>')
    yy = proc.y + PROC_HEADER + 6
    for port in ports:
        is_in = port in proc.inputs
        col = WIRE_IN if is_in else WIRE_OUT
        mark = "◂" if is_in else "▸"
        t = proc.ptypes.get(port, "")
        u = _unit(t)
        lbl = f"{port.replace('_',' ')}"
        out.append(
            f'<text x="{proc.x+10:.1f}" y="{yy+11:.1f}" font-family="{FONT}" '
            f'font-size="9" fill="{INK}"><tspan fill="{col}" font-size="8">{mark}</tspan> '
            f'{_esc(lbl)}<tspan fill="{MUTED}" font-size="7.5">'
            f'{("  ("+u+")") if u else ""}</tspan></text>')
        yy += PORT_H


def _curve(x1, y1, x2, y2, color):
    dx = max(30, abs(x2 - x1) * 0.4)
    return (f'<path d="M{x1:.1f},{y1:.1f} C{x1+dx:.1f},{y1:.1f} {x2-dx:.1f},{y2:.1f} '
            f'{x2:.1f},{y2:.1f}" fill="none" stroke="{color}" stroke-width="1.3" '
            f'stroke-dasharray="4 3" opacity="0.85" marker-end="url(#arrow-{("in" if color==WIRE_IN else "out")})"/>')


def render_composite(state: dict, core, title: str = "", subtitle: str = "") -> str:
    stores = _build_stores(state)
    procs = _build_procs(state, core)

    for s in stores:
        _measure(s)

    # place store forest in a vertical stack of roots (they read top→bottom)
    proc_h = {}
    for p in procs:
        nports = len(set(list(p.inputs) + list(p.outputs)))
        p.h = PROC_HEADER + 6 + nports * PORT_H + 6
    rail_h = sum(p.h for p in procs) + PROC_GAP * max(len(procs) - 1, 0)

    store_x = PAD + (PROC_W + RAIL_GAP if procs else 0)
    y = PAD + 34
    max_right = store_x
    for s in stores:
        _place(s, store_x, y)
        y += s.h + PANEL_GAP
        max_right = max(max_right, s.x + s.w)
    stores_h = y - (PAD + 34)

    # place processes centered vertically against the store block
    py = PAD + 34 + max(0, (stores_h - rail_h) / 2)
    for p in procs:
        p.x, p.y = PAD, py
        py += p.h + PROC_GAP

    width = max_right + PAD
    # widen so the title / subtitle never clip
    if title:
        width = max(width, _tw(title, 15) + 2 * PAD)
    if subtitle:
        width = max(width, _tw(subtitle, 10) + 2 * PAD)
    height = max(y, PAD + 34 + rail_h) + PAD

    idx = {}
    _index(stores, idx)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" '
        f'height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'font-family="{FONT}">',
        f'<defs>'
        f'<marker id="arrow-in" markerWidth="7" markerHeight="7" refX="6" refY="3" '
        f'orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="{WIRE_IN}"/></marker>'
        f'<marker id="arrow-out" markerWidth="7" markerHeight="7" refX="6" refY="3" '
        f'orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="{WIRE_OUT}"/></marker>'
        f'</defs>',
        f'<rect x="0" y="0" width="{width:.0f}" height="{height:.0f}" fill="{PAGE_BG}"/>',
    ]
    if title:
        out.append(
            f'<text x="{PAD}" y="{PAD+16}" font-family="{FONT}" font-size="15" '
            f'font-weight="700" fill="{INK}">{_esc(title)}</text>')
    if subtitle:
        out.append(
            f'<text x="{PAD}" y="{PAD+30}" font-family="{FONT}" font-size="10" '
            f'fill="{MUTED}">{_esc(subtitle)}</text>')

    # wires first (under nodes)
    for p in procs:
        cx = p.x + p.w
        for i, (port, path) in enumerate(p.inputs.items()):
            node = _anchor(path, idx)
            if node is None:
                continue
            y1 = p.y + PROC_HEADER + 6 + (list(p.inputs).index(port)) * PORT_H + 8
            out.append(_curve(node.x, node.y + node.h / 2, cx, y1, WIRE_IN))
        outs = [pp for pp in p.outputs if pp not in p.inputs]
        base = len(p.inputs)
        for j, port in enumerate(p.outputs):
            path = p.outputs[port]
            node = _anchor(path, idx)
            if node is None:
                continue
            row = port if port in p.inputs else port
            ridx = (list(p.inputs) + outs).index(port)
            y1 = p.y + PROC_HEADER + 6 + ridx * PORT_H + 8
            out.append(_curve(cx, y1, node.x, node.y + node.h / 2, WIRE_OUT))

    for s in stores:
        _draw_node(s, out)
    for p in procs:
        _draw_proc(p, out)

    out.append("</svg>")
    return "\n".join(out)
