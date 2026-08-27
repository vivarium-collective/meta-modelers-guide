"""Fig 7 · a cell's subsystems are a NESTED hierarchy of coupled processes.

The runnable fig07 composite (meta_modelers_guide.composites.fig07-runnable) wires six
ODE handlers over one place graph whose stores nest up to SIX levels deep (cytoplasm →
nucleus → chromosome → chromatin → nucleosome → DNA) WITHOUT flattening it. The handlers'
outputs feed each other's inputs, so running the composite makes the whole hierarchy
evolve as one coupled cell:

    transmembrane transport → cytoplasmic nutrients
    metabolism              → metabolites + energy
    transcription (deep DNA)→ RNA
    translation             → protein
    subunit assembly        → ribosome   (closes the loop back to translation)
    replication/repair      → holds DNA at its genome set point

This test asserts the CAUSAL claim the figure makes: the nested cascade actually
PROPAGATES — from a seeded environment, an observable rises at EACH level of the hierarchy
(transport, metabolism, transcription, translation, assembly), not just the first.

Mirrors tests/test_fig10_topology.py (run the composite via build_core, assert on the
emitted trajectory).
"""
from __future__ import annotations

import json
from pathlib import Path

from process_bigraph import Composite, gather_emitter_results

from meta_modelers_guide.core import build_core

COMPOSITE = (
    Path(__file__).resolve().parent.parent
    / "meta_modelers_guide" / "composites" / "fig07-runnable.composite.json"
)

# The two deepest place-graph paths the figure nests: the genome six levels down,
# and the ribosome pool four levels down. Processes act on these WITHOUT the place
# graph being flattened.
DNA_PATH = ("cytoplasm", "nucleus", "chromosome", "chromatin", "nucleosome", "DNA")
RIBOSOME_PATH = ("cytoplasm", "organelles", "ribosomal_complex", "ribosome")


def _dig(tree, path):
    node = tree
    for key in path:
        node = node[key]
    return node


def _run():
    """Run the composite and return (spec, final_state_tree, emitter_rows)."""
    spec = json.loads(COMPOSITE.read_text())
    core = build_core()
    sim = Composite({"state": spec["state"]}, core=core)
    sim.run(spec["default_n_steps"])
    rows = gather_emitter_results(sim)[("emitter",)]
    return spec, sim.state, rows


def _trajectory():
    spec, _state, rows = _run()
    return spec, rows


def _series(rows, key):
    return [float(r[key]) for r in rows]


def test_composite_runs_default_n_steps_and_emits():
    spec, rows = _trajectory()
    # default_n_steps ticks + the initial emit ⇒ n+1 frames; the run completes clean.
    assert len(rows) == spec["default_n_steps"] + 1
    assert _series(rows, "time")[-1] == float(spec["default_n_steps"])


def test_transport_fills_the_cytoplasmic_nutrient_pool():
    """Level 1 — the membrane transporter imports nutrients into the cytoplasm."""
    _, rows = _trajectory()
    nut = _series(rows, "nutrients")
    assert nut[0] == 0.0            # product starts empty
    assert nut[-1] > 1.0           # imported over the run
    for a, b in zip(nut, nut[1:]):
        assert b >= a - 1e-9       # nutrient supply is on ⇒ monotonic fill


def test_metabolism_produces_metabolites_and_energy():
    """Level 2 — metabolism converts the imported nutrients into metabolites + energy."""
    _, rows = _trajectory()
    met = _series(rows, "metabolites")
    ene = _series(rows, "energy")
    assert met[-1] > met[0] + 1.0
    assert ene[-1] > ene[0] + 1.0


def test_central_dogma_transcription_and_translation_rise():
    """Levels 3–4 — transcription of the DEEP DNA makes RNA, which translation turns
    into protein. Both downstream products rise, proving the cascade reaches the
    deeply-nested gene-expression subsystem."""
    _, rows = _trajectory()
    rna = _series(rows, "rna")
    prot = _series(rows, "proteins")
    assert rna[0] == 0.0 and rna[-1] > 1e-3       # transcription output rises
    assert prot[0] == 0.0 and prot[-1] > 1e-3     # translation output rises
    # protein cannot lead RNA: translation is downstream of transcription.
    assert rna[-1] > prot[-1]


def test_assembly_builds_ribosomes_closing_the_loop():
    """Level 5 — subunit assembly consumes protein + subunits to grow the ribosome pool,
    the downstream observable that closes the loop back to translation."""
    _, rows = _trajectory()
    rib = _series(rows, "ribosome")
    assert rib[-1] > rib[0] + 1e-3               # ribosome pool grows past its bootstrap seed


def test_cascade_propagates_across_multiple_levels():
    """The whole point: a non-trivial change occurs at MULTIPLE levels of the nested
    hierarchy in one coupled run (not just at the input)."""
    _, rows = _trajectory()
    levels = {
        "nutrients": _series(rows, "nutrients"),      # transport
        "metabolites": _series(rows, "metabolites"),  # metabolism
        "rna": _series(rows, "rna"),                  # transcription (deep DNA)
        "proteins": _series(rows, "proteins"),        # translation
        "ribosome": _series(rows, "ribosome"),        # assembly
    }
    changed = [name for name, s in levels.items() if abs(s[-1] - s[0]) > 1e-3]
    assert set(changed) == set(levels), f"only these levels changed: {changed}"


def test_place_graph_containment_is_preserved_as_dynamics_run():
    """The figure's core claim: processes act on stores buried deep in the place
    graph WITHOUT flattening it. After a full run the nested containment is still
    intact — the genome six levels down, the ribosome pool four levels down — and
    the deep stores still sit as nested dicts inside their parents, alongside their
    untouched siblings (histone next to DNA)."""
    _spec, state, _rows = _run()
    # Every intermediate container along the deepest path is still a nested dict —
    # the six-level chain was never collapsed into a flat key.
    for depth in range(1, len(DNA_PATH)):
        node = _dig(state, DNA_PATH[:depth])
        assert isinstance(node, dict), f"level {depth} ({DNA_PATH[depth-1]}) was flattened"
    # The leaf stores are reachable at full depth and hold scalar quantities.
    dna = _dig(state, DNA_PATH)
    ribosome = _dig(state, RIBOSOME_PATH)
    assert isinstance(dna, float)
    assert isinstance(ribosome, float)
    # A sibling store one level up from DNA is still nested alongside it (the
    # nucleosome contains BOTH DNA and histone) — containment, not just reachability.
    nucleosome = _dig(state, DNA_PATH[:-1])
    assert "DNA" in nucleosome and "histone" in nucleosome


def test_process_at_a_deep_level_moves_quantity_in_its_nested_store():
    """Anchor: a process acting at ONE nesting level moves quantity in a nested
    store. Subunit assembly writes the ribosome pool four levels deep — it grows
    past its bootstrap seed. Replication/repair holds the genome six levels deep at
    its set point — a homeostatic hold, not drift. Both are read from the final
    place graph at full depth, not from a flattened observable."""
    spec, state, rows = _run()
    ribosome_series = _series(rows, "ribosome")
    # Deep-nested (4 levels) store the assembly process drives: grows over the run
    # AND the final place-graph value matches the last emitted frame (same store).
    assert ribosome_series[-1] > ribosome_series[0]
    assert _dig(state, RIBOSOME_PATH) == ribosome_series[-1]
    # Deep-nested (6 levels) genome the replication/repair process holds at its set
    # point (dna_init == 1.0): conserved within tolerance, never runs away.
    dna_series = _series(rows, "dna")
    set_point = float(spec["state"]["replication_and_repair"]["config"]["dna_init"])
    assert all(abs(d - set_point) < 1e-6 for d in dna_series)
    assert _dig(state, DNA_PATH) == dna_series[-1]
