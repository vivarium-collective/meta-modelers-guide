"""cpm_viz — bake the flagship CPM run into a GIF (cell over its nutrient field)
plus a synced Plotly time-series metrics panel.

The CPM lattice and the diffusing ``fields`` grid are NOT process-bigraph stores
(the lattice lives on the live ``CpmCellField`` process instance; the field grid
IS a store but a plain ``map[array]`` that Composite doesn't otherwise surface as
a step-addressable output). So this module drives a manual cadence loop directly
against a live :class:`process_bigraph.Composite`, calling ``comp.run(cadence)``
and, after each tick, reaching into ``comp.state`` for both the live world object
and the scalar ``obs`` store to capture one animation frame + one row of metrics.

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

import io
from pathlib import Path
from typing import Any

import numpy as np


# --------------------------------------------------------------------------
# Frame capture
# --------------------------------------------------------------------------

def _render_frame(lattice: np.ndarray, glucose: np.ndarray, acetate: np.ndarray,
                   glucose_initial: np.ndarray, com: list[float] | None, time: float,
                   glc_vmax: float, ace_vmax: float, depletion_vabs: float) -> np.ndarray:
    """Render one matplotlib (Agg) frame: glucose heatmap + cell footprint
    outline + COM marker (left), glucose depletion (``glucose - glucose_initial``,
    diverging colormap centered at 0) + footprint (middle), acetate plume +
    footprint (right). Returns an (H, W, 3) uint8 RGB array (the figure canvas
    buffer).

    ``glc_vmax``/``ace_vmax``/``depletion_vabs`` are fixed across the whole run
    (computed once by the caller from every captured frame) rather than
    per-frame maxima — a per-frame max on the raw glucose panel would rescale
    color on every tick and hide the depletion halo behind the field's own
    left-to-right gradient. The middle panel is the direct fix for that: it
    plots the DIFFERENCE from the initial field on a symmetric diverging scale
    (blue = net consumed, red = net resupplied by diffusion), which is where
    the niche-construction signal (the cell measurably drawing down its own
    local nutrient) actually becomes legible, independent of the raw
    gradient's much larger dynamic range.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.4), dpi=100)
    ax_glc, ax_dep, ax_ace = axes

    def _footprint_and_com(ax, edgecolor):
        ax.contour(lattice > 0, levels=[0.5], colors="white", linewidths=1.6)
        if com is not None:
            ax.plot(com[0], com[1], marker="o", markersize=7,
                    markerfacecolor="none", markeredgecolor=edgecolor, markeredgewidth=2.0)

    im = ax_glc.imshow(glucose, origin="lower", cmap="viridis", vmin=0.0, vmax=glc_vmax)
    _footprint_and_com(ax_glc, "crimson")
    ax_glc.set_title(f"glucose  (t={time:.1f})", fontsize=10)
    ax_glc.set_xticks([]); ax_glc.set_yticks([])
    fig.colorbar(im, ax=ax_glc, fraction=0.046, pad=0.04)

    depletion = glucose - glucose_initial
    # RdBu_r (not plain RdBu): matplotlib's RdBu maps negative->red/positive->blue,
    # the opposite of the reading we want here (negative = net consumed = blue,
    # positive = net resupplied by diffusion = red).
    im_dep = ax_dep.imshow(depletion, origin="lower", cmap="RdBu_r",
                            vmin=-depletion_vabs, vmax=depletion_vabs)
    _footprint_and_com(ax_dep, "black")
    ax_dep.set_title("glucose depletion  (Δ from t=0)", fontsize=10)
    ax_dep.set_xticks([]); ax_dep.set_yticks([])
    fig.colorbar(im_dep, ax=ax_dep, fraction=0.046, pad=0.04)

    im2 = ax_ace.imshow(acetate, origin="lower", cmap="magma", vmin=0.0, vmax=ace_vmax)
    _footprint_and_com(ax_ace, "deepskyblue")
    ax_ace.set_title("acetate plume", fontsize=10)
    ax_ace.set_xticks([]); ax_ace.set_yticks([])
    fig.colorbar(im2, ax=ax_ace, fraction=0.046, pad=0.04)

    fig.suptitle("single-cell-in-a-field: CPM cell over its nutrient field", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))

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
    ``local_nutrient``, ``biomass``, ``acetate_secreted``, ...), one entry per
    frame, drawn straight from the composite's ``obs`` store after each tick.
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

    return frames, metrics


# --------------------------------------------------------------------------
# Colony (N-cell) frame capture
# --------------------------------------------------------------------------

# Distinct per-cell-id colors (cycled if there are ever more cells than colors;
# only 2-4 cells are expected per the colony_field.py docstring).
_ID_PALETTE = ["crimson", "deepskyblue", "gold", "limegreen", "orchid", "sandybrown"]


def _render_colony_frame(lattice: np.ndarray, glucose: np.ndarray, acetate: np.ndarray,
                          coms: dict[str, list[float]], roles: dict[int, str], time: float,
                          glc_vmax: float, ace_vmax: float, show_acetate: bool) -> np.ndarray:
    """Render one matplotlib (Agg) frame for a colony tick: glucose heatmap with
    every live cell's footprint outlined + COM-marked in a distinct per-id color
    (left), and — only when ``show_acetate`` (cross-feeding regimes) — an
    acetate plume panel with the same per-id overlays (right). Returns an
    (H, W, 3) uint8 RGB array (the figure canvas buffer).

    Unlike the flagship's single-cell ``_render_frame`` (which needs a
    depletion-vs-initial panel to make niche construction legible), a colony
    frame's interesting signal IS the cell-id partition of the lattice itself —
    so here the per-cell contour overlay carries that instead of a middle
    depletion panel.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ids = sorted(roles.keys())
    colors = {cid: _ID_PALETTE[i % len(_ID_PALETTE)] for i, cid in enumerate(ids)}

    n_panels = 2 if show_acetate else 1
    fig, axes = plt.subplots(1, n_panels, figsize=(6.6 * n_panels, 4.4), dpi=100)
    axes = [axes] if n_panels == 1 else list(axes)

    def _overlay(ax):
        for cid in ids:
            fp = lattice == cid
            if fp.any():
                ax.contour(fp, levels=[0.5], colors=[colors[cid]], linewidths=1.8)
            com = coms.get(str(cid))
            if com:
                ax.plot(com[0], com[1], marker="o", markersize=7, markerfacecolor="none",
                        markeredgecolor=colors[cid], markeredgewidth=2.0)

    ax_glc = axes[0]
    im = ax_glc.imshow(glucose, origin="lower", cmap="viridis", vmin=0.0, vmax=glc_vmax)
    _overlay(ax_glc)
    ax_glc.set_title(f"glucose + cell footprints  (t={time:.1f})", fontsize=10)
    ax_glc.set_xticks([]); ax_glc.set_yticks([])
    fig.colorbar(im, ax=ax_glc, fraction=0.046, pad=0.04)
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

    fig.suptitle("colony: CPM cells over shared nutrient field(s)", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))

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
    ``metrics["time"]`` (and as ``frames``).

    The colony process instance is reached generically by scanning
    ``composite_state`` for the process whose ``address`` names
    ``CpmColonyField`` (the colony composites happen to call that store
    "colony", but nothing here hardcodes that key) — mirrors how the flagship
    reaches ``comp.state["cell"]["instance"].world``.
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

    frames = [
        _render_colony_frame(lat, g, a, coms, roles, t, glc_vmax, ace_vmax, show_acetate)
        for lat, g, a, coms, t in raw
    ]

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

    Accepts either shape metrics comes in across this module's two frame
    capturers, branching on it automatically so existing (flagship)
    call sites are unaffected:

    * flat (``run_flagship_frames``): a dict of equal-length lists sharing a
      ``time`` axis, one trace per metric — handled below.
    * per-cell (``run_colony_frames``): a dict of ``{metric: {cell_id:
      [...]}}`` id-string-keyed maps sharing a ``time`` axis, one trace per
      (metric, cell id) pair — delegated to ``_metrics_panel_percell``.

    Volume (O(10-100)), biomass (O(0.1)), and local_nutrient/acetate_secreted
    (O(1)) live on very different scales, so volume is plotted on a secondary
    right-hand y-axis and everything else shares the primary left-hand axis.
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
    if any(isinstance(v, dict) for k, v in metrics.items() if k != "time"):
        return _metrics_panel_percell(metrics, out_path, include_plotlyjs)

    times = metrics.get("time") or list(range(len(next(iter(metrics.values()), []))))
    series = {k: v for k, v in metrics.items() if k != "time" and v}

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
    output shape (``{metric: {cell_id: [...]}}``). One trace per (metric, cell
    id) pair, colored by cell id (matching ``_render_colony_frame``'s
    ``_ID_PALETTE``) and distinguished by metric via line dash style, so a
    reader can track "cell 2's biomass" as one consistent color across every
    metric. ``volume`` again gets its own secondary y-axis (same O(10-100) vs
    O(0.1-1) scale mismatch as the flagship). Falls back to a small static HTML
    table if Plotly is unavailable.
    """
    times = metrics.get("time") or []
    metric_keys = [k for k in metrics if k != "time" and isinstance(metrics[k], dict)]
    cell_ids = sorted({cid for k in metric_keys for cid in metrics[k]}, key=lambda s: (len(s), s))

    try:
        import plotly.graph_objects as go
    except ImportError:
        cols = [(k, cid) for k in metric_keys for cid in cell_ids]
        header = "".join(f"<th>{k} (cell {cid})</th>" for k, cid in cols)
        rows = "".join(
            "<tr>" + "".join(f"<td>{metrics[k][cid][i]}</td>" for k, cid in cols) + "</tr>"
            for i in range(len(times))
        )
        out_path.write_text(
            f"<html><body><p>Plotly unavailable — static table fallback.</p>"
            f"<table border='1'><tr><th>time</th>{header}</tr>"
            + "".join(
                f"<tr><td>{t}</td>" + "".join(f"<td>{metrics[k][cid][i]}</td>" for k, cid in cols) + "</tr>"
                for i, t in enumerate(times)
            )
            + "</table></body></html>"
        )
        return "table-fallback"

    secondary = {"volume"}
    dash_by_metric = {}
    _dashes = ["solid", "dash", "dot", "dashdot"]
    for i, k in enumerate(metric_keys):
        dash_by_metric[k] = _dashes[i % len(_dashes)]
    color_by_cell = {cid: _ID_PALETTE[i % len(_ID_PALETTE)] for i, cid in enumerate(cell_ids)}

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
