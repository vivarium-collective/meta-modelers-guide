"""Fig 10-1 division as a GENUINE structural rewrite: firing the rule CREATES the
daughter nodes (vs. the pre-declared-structure DivisionRewrite handler)."""
from __future__ import annotations

from viva_meta_modelers_guide.structural import one_cell, divide, cells_in


def test_division_creates_two_daughter_nodes():
    before = one_cell(biomass=2.0, dna=1.0)
    assert cells_in(before) == ["cell"]              # one cell, no pre-declared daughters
    after = divide(before)
    daughters = cells_in(after)
    assert set(daughters) == {"daughter_1", "daughter_2"}   # nodes were CREATED
    assert "cell" not in after                        # the parent node is gone


def test_contents_carried_into_both_daughters():
    after = divide(one_cell(biomass=2.0, dna=1.5))
    for d in ("daughter_1", "daughter_2"):
        node = after[d]
        assert node.get("biomass") == 2.0 and node.get("dna") == 1.5


def test_node_count_grows():
    before = one_cell()
    after = divide(before)
    assert len(cells_in(after)) == 2 * len(cells_in(before))   # 1 -> 2, real node insertion


def test_division_fires_in_a_live_composite():
    """The ReactionStep divides the cell inside a running Composite (typed store)."""
    from viva_meta_modelers_guide.structural import run_division
    colony = run_division(biomass=2.0, dna=1.0)
    assert set(cells_in(colony)) == {"daughter_1", "daughter_2"}   # created in-composite
    assert "cell" not in colony
    for d in ("daughter_1", "daughter_2"):
        assert colony[d].get("biomass") == 2.0                      # contents carried
