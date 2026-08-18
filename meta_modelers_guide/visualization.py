"""Interactive Plotly Visualization steps for the guide's EXECUTABLE composites.

Embedded in a running composite, a :class:`Visualization` step renders HTML that
the workbench loom shows in its **Visualizations** panel after a run (press ▶ Run).
This module gives every executable figure a nice interactive Plotly view of what
it actually does:

* :class:`DynamicsPlot` — an interactive time-series of the observables the step
  is wired to (constant / non-finite series are dropped so the plot stays clean).
* :class:`DynamicsMovie` — the same data as an animated Plotly figure (a Play
  button sweeps a marker across the trajectory), the "movie of what happened" for
  figures where watching the arc matters (growth → division → death, a colony
  developing, a population turning over).

Both declare their input ports from a ``observables`` config map ({label: type}),
so a single reusable class serves every composite — the composite's state entry
just wires each label to a store path (see ``scripts/add_composite_viz.py``).
"""
from __future__ import annotations

import math
from typing import Any

from process_bigraph import Visualization

# Deterministic, colour-blind-safe categorical order (validated palette family).
_PALETTE = ["#0d6e6b", "#a5620f", "#3f9e99", "#657572",
            "#c98a3a", "#1c7a77", "#8b9995", "#0a4f4c", "#b4531f", "#2f8f8a"]


def _leaf(label: str) -> str:
    return label.split(".")[-1]


class _ObservableStep(Visualization):
    """Shared plumbing: declare ports from ``observables`` + accumulate a buffer."""

    config_schema = {
        **Visualization.config_schema,
        # {label: bigraph-type} — one input port per observable, so any set of
        # stores can be wired without a bespoke subclass. `time` is added below.
        "observables": {"_type": "map[string,string]", "_default": {}},
    }

    def inputs(self) -> dict[str, Any]:
        ports = dict((self.config.get("observables") or {}))
        ports["time"] = "float"
        return ports

    def accumulate(self, state: dict) -> None:
        buf = getattr(self, "_buf", None)
        if buf is None:
            buf = self._buf = {"time": []}
        t = state.get("time")
        buf["time"].append(float(t) if isinstance(t, (int, float)) else len(buf["time"]))
        for label in (self.config.get("observables") or {}):
            v = state.get(label)
            if isinstance(v, dict):                       # map[string,float] field → aggregate
                v = sum(float(x) for x in v.values() if isinstance(x, (int, float)))
            buf.setdefault(label, []).append(float(v) if isinstance(v, (int, float)) else 0.0)

    def _series(self):
        """{label: values} for every MOVING observable, longest-common length,
        sorted by dynamic range (biggest mover first), + the time axis."""
        buf = getattr(self, "_buf", None) or {"time": []}
        times = buf.get("time") or [0]
        clean = {}
        for label, ys in buf.items():
            if label == "time" or not ys:
                continue
            if all(math.isfinite(y) for y in ys) and (max(ys) - min(ys)) > 1e-9:
                clean[label] = ys
        ordered = dict(sorted(clean.items(), key=lambda kv: max(kv[1]) - min(kv[1]), reverse=True))
        return times, ordered

    def _empty(self) -> str:
        return ('<p style="font-family:system-ui;color:#888;padding:14px">'
                "This run produced no moving observables to plot.</p>")


class DynamicsPlot(_ObservableStep):
    """Interactive Plotly time-series of the wired observables over the run."""

    def render(self) -> str:
        times, series = self._series()
        if not series:
            return self._empty()
        import plotly.graph_objects as go
        fig = go.Figure()
        for i, (label, ys) in enumerate(series.items()):
            fig.add_trace(go.Scatter(
                x=times[:len(ys)], y=ys, mode="lines",
                name=_leaf(label), line=dict(width=2.4, color=_PALETTE[i % len(_PALETTE)])))
        fig.update_layout(
            title=self.config.get("title") or "Dynamics",
            xaxis_title="time", yaxis_title="observable",
            template="plotly_white", height=440,
            margin=dict(l=56, r=20, t=52, b=44),
            legend=dict(orientation="h", yanchor="bottom", y=-0.28, xanchor="left", x=0),
            hovermode="x unified")
        return fig.to_html(include_plotlyjs="cdn", full_html=True,
                           div_id=self.stable_div_id("dyn"),
                           config={"displayModeBar": False, "responsive": True})


class DynamicsMovie(_ObservableStep):
    """Animated Plotly trajectory — a Play button sweeps a marker along each
    curve, replaying the arc of the run (grow → divide → die, colonize, evolve)."""

    def render(self) -> str:
        times, series = self._series()
        if not series:
            return self._empty()
        import plotly.graph_objects as go
        labels = list(series.keys())
        n = min(len(times), *(len(series[l]) for l in labels))
        t = times[:n]
        # Base traces: the full faint curves + a leading marker per series.
        base = []
        for i, label in enumerate(labels):
            col = _PALETTE[i % len(_PALETTE)]
            base.append(go.Scatter(x=t, y=series[label][:n], mode="lines",
                                   name=_leaf(label), line=dict(width=2, color=col)))
        for i, label in enumerate(labels):
            col = _PALETTE[i % len(_PALETTE)]
            base.append(go.Scatter(x=[t[0]], y=[series[label][0]], mode="markers",
                                   name=_leaf(label) + " •", showlegend=False,
                                   marker=dict(size=11, color=col)))
        # Frames advance the markers along the curves.
        frames = []
        for k in range(n):
            data = []
            for i, label in enumerate(labels):
                col = _PALETTE[i % len(_PALETTE)]
                data.append(go.Scatter(x=[t[k]], y=[series[label][k]], mode="markers",
                                       marker=dict(size=11, color=col)))
            frames.append(go.Frame(data=data, name=str(k),
                                    traces=list(range(len(labels), 2 * len(labels)))))
        fig = go.Figure(data=base, frames=frames)
        fig.update_layout(
            title=self.config.get("title") or "Movie",
            xaxis_title="time", yaxis_title="observable",
            template="plotly_white", height=460,
            margin=dict(l=56, r=20, t=52, b=64),
            legend=dict(orientation="h", yanchor="bottom", y=-0.32, xanchor="left", x=0),
            updatemenus=[dict(type="buttons", showactive=False, x=0.02, y=1.12,
                              buttons=[
                                  dict(label="▶ Play", method="animate",
                                       args=[None, {"frame": {"duration": 90, "redraw": True},
                                                    "fromcurrent": True,
                                                    "transition": {"duration": 0}}]),
                                  dict(label="❘❘ Pause", method="animate",
                                       args=[[None], {"frame": {"duration": 0, "redraw": False},
                                                      "mode": "immediate"}]),
                              ])])
        return fig.to_html(include_plotlyjs="cdn", full_html=True,
                           div_id=self.stable_div_id("movie"),
                           config={"displayModeBar": False, "responsive": True})
