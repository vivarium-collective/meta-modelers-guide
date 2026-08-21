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
                   com: list[float] | None, time: float,
                   glc_vmax: float, ace_vmax: float) -> np.ndarray:
    """Render one matplotlib (Agg) frame: glucose heatmap + cell footprint
    outline + acetate plume contour + COM marker. Returns an (H, W, 3) uint8
    RGB array (the figure canvas buffer).

    ``glc_vmax``/``ace_vmax`` are fixed across the whole run (computed once by
    the caller from every captured frame) rather than per-frame maxima — a
    per-frame max on the glucose panel would rescale color on every tick and
    hide the depletion halo behind the field's own left-to-right gradient;
    a fixed scale lets the halo actually read as a visible dip over time.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(9.0, 4.4), dpi=100)
    ax_glc, ax_ace = axes

    im = ax_glc.imshow(glucose, origin="lower", cmap="viridis", vmin=0.0, vmax=glc_vmax)
    ax_glc.contour(lattice > 0, levels=[0.5], colors="white", linewidths=1.6)
    if com is not None:
        ax_glc.plot(com[0], com[1], marker="o", markersize=7,
                    markerfacecolor="none", markeredgecolor="crimson", markeredgewidth=2.0)
    ax_glc.set_title(f"glucose  (t={time:.1f})", fontsize=10)
    ax_glc.set_xticks([]); ax_glc.set_yticks([])
    fig.colorbar(im, ax=ax_glc, fraction=0.046, pad=0.04)

    im2 = ax_ace.imshow(acetate, origin="lower", cmap="magma", vmin=0.0, vmax=ace_vmax)
    ax_ace.contour(lattice > 0, levels=[0.5], colors="white", linewidths=1.6)
    if com is not None:
        ax_ace.plot(com[0], com[1], marker="o", markersize=7,
                    markerfacecolor="none", markeredgecolor="deepskyblue", markeredgewidth=2.0)
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

        t = float(comp.state.get("global_time", (tick + 1) * cadence))
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

    frames = [_render_frame(lat, g, a, com, t, glc_vmax, ace_vmax)
              for lat, g, a, com, t in raw]

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


def metrics_panel(metrics: dict[str, list[float]], out_path: str | Path) -> str:
    """Write an interactive Plotly time-series panel of ``metrics`` (a dict of
    equal-length lists sharing a ``time`` axis) to ``out_path`` as HTML.

    Volume (O(10-100)), biomass (O(0.1)), and local_nutrient/acetate_secreted
    (O(1)) live on very different scales, so volume is plotted on a secondary
    right-hand y-axis and everything else shares the primary left-hand axis.
    Falls back to a small static HTML table if Plotly is unavailable.
    """
    out_path = Path(out_path)
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
    out_path.write_text(fig.to_html(include_plotlyjs="inline", full_html=True,
                                     config={"displayModeBar": False, "responsive": True}))
    return "plotly"
