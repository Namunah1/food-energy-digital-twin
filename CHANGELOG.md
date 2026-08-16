# Changelog

Chronological, grounded in the actual sequence of investigation and
implementation work. Each entry links to the full report where one
exists. No entry here describes work that wasn't actually done and
verified.

## Consolidation pass (this document's creation)

- Restructured the repository into `backend/ frontend/ model/ data/ docs/
  tests/ scripts/ deployment/ publication/ examples/`.
- **Fixed a real path-resolution break caused by the restructuring
  itself**: `backend/app/model_bridge.py` hardcoded a path assuming the
  model lived at `backend/model_src/...`; updated to `../../model`, and
  verified end-to-end via the full pytest suite before/after.
- **Fixed a real data-directory conflict**: `model/src/model.py`
  independently resolves data at `model/../data`; rather than duplicate
  the ~10MB data directory or fight the model's internal convention,
  made `model/data` a symlink to the top-level `data/` (single source of
  truth, satisfies both the "clearly separate /data" requirement and
  "preserve backward compatibility").
- **Removed real dead/junk artifacts found during restructuring**: an
  empty, unused `backend/app/routers/` directory nothing imported from;
  a literal directory named `{fao,owid,usda,nd_gain,iea}` in
  `data/raw/` (an unexpanded shell brace-expansion typo from the
  original repo, confirmed empty before removal); stale Windows-console
  crash logs from the user's own local run attempts, not carried into
  the clean repo.
- **Found and fixed a real bug via a new pytest suite**
  (`tests/api/test_endpoints.py`, written this pass): `POST
  /api/policy_search/node_level` did not catch its own `ValueError` for
  an unrecognised lever type — would have crashed to an unhandled
  exception in a real deployment. Now returns a clean HTTP 400.

## Phase E — Digital Twin frontend integration

New `/policy-lab` route consuming the Phase A/B/D policy-search API.
Verified via `tsc --noEmit`, a full Next.js production build, a real
running backend server (not just TestClient), and a real running
frontend server. See `docs/implementation/PHASE_E_IMPLEMENTATION_REPORT.md`.

## Phase D — Node-level policy optimisation

`node_level_policy_search()`: search over *which* countries a lever
should target, not just intensity. Illustrative cost model
(`LEVER_COSTS_ILLUSTRATIVE`, explicitly not real currency). 8/8 new
tests; a genuine finding surfaced by the search itself: some
randomly-sampled aid allocations produced *negative* population-saved
(worse than doing nothing). See
`docs/implementation/PHASE_D_IMPLEMENTATION_REPORT.md`.

## Phase C, increment 2 — Fertilizer N/P/K, water reservoir stock

`resource_drivers.py`: Mitscherlich-type fertilizer response (correctly
normalised so baseline application = no change from existing
calibration — a real correctness fix made during development, not
shipped-then-found), water reservoir balance. **Two real bugs found and
fixed before shipping**: the fertilizer response function's un-normalised
form would have silently cut baseline production ~14%; the water
driver's first version drained Egypt's stock to zero in one step from a
units-scale mismatch. 12/12 tests. See
`docs/implementation/PHASE_C2_IMPLEMENTATION_REPORT.md`.

## Phase C, increment 1 — Continuous climate drivers, soil quality

`climate_drivers.py`: continuous rainfall/temperature-anomaly driver
(synthetic placeholder data, clearly labelled), soil quality state, and
the triple-counting resolution (`climate_single_channel_mode`, opt-in,
default preserves original validated behaviour exactly). 7/7 tests. See
`docs/implementation/PHASE_C_IMPLEMENTATION_REPORT.md`.

## Phase B — Missing policy levers

7 new levers (global reserve pool, food aid, coordinated export
restriction, climate adaptation, import tariff, energy intervention,
interim fertilizer support). Two core-file edits
(`agent.py`/`trade.py`), both getattr-guarded for exact backward
compatibility. 11/11 tests. See
`docs/implementation/PHASE_B_IMPLEMENTATION_REPORT.md`.

## Phase A — Policy search infrastructure

`policy_search()`: extends `worst_case_discovery()`'s sample-run-rank
pattern, retargeted from finding bad shocks to finding good policies.
Synced the deployment backend's vendored model to the fixed canonical
copy (see "Phase 2.5" below) — a prerequisite the audit surfaced was
still outstanding. 8/8 tests. See
`docs/implementation/PHASE_A_IMPLEMENTATION_REPORT.md`.

## Implementation audit

Full traceability matrix, spec section → files → functions → status →
gaps. Found `/api/policy_optimization` already existed and was more
capable than the spec assumed; found `pandemic` already had a real
trigger type (the spec had implied it didn't). See
`docs/IMPLEMENTATION_AUDIT.md`.

## Digital Twin Scientific Design Specification

The 20-section canonical blueprint (mathematical architecture, causal
graph, all state/policy/global/climate/resource/trade/geopolitical
variables, optimisation objective, calibration/validation strategy,
software architecture, DB schema, API contracts). See
`docs/architecture/SCIENTIFIC_DESIGN_SPECIFICATION.md`.

## Phase 2.5b — Causal decomposition

Full subsystem-by-subsystem trace (10 subsystems: RC price amplification,
trade, STC overload accumulation, food security, coping capacity,
export-ban cascades, energy-food coupling, reserves, climate stress,
political instability). Found two dead-code mechanisms
(`_rc_contagion_boost` computed but never read; `G_BASE` gravity
constant declared but never used). Identified the RC-amplification
missing-negative-feedback loop as the model's dominant, still-open
issue. See `docs/architecture/CAUSAL_DECOMPOSITION.md`.

## Phase 2.5 — Sequencing fix, and a correction to this project's own prior claim

Investigated why every scenario showed a premature, step-1 overload
wave. Root cause: the STC engine evaluated food-security overload
*before* trade resolved each tick — a real sequencing bug, not a
calibration issue. Fixed by reordering. **A materially important
correction along the way**: this session's own earlier report that the
fix eliminated the issue entirely (12→0 overloaded nodes) was itself
wrong — traced to the test harness never incrementing Mesa's step
counter. Corrected, real effect: 12→8. After merging, **full-episode
validation got measurably worse, not better** (2022 FPI error: 9.1%→38.0%,
later 109.2% after the separate Mesa-version bug was also fixed) — this
was reported plainly rather than reverted or hidden. See
`docs/validation/PHASE2_5_BASELINE_STABILITY_INVESTIGATION.md` and
`docs/validation/PHASE2_5_MERGE_CHANGE_REPORT.md`.

## Phase 2 — Scenario catalogue

5 historical (2008, 2010 Russia export ban, 2011 East Africa, 2019-20
COVID, 2022 Ukraine) + 5 counterfactual scenarios, real Monte Carlo runs.
**Found a critical, session-invalidating bug while building new
scenarios**: Mesa 3.x's `Model.step()` wrapper double-increments the
step counter when combined with this codebase's own increment, silently
desyncing every trigger's timing from its documented calendar-year
intent. Fixed; every number in this session before the fix was
re-verified after it. See `docs/scenarios/SCENARIO_CATALOGUE.md` and
`docs/validation/PHASE2_VALIDATION_UPDATE.md`.

## Phase 1 — Agent/node documentation, deployment architecture

Full documentation of all 35 nodes from real calibration data (not
narrative). Deployment architecture recommendation: scale by replicating
whole simulations, not per-country microservices — justified from the
trade-clearing step's synchronous fixed-point structure, not asserted.
See `docs/nodes/NODE_DOCUMENTATION.md` and
`docs/architecture/DEPLOYMENT_ARCHITECTURE.md`.
