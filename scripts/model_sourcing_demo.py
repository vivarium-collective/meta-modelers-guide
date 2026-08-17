"""Model-sourcing demonstration: 6 tasks, each choosing among real modules,
each graded by the sourcing audit; runnable choices are actually run."""
import json
from process_bigraph import Composite, composite_generator as CG
import viva_munk.composites as MC
import spatio_flux.composites as SC
from viva_meta_modelers_guide.core import build_core
from viva_superpowers import module_sourcing as MS, loop_state as L

# --- capability catalog (the manifest: module -> capabilities) ---
CATALOG = {
    "viva-munk":   ["physics_2d", "rigid_body", "collision", "mechanics", "adhesion"],
    "spatio-flux": ["spatial", "fba", "dfba", "diffusion", "reaction", "metabolism"],
    "viva-cpm":    ["cpm", "cell_shape", "adhesion", "spatial", "morphology"],
    "growth-proc": ["growth", "biomass"],
}

# ONE shared workspace core: importing viva-munk + spatio-flux inherits ALL
# their processes+types into it (viva_meta_modelers_guide.core.build_core), so
# every task below runs against a single core instead of a per-task module core.
# This is model-sourcing "reuse" made literal — the reused module contributes to
# the workspace core rather than standing up a parallel one.
core = build_core()

def run_munk(doc_fn, t=3.0):
    d = doc_fn(); st = d.get('state', d)
    sim = Composite({'state': st}, core=core); sim.run(t)
    cells = sim.state.get('cells') or sim.state.get('segment_cells') or {}
    return f"ran t={t}; {len(cells) if isinstance(cells,dict) else '?'} bodies"

def run_spatioflux(key, t=5.0):
    # spatio-flux composites are @composite_generator entries: build the state
    # document via build_generator(entry, core), then run on the shared core.
    entry = SC.REGISTRY.get(key)
    doc = CG.build_generator(entry, core=core)
    sim = Composite({'state': doc}, core=core); sim.run(t)
    fields = sim.state.get('fields', {})
    def _sum(name):
        v = fields.get(name)
        if v is None:
            return None
        import numpy as np
        return float(np.sum(v))
    g, a = _sum('glucose'), _sum('acetate')
    if g is not None:
        return f"ran t={t}; glucose 10.0->{g:.2f}, acetate 0.0->{a:.3f}"
    return f"ran t={t}; state keys {list(sim.state.keys())[:4]}"

def run_cpm(t=6):
    # Minimal Cellular Potts shape dynamics on the shared core: two cells seeded
    # as small square blocks relax toward their target volume/surface under the
    # Metropolis Hamiltonian (viva-cpm's Rust engine via CPMProcess).
    spec = {
        "potts": {"dims": [40, 40, 1], "boundary": "noflux",
                  "neighbor_order": 2, "temperature": 10.0, "seed": 1},
        "cells": [
            {"type": 1, "target_volume": 80.0, "lambda_volume": 2.0,
             "target_surface": 40.0, "lambda_surface": 0.5, "seed_block": [8, 8, 0, 14, 14, 1]},
            {"type": 1, "target_volume": 80.0, "lambda_volume": 2.0,
             "target_surface": 40.0, "lambda_surface": 0.5, "seed_block": [24, 24, 0, 30, 30, 1]},
        ],
        "contact": [{"a": 1, "b": 1, "j": 10.0}],
    }
    state = {
        "cpm": {"_type": "process", "address": "local:CPMProcess",
                "config": {"spec": spec, "mcs_per_update": 10},
                "inputs": {"fates": ["fates"]},
                "outputs": {"volumes": ["volumes"], "types": ["types"], "positions": ["positions"],
                            "field_at_cell": ["field_at_cell"], "neighbor_secretory": ["neighbor_secretory"]}},
        "fates": {}, "volumes": [], "types": [], "positions": [],
        "field_at_cell": {}, "neighbor_secretory": {},
    }
    sim = Composite({'state': state}, core=core); sim.run(t)
    vols = [v for v in (sim.state.get('volumes') or []) if v < 400]  # drop Medium (bg)
    return f"ran {t} updates; cell volumes {sorted(round(v) for v in vols)} (target 80, relaxing from 36)"

# --- the 6 sourcing tasks ---
TASKS = [
  dict(name="cell-jostling", requires=["physics_2d","rigid_body","collision"],
       sourcing=dict(decision="reuse", modules=["viva-munk"], rationale="pymunk 2D rigid-body physics is exactly cell jostling"),
       run=lambda: run_munk(MC.biofilm_document)),
  dict(name="growth-and-push", requires=["growth","physics_2d"],
       sourcing=dict(decision="compose", modules=["growth-proc","viva-munk"], rationale="growth process + viva-munk physics"),
       run=lambda: run_munk(MC.glucose_growth_document)),
  dict(name="spatial-competition", requires=["spatial","dfba","diffusion"],
       sourcing=dict(decision="reuse", modules=["spatio-flux"], rationale="spatio-flux does spatial dFBA competition"),
       run=lambda: run_spatioflux("spatio_flux.composites.metabolism.community_dfba")),
  dict(name="shape-dynamics", requires=["cpm","cell_shape","morphology"],
       sourcing=dict(decision="reuse", modules=["viva-cpm"], rationale="viva-cpm is a Cellular Potts shape engine"),
       run=run_cpm),
  dict(name="novel-mechanism", requires=["quantum_signal","exotic_transport"],
       sourcing=dict(decision="build-new", modules=[], rationale="no catalogued module covers this"),
       run=None),
  dict(name="TRAP-wrong-reuse", requires=["physics_2d","spatial"],
       sourcing=dict(decision="reuse", modules=["viva-munk"], rationale="looks like physics"),
       run=None),  # viva-munk lacks 'spatial' -> audit should catch
]

print(f"{'task':22s} {'decision':10s} {'sourcing-gate':13s} source_fit reinv novel   real-run")
results = []
for t in TASKS:
    spec = {"name": t["name"], "requires": t["requires"], "sourcing": t["sourcing"]}
    rep = MS.build_sourcing_report(spec, CATALOG); gate = MS.sourcing_gate(rep)
    ax = {a["id"]: a["verdict"] for g in rep["groups"].values() for a in g["axes"]}
    run = "—"
    if t["run"]:
        try: run = t["run"]()
        except Exception as e: run = f"run err: {type(e).__name__}"
    print(f"{t['name']:22s} {t['sourcing']['decision']:10s} {gate:13s} {ax['source_fit']:10s} {ax['reinvention']:5s} {ax['novelty_justified']:6s} {run}")
    results.append(dict(task=t["name"], requires=t["requires"], sourcing=t["sourcing"],
                        gate=gate, axes=ax, real_run=run))

# --- machine-readable artifact: the audit results + the catalog it was graded against ---
import os
out = os.path.join(os.path.dirname(__file__), os.pardir, "workspace", "investigations",
                   "model-sourcing", "results.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w") as fh:
    json.dump(dict(schema="model_sourcing_results/v1", catalog=CATALOG,
                   loop_select_phase="SELECT" in L.STATES, results=results), fh, indent=2)
print(f"\nresults -> {os.path.relpath(out)}")
