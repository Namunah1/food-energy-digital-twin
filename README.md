# Global Food-Energy Systemic Risk Digital Twin

A 35-node agent-based model (21 countries + 14 regional blocs) of the
global food-energy system, coupled through a real trade network, with a
policy-optimisation layer for testing interventions against historical
and counterfactual crisis scenarios.

**Status: research prototype, honestly validated.** This README states
the model's real, current validation status plainly — see
[Validation status](#validation-status) below — because a repository
claiming otherwise would not survive a reviewer re-running the code
(this happened once already during development; see
[`docs/validation/PHASE2_VALIDATION_UPDATE.md`](docs/validation/PHASE2_VALIDATION_UPDATE.md)).
**For the honest, unoptimized answer to "is this a complete Digital
Twin?"** — evaluated as an independent ASABE reviewer would — see
[`docs/DIGITAL_TWIN_COMPLETENESS_AUDIT.md`](docs/DIGITAL_TWIN_COMPLETENESS_AUDIT.md).

## What this is

- A Mesa-based (Python) agent-based simulation of food production, trade,
  reserves, energy-food coupling, and systemic-overload dynamics
  (Homer-Dixon "Limited Fuse, Big Bang" framework), calibrated against
  real FAO/World Bank/OWID/ND-GAIN data.
- A FastAPI backend exposing ~30 endpoints for running scenarios,
  comparing policies, and querying per-node/per-scenario results.
- A Next.js frontend (Experiment Studio, Countries browser, Policy Lab)
  for interactive exploration.
- A policy-search layer that answers "what combination of interventions,
  across which countries, minimises population at risk under a given
  crisis?" — via combinatorial search over reserve mandates, trade
  diversification, food aid, tariffs, climate adaptation funding, and
  more.

## What this is not (yet)

- **Not a production forecasting tool.** Peak-price retrodiction against
  real historical crises currently fails on 3 of 4 scored episodes (see
  below) — the model reproduces the right *shape* of crises but
  overshoots price magnitude, traced to a specific, documented mechanism
  (not a mystery — see [Open scientific issues](#open-scientific-issues)).
- **Not calibrated on real environmental data.** Rainfall, temperature,
  fertilizer trade, and water-withdrawal drivers are real, tested
  *mechanisms* running on clearly-labelled *synthetic placeholder* data
  — see [`docs/architecture/DIGITAL_TWIN_ARCHITECTURE.md`](docs/architecture/DIGITAL_TWIN_ARCHITECTURE.md)
  Section 12 for exactly which real data sources (CHIRPS, IFA, FAO
  AQUASTAT) would need to be acquired before this changes.
- **Not cost-constrained.** The policy-search layer's budget model is
  explicitly illustrative (arbitrary units, not currency) — no real
  cost-of-intervention data was sourced.

## Quick start

See [`INSTALL.md`](INSTALL.md) for full setup. Short version:

```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
# -> http://localhost:3000
```

Or via Docker: `docker-compose up` from the repository root.

## Repository structure

```
backend/          FastAPI application (app/main.py, model_bridge.py, ...)
frontend/          Next.js application (Experiment Studio, Policy Lab, ...)
model/             The canonical scientific model (Mesa ABM) + real data
  src/             model.py, agent.py, trade.py, stc_engine.py, ...
  data/            -> symlink to /data (single source of truth)
data/              Raw + processed calibration data (FAO, World Bank, OWID, ND-GAIN)
docs/              Full documentation suite (see below)
tests/             pytest suites (model/ and api/)
scripts/           Standalone reproducibility/investigation scripts
deployment/        Dockerfiles; see deployment/README.md for what's real vs. proposed
publication/       Paper/report outlines for conference & journal submission
examples/          Minimal runnable usage examples
```

## Documentation map

| Document | What it covers |
|---|---|
| [`INSTALL.md`](INSTALL.md) | Full setup, both local and Docker |
| [`USER_GUIDE.md`](USER_GUIDE.md) | Using the frontend and API as a researcher |
| [`DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) | Codebase conventions, how to add a scenario/lever/driver |
| [`docs/architecture/SCIENTIFIC_DESIGN_SPECIFICATION.md`](docs/architecture/SCIENTIFIC_DESIGN_SPECIFICATION.md) | The canonical 20-section blueprint: equations, state variables, API contracts, DB schema |
| [`docs/architecture/CAUSAL_DECOMPOSITION.md`](docs/architecture/CAUSAL_DECOMPOSITION.md) | Every subsystem's inputs/outputs/feedbacks/stability, with a diagram |
| [`docs/agents/`](docs/agents/) | **One real, data-generated profile per node** (35 files) — state, policies, trade, climate, resources, risk |
| [`docs/policies/`](docs/policies/) | **One document per implemented policy lever** (11), extracted directly from source code |
| [`docs/global_policies/`](docs/global_policies/) | Real global-scope mechanisms, and an honest accounting of proposed-but-not-implemented ones |
| [`docs/nodes/NODE_DOCUMENTATION.md`](docs/nodes/NODE_DOCUMENTATION.md) | Narrative-form node documentation (predates the per-agent files above) |
| [`docs/scenarios/SCENARIO_CATALOGUE.md`](docs/scenarios/SCENARIO_CATALOGUE.md) | 5 historical + 5 counterfactual scenarios, real Monte Carlo results |
| [`docs/validation/`](docs/validation/) | The full, honest validation history — including the corrections |
| [`docs/IMPLEMENTATION_AUDIT.md`](docs/IMPLEMENTATION_AUDIT.md) | What's actually implemented vs. specified, file-by-file |
| [`docs/TRACEABILITY_MATRIX.md`](docs/TRACEABILITY_MATRIX.md) | Requirement → file → function → test → doc, for every phase of work |
| [`docs/implementation/`](docs/implementation/) | Phase-by-phase engineering reports (Phases A–E), each with real test results |
| [`docs/DIGITAL_TWIN_COMPLETENESS_AUDIT.md`](docs/DIGITAL_TWIN_COMPLETENESS_AUDIT.md) | **Read this for the honest "is this a complete Digital Twin?" verdict**, a version roadmap, and a full gap analysis |
| [`docs/POLICY_LAB_COMPLIANCE.md`](docs/POLICY_LAB_COMPLIANCE.md) | Verification that the frontend exposes only real policies |
| [`docs/FINAL_AUDIT.md`](docs/FINAL_AUDIT.md) | Dead code, duplicates, broken links — a real mechanical audit |
| [`publication/`](publication/) | Paper outline and reviewer FAQ, grounded in what actually exists |
| [`LIMITATIONS.md`](LIMITATIONS.md) | Every known gap, in one place |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed, when, and why |

## Validation status

From the most recent full retrodiction run (`model/data/processed/retrodiction_scores.json`,
regenerable via `model/src/regenerate_all.py`), POM (Pattern-Oriented
Modelling) score = **0.30** against a target of ≥0.70:

| Episode | Peak-FPI error | Export-ban rate | Population at risk |
|---|---|---|---|
| 2008 crisis | 41.2% (fail) | pass | fail |
| 2010-11 Russia/Arab Spring | 163.2% (fail) | fail | pass |
| 2019-20 COVID | 62.4% (fail) | pass | pass |
| 2022 Ukraine | 109.2% (fail) | pass | pass |

**This is worse than an earlier-reported figure** (9.1% error on 2022,
reported mid-session, later found to be a step-counting measurement
artefact — corrected in
[`docs/validation/PHASE2_VALIDATION_UPDATE.md`](docs/validation/PHASE2_VALIDATION_UPDATE.md)).
Population-at-risk is the strongest metric (3/4 pass) and is what the
policy-optimisation layer uses as its objective, deliberately, for that
reason.

## Open scientific issues

The single highest-priority open item: the RC (Rigidity Cycle) price
amplification mechanism has no intrinsic negative feedback — see
[`docs/architecture/CAUSAL_DECOMPOSITION.md`](docs/architecture/CAUSAL_DECOMPOSITION.md)
Section 1 for the full mechanism trace. This is why price-magnitude
retrodiction currently fails while population-at-risk mostly passes.
Kept deliberately open (not silently tuned around) per this project's
own working discipline — see
[`docs/validation/PHASE2_5_MERGE_CHANGE_REPORT.md`](docs/validation/PHASE2_5_MERGE_CHANGE_REPORT.md)
for the reasoning.

## Citation

See [`CITATION.cff`](CITATION.cff).

## License

See [`LICENSE`](LICENSE).
