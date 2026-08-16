# Phase D Implementation Report — Node-Level Policy Optimisation

## What was implemented

1. **`node_level_policy_search()`** — a focused search answering the
   Digital Twin spec Section 10 question directly: "which N countries
   should receive [lever] to minimise global PAR." Supports the
   node-targeted Phase B levers (`food_aid`, `climate_adaptation`,
   `import_tariff`, `coordinated_export_restriction`). Samples random
   node combinations (donor/recipient pairs for aid; single nodes for
   adaptation/tariff; node sets for coordinated restriction), runs each,
   ranks by `population_saved_millions` — same objective as Phase A,
   applied to a genuinely different search dimension (which nodes, not
   which global lever).

2. **`policy_search()` extended** with `include_node_targeted_sampling`
   and `node_pool` — the *general* search can now also sample
   node-targeted candidates alongside the global-lever combinations from
   Phase A, rather than requiring the caller to name a node explicitly via
   `custom_levers` (Phase B's only prior option).

3. **`LEVER_COSTS_ILLUSTRATIVE`** — the Section 11 gap ("no cost model
   exists yet") given an explicit, deliberately-illustrative structure:
   relative cost *ordering* across levers (aid/tariffs cheaper than a
   reserve mandate or trade-network rewiring) is a modelling judgement,
   not sourced data. `max_budget` annotates every candidate with its
   illustrative cost and a `within_budget` flag — **candidates over
   budget are never silently dropped**, only ranked lower, so a caller
   can see what was excluded and why.

4. **API**: new `POST /api/policy_search/node_level`, and
   `PolicySearchRequest` extended with `include_node_targeted_sampling`,
   `node_pool`, `max_budget` — both `/api/policy_optimization` (Phase A's
   baseline) and the original `/api/policy_search` behaviour (no new
   kwargs supplied) are unaffected.

## Real test results

`test_phase_d_node_optimization.py`: **8/8 passed**, including:

- **Backward compatibility**: `policy_search()` called exactly as the
  Phase A/B tests call it (no Phase D kwargs) still evaluates exactly 13
  candidates, unaffected.
- **The core deliverable, verified not assumed**: a food-aid node search
  explored 9 distinct donor/recipient pairs out of 10 random candidates —
  genuinely searching the node space, not repeating one choice.
- **A real, honest finding the search itself surfaced**: ranked results
  for one node-search run ranged from **+1.5M to −0.3M** people saved —
  meaning some randomly-sampled aid allocations *made things worse* than
  doing nothing. This is correct, expected search behaviour (not every
  candidate should help; a poorly-targeted transfer can strip a marginal
  donor's own buffer without meaningfully helping an unsuited recipient)
  and the ranking correctly surfaces it rather than hiding it.
- **Budget filtering prioritises correctly**: with a tight budget, every
  within-budget candidate ranked above every over-budget one, confirmed
  by checking the ranking order directly, not just that the flag exists.
- **Unsupported lever types rejected with a clear error**, not a silent
  no-op or crash.

**Final regression gate**: full 4-episode retrodiction battery re-run
after all Phase D changes — **exact match** to every prior phase's
baseline (POM=0.300, FPI errors 41.15% / 109.24% / 163.21% / 62.41%).
Zero drift across four phases of additive changes now.

**Cross-phase regression**: all 34 tests across
`test_phase_a_policy_search.py` (8), `test_phase_b_policy_levers.py` (11),
`test_phase_c_climate_drivers.py` (7), and
`test_phase_d_node_optimization.py` (8) pass together in the deployment
copy, confirming the four phases compose without interference.

## Known limitations, stated plainly

- **The cost model is explicitly illustrative**, not sourced from real
  data (FAO/World Bank cost-of-storage literature, per the Digital Twin
  spec Section 12, was never acquired this session). Every place it's
  surfaced — the module docstring, the API response's `cost_model_note`
  field, this report — says so. A caller building a real budget-
  constrained recommendation on top of this needs real cost data first.
- **`node_level_policy_search` supports 4 of Phase B's 7 levers**
  (`food_aid`, `climate_adaptation`, `import_tariff`,
  `coordinated_export_restriction`) — `global_reserve_pool`,
  `energy_intervention`, and `fertilizer_support_interim` aren't
  node-search-shaped in the same way (the reserve pool is inherently
  global; energy intervention can't target an exact node per Phase B's
  own documented limitation). Calling with an unsupported type raises a
  clear `ValueError` rather than silently no-op'ing.
- **Random sampling, not true optimisation** — this is the same
  black-box, sample-and-rank approach as Phase A (per the Digital Twin
  spec Section 10's own recommendation, given the ~1s/candidate runtime
  makes this tractable without a differentiable surrogate). A more
  sophisticated search (Bayesian optimisation, genetic algorithms) would
  converge faster per evaluation but was not built this phase — flagged
  as a possible future refinement, not a gap in what was promised.

## Files changed

- `scenarios.py` — `LEVER_COSTS_ILLUSTRATIVE`, `node_level_policy_search()`,
  `policy_search()` extended with three new optional parameters (default
  values preserve exact prior behaviour)
- `test_phase_d_node_optimization.py` — new, 8 tests
- `app/schemas.py` — new `NodeLevelSearchRequest`, `PolicySearchRequest`
  extended with three optional fields
- `app/model_bridge.py` — new `run_node_level_policy_search()`,
  `run_policy_search()` extended with matching optional parameters
- `app/main.py` — new `POST /api/policy_search/node_level`, one import
  line updated

**Nothing existing was rewritten.** Four phases in, every prior phase's
tests still pass unmodified, and the retrodiction battery has not moved
by a single decimal point from engineering work in phases A through D.

## Next

Per the earlier fork: Phase C's remaining pieces (C3 fertilizer N/P/K +
its dedicated trade network, C4 water reservoir stock) or Phase E
(Digital Twin frontend integration) — Phase D's new endpoints are now
real and API-contract-ready for whichever comes first.
