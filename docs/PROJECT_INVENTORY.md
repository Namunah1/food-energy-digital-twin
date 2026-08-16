# Project Inventory

150 real files (excluding `node_modules`/`.next`/`__pycache__`), grouped
by directory. This is not a line-by-line listing of every file (see the
repository tree itself for that) -- it documents purpose, status, and
dependencies for every directory and every file whose purpose isn't
obvious from its name/location, per the consolidation task's request.

## `/backend` (15 files) -- FastAPI application

| File | Purpose | Status | Depends on |
|---|---|---|---|
| `app/main.py` | All ~30 HTTP routes | Complete, tested | `model_bridge.py`, `schemas.py` |
| `app/model_bridge.py` | Translation layer: HTTP request -> model call -> response. Zero scientific computation by design. | Complete, tested | `model/src/*` (via path) |
| `app/schemas.py` | Pydantic request/response models | Complete | -- |
| `app/experiment_store.py`, `notebook_store.py` | SQLite persistence (single-table, JSON-document pattern) | Working, not multi-replica-safe (see LIMITATIONS.md) | -- |
| `app/experiment.py`, `notebook.py` | Experiment/notebook domain objects | Pre-existing, not re-audited this session | -- |
| `app/advisor.py`, `ai_providers.py` | LLM-advisor chat feature | Pre-existing, not re-audited this session | -- |
| `app/health.py`, `coordinates.py` | Health check, geo-coordinate lookup for map UI | Pre-existing | -- |
| `requirements.txt` | Pinned deps, including `mesa==3.1.4` (critical, see INSTALL.md) | Current | -- |
| `Dockerfile` | Container build | Current, used by `docker-compose.yml` | -- |

## `/frontend` (37 files) -- Next.js application

Key files: `src/app/policy-lab/page.tsx` (new this session, Phase E),
`src/app/console/page.tsx` (Experiment Studio), `src/app/countries/page.tsx`,
`src/lib/api.ts` (all backend client bindings), `src/components/Nav.tsx`,
`src/components/console/ExplanationPanel.tsx` (renders policy-search
results). Full file list not individually annotated here -- the Next.js
App Router convention (`app/<route>/page.tsx`) makes each file's purpose
directly inferable from its path, and `DEVELOPER_GUIDE.md` documents the
conventions rather than repeating them per file.

## `/model/src` (20 files) -- the canonical scientific model

| File | Lines | Purpose |
|---|---|---|
| `model.py` | 710 | Core simulation loop (`FoodEnergyModel.step()`) |
| `agent.py` | 621 | `CountryAgent`: production, consumption, export policy |
| `stc_engine.py` | 1122 | Stress-Trigger-Cascade engine + every historical/counterfactual trigger definition |
| `scenarios.py` | 1554 | Scenario registry (S1-S5), policy levers (Phases A/B/D), search (`policy_search`, `node_level_policy_search`) |
| `trade.py` | 304 | Gravity-model trade resolution |
| `energy.py` | 364 | Energy stress, energy-food coupling |
| `political_economy.py` | 371 | Trader module, reserve mandate/diversification/regulation mechanisms |
| `prices.py` | 264 | Global price system |
| `climate_drivers.py` | 216 | New, Phase C1: continuous climate drivers, soil quality |
| `resource_drivers.py` | 297 | New, Phase C2: fertilizer N/P/K, water reservoir stock |
| `retrodiction.py` | 900 | Historical validation battery (`run_phase8`) |
| `sensitivity.py` | 615 | OAT/Morris/Sobol sensitivity analysis |
| `ml_calibration.py` | 569 | CC_index ML regression (the one fully-cross-validated subsystem) |
| `data_pipeline.py` | 902 | Raw to processed data ETL (CLI entrypoint) |
| `metrics.py` | 289 | Per-run metrics collection |
| `visualize.py` | 587 | Figure generation for the original publication freeze |
| `regenerate_all.py` | 249 | Master reproducibility entrypoint (CLI) |
| `run.py` | 188 | Additional CLI entrypoint |
| `calibrate_rc_price_amp.py` | 135 | RC price amplification calibration helper |

`model/data` -> symlink to top-level `/data` (see `docs/FINAL_AUDIT.md`
item 2 for why).

## `/data` (26 files)

`raw/` -- FAO, OWID, IEA, ND-GAIN source files (see `docs/DATA_PROVENANCE.md`
for full source/license/column documentation, pre-existing from the
original project, not regenerated this session).
`processed/` -- 19 files, all real, current outputs of `regenerate_all.py`/
`retrodiction.py` run against the fully-merged, five-phase-fixed model
(includes `retrodiction_scores.json`, `network_weights.csv`,
`node_parameters.csv`, `node_panel.csv`).

## `/docs` (21 files)

See `README.md`'s Documentation map table for the reading-order guide.
Organized into `architecture/`, `validation/`, `scenarios/`, `nodes/`,
`implementation/` (Phase A-E reports) subdirectories, plus top-level
`DATA_PROVENANCE.md`, `IMPLEMENTATION_AUDIT.md`, `FINAL_AUDIT.md`,
`BUGS_FIXED_ORIGINAL.md` (pre-existing project history).

## `/tests` (7 files)

`api/test_endpoints.py` -- new this consolidation, 10 tests, real
pytest suite (previously verified only via ad-hoc TestClient scripts
during development). `model/test_phase_*.py` -- 5 files, 46 tests total
across Phases A/B/C1/C2/D, all passing. `model/conftest.py` -- new this
consolidation, enables clean `pytest` discovery without manual path
copying.

## `/scripts` (3 files)

`run_phase2_catalogue.py`, `phase2_5_ablation.py`,
`regenerate_all_SMOKETEST.py` (relocated near-duplicate, see
`docs/FINAL_AUDIT.md`). `README.md` documents the same-directory-import
convention these require.

## `/deployment` (3 files)

Two `Dockerfile.*` copies (real, working -- the authoritative ones are
referenced by root `docker-compose.yml`) and `README.md` stating
explicitly what's real (Docker) vs. proposed-only (Kubernetes, queues --
see `docs/architecture/DEPLOYMENT_ARCHITECTURE.md`).

## `/publication`, `/examples`

Populated in this consolidation pass -- see those directories' own
contents; not exhaustively itemised here to avoid duplicating what's
already self-describing at that location.

## Root-level files (17)

`README.md`, `ARCHITECTURE.md`, `INSTALL.md`, `USER_GUIDE.md`,
`DEVELOPER_GUIDE.md`, `CHANGELOG.md`, `LIMITATIONS.md`, `FAQ.md`,
`LICENSE`, `CITATION.cff`, `.gitignore`, `docker-compose.yml`, this file
and its sibling analytical documents (`docs/TRACEABILITY_MATRIX.md`,
`docs/FINAL_AUDIT.md`, and the consolidation's own final report).
