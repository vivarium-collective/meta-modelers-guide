#!/usr/bin/env python
"""Serialize the playable disintegration composite (build_disintegration) to
composites/fig06-disintegration-dynamics.composite.json — discoverable by the
workbench and playable via /viva-explore (the Composite Explorer / loom)."""
from __future__ import annotations

import json
from pathlib import Path

from meta_modelers_guide.wholecell import build_disintegration

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "meta_modelers_guide" / "composites" / "fig06-disintegration-dynamics.composite.json"


def main() -> None:
    doc = {
        "name": "Disintegration (playable)",
        "description": ("Fig 6a — cell disintegration as a PLAYABLE trajectory: a "
                        "thermal shock pushes the cell past its viability bound; "
                        "viability collapses, viability-gated metabolism halts, and "
                        "biomass decays into molecular debris (cell→molecular level "
                        "shift). Assembled in the figures' style (see wholecell.py), "
                        "not compiler-emitted. Play it to watch the collapse."),
        "requires": {"processes": ["ThermalEnvironment", "Uptake",
                                    "ViabilityGatedMetabolism", "ViabilityMonitor",
                                    "DisintegrationEvent"]},
        "state": build_disintegration(emit=True)["state"],
    }
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print("built", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
