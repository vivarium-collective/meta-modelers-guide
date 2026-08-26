"""Draft-process interfaces referenced by the guide's figure composites.

Several figure composites wire ``local:<Name>`` process nodes that illustrate a
biological role without committing to dynamics — the guide's whole point about
*draft processes* (a typed port interface + a behavior contract, no update law).
This module supplies those interface declarations so the composites build and
their wiring type-checks. Each is a :class:`DraftProcess`; the ports mirror how
the composites wire them. Executable counterparts live in the ``*_executable``
composites (real handler processes), per the guide's draft→executable split.
"""
from __future__ import annotations

from process_bigraph import DraftProcess, draft_process


def _contract(summary: str, ports: dict[str, str]) -> dict:
    return {"summary": summary, "behavior": summary, "senses": "its input ports.",
            "affects": "its output ports.", "constraints": "illustrative draft; "
            "no dynamics.", "ports": ports}


@draft_process(
    name="Reaction",
    inputs={"substrate": "concentration"},
    outputs={"product": "concentration"},
    contract=_contract("Reaction — converts substrate into product.",
                       {"substrate": "substrate pool (mol·L⁻¹)",
                        "product": "product pool (mol·L⁻¹)"}),
)
class Reaction(DraftProcess):
    pass


@draft_process(
    name="Express",
    inputs={"genes": "concentration"},
    outputs={"ribosomes": "concentration"},
    contract=_contract("Express — reads genes and produces ribosomes.",
                       {"genes": "gene template pool (mol·L⁻¹)",
                        "ribosomes": "ribosome pool produced (mol·L⁻¹)"}),
)
class Express(DraftProcess):
    pass


@draft_process(
    name="Grow",
    inputs={"ribosomes": "concentration", "nutrients": "concentration",
            "signals": "concentration"},
    outputs={"membrane": "structure"},
    contract=_contract("Grow — builds membrane from ribosomes, nutrients, signals.",
                       {"ribosomes": "ribosome pool (mol·L⁻¹)",
                        "nutrients": "nutrient pool (mol·L⁻¹)",
                        "signals": "signalling input (mol·L⁻¹)",
                        "membrane": "membrane structure produced"}),
)
class Grow(DraftProcess):
    pass


@draft_process(
    name="Transport",
    inputs={"channels": "count", "nutrients": "concentration"},
    outputs={"shape": "structure"},
    contract=_contract("Transport — moves nutrients through channels, shaping the cell.",
                       {"channels": "transport channel count",
                        "nutrients": "nutrient pool (mol·L⁻¹)",
                        "shape": "resulting cell shape"}),
)
class Transport(DraftProcess):
    pass


@draft_process(
    name="Metabolism",
    inputs={"enzymes": "concentration", "energy": "energy"},
    outputs={"metabolites": "concentration"},
    contract=_contract("Metabolism — enzymes and energy yield metabolites.",
                       {"enzymes": "enzyme pool (mol·L⁻¹)",
                        "energy": "free energy input (J)",
                        "metabolites": "metabolite pool produced (mol·L⁻¹)"}),
)
class Metabolism(DraftProcess):
    pass


@draft_process(
    name="Division",
    inputs={"volume": "volume", "phase": "phase"},
    outputs={"phase": "phase"},
    contract=_contract("Division — advances cell-cycle phase once volume permits.",
                       {"volume": "cell volume (m³)",
                        "phase": "cell-cycle phase (0–1)"}),
)
class Division(DraftProcess):
    pass


@draft_process(
    name="RNADegradation",
    inputs={"mrna": "concentration"},
    outputs={"mrna": "concentration"},
    contract=_contract("RNA degradation — turns over the mRNA pool.",
                       {"mrna": "mRNA pool (mol·L⁻¹)"}),
)
class RNADegradation(DraftProcess):
    pass


@draft_process(
    name="MolecularPacking",
    inputs={"molecules": "concentration", "volume": "volume"},
    outputs={"structure": "structure"},
    contract=_contract("Molecular packing — arranges molecules into structure.",
                       {"molecules": "molecule pool (mol·L⁻¹)",
                        "volume": "available volume (m³)",
                        "structure": "packed structure"}),
)
class MolecularPacking(DraftProcess):
    pass


@draft_process(
    name="ABM",
    inputs={"population": "cell_count", "field": "concentration"},
    outputs={"population": "cell_count"},
    contract=_contract("ABM — an agent-based cell population responding to a field.",
                       {"population": "cell population (cells)",
                        "field": "environmental field (mol·L⁻¹)"}),
)
class ABM(DraftProcess):
    pass


@draft_process(
    name="BigraphLink",
    inputs={"in": "quantity"},
    outputs={"out": "quantity"},
    contract=_contract("Bigraph link — a link-graph edge relating two ports.",
                       {"in": "linked input", "out": "linked output"}),
)
class BigraphLink(DraftProcess):
    pass


@draft_process(
    name="GrainSelector",
    inputs={"viability": "viability"},
    outputs={"active_grain": "grain"},
    contract=_contract("Grain selector — picks the active coarse-graining level.",
                       {"viability": "current viability (0–1)",
                        "active_grain": "selected grain level"}),
)
class GrainSelector(DraftProcess):
    pass


@draft_process(
    name="CoarseGrain",
    inputs={"inflow": "concentration", "active_grain": "grain"},
    outputs={"biomass": "concentration", "energy": "energy",
             "secretions": "concentration"},
    contract=_contract("Coarse-grain metabolism — lumped growth from inflow.",
                       {"inflow": "nutrient inflow (mol·L⁻¹)",
                        "active_grain": "active grain level",
                        "biomass": "biomass produced (mol·L⁻¹)",
                        "energy": "energy produced (J)",
                        "secretions": "secreted products (mol·L⁻¹)"}),
)
class CoarseGrain(DraftProcess):
    pass


@draft_process(
    name="FineGrain",
    inputs={"inflow": "concentration", "active_grain": "grain"},
    outputs={"biomass": "concentration", "energy": "energy",
             "secretions": "concentration"},
    contract=_contract("Fine-grain metabolism — resolved growth from inflow.",
                       {"inflow": "nutrient inflow (mol·L⁻¹)",
                        "active_grain": "active grain level",
                        "biomass": "biomass produced (mol·L⁻¹)",
                        "energy": "energy produced (J)",
                        "secretions": "secreted products (mol·L⁻¹)"}),
)
class FineGrain(DraftProcess):
    pass
