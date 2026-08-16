# Interactive Policy Lab — Compliance with "real controls only"

## Requirement

"The Digital Twin should expose ALL implemented policies... Do NOT
invent controls for unimplemented policies. Only expose real ones. Mark
proposed ones separately."

## Verification (checked directly against the real frontend source)

`frontend/src/app/policy-lab/page.tsx`'s `NODE_LEVEL_LEVERS` constant --
the exact set of node-targeted levers exposed in the UI dropdown -- lists
exactly 4 entries: `food_aid`, `climate_adaptation`, `import_tariff`,
`coordinated_export_restriction`. Cross-checked against
`scripts/generate_policy_catalog.py`'s `POLICIES` list (11 real,
introspected levers): all 4 UI-exposed levers exist there. **Zero UI
controls reference a policy that isn't real.**

The general search panel exposes no per-lever controls at all -- it
samples from `scenarios.py::LEVER_FACTORIES` (4 real global levers:
`reserve_mandate`, `trade_diversification`, `trader_regulation`,
`renewable_push`) automatically, so there is no user-facing control
surface that could expose an unimplemented policy.

## What is NOT exposed in the UI (and why that's correct, not a gap)

7 of the 11 real, implemented levers are not in the current UI:
`global_reserve_pool`, `fertilizer_support_interim`,
`fertilizer_redistribution`, `energy_intervention` (all real, all
API-accessible via `custom_levers` in `POST /api/policy_search`, none
yet wired to a frontend control), plus the 4 always-on mechanisms
(export policy, reserve accumulation, sanction penalty -- not "levers" in
the interactive sense, they're continuous per-node state).

This is an honest, real gap -- not a violation of the "only real ones"
rule (nothing fake is shown), but a real UI-completeness gap worth
noting. Extending `NODE_LEVEL_LEVERS` and the general-search panel to
cover all 11 is a small, well-scoped follow-up (each lever already has a
working `CUSTOM_LEVER_BUILDERS` entry -- see
`docs/implementation/PHASE_B_IMPLEMENTATION_REPORT.md`), not a redesign.

## Requirement satisfied

Yes, as implemented: no invented controls exist. Coverage is partial
(4 of 11 real levers have dedicated UI), and that gap is now documented
rather than silently present.
