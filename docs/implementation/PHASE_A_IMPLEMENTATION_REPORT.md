# Phase A Implementation Report — Policy Optimisation Extension

## What was implemented

1. **Synchronised the deployment backend's vendored model** with the
   canonical, verified copy from Phase 2.5 (Mesa step-counting fix + STC
   sequencing fix) — `model.py`, `stc_engine.py`. Confirmed identical
   behaviour post-sync (steps=1, n_overloaded=8, matching the canonical
   copy exactly). Pinned `mesa==3.1.4` in both `requirements.txt` files
   (previously `mesa>=2.0`, which silently resolves to a version that
   reintroduces the double-increment bug) — this was a necessary
   prerequisite, not scope creep: building new features on an
   unsynchronised, unpinned deployment target would have meant Phase A's
   own tests could pass locally and still fail in deployment.

2. **`scenarios.py`: four parameterised lever factories**, each an
   additive wrapper that reuses an existing mechanism unchanged:
   `make_reserve_mandate_lever(target_months)`,
   `make_trade_diversification_lever(rho_cut_frac, boost_edge_frac,
   boost_multiplier)` (backed by a new `_trade_diversification_param()`
   generalisation, with the original `_trade_diversification()` now a
   thin wrapper calling it with identical original defaults),
   `make_trader_regulation_lever(margin_cap)`,
   `make_renewable_push_lever(boost_multiplier, cap)`, plus
   `_combine_levers()` to compose any of the above into one response
   function (this is how lever *combinations* are represented — sequential
   application of existing single-mechanism functions, no new combination
   logic needed).

3. **`scenarios.policy_search()`** — the actual search, extending
   `worst_case_discovery()`'s sample→run→score→rank pattern (per the
   audit's explicit recommendation), retargeted to the policy action space
   and objective-flipped (maximise `population_saved_millions`, i.e.
   minimise PAR, per the Digital Twin spec Section 10). Includes the 5
   original fixed levers as a subset plus N randomly-sampled combinations
   and intensities within documented bounds.

4. **API layer**: new `PolicySearchRequest` schema (`schemas.py`), new
   `model_bridge.run_policy_search()` (a thin translation wrapper,
   identical design principle to every existing `model_bridge` function —
   no scientific computation in this layer), new `POST /api/policy_search`
   endpoint (`main.py`) — `/api/policy_optimization` is untouched and still
   works, confirmed by direct test.

## Real test results (not asserted — executed, output shown)

`test_phase_a_policy_search.py`, 8/8 passed, run in both the canonical and
deployment copies:

- **Backward compatibility (5 tests):** every existing lever, called
  through its new parameterised factory with the original hardcoded
  values, produces **byte-identical** `model.summary()` output to the
  unmodified original function. This is the strongest form of backward-
  compatibility verification available short of a full diff of every
  state variable.
- **New search actually searches:** 13 candidates (5 fixed + 8 random)
  evaluated, 11 distinct PAR outcomes, correctly sorted descending.
- **Documented limitation confirmed empirically, not just asserted:**
  reserve-mandate-alone saved 14.9M people; the full transformational
  bundle saved 46.8M — consistent with the audit's finding that reserve
  mandate is comparatively weak on its own.
- **Intensity parameters checked in both directions:** reserve-mandate
  intensity (1mo vs 6mo) produces genuinely different outcomes (PAR 561.33
  vs 546.45) — confirming it's a real lever, not a no-op. Trader-regulation
  intensity (`margin_cap` 0.02 vs 0.10) produces **identical** output —
  this is not a bug in the new code, it's a direct, now-verified
  confirmation of the audit's finding that `apply_trader_regulation()`
  hardcodes its 15% reduction upstream and doesn't actually use its own
  `margin_cap` parameter. This is documented explicitly in
  `make_trader_regulation_lever()`'s docstring and its `lever_params`
  output includes both the requested and actual values, rather than
  silently pretending the parameter works.

**End-to-end HTTP verification** (FastAPI TestClient, real request/response,
not a unit-test mock): `POST /api/policy_search` → 200, 10 candidates
evaluated, real ranked output. `POST /api/policy_optimization` (original,
unmodified) → 200, 5 candidates, `note` field intact. `GET /api/health` →
200.

## Known limitations carried forward (not fixed in this phase, by design)

- **Trader regulation's `margin_cap` parameter is a documented no-op** —
  fixing this would mean modifying `political_economy.py`'s
  `apply_trader_regulation()`, which is out of Phase A's scope (Rule 2:
  extend where the audit recommends extension; this specific function
  wasn't flagged for extension, only for use). Flagged for Phase B.
- **Reserve mandate remains structurally weak for zero-reserve nodes** —
  this is inherent to the underlying mechanism (a reclassification, not
  new food), not something the search layer can work around. A genuine
  fix (Phase B, per the Digital Twin spec's flagged reserve-target
  redefinition) would need to change what the mandate *does*, not just
  how intensely it's applied.
- **The RC-amplification negative-feedback gap remains open**, per your
  explicit instruction to keep it open without freezing engineering
  progress. `policy_search()`'s objective (PAR) was deliberately chosen
  over FPI specifically because PAR is not directly downstream of that
  unresolved loop (per the Digital Twin spec's own reasoning, Section 10)
  — this phase did not need to wait for that fix, and didn't.
- **Cost constraints (Digital Twin spec Section 11) are not implemented**
  — `policy_search()` has no budget model; every candidate is currently
  "free." This is explicitly Phase D/E territory (constrained
  optimisation), not Phase A.
- **Frontend integration for this phase is API-contract-only** — the
  endpoint returns clean, typed JSON ready for a frontend to consume, but
  no UI was built. Per the phase breakdown, full Digital Twin frontend
  work is explicitly Phase E; building a one-off UI for this endpoint now
  would risk being thrown away when Phase E's broader frontend
  architecture is designed. This is a deliberate sequencing choice, not
  an omission.

## Files changed

- `model_src/.../src/model.py`, `stc_engine.py` — synced from canonical (Phase 2.5 fixes)
- `model_src/.../src/scenarios.py` — 4 lever factories + `policy_search()` (additive)
- `model_src/.../src/test_phase_a_policy_search.py` — new, 8 tests
- `app/schemas.py` — new `PolicySearchRequest`
- `app/model_bridge.py` — new `run_policy_search()`, one new import
- `app/main.py` — new `POST /api/policy_search` endpoint, one import line updated
- `requirements.txt` (both) — `mesa>=2.0` → `mesa==3.1.4`, documented inline

**Nothing existing was rewritten.** Every pre-existing function, endpoint,
and schema is unchanged and independently re-verified as unchanged.

## Next: Phase B

Per the stated dependency order, Phase B (implement missing policy levers
— food aid, fertilizer redistribution, import tariff/subsidy, adaptation
funding, global pooled reserve) is next. Phase A's `_combine_levers()` and
`policy_search()` are designed to accept new levers with zero changes to
the search logic itself — a new Phase B lever just needs a factory
function with the same `fn(model) -> None` signature and an entry in
`LEVER_FACTORIES`/`LEVER_RANGES`, confirming the extensibility this
implementation was built for.
