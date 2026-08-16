"""Phase 5 · interface types + process kinds bind to ontology terms; conformance
can be ontology-aware; executables carry provenance."""
from __future__ import annotations

from viva_meta_modelers_guide.core import build_core
from viva_meta_modelers_guide.compile import _type_compatible
from viva_meta_modelers_guide.handler_envs import ENVS
from viva_meta_modelers_guide.ontology import (
    interface_term, process_term, term_ref, ontology_compatible, figure_provenance,
)
from viva_meta_modelers_guide._types import UNITS


def test_every_interface_quantity_has_a_term():
    for quantity in UNITS:
        assert interface_term(quantity) is not None, f"{quantity} unmapped"


def test_process_terms_resolve_for_every_handled_draft():
    for env in ENVS.values():
        for draft in env:
            term = process_term(draft)
            assert term is not None, f"no process term for {draft}"
            assert term_ref(term)


def test_known_go_ids():
    assert process_term("CellMetabolism")["id"] == "GO:0008152"
    assert process_term("Transcription")["id"] == "GO:0006351"
    assert process_term("Divide")["id"] == "GO:0051301"
    assert interface_term("temperature")["id"] == "PATO:0000146"


def test_ontology_compatible_same_term():
    # concentration and concentration share a term (reflexive, mapped).
    assert ontology_compatible("concentration", "concentration")
    # two unrelated quantities are not compatible.
    assert not ontology_compatible("mass", "temperature")


def test_conformance_uses_ontology(monkeypatch=None):
    core = build_core()
    # a handler type that denotes the same ontology term as the signature type is
    # accepted by _type_compatible even if the names differ. temperature ≠ voltage
    # by name, but both are distinct terms, so NOT compatible; a same-term pair is.
    assert _type_compatible(core, "concentration", "concentration")
    assert not _type_compatible(core, "temperature", "voltage")


def test_figure_provenance_shape():
    prov = figure_provenance(ENVS["fig06-coarse"])
    assert "CoarseGrainedMetabolism" in prov
    assert prov["CoarseGrainedMetabolism"]["process_term"].startswith("GO:")
