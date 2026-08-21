"""cpm_viz — bake CPM runs into GIFs (cells over their nutrient field(s)) plus
synced Plotly time-series metrics panels, across four studies (flagship
single-cell, colony/N-cell, disintegration, growth-and-division).

The CPM lattice and the diffusing ``fields`` grid are NOT process-bigraph
stores (the lattice lives on the live CPM process instance; the field grid IS
a store but a plain ``map[array]`` that Composite doesn't otherwise surface as
a step-addressable output). So every ``run_*_frames`` function here drives a
manual cadence loop directly against a live :class:`process_bigraph.Composite`,
calling ``comp.run(cadence)`` and, after each tick, reaching into
``comp.state`` for both the live world object and the scalar ``obs`` store to
capture one animation frame + one row of metrics.

Shared viz-style contract (P1-c-1): every renderer in this module is built on
the same small set of primitives instead of each hand-rolling its own
look-and-feel:

* :func:`_footprint_fill` — a translucent filled cell region PLUS a thin
  contour, never contour-only (a bare contour vanishes once a cell fills the
  frame or sits on a saturated field).
* :func:`_delta_field` — a field's signed difference from its t0 snapshot on
  a diverging colormap; the depletion/accumulation IS the biology, and a raw
  abundant/near-uniform field just saturates one flat color.
* :func:`_lineage_colors` — a founder hue + per-generation shade step (using
  the ``generation``/``max_generation`` observables ``growth_division.py``
  emits), so a lineage of 8+ concurrently-live cells stays distinguishable
  instead of recycling a small fixed palette, while siblings still read as
  visually related.
* :func:`_event_label_for_tick` / :func:`_event_vlines` — one shared
  ``events: list[(tick, label)]`` representation, generalizing
  disintegration's old one-off ``released_tick`` marker into "mark event at
  tick T with label L" for both the GIF frame title (when it fires) and the
  metrics panel's time axis (a vertical line + label).
* :func:`_com_marker` / ``_COM_ACCENT`` — one shared center-of-mass accent
  color for single-cell studies (flagship), instead of a different color per
  panel with no semantic meaning. Multi-cell studies (colony,
  growth-division) still color each cell's COM marker by its own identity/
  lineage color, which IS semantically meaningful.
* :func:`_pattern_title` — one shared title scheme: the pattern name (the
  paper's pattern-taxonomy language, e.g. "Cell–environment coupling —
  sense/act loop") plus a single ``t=…``, not a repeated repo/composite slug
  and not a `(t=…)` stamped separately onto every sub-panel.
* Explicit renderer→panel-kind dispatch: every ``run_*_frames`` stamps
  ``metrics["_panel"]`` with its own kind name; :func:`metrics_panel` looks
  that up in ``_METRICS_PANEL_DISPATCH`` instead of sniffing which keys
  happen to be present — a fifth study's metrics shape can't silently
  misroute onto an unrelated panel.

Two independently-guarded optional-dependency paths:

* GIF encoding prefers ``imageio`` (records ``used_encoder = "imageio"``), and
  falls back to Pillow's multi-frame GIF writer if imageio is unavailable
  (``used_encoder = "pillow"``). If neither is importable, a single PNG (of the
  last frame) is written instead and a note explains the degradation.
* The metrics panel prefers Plotly (interactive HTML); if plotly is unavailable
  a tiny static HTML table is written instead so the pipeline never hard-fails
  on a missing optional dependency.
"""
from __future__ import annotations

import colorsys
from pathlib import Path
from typing import Any

import numpy as np


# --------------------------------------------------------------------------
# Shared viz-style contract (P1-c-1)
# --------------------------------------------------------------------------

def _footprint_fill(ax, mask: np.ndarray, color, *, fill_alpha: float = 0.5,
                     lw: float = 1.6, contour_color=None) -> None:
    """Shared footprint-drawing primitive for every renderer in this module:
    a translucent filled region in ``color`` at ``fill_alpha`` (~0.5) PLUS a
    thin contour on top — not contour-only, which vanishes once a cell's
    footprint fills most of the frame or sits on a saturated field (a bare
    contour is invisible against a same-toned background either way). No-op
    on an empty mask.
    """
    if mask is None or not np.any(mask):
        return
    from matplotlib.colors import to_rgb
    r, g, b = to_rgb(color)
    rgba = np.zeros((*mask.shape, 4))
    rgba[mask] = (r, g, b, fill_alpha)
    ax.imshow(rgba, origin="lower")
    ax.contour(mask, levels=[0.5], colors=[contour_color or color], linewidths=lw)


def _delta_field(ax, fig, current: np.ndarray, initial: np.ndarray, vabs: float,
                  title: str, *, cmap: str = "RdBu_r", cbar_label: str | None = None):
    """Shared Δ-from-t0 field panel: the signed difference from the field's
    t0 snapshot on a diverging colormap centered at 0 (``RdBu_r``, not plain
    ``RdBu`` — matplotlib's ``RdBu`` maps negative→red, the opposite of the
    depletion/accumulation reading wanted here: negative = net consumed =
    blue, positive = net resupplied/produced = red). A raw field that's
    abundant or near-uniform saturates one flat color and goes visually
    dead; the delta IS where the biology (depletion, accumulation) becomes
    legible. ``vabs`` should be fixed by the caller across the whole run so
    color doesn't rescale frame-to-frame. Draws the image, title, and
    colorbar directly on ``ax``/``fig`` and returns the image handle.
    """
    delta = current - initial
    im = ax.imshow(delta, origin="lower", cmap=cmap, vmin=-vabs, vmax=vabs)
    ax.set_title(title, fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label=cbar_label)
    return im


_COM_ACCENT = "#ff2fb0"  # single shared COM-marker accent (single-cell studies)


def _com_marker(ax, com, *, color=_COM_ACCENT, markersize: float = 7) -> None:
    """Shared center-of-mass marker. Single-cell studies (flagship) pass no
    ``color`` and get the one shared ``_COM_ACCENT`` across every panel
    (replacing the old per-panel crimson/black/deepskyblue, which varied for
    no semantic reason). Multi-cell studies (colony, growth-division) pass
    the cell's own identity/lineage color, which IS meaningful."""
    if com is None:
        return
    ax.plot(com[0], com[1], marker="o", markersize=markersize, markerfacecolor="none",
            markeredgecolor=color, markeredgewidth=2.0)


def _pattern_title(fig, pattern_name: str, t: float, *, event_label: str | None = None) -> None:
    """Shared title scheme for every renderer: the pattern name (matching the
    paper's pattern-taxonomy language, e.g. "Cell–environment coupling —
    sense/act loop") plus ONE shared ``t=…`` — replacing each renderer's
    previous ad hoc suptitle (which repeated the repo/composite slug, e.g.
    "single-cell-in-a-field: CPM cell over its nutrient field") and each
    sub-panel's own repeated ``(t=…)``. When ``event_label`` is given (an
    event fires on this exact frame — see :func:`_event_label_for_tick`),
    it's appended so the frame is annotated the moment the event happens."""
    text = f"{pattern_name}  —  t={t:.1f}"
    if event_label:
        text += f"   ·   {event_label}"
    fig.suptitle(text, fontsize=11)


_EVENT_COLOR = "#7a1414"


def _event_label_for_tick(events: list[tuple[float, str]], t: float) -> str | None:
    """Return the label of any event in ``events`` (``[(tick, label), ...]``)
    that fires exactly at tick ``t`` (float-tolerant equality), else ``None``.
    Feeds :func:`_pattern_title`'s ``event_label`` so a GIF frame is annotated
    the moment the event happens — generalizes disintegration's old one-off
    ``released_tick`` marker into a reusable "mark event at tick T with label
    L" usable by any renderer."""
    for tick, label in events:
        if tick is not None and abs(float(tick) - float(t)) < 1e-6:
            return label
    return None


def _event_vlines(fig, events: list[tuple[float, str]], times: list[float]) -> None:
    """Metrics-panel counterpart of :func:`_event_label_for_tick`: a dashed
    vertical line + label (in the shared ``_EVENT_COLOR``) at each
    ``(tick, label)`` in ``events`` that falls inside the captured time
    range. Same ``events`` representation as the frame-title marker, so one
    list drives both the GIF annotation and the metrics panel's time axis."""
    if not times:
        return
    lo, hi = min(times), max(times)
    for tick, label in events:
        if tick is None:
            continue
        tick = float(tick)
        if lo <= tick <= hi:
            fig.add_vline(x=tick, line_dash="dash", line_color=_EVENT_COLOR,
                          annotation_text=label, annotation_position="top")


def _lineage_colors(ids: list[int], generation: dict, *, lineage: dict[int, int] | None = None,
                     single_founder: bool = False) -> dict[int, str]:
    """Assign every live cell id a hex color from a founder hue + a
    per-generation shade step (using the ``generation`` observable
    ``growth_division.py`` emits), instead of a small fixed palette that
    recycles once more than ~6 cells are alive at once — illegible for an
    8+-cell lineage, and makes unrelated cells look identical.

    ``lineage`` (child id → parent id) is used to trace each id back to its
    TRUE founder when available. When it isn't (this module has no exposed
    parent map for growth-division — only the ``generation`` scalar per id is
    an observable), ``single_founder=True`` treats every id as descending
    from one shared founder hue (correct here: every study starts from
    exactly one seed cell). ``single_founder=False`` (the colony studies'
    fixed, non-dividing roster, where ids ARE independent founders) instead
    spreads a distinct hue per id.

    Within a hue family, a small deterministic golden-ratio hue jitter per id
    keeps same-generation siblings distinguishable from each other while
    still reading as visually related (shared hue family, generation-matched
    shade); generation steps the shade (lightness/saturation), so a
    lineage's depth is legible directly from color, cycling within a bounded
    band so it never blows out to white/black at high generation counts.
    """
    lineage = lineage or {}

    def _root(cid: int) -> int:
        seen: set[int] = set()
        cur = cid
        while cur in lineage and cur not in seen:
            seen.add(cur)
            cur = lineage[cur]
        return cur

    if lineage:
        roots = sorted({_root(cid) for cid in ids})
    elif single_founder:
        roots = [min(ids)] if ids else []
    else:
        roots = sorted(ids)

    hue_by_root = {r: (i / max(len(roots), 1)) for i, r in enumerate(roots)}

    colors: dict[int, str] = {}
    for cid in ids:
        if lineage:
            root = _root(cid)
        elif single_founder:
            root = roots[0] if roots else cid
        else:
            root = cid
        base_hue = hue_by_root.get(root, 0.52)
        gen = int(generation.get(cid, generation.get(str(cid), 0)) or 0)
        # Deterministic per-id hue jitter (golden-ratio hash, never repeats
        # like a fixed cycling palette) so same-generation siblings stay
        # distinguishable from each other -- wide enough (~110° of the wheel)
        # that 8+ concurrently-live cells actually separate visually, while
        # still centered on the founder hue so the family reads as related.
        # A second, differently-hashed jitter perturbs lightness too, so two
        # siblings that land close in hue still don't look identical.
        jitter = ((cid * 0.6180339887) % 1.0 - 0.5) * 0.30
        hue = (base_hue + jitter) % 1.0
        lightness_jitter = ((cid * 0.7548776662) % 1.0 - 0.5) * 0.10
        step = gen % 6
        lightness = min(max(0.58 - step * 0.07 + lightness_jitter, 0.24), 0.74)
        saturation = min(0.68 + step * 0.05, 0.95)
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        colors[cid] = "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
    return colors


# --------------------------------------------------------------------------
# Flagship (single cell) frame capture
# --------------------------------------------------------------------------

def _render_frame(lattice: np.ndarray, glucose: np.ndarray, acetate: np.ndarray,
                   glucose_initial: np.ndarray, com: list[float] | None, time: float,
                   glc_vmax: float, ace_vmax: float, depletion_vabs: float) -> np.ndarray:
    """Render one matplotlib (Agg) frame: glucose heatmap + cell footprint
    fill (left), glucose depletion (``glucose - glucose_initial``, diverging
    colormap centered at 0, via the shared :func:`_delta_field`) + footprint
    (middle), acetate plume + footprint (right). Returns an (H, W, 3) uint8
    RGB array (the figure canvas buffer).

    ``glc_vmax``/``ace_vmax``/``depletion_vabs`` are fixed across the whole
    run (computed once by the caller from every captured frame) rather than
    per-frame maxima — a per-frame max on the raw glucose panel would rescale
    color on every tick and hide the depletion halo behind the field's own
    left-to-right gradient. The middle panel is the direct fix for that: it
    plots the DIFFERENCE from the initial field on a symmetric diverging
    scale, which is where the niche-construction signal (the cell measurably
    drawing down its own local nutrient) actually becomes legible,
    independent of the raw gradient's much larger dynamic range.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.4), dpi=100)
    ax_glc, ax_dep, ax_ace = axes

    def _footprint_and_com(ax):
        _footprint_fill(ax, lattice > 0, "white", fill_alpha=0.4, contour_color="white")
        _com_marker(ax, com)

    im = ax_glc.imshow(glucose, origin="lower", cmap="viridis", vmin=0.0, vmax=glc_vmax)
    _footprint_and_com(ax_glc)
    ax_glc.set_title("glucose", fontsize=10)
    ax_glc.set_xticks([]); ax_glc.set_yticks([])
    fig.colorbar(im, ax=ax_glc, fraction=0.046, pad=0.04)

    _delta_field(ax_dep, fig, glucose, glucose_initial, depletion_vabs,
                 "glucose depletion  (Δ from t=0)", cbar_label="Δ glucose")
    _footprint_and_com(ax_dep)

    im2 = ax_ace.imshow(acetate, origin="lower", cmap="magma", vmin=0.0, vmax=ace_vmax)
    _footprint_and_com(ax_ace)
    ax_ace.set_title("acetate plume", fontsize=10)
    ax_ace.set_xticks([]); ax_ace.set_yticks([])
    fig.colorbar(im2, ax=ax_ace, fraction=0.046, pad=0.04)

    _pattern_title(fig, "Cell–environment coupling — sense/act loop", time)
    fig.tight_layout(rect=(0, 0, 1, 0.92))

    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    rgb = buf[:, :, :3].copy()
    plt.close(fig)
    return rgb


def run_flagship_frames(composite_state: dict, core, steps: int = 20, cadence: int = 1
                         ) -> tuple[list[np.ndarray], dict[str, list[float]]]:
    """Build a fresh :class:`Composite` from ``composite_state`` and run it in a
    manual cadence loop, capturing one animation frame + one metrics row per tick.

    Returns ``(frames, metrics)``: ``frames`` is a list of (H, W, 3) uint8 RGB
    arrays; ``metrics`` is a dict of equal-length lists (``time``, ``volume``,
    ``local_nutrient``, ``biomass``, ``acetate_secreted``, ...) plus the
    explicit panel-dispatch marker ``metrics["_panel"] = "flagship"`` (see
    :func:`metrics_panel`), one entry per frame, drawn straight from the
    composite's ``obs`` store after each tick.
    """
    from process_bigraph import Composite

    comp = Composite({"state": composite_state}, core=core)

    ny, nx = comp.state["fields"]["glucose"].shape
    n_ticks = max(int(steps) // max(int(cadence), 1), 1)

    # Captured BEFORE the run loop so every frame's depletion panel diffs
    # against the true initial condition, not a moving baseline.
    glucose_initial = np.asarray(comp.state["fields"]["glucose"]).copy()

    metrics: dict[str, list[float]] = {
        "time": [], "volume": [], "local_nutrient": [], "biomass": [], "acetate_secreted": []
    }
    raw: list[tuple[np.ndarray, np.ndarray, np.ndarray, list[float] | None, float]] = []

    for tick in range(n_ticks):
        comp.run(cadence)

        world = comp.state["cell"]["instance"].world
        lattice = np.array(world.snapshot()).reshape(ny, nx)
        glucose = np.asarray(comp.state["fields"]["glucose"]).copy()
        acetate = np.asarray(comp.state["fields"]["acetate"]).copy()
        obs = comp.state["obs"]

        t = float((tick + 1) * cadence)
        com = obs.get("position")

        raw.append((lattice, glucose, acetate, com, t))

        metrics["time"].append(t)
        metrics["volume"].append(float(obs.get("volume", 0.0)))
        metrics["local_nutrient"].append(float(obs.get("local_nutrient", 0.0)))
        metrics["biomass"].append(float(obs.get("biomass", 0.0)))
        metrics["acetate_secreted"].append(float(obs.get("acetate_secreted", 0.0)))

    # Fixed color scales across the whole run (see `_render_frame` docstring) —
    # computed only after every tick has run, so a single pass over `raw`.
    glc_vmax = max((float(g.max()) for _, g, _, _, _ in raw), default=1e-9) or 1e-9
    ace_vmax = max((float(a.max()) for _, _, a, _, _ in raw), default=1e-9) or 1e-9
    depletion_vabs = max(
        (float(np.abs(g - glucose_initial).max()) for _, g, _, _, _ in raw), default=1e-9
    ) or 1e-9

    frames = [_render_frame(lat, g, a, glucose_initial, com, t, glc_vmax, ace_vmax, depletion_vabs)
              for lat, g, a, com, t in raw]

    metrics["_panel"] = "flagship"
    return frames, metrics


# --------------------------------------------------------------------------
# Colony (N-cell) frame capture
# --------------------------------------------------------------------------

# Fallback per-cell-id colors for metrics panels that don't get an explicit
# `metrics["_colors"]` map (see `_lineage_colors`, which drives the GIF frame
# colors and is stored on `metrics["_colors"]` so the panel and the frames
# always agree). Only 2-4 cells are expected per the colony_field.py docstring.
_ID_PALETTE = ["crimson", "deepskyblue", "gold", "limegreen", "orchid", "sandybrown"]


def _render_colony_frame(lattice: np.ndarray, glucose: np.ndarray, acetate: np.ndarray,
                          coms: dict[str, list[float]], roles: dict[int, str], time: float,
                          glc_vmax: float, ace_vmax: float, show_acetate: bool, *,
                          glucose_initial: np.ndarray | None = None,
                          depletion_vabs: float | None = None,
                          pattern_name: str = "Cell–cell coupling",
                          colors: dict[int, str] | None = None) -> np.ndarray:
    """Render one matplotlib (Agg) frame for a colony tick: every live cell's
    translucent footprint fill + contour + COM marker, in a distinct per-id
    color, over either the raw glucose heatmap (cross-feeding regime) or the
    Δ-from-t0 glucose depletion panel (competition regime, when
    ``glucose_initial``/``depletion_vabs`` are given — a raw glucose field in
    a pure-competition run goes uniformly dark as both competitors draw it
    down together, reading as an empty dead field; the delta is where the
    "who's winning" signal actually lives) — and, only when ``show_acetate``
    (cross-feeding regimes), an acetate plume panel with the same per-id
    overlays. Returns an (H, W, 3) uint8 RGB array (the figure canvas
    buffer).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ids = sorted(roles.keys())
    colors = colors or _lineage_colors(ids, {cid: 0 for cid in ids})

    n_panels = 2 if show_acetate else 1
    fig, axes = plt.subplots(1, n_panels, figsize=(6.6 * n_panels, 4.4), dpi=100)
    axes = [axes] if n_panels == 1 else list(axes)

    def _overlay(ax):
        for cid in ids:
            fp = lattice == cid
            _footprint_fill(ax, fp, colors[cid], fill_alpha=0.5, contour_color=colors[cid])
            com = coms.get(str(cid))
            _com_marker(ax, com, color=colors[cid])

    ax_glc = axes[0]
    use_delta = glucose_initial is not None and depletion_vabs is not None
    if use_delta:
        _delta_field(ax_glc, fig, glucose, glucose_initial, depletion_vabs,
                     "glucose depletion (Δ from t=0) + cell footprints", cbar_label="Δ glucose")
    else:
        im = ax_glc.imshow(glucose, origin="lower", cmap="viridis", vmin=0.0, vmax=glc_vmax)
        ax_glc.set_title("glucose + cell footprints", fontsize=10)
        fig.colorbar(im, ax=ax_glc, fraction=0.046, pad=0.04)
    _overlay(ax_glc)
    ax_glc.set_xticks([]); ax_glc.set_yticks([])
    handles = [plt.Line2D([0], [0], color=colors[cid], lw=2, label=f"cell {cid} ({roles[cid]})")
               for cid in ids]
    ax_glc.legend(handles=handles, loc="upper right", fontsize=7, framealpha=0.6)

    if show_acetate:
        ax_ace = axes[1]
        im2 = ax_ace.imshow(acetate, origin="lower", cmap="magma", vmin=0.0, vmax=ace_vmax)
        _overlay(ax_ace)
        ax_ace.set_title("acetate plume + cell footprints", fontsize=10)
        ax_ace.set_xticks([]); ax_ace.set_yticks([])
        fig.colorbar(im2, ax=ax_ace, fraction=0.046, pad=0.04)

    _pattern_title(fig, pattern_name, time)
    fig.tight_layout(rect=(0, 0, 1, 0.92))

    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    rgb = buf[:, :, :3].copy()
    plt.close(fig)
    return rgb


def run_colony_frames(composite_state: dict, core, steps: int = 20, cadence: int = 1
                       ) -> tuple[list[np.ndarray], dict[str, Any]]:
    """Mirror :func:`run_flagship_frames`, but for a colony of N CPM cells
    sharing one field (``CpmColonyField``): builds a fresh :class:`Composite`
    from ``composite_state`` and runs it in a manual cadence loop, capturing
    one animation frame + one metrics row (per cell id) per tick.

    Returns ``(frames, metrics)``: ``frames`` is a list of (H, W, 3) uint8 RGB
    arrays; ``metrics`` is ``{"time": [...], "biomass": {cid: [...]}, "volume":
    {cid: [...]}, "local_glucose": {cid: [...]}, "local_acetate": {cid:
    [...]}}`` — id-string-keyed, every per-cell list sharing the same length as
    ``metrics["time"]`` (and as ``frames``) — plus ``metrics["_colors"]`` (the
    same per-id hex colors used in the frames, id-string-keyed, so a metrics
    panel can match them) and the explicit panel-dispatch marker
    ``metrics["_panel"]`` (see :func:`metrics_panel`).

    The colony process instance is reached generically by scanning
    ``composite_state`` for the process whose ``address`` names
    ``CpmColonyField`` (the colony composites happen to call that store
    "colony", but nothing here hardcodes that key) — mirrors how the flagship
    reaches ``comp.state["cell"]["instance"].world``.

    The regime (and so the panel kind / frame style) is auto-detected from
    the configured cell ``role``s rather than a caller-supplied flag: every
    cell rostered ``"competitor"`` (no consumer/secretor) is a pure
    competition regime — gets the Δ-glucose depletion panel (P1-c-2: the
    raw field goes uniformly dark, the winner reads as an empty dead field)
    and the ``"colony_compete"`` panel kind (adds the biomass-divergence
    trace); anything with a ``"consumer"`` role is cross-feeding — keeps the
    raw glucose + acetate two-panel layout and the generic per-cell panel.
    """
    from process_bigraph import Composite

    proc_key = next(
        k for k, v in composite_state.items()
        if isinstance(v, dict) and v.get("_type") == "process"
        and "CpmColonyField" in v.get("address", "")
    )

    comp = Composite({"state": composite_state}, core=core)

    ny, nx = comp.state["fields"]["glucose"].shape
    n_ticks = max(int(steps) // max(int(cadence), 1), 1)

    cell_cfgs = list(composite_state[proc_key]["config"].get("cells") or [])
    roles: dict[int, str] = {i + 1: cfg.get("role", "competitor") for i, cfg in enumerate(cell_cfgs)}
    expected_ids = sorted(roles.keys())
    # Acetate is only worth its own panel when a "consumer" respires it as its
    # dynamic substrate (cross-feeding regimes) -- a pure competition regime's
    # acetate is a byproduct nobody in the colony is doing anything with.
    show_acetate = any(role == "consumer" for role in roles.values())
    all_competitor = bool(roles) and all(role == "competitor" for role in roles.values())

    if all_competitor:
        pattern_name = "Cell–cell coupling — competitive exclusion"
        panel_kind = "colony_compete"
    elif show_acetate:
        pattern_name = "Cell–cell coupling — cross-feeding"
        panel_kind = "colony"
    else:
        pattern_name = "Cell–cell coupling"
        panel_kind = "colony"

    # Only the competition regime needs a depletion baseline (see docstring).
    glucose_initial = (
        np.asarray(comp.state["fields"]["glucose"]).copy() if all_competitor else None
    )

    metrics: dict[str, Any] = {
        "time": [],
        "biomass": {str(cid): [] for cid in expected_ids},
        "volume": {str(cid): [] for cid in expected_ids},
        "local_glucose": {str(cid): [] for cid in expected_ids},
        "local_acetate": {str(cid): [] for cid in expected_ids},
    }
    raw: list[tuple[np.ndarray, np.ndarray, np.ndarray, dict, float]] = []

    for tick in range(n_ticks):
        comp.run(cadence)

        world = comp.state[proc_key]["instance"].world
        lattice = np.array(world.snapshot()).reshape(ny, nx)
        glucose = np.asarray(comp.state["fields"]["glucose"]).copy()
        acetate = np.asarray(comp.state["fields"]["acetate"]).copy()
        obs = comp.state["obs"]

        t = float((tick + 1) * cadence)
        coms = dict(obs.get("position", {}))

        raw.append((lattice, glucose, acetate, coms, t))
        metrics["time"].append(t)

        for key in ("biomass", "volume", "local_glucose", "local_acetate"):
            obs_map = obs.get(key, {}) or {}
            for cid in expected_ids:
                cidstr = str(cid)
                series = metrics[key][cidstr]
                if cidstr in obs_map:
                    series.append(float(obs_map[cidstr]))
                else:
                    # cell died / dropped off the lattice this tick -- hold the
                    # last known value rather than shortening the series (every
                    # per-cell array must stay the same length as `frames`).
                    series.append(series[-1] if series else 0.0)

    glc_vmax = max((float(g.max()) for _, g, _, _, _ in raw), default=1e-9) or 1e-9
    ace_vmax = max((float(a.max()) for _, _, a, _, _ in raw), default=1e-9) or 1e-9
    depletion_vabs = None
    if all_competitor:
        depletion_vabs = max(
            (float(np.abs(g - glucose_initial).max()) for _, g, _, _, _ in raw), default=1e-9
        ) or 1e-9

    colors = _lineage_colors(expected_ids, {cid: 0 for cid in expected_ids})

    frames = [
        _render_colony_frame(lat, g, a, coms, roles, t, glc_vmax, ace_vmax, show_acetate,
                              glucose_initial=glucose_initial, depletion_vabs=depletion_vabs,
                              pattern_name=pattern_name, colors=colors)
        for lat, g, a, coms, t in raw
    ]

    metrics["_panel"] = panel_kind
    metrics["_colors"] = {str(k): v for k, v in colors.items()}
    return frames, metrics


# --------------------------------------------------------------------------
# Disintegration (single dissolving cell + scattering particles) frame capture
# --------------------------------------------------------------------------

def _render_disintegration_frame(stressor: np.ndarray, footprint: np.ndarray,
                                  particle_px: list[tuple[float, float]], time: float,
                                  stressor_vmax: float, *, event_label: str | None = None
                                  ) -> np.ndarray:
    """Render one matplotlib (Agg) frame: the ``stressor`` field as a heatmap
    background, the CPM cell's footprint drawn via the shared
    :func:`_footprint_fill` (translucent fill + contour — stays legible down
    to a handful of pixels right before full dissolution, unlike a bare
    contour), and every live particle's mapped pixel position overplotted as
    a small scattering debris marker. Returns an (H, W, 3) uint8 RGB array
    (the figure canvas buffer). ``event_label`` (from
    :func:`_event_label_for_tick`) is stamped into the shared title the
    moment the cell's release fires.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1, figsize=(6.4, 5.6), dpi=100)

    im = ax.imshow(stressor, origin="lower", cmap="inferno", vmin=0.0, vmax=stressor_vmax)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="stressor")

    _footprint_fill(ax, footprint, "deepskyblue", fill_alpha=0.5, contour_color="white")

    if particle_px:
        cols, rows = zip(*particle_px)
        ax.scatter(cols, rows, s=14, c="white", alpha=0.65, edgecolors="black",
                   linewidths=0.3, zorder=5)

    ax.set_xticks([]); ax.set_yticks([])
    _pattern_title(fig, "Cell viability — disintegration under stress", time, event_label=event_label)
    fig.tight_layout(rect=(0, 0, 1, 0.92))

    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    rgb = buf[:, :, :3].copy()
    plt.close(fig)
    return rgb


def run_disintegration_frames(composite_state: dict, core, steps: int = 20, cadence: int = 1
                               ) -> tuple[list[np.ndarray], dict[str, list[float]]]:
    """Mirror :func:`run_flagship_frames`, but for the disintegration study
    (``CpmDisintegration``): builds a fresh :class:`Composite` from
    ``composite_state`` and runs it in a manual cadence loop, capturing one
    animation frame + one metrics row per tick.

    Reaches the live CPM world via the process instance whose ``address``
    names ``CpmDisintegration`` (found generically, like ``run_colony_frames``
    does for ``CpmColonyField``, rather than hardcoding the ``"cell"`` store
    key) for the lattice snapshot, AND the shared ``particles`` map store
    (grown incrementally by that process and moved by a separate
    ``BrownianMovement`` step) for the scattering debris cloud.

    Particle ``position`` (x, y) is mapped to a pixel (col, row) with the
    SAME convention the process uses in reverse: the process places a shed
    particle's pixel center at ``x = (col + 0.5) * bounds_x / nx`` (and same
    for y/row), so the forward pixel mapping used here for plotting is
    ``col = x / bounds_x * nx``, ``row = y / bounds_y * ny``.

    Returns ``(frames, metrics)``: ``frames`` is a list of (H, W, 3) uint8 RGB
    arrays; ``metrics`` is a dict of equal-length lists -- ``time``, ``area``,
    ``mean_stressor``, ``n_particles``, ``n_components``, ``released_tick``
    -- plus the explicit panel-dispatch marker ``metrics["_panel"]`` (see
    :func:`metrics_panel`), one entry per frame, drawn from the composite's
    ``obs`` store and the ``particles`` store after each tick. The single
    ``released_tick`` event (once the cell's release fires) is marked both on
    the GIF frame it fires on and on the metrics panel's time axis, via the
    shared ``events`` convention (:func:`_event_label_for_tick` /
    :func:`_event_vlines`).
    """
    from process_bigraph import Composite

    proc_key = next(
        k for k, v in composite_state.items()
        if isinstance(v, dict) and v.get("_type") == "process"
        and "CpmDisintegration" in v.get("address", "")
    )

    comp = Composite({"state": composite_state}, core=core)

    ny, nx = comp.state["fields"]["stressor"].shape
    bounds = dict(composite_state[proc_key]["config"].get("bounds") or {})
    bx = float(bounds.get("x", nx))
    by = float(bounds.get("y", ny))
    n_ticks = max(int(steps) // max(int(cadence), 1), 1)

    metrics: dict[str, list[float]] = {
        "time": [], "area": [], "mean_stressor": [], "n_particles": [],
        "n_components": [], "released_tick": [],
    }
    raw: list[tuple[np.ndarray, np.ndarray, list[tuple[float, float]], float]] = []

    for tick in range(n_ticks):
        comp.run(cadence)

        world = comp.state[proc_key]["instance"].world
        lattice = np.array(world.snapshot()).reshape(ny, nx)
        footprint = lattice > 0
        stressor = np.asarray(comp.state["fields"]["stressor"]).copy()
        obs = comp.state["obs"]
        particles = comp.state.get("particles", {}) or {}

        particle_px = []
        for p in particles.values():
            pos = p.get("position") if isinstance(p, dict) else None
            if pos is None:
                continue
            x, y = float(pos[0]), float(pos[1])
            particle_px.append((x / bx * nx, y / by * ny))

        t = float((tick + 1) * cadence)
        raw.append((stressor, footprint, particle_px, t))

        metrics["time"].append(t)
        metrics["area"].append(float(obs.get("area", 0.0)))
        metrics["mean_stressor"].append(float(obs.get("mean_stressor", 0.0)))
        metrics["n_particles"].append(float(len(particles)))
        metrics["n_components"].append(float(obs.get("n_components", 0.0)))
        metrics["released_tick"].append(float(obs.get("released_tick", 0.0)))

    stressor_vmax = max((float(s.max()) for s, _, _, _ in raw), default=1e-9) or 1e-9

    released_ticks = metrics["released_tick"]
    events: list[tuple[float, str]] = []
    if released_ticks and released_ticks[-1] > 0:
        events.append((released_ticks[-1], "released"))

    frames = [
        _render_disintegration_frame(s, fp, ppx, t, stressor_vmax,
                                      event_label=_event_label_for_tick(events, t))
        for s, fp, ppx, t in raw
    ]

    metrics["_panel"] = "disintegration"
    return frames, metrics


# --------------------------------------------------------------------------
# Growth-and-division (single lineage compounding via `divide_cells`) frame
# capture
# --------------------------------------------------------------------------

def _render_growth_division_frame(lattice: np.ndarray, glucose: np.ndarray,
                                   glucose_initial: np.ndarray, coms: dict[str, list[float]],
                                   generation: dict[int, int], colors: dict[int, str],
                                   time: float, depletion_vabs: float, pattern_name: str, *,
                                   event_label: str | None = None) -> np.ndarray:
    """Render one matplotlib (Agg) frame for a growth-division tick: the
    glucose Δ-from-t0 depletion panel (P1-c-2 fix — the field starts abundant
    and near-uniform, so the raw heatmap renders as flat saturated yellow
    with invisible contours; the delta is where growth-driven consumption
    actually shows) with every live cell's translucent footprint fill +
    contour + COM marker, colored by lineage/generation (founder hue + shade
    step, via :func:`_lineage_colors` — NOT a small palette that recycles
    once the population passes ~6 cells). Returns an (H, W, 3) uint8 RGB
    array (the figure canvas buffer). ``event_label`` (from
    :func:`_event_label_for_tick`) stamps the shared title the moment a
    division fires.

    Unlike the colony's ``_render_colony_frame`` (whose cell ids are fixed
    from the start), growth-division ids are created dynamically by
    ``world.divide_cells`` as the run proceeds (a parent keeps its id, a
    fresh daughter id is minted) -- so ``colors``/``generation`` are computed
    ONCE by the caller over every id that ever appears across the whole run
    (see ``run_growth_division_frames``), keeping a given lineage's color
    stable across every frame regardless of which tick first introduces it.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1, figsize=(6.6, 5.6), dpi=100)

    _delta_field(ax, fig, glucose, glucose_initial, depletion_vabs,
                 "glucose depletion (Δ from t=0)", cbar_label="Δ glucose")

    ids = sorted(int(i) for i in np.unique(lattice) if i != 0)
    for cid in ids:
        fp = lattice == cid
        if not fp.any():
            continue
        color = colors.get(cid, "#888888")
        _footprint_fill(ax, fp, color, fill_alpha=0.5, contour_color=color)
        com = coms.get(str(cid))
        _com_marker(ax, com, color=color, markersize=6)

    handles = [
        plt.Line2D([0], [0], color=colors.get(cid, "#888888"), lw=2,
                   label=f"cell {cid} (gen {generation.get(cid, 0)})")
        for cid in ids
    ]
    if handles:
        ax.legend(handles=handles, loc="upper right", fontsize=6.5, framealpha=0.6,
                  ncol=2 if len(handles) > 6 else 1)

    ax.set_xticks([]); ax.set_yticks([])
    _pattern_title(fig, pattern_name, time, event_label=event_label)
    fig.tight_layout(rect=(0, 0, 1, 0.92))

    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    rgb = buf[:, :, :3].copy()
    plt.close(fig)
    return rgb


def run_growth_division_frames(composite_state: dict, core, steps: int = 20, cadence: int = 1
                                ) -> tuple[list[np.ndarray], dict[str, Any]]:
    """Mirror :func:`run_colony_frames`, but for the growth-and-division
    lineage study (``CpmGrowthDivision``): builds a fresh :class:`Composite`
    from ``composite_state`` and runs it in a manual cadence loop, capturing
    one animation frame + one metrics row per tick.

    Reaches the live CPM world via the process instance whose ``address``
    names ``CpmGrowthDivision`` (found generically, like ``run_colony_frames``
    does for ``CpmColonyField``, rather than hardcoding the ``"cell"`` store
    key).

    Returns ``(frames, metrics)``: ``frames`` is a list of (H, W, 3) uint8 RGB
    arrays; ``metrics`` is ``{"time": [...], "n_cells": [...], "total_volume":
    [...], "volume": {cell_id: [...]}, "division_events": [(tick, label),
    ...], "_colors": {cell_id: hex}}`` -- the first three are flat,
    equal-length lists (one entry per frame, like the flagship/disintegration
    shape) so ``metrics_panel`` can plot the population staircase directly,
    plus the explicit panel-dispatch marker ``metrics["_panel"]`` (see
    :func:`metrics_panel`). ``volume`` is a BONUS per-cell map (like the
    colony's per-cell metrics) but, unlike the colony's fixed-roster cells,
    growth-division cells are born mid-run by division -- so each per-cell
    series is front-padded with ``None`` for every tick before that id
    existed (rather than back-filled with 0.0/held-last-value, which would
    misleadingly plot a nonexistent cell at zero volume). Every ``volume``
    series is kept the same length as ``metrics["time"]``/``frames`` so a
    caller can zip them directly; Plotly renders a leading gap for the
    ``None``s. ``division_events`` marks every tick where ``n_cells``
    increased (a division fired), via the shared ``events`` convention used
    by both the GIF frame titles and the metrics panel's time axis.
    """
    from process_bigraph import Composite

    proc_key = next(
        k for k, v in composite_state.items()
        if isinstance(v, dict) and v.get("_type") == "process"
        and "CpmGrowthDivision" in v.get("address", "")
    )

    comp = Composite({"state": composite_state}, core=core)

    ny, nx = comp.state["fields"]["glucose"].shape
    n_ticks = max(int(steps) // max(int(cadence), 1), 1)

    glucose_initial = np.asarray(comp.state["fields"]["glucose"]).copy()

    metrics: dict[str, Any] = {"time": [], "n_cells": [], "total_volume": [], "volume": {}}
    raw: list[tuple[np.ndarray, np.ndarray, dict, float]] = []
    generation_all: dict[int, int] = {}

    for tick in range(n_ticks):
        comp.run(cadence)

        world = comp.state[proc_key]["instance"].world
        lattice = np.array(world.snapshot()).reshape(ny, nx)
        glucose = np.asarray(comp.state["fields"]["glucose"]).copy()
        obs = comp.state["obs"]

        t = float((tick + 1) * cadence)
        coms = dict(obs.get("position", {}) or {})
        vol_map = dict(obs.get("volume", {}) or {})
        gen_map = dict(obs.get("generation", {}) or {})
        for cidstr, g in gen_map.items():
            generation_all[int(cidstr)] = int(g)

        raw.append((lattice, glucose, coms, t))

        metrics["time"].append(t)
        metrics["n_cells"].append(float(obs.get("n_cells", 0.0)))
        metrics["total_volume"].append(float(obs.get("total_volume", 0.0)))

        n_so_far = len(metrics["time"])
        for cidstr, v in vol_map.items():
            series = metrics["volume"].get(cidstr)
            if series is None:
                series = [None] * (n_so_far - 1)  # not-yet-born padding
                metrics["volume"][cidstr] = series
            series.append(float(v))
        for cidstr, series in metrics["volume"].items():
            if len(series) < n_so_far:
                series.append(None)  # dropped off the lattice this tick (shouldn't normally happen)

    depletion_vabs = max(
        (float(np.abs(g - glucose_initial).max()) for _, g, _, _ in raw), default=1e-9
    ) or 1e-9

    # Colors/generation computed ONCE over every id that ever appeared (union
    # across the whole run) -- see `_render_growth_division_frame` docstring
    # for why per-tick recomputation would risk unstable colors.
    colors = _lineage_colors(sorted(generation_all), generation_all, single_founder=True)

    # A division event: any tick where n_cells increased over the previous
    # captured tick -- generalizes disintegration's single `released_tick`
    # marker into a reusable multi-event list via the shared `events`
    # convention (see `_event_label_for_tick` / `_event_vlines`).
    events: list[tuple[float, str]] = []
    prev_n: float | None = None
    for t, n in zip(metrics["time"], metrics["n_cells"]):
        if prev_n is not None and n > prev_n:
            events.append((t, f"division → {int(n)} cells"))
        prev_n = n

    frames = [
        _render_growth_division_frame(
            lat, g, glucose_initial, coms, generation_all, colors, t, depletion_vabs,
            "Growth & division — a lineage compounds",
            event_label=_event_label_for_tick(events, t),
        )
        for lat, g, coms, t in raw
    ]

    metrics["_panel"] = "growth_division"
    metrics["_colors"] = {str(k): v for k, v in colors.items()}
    metrics["division_events"] = events
    return frames, metrics


# --------------------------------------------------------------------------
# Sorting (differential-adhesion, two-type checkerboard demixing) frame
# capture
# --------------------------------------------------------------------------

# Two fixed, visually distinct type colors -- shared across every sorting
# frame/legend so "type 1" and "type 2" read as the same color throughout the
# whole GIF (there's no field/lineage to derive a palette from here, unlike
# `_lineage_colors`, since CpmSorting's two types are a fixed, non-dividing
# roster known up front).
_SORTING_TYPE_COLORS: dict[int, str] = {1: "#d1495b", 2: "#2f6f9f"}
_SORTING_MEDIUM_BG = "#eef2f0"


def _render_sorting_frame(lattice: np.ndarray, type_lattice: np.ndarray, time: float,
                           colors: dict[int, str]) -> np.ndarray:
    """Render one matplotlib (Agg) frame for a sorting tick: every live pixel
    colored by its cell's TYPE (not by cell id -- the demixing signal IS the
    two type populations separating, individual cell identity within a type
    isn't the point) via the shared :func:`_footprint_fill` (translucent
    fill + contour, layered per type over a flat medium-colored background --
    there's no diffusing field here, so unlike every other renderer in this
    module there's no heatmap to draw underneath). Returns an (H, W, 3) uint8
    RGB array (the figure canvas buffer).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgb

    ny, nx = lattice.shape
    fig, ax = plt.subplots(1, 1, figsize=(6.2, 6.2), dpi=100)

    bg = np.ones((ny, nx, 4))
    bg[..., :3] = to_rgb(_SORTING_MEDIUM_BG)
    ax.imshow(bg, origin="lower")

    for t, color in colors.items():
        _footprint_fill(ax, type_lattice == t, color, fill_alpha=0.55, contour_color=color)

    handles = [plt.Line2D([0], [0], color=color, lw=2, label=f"type {t}")
               for t, color in colors.items()]
    ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.6)

    ax.set_xticks([]); ax.set_yticks([])
    _pattern_title(fig, "Biomolecular complementarity — differential-adhesion sorting", time)
    fig.tight_layout(rect=(0, 0, 1, 0.92))

    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    rgb = buf[:, :, :3].copy()
    plt.close(fig)
    return rgb


def run_sorting_frames(composite_state: dict, core, steps: int = 60, cadence: int = 5
                        ) -> tuple[list[np.ndarray], dict[str, list[float]]]:
    """Mirror :func:`run_flagship_frames`, but for the sorting study
    (``CpmSorting``): builds a fresh :class:`Composite` from
    ``composite_state`` and runs it in a manual cadence loop, capturing one
    animation frame + one metrics row per tick.

    Reaches the live CPM world via the process instance whose ``address``
    names ``CpmSorting`` (found generically, like ``run_colony_frames`` does
    for ``CpmColonyField``, rather than hardcoding the ``"cell"`` store key)
    for the lattice snapshot. There is no ``fields`` store for this study (no
    field input/output at all -- see ``sorting.py``'s module docstring), so
    the grid shape comes from the process config instead of a field array's
    ``.shape``.

    Returns ``(frames, metrics)``: ``frames`` is a list of (H, W, 3) uint8 RGB
    arrays; ``metrics`` is ``{"time": [...], "hetero_frac": [...],
    "cell_pixels": [...]}`` -- flat, equal-length lists (one entry per frame,
    like the flagship/disintegration shape), drawn straight from the
    composite's ``obs`` store after each tick, plus the explicit
    panel-dispatch marker ``metrics["_panel"] = "sorting"`` (see
    :func:`metrics_panel`).
    """
    from process_bigraph import Composite

    proc_key = next(
        k for k, v in composite_state.items()
        if isinstance(v, dict) and v.get("_type") == "process"
        and "CpmSorting" in v.get("address", "")
    )

    comp = Composite({"state": composite_state}, core=core)

    grid = dict(composite_state[proc_key]["config"].get("grid") or {})
    nx, ny = int(grid.get("nx", 70)), int(grid.get("ny", 70))
    n_ticks = max(int(steps) // max(int(cadence), 1), 1)

    metrics: dict[str, list[float]] = {"time": [], "hetero_frac": [], "cell_pixels": []}
    raw: list[tuple[np.ndarray, np.ndarray, float]] = []

    for tick in range(n_ticks):
        comp.run(cadence)

        world = comp.state[proc_key]["instance"].world
        lattice = np.array(world.snapshot()).reshape(ny, nx)
        obs = comp.state["obs"]

        # Per-pixel type, derived from the lattice + the process's per-cell
        # `type` observable (id -> type) -- never cached, re-derived every
        # tick like every other renderer's live-id handling in this module.
        type_map = {int(k): float(v) for k, v in (obs.get("type") or {}).items()}
        type_lattice = np.zeros_like(lattice, dtype=float)
        for cid, t in type_map.items():
            type_lattice[lattice == cid] = t

        t = float((tick + 1) * cadence)
        raw.append((lattice, type_lattice, t))

        metrics["time"].append(t)
        metrics["hetero_frac"].append(float(obs.get("hetero_frac", 0.0)))
        metrics["cell_pixels"].append(float(obs.get("cell_pixels", 0.0)))

    frames = [_render_sorting_frame(lat, tl, t, _SORTING_TYPE_COLORS) for lat, tl, t in raw]

    metrics["_panel"] = "sorting"
    return frames, metrics


# --------------------------------------------------------------------------
# Cahn-Hilliard (condensate phase separation) frame capture
# --------------------------------------------------------------------------

def _render_cahn_hilliard_frame(phi: np.ndarray, time: float) -> np.ndarray:
    """Render one matplotlib (Agg) frame for a Cahn-Hilliard tick: ``phi`` as
    a diverging heatmap fixed at the physical +/-1 coexistence bounds (not a
    per-frame min/max -- color must stay comparable frame-to-frame as domains
    grow from the near-flat, near-zero starting noise toward the +1/-1
    coexistence values, the same fixed-scale reasoning as every other
    renderer's ``*_vmax``/``vabs``). Returns an (H, W, 3) uint8 RGB array
    (the figure canvas buffer).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1, figsize=(6.2, 5.6), dpi=100)

    im = ax.imshow(phi, origin="lower", cmap="RdBu", vmin=-1.0, vmax=1.0)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="phi")

    ax.set_xticks([]); ax.set_yticks([])
    _pattern_title(fig, "Biomolecular complementarity — Cahn–Hilliard condensation", time)
    fig.tight_layout(rect=(0, 0, 1, 0.92))

    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())
    rgb = buf[:, :, :3].copy()
    plt.close(fig)
    return rgb


def run_cahn_hilliard_frames(composite_state: dict, core, steps: int = 35, cadence: int = 5
                              ) -> tuple[list[np.ndarray], dict[str, list[float]]]:
    """Mirror :func:`run_flagship_frames`, but for the condensate study
    (``CahnHilliard``): builds a fresh :class:`Composite` from
    ``composite_state`` and runs it in a manual cadence loop, capturing one
    animation frame + one metrics row per tick.

    Unlike every CPM-lattice renderer in this module, there is no world-
    owning process instance to reach into -- ``phi`` IS a genuine
    process-bigraph ``fields`` store (see ``cahn_hilliard.py``'s module
    docstring), so it's read straight off ``comp.state["fields"]["phi"]``
    after each tick, same as the flagship/colony/growth-division renderers
    read ``glucose``/``acetate``.

    Returns ``(frames, metrics)``: ``frames`` is a list of (H, W, 3) uint8 RGB
    arrays; ``metrics`` is ``{"time": [...], "phi_var": [...]}`` -- flat,
    equal-length lists (one entry per frame), drawn straight from the
    composite's ``obs`` store after each tick, plus the explicit
    panel-dispatch marker ``metrics["_panel"] = "cahn_hilliard"`` (see
    :func:`metrics_panel`).
    """
    from process_bigraph import Composite

    comp = Composite({"state": composite_state}, core=core)
    n_ticks = max(int(steps) // max(int(cadence), 1), 1)

    metrics: dict[str, list[float]] = {"time": [], "phi_var": []}
    raw: list[tuple[np.ndarray, float]] = []

    for tick in range(n_ticks):
        comp.run(cadence)

        phi = np.asarray(comp.state["fields"]["phi"]).copy()
        obs = comp.state["obs"]

        t = float((tick + 1) * cadence)
        raw.append((phi, t))

        metrics["time"].append(t)
        metrics["phi_var"].append(float(obs.get("phi_var", 0.0)))

    frames = [_render_cahn_hilliard_frame(phi, t) for phi, t in raw]

    metrics["_panel"] = "cahn_hilliard"
    return frames, metrics


# --------------------------------------------------------------------------
# GIF encoding
# --------------------------------------------------------------------------

def frames_to_gif(frames: list[np.ndarray], out_path: str | Path, fps: int = 6) -> str:
    """Write ``frames`` (RGB uint8 arrays) to an animated GIF at ``out_path``.

    Prefers ``imageio`` (records/returns ``"imageio"``); falls back to Pillow's
    multi-frame GIF writer (``"pillow"``) if imageio is unavailable. If neither
    optional dependency is importable, writes a single PNG of the last frame
    instead (path adjusted to ``.png``) and returns ``"png-fallback"``.
    """
    out_path = Path(out_path)
    if not frames:
        raise ValueError("frames_to_gif: no frames to encode")

    try:
        import imageio.v2 as imageio
        # imageio's GIF writer deprecated `fps` in favor of `duration` (ms per
        # frame); pass duration so we don't warn on current imageio while still
        # honoring the fps the caller asked for.
        imageio.mimsave(str(out_path), frames, duration=1000 / max(fps, 1), loop=0)
        return "imageio"
    except ImportError:
        pass

    try:
        from PIL import Image
        duration_ms = int(1000 / max(fps, 1))
        pil_frames = [Image.fromarray(f) for f in frames]
        pil_frames[0].save(
            str(out_path), format="GIF", save_all=True,
            append_images=pil_frames[1:], duration=duration_ms, loop=0,
        )
        return "pillow"
    except ImportError:
        pass

    # Last-resort degradation: neither optional GIF dependency is available.
    png_path = out_path.with_suffix(".png")
    from PIL import Image  # if this also fails there's truly no imaging lib
    Image.fromarray(frames[-1]).save(str(png_path), format="PNG")
    return "png-fallback"


# --------------------------------------------------------------------------
# Metrics panel
# --------------------------------------------------------------------------

_PALETTE = ["#0d6e6b", "#a5620f", "#3f9e99", "#657572", "#c98a3a"]


def metrics_panel(metrics: dict[str, Any], out_path: str | Path,
                   include_plotlyjs: str | bool = "inline") -> str:
    """Write an interactive Plotly time-series panel of ``metrics`` to
    ``out_path`` as HTML.

    Dispatches EXPLICITLY on ``metrics["_panel"]`` — a kind name every
    ``run_*_frames`` in this module stamps onto the metrics dict it returns
    (``"flagship"``, ``"colony"``, ``"colony_compete"``, ``"disintegration"``,
    ``"growth_division"``) — via ``_METRICS_PANEL_DISPATCH``, rather than
    sniffing which keys happen to be present in the dict. The renderer that
    produced the data names its own panel kind; a metrics dict from a future
    fifth study can't silently misroute onto an unrelated panel shape just
    because it happens to share a key name with an existing one. Missing or
    unrecognized ``_panel`` raises immediately instead of guessing.

    Volume (O(10-100)), biomass (O(0.1)), and local_nutrient/acetate_secreted
    (O(1)) live on very different scales, so volume is plotted on a secondary
    right-hand y-axis and everything else shares the primary left-hand axis
    (see each ``_metrics_panel_*`` implementation for its own scale notes).
    Falls back to a small static HTML table if Plotly is unavailable.

    ``include_plotlyjs`` is passed straight through to Plotly's ``fig.to_html``.
    The default ``"inline"`` bakes the full ~4.5 MB Plotly.js library into the
    same ``<script>`` tag as the figure's own ``Plotly.newPlot`` call — fine for
    a throwaway/tmp render, but it defeats the workspace's shared-plotly.js
    convention other studies' baked ``viz/*.html`` follow (a small file with a
    ``<script src="../../../plotly.min.js">`` pointing at the one workspace-root
    copy), which is also what the self-contained investigation-report inliner
    expects (it strips a *separate* library-only ``<script src=…>`` tag, not one
    that also carries ``newPlot``). Pass a relative path to ``plotly.min.js``
    (e.g. ``"../../../plotly.min.js"`` from ``studies/<slug>/viz/``) when baking
    a study's committed artifact so it matches that convention.
    """
    out_path = Path(out_path)
    kind = metrics.get("_panel")
    fn = _METRICS_PANEL_DISPATCH.get(kind)
    if fn is None:
        raise ValueError(
            f"metrics_panel: no panel renderer registered for kind {kind!r} -- "
            f"the run_*_frames call site must stamp metrics['_panel'] to one of "
            f"{sorted(_METRICS_PANEL_DISPATCH)} (explicit dispatch, not key-"
            "sniffing, so a fifth study's metrics shape can't silently misroute)."
        )
    return fn(metrics, out_path, include_plotlyjs)


def _metrics_panel_flat(metrics: dict[str, list[float]], out_path: Path,
                         include_plotlyjs: str | bool) -> str:
    """Flagship counterpart of :func:`metrics_panel`: a flat dict of
    equal-length lists sharing a ``time`` axis, one trace per metric."""
    times = metrics.get("time") or list(range(len(next(iter(metrics.values()), []))))
    series = {k: v for k, v in metrics.items() if k != "time" and not k.startswith("_") and v}

    try:
        import plotly.graph_objects as go
    except ImportError:
        rows = "".join(
            "<tr>" + "".join(f"<td>{v}</td>" for v in vals) + "</tr>"
            for vals in zip(times, *series.values())
        )
        header = "".join(f"<th>{k}</th>" for k in ("time", *series.keys()))
        out_path.write_text(
            f"<html><body><p>Plotly unavailable — static table fallback.</p>"
            f"<table border='1'><tr>{header}</tr>{rows}</table></body></html>"
        )
        return "table-fallback"

    secondary = {"volume"}
    fig = go.Figure()
    for i, (label, ys) in enumerate(series.items()):
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(go.Scatter(
            x=times, y=ys, mode="lines+markers", name=label,
            line=dict(width=2.6, color=color),
            yaxis="y2" if label in secondary else "y",
        ))

    fig.update_layout(
        title=dict(text="<b>single-cell-in-a-field — synced metrics</b>", x=0.01, xanchor="left"),
        xaxis=dict(title="time", gridcolor="rgba(120,130,125,0.16)"),
        yaxis=dict(title="local_nutrient / biomass / acetate_secreted",
                   gridcolor="rgba(120,130,125,0.16)"),
        yaxis2=dict(title="volume", overlaying="y", side="right", showgrid=False),
        template="plotly_white", height=460,
        legend=dict(orientation="h", yanchor="bottom", y=-0.26, xanchor="left", x=0),
        hovermode="x unified", margin=dict(l=56, r=56, t=54, b=54),
    )
    out_path.write_text(fig.to_html(include_plotlyjs=include_plotlyjs, full_html=True,
                                     config={"displayModeBar": False, "responsive": True}))
    return "plotly"


def _metrics_panel_percell(metrics: dict[str, dict[str, list[float]]], out_path: Path,
                            include_plotlyjs: str | bool) -> str:
    """Per-cell counterpart of :func:`metrics_panel` for ``run_colony_frames``'
    cross-feeding-regime output shape (``{metric: {cell_id: [...]}}``). One
    trace per (metric, cell id) pair, colored by cell id — using the SAME
    colors the GIF frames used (``metrics["_colors"]``, falling back to
    ``_ID_PALETTE`` if absent) so a reader can track "cell 2's biomass" as one
    consistent color across the GIF and every metric panel — and
    distinguished by metric via line dash style. ``volume`` again gets its
    own secondary y-axis (same O(10-100) vs O(0.1-1) scale mismatch as the
    flagship). Falls back to a small static HTML table if Plotly is
    unavailable.
    """
    times = metrics.get("time") or []
    metric_keys = [k for k in metrics if k != "time" and not k.startswith("_")
                   and isinstance(metrics[k], dict)]
    cell_ids = sorted({cid for k in metric_keys for cid in metrics[k]}, key=lambda s: (len(s), s))
    stored_colors = metrics.get("_colors") or {}

    try:
        import plotly.graph_objects as go
    except ImportError:
        cols = [(k, cid) for k in metric_keys for cid in cell_ids]
        header = "".join(f"<th>{k} (cell {cid})</th>" for k, cid in cols)
        rows = "".join(
            "<tr><td>" + str(t) + "</td>" + "".join(f"<td>{metrics[k][cid][i]}</td>" for k, cid in cols) + "</tr>"
            for i, t in enumerate(times)
        )
        out_path.write_text(
            f"<html><body><p>Plotly unavailable — static table fallback.</p>"
            f"<table border='1'><tr><th>time</th>{header}</tr>{rows}</table></body></html>"
        )
        return "table-fallback"

    secondary = {"volume"}
    dash_by_metric = {}
    _dashes = ["solid", "dash", "dot", "dashdot"]
    for i, k in enumerate(metric_keys):
        dash_by_metric[k] = _dashes[i % len(_dashes)]
    color_by_cell = {
        cid: stored_colors.get(cid, _ID_PALETTE[i % len(_ID_PALETTE)])
        for i, cid in enumerate(cell_ids)
    }

    fig = go.Figure()
    for k in metric_keys:
        for cid in cell_ids:
            ys = metrics[k].get(cid)
            if not ys:
                continue
            fig.add_trace(go.Scatter(
                x=times, y=ys, mode="lines+markers", name=f"{k} (cell {cid})",
                line=dict(width=2.4, color=color_by_cell[cid], dash=dash_by_metric[k]),
                yaxis="y2" if k in secondary else "y",
            ))

    fig.update_layout(
        title=dict(text="<b>colony — synced per-cell metrics</b>", x=0.01, xanchor="left"),
        xaxis=dict(title="time", gridcolor="rgba(120,130,125,0.16)"),
        yaxis=dict(title="biomass / local_glucose / local_acetate",
                   gridcolor="rgba(120,130,125,0.16)"),
        yaxis2=dict(title="volume", overlaying="y", side="right", showgrid=False),
        template="plotly_white", height=480,
        legend=dict(orientation="h", yanchor="bottom", y=-0.32, xanchor="left", x=0),
        hovermode="x unified", margin=dict(l=56, r=56, t=54, b=64),
    )
    out_path.write_text(fig.to_html(include_plotlyjs=include_plotlyjs, full_html=True,
                                     config={"displayModeBar": False, "responsive": True}))
    return "plotly"


def _metrics_panel_compete(metrics: dict[str, Any], out_path: Path,
                            include_plotlyjs: str | bool) -> str:
    """Competition-regime counterpart of :func:`metrics_panel` for
    ``run_colony_frames``' per-cell output shape, selected via the explicit
    ``metrics["_panel"] == "colony_compete"`` marker (set by the renderer
    when every colony cell is rostered ``"competitor"``). P1-c-2: the
    compete GIF previously had NO metrics panel at all, so the study's
    headline number — the ~3.69x final biomass margin between the two
    competitors — was never plotted anywhere. This panel draws both cells'
    biomass PLUS a bold divergence trace (the faster competitor's biomass
    over the slower one, ratio ≥ 1 and rising as the takeover happens) on its
    own secondary axis, with the final margin in the panel title.
    """
    times = metrics.get("time") or []
    biomass = metrics.get("biomass") or {}
    cell_ids = sorted(biomass, key=lambda s: (len(s), s))
    stored_colors = metrics.get("_colors") or {}

    try:
        import plotly.graph_objects as go
    except ImportError:
        header = "".join(f"<th>biomass (cell {cid})</th>" for cid in cell_ids)
        rows = "".join(
            "<tr><td>" + str(t) + "</td>"
            + "".join(f"<td>{biomass[cid][i]}</td>" for cid in cell_ids) + "</tr>"
            for i, t in enumerate(times)
        )
        out_path.write_text(
            f"<html><body><p>Plotly unavailable — static table fallback.</p>"
            f"<table border='1'><tr><th>time</th>{header}</tr>{rows}</table></body></html>"
        )
        return "table-fallback"

    color_by_cell = {
        cid: stored_colors.get(cid, _PALETTE[i % len(_PALETTE)])
        for i, cid in enumerate(cell_ids)
    }

    fig = go.Figure()
    for cid in cell_ids:
        ys = biomass.get(cid)
        if not ys:
            continue
        fig.add_trace(go.Scatter(x=times, y=ys, mode="lines+markers", name=f"biomass (cell {cid})",
                                  line=dict(width=2.4, color=color_by_cell[cid])))

    divergence: list[float] | None = None
    if len(cell_ids) >= 2:
        a, b = biomass[cell_ids[0]], biomass[cell_ids[1]]
        divergence = [(av / bv) if bv > 1e-9 else float("nan") for av, bv in zip(a, b)]
        fig.add_trace(go.Scatter(
            x=times, y=divergence, mode="lines+markers",
            name=f"biomass divergence (cell {cell_ids[0]} / cell {cell_ids[1]})",
            line=dict(width=3.2, color=_EVENT_COLOR), yaxis="y2",
        ))

    final = f"{divergence[-1]:.2f}x" if divergence and divergence[-1] == divergence[-1] else "n/a"
    fig.update_layout(
        title=dict(text=f"<b>competition — biomass divergence (final margin {final})</b>",
                   x=0.01, xanchor="left"),
        xaxis=dict(title="time", gridcolor="rgba(120,130,125,0.16)"),
        yaxis=dict(title="biomass", gridcolor="rgba(120,130,125,0.16)"),
        yaxis2=dict(title="biomass divergence (ratio)", overlaying="y", side="right", showgrid=False),
        template="plotly_white", height=460,
        legend=dict(orientation="h", yanchor="bottom", y=-0.26, xanchor="left", x=0),
        hovermode="x unified", margin=dict(l=56, r=56, t=54, b=54),
    )
    out_path.write_text(fig.to_html(include_plotlyjs=include_plotlyjs, full_html=True,
                                     config={"displayModeBar": False, "responsive": True}))
    return "plotly"


def _metrics_panel_disintegration(metrics: dict[str, list[float]], out_path: Path,
                                   include_plotlyjs: str | bool) -> str:
    """Disintegration counterpart of :func:`metrics_panel` for
    ``run_disintegration_frames``' output shape (flat equal-length lists, like
    the flagship, but a different set of keys). ``area`` (pixel count,
    O(1-64)) and ``n_particles`` (shed debris count, O(1-70)) share the
    primary left-hand axis -- both are roughly the same "how much cell is
    left vs. how much debris exists" order of magnitude, and plotting them
    together is the whole payoff shot (cell shrinks while the cloud grows).
    ``mean_stressor`` (O(0-1.5), the viability-threshold-crossing signal) gets
    its own secondary right-hand axis so its much smaller range doesn't get
    flattened against the pixel/particle counts. The ``released_tick`` event
    (the tick the process latched release, from the LAST metrics row -- the
    value is constant across the whole run once released) is marked via the
    shared :func:`_event_vlines` (same ``events`` convention the GIF frame
    title uses), when the cell released during the captured run. Falls back
    to a small static HTML table if Plotly is unavailable.
    """
    times = metrics.get("time") or []
    area = metrics.get("area") or []
    mean_stressor = metrics.get("mean_stressor") or []
    n_particles = metrics.get("n_particles") or []
    n_components = metrics.get("n_components") or []
    released_ticks = metrics.get("released_tick") or []
    released_tick = released_ticks[-1] if released_ticks else 0.0

    try:
        import plotly.graph_objects as go
    except ImportError:
        cols = ("time", "area", "mean_stressor", "n_particles", "n_components", "released_tick")
        header = "".join(f"<th>{c}</th>" for c in cols)
        rows = "".join(
            "<tr>" + "".join(f"<td>{v}</td>" for v in vals) + "</tr>"
            for vals in zip(times, area, mean_stressor, n_particles, n_components, released_ticks)
        )
        out_path.write_text(
            f"<html><body><p>Plotly unavailable — static table fallback.</p>"
            f"<table border='1'><tr>{header}</tr>{rows}</table></body></html>"
        )
        return "table-fallback"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=area, mode="lines+markers", name="area",
                              line=dict(width=2.6, color=_PALETTE[0])))
    fig.add_trace(go.Scatter(x=times, y=n_particles, mode="lines+markers", name="n_particles",
                              line=dict(width=2.6, color=_PALETTE[1])))
    if n_components:
        fig.add_trace(go.Scatter(x=times, y=n_components, mode="lines+markers", name="n_components",
                                  line=dict(width=1.8, color=_PALETTE[3], dash="dot")))
    fig.add_trace(go.Scatter(x=times, y=mean_stressor, mode="lines+markers", name="mean_stressor",
                              line=dict(width=2.6, color=_PALETTE[2]), yaxis="y2"))

    fig.update_layout(
        title=dict(text="<b>disintegration — synced metrics</b>", x=0.01, xanchor="left"),
        xaxis=dict(title="time", gridcolor="rgba(120,130,125,0.16)"),
        yaxis=dict(title="area (px) / n_particles / n_components",
                   gridcolor="rgba(120,130,125,0.16)"),
        yaxis2=dict(title="mean_stressor", overlaying="y", side="right", showgrid=False),
        template="plotly_white", height=460,
        legend=dict(orientation="h", yanchor="bottom", y=-0.26, xanchor="left", x=0),
        hovermode="x unified", margin=dict(l=56, r=56, t=54, b=54),
    )
    events: list[tuple[float, str]] = [(released_tick, "released")] if released_tick else []
    _event_vlines(fig, events, times)

    out_path.write_text(fig.to_html(include_plotlyjs=include_plotlyjs, full_html=True,
                                     config={"displayModeBar": False, "responsive": True}))
    return "plotly"


def _metrics_panel_growth_division(metrics: dict[str, Any], out_path: Path,
                                    include_plotlyjs: str | bool) -> str:
    """Growth-division counterpart of :func:`metrics_panel` for
    ``run_growth_division_frames``' output shape: flat ``n_cells``/
    ``total_volume`` lists (like the flagship/disintegration shape) PLUS an
    optional per-cell ``volume`` map (``{cell_id: [...]}``, front-padded with
    ``None`` before a cell was born -- see that function's docstring).

    ``n_cells`` (the 1->2->4->8 staircase, O(1-16)) is drawn as a bold
    step-line (``line_shape="hv"``) on the primary left-hand axis;
    ``total_volume`` (O(10-100s), scaling with the population) and any
    optional per-cell ``volume`` sawtooth traces (same rough order of
    magnitude as ``total_volume``, one thin dotted line per lineage, colored
    with the SAME lineage colors the GIF frames used --
    ``metrics["_colors"]``, falling back to ``_ID_PALETTE`` if absent) share
    a secondary right-hand axis. Every division event (``metrics
    ["division_events"]``, the same ``events`` convention the GIF frame
    titles use) is marked with a dashed vertical line via the shared
    :func:`_event_vlines`. Falls back to a small static HTML table (just the
    three guaranteed flat series) if Plotly is unavailable.
    """
    times = metrics.get("time") or []
    n_cells = metrics.get("n_cells") or []
    total_volume = metrics.get("total_volume") or []
    percell_volume = metrics.get("volume") or {}
    cell_ids = sorted(percell_volume, key=lambda s: (len(s), s)) if isinstance(percell_volume, dict) else []
    stored_colors = metrics.get("_colors") or {}
    division_events = metrics.get("division_events") or []

    try:
        import plotly.graph_objects as go
    except ImportError:
        cols = ("time", "n_cells", "total_volume")
        header = "".join(f"<th>{c}</th>" for c in cols)
        rows = "".join(
            "<tr>" + "".join(f"<td>{v}</td>" for v in vals) + "</tr>"
            for vals in zip(times, n_cells, total_volume)
        )
        out_path.write_text(
            f"<html><body><p>Plotly unavailable — static table fallback.</p>"
            f"<table border='1'><tr>{header}</tr>{rows}</table></body></html>"
        )
        return "table-fallback"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=n_cells, mode="lines+markers", name="n_cells",
                              line=dict(width=3.0, color=_PALETTE[0], shape="hv")))
    fig.add_trace(go.Scatter(x=times, y=total_volume, mode="lines+markers", name="total_volume",
                              line=dict(width=2.2, color=_PALETTE[1]), yaxis="y2"))

    for i, cid in enumerate(cell_ids):
        ys = percell_volume.get(cid)
        if not ys:
            continue
        color = stored_colors.get(cid, _ID_PALETTE[i % len(_ID_PALETTE)])
        fig.add_trace(go.Scatter(x=times, y=ys, mode="lines", name=f"volume (cell {cid})",
                                  line=dict(width=1.3, color=color, dash="dot"),
                                  yaxis="y2", connectgaps=False))

    fig.update_layout(
        title=dict(text="<b>growth &amp; division — synced metrics</b>", x=0.01, xanchor="left"),
        xaxis=dict(title="time", gridcolor="rgba(120,130,125,0.16)"),
        yaxis=dict(title="n_cells", gridcolor="rgba(120,130,125,0.16)"),
        yaxis2=dict(title="volume (total / per-cell)", overlaying="y", side="right", showgrid=False),
        template="plotly_white", height=460,
        legend=dict(orientation="h", yanchor="bottom", y=-0.26, xanchor="left", x=0),
        hovermode="x unified", margin=dict(l=56, r=56, t=54, b=54),
    )
    _event_vlines(fig, division_events, times)

    out_path.write_text(fig.to_html(include_plotlyjs=include_plotlyjs, full_html=True,
                                     config={"displayModeBar": False, "responsive": True}))
    return "plotly"


def _metrics_panel_sorting(metrics: dict[str, list[float]], out_path: Path,
                            include_plotlyjs: str | bool) -> str:
    """Sorting counterpart of :func:`metrics_panel` for
    ``run_sorting_frames``' output shape (flat equal-length lists, like the
    flagship/disintegration shape). ``hetero_frac`` (the demixing curve, the
    study's headline number, collapsing from the checkerboard's well-mixed
    start toward a sorted low value) is drawn on the primary left-hand axis;
    ``cell_pixels`` (the cohesion guard -- a dissolving/fragmenting clump
    must not be misread as "sorted" just because its heterotypic interface
    shrank along with everything else, see ``sorting.py``'s module
    docstring) gets its own secondary right-hand axis since it lives on a
    very different scale (O(100s) pixels vs. ``hetero_frac``'s [0, 1]
    range). Falls back to a small static HTML table if Plotly is
    unavailable.
    """
    times = metrics.get("time") or []
    hetero = metrics.get("hetero_frac") or []
    cohesion = metrics.get("cell_pixels") or []

    try:
        import plotly.graph_objects as go
    except ImportError:
        header = "".join(f"<th>{c}</th>" for c in ("time", "hetero_frac", "cell_pixels"))
        rows = "".join(
            "<tr>" + "".join(f"<td>{v}</td>" for v in vals) + "</tr>"
            for vals in zip(times, hetero, cohesion)
        )
        out_path.write_text(
            f"<html><body><p>Plotly unavailable — static table fallback.</p>"
            f"<table border='1'><tr>{header}</tr>{rows}</table></body></html>"
        )
        return "table-fallback"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=hetero, mode="lines+markers", name="hetero_frac",
                              line=dict(width=2.8, color=_PALETTE[0])))
    fig.add_trace(go.Scatter(x=times, y=cohesion, mode="lines+markers", name="cell_pixels (cohesion)",
                              line=dict(width=2.0, color=_PALETTE[1], dash="dot"), yaxis="y2"))

    fig.update_layout(
        title=dict(text="<b>sorting — demixing + cohesion</b>", x=0.01, xanchor="left"),
        xaxis=dict(title="time", gridcolor="rgba(120,130,125,0.16)"),
        yaxis=dict(title="hetero_frac", gridcolor="rgba(120,130,125,0.16)"),
        yaxis2=dict(title="cell_pixels (cohesion)", overlaying="y", side="right", showgrid=False),
        template="plotly_white", height=460,
        legend=dict(orientation="h", yanchor="bottom", y=-0.26, xanchor="left", x=0),
        hovermode="x unified", margin=dict(l=56, r=56, t=54, b=54),
    )
    out_path.write_text(fig.to_html(include_plotlyjs=include_plotlyjs, full_html=True,
                                     config={"displayModeBar": False, "responsive": True}))
    return "plotly"


def _metrics_panel_cahn_hilliard(metrics: dict[str, list[float]], out_path: Path,
                                  include_plotlyjs: str | bool) -> str:
    """Cahn-Hilliard counterpart of :func:`metrics_panel` for
    ``run_cahn_hilliard_frames``' output shape (flat equal-length lists).
    ``phi_var`` is the study's headline number -- it rises from the
    near-flat starting noise toward the coexistence variance as ``phi``
    separates into +1/-1 domains -- so it's the only trace, on a single
    axis (no secondary-scale metric to share the panel with, unlike every
    other study here). Falls back to a small static HTML table if Plotly is
    unavailable.
    """
    times = metrics.get("time") or []
    phi_var = metrics.get("phi_var") or []

    try:
        import plotly.graph_objects as go
    except ImportError:
        rows = "".join(
            f"<tr><td>{t}</td><td>{v}</td></tr>" for t, v in zip(times, phi_var)
        )
        out_path.write_text(
            f"<html><body><p>Plotly unavailable — static table fallback.</p>"
            f"<table border='1'><tr><th>time</th><th>phi_var</th></tr>{rows}</table></body></html>"
        )
        return "table-fallback"

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=phi_var, mode="lines+markers", name="phi_var",
                              line=dict(width=2.8, color=_PALETTE[0])))

    fig.update_layout(
        title=dict(text="<b>condensate — phase-separation variance</b>", x=0.01, xanchor="left"),
        xaxis=dict(title="time", gridcolor="rgba(120,130,125,0.16)"),
        yaxis=dict(title="phi_var", gridcolor="rgba(120,130,125,0.16)"),
        template="plotly_white", height=460,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="left", x=0),
        hovermode="x unified", margin=dict(l=56, r=56, t=54, b=54),
    )
    out_path.write_text(fig.to_html(include_plotlyjs=include_plotlyjs, full_html=True,
                                     config={"displayModeBar": False, "responsive": True}))
    return "plotly"


# Explicit renderer→panel-kind dispatch table (see `metrics_panel`'s
# docstring): every `run_*_frames` in this module stamps `metrics["_panel"]`
# with its own kind name, looked up here instead of sniffed from which keys
# happen to be present.
_METRICS_PANEL_DISPATCH: dict[str, Any] = {
    "flagship": _metrics_panel_flat,
    "colony": _metrics_panel_percell,
    "colony_compete": _metrics_panel_compete,
    "disintegration": _metrics_panel_disintegration,
    "growth_division": _metrics_panel_growth_division,
    "sorting": _metrics_panel_sorting,
    "cahn_hilliard": _metrics_panel_cahn_hilliard,
}
