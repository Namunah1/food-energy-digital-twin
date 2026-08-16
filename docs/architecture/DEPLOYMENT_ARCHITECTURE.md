# Phase 5 — Production Deployment Architecture

## 1. Architectural decision, stated up front

**Do not distribute the 35 country-agents as independent services.**
Justification, grounded directly in the code (`trade.py`, `model.py`,
`stc_engine.py`):

- Every tick resolves a **synchronous fixed-point calculation** across the
  full 35×35 trade mesh (1,190 edges) — `execute_trade_step()` needs every
  agent's current σ_i, export regime, and price expectation simultaneously
  to compute gravity-model flows, and the STC engine's overload/cascade
  logic (`stc_engine.py::step()`) needs the *result* of that trade
  resolution before it can update FS_index/ES_index for the next tick.
  There is no point in the tick where two country-agents could correctly
  update independently without a barrier sync — the computation is a
  single coupled dynamical system, not 35 loosely-coupled actors.
- The actual hot-path computation (`trade.py`, `prices.py`, `stc_engine.py`)
  is already vectorised `numpy`/`pandas`/`networkx` operating over the full
  node set in one process. Splitting this into 35 pods would replace an
  in-memory matrix operation (microseconds) with 35 concurrent network
  calls per tick, each carrying serialization + round-trip latency — a
  regression of multiple orders of magnitude for zero scientific benefit,
  since no agent has private state or private compute that benefits from
  isolation.
- The genuine scaling need, visible directly in the existing code, is
  **replica-level parallelism**: `scenarios.py` already runs N_MC=20
  Monte Carlo replicas per scenario, `sensitivity.py` runs 96 (OAT) + up to
  1,664 (Sobol) independent parameter-sweep runs, and `retrodiction.py`
  runs 30 MC replicas per historical episode. These are **embarrassingly
  parallel across whole-simulation instances** — this is where Kubernetes
  adds real value.

This directly implements your Phase 5 instruction: *"Choose the
architecture that best matches the actual simulation. Do NOT distribute
agents unless technically justified. If simulation-level parallelism is
superior, explain why."* — the above is that justification, derived from
the code, not asserted.

---

## 2. Target architecture

```
                        ┌─────────────────────┐
   Browser (Next.js) ── │   NGINX Ingress      │
                        │  (TLS, WS upgrade)   │
                        └──────────┬───────────┘
                                   │
                   ┌───────────────┴────────────────┐
                   │                                 │
          ┌────────▼────────┐              ┌─────────▼─────────┐
          │  API Gateway      │              │  WebSocket Gateway  │
          │  (FastAPI, stateless,│           │ (FastAPI, subscribes│
          │   HPA on CPU/RPS)  │              │  to Redis Streams)  │
          └────────┬──────────┘              └─────────▲──────────┘
                   │ enqueue job                        │ publish tick
          ┌────────▼──────────┐              ┌──────────┴──────────┐
          │  Redis / NATS      │◄─────────────┤  Simulation Worker   │
          │  JetStream         │   tick events │  Deployment (HPA on  │
          │  (job queue +      │               │  queue depth)        │
          │   pub/sub bus)     │               │  = the existing 35-  │
          └────────┬──────────┘               │  agent Mesa model,   │
                   │                            │  ONE model instance  │
          ┌────────▼──────────┐                │  per pod, per run    │
          │  Postgres           │               └──────────────────────┘
          │ (experiments,       │
          │  scenario configs,  │
          │  replaces SQLite)   │
          └─────────────────────┘

          ┌─────────────────────────────────────────────┐
          │ Observability: Prometheus + Grafana + OTel    │
          │ scraping /metrics from every pod              │
          └─────────────────────────────────────────────┘
```

### 2.1 Simulation Worker (the core compute unit)
- **One container image**, built once from the existing `backend/Dockerfile`
  plus the vendored `model_src/`. No per-country environment variables —
  the *whole 35-node model* is the unit of replication, not a country.
- Each worker pod pulls one job (a scenario+seed+MC-replica triple) off the
  queue, runs `FoodEnergyModel` to completion in-process exactly as it does
  today, and streams tick-level state (via a small callback added to
  `model.step()`) to Redis Streams for the WebSocket gateway to pick up.
- **Resource requests/limits** — the workload is CPU-bound and
  numpy-vectorized, not memory-heavy (35 nodes × ~20 state vars is trivial
  memory). Sized from what the code actually does (a 30-step run with 20 MC
  replicas today; Sobol runs hit 1,664 replicas):
  - `requests`: 500m CPU / 512Mi memory (baseline single-replica run)
  - `limits`: 2000m CPU / 1Gi memory (headroom for a burst Sobol batch
    within one pod if you choose to batch replicas per pod rather than
    1:1 replica:pod — see 2.3)
- **HorizontalPodAutoscaler** on **queue depth** (via KEDA + the Redis/NATS
  queue length metric), not CPU utilization — CPU-based scaling reacts too
  late for a burst of 96–1,664 queued Sobol jobs; queue-depth-based scaling
  reacts immediately when a large sweep is submitted, and scales back to
  zero (or a small floor) when idle. This is the correct trigger for "CPU
  spikes when many replicas run simultaneously" — the spike is bursty and
  job-driven, not steady-state, so KEDA scale-to-zero is a real cost
  saving over a fixed Deployment replica count.

### 2.2 Why a job queue instead of direct HTTP-triggered runs
The current `model_bridge.py` computes synchronously on each API request
(`mb.get_baseline_model(...)`), cached with `functools`. That's fine for a
dashboard-scale demo but breaks down for: (a) Monte Carlo batches that take
minutes, (b) concurrent users triggering overlapping runs, (c) the
requirement for "real-time" streaming during long crisis-scenario runs. A
job queue (NATS JetStream is a good fit here — lighter-weight than Kafka,
has native pub/sub *and* durable queue semantics, avoiding the need to run
both Redis and a separate message bus) decouples "accept the request" from
"run the simulation," and the pub/sub side is what the WebSocket gateway
subscribes to for live tick streaming.

### 2.3 Batching replicas within a pod (important cost optimization)
Because a single worker pod can already loop over N_MC replicas in-process
(exactly as `scenarios.py` does today with `N_MC=20`), **you do not need
1,664 pods for a full Sobol run.** Batch replicas per job (e.g., 20–50
replicas/pod) and let HPA scale the number of *batches*, not the number of
*replicas*. This mirrors what the code already does and avoids
per-pod-startup overhead (image pull, Python import, data-file load) being
paid 1,664 times instead of ~30–80 times.

### 2.4 Experiment workers vs. interactive workers (two node pools)
Split the Deployment into two, both running the same image:
- **Interactive pool**: small, low-latency, always-warm (min replicas ≥ 1),
  serves single baseline/scenario runs for the dashboard (`/api/baseline/*`,
  `/api/scenarios` in the current `main.py`).
- **Batch/experiment pool**: scale-to-zero, KEDA-triggered, serves Sobol
  sweeps, worst-case discovery (`worst_case_discovery()`), and multi-seed
  historical retrodiction batches — exactly the workloads that currently
  take minutes in `regenerate_all.py`.

### 2.5 Data layer
- `data/processed/*.csv` and `network_weights.csv` — read-only, small
  (a few MB total). Bake into the image or mount from a read-only PVC /
  object-storage-backed volume (S3/GCS + CSI driver) so a data-pipeline
  refresh doesn't require an image rebuild.
- Replace `experiments.sqlite3` (single-writer, doesn't survive pod
  restarts or scale beyond one replica) with **Postgres** for the
  experiment store and notebook store — this is a real correctness issue
  today (`experiment_store.py`/`notebook_store.py` writing to local SQLite
  inside an ephemeral container) that must be fixed before any multi-replica
  deployment, independent of the scaling discussion above.

---

## 3. Observability

- **Prometheus**: instrument `model.step()` and `MetricsCollector` to
  expose per-node gauges matching your original request —
  `food_reserve_metric{country="India",run_id="..."}`,
  `inflation_index{country="US",run_id="..."}` — plus job-queue depth,
  worker pod count, and run duration histograms.
- **Grafana**: one dashboard per scenario class (baseline, historical
  retrodiction, named scenarios, Sobol sweeps), with per-node panels
  templated by the `country` label so 35 nodes don't require 35 separate
  panels.
- **OpenTelemetry**: trace a single simulation run end-to-end — job
  enqueue → worker pickup → per-tick spans → completion — so a slow Sobol
  batch can be diagnosed (is it queue wait time, or actual compute time?)
  without guessing. This matters specifically because the existing
  `sensitivity.py`/`regenerate_all.py` pipeline has known historical bugs
  (documented in `FINAL_VERIFICATION_REPORT.md`, items 4–13) around
  silently wrong values propagating through multi-stage pipelines —
  distributed tracing is a concrete mitigation against that failure class
  recurring in production, not just a monitoring nicety.

---

## 4. What does *not* change from the current architecture

- The scientific core (`model.py`, `agent.py`, `trade.py`, `stc_engine.py`,
  `scenarios.py`) is **vendored and unmodified**, exactly as
  `model_bridge.py`'s own docstring states today ("does not compute,
  approximate, or reimplement any scientific quantity"). This principle
  should hold under the new architecture too — the worker pod runs the
  same `FoodEnergyModel` class, just orchestrated by a queue instead of a
  synchronous HTTP handler.
- The Next.js frontend's data-fetching contract barely changes: it already
  expects REST for static data and (per your original request) should move
  to WebSocket for live ticks — the WebSocket gateway described above is a
  thin addition, not a rewrite.

---

## 5. What would justify per-agent distribution (for completeness, not because it applies here)

If a future version of this project genuinely needed independent
per-country policy modules — e.g., different research teams each owning
and iterating on one country's behavioural model, deployed and versioned
independently of the others — that would be a real justification for an
actor-model decomposition (e.g., Ray actors, one per country, with a
barrier-synchronized tick coordinator). Nothing in the current codebase
indicates that need: all 35 `CountryAgent` instances share one behaviour
class with per-node *parameters*, not per-node *code*. If this changes,
revisit this section specifically — the rest of the architecture (queue,
observability, gateway) does not need to change to accommodate it.
