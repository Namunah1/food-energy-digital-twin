# User Guide

For researchers using the platform via the frontend or API — not for
developers extending the model (see `DEVELOPER_GUIDE.md` for that).

## Via the frontend

- **Experiment Studio** (`/console`) — configure and run a scenario
  (baseline, historical retrodiction, or a custom shock combination),
  compare two runs side by side, see the `ExplanationPanel`'s crisis
  attribution breakdown per node.
- **Countries** (`/countries`) — browse all 35 nodes, their current
  calibrated values, and historical trends.
- **Policy Lab** (`/policy-lab`) — run a combinatorial policy search
  (which lever combination minimises population at risk) or a node-level
  search (which countries should receive a specific intervention).

## Via the API

Base URL: `http://localhost:8000` (or your deployed backend).

**Run a scenario:**
```bash
curl -X POST http://localhost:8000/api/run_simulation \
  -H "Content-Type: application/json" \
  -d '{"shocks": [{"shock_type": "climate_drought", "target_node": "Australia", "start_step": 2, "duration": 3, "severity": 0.48, "scope": 0.2}], "n_steps": 20}'
```

**Search for a good policy:**
```bash
curl -X POST http://localhost:8000/api/policy_search \
  -H "Content-Type: application/json" \
  -d '{"shocks": [...], "start_year": 2022, "n_steps": 15, "n_random": 20}'
```

**Find which countries should receive food aid:**
```bash
curl -X POST http://localhost:8000/api/policy_search/node_level \
  -H "Content-Type: application/json" \
  -d '{"lever_type": "food_aid", "node_pool": ["United States", "Argentina", "Pakistan", "Central Africa"], "shocks": [], "start_year": 2022, "n_steps": 15}'
```

Full endpoint list: read `backend/app/main.py` directly (every route is
declared with `@app.get`/`@app.post` near the top-level of the file) —
a complete, hand-written per-endpoint reference for all ~30 endpoints was
not produced this consolidation pass (see `LIMITATIONS.md` /
`docs/IMPLEMENTATION_AUDIT.md` for what exists); the routes and their
Pydantic request/response schemas (`backend/app/schemas.py`) are the
authoritative source and are self-documenting via FastAPI's automatic
`/docs` (Swagger UI) once the server is running.

## Interpreting results

- **`max_price_index`**: peak normalised FAO Food Price Index equivalent
  over the run. **Read this with the validation status in mind** — see
  `README.md`'s Validation status table; this metric currently
  overshoots real historical values.
- **`max_PAR_millions`**: peak population at risk, in millions. This is
  the model's strongest-validated metric (3/4 historical episodes pass)
  and what the policy-search layer optimises.
- **`population_saved_millions`** (policy search results): control run's
  PAR minus the candidate policy's PAR. Can be **negative** — a
  poorly-targeted policy can make things worse than doing nothing, and
  the search surfaces this rather than hiding it (see
  `docs/implementation/PHASE_D_IMPLEMENTATION_REPORT.md` for a real
  example).
- **`illustrative_cost`** / **`within_budget`**: NOT real currency — see
  `LIMITATIONS.md`.

## A note on synthetic vs. real data

If you attach `climate_drivers.ContinuousClimateDriver`,
`resource_drivers.FertilizerDriver`, or `resource_drivers.WaterStockDriver`
to a model instance without supplying real data, they run on clearly-
labelled synthetic placeholders. Check each module's docstring before
treating any result derived from them as a calibrated scientific claim.
