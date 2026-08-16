# Installation

Every command below was actually run and verified during this
consolidation pass, not written from assumption.

## Prerequisites

- Python 3.12 (the model requires **Mesa pinned to exactly 3.1.4** —
  see the warning below, this is not optional)
- Node.js 18+ and npm
- (Optional) Docker + Docker Compose for the containerised path

## Critical: the Mesa version pin

`backend/requirements.txt` and `model/requirements.txt` (if present)
must pin `mesa==3.1.4`. **Do not install `mesa` unpinned.** Every Mesa
3.x release wraps `Model.step()` with its own auto-incrementing counter;
this codebase's `model.py` also increments its own step counter, and the
combination silently double-counts every simulated year unless exactly
this version is used — a real bug found and fixed during development
(see `docs/validation/PHASE2_5_MERGE_CHANGE_REPORT.md`). Mesa 2.x is
*also* incompatible, for an unrelated reason: this codebase's
`CountryAgent` uses the Mesa-3-only single-argument `Agent(model)`
constructor.

## Local setup

### 1. Backend

```bash
cd backend
pip install -r requirements.txt --break-system-packages   # or use a venv
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify: `curl http://localhost:8000/api/health` should return
`{"status":"ok"}`.

### 2. Frontend

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Visit `http://localhost:3000`. The Policy Lab is at `/policy-lab`.

### 3. Run the test suites

```bash
# From repository root
pip install pytest --break-system-packages
python3 -m pytest tests/api/test_endpoints.py -v      # ~35s, 10 tests
python3 -m pytest tests/model/ -v                       # several minutes, 46 tests
```

Both suites were run and passed during this consolidation (see
`docs/implementation/` for the full per-phase results).

### 4. Regenerate the validation data (optional, ~3 minutes)

```bash
cd model/src
python3 -c "
from retrodiction import run_phase8
result = run_phase8(n_steps=25, n_mc=30, verbose=True)
print('POM score:', result['pom_score'])
"
```

This writes to `model/data/processed/` (via the `data` symlink, real
files live in the top-level `/data`). Expect `POM score: 0.3` — if you
get a different number, something in your environment differs from what
this consolidation verified (check the Mesa version first).

## Docker

```bash
docker-compose up
```

Builds and runs both services per `docker-compose.yml` at the repository
root. Backend on `:8000`, frontend on `:3000`. This is the **current,
real** deployment path — see `deployment/README.md` for what's
additionally proposed (Kubernetes, job queues) but not yet built.

## Known environment gotchas (found during this session, not hypothetical)

- **`pip install` needs `--break-system-packages`** on recent Debian/Ubuntu
  Python installs (PEP 668 externally-managed environment) — every
  install command in this project's development used this flag.
- **The model's own internal path resolution expects data at
  `model/data`**, not the top-level `/data` directory — this is why
  `model/data` is a symlink, not a real directory. Do not delete or
  replace it with a real folder; `model/src/model.py`'s own path logic
  will silently look in the wrong place.
- **Tests in `tests/model/` rely on a same-directory import convention**
  (`sys.path.insert(0, '.')` inside each test file) inherited from the
  original codebase. `tests/model/conftest.py` handles this for pytest;
  running a test file directly with `python3 test_x.py` requires being
  inside `model/src/` (or copying the test file there first).
