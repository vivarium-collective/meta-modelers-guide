#!/usr/bin/env python
"""Render Fig 10's time-series demonstration: biofilm emergence as quantities over time.

Fig 10b's principle is that multicellular development is a runtime place-graph rewrite:
free motile bacteria ATTACH + aggregate into a nested microcolony, then the sessile
community MATURES by secreting extracellular matrix. The fig-10 snapshot sequence shows
the TOPOLOGY at three stages; this shows the same transition as QUANTITIES OVER TIME. It
RUNS the runnable fig10-emergence composite via build_core()+Composite for the composite's
default_n_steps and gathers the whole-environment trajectory from the emitter:

  * free (planktonic) cells   — top-level motile bacteria; drops to 0 at attachment;
  * biofilm-nested cells       — the same cells after they nest into the biofilm (sessile);
  * ECM (matrix) nodes         — appear only once the community has matured.

The curves read as a planktonic → sessile → matured transition: free cells fall to zero
exactly as nested cells rise (attachment/aggregation), then ECM climbs from zero after
maturation begins. Writes a labelled time-series PNG to the fig-10 study visualizations.

    python scripts/build_fig10_dynamics.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

ROOT = Path(__file__).resolve().parent.parent
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig10-emergence.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-10" / "visualizations" / "fig10-dynamics.png"

# palette (matches the study figures' teal / accent family)
C_FREE, C_NESTED, C_ECM = "#b4531f", "#0b7a75", "#4b5bd6"


def _top_nodes(tree: dict, ctrl: str):
    return [k for k, v in tree.items()
            if not k.startswith("_") and isinstance(v, dict) and v.get("_control") == ctrl]


def _env_counts(env: dict):
    """(#free top-level cells, #biofilm-nested cells, #ecm nodes) for one env frame."""
    free = len(_top_nodes(env, "cell"))
    nested = ecm = 0
    bf = env.get("biofilm")
    if isinstance(bf, dict):
        contents = bf.get("contents", {})
        nested = sum(1 for v in contents.values()
                     if isinstance(v, dict) and v.get("_control") == "cell")
        ecm = sum(1 for v in contents.values()
                  if isinstance(v, dict) and v.get("_control") == "ecm")
    return free, nested, ecm


def _run():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def main() -> None:
    rows = _run()
    t = [float(r["time"]) for r in rows]
    counts = [_env_counts(r["env"]) for r in rows]
    free = [c[0] for c in counts]
    nested = [c[1] for c in counts]
    ecm = [c[2] for c in counts]

    attach_t = next((t[i] for i in range(len(t)) if nested[i] > 0), None)
    mature_t = next((t[i] for i in range(len(t)) if ecm[i] > 0), None)

    # ── the load-bearing claim: planktonic → sessile → matured ────────────────
    assert free[-1] == 0, "free planktonic cells should all attach (free → 0)"
    assert max(nested) > 0, "cells should nest into a biofilm microcolony"
    assert max(ecm) > 0, "the matured community should secrete ECM"
    assert mature_t is not None and attach_t is not None and mature_t > attach_t, \
        "ECM (maturation) should appear only after attachment"

    # ── figure ──────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(10.5, 6.5))
    fig.suptitle("Fig 10 — biofilm emergence as a place-graph rewrite, over time",
                 fontsize=15, fontweight="bold")
    fig.text(0.5, 0.925,
             "Free motile bacteria attach + aggregate into a nested microcolony (free → nested), "
             "then the sessile community matures by secreting ECM.",
             ha="center", fontsize=10, color="#444")

    ax.step(t, free, where="post", color=C_FREE, lw=2.6, marker="o", ms=5,
            label="free (planktonic, motile) cells")
    ax.step(t, nested, where="post", color=C_NESTED, lw=2.6, marker="s", ms=5,
            label="biofilm-nested (sessile) cells")
    ax.step(t, ecm, where="post", color=C_ECM, lw=2.4, marker="^", ms=5,
            label="ECM (matrix) nodes")

    if attach_t is not None:
        ax.axvline(attach_t, color="#0b7a75", ls="--", lw=1.2, alpha=0.7)
        ax.text(attach_t + 0.15, max(nested) * 0.5, "attach +\naggregate",
                fontsize=8, color="#0b7a75", va="center")
    if mature_t is not None:
        ax.axvline(mature_t, color="#4b5bd6", ls="--", lw=1.2, alpha=0.7)
        ax.text(mature_t + 0.15, max(ecm) + 0.4, "mature\n(ECM)",
                fontsize=8, color="#4b5bd6", va="center")

    ax.set_ylabel("number of nodes")
    ax.set_xlabel("time")
    ax.set_title("planktonic → sessile → matured", fontsize=11)
    ax.legend(fontsize=9, loc="center right")
    ax.grid(alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.9))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  free cells   {free[0]} → {free[-1]}  (attach at t={attach_t})")
    print(f"  nested cells {nested[0]} → {nested[-1]}")
    print(f"  ECM nodes    {ecm[0]} → {ecm[-1]}  (mature at t={mature_t})")


if __name__ == "__main__":
    main()
