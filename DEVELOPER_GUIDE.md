# Developer Guide

## Core principle this codebase follows (and you should too)

**Extend, don't rewrite.** Every phase of this project's development
(see `CHANGELOG.md`) followed the same discipline: new functionality is
added as backward-compatible, `getattr`-defaulted, or `None`-default-slot
extensions to existing functions, verified byte-identical when unused.
Before adding anything, check `docs/IMPLEMENTATION_AUDIT.md` — it maps
every specification section to the file/function that already
implements (or partially implements) it, specifically to prevent
duplicate work.

## Adding a new policy lever

1. Write a factory function in `model/src/scenarios.py` following the
   existing pattern: `make_X_lever(params...) -> callable(model) -> None`.
   Set `lever.__name__` and `lever.lever_params` (used by the search
   layer's output labelling).
2. If it's node-targeted (needs a specific country), add it to
   `CUSTOM_LEVER_BUILDERS` so the API's `custom_levers` field and
   `node_level_policy_search()` can use it.
3. If it needs genuinely new state (not just modifying existing agent
   attributes), follow the `climate_drivers.py`/`resource_drivers.py`
   pattern: an optional `model.<x>_driver = None` slot, a `.step(model)`
   method, wired into `model.py`'s `step()` with a `None`-check guard.
4. Write a test that checks **both** backward compatibility (does the
   default/unset case reproduce prior behaviour exactly?) and the new
   mechanism's real effect (does a real before/after comparison show the
   expected direction of change?). See any `tests/model/test_phase_*.py`
   for the pattern.
5. Run the full retrodiction battery
   (`model/src/retrodiction.py::run_phase8`) as a regression gate before
   considering the change complete — every phase in this project's
   history did this, and it caught real problems every time it wasn't
   skipped.

## Adding a new environmental/resource driver

Read `docs/architecture/DIGITAL_TWIN_ARCHITECTURE.md` Part C first — it
specifies the equation, calibration confidence tier, and integration
point for each driver category (climate, soil, fertilizer, water) before
any of them were built. If you're adding a driver not covered there,
write the equivalent section first.

**Be honest about calibration confidence.** Every driver in this
codebase is tagged HIGH/MEDIUM/LOW confidence in its own docstring, and
LOW-confidence drivers explicitly say they should not be presented as
calibrated. Follow this convention — do not silently upgrade a
placeholder to "real" by removing the disclaimer.

## Modifying the core simulation loop (`model.py::step()`)

This is the highest-risk file in the codebase — every scenario runs
through it. Any change here **must** include:
1. A `getattr`/`None`-default check making the change a no-op when
   unused.
2. A determinism check (same seed, same result, twice).
3. The full retrodiction battery re-run, compared against the current
   baseline in `docs/validation/` (currently POM=0.30,
   FPI errors 41.15%/109.24%/163.21%/62.41%). If your change moves these
   numbers, that's not automatically wrong — but it must be reported,
   not silently absorbed (see `docs/validation/PHASE2_5_MERGE_CHANGE_REPORT.md`
   for the precedent: a change that made validation *worse* was still
   merged and reported plainly, because it was scientifically justified).

## Running tests

```bash
# From repo root
python3 -m pytest tests/api/test_endpoints.py -v
python3 -m pytest tests/model/ -v
```

`tests/model/conftest.py` adds `model/src` to the import path
automatically. See `INSTALL.md`'s "known environment gotchas" if you hit
import errors running a test file directly rather than via pytest.

## Backend/frontend conventions

- Backend: every new endpoint follows the pattern in `backend/app/main.py`
  — a thin route handler calling a `model_bridge.py` function that
  translates the request and delegates to the canonical scientific
  module (`model/src/`). **`model_bridge.py` should never contain
  scientific computation itself** — this is a strict, deliberate
  separation maintained since the project's original design.
- Frontend: new pages go in `frontend/src/app/<route>/page.tsx`
  (Next.js App Router), reusing `frontend/src/components/ui/` primitives
  and the existing Tailwind design tokens (`ink-1`/`ink-2`/`ink-3`,
  `teal`, `panel-2`, `hairline` — see any existing page for examples,
  not a separate design-tokens file). API client bindings go in
  `frontend/src/lib/api.ts`, following the existing `postJSON`/`getJSON`
  pattern.

## Known conventions you should not "fix" without understanding why first

- **The one-step lag in export policy and STC overload evaluation**
  (`model.py::step()`'s comments explain this explicitly) is intentional
  — it avoids requiring simultaneous equation solving within a single
  tick. Don't "simplify" this without reading
  `docs/architecture/CAUSAL_DECOMPOSITION.md` first.
- **`agent.py`'s FS_index clips to `[0, 2]`, not `[0, 1]`** — this is a
  real, identified design concern (Section 13.2 of the causal
  decomposition), not an oversight, and changing it without
  understanding the overload-ratio dynamic will silently change every
  historical scenario's behaviour.
