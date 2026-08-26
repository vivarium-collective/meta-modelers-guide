#!/usr/bin/env python
"""Render Fig 7's time-series demonstration: the nested cellular hierarchy in motion.

Fig 7b's principle is that a cell's subsystems are a NESTED hierarchy of coupled
processes running together. This RUNS the runnable composite
(meta_modelers_guide.composites.fig07-runnable): six ODE handlers act on stores buried
up to SIX levels down in one place graph (extracellular_matrix → membrane → cytoplasm →
nucleus → chromosome → chromatin → nucleosome → DNA) WITHOUT flattening it, and their
outputs feed each other's inputs so the whole hierarchy evolves as one coupled system:

  * transmembrane transport imports nutrients across the membrane (→ cytoplasmic pool);
  * metabolism turns nutrients + enzymes into metabolites + energy;
  * transcription reads the deeply-nested DNA into RNA;
  * translation reads RNA + metabolites on the ribosome pool into proteins;
  * subunit assembly builds ribosomes from proteins (closing the loop back to translation);
  * replication/repair holds the DNA copy number at its genome set point.

It writes a four-panel time-series PNG to the fig-07 study visualizations and asserts the
load-bearing claim: the cascade actually PROPAGATES across levels — the transported
nutrient, the metabolic products, the transcript, the protein, and the assembled ribosome
all rise together from a seeded environment. Re-run whenever the fig07 handlers or the
runnable composite change.

    python scripts/build_fig07_dynamics.py
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
COMPOSITE = ROOT / "meta_modelers_guide" / "composites" / "fig07-runnable.composite.json"
OUT = ROOT / "workspace" / "studies" / "fig-07" / "visualizations" / "fig07-dynamics.png"

# palette (teal / accent family shared with the other study figures)
C_NUT, C_MET, C_ENE = "#0b7a75", "#1c7a77", "#b4531f"
C_RNA, C_PROT, C_RIB, C_DNA = "#4b5bd6", "#7a4bd6", "#c2851b", "#8a8f98"


def _run():
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    return gather_emitter_results(sim)[("emitter",)]


def main() -> None:
    rows = _run()
    t = [float(r["time"]) for r in rows]
    nut = [float(r["nutrients"]) for r in rows]
    met = [float(r["metabolites"]) for r in rows]
    ene = [float(r["energy"]) for r in rows]
    rna = [float(r["rna"]) for r in rows]
    prot = [float(r["proteins"]) for r in rows]
    rib = [float(r["ribosome"]) for r in rows]
    dna = [float(r["dna"]) for r in rows]

    # ── the load-bearing claim: the nested cascade PROPAGATES across levels ─────
    assert nut[-1] > nut[0] + 1.0, "transport should fill the cytoplasmic nutrient pool"
    assert met[-1] > met[0] + 1.0, "metabolism should produce metabolites"
    assert rna[-1] > rna[0] + 1e-3, "transcription output (RNA) should rise"
    assert prot[-1] > prot[0] + 1e-3, "translation output (protein) should rise"
    assert rib[-1] > rib[0] + 1e-3, "ribosome assembly should build the ribosome pool"

    # ── figure ────────────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5), sharex=True)
    fig.suptitle("Fig 7 — a nested hierarchy of coupled subsystems running together",
                 fontsize=15, fontweight="bold")
    fig.text(0.5, 0.925,
             "Six processes act on stores up to SIX levels deep in one place graph; their "
             "outputs feed each other so the whole hierarchy evolves as one coupled cell.",
             ha="center", fontsize=10, color="#444")

    ax = axes[0][0]
    ax.plot(t, nut, color=C_NUT, lw=2.2, marker="o", ms=3, label="nutrients (cytoplasm)")
    ax.set_title("Transmembrane transport  (membrane → cytoplasm)", fontsize=11)
    ax.set_ylabel("imported nutrient pool")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)

    ax = axes[0][1]
    ax.plot(t, met, color=C_MET, lw=2.2, marker="o", ms=3, label="metabolites")
    ax.plot(t, ene, color=C_ENE, lw=2.2, marker="s", ms=3, label="energy")
    ax.set_title("Metabolism  (nutrients + enzymes → metabolites + energy)", fontsize=11)
    ax.set_ylabel("cytoplasmic products")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)

    ax = axes[1][0]
    ax.plot(t, rna, color=C_RNA, lw=2.2, marker="o", ms=3, label="RNA (transcription)")
    ax.plot(t, prot, color=C_PROT, lw=2.2, marker="^", ms=3, label="protein (translation)")
    ax.set_title("Central dogma  (DNA →6 levels→ RNA → protein)", fontsize=11)
    ax.set_ylabel("gene-expression products")
    ax.set_xlabel("time")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.25)

    ax = axes[1][1]
    ax.plot(t, rib, color=C_RIB, lw=2.2, marker="o", ms=3, label="ribosome (assembly)")
    ax.plot(t, dna, color=C_DNA, lw=2.0, ls="--", marker="s", ms=3,
            label="DNA (replication set point)")
    ax.set_title("Ribosome assembly  &  DNA maintenance", fontsize=11)
    ax.set_ylabel("assembled ribosome / DNA copies")
    ax.set_xlabel("time")
    ax.legend(fontsize=8, loc="center left")
    ax.grid(alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.9))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150)
    plt.close(fig)
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  nutrients (transport)   {nut[0]:.4f} → {nut[-1]:.4f}")
    print(f"  metabolites (metabolism){met[0]:.4f} → {met[-1]:.4f}")
    print(f"  energy (metabolism)     {ene[0]:.4f} → {ene[-1]:.4f}")
    print(f"  RNA (transcription)     {rna[0]:.4f} → {rna[-1]:.4f}")
    print(f"  protein (translation)   {prot[0]:.4f} → {prot[-1]:.4f}")
    print(f"  ribosome (assembly)     {rib[0]:.4f} → {rib[-1]:.4f}")
    print(f"  DNA (replication)       {dna[0]:.4f} → {dna[-1]:.4f}  (held at set point)")


if __name__ == "__main__":
    main()
