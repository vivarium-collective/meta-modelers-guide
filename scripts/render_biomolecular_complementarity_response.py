#!/usr/bin/env python
"""The *biomolecular-complementarity* study's "response of the contract" figure.

The paper's §Molecular compositions section (Fig 7) frames its subject as a
question about interfaces: which patterns of molecular complementarity give rise
to interfaces that behave as functional, regulatable boundaries. This study puts
two spatial primitives of that question on the lattice and asks the contract's
demand directly -- COMPLEMENTARY INTERACTIONS DRIVE SPATIAL ORDER:

  (a) SORTING (``cell-sorting-spatial``, a real ``CpmSorting`` differential-
      adhesion executable): two cell types differing only in which contacts they
      find energetically favorable demix a seeded checkerboard -- the heterotypic-
      contact fraction collapses from a raw ~1.0 checkerboard toward a sorted low
      value -- WHILE the clump stays cohesive (live-cell pixels held, per-type
      counts conserved). The NEUTRAL-J control (all contact energies equal) stays
      MIXED: the contact-energy asymmetry J is the CAUSE, not CPM dynamics.

  (b) CONDENSATE (``condensate-cahn-hilliard``, a real ``CahnHilliard``
      executable): a near-critical scalar composition field phase-separates --
      the field variance rises from near-zero toward the coexistence variance as
      two domains form -- WHILE total mass is conserved (a divergence-of-a-flux
      update) and the field stays bounded in the physical two-phase range.

Every curve here is measured off the REAL running compiled executable -- not a
re-plot of the baked GIFs. The sorting arm is driven in a manual cadence loop
against a live ``Composite`` so each tick's lattice can be snapped for the
filmstrip; the condensate arm is run through the composite's own RAMEmitter,
whose emitted ``phi`` leaves come back as 2-D fields for the imshow money shots.

Outputs into the study's visualizations/:
  biomolecular-complementarity-response.svg / .png
Prints the headline numbers (hetero_frac decline, neutral control, cell-count +
pixel conservation, phi_var growth, mass drift, phi bounds).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.colors import ListedColormap, BoundaryNorm
from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core
from meta_modelers_guide.cpm.sorting import hetero_frac, cell_pixels

ROOT = Path(__file__).resolve().parent.parent
COMPOSITES = ROOT / "meta_modelers_guide" / "composites"
VIZ = ROOT / "workspace" / "studies" / "biomolecular-complementarity" / "visualizations"

SORTING = "cell-sorting-spatial"
CONDENSATE = "condensate-cahn-hilliard"

# Book palette -- the guide's teal family + a warm accent.
INK = "#16211f"
TEAL = "#0d6e6b"
TEAL_L = "#3f9e99"
WARM = "#a5620f"
WARM_L = "#c98a3a"
GRID = "#c9d3d1"
UNIFORM = "#7a8582"
MEDIUM = "#e8edec"        # CPM medium (background lattice)
FLOOR_C = "#7a8582"

SORT_TICKS = 60           # 60 ticks x mcs=10 = 600 Monte Carlo steps
COND_TICKS = 50           # 50 ticks x steps_per_tick=200 = 10000 explicit CH steps

_CORE = None


def _core():
    global _CORE
    if _CORE is None:
        _CORE = build_core()
    return _CORE


def _load(stem):
    """Deep-copied state dict for a study composite (the real baked spec)."""
    state = json.loads((COMPOSITES / f"{stem}.composite.json").read_text())["state"]
    return json.loads(json.dumps(state))


# ── sorting arm ──────────────────────────────────────────────────────────────
def _type_lattice(world, lat):
    """Map a cell-id lattice to a type lattice (0 medium, 1 type-1, 2 type-2)
    for a colorized snapshot."""
    types = world.cell_types()
    out = np.zeros_like(lat)
    for cid in np.unique(lat):
        if cid == 0:
            continue
        out[lat == cid] = int(types[int(cid)])
    return out


def _run_sorting(neutral=False, n_ticks=SORT_TICKS):
    """Drive the real CpmSorting executable in a manual cadence loop (so each
    tick's lattice can be captured). ``neutral`` rebuilds the causal control by
    flattening every contact energy to a single value (all J equal -> heterotypic
    contact is no costlier than homotypic -> no thermodynamic drive to demix)."""
    st = _load(SORTING)
    if neutral:
        # neutral-J control: all contact energies equal (study uses all J = 8).
        for c in st["cell"]["config"]["contact"]:
            c["j"] = 8.0
    grid = st["cell"]["config"]["grid"]
    nx, ny = int(grid["nx"]), int(grid["ny"])
    sim = Composite({"state": st}, core=_core())
    world = sim.state["cell"]["instance"].world

    # t0 -- the raw seeded checkerboard, before any relaxation (~1.0).
    lat0 = np.array(world.snapshot()).reshape(ny, nx)
    mcs, hf, px = [0.0], [hetero_frac(lat0, world.cell_types())], [float(cell_pixels(lat0))]
    n1, n2 = [], []
    lattices = {0: _type_lattice(world, lat0)}

    for tick in range(n_ticks):
        sim.run(1)
        o = sim.state["obs"]
        lat = np.array(world.snapshot()).reshape(ny, nx)
        mcs.append(float((tick + 1) * st["cell"]["config"]["mcs"]))
        hf.append(float(o["hetero_frac"]))
        px.append(float(o["cell_pixels"]))
        n1.append(int(o["n_type1"])); n2.append(int(o["n_type2"]))
        lattices[tick + 1] = _type_lattice(world, lat)

    return {
        "mcs": np.array(mcs), "hetero": np.array(hf), "pixels": np.array(px),
        "n_type1": np.array(n1), "n_type2": np.array(n2), "lattices": lattices,
        "n_ticks": n_ticks, "mcs_per_tick": int(st["cell"]["config"]["mcs"]),
    }


# ── condensate arm ───────────────────────────────────────────────────────────
def _run_condensate(n_ticks=COND_TICKS):
    """Run the real CahnHilliard executable through its own RAMEmitter; read the
    phi field + variance/mean/bounds straight off the emitted rows."""
    st = _load(CONDENSATE)
    spt = int(st["ch"]["config"]["steps_per_tick"])
    sim = Composite({"state": st}, core=_core())
    sim.run(n_ticks)
    rows = gather_emitter_results(sim)[("emitter",)]
    # row 0 is the pre-update emit (obs still zero-initialised): drop it so the
    # series starts from the first true reading of the seeded field.
    rows = rows[1:]
    steps = np.array([float(r["time"]) * spt for r in rows])
    return {
        "steps": steps,
        "phi_var": np.array([float(r["phi_var"]) for r in rows]),
        "phi_mean": np.array([float(r["phi_mean"]) for r in rows]),
        "phi_min": np.array([float(r["phi_min"]) for r in rows]),
        "phi_max": np.array([float(r["phi_max"]) for r in rows]),
        "fields": {int(round(float(r["time"]) * spt)): np.array(r["phi"], dtype=float)
                   for r in rows},
        "steps_per_tick": spt,
    }


def render():
    VIZ.mkdir(parents=True, exist_ok=True)
    head = {}

    diff = _run_sorting(neutral=False)
    neut = _run_sorting(neutral=True)
    cond = _run_condensate()

    # ── headline numbers ─────────────────────────────────────────────────────
    hetero0 = float(diff["hetero"][0])            # raw checkerboard ~1.0
    hetero_first = float(diff["hetero"][1])        # first observation ~0.64
    hetero_final = float(diff["hetero"][-1])       # sorted ~0.06
    neut_final = float(neut["hetero"][-1])         # neutral control ~0.52
    px_drift = abs(diff["pixels"][-1] - diff["pixels"][1]) / diff["pixels"][1]
    pv0 = float(cond["phi_var"][0])                # near-flat ~7e-5
    pv_final = float(cond["phi_var"][-1])          # ~0.38
    mass_drift = float(np.max(np.abs(cond["phi_mean"] - cond["phi_mean"][0])))
    phi_lo = float(cond["phi_min"].min()); phi_hi = float(cond["phi_max"].max())

    head.update(
        sorting_hetero_raw_checkerboard=round(hetero0, 3),
        sorting_hetero_first_obs=round(hetero_first, 3),
        sorting_hetero_final=round(hetero_final, 3),
        sorting_hetero_fold_drop=round(hetero_first / max(hetero_final, 1e-9), 1),
        neutral_hetero_final=round(neut_final, 3),
        cell_pixels_final=int(round(diff["pixels"][-1])),
        cell_pixels_drift_pct=round(px_drift * 100, 2),
        n_type1_final=int(diff["n_type1"][-1]),
        n_type2_final=int(diff["n_type2"][-1]),
        condensate_phi_var_start=round(pv0, 6),
        condensate_phi_var_final=round(pv_final, 4),
        condensate_mass_drift=mass_drift,
        condensate_phi_min=round(phi_lo, 3),
        condensate_phi_max=round(phi_hi, 3),
        sorting_total_mcs=int(diff["mcs"][-1]),
        condensate_total_steps=int(cond["steps"][-1]),
    )

    # ── figure ────────────────────────────────────────────────────────────────
    plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#3a4744",
                         "axes.labelcolor": INK, "text.color": INK,
                         "xtick.color": INK, "ytick.color": INK})
    fig = plt.figure(figsize=(13.6, 8.6), dpi=120)
    outer = gridspec.GridSpec(2, 1, height_ratios=[1.0, 0.82], hspace=0.36,
                              left=0.065, right=0.955, top=0.9, bottom=0.055)
    top = outer[0].subgridspec(1, 2, wspace=0.24)
    bot = outer[1].subgridspec(1, 6, wspace=0.10)

    def _clean(a):
        for sp in ("top", "right"):
            a.spines[sp].set_visible(False)
        a.grid(True, color=GRID, alpha=0.5, lw=0.6)

    # (A) SORTING order parameter -- hetero_frac(t) collapses; neutral control
    #     stays flat; cohesion guard (cell_pixels) holds on the twin axis.
    a = fig.add_subplot(top[0, 0])
    a.plot(diff["mcs"], diff["hetero"], color=TEAL, lw=2.6, zorder=3,
           label="differential J (sorts)")
    a.plot(neut["mcs"], neut["hetero"], color=WARM, lw=2.4, ls="--", zorder=3,
           label="neutral J control (stays mixed)")
    a.scatter([diff["mcs"][0]], [hetero0], color=UNIFORM, s=40, zorder=4)
    a.annotate(f"raw checkerboard\nhetero = {hetero0:.2f}", (diff["mcs"][0], hetero0),
               (diff["mcs"][0] + 55, hetero0 - 0.02), fontsize=7.6, color=UNIFORM,
               arrowprops=dict(arrowstyle="->", color=UNIFORM, lw=0.8))
    a.scatter([diff["mcs"][-1]], [hetero_final], color=TEAL, s=48, zorder=5,
              edgecolor="white", linewidth=0.8)
    a.annotate(f"sorted\nhetero = {hetero_final:.2f}", (diff["mcs"][-1], hetero_final),
               (diff["mcs"][-1] - 210, hetero_final + 0.14), fontsize=7.8, color=TEAL,
               arrowprops=dict(arrowstyle="->", color=TEAL, lw=0.8))
    a.annotate(f"neutral J -> {neut_final:.2f}\n(J is the cause)",
               (neut["mcs"][-1], neut_final), (neut["mcs"][-1] - 250, neut_final - 0.18),
               fontsize=7.8, color=WARM, arrowprops=dict(arrowstyle="->", color=WARM, lw=0.8))
    a.set_ylim(0, 1.05)
    a.set_title("sorting order parameter -- heterotypic-contact fraction",
                color=INK, fontsize=10.5)
    a.set_xlabel("Monte Carlo steps"); a.set_ylabel("hetero_frac", color=TEAL)
    a.tick_params(axis="y", colors=TEAL)
    a.legend(frameon=False, fontsize=7.8, loc="center right")

    a2 = a.twinx()
    a2.plot(diff["mcs"][1:], diff["pixels"][1:], color=TEAL_L, lw=1.4, ls=":",
            zorder=2, label="cohesion guard")
    a2.set_ylabel("cell_pixels (cohesion guard)", color=TEAL_L)
    a2.tick_params(axis="y", colors=TEAL_L)
    a2.set_ylim(0, max(diff["pixels"]) * 1.9)
    a2.spines["top"].set_visible(False)
    a2.text(0.035, 0.86,
            f"cohesion guard: pixels ~{int(round(diff['pixels'][-1]))} ({px_drift*100:.1f}% drift), "
            f"counts {diff['n_type1'][-1]}/{diff['n_type2'][-1]}\n-- the clump sorted, it did not dissolve",
            transform=a.transAxes, fontsize=7.2, color=TEAL_L, va="top")
    a.grid(True, color=GRID, alpha=0.5, lw=0.6)

    # (B) CONDENSATE order parameter -- phi_var(t) rises; mass conserved.
    a = fig.add_subplot(top[0, 1])
    a.semilogy(cond["steps"], cond["phi_var"], color=WARM, lw=2.6, zorder=3)
    a.scatter([cond["steps"][0]], [pv0], color=UNIFORM, s=40, zorder=4)
    a.annotate(f"near-critical seed\nphi_var = {pv0:.1e}", (cond["steps"][0], pv0),
               (cond["steps"][-1] * 0.20, pv0 * 0.6), fontsize=7.8, color=UNIFORM,
               arrowprops=dict(arrowstyle="->", color=UNIFORM, lw=0.8))
    a.scatter([cond["steps"][-1]], [pv_final], color=WARM, s=48, zorder=5,
              edgecolor="white", linewidth=0.8)
    a.annotate(f"two phases\nphi_var = {pv_final:.2f}", (cond["steps"][-1], pv_final),
               (cond["steps"][-1] * 0.52, pv_final * 0.10), fontsize=7.8, color=WARM,
               arrowprops=dict(arrowstyle="->", color=WARM, lw=0.8))
    a.set_title("condensate order parameter -- composition-field variance",
                color=INK, fontsize=10.5)
    a.set_xlabel("Cahn-Hilliard steps"); a.set_ylabel("phi_var  (log scale)", color=WARM)
    a.tick_params(axis="y", colors=WARM)
    a.text(0.03, 0.955,
           f"mass conserved:  phi_mean drift = {mass_drift:.1e}  (round-off)\n"
           f"field bounded:  phi in [{phi_lo:.2f}, {phi_hi:.2f}]  -- no NaN",
           transform=a.transAxes, fontsize=7.8, color=INK, va="top",
           bbox=dict(boxstyle="round,pad=0.4", fc="#f2f6f5", ec=GRID, lw=0.8))
    _clean(a)

    # ── bottom row: final-field / lattice "money shots" ─────────────────────────
    # sorting: type lattice (medium / type-1 / type-2) at three MCS checkpoints.
    sort_cmap = ListedColormap([MEDIUM, TEAL, WARM])
    sort_norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], sort_cmap.N)
    sort_shots = [
        (0, "seeded checkerboard\n0 MCS -- mixed"),
        (diff["n_ticks"] // 3, f"relaxing\n{(diff['n_ticks'] // 3) * diff['mcs_per_tick']} MCS"),
        (diff["n_ticks"], f"sorted clump\n{diff['n_ticks'] * diff['mcs_per_tick']} MCS"),
    ]
    for j, (tick, label) in enumerate(sort_shots):
        a = fig.add_subplot(bot[0, j])
        a.imshow(diff["lattices"][tick], cmap=sort_cmap, norm=sort_norm,
                 interpolation="nearest", origin="lower")
        a.set_xticks([]); a.set_yticks([])
        for sp in a.spines.values():
            sp.set_edgecolor(TEAL); sp.set_linewidth(2.0)
        a.set_title(label, color=TEAL, fontsize=8.4, pad=4)

    # condensate: phi field on a diverging scale centred at 0 at three steps.
    cond_steps_sorted = sorted(cond["fields"])
    cond_shots = [
        (cond_steps_sorted[0], f"near-critical seed\n{cond_steps_sorted[0]} steps -- uniform"),
        (cond_steps_sorted[len(cond_steps_sorted) // 3],
         f"spinodal coarsening\n{cond_steps_sorted[len(cond_steps_sorted) // 3]} steps"),
        (cond_steps_sorted[-1], f"two phases (phi ~ +/-1)\n{cond_steps_sorted[-1]} steps"),
    ]
    im = None
    for j, (step, label) in enumerate(cond_shots):
        a = fig.add_subplot(bot[0, 3 + j])
        im = a.imshow(cond["fields"][step], cmap="RdBu_r", vmin=-1.0, vmax=1.0,
                      interpolation="nearest", origin="lower")
        a.set_xticks([]); a.set_yticks([])
        for sp in a.spines.values():
            sp.set_edgecolor(WARM); sp.set_linewidth(2.0)
        a.set_title(label, color=WARM, fontsize=8.4, pad=4)
    # one shared colorbar under the condensate triptych
    cax = fig.add_axes([0.64, 0.028, 0.28, 0.014])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal")
    cb.set_label("composition field  phi", fontsize=7.8)
    cb.ax.tick_params(labelsize=7)

    # legend patch for the sorting types
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=TEAL, edgecolor="none", label="cell type 1"),
               Patch(facecolor=WARM, edgecolor="none", label="cell type 2"),
               Patch(facecolor=MEDIUM, edgecolor=GRID, label="medium")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.065, 0.018),
               frameon=False, fontsize=7.6, ncol=3, columnspacing=1.2, handlelength=1.2)

    fig.text(0.065, 0.452,
             "SORTING (CpmSorting, 8x8 checkerboard) -- like sits with like;\n"
             "the heterotypic interface collapses",
             fontsize=8.3, color=TEAL, style="italic", va="top")
    fig.text(0.635, 0.452,
             "CONDENSATE (Cahn-Hilliard, 64x64 field) -- a mass-conserved\n"
             "boundary forms out of a well-mixed medium",
             fontsize=8.3, color=WARM, style="italic", va="top")

    fig.suptitle("Biomolecular complementarity, spatialized -- the response the contract demands",
                 fontsize=14, color=INK, y=0.965, weight="bold")
    fig.text(0.5, 0.925,
             "Complementary interactions drive spatial order: differential adhesion sorts two cell types "
             "(and equal J does not); a near-critical field phase-separates. "
             "Every curve measured off the real compiled executable.",
             ha="center", fontsize=9.2, color="#3a4744")

    fig.savefig(VIZ / "biomolecular-complementarity-response.svg", format="svg")
    fig.savefig(VIZ / "biomolecular-complementarity-response.png", format="png")
    plt.close(fig)
    return head


if __name__ == "__main__":
    h = render()
    print(json.dumps(h, indent=2))
    print("\nwrote", VIZ / "biomolecular-complementarity-response.svg")
