# Phase B Implementation Report — Missing Policy Levers

## What was implemented

Seven new levers, per the Digital Twin spec Section 4 gap list, registered
in a new `CUSTOM_LEVER_BUILDERS` dict so the API and future phases can add
more without touching `policy_search()` itself:

| Lever | Spec section | Mechanism | New state touched |
|---|---|---|---|
| Global reserve pool | B1+B8 | One-time levy from surplus nodes → pooled → drawn by need | `food_imperish` (transfer only, conserved) |
| Food aid | B2 | Direct node-to-node transfer, bypasses the gravity model's affordability gate entirely | `food_imperish` |
| Coordinated export restriction | B3 | `export_fraction` cap applied to N named nodes at once | `export_fraction`, `export_ban` |
| Climate adaptation funding | B6 | Reduces a node's drought/heatwave/flood sensitivity | New optional `climate_sensitivity_multiplier` attribute |
| Import tariff/subsidy | (new, spec-implied) | Multiplies effective price in the trade affordability constraint | New optional `import_tariff_multiplier` attribute |
| Energy release/subsidy | B7 | Named wrapper around existing `apply_energy_shock` with negative severity | none new (confirmed audit finding: mechanism already supported this) |
| Fertilizer support — **INTERIM** | B4 (partial) | Routed through the energy-food coupling channel, explicitly labelled as a proxy | `energy_fuel` |

## Two core-file edits, both additive and both verified byte-identical when unused

`agent.py::_update_climate_modifier` and `trade.py::_gravity_volume` are
hot-path functions run by *every* scenario, not just new ones — these were
the highest-risk changes in this phase. Both edits follow the same
pattern: read an optional new attribute via `getattr(obj, name, default)`
where `default` reproduces the original formula exactly. Verified two
ways: (1) direct equation check — confirmed by hand-calculation that the
tariff multiplier produces exactly the documented before/after volumes;
(2) full determinism check — running the same scenario twice with no new
attributes set produces bit-identical `model.summary()` output.

## Real test results

`test_phase_b_policy_levers.py`: **11/11 passed** (one initial failure —
`test_import_tariff_reduces_trade` — was traced to the *test's* synthetic
`edge_cap` being small enough that trade capacity, not affordability, was
the binding constraint; fixed by widening the test's capacity headroom,
then re-verified against a hand-calculated affordability value directly).
`test_phase_a_policy_search.py`: **8/8 still passing** after the Phase B
edits — no regression in Phase A's functionality.

**Full retrodiction battery re-run as a regression gate** (POM score and
all 4 episode FPI errors): **exact match** to the post-Phase-2.5-merge
baseline (POM=0.300, 2008=41.15%, 2022=109.24%, 2011=163.21%,
2020=62.41%) — confirms the Phase B edits changed nothing about the
model's core scientific behaviour when the new levers aren't invoked.

## Real, run-based findings (not asserted)

- **Global reserve pool conserves total system stock exactly**
  (3.276×10¹⁵ → 3.276×10¹⁵ kcal, transfer-only as designed) — confirmed
  by direct summation before/after, not just by reading the code.
- **Food aid genuinely bypasses affordability**: tested by setting a
  recipient's capital to near-zero (which would make `affordable_kcal≈0`
  in the gravity model, blocking ordinary trade) and confirming aid still
  arrives — this is the mechanism's entire reason for existing, and it's
  now verified, not just asserted in the docstring.
- **Climate adaptation measurably changes the climate modifier**
  (0.680 → 0.840 for the same drought severity, 50% effectiveness) — a
  real, checkable equation output, not a placeholder.

## Known limitations, stated plainly (not hidden)

- **The global reserve pool is a one-time redistribution, not a
  continuous mechanism.** `response_fn` levers are called once, before
  `model.run()` starts — a genuinely continuous pool (recalculated every
  tick) would need a new hook into `model.step()`'s core loop, which is
  out of scope for "extend, don't rewrite" and is flagged for a future
  phase if wanted, not silently approximated as equivalent.
- **The fertilizer lever is explicitly interim** — its own `lever_params`
  output includes `"status": "INTERIM"` so no caller can mistake it for
  the full Φ_i (N/P/K) mechanism, which requires Phase C's new state
  variables.
- **Climate adaptation's `effectiveness` parameter has no independent
  calibration source** (consistent with the Digital Twin spec's own
  Section 12 tiering — this was flagged LOW-confidence before
  implementation, not discovered after). The factory's `lever_params`
  output says so explicitly.
- **Energy intervention cannot target an exact named node** — it inherits
  this limitation from the underlying `apply_energy_shock`, which shocks
  a randomly-sampled scope of nodes. Passing `node_name` narrows the scope
  to approximately one node but isn't exact-name targeting. Documented in
  the factory's docstring rather than silently pretending precision that
  doesn't exist.
- **`CustomLeverSpec`'s Pydantic schema is intentionally loose** (all
  lever-specific fields optional, validated at the model layer via
  `scenarios.build_custom_lever`, not at the API layer) — a deliberate
  tradeoff to avoid seven near-duplicate request models; a malformed spec
  produces a clear warning and is skipped, not a 500 error, verified by
  the `bogus_unknown_lever` test case.

## API surface added

`POST /api/policy_search` (from Phase A) now additionally accepts
`custom_levers: [CustomLeverSpec]` — each valid spec is evaluated as its
own candidate, plus one combined "bundle" candidate if more than one valid
custom lever is supplied. Verified end-to-end via FastAPI TestClient with
three real custom levers (food aid, climate adaptation, import tariff):
200 response, all three appear as individual candidates plus the bundle,
ranked correctly. `/api/policy_optimization` (original) and `/api/health`
re-confirmed unaffected.

## Files changed

- `agent.py` — one method, additive/backward-compatible
- `trade.py` — one function, additive/backward-compatible
- `scenarios.py` — 7 new lever factories, `CUSTOM_LEVER_BUILDERS` registry,
  `build_custom_lever()`, `custom_levers` param threaded through
  `policy_search()`
- `test_phase_b_policy_levers.py` — new, 11 tests
- `app/schemas.py` — new `CustomLeverSpec`, extended `PolicySearchRequest`
- `app/model_bridge.py` — `run_policy_search()` extended with one new
  parameter, passed through unchanged otherwise
- `app/main.py` — one line changed to pass `custom_levers` through

## Next: Phase C

Environmental/resource drivers (rainfall, soil, fertilizer N/P/K, water
stock) per the Digital Twin spec Parts C1-C4. Per the spec's own stated
dependency order (Section 15, item 4), this must resolve the climate
triple-counting issue (Phase 2.5b finding) as part of the same change, not
after — flagged as the first design decision for Phase C, not an
afterthought.
