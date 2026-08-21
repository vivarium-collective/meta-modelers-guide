"""A reusable, composite-agnostic closed mass-balance control for field-coupled
composites.

Why this exists
----------------
The source paper frames conservation laws (mass, energy balance) as interface
constraints on any process-bigraph coupling: "They are constrained by
conservation laws such as mass and energy balance, which coupled internal
processes to external exchange." The flagship spatial study
(``workspace/studies/cell-environment-coupling-spatial/study.yaml``) lists
this as an explicit, still-unmet next step: "Track field-wide mass (source +
diffusion + uptake + secretion) as an explicit closed balance rather than
reporting depletion/secretion as separate totals." This module is that
control.

How it works
------------
A field-coupled composite (e.g. ``single-cell-in-a-field.composite.json``)
has exactly N processes that write additive per-tick deltas onto one shared
``fields: map[array]`` store (a spatio_flux ``DiffusionAdvection`` step, plus
one or more cell/organism processes such as ``CpmCellField``). This helper
re-runs the composite with every named writer process transparently wrapped
to *record* its own returned ``fields`` delta each tick, BEFORE the
process-bigraph engine sums that delta onto the shared grid. After the run it
checks, per species::

    final_field_mass == initial_field_mass + sum(every writer's own reported deltas)

This is a genuine cross-check, not tautological bookkeeping: the writer's
*reported* delta and what actually accumulates in the grid travel through two
independent code paths (the process's own per-tick arithmetic vs.
process-bigraph's additive ``apply`` for a ``map[array]`` port). A bug in
either — a clamp that manufactures mass, a double-write, a schema ``apply``
that silently concatenates instead of sums (this repo has hit exactly that
failure mode for plain ``list`` ports — see ``cell_field.py``'s
``overwrite[...]`` output-schema comment) — surfaces as a nonzero residual.

What this control closes
-------------------------
- For a *source* species (a writer only ever adds mass, e.g. secreted
  acetate) and a *sink* species (a writer only ever removes mass, e.g.
  consumed glucose), it closes the full per-species ledger:
  ``initial_mass + sources - sinks == final_mass`` within tolerance, where
  "sources"/"sinks" are the writers' own reported per-tick deltas summed over
  the run — not re-derived from the field itself.
- It also reports each writer's own net contribution separately (e.g.
  ``diff`` vs ``cell``), so a diffusion boundary-condition leak (Neumann BC
  should net to ~0 mass change) is visible as a nonzero
  ``writer_net_exchange["diff"]`` rather than being silently absorbed into
  the cell's ledger entry.

What this control does NOT close
----------------------------------
- It does not independently verify the biology of the FBA solve itself (e.g.
  that ``EX_glc__D_e``/``EX_ac_e`` fluxes are metabolically correct) — only
  that whatever a writer process computed and returned is exactly what
  accumulated in the shared field.
- It does not prove ``DiffusionAdvection`` is leak-free from first
  principles; it trusts Neumann BC to conserve mass and *reports* the
  diffusion writer's own net contribution so a reviewer can see any leak
  here, rather than separately deriving the discrete-Laplacian proof.
- Any process that touches the ``fields`` store but is NOT named in
  ``writer_process_names`` is invisible to the ledger — its contribution
  would show up folded into an unexplained residual instead of being
  attributed. Callers must list every writer.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np
from bigraph_schema.protocols import local_lookup
from process_bigraph import Composite


@dataclass
class SpeciesLedger:
    """The closed mass-balance ledger for one field species over one run."""

    species: str
    initial_mass: float
    final_mass: float
    writer_net_exchange: dict = field(default_factory=dict)  # {writer name: net Σdelta}
    predicted_final_mass: float = 0.0
    residual: float = 0.0

    @property
    def total_writer_exchange(self) -> float:
        return sum(self.writer_net_exchange.values())

    def is_closed(self, tol: float = 1e-6) -> bool:
        return abs(self.residual) <= tol


def _wrap_recording(base_cls, sink: list, fields_key: str):
    """Return a subclass of `base_cls` whose `update()` behaves identically but
    also appends a copy of its returned `fields_key` delta (per species, as
    plain float ndarrays) onto `sink`, one entry per tick."""

    class _RecordingProcess(base_cls):
        def update(self, state, interval):
            out = base_cls.update(self, state, interval)
            deltas = out.get(fields_key) if isinstance(out, Mapping) else None
            if deltas:
                sink.append({sp: np.array(np.asarray(v), dtype=float, copy=True)
                             for sp, v in deltas.items()})
            else:
                sink.append({})
            return out

    _RecordingProcess.__name__ = f"_MassBalanceRecording_{base_cls.__name__}"
    return _RecordingProcess


def field_mass_balance(
    composite_state: Mapping,
    core,
    n_ticks: int,
    *,
    writer_process_names: Sequence[str],
    fields_key: str = "fields",
    species: Iterable[str] | None = None,
) -> dict[str, SpeciesLedger]:
    """Run a (deep-copied) `composite_state` for `n_ticks` and return a closed
    per-species mass ledger for its shared `fields_key` store.

    Args:
        composite_state: the ``state`` dict of a process-bigraph composite
            spec (e.g. ``json.loads(composite_json_text)["state"]``). Not
            mutated — a deep copy is run.
        core: a process-bigraph core (e.g. ``meta_modelers_guide.core.build_core()``)
            with every process address in the composite already registered.
        n_ticks: number of ``interval``-sized ticks to run.
        writer_process_names: names (top-level keys into `composite_state`) of
            EVERY process whose `outputs()` write additive deltas onto
            `fields_key`. Any writer omitted here is invisible to the ledger.
        fields_key: the shared store's key in `composite_state` (default
            ``"fields"``).
        species: which field species to report on; defaults to every species
            present in the initial `fields_key` store.

    Returns:
        ``{species: SpeciesLedger}``.
    """
    if not writer_process_names:
        raise ValueError("writer_process_names must list every process that writes "
                          f"onto {fields_key!r} — got an empty sequence")

    state = copy.deepcopy(dict(composite_state))
    recorded: dict[str, list] = {name: [] for name in writer_process_names}

    for name in writer_process_names:
        if name not in state:
            raise KeyError(f"writer process {name!r} not found in composite state")
        proc_state = state[name]
        address = proc_state.get("address", "")
        if not address.startswith("local:"):
            raise ValueError(f"process {name!r}: only 'local:...' addresses are "
                              f"supported by field_mass_balance, got {address!r}")
        base_name = address.split(":", 1)[1]
        # `base_name` is either a plain registry key (``ClassName``, resolved via
        # ``core.link_registry``) or a directly-importable ``!module.path.ClassName``
        # (bigraph-schema's "local module protocol") -- ``local_lookup`` handles
        # both forms exactly as the composite engine itself does when building.
        base_cls = local_lookup(core, base_name)
        if base_cls is None:
            raise ValueError(f"process class {base_name!r} (for {name!r}) could not "
                              "be resolved from the given core (checked the link "
                              "registry and, for '!'-prefixed addresses, direct import)")

        wrapped_cls = _wrap_recording(base_cls, recorded[name], fields_key)
        wrapped_name = f"_MassBalanceRecording_{name}_{base_name}"
        core.register_link(wrapped_name, wrapped_cls)
        proc_state["address"] = f"local:{wrapped_name}"

    comp = Composite({"state": state}, core=core)
    fields0 = comp.state[fields_key]
    all_species = list(species) if species is not None else list(fields0.keys())
    initial_mass = {sp: float(np.sum(np.asarray(fields0[sp]))) for sp in all_species}

    comp.run(n_ticks)

    fields1 = comp.state[fields_key]
    final_mass = {sp: float(np.sum(np.asarray(fields1[sp]))) for sp in all_species}

    ledgers: dict[str, SpeciesLedger] = {}
    for sp in all_species:
        writer_net = {}
        for name in writer_process_names:
            total = 0.0
            for delta in recorded[name]:
                if sp in delta:
                    total += float(np.sum(delta[sp]))
            writer_net[name] = total
        predicted = initial_mass[sp] + sum(writer_net.values())
        residual = final_mass[sp] - predicted
        ledgers[sp] = SpeciesLedger(
            species=sp,
            initial_mass=initial_mass[sp],
            final_mass=final_mass[sp],
            writer_net_exchange=writer_net,
            predicted_final_mass=predicted,
            residual=residual,
        )
    return ledgers
