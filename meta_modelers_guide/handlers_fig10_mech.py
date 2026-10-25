"""Fig 10 · development (biofilm) — a *mechanistic*, spatially-emergent biofilm.

Real-mechanism upgrade of ``fig10_topology.BiofilmEmergence`` (kept as the
baseline). The baseline reorganizes the place graph on a WALL CLOCK: cells attach
at ``attach_at`` and secrete ECM at ``mature_at``, regardless of where they are.
That demonstrates the *structure* of the rewrite, not an emergent decision (the
review's objection).

Here attachment EMERGES from spatial state. Motile cells live at 2-D positions in
a box (``xs``/``ys`` map[float] stores, lattice units). Each tick:

* **motility + local adhesion** — free cells drift toward the centroid of
  neighbours within ``sense_radius`` at a rate set by ``adhesion`` (a local
  attraction), with short-range ``repulsion`` so they pack to a finite-radius
  cluster rather than a point. Turn ``adhesion`` off and they never aggregate.
* **proximity + SUSTAINED contact → collective** — when at least ``quorum`` cells
  sit inside ``form_radius`` of the centroid for ``sustain_ticks`` consecutive
  ticks, the biofilm forms: the ``colony`` place graph is rewritten so the cells
  nest under a new ``biofilm`` node (identity + biomass preserved — the topology
  smoke test), ``formed`` flips on, and the collective ``cohesion`` port becomes
  operative. The trigger is the measured cluster geometry, not a configured tick.
* **ECM secretion / persistence** — once sessile, cells secrete ECM (``ecm``
  store) that degrades first-order; ECM binds the community (``cohesion`` =
  ecm/(ecm+k_bind)). Without ECM the sessile cells slowly spread back apart
  (``spread_rate`·(1−cohesion)``) — so blocking ECM changes persistence/morphology.

Matched-null controls (set with an EPSILON, never 0.0 — a float 0.0 config is
silently restored to its schema default): ``adhesion=ε`` (no aggregation, no
biofilm), ``ecm_rate=ε`` (forms, then disperses). All classes auto-register at
``local:<ClassName>`` via build_core.
"""
from __future__ import annotations

import copy
import math

from process_bigraph import Process


def _f(d):
    return {"_type": "float", "_default": d}


def _node(control, **contents):
    return {"_control": control, "contents": dict(contents)}


def _read_map(m) -> list[float]:
    """Index-ordered floats from a map[float] store (keys '0'..'N-1')."""
    return [float(m[str(i)]) for i in range(len([k for k in m if not str(k).startswith("_")]))]


def _delta_map(deltas) -> dict:
    return {str(i): deltas[i] for i in range(len(deltas))}


class BiofilmColony(Process):
    """Spatially-emergent biofilm: free motile cells aggregate by local adhesion,
    form a collective once a quorum is sustained in proximity (a place-graph
    rewrite), secrete ECM that binds the community, and disperse again without it.
    Everything is driven by the cells' positions, not a clock."""

    config_schema = {
        "sense_radius": _f(6.0),     # neighbour sensing radius (lattice units)
        "adhesion": _f(0.35),        # attraction rate toward neighbour centroid
        "repulsion": _f(0.45),       # short-range push (avoids collapse to a point)
        "rep_radius": _f(1.2),       # range of the short-range repulsion
        "form_radius": _f(2.2),      # cluster radius that counts as "aggregated"
        "quorum": _f(4.0),           # cells within form_radius needed to form
        "sustain_ticks": _f(3.0),    # consecutive ticks of proximity before forming
        "ecm_rate": _f(0.6),         # ECM secretion per sessile cell per tick
        "ecm_decay": _f(0.05),       # first-order ECM degradation
        "k_bind": _f(2.0),           # ECM half-saturation for cohesion
        "spread_rate": _f(0.5),      # sessile dispersal when unbound by ECM
        "max_step": _f(1.0),         # clamp |displacement| per tick
        "box": _f(16.0),             # dish size; cells cannot leave [0, box]
    }

    def __init__(self, config=None, core=None):
        super().__init__(config, core=core)
        self._sustain = 0.0
        self._formed = False
        self._form_t = -1.0
        self._t = 0.0
        self._last = {}

    def inputs(self):
        return {"xs": "map[float]", "ys": "map[float]", "ecm": "concentration",
                "colony": "tree[node]"}

    def outputs(self):
        return {"xs": "map[float]", "ys": "map[float]", "ecm": "concentration",
                "colony": "overwrite[tree[node]]",
                "cluster_radius": "length", "cohesion": "fraction",
                "n_clustered": "cell_count", "formed": "fraction",
                "ecm_total": "concentration"}

    def _set(self, port, value):
        d = value - self._last.get(port, 0.0)
        self._last[port] = value
        return d

    def update(self, state, interval):
        self._t += interval
        c = self.config
        xs = _read_map(state["xs"])
        ys = _read_map(state["ys"])
        n = len(xs)
        ecm = float(state.get("ecm", 0.0))

        cx = sum(xs) / n
        cy = sum(ys) / n
        dists = [math.hypot(xs[i] - cx, ys[i] - cy) for i in range(n)]
        cluster_radius = max(dists)
        n_clustered = sum(1 for d in dists if d <= c["form_radius"])
        cohesion = ecm / (ecm + c["k_bind"]) if ecm > 0 else 0.0

        dx = [0.0] * n
        dy = [0.0] * n

        if not self._formed:
            # free swimmers: local adhesion toward neighbour centroid + repulsion
            for i in range(n):
                nbrs = [j for j in range(n) if j != i and
                        math.hypot(xs[i] - xs[j], ys[i] - ys[j]) <= c["sense_radius"]]
                if nbrs:
                    nx = sum(xs[j] for j in nbrs) / len(nbrs)
                    ny = sum(ys[j] for j in nbrs) / len(nbrs)
                    dx[i] += c["adhesion"] * (nx - xs[i]) * interval
                    dy[i] += c["adhesion"] * (ny - ys[i]) * interval
            self._repel(xs, ys, dx, dy, interval)
            # emergent formation: quorum sustained inside form_radius
            if n_clustered >= int(c["quorum"]) and cluster_radius <= c["form_radius"]:
                self._sustain += interval
            else:
                self._sustain = 0.0
            form_now = self._sustain >= c["sustain_ticks"]
        else:
            # sessile community: ECM binds; without it, cells spread back apart
            unbound = 1.0 - cohesion
            for i in range(n):
                dx[i] += c["spread_rate"] * unbound * (xs[i] - cx) * interval
                dy[i] += c["spread_rate"] * unbound * (ys[i] - cy) * interval
            self._repel(xs, ys, dx, dy, interval)
            form_now = False

        # clamp displacement, then keep cells inside the dish [0, box]
        box = c["box"]
        for i in range(n):
            dx[i] = max(-c["max_step"], min(c["max_step"], dx[i]))
            dy[i] = max(-c["max_step"], min(c["max_step"], dy[i]))
            nx, ny = xs[i] + dx[i], ys[i] + dy[i]
            if nx < 0: dx[i] = -xs[i]
            elif nx > box: dx[i] = box - xs[i]
            if ny < 0: dy[i] = -ys[i]
            elif ny > box: dy[i] = box - ys[i]

        out = {
            "xs": _delta_map(dx), "ys": _delta_map(dy),
            "cluster_radius": self._set("cluster_radius", cluster_radius),
            "cohesion": self._set("cohesion", cohesion),
            "n_clustered": self._set("n_clustered", float(n_clustered)),
            "formed": self._set("formed", 1.0 if self._formed else 0.0),
            "ecm_total": self._set("ecm_total", ecm),
        }

        # ECM dynamics once sessile (secretion − decay)
        d_ecm = 0.0
        if self._formed:
            d_ecm = c["ecm_rate"] * n * interval - c["ecm_decay"] * ecm * interval
        out["ecm"] = d_ecm

        # emergent place-graph rewrite: nest the free cells into a biofilm node
        if form_now and not self._formed:
            self._formed = True
            self._form_t = self._t
            colony = copy.deepcopy(state["colony"])
            cells = {}
            for k in list(colony.keys()):
                if str(k).startswith("_"):
                    continue
                node = colony[k]
                if isinstance(node, dict) and node.get("_control") == "cell":
                    cells[k] = node            # preserve identity + biomass
            new_colony = {"_type": "tree[node]",
                          "biofilm": {"_control": "biofilm", "contents": cells}}
            out["colony"] = new_colony
            out["formed"] = self._set("formed", 1.0)
        return out

    def _repel(self, xs, ys, dx, dy, interval):
        c = self.config
        n = len(xs)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                d = math.hypot(xs[i] - xs[j], ys[i] - ys[j])
                if 1e-9 < d < c["rep_radius"]:
                    push = c["repulsion"] * (c["rep_radius"] - d) / d * interval
                    dx[i] += push * (xs[i] - xs[j])
                    dy[i] += push * (ys[i] - ys[j])
