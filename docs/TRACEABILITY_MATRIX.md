# Requirements Traceability Matrix

Extends `docs/IMPLEMENTATION_AUDIT.md`'s matrix (which covered the state
as of the audit) with everything built in Phases A-E since. Format:
Requirement → Specification section → Implementation file → Function →
Validation → Tests → Documentation.

| Requirement | Spec section | File | Function | Validation | Tests | Docs |
|---|---|---|---|---|---|---|
| Core simulation loop | Design Spec §16 | `model/src/model.py` | `FoodEnergyModel.step()` | Retrodiction battery (POM=0.30) | `tests/model/test_phase_*.py` (all, indirectly) | `docs/architecture/CAUSAL_DECOMPOSITION.md` |
| Trade network resolution | Design Spec §8 | `model/src/trade.py` | `_gravity_volume`, `execute_trade_step` | Retrodiction battery | `tests/model/test_phase_b_policy_levers.py::test_import_tariff_reduces_trade` | `docs/architecture/CAUSAL_DECOMPOSITION.md` §2 |
| STC overload accumulation | Design Spec §3 | `model/src/stc_engine.py` | `STCEngine._accumulate_stress`, `_detect_overload` | Ablation study (12→8 nodes) | `scripts/phase2_5_ablation.py` | `docs/validation/PHASE2_5_BASELINE_STABILITY_INVESTIGATION.md` |
| Coping capacity (CC_index) | Design Spec §5 | `model/src/stc_engine.py`, `model/src/ml_calibration.py` | `_accumulate_stress` (CC formula) | Cross-validated regression, R²=0.86 | — (pre-existing, not re-tested this session) | `docs/validation/VALIDATION_REPORT_INITIAL.md` §2 |
| Historical retrodiction (4 episodes) | Design Spec §13 | `model/src/retrodiction.py` | `run_phase8` | Real FAO FPI/export-ban-rate/PAR comparison | Re-run as regression gate every phase this session | `docs/validation/` (all 4 docs) |
| Scenario catalogue (5 historical + 5 counterfactual) | Mission Phase 2 | `model/src/stc_engine.py` (triggers), `scripts/run_phase2_catalogue.py` | `triggers_2008_food_energy`, etc. | Real MC runs, crisis attribution | — | `docs/scenarios/SCENARIO_CATALOGUE.md` |
| Climate triple-counting resolution | Causal Decomposition §13.2 | `model/src/stc_engine.py`, `model/src/energy.py`, `model/src/model.py` | `climate_single_channel_mode` flag | Verified opt-in, byte-identical when off | `tests/model/test_phase_c_climate_drivers.py::test_triple_counting_fix_*` (2 tests) | `docs/implementation/PHASE_C_IMPLEMENTATION_REPORT.md` |
| Continuous climate drivers (C1) | Digital Twin Arch. Part C1 | `model/src/climate_drivers.py` | `ContinuousClimateDriver` | Synthetic-data mechanism test only — NOT calibrated | `tests/model/test_phase_c_climate_drivers.py` (7 tests) | `docs/implementation/PHASE_C_IMPLEMENTATION_REPORT.md` |
| Soil quality (C2) | Digital Twin Arch. Part C2 | `model/src/climate_drivers.py` | `SoilQualityDriver` | Real production before/after comparison | Same file as above | Same |
| Fertilizer N/P/K (C3) | Digital Twin Arch. Part C3 | `model/src/resource_drivers.py` | `FertilizerDriver`, `mitscherlich_response` | Normalisation verified exact; shortage effect verified real | `tests/model/test_phase_c2_resource_drivers.py` (12 tests) | `docs/implementation/PHASE_C2_IMPLEMENTATION_REPORT.md` |
| Water reservoir stock (C4) | Digital Twin Arch. Part C4 | `model/src/resource_drivers.py` | `WaterStockDriver` | Units-scale bug found + fixed; re-verified | Same file as above | Same |
| Policy search infrastructure | Design Spec §10 | `model/src/scenarios.py` | `policy_search` | Objective correctness verified (PAR-based, matches spec) | `tests/model/test_phase_a_policy_search.py` (8 tests) | `docs/implementation/PHASE_A_IMPLEMENTATION_REPORT.md` |
| Reserve mandate (global pool variant) | Digital Twin Arch. Part B1/B8 | `model/src/scenarios.py` | `make_global_reserve_pool_lever` | Stock-conservation verified exactly | `tests/model/test_phase_b_policy_levers.py::test_reserve_pool_moves_real_stock` | `docs/implementation/PHASE_B_IMPLEMENTATION_REPORT.md` |
| Food aid | Digital Twin Arch. Part B2 | `model/src/scenarios.py` | `make_food_aid_lever` | Affordability-bypass verified with a zero-capital test node | `tests/model/test_phase_b_policy_levers.py::test_food_aid_bypasses_affordability` | Same |
| Coordinated export restriction | Digital Twin Arch. Part B3 | `model/src/scenarios.py` | `make_coordinated_export_restriction_lever` | Multi-node targeting verified | `tests/model/test_phase_b_policy_levers.py::test_coordinated_export_restriction_hits_all_targets` | Same |
| Climate adaptation funding | Digital Twin Arch. Part B6 | `model/src/scenarios.py`, `model/src/agent.py` | `make_climate_adaptation_lever` | Real climate_modifier before/after comparison | `tests/model/test_phase_b_policy_levers.py::test_climate_adaptation_reduces_sensitivity` | Same |
| Import tariff/subsidy | (spec-implied, not separately numbered) | `model/src/scenarios.py`, `model/src/trade.py` | `make_import_tariff_lever` | Real affordability-formula hand-calculation | `tests/model/test_phase_b_policy_levers.py::test_import_tariff_reduces_trade` | Same |
| Energy release/subsidy | Digital Twin Arch. Part B7 | `model/src/scenarios.py` | `make_energy_intervention_lever` | Reuses existing, already-validated shock interface | `tests/model/test_phase_b_policy_levers.py::test_energy_intervention_increases_supply` | Same |
| Fertilizer support (interim) | Digital Twin Arch. Part B4 (partial) | `model/src/scenarios.py` | `make_fertilizer_support_lever_INTERIM` | Self-labelled INTERIM in output | `tests/model/test_phase_b_policy_levers.py::test_fertilizer_interim_labelled_and_functional` | Same |
| Fertilizer redistribution (real) | Digital Twin Arch. Part B4 (full) | `model/src/resource_drivers.py` | `make_fertilizer_redistribution_lever` | Requires-driver error path verified | `tests/model/test_phase_c2_resource_drivers.py::test_fertilizer_redistribution_*` (2 tests) | `docs/implementation/PHASE_C2_IMPLEMENTATION_REPORT.md` |
| Node-level policy optimisation | Design Spec §10 (node-level extension) | `model/src/scenarios.py` | `node_level_policy_search` | Real donor/recipient exploration verified (9 distinct pairs / 10 samples) | `tests/model/test_phase_d_node_optimization.py` (8 tests) | `docs/implementation/PHASE_D_IMPLEMENTATION_REPORT.md` |
| Illustrative cost model | Design Spec §11 | `model/src/scenarios.py` | `LEVER_COSTS_ILLUSTRATIVE` | Budget-ranking order verified correct | `tests/model/test_phase_d_node_optimization.py::test_budget_filtering_*` | Same |
| `POST /api/policy_optimization` | Design Spec §19 | `backend/app/main.py`, `model_bridge.py` | `run_policy_optimization` | Pre-existing, re-confirmed unaffected every phase | `tests/api/test_endpoints.py::test_policy_optimization_original_endpoint_unaffected` | `docs/IMPLEMENTATION_AUDIT.md` Part 1.1 |
| `POST /api/policy_search` | Design Spec §19 (new) | `backend/app/main.py`, `model_bridge.py`, `schemas.py` | `run_policy_search`, `PolicySearchRequest` | Real HTTP round-trip, real uvicorn server | `tests/api/test_endpoints.py::test_policy_search_*` (2 tests) | `docs/implementation/PHASE_A/B/D_IMPLEMENTATION_REPORT.md` |
| `POST /api/policy_search/node_level` | Design Spec §19 (new) | Same files | `run_node_level_policy_search`, `NodeLevelSearchRequest` | Real HTTP round-trip; bugfix during this consolidation (unhandled ValueError → clean 400) | `tests/api/test_endpoints.py::test_policy_search_node_level_*` (2 tests) | `docs/implementation/PHASE_D_IMPLEMENTATION_REPORT.md`, `docs/FINAL_AUDIT.md` |
| Frontend Policy Lab | Design Spec §17 (frontend) | `frontend/src/app/policy-lab/page.tsx` | `PolicyLabPage` | TypeScript compile, production build, real server round-trip | Manual (no headless-browser test — flagged in LIMITATIONS.md) | `docs/implementation/PHASE_E_IMPLEMENTATION_REPORT.md` |
| Deployment architecture | Design Spec §17, §15 phase 7 | `docker-compose.yml`, `deployment/` | — | Docker path is real/working; K8s is design-only | — | `docs/architecture/DEPLOYMENT_ARCHITECTURE.md` |
| Database schema (extended) | Design Spec §18 | `backend/app/experiment_store.py` (current); proposed extension not implemented | — | Current schema in production use | — | `docs/architecture/SCIENTIFIC_DESIGN_SPECIFICATION.md` §18 |
| Mesa version pin (regression prevention) | — (found this session) | `backend/requirements.txt`, `model/requirements.txt` | — | Verified: `mesa==3.1.4` reproduces documented step-counting behaviour | Implicit in every model test | `docs/validation/PHASE2_5_MERGE_CHANGE_REPORT.md`, `INSTALL.md` |

## Requirements explicitly NOT traceable to a completed implementation

| Requirement | Spec section | Status |
|---|---|---|
| Real environmental calibration data (CHIRPS, IFA, AQUASTAT) | Digital Twin Arch. §12 | Not acquired — every driver above uses labelled synthetic placeholders |
| Bilateral fertilizer trade network | Digital Twin Arch. Part C3 (original proposal) | Deliberately not built (would require fabricated data) — simpler stock model built instead |
| Real cost-of-intervention data | Design Spec §11 | Not sourced — illustrative units only |
| Kubernetes manifests, job queue, Postgres migration | Design Spec §17 | Designed, not implemented |
| RC-amplification negative feedback | Causal Decomposition §13.1 | Deliberately kept open per explicit instruction |
