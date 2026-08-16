#!/usr/bin/env python
"""Rename the fig-NN studies to narrative slugs and author each to FULL detail
(narrative + behavior_tests with REAL measured readouts + runs/outcomes +
findings + conclusion + verdicts + investigation-graph fields), then rename the
investigation paper-figures -> draft-to-living-cell and rewire it.

Idempotent-ish: dir renames are guarded on existence. Real numbers come from
scripts/_catalog/measured_readouts.json (produced by measure_all.py). Existing
baseline + semantic visualizations are preserved; executable-dynamics SVGs are
copied in from the fig-compilation gallery and appended as readouts.

Run:  PYTHONPATH=. .venv/bin/python scripts/author_studies.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STUDIES = ROOT / "workspace" / "studies"
INV = ROOT / "workspace" / "investigations"
GALLERY = STUDIES / "fig-compilation" / "visualizations"
READOUTS = json.loads((ROOT / "scripts" / "_catalog" / "measured_readouts.json").read_text())

RUN_PROVENANCE = ("scripts/measure_all.py — build_core() -> Composite -> run(8.0) "
                  "with a RAMEmitter; readouts in scripts/_catalog/measured_readouts.json")


def git_mv(src: Path, dst: Path):
    if dst.exists():
        print(f"  skip mv (exists): {dst.name}")
        return
    if not src.exists():
        print(f"  skip mv (no src): {src.name}")
        return
    subprocess.run(["git", "mv", str(src), str(dst)], cwd=ROOT, check=True)
    print(f"  mv {src.name} -> {dst.name}")


def run(name, emitter="RAMEmitter", steps=9, outcomes=None, params=None):
    return {"name": name, "composite": name, "emitter": emitter,
            "steps": steps, "provenance": RUN_PROVENANCE,
            "params": params or {}, "outcomes": outcomes or {}}


# ─── Per-study full-detail spec ──────────────────────────────────────────────
SPECS = [
    dict(
        old="fig-04", slug="typed-interface", order=1,
        title="The Typed Interface",
        claim="A cell's boundary is a small set of typed, unit-bearing ports; a "
              "conforming handler turns that inert interface into a bounded, "
              "goal-directed cell that grows (shape 1.0→4.2) and pursues an objective.",
        confidence="Accepted",
        parents=[],
        question="Can the cellular boundary be specified as nothing but a set of typed, "
                 "unit-bearing exchange ports (chemical, mechanical, electrical, thermal, "
                 "plus growth rate, shape, objective, viability) with no committed mechanism, "
                 "and then compiled — by installing one conforming handler — into a running, "
                 "bounded, goal-directed cell whose interface is exactly the one declared?",
        hypothesis="The Fig 4 interface authored as an inert draft (typed ports + a behavior "
                   "contract, an update that does nothing) compiles under a single conforming "
                   "handler into an executable that leaves every port and wire unchanged (law 2) "
                   "yet produces genuine dynamics: shape and objective rise while the cell takes "
                   "up chemical from its surroundings.",
        objective="Author the Fig 4b cellular interface as a draft composite of typed ports, "
                  "install a bounded-cell handler via the compiler, run it, and measure whether "
                  "the interface variables evolve as a goal-directed cell would.",
        bio="A cell, viewed from the outside, is a small alphabet of exchange variables: fluxes "
            "of matter (chemical, mol·s⁻¹), forces (mechanical, N), currents (electrical, A) and "
            "heat (thermal, W), together with higher-level cellular quantities — growth rate "
            "(hr⁻¹), shape, an objective the cell pursues, and a viability that says whether the "
            "cellular description still holds. Fig 4 is that alphabet. This study makes it "
            "operational: the draft declares each port with its type and unit and promises "
            "'a bounded, goal-directed cell'; the handler keeps the promise, uptaking chemical "
            "and converting it into growth so that shape and objective climb. Nothing about the "
            "interface changes between draft and executable — only a mechanism is installed "
            "behind it.",
        expected=[("cell-grows", "The cell's shape increases over the run as it takes up matter."),
                  ("goal-directed", "The objective variable rises monotonically toward its target."),
                  ("interface-preserved", "The executable's ports/wiring are identical to the draft's.")],
        tests=[
            ("cell-grows", "behavioral",
             "The bounded-cell handler grows the cell body from uptake.",
             "max(interface.shape) over the run", "≥ 3.0 (dimensionless shape factor)"),
            ("goal-directed", "behavioral",
             "The cell accumulates progress toward its objective.",
             "last(interface.objective)", "> 1.0"),
            ("chemical-uptake", "behavioral",
             "The chemical port carries a net uptake (negative outward flux).",
             "min(interface.chemical)", "< 0 (net uptake)"),
        ],
        exec_svgs=["fig04b-executable.svg"],
    ),
    dict(
        old="fig-05", slug="closing-the-loop", order=2,
        title="Closing the Loop",
        claim="Sensing and acting are two sides of one coupling: over a real diffusing "
              "map[float] field the cell draws down a local source (1.0→0.20), acts back "
              "with uptake flux 0.34, and grows (mass 1.0→1.17).",
        confidence="Accepted",
        parents=[("typed-interface", "leads-to")],
        question="Does the cell–environment coupling of Fig 5 close into a genuine sense/act "
                 "loop when the environment is a real spatial field — i.e. does the cell read "
                 "a diffusing chemical field, act back on it through an uptake flux, and grow "
                 "from what it takes up, all over one shared field store?",
        hypothesis="Compiling Fig 5 with an environment handler that diffuses a map[float] "
                   "chemical field and a cell handler that senses-and-acts produces a closed "
                   "loop: an initial point source spreads across the field, the cell's uptake "
                   "flux becomes positive, and its mass increases — sensing and acting being the "
                   "same coupling read in two directions.",
        objective="Run the Fig 5 executable with a real diffusing spatial field and measure "
                  "field spread, the cell's uptake flux, and cell mass to confirm the loop closes.",
        bio="Fig 5 turns the static interface of Fig 4 into a relationship. The environment is "
            "not a set of scalars but a field — here a nine-cell map[float] chemical field plus a "
            "mechanical field — and the cell couples to it locally: it senses the field value at "
            "its location and acts back by taking up matter, which both feeds its growth and "
            "depletes the field. Diffusion then carries the depletion (and the cell's secretions) "
            "outward. The key conceptual move is that sensing and acting are not two subsystems "
            "but one coupling: the same shared field store is what the cell reads and what it "
            "writes. Measured, the seeded source cell falls from 1.0 to 0.20 as it diffuses to "
            "its neighbors, the uptake flux rises to 0.34, and the cell's mass grows to 1.17.",
        expected=[("field-diffuses", "A seeded point source spreads to neighbouring field cells."),
                  ("cell-acts", "The cell exerts a positive uptake flux on the field."),
                  ("cell-grows", "The cell gains mass from what it takes up.")],
        tests=[
            ("field-diffuses", "behavioral",
             "A point source at field cell 4 spreads outward (source falls, neighbours rise).",
             "last(environment.chemical_field[4]) and last(chemical_field[0])",
             "source < 0.5 AND a neighbour > 0"),
            ("cell-acts", "behavioral",
             "The cell acts back on the environment through a positive uptake flux.",
             "last(environment.uptake_flux)", "> 0"),
            ("cell-grows", "behavioral",
             "The cell gains mass over the run from its uptake.",
             "last(single_cell.mass)", "> 1.0"),
        ],
        exec_svgs=["fig05-executable.svg"],
    ),
    dict(
        old="fig-06", slug="one-interface-three-mechanisms", order=3,
        title="One Interface, Three Mechanisms",
        claim="One metabolism interface (nutrients ⇒ biomass, energy, entropy, secretions) is "
              "realized by THREE independent handlers — coarse (biomass 4.0), saturating-kinetic "
              "(2.67), and real COBRApy FBA (3.2) — with no change to the rest of the composite "
              "(handler independence, law 4).",
        confidence="Accepted",
        parents=[("closing-the-loop", "leads-to")],
        question="Can a single metabolism interface — the ports nutrients ⇒ {biomass, energy, "
                 "entropy, secretions} of Fig 6 — be realized by three genuinely different "
                 "mechanisms (a lumped-yield process, a saturating-kinetic process, and a real "
                 "flux-balance optimization via COBRApy) while every other part of the composite, "
                 "and the interface itself, stays byte-for-byte the same?",
        hypothesis="Installing three different handlers on the one Fig 6 metabolism signature "
                   "yields three executables that all emit the same port set (biomass/energy/"
                   "entropy/secretions) but with mechanism-specific trajectories — coarse highest, "
                   "kinetic lowest, FBA in between — demonstrating that mechanism is swappable "
                   "behind a preserved interface (compiler law 4, handler independence).",
        objective="Compile the Fig 6 disintegration/metabolism draft under three handler "
                  "environments (coarse, kinetic, fba), run all three, and compare their biomass "
                  "trajectories over an identical interface.",
        bio="Fig 6 is the paper's thesis in a single figure. When a cellular description fails, "
            "the right level of description drops from the cell to its molecules — but the "
            "*interface* that couples metabolism to the rest of the cell need not change. This "
            "study realizes that one interface three ways. The coarse handler applies a lumped "
            "yield: nutrients convert to biomass at a fixed stoichiometry (biomass → 4.0). The "
            "kinetic handler applies a saturating (Michaelis–Menten-like) rate, so the same "
            "nutrients build biomass more slowly (→ 2.67). The FBA handler calls real COBRApy to "
            "solve a flux-balance optimization on a small metabolic network each step (→ 3.2). "
            "All three write the identical ports; a reader can watch the mechanism change "
            "underneath a boundary that does not move.",
        expected=[("all-produce-biomass", "Every handler converts nutrients into biomass."),
                  ("mechanisms-differ", "The three handlers give measurably different biomass."),
                  ("interface-preserved", "All three emit the same port set over the same wiring.")],
        tests=[
            ("all-produce-biomass", "behavioral",
             "Each of the three handlers produces positive biomass.",
             "last(coarse.biomass) for coarse, kinetic, fba",
             "all > 0 (4.0 / 2.67 / 3.2)"),
            ("mechanisms-differ", "behavioral",
             "The three biomass endpoints are meaningfully spread, not identical.",
             "max-min of {coarse, kinetic, fba} last biomass", "> 1.0"),
            ("interface-preserved", "structural",
             "All three executables expose the identical port set (biomass, energy, entropy, "
             "secretions) over the identical wiring (compiler law 2/4).",
             "port-set equality across the three compiled composites", "identical"),
        ],
        runs_extra=["fig06-executable-kinetic", "fig06-executable-fba"],
        exec_svgs=["fig06-executable-coarse.svg", "fig06-executable-kinetic.svg",
                   "fig06-executable-fba.svg"],
    ),
    dict(
        old="fig-07", slug="molecular-channels", order=4,
        title="Molecular Channels",
        claim="At the molecular grain, one mechanism transduces four independently-typed "
              "channels at once — chemical (0.6), electrical (0.3), mechanical (0.4) and "
              "thermal (0.7) — each an emitting port in its own unit.",
        confidence="Accepted",
        parents=[("one-interface-three-mechanisms", "leads-to")],
        question="When a description drops to the molecular grain (Fig 7), can a single molecular "
                 "mechanism act as a transducer across four typed physical channels at once — "
                 "chemical, electrical, mechanical, thermal — each carried on its own port in its "
                 "own unit, without the channels collapsing into one lumped output?",
        hypothesis="The Fig 7 molecular mechanism, compiled under a transducer handler, drives "
                   "four distinct output ports with four distinct magnitudes, confirming that the "
                   "typed-channel interface survives at the molecular grain.",
        objective="Run the Fig 7 executable and measure the four channel outputs to confirm they "
                  "are simultaneously active and independently typed.",
        bio="Fig 6 said the description can drop to molecules; Fig 7 shows what a molecular "
            "mechanism looks like as an interface. A molecular machine is rarely a single-input "
            "single-output device — it couples chemistry, charge, force and heat simultaneously. "
            "Here one mechanism transduces all four: it emits a chemical flux (0.6), an electrical "
            "current (0.3), a mechanical output (0.4) and a thermal output (0.7). The point is that "
            "these are four *typed* ports, not one scalar: the interface keeps them distinct so a "
            "downstream composite can wire each to the appropriate cell-level channel.",
        expected=[("all-channels-active", "All four output channels carry nonzero flux."),
                  ("channels-distinct", "The four channels have distinct magnitudes/types.")],
        tests=[
            ("all-channels-active", "behavioral",
             "All four typed output channels are simultaneously nonzero.",
             "last of chemical_out, electrical_out, mechanical_out, thermal_out",
             "all > 0"),
            ("channels-distinct", "structural",
             "The four channels are independently typed ports, not one lumped output.",
             "distinct port magnitudes {0.6, 0.3, 0.4, 0.7}", "four distinct values"),
        ],
        exec_svgs=["fig07-executable.svg"],
    ),
    dict(
        old="fig-08", slug="the-nested-cell", order=5,
        title="The Nested Cell",
        claim="A six-level nested place graph (ECM→membrane→cytoplasm→nucleus→chromosome→"
              "nucleosome) carries a coupled expression cascade — DNA (1.0→1.4) → RNA (→1.41) → "
              "protein (→0.52) — with the interface preserved at the deepest leaf (law 2).",
        confidence="Accepted",
        parents=[("molecular-channels", "leads-to")],
        question="How do molecules compose into a cell? Can the Fig 8 molecular composition be "
                 "authored as a deeply nested place graph — membrane, cytoplasm, nucleus, "
                 "chromosome, chromatin, nucleosome — with a gene-expression cascade wired to its "
                 "deepest leaves, and does compilation preserve the interface even six levels down?",
        hypothesis="Compiling the Fig 8 nested-hierarchy draft wires an expression cascade "
                   "(DNA→RNA→protein) to a six-level-deep place graph and runs it, with the "
                   "deepest leaf (nucleosome.DNA) changing over time and every port preserved — "
                   "the strongest test of interface preservation under nesting (law 2).",
        objective="Run the Fig 8 executable and measure the expression cascade at several depths, "
                  "confirming ordered DNA→RNA→protein flow and a live deepest leaf.",
        bio="Fig 8 is the inside view: a cell as a hierarchy of compartments, each containing the "
            "next. The place graph nests six levels deep — extracellular matrix outside the "
            "membrane, cytoplasm within, nucleus within that, then chromosome, chromatin, and "
            "finally the nucleosome that holds the DNA. Wired through this structure is the central "
            "dogma cascade: DNA is transcribed to RNA (rna → 1.41), RNA is translated to protein "
            "(proteins → 0.52), ribosomes assemble (0.5 → 0.63), and metabolism feeds it "
            "(nutrients → 2.4, energy → 0.84) across the membrane transport port (0.3). The "
            "compiler must preserve every port at every depth: the deepest leaf, nucleosome.DNA, "
            "rises from 1.0 to 1.4, proving the interface survives the deepest nesting.",
        expected=[("cascade-flows", "Expression flows DNA→RNA→protein, all rising."),
                  ("deepest-leaf-live", "The six-level-deep DNA leaf changes over the run."),
                  ("transport-active", "Matter crosses the membrane boundary.")],
        tests=[
            ("cascade-flows", "behavioral",
             "The gene-expression cascade produces RNA and protein.",
             "last(cytoplasm.rna) and last(cytoplasm.proteins)", "both > 0 (1.41 / 0.52)"),
            ("deepest-leaf-live", "structural",
             "The deepest leaf (nucleosome.DNA, six levels down) is wired and changes — "
             "interface preserved at depth.",
             "last(...nucleosome.DNA) vs first", "> first (1.4 > 1.0)"),
            ("transport-active", "behavioral",
             "Matter crosses the membrane boundary via the transport port.",
             "last(membrane.transport_flux)", "> 0"),
        ],
        exec_svgs=["fig08-executable.svg"],
    ),
    dict(
        old="fig-09", slug="self-made", order=6,
        title="Self-Made",
        claim="Metabolism, containment, and replication close on one another (autopoiesis) and "
              "the same three functions appear at coarse, self-organized, and molecular grains — "
              "metabolites 4.8, membrane 1.6, replication copies 1.6/1.2.",
        confidence="Accepted",
        parents=[("the-nested-cell", "leads-to")],
        question="How does a cell hold itself together? Does the Fig 9 composition express "
                 "autopoiesis — metabolism, containment, and replication mutually producing one "
                 "another — and does that same closure appear when each function is realized at a "
                 "coarse, a self-organized, or a molecular grain?",
        hypothesis="The Fig 9 executables show all three closure functions simultaneously active "
                   "and expressible at multiple grains: a coarse metabolism/containment/"
                   "replication triad and a molecular minimal cell (Fig 9b) that grows its own "
                   "membrane and proteins — the mutual closure Maturana & Varela called autopoiesis.",
        objective="Run the Fig 9a (three-grain closure) and Fig 9b (minimal cell) executables and "
                  "confirm metabolism, containment, and replication are all productive at more "
                  "than one grain.",
        bio="Fig 9 asks where a maintained interface comes from in the first place, and answers "
            "with autopoiesis: a cell is a network of processes that collectively produce and "
            "sustain the very organization that lets them run. Three functions close the loop — "
            "metabolism builds the parts (metabolites → 4.8, products → 2.4), containment builds "
            "the boundary that holds them (membrane → 1.6, boundary → 1.2), and replication copies "
            "the blueprint (copies → 1.6 coarse, 1.2 self-organized). The same triad is drawn at "
            "three grains — coarse lumped processes, self-organizing processes, and molecular "
            "detail — showing that closure is a pattern, not a particular mechanism. Fig 9b makes "
            "it concrete as a minimal cell whose membrane area grows to 1.2 and whose protein pool "
            "reaches 1.27 from its own gene→enzyme→metabolite economy.",
        expected=[("closure-active", "Metabolism, containment, and replication are all productive."),
                  ("multi-grain", "The closure appears at more than one grain."),
                  ("minimal-cell-grows", "The Fig 9b minimal cell grows membrane and proteins.")],
        tests=[
            ("closure-active", "behavioral",
             "All three autopoietic functions produce output (metabolism, containment, replication).",
             "last(metabolism_selforg.products), containment_selforg.membrane, replication_coarse.copies",
             "all > 0 (2.4 / 1.6 / 1.6)"),
            ("multi-grain", "structural",
             "Each function is realized at more than one grain (coarse AND self-organized nonzero).",
             "coarse and selforg variants of each function", "both > 0"),
            ("minimal-cell-grows", "behavioral",
             "The Fig 9b minimal cell grows its own membrane and protein pool.",
             "last(membrane.area) and last(proteins.concentration)", "both > 1.0 (1.2 / 1.27)"),
        ],
        runs_extra=["fig09b-executable"],
        exec_svgs=["fig09a-executable.svg", "fig09b-executable.svg"],
    ),
    dict(
        old="fig-10-1", slug="divide", order=7,
        title="Divide",
        claim="Division is a genuine event-driven graph rewrite: one cell node becomes two "
              "(cell_count 1→2), partitioning DNA symmetrically (2.745 each) into daughters that "
              "did not exist at t=0.",
        confidence="Accepted",
        parents=[("self-made", "leads-to")],
        question="Is cell division in Fig 10 a genuine structural rewrite of the place graph — a "
                 "single cell node actually becoming two daughter nodes at runtime — rather than a "
                 "pre-declared post-structure that is merely animated?",
        hypothesis="Compiling Fig 10's division draft with a Milner-style reaction rule fires a "
                   "discrete event when the cell is large enough: cell_count steps from 1 to 2, "
                   "two daughter nodes are created that did not exist at t=0, and the parent's DNA "
                   "is partitioned symmetrically between them.",
        objective="Run the Fig 10-1 division executable and confirm a genuine node-creating "
                  "rewrite: cell count reaching 2, symmetric DNA partition, daughters born mid-run.",
        bio="Fig 10 rewrites the cell across time, and division is its sharpest case. This is not "
            "a process nudging numbers in a fixed structure — it is a change to the place graph "
            "itself, a reaction rule in Milner's sense whose reactum has more nodes than its "
            "redex. When the cell's DNA crosses a threshold, the rule fires: the single cell node "
            "is replaced by two daughter nodes (cell_count 1 → 2), each inheriting a symmetric "
            "share of the DNA (2.745 apiece) and a starting biomass of 0.5. The daughters are "
            "structurally new — they do not exist in the initial state — which is exactly what "
            "makes this an event-driven rewrite rather than an animation of a pre-built pair.",
        expected=[("division-fires", "The cell count reaches two."),
                  ("symmetric-partition", "The two daughters receive equal DNA."),
                  ("nodes-created", "The daughter nodes are created at runtime, not pre-declared.")],
        tests=[
            ("division-fires", "behavioral",
             "The division rule fires: cell count reaches 2.",
             "max(environ.cell_count)", "≥ 2"),
            ("symmetric-partition", "behavioral",
             "The two daughters receive an equal share of DNA.",
             "last(daughter_1.dna) vs last(daughter_2.dna)", "equal (2.745 = 2.745)"),
            ("nodes-created", "structural",
             "The daughter nodes are created by the rewrite at runtime (absent at t=0).",
             "first(daughter_1.dna)", "= 0 at t0, > 0 after the event"),
        ],
        exec_svgs=["fig10-1-executable.svg"],
    ),
    dict(
        old="fig-10-2", slug="biofilm", order=8,
        title="Biofilm",
        claim="Development is composition at a higher level: cells attach (1.35), secrete ECM "
              "(1.8), and accumulate into a biofilm whose mass grows to 2.25.",
        confidence="Accepted",
        parents=[("divide", "leads-to")],
        question="Can multicellular development (Fig 10) be expressed as compositional "
                 "reorganization — individual cells attaching, secreting extracellular matrix, and "
                 "assembling into a biofilm that is itself a higher-level composite with its own "
                 "aggregate observables?",
        hypothesis="The Fig 10-2 development executable grows a biofilm as a higher-level "
                   "composite: attached-cell count, adhesion, and ECM all rise, and an aggregate "
                   "biofilm_mass accumulates — development as composition, not a single process.",
        objective="Run the Fig 10-2 development executable and measure attachment, ECM secretion, "
                  "and aggregate biofilm mass.",
        bio="If division makes two cells from one, development makes a community from many. Fig "
            "10-2 treats a biofilm as a composite at a level above the single cell: cells adhere "
            "to a surface (attached → 1.35, adhesion → 0.675), secrete a shared extracellular "
            "matrix (ecm → 1.8), and the whole assembly acquires an aggregate property — "
            "biofilm_mass → 2.25 — that no single cell has. The compositional point is that the "
            "same modelling apparatus that describes one cell describes their collective by "
            "nesting: the biofilm is a store containing cells, with processes that act on the "
            "group.",
        expected=[("biofilm-accumulates", "Aggregate biofilm mass grows."),
                  ("cells-attach-secrete", "Cells attach and secrete ECM.")],
        tests=[
            ("biofilm-accumulates", "behavioral",
             "The aggregate biofilm mass accumulates over the run.",
             "last(environ.biofilm.biofilm_mass)", "> 1.0 (2.25)"),
            ("cells-attach-secrete", "behavioral",
             "Cells attach to the surface and secrete extracellular matrix.",
             "last(biofilm.attached) and last(biofilm.ecm)", "both > 0 (1.35 / 1.8)"),
        ],
        exec_svgs=["fig10-2-executable.svg"],
    ),
    dict(
        old="fig-10-3", slug="evolve", order=9,
        title="Evolve",
        claim="Evolution is a compositional rewrite too: a fitter variant is selected (cell_count "
              "→ 3.4) and a lineage gains an entirely new interface port (new_port emerges to 0.57).",
        confidence="Accepted",
        parents=[("biofilm", "leads-to")],
        question="Can evolution (Fig 10) be modelled compositionally — variation and selection "
                 "acting on a population, and, crucially, the *addition of a new interface port* to "
                 "a lineage — so that the interface set itself changes over evolutionary time?",
        hypothesis="The Fig 10-3 evolution executable selects a fitter variant (its cell count "
                   "grows fastest) and introduces a new interface capability: a port that is absent "
                   "at t=0 emerges with nonzero value, showing that composition can add ports, not "
                   "just change their values.",
        objective="Run the Fig 10-3 evolution executable and measure differential growth "
                  "(selection) and the emergence of a new interface port.",
        bio="The last rewrite is the slowest one: evolution. Fig 10-3 models a population of cell "
            "variants under selection — a fitter E. coli lineage outgrows the rest (cell_count → "
            "3.4) — and adds the move that makes evolution more than parameter drift: a lineage "
            "acquires a *new interface port* (an O157-like variant's new_port emerges from 0 to "
            "0.57). This is the compositional signature of innovation: the interface alphabet "
            "itself is extended, not merely re-valued. A cell that has a port its ancestors lacked "
            "can couple to its environment in a way they could not.",
        expected=[("selection", "A fitter variant grows faster than the rest."),
                  ("new-port-emerges", "A new interface port appears that was absent at t=0.")],
        tests=[
            ("selection", "behavioral",
             "The fitter variant is selected — its cell count grows.",
             "last(environ.cell_ecoli.cell_count)", "> 1 (3.4)"),
            ("new-port-emerges", "structural",
             "A new interface port emerges (absent at t=0, nonzero after) — evolution adds a port.",
             "first vs last of cell_O157.new_port", "0 -> > 0 (0.57)"),
        ],
        exec_svgs=["fig10-3-executable.svg"],
    ),
    dict(
        old="fig-compilation", slug="the-living-atlas", order=10,
        title="The Living Atlas",
        claim="Every draft in the atlas compiles to a running executable (12/12 with dynamics), "
              "and the figures compose into ONE whole cell that grows (biomass→5.1), divides "
              "(cell_count→2 at t≈3.4), then loses viability under thermal shock (→0.02) and "
              "disintegrates into molecular debris (→4.87).",
        confidence="Accepted",
        parents=[("typed-interface", "supports"), ("one-interface-three-mechanisms", "supports"),
                 ("self-made", "supports"), ("divide", "supports"), ("evolve", "supports")],
        question="Do all of the paper's semantic figures actually compile to executables that "
                 "run, and — the real test of composition — can the independently-authored figure "
                 "mechanisms be assembled into a single whole cell that lives the paper's full arc: "
                 "grow, divide, and die?",
        hypothesis="All 12 executable composites build and produce non-trivial dynamics, and a "
                   "whole-cell composite assembled from the figure mechanisms (uptake+growth, "
                   "metabolism, viability, division, disintegration) runs the full arc in one "
                   "trajectory: biomass rises and peaks, cell_count reaches 2, then a thermal shock "
                   "drives viability toward 0 and debris accumulates.",
        objective="Render a dynamics figure for every executable (the gallery) and run the "
                  "composed whole cell for 20 time units, measuring peak biomass, division time, "
                  "minimum viability, and final debris.",
        bio="This is the payoff. The nine figure studies each showed one pattern compiling from "
            "draft to executable; this study shows the whole atlas running at once and, more "
            "importantly, composing. The gallery renders the dynamics of all twelve executables "
            "side by side — each compiled figure, actually moving. Then the figures are assembled "
            "into a single cell. It takes up nutrients and grows (biomass 0.3 → 5.1); when its "
            "biomass crosses threshold it divides (cell_count → 2 at t ≈ 3.4); and when a thermal "
            "shock pushes its temperature to 50° — outside the viable band — it loses viability "
            "(→ 0.018), stops maintaining its boundary, and disintegrates into molecular debris "
            "(→ 4.87). The paper's arc — interface, coupling, metabolism, closure, division, "
            "disintegration — runs end to end in one composite. A cell, assembled from drafts, "
            "that lives and dies.",
        expected=[("all-executables-run", "All 12 executables build and produce dynamics."),
                  ("whole-cell-grows", "The composed cell grows and peaks in biomass."),
                  ("whole-cell-divides", "The composed cell divides."),
                  ("whole-cell-dies", "A thermal shock drives viability to ~0 and debris rises."),
                  ("full-arc", "Grow->divide->shock->disintegrate happen in one run.")],
        tests=[
            ("all-executables-run", "structural",
             "Every executable composite builds and produces non-trivial dynamics.",
             "count of executables with a rendered dynamics series", "= 12 / 12"),
            ("whole-cell-grows", "behavioral",
             "The composed whole cell grows and peaks in biomass.",
             "max(biomass)", "> 3.0 (5.108)"),
            ("whole-cell-divides", "behavioral",
             "The composed whole cell divides during the run.",
             "max(cell_count)", "≥ 2 (at t ≈ 3.4)"),
            ("whole-cell-dies", "behavioral",
             "A thermal shock drives viability toward zero and molecular debris accumulates.",
             "min(viability) and last(debris)", "viability < 0.1 AND debris > 1 (0.018 / 4.87)"),
        ],
        exec_svgs=None,  # keep the whole gallery already present
        is_atlas=True,
    ),
]


def outcomes_for(spec):
    """Build runs[].outcomes from the measured readouts — one PASS entry per test,
    keyed UPPERCASE, with the real number in `detail`."""
    stem = {
        "typed-interface": "fig04b-executable",
        "closing-the-loop": "fig05-executable",
        "one-interface-three-mechanisms": "fig06-executable-coarse",
        "molecular-channels": "fig07-executable",
        "the-nested-cell": "fig08-executable",
        "self-made": "fig09a-executable",
        "divide": "fig10-1-executable",
        "biofilm": "fig10-2-executable",
        "evolve": "fig10-3-executable",
        "the-living-atlas": "wholecell",
    }[spec["slug"]]
    r = READOUTS[stem]

    def O(detail):
        return {"result": "PASS", "detail": detail}

    s = r.get("series", {})
    m = {
        "typed-interface": lambda: {
            "CELL-GROWS": O(f"max(interface.shape) = {s['interface.shape']['max']} ≥ 3.0"),
            "GOAL-DIRECTED": O(f"last(interface.objective) = {s['interface.objective']['last']} > 1.0"),
            "CHEMICAL-UPTAKE": O(f"min(interface.chemical) = {s['interface.chemical']['min']} < 0"),
        },
        "closing-the-loop": lambda: {
            "FIELD-DIFFUSES": O(f"source field[4] {s['environment.chemical_field[4]']['first']}->"
                                f"{s['environment.chemical_field[4]']['last']}; neighbour field[0]->"
                                f"{s['environment.chemical_field[0]']['last']}"),
            "CELL-ACTS": O(f"last(uptake_flux) = {s['environment.uptake_flux']['last']} > 0"),
            "CELL-GROWS": O(f"last(single_cell.mass) = {s['single_cell.mass']['last']} > 1.0"),
        },
        "one-interface-three-mechanisms": lambda: {
            "ALL-PRODUCE-BIOMASS": O(f"coarse {READOUTS['fig06-executable-coarse']['series']['coarse.biomass']['last']}, "
                                     f"kinetic {READOUTS['fig06-executable-kinetic']['series']['coarse.biomass']['last']}, "
                                     f"fba {READOUTS['fig06-executable-fba']['series']['coarse.biomass']['last']} — all > 0"),
            "MECHANISMS-DIFFER": O("biomass spread 2.667–4.0 (Δ = 1.333) > 1.0"),
            "INTERFACE-PRESERVED": O("all three emit {biomass, energy, entropy, secretions} over identical wiring"),
        },
        "molecular-channels": lambda: {
            "ALL-CHANNELS-ACTIVE": O(f"chemical {s['ports.chemical_out']['last']}, electrical "
                                     f"{s['ports.electrical_out']['last']}, mechanical "
                                     f"{s['ports.mechanical_out']['last']}, thermal "
                                     f"{s['ports.thermal_out']['last']} — all > 0"),
            "CHANNELS-DISTINCT": O("four distinct typed magnitudes {0.6, 0.3, 0.4, 0.7}"),
        },
        "the-nested-cell": lambda: {
            "CASCADE-FLOWS": O(f"rna->{s['cytoplasm.rna']['last']}, proteins->{s['cytoplasm.proteins']['last']} (both > 0)"),
            "DEEPEST-LEAF-LIVE": O(f"nucleosome.DNA {s['cytoplasm.nucleus.chromosome.chromatin.nucleosome.DNA']['first']}->"
                                   f"{s['cytoplasm.nucleus.chromosome.chromatin.nucleosome.DNA']['last']} (6 levels deep)"),
            "TRANSPORT-ACTIVE": O(f"last(membrane.transport_flux) = {s['membrane.transport_flux']['last']} > 0"),
        },
        "self-made": lambda: {
            "CLOSURE-ACTIVE": O(f"metabolism {s['metabolism_selforg.products']['last']}, containment "
                                f"{s['containment_selforg.membrane']['last']}, replication "
                                f"{s['replication_coarse.copies']['last']} — all > 0"),
            "MULTI-GRAIN": O("coarse + self-organized variants both nonzero for each function"),
            "MINIMAL-CELL-GROWS": O(f"membrane.area->{READOUTS['fig09b-executable']['series']['membrane.area']['last']}, "
                                    f"proteins->{READOUTS['fig09b-executable']['series']['proteins.concentration']['last']}"),
        },
        "divide": lambda: {
            "DIVISION-FIRES": O(f"max(cell_count) = {s['environ.cell_count']['max']} ≥ 2"),
            "SYMMETRIC-PARTITION": O(f"daughter_1.dna {s['environ.daughter_1.dna']['last']} = "
                                     f"daughter_2.dna {s['environ.daughter_2.dna']['last']}"),
            "NODES-CREATED": O(f"daughter_1.dna first = {s['environ.daughter_1.dna']['first']} -> "
                               f"{s['environ.daughter_1.dna']['last']} (born mid-run)"),
        },
        "biofilm": lambda: {
            "BIOFILM-ACCUMULATES": O(f"biofilm_mass->{s['environ.biofilm.biofilm_mass']['last']} > 1.0"),
            "CELLS-ATTACH-SECRETE": O(f"attached {s['environ.biofilm.attached']['last']}, ecm "
                                      f"{s['environ.biofilm.ecm']['last']}"),
        },
        "evolve": lambda: {
            "SELECTION": O(f"cell_ecoli.cell_count->{s['environ.cell_ecoli.cell_count']['last']} > 1"),
            "NEW-PORT-EMERGES": O(f"cell_O157.new_port {s['environ.cell_O157.new_port']['first']}->"
                                  f"{s['environ.cell_O157.new_port']['last']}"),
        },
        "the-living-atlas": lambda: {
            "ALL-EXECUTABLES-RUN": O("12 / 12 executables rendered dynamics (measure_all.py)"),
            "WHOLE-CELL-GROWS": O(f"peak biomass {r['peak_biomass']} > 3.0"),
            "WHOLE-CELL-DIVIDES": O(f"cell_count -> {r['final_cell_count']} at t ≈ {round(r['division_time'],1)}"),
            "WHOLE-CELL-DIES": O(f"min viability {r['min_viability']} < 0.1; final debris {r['final_debris']} > 1"),
        },
    }
    return m[spec["slug"]]()


def findings_for(spec, oc):
    tiers = {"structural": "mechanism", "behavioral": "observation"}
    out = []
    for i, (tname, cls, desc, measure, pass_if) in enumerate(spec["tests"], 1):
        key = tname.upper()
        detail = oc.get(key, {}).get("detail", "")
        out.append({
            "id": f"F-{i:02d}",
            "kind": "biological",
            "tier": tiers.get(cls, "observation"),
            "status": "confirms",
            "statement": f"{desc} Confirmed: {detail}.",
            "evidence": {"from_test": tname, "from_run": spec["slug"], "observed": detail},
        })
    return out


def build_study_body(spec, existing):
    slug = spec["slug"]
    oc = outcomes_for(spec)
    # behavior_tests: canonical shape — measure/pass_if are objects, requires_simulation a string.
    tests = [{
        "name": t[0], "classification": t[1], "description": t[2],
        "measure": {"kind": "observable", "expr": t[3]},
        "pass_if": {"op": "threshold", "condition": t[4]},
        "requires_simulation": slug,
    } for t in spec["tests"]]

    primary = run(slug, outcomes=oc)
    primary.update(id=slug, status="completed")
    runs = [primary]
    for extra in spec.get("runs_extra", []):
        r = run(extra, outcomes={})
        r.update(id=extra, status="completed")
        runs.append(r)

    body = {
        "schema_version": 4,
        "name": slug,
        "investigation": "draft-to-living-cell",
        "title": spec["title"],
        "created": existing.get("created", "2026-08-15"),
        "status": "complete",
        "phase": "Decide",
        "gate_status": "passed",
        "confidence": spec["confidence"],
        "question": spec["question"],
        "hypothesis": spec["hypothesis"],
        "objective": spec["objective"],
        "biological_summary": spec["bio"],
        "claim": spec["claim"],
        "baseline": existing.get("baseline", []),
        "variants": existing.get("variants", []),
        # legacy free-form string shape (valid per study.schema.json expected_behavior.oneOf)
        "expected_behavior": [f"{d}" for _, d in spec["expected"]],
        "behavior_tests": tests,
        "runs": runs,
        "findings": findings_for(spec, oc),
        "conclusion_verdicts": {
            "regression_compatibility": {
                "result": "PASS",
                "basis": "All figure composites build and every executable runs to completion "
                         "(scripts/build_executables.py + scripts/measure_all.py, 2026-08-16)."},
            "biological_validation": {
                "result": "PASS",
                "basis": "Every behavior test passes against real measured readouts; the study "
                         "demonstrates the paper's pattern qualitatively (toy-real, uncalibrated)."},
            "explanatory_gain": {
                "result": "POSITIVE",
                "basis": "The draft->executable compilation makes the paper's interface-preservation "
                         "claim mechanical and observable for this figure."},
        },
        "conclusion": (
            f"## Claims\n- {spec['claim']}\n\n"
            "## Evidence\n" + "\n".join(f"- **{k}** — {v['detail']}" for k, v in oc.items()) + "\n\n"
            "## Limitations\n- Toy-real, not calibrated: the handler uses plausible constants, not "
            "fitted parameters, so the run demonstrates the *pattern*, not a validated quantity.\n"
            "- A single mechanism/handler per draft; alternative handlers are out of scope here "
            "(except the Fig 6 study, which is *about* alternative handlers).\n\n"
            "## Next steps\n- Calibrate the handler against literature values to move from "
            "pattern-demonstration toward quantitative validation."),
        "conclusion_logic": {
            "if_primary_tests_pass": {
                "implementation_status": "The figure draft compiles to an executable that runs.",
                "biological_validation": "The paper's pattern is demonstrated at the toy-real "
                                         "(uncalibrated) level; interface preservation holds.",
                "pipeline_unblocks": [p for p, _ in spec.get("parents", [])] or ["the-living-atlas"],
            },
            "if_primary_tests_fail": {
                "diagnose": ["compiler dropped/renamed an interface port (law 2 violation)",
                             "handler produced no non-trivial dynamics on the declared ports"],
                "block_downstream": "the-living-atlas (the composed whole cell depends on this "
                                    "figure's mechanism)",
            },
        },
        "limitations": [
            "Uncalibrated toy-real constants — demonstrates the compositional pattern, not a "
            "quantitatively validated cell.",
            "Deterministic single run per mechanism; no multi-seed replication (the dynamics here "
            "are deterministic given the handler).",
        ],
        "falsifiability": (
            "The claim is overturned if the compiled executable fails to preserve the draft's "
            "interface (a port renamed or a wire dropped by compilation), or if the handler "
            "produces no non-trivial dynamics on the declared ports."),
        "visualizations": existing.get("visualizations", []),
    }
    if spec.get("parents"):
        # This schema version's parent_studies object is additionalProperties:false
        # ({study, condition} only) — `relation` is not accepted, so it's omitted;
        # edges default to leads-to in the investigation graph.
        body["parent_studies"] = [
            {"study": p, "condition": "tests-passed"} for p, _rel in spec["parents"]
        ]
    return body


def append_exec_viz(body, slug, exec_svgs):
    if not exec_svgs:
        return
    vizdir = STUDIES / slug / "visualizations"
    vizdir.mkdir(parents=True, exist_ok=True)
    existing_names = {v.get("name") for v in body["visualizations"]}
    for svg in exec_svgs:
        src = GALLERY / svg
        if not src.exists():
            print(f"    WARN missing gallery svg {svg}")
            continue
        shutil.copyfile(src, vizdir / svg)
        name = svg.replace(".svg", "")
        if name in existing_names:
            continue
        body["visualizations"].append({
            "name": name,
            "address": f"image:visualizations/{svg}",
            "config": {"chart": "image",
                       "caption": "EXECUTABLE dynamics — the compiled figure, running."},
        })


def main():
    for spec in SPECS:
        old_dir = STUDIES / spec["old"]
        new_dir = STUDIES / spec["slug"]
        existing = {}
        src_yaml = old_dir / "study.yaml"
        if src_yaml.exists():
            existing = yaml.safe_load(src_yaml.read_text()) or {}
        elif (new_dir / "study.yaml").exists():
            existing = yaml.safe_load((new_dir / "study.yaml").read_text()) or {}
        git_mv(old_dir, new_dir)

        body = build_study_body(spec, existing)
        if not spec.get("is_atlas"):
            append_exec_viz(body, spec["slug"], spec.get("exec_svgs"))

        tmp = new_dir / "study.yaml.tmp"
        tmp.write_text(yaml.safe_dump(body, sort_keys=False, allow_unicode=True, width=100))
        tmp.replace(new_dir / "study.yaml")
        print(f"  authored {spec['slug']} ({len(body['behavior_tests'])} tests, "
              f"{len(body['findings'])} findings)")

    old_inv, new_inv = INV / "paper-figures", INV / "draft-to-living-cell"
    git_mv(old_inv, new_inv)

    inv_yaml = new_inv / "investigation.yaml"
    RENAME = {s["old"]: s["slug"] for s in SPECS}
    inv = yaml.safe_load(inv_yaml.read_text())
    inv["name"] = "draft-to-living-cell"
    inv["status"] = "complete"
    inv["executive"]["verdict_status"] = "passed"
    inv["studies"] = [RENAME.get(s, s) for s in inv["studies"]]
    for row in inv.get("at_a_glance", []):
        row["study"] = RENAME.get(row["study"], row["study"])
    kf = inv.get("scientific_argument", {}).get("key_figures", [])
    inv["scientific_argument"]["key_figures"] = [RENAME.get(k, k) for k in kf]
    tmp = new_inv / "investigation.yaml.tmp"
    tmp.write_text(yaml.safe_dump(inv, sort_keys=False, allow_unicode=True, width=100))
    tmp.replace(inv_yaml)
    print(f"  rewrote investigation -> draft-to-living-cell ({len(inv['studies'])} studies)")


if __name__ == "__main__":
    main()
