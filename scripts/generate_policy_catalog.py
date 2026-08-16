#!/usr/bin/env python3
"""
generate_policy_catalog.py
-----------------------------
Generates one document per implemented policy lever
(/docs/policies/<name>.md), extracting the REAL docstring, signature,
and lever_params structure directly from the code via Python
introspection -- not re-typed by hand. This guarantees the catalog can
never silently drift from what the code actually does, since it IS what
the code says about itself.

Run: PYTHONPATH=model/src python3 scripts/generate_policy_catalog.py
"""
import sys
import os
import inspect

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "model", "src"))
OUT_DIR = os.path.join(REPO_ROOT, "docs", "policies")

import scenarios
import resource_drivers
import political_economy

POLICIES = [
    ("Reserve Mandate", scenarios.make_reserve_mandate_lever, "scenarios.py"),
    ("Global Reserve Pool", scenarios.make_global_reserve_pool_lever, "scenarios.py"),
    ("Food Aid", scenarios.make_food_aid_lever, "scenarios.py"),
    ("Coordinated Export Restriction", scenarios.make_coordinated_export_restriction_lever, "scenarios.py"),
    ("Climate Adaptation Funding", scenarios.make_climate_adaptation_lever, "scenarios.py"),
    ("Import Tariff Subsidy", scenarios.make_import_tariff_lever, "scenarios.py"),
    ("Energy Intervention", scenarios.make_energy_intervention_lever, "scenarios.py"),
    ("Fertilizer Support Interim", scenarios.make_fertilizer_support_lever_INTERIM, "scenarios.py"),
    ("Fertilizer Redistribution", resource_drivers.make_fertilizer_redistribution_lever, "resource_drivers.py"),
    ("Trade Diversification", political_economy.PoliticalEconomyModule.apply_diversification, "political_economy.py"),
    ("Trader Regulation", political_economy.PoliticalEconomyModule.apply_trader_regulation, "political_economy.py"),
]


def generate_policy_doc(name, fn, source_file):
    sig = inspect.signature(fn)
    doc = inspect.getdoc(fn) or "(no docstring found)"
    lines = []
    lines.append(f"# Policy: {name}\n")
    lines.append(f"*Extracted directly from `model/src/{source_file}::{fn.__name__}`'s real "
                  f"signature and docstring via Python introspection -- not hand-transcribed.*\n")
    lines.append(f"## Signature\n")
    lines.append(f"```python\n{fn.__name__}{sig}\n```\n")
    lines.append(f"## Full documentation (from source)\n")
    lines.append(f"```\n{doc}\n```\n")
    lines.append(f"## Cross-references\n")
    lines.append(f"- Source file: `model/src/{source_file}`")
    lines.append(f"- Traceability entry: `docs/TRACEABILITY_MATRIX.md`")
    lines.append(f"- Implementation report: see `docs/implementation/` for the phase that built this")
    lines.append(f"- Tests: `tests/model/test_phase_*.py` (search for `{fn.__name__}`)")
    return "\n".join(lines)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    index = ["# Policy Catalog Index\n",
             f"{len(POLICIES)} implemented policy levers, each documented by extracting the "
             "REAL docstring and signature from the code (see "
             "`scripts/generate_policy_catalog.py`). This is the complete list of policies "
             "this project has actually implemented -- nothing here is proposed-only; "
             "proposed-but-not-implemented policies are catalogued separately in "
             "`docs/global_policies/README.md`.\n"]
    for name, fn, source_file in POLICIES:
        doc = generate_policy_doc(name, fn, source_file)
        safe = name.replace(" ", "_")
        with open(os.path.join(OUT_DIR, f"{safe}.md"), "w") as f:
            f.write(doc)
        index.append(f"- [{name}]({safe}.md) (`{source_file}`)")
    with open(os.path.join(OUT_DIR, "README.md"), "w") as f:
        f.write("\n".join(index))
    print(f"Generated {len(POLICIES)} policy docs + index in {OUT_DIR}")
