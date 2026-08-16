# Limitations

Every known gap in this project, consolidated in one place. Nothing here
is new — each item is drawn from the phase report that found it, linked
for the full context. This document exists so a new reader doesn't have
to piece limitations together from 20+ separate reports.

## Scientific limitations

### The dominant, still-open issue: RC price amplification has no intrinsic negative feedback
Peak-FPI retrodiction fails on all 4 scored historical episodes. Traced
to a specific mechanism (not a mystery): every overload-count increase
triggers a direct price shock with no counteracting term of its own —
everything that currently constrains it is borrowed from the price
system's hard ceiling. **Deliberately kept open**, not tuned around —
see `docs/architecture/CAUSAL_DECOMPOSITION.md` Section 1 and
`docs/validation/PHASE2_5_MERGE_CHANGE_REPORT.md`.

### Population-at-risk is the strongest validated metric; price magnitude is the weakest
3 of 4 episodes pass on PAR; 0 of 4 pass on peak-FPI. This is why the
policy-optimisation objective uses PAR, deliberately, not FPI.

### No real environmental or resource calibration data was acquired
Rainfall, temperature anomaly, fertilizer N/P/K trade, and water
withdrawal-by-sector are all real, tested *mechanisms* running on
explicitly-labelled *synthetic placeholder* data. See
`docs/architecture/DIGITAL_TWIN_ARCHITECTURE.md` Section 12 for the
specific real sources (CHIRPS, Berkeley Earth/NOAA GHCN, IFA, FAO
AQUASTAT) that would need to be sourced and integrated.

### The fertilizer trade network is a simplified stock model, not the originally-specified bilateral gravity network
Building a full bilateral network with fabricated capacity/cost/risk
matrices would have been a more serious fabrication than the simpler,
honestly-labelled producer/consumer model actually shipped. See
`docs/implementation/PHASE_C2_IMPLEMENTATION_REPORT.md`.

### Climate triple-counting resolution is opt-in, not default
`climate_modifier` feeds production, FS_index, and ES_index
simultaneously; a fix exists (`climate_single_channel_mode`) but is not
the default, specifically to avoid retroactively changing every
validated historical result without explicit sign-off.

### The illustrative cost model is not real cost data
`LEVER_COSTS_ILLUSTRATIVE` (Phase D) uses arbitrary units and a
deliberately-chosen *relative ordering* across levers, not sourced FAO/
World Bank cost-of-storage figures. Any budget-constrained search result
should be read as "what the search would do if these were real costs,"
not a real recommendation.

### Reserve mandate is functionally weak for the nodes that need it most
It reclassifies existing stock (reserves → imperishable), it does not
create new food. For near-zero-reserve nodes (Central Africa, confirmed
in the Phase 2.5 diagnostic), there is nothing to reclassify.

### CC_index calibration may have an unresolved circularity
The coping-capacity regression target and a downstream validation check
both trace back to the same FAO undernourishment series — flagged in
`docs/validation/VALIDATION_REPORT_INITIAL.md`, not resolved this
session.

### 2011 East Africa's trigger severity is not FAO-yield-sourced
Unlike every other historical trigger, `node_panel.csv`'s cereal-yield
data is NaN for East Africa in 2010-11; severity is calibrated from
documented humanitarian facts instead. Flagged explicitly in the
trigger's own docstring.

## Software/engineering limitations

### The vendored model is not an installable Python package
`tests/model/*.py` and `model/src/regenerate_all.py` rely on a
same-directory `sys.path.insert(0, '.')` import convention inherited
from the original codebase, not `pip install -e .`. `tests/model/conftest.py`
works around this for pytest; direct script execution still requires
being inside `model/src/`.

### No Kubernetes manifests, job queue, or Postgres migration exist
`docs/architecture/DEPLOYMENT_ARCHITECTURE.md` contains a complete,
reasoned design; no YAML or migration scripts were ever written. The
current, real, working deployment path is `docker-compose up` — see
`deployment/README.md`.

### The experiment store is SQLite, single-writer
Does not survive multi-replica deployment. A Postgres schema is
*designed* (`docs/architecture/SCIENTIFIC_DESIGN_SPECIFICATION.md`
Section 18) but not implemented.

### Full client-side interactivity of the Policy Lab page was not verified with a headless browser
Verified: TypeScript compiles, production build succeeds, the real
backend returns real results, the real frontend server serves the page
with correct content. Not verified: the click-through, in-browser
experience with JavaScript execution — this environment did not have a
headless browser readily available. Recommended as the final check
before considering the page production-verified.

### `apply_trader_regulation()`'s `margin_cap` parameter is a documented no-op
Confirmed empirically (not just by reading the code) during Phase A
testing: calling it with different `margin_cap` values produces
identical output, because the underlying function hardcodes a 15%
reduction regardless of its own parameter.

## What was explicitly, deliberately not built

- A dynamic political-instability feedback loop (e.g. famine → rising
  unrest) — a scope boundary stated in the causal decomposition, not an
  oversight.
- Sub-national spatial resolution — the 35-node structure (21 countries +
  14 regional blocs) is a documented trade-off from the earliest phase
  of this project.
- A differentiable surrogate model for gradient-based policy
  optimisation — black-box random search was judged sufficient given the
  model's ~1 second/replica runtime; revisit only if that assumption is
  found wrong empirically.
