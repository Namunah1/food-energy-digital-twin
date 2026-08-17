"""
main.py — FastAPI application for the Food-Energy Systemic Risk platform.

All scientific computation happens inside model_bridge.py, which calls
directly into the vendored, unmodified ABM (model_src/). This file only
handles HTTP/WebSocket plumbing, validation, and JSON shaping.
"""
import asyncio
import json
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Gauge
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import model_bridge as mb
from .schemas import (
    SimulationRequest, ResearchScenarioRequest, ComparisonRequest, AdvisorRequest,
    ProjectionRequest, CascadeTraceRequest, PolicyOptimizationRequest, PolicySearchRequest,
    NodeLevelSearchRequest,
    ExperimentCreateRequest, ExperimentBranchRequest, AnnotationRequest,
    NotebookCreateRequest, NotebookEntryCreateRequest, NotebookEntryUpdateRequest,
)
from . import experiment as _experiment
from . import experiment_store as _experiment_store
from . import notebook as _notebook
from . import health as _health
from fastapi.responses import PlainTextResponse
from . import advisor as _advisor
from . import ai_providers as _ai_providers


app = FastAPI(
    title="Food-Energy Systemic Risk Assessment API",
    description="REST/WebSocket API over the Gambhir/Homer-Dixon-framework "
                "Food-Energy Systemic Risk Agent-Based Model.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # dev default; tighten in deployment (see README)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

# Scientific model metrics exposed to Prometheus.
# These values come directly from the ABM metrics dataframe.
model_gfs = Gauge(
    "food_energy_gfs",
    "Global Food Security metric",
)

model_undernourished = Gauge(
    "food_energy_undernourished",
    "Fraction of population that is undernourished",
)

model_trade_collapse = Gauge(
    "food_energy_trade_collapse",
    "Trade collapse metric",
)

model_export_ban_rate = Gauge(
    "food_energy_export_ban_rate",
    "Fraction of nodes under export restrictions",
)

model_par_millions = Gauge(
    "food_energy_par_millions",
    "Population at risk in millions",
)

model_price_index = Gauge(
    "food_energy_price_index",
    "Food price index",
)

model_price_ratio = Gauge(
    "food_energy_price_ratio",
    "Food price ratio",
)

model_sav_scale = Gauge(
    "food_energy_sav_scale",
    "Strategic adaptive vulnerability scale",
)

model_mean_fs_index = Gauge(
    "food_energy_mean_fs_index",
    "Mean food security index",
)

model_mean_es_index = Gauge(
    "food_energy_mean_es_index",
    "Mean energy security index",
)

model_overload_food = Gauge(
    "food_energy_overload_food",
    "Number of food-overloaded nodes",
)

model_overload_energy = Gauge(
    "food_energy_overload_energy",
    "Number of energy-overloaded nodes",
)

def update_model_metrics(metrics: dict) -> None:
    """Expose the latest ABM metrics to Prometheus."""

    model_gfs.set(metrics.get("GFS", 0.0))
    model_undernourished.set(metrics.get("U_undernourished", 0.0))
    model_trade_collapse.set(metrics.get("TC_trade_collapse", 0.0))
    model_export_ban_rate.set(metrics.get("EB_export_ban_rate", 0.0))
    model_par_millions.set(metrics.get("PAR_millions", 0.0))
    model_price_index.set(metrics.get("price_index", 0.0))
    model_price_ratio.set(metrics.get("price_ratio", 0.0))
    model_sav_scale.set(metrics.get("SAV_scale", 0.0))
    model_mean_fs_index.set(metrics.get("mean_FS_index", 0.0))
    model_mean_es_index.set(metrics.get("mean_ES_index", 0.0))
    model_overload_food.set(metrics.get("n_overload_food", 0.0))
    model_overload_energy.set(metrics.get("n_overload_energy", 0.0))


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ── Static reference data ───────────────────────────────────────────────────

@app.get("/api/countries")
def get_countries():
    return mb.list_countries()


@app.get("/api/scenarios")
def get_scenarios():
    return mb.list_scenario_specs()


# ── Baseline dashboard / map / network state ────────────────────────────────

@app.get("/api/baseline/metrics")
def get_baseline_metrics(steps: int = Query(10, ge=1, le=30), seed: int = 42):
    model = mb.get_baseline_model(steps=steps, seed=seed)
    ts = mb.global_metrics_timeseries(model)

    if ts:
        update_model_metrics(ts[-1])

    return {
        "timeseries": ts,
        "summary": model.summary(),
        "current": ts[-1] if ts else None,
    }



@app.get("/api/baseline/nodes")
def get_baseline_nodes(steps: int = Query(10, ge=1, le=30), seed: int = 42):
    model = mb.get_baseline_model(steps=steps, seed=seed)
    return mb.node_state_snapshot(model)


@app.get("/api/network")
def get_network(steps: int = Query(10, ge=1, le=30), seed: int = 42):
    model = mb.get_baseline_model(steps=steps, seed=seed)
    return {
        "nodes": mb.node_state_snapshot(model),
        "edges": mb.network_edges(model),
    }


@app.get("/api/country/{name}")
def get_country(name: str, steps: int = Query(10, ge=1, le=30), seed: int = 42):
    profile = mb.country_profile(name, steps=steps, seed=seed)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Unknown country/node: {name}")
    return profile


@app.get("/api/country/{name}/history")
def get_country_history(name: str):
    history = mb.country_history(name)
    if history is None:
        raise HTTPException(status_code=404, detail=f"Unknown country/node: {name}")
    return history


# ── Research scenarios (S0-S5, Monte Carlo) ─────────────────────────────────

@app.post("/api/research_scenario")
def post_research_scenario(req: ResearchScenarioRequest):
    valid_names = {s["name"] for s in mb.list_scenario_specs()}
    if req.name not in valid_names:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {req.name}")
    return mb.run_research_scenario(req.name, n_mc=req.n_mc, n_steps=req.n_steps, seed=req.seed)


# ── Historical replay ────────────────────────────────────────────────────────

@app.get("/api/historical/episodes")
def get_historical_episodes():
    return mb.list_historical_episodes()


@app.get("/api/historical/{key}")
def get_historical_episode(key: str, n_mc: int = Query(6, ge=1, le=30), n_steps: int = Query(25, ge=10, le=40)):
    if key in mb.DESCRIPTIVE_EPISODES:
        result = mb.run_descriptive_episode(key, n_steps=n_steps)
    else:
        result = mb.run_historical_episode(key, n_mc=n_mc, n_steps=n_steps)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown episode: {key}")
    return result


# ── Scenario Lab: custom simulation (REST, synchronous) ─────────────────────

@app.post("/api/run_simulation")
def post_run_simulation(req: SimulationRequest):
    shocks = [s.model_dump() for s in req.shocks]
    result = mb.run_custom_simulation(
        shocks=shocks, responses=req.responses, n_steps=req.n_steps, seed=req.seed,
        capture_snapshots=req.capture_snapshots,
    )
    if req.compare_baseline:
        result["baseline"] = mb.run_baseline_comparison(n_steps=req.n_steps, seed=req.seed)
    return result


# ── Scenario Lab: custom simulation (WebSocket, streamed step-by-step) ──────

@app.websocket("/ws/simulate")
async def ws_simulate(websocket: WebSocket):
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        payload = json.loads(raw)
        req = SimulationRequest(**payload)
        shocks = [s.model_dump() if hasattr(s, "model_dump") else s for s in req.shocks]

        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def step_callback(step: int, rec: dict):
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "step", "step": step, "metrics": rec})

        async def run_in_thread():
            def _run():
                result = mb.run_custom_simulation(
                    shocks=shocks, responses=req.responses, n_steps=req.n_steps,
                    seed=req.seed, step_callback=step_callback,
                )
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "done", "result": result})
            await asyncio.to_thread(_run)

        run_task = asyncio.create_task(run_in_thread())

        while True:
            item = await queue.get()
            await websocket.send_text(json.dumps(item, default=str))
            if item["type"] == "done":
                break

        await run_task
    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── Comparison mode ──────────────────────────────────────────────────────────

@app.post("/api/compare")
def post_compare(req: ComparisonRequest):
    valid_names = {s["name"] for s in mb.list_scenario_specs()}
    runs = []
    for r in req.runs:
        if r.kind == "research":
            if r.name not in valid_names:
                raise HTTPException(status_code=404, detail=f"Unknown scenario: {r.name}")
            runs.append({"kind": "research", "name": r.name})
        else:
            runs.append({
                "kind": "custom",
                "id": r.id or "custom",
                "label": r.label or "Custom scenario",
                "shocks": [sh.model_dump() for sh in r.shocks],
                "responses": r.responses,
            })
    return mb.run_comparison(runs, n_steps=req.n_steps, seed=req.seed)


# ── Network centrality --------------------------------------------------------

@app.get("/api/network/centrality")
def get_network_centrality(steps: int = Query(10, ge=1, le=30), seed: int = 42):
    return mb.network_with_centrality(steps=steps, seed=seed)


# ── Time machine ---------------------------------------------------------------

@app.get("/api/time_machine")
def get_time_machine(end_year: int = Query(2050, ge=2025, le=2060), seed: int = 42):
    return mb.time_machine(end_year=end_year, seed=seed)


@app.get("/api/real_year/{year}")
def get_real_year(year: int):
    result = mb.real_year_snapshot(year)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No real panel data for year {year} (coverage: 2000-{mb.NODE_PANEL_MAX_YEAR})")
    return result


# ── AI Policy Advisor ─────────────────────────────────────────────────────────

@app.get("/api/advisor/providers")
def get_advisor_providers():
    return _ai_providers.list_providers()


@app.post("/api/advisor/ask")
def post_advisor_ask(req: AdvisorRequest):
    return _advisor.answer_question(req.question)


# ── Custom projection (year + scenario -> number + reasoning) ────────────────

@app.post("/api/project")
def post_project(req: ProjectionRequest):
    shocks = [s.model_dump() for s in req.shocks]
    result = mb.run_custom_projection(
        shocks=shocks, responses=req.responses, target_year=req.target_year,
        start_year=req.start_year, n_mc=req.n_mc, seed=req.seed,
    )

    explanation = None
    provider_name = None
    if req.explain:
        stats = result["stats"]
        grounding_data = {
            "start_year": result["start_year"],
            "target_year": result["target_year"],
            "n_steps": result["n_steps"],
            "n_mc": result["n_mc"],
            "used_real_anchor": result["used_real_anchor"],
            "price_index_mean": stats["max_price_index"]["mean"],
            "price_index_std": stats["max_price_index"]["std"],
            "price_index_p5": stats["max_price_index"]["p5"],
            "price_index_p95": stats["max_price_index"]["p95"],
            "par_bn_mean": stats["max_PAR_millions"]["mean"] / 1000,
            "par_bn_std": stats["max_PAR_millions"]["std"] / 1000,
            "baseline_price_index": result["baseline_summary"]["max_price_index"],
            "baseline_par_bn": result["baseline_summary"]["max_PAR_millions"] / 1000,
            "attribution": result["attribution"][:5],
        }
        advisor_result = _advisor._finalize(
            f"Project to {req.target_year} with the given scenario",
            {"intent": "custom_projection", "data": grounding_data},
        )
        explanation = advisor_result["answer"]
        provider_name = advisor_result["provider"]

    result["explanation"] = explanation
    result["explanation_provider"] = provider_name
    return result


# ── Shock library & cascade trace ─────────────────────────────────────────────

@app.get("/api/shock_library")
def get_shock_library():
    return mb.get_shock_library()


@app.post("/api/cascade_trace")
def post_cascade_trace(req: CascadeTraceRequest):
    shocks = [s.model_dump() for s in req.shocks]
    return mb.cascade_trace(shocks, req.responses, req.start_year, req.n_steps, req.seed)


# ── Policy optimization ───────────────────────────────────────────────────────

@app.post("/api/policy_optimization")
def post_policy_optimization(req: PolicyOptimizationRequest):
    shocks = [s.model_dump() for s in req.shocks]
    return mb.run_policy_optimization(shocks, req.start_year, req.n_steps, req.seed)


@app.post("/api/policy_search")
def post_policy_search(req: PolicySearchRequest):
    """
    PHASE A/B/D (this session): combinatorial + intensity + node-level
    policy search. Extends /api/policy_optimization above (unchanged,
    still available) rather than replacing it.
    """
    shocks = [s.model_dump() for s in req.shocks]
    custom_levers = [c.model_dump(exclude_none=True) for c in req.custom_levers]
    return mb.run_policy_search(
        shocks, req.start_year, req.n_steps,
        n_random=req.n_random, include_fixed_levers=req.include_fixed_levers,
        custom_levers=custom_levers,
        include_node_targeted_sampling=req.include_node_targeted_sampling,
        node_pool=req.node_pool, max_budget=req.max_budget, seed=req.seed,
    )


@app.post("/api/policy_search/node_level")
def post_node_level_policy_search(req: NodeLevelSearchRequest):
    """
    PHASE D (this session): "which countries should receive [lever] to
    minimise global PAR" — a focused search over node targeting for one
    specific lever type, distinct from the mixed general search above.

    BUGFIX (found during final consolidation, this session's real pytest
    suite, tests/api/test_endpoints.py): an unknown lever_type previously
    propagated scenarios.node_level_policy_search()'s ValueError as an
    unhandled exception (crashing to a generic 500 with no useful message
    in a real deployment). Now caught and returned as a clean 400 with
    the actual list of valid lever types, matching how every other
    validation error in this file is surfaced.
    """
    shocks = [s.model_dump() for s in req.shocks]
    try:
        return mb.run_node_level_policy_search(
            req.lever_type, req.node_pool, shocks, req.start_year, req.n_steps,
            n_random=req.n_random, max_budget=req.max_budget, seed=req.seed,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Experiment Studio: canonical entry point ──────────────────────────────────
# One Experiment object (world state + shock spec + interventions +
# uncertainty config + metadata) in, one ExperimentResult out, regardless of
# mode. This supersedes calling the individual simulation endpoints above
# directly from the frontend -- they remain for internal reuse and backward
# compatibility, but new frontend code should talk to /api/experiments only.

@app.post("/api/experiments")
def post_create_experiment(req: ExperimentCreateRequest):
    return _experiment.create_experiment(req.model_dump())


@app.get("/api/experiments")
def get_list_experiments(limit: int = Query(100, ge=1, le=500)):
    return _experiment_store.list_experiments(limit=limit)


@app.get("/api/experiments/{experiment_id}")
def get_experiment(experiment_id: str):
    exp = _experiment_store.load_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail=f"Unknown experiment: {experiment_id}")
    return exp


@app.post("/api/experiments/{experiment_id}/branch")
def post_branch_experiment(experiment_id: str, req: ExperimentBranchRequest):
    overrides = {k: v for k, v in req.model_dump().items() if v is not None}
    if "shocks" in overrides:
        overrides["shocks"] = [s if isinstance(s, dict) else s for s in overrides["shocks"]]
    result = _experiment.branch_experiment(experiment_id, overrides)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown experiment: {experiment_id}")
    return result


@app.patch("/api/experiments/{experiment_id}/annotation")
def patch_experiment_annotation(experiment_id: str, req: AnnotationRequest):
    result = _experiment_store.update_annotation(experiment_id, req.annotation)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown experiment: {experiment_id}")
    return result


@app.delete("/api/experiments/{experiment_id}")
def delete_experiment(experiment_id: str):
    ok = _experiment_store.delete_experiment(experiment_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Unknown experiment: {experiment_id}")
    return {"deleted": True}


# ── Experiment Health ──────────────────────────────────────────────────────

@app.get("/api/experiments/{experiment_id}/health")
def get_experiment_health(experiment_id: str):
    exp = _experiment_store.load_experiment(experiment_id)
    if exp is None:
        raise HTTPException(status_code=404, detail=f"Unknown experiment: {experiment_id}")
    return _health.compute_health(exp)


# ── Scientific Notebook ────────────────────────────────────────────────────

@app.post("/api/notebooks")
def post_create_notebook(req: NotebookCreateRequest):
    return _notebook.create_notebook(req.title, req.description, req.author)


@app.get("/api/notebooks")
def get_list_notebooks():
    return _notebook.list_notebooks()


@app.get("/api/notebooks/{notebook_id}")
def get_notebook(notebook_id: str):
    nb = _notebook.get_notebook(notebook_id)
    if nb is None:
        raise HTTPException(status_code=404, detail=f"Unknown notebook: {notebook_id}")
    return nb


@app.delete("/api/notebooks/{notebook_id}")
def delete_notebook(notebook_id: str):
    if not _notebook.delete_notebook(notebook_id):
        raise HTTPException(status_code=404, detail=f"Unknown notebook: {notebook_id}")
    return {"deleted": True}


@app.post("/api/notebooks/{notebook_id}/entries")
def post_add_entry(notebook_id: str, req: NotebookEntryCreateRequest):
    entry = _notebook.add_entry(notebook_id, req.entry_type, req.experiment_ids, req.text)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown notebook: {notebook_id}")
    return entry


@app.patch("/api/notebooks/entries/{entry_id}")
def patch_entry(entry_id: str, req: NotebookEntryUpdateRequest):
    entry = _notebook.update_entry(entry_id, req.text)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unknown entry: {entry_id}")
    return entry


@app.delete("/api/notebooks/entries/{entry_id}")
def delete_entry(entry_id: str):
    if not _notebook.delete_entry(entry_id):
        raise HTTPException(status_code=404, detail=f"Unknown entry: {entry_id}")
    return {"deleted": True}


@app.get("/api/notebooks/{notebook_id}/export")
def export_notebook(notebook_id: str, format: str = Query("markdown", pattern="^(markdown|json)$")):
    if format == "json":
        data = _notebook.export_json(notebook_id)
        if data is None:
            raise HTTPException(status_code=404, detail=f"Unknown notebook: {notebook_id}")
        return data
    md = _notebook.export_markdown(notebook_id)
    if md is None:
        raise HTTPException(status_code=404, detail=f"Unknown notebook: {notebook_id}")
    return PlainTextResponse(md, media_type="text/markdown")
