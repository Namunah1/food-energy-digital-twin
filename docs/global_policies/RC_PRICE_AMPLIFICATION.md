# Global Policy: RC Price Amplification

## Purpose

Represents the Homer-Dixon Rigidity Cycle (RC) -- a systemic-risk
amplification effect where a rising count of overloaded nodes drives the
global price up directly, independent of the underlying supply-demand
fundamentals already captured by the price system's normal update.

## Equation

Fires only when `n_overloaded(t) > n_overloaded(t-1)` (overload count
increasing):

```
factor = 1 + RC_PRICE_AMPLIFICATION * n_overloaded(t)
price(t) <- clip(price(t) * factor, 0.80, 5.00)
```

Full derivation and its place in the model's causal graph:
`docs/architecture/CAUSAL_DECOMPOSITION.md` Section 1.

## Current value

`RC_PRICE_AMPLIFICATION = 0.021` (`model/src/stc_engine.py`).

## Scientific source

Hand-set constant, calibrated during earlier development iterations --
**not independently sourced from a real RC-specific historical
dataset.** This is stated explicitly in `docs/architecture/CAUSAL_DECOMPOSITION.md`
Section 1's assessment: "Not empirically calibrated against any
independent RC-specific dataset."

## Affected nodes

All 35 -- the price it modifies is a single global scalar shared by
every node's food-security and trade-affordability calculations.

## Affected variables

`price_system.price` directly; indirectly, every node's `FS_index` (via
the price-ratio term in `_compute_FS_index`), and therefore the overload
count that feeds back into this same mechanism next tick.

## Sensitivity

**This is the single most sensitive parameter in the entire model.**
Sobol sensitivity analysis found its total-order sensitivity index
dominates every other calibrated constant by more than 200x for
price-related outcomes (`docs/validation/VALIDATION_REPORT_INITIAL.md`
Section 3) -- a finding that has been reproduced across every version of
the model tested during this project's history.

## Optimisation space

**Not currently exposed as an optimisable/searchable parameter** in
`policy_search()` or `node_level_policy_search()` -- those search over
policy LEVERS (interventions a decision-maker could actually apply), and
`RC_PRICE_AMPLIFICATION` is a model-calibration constant, not a policy
lever. It was explicitly **not modified** during this project's Phase D
work per direct instruction ("Do not modify RC_PRICE_AMPLIFICATION").

## Known limitation

This mechanism has no intrinsic negative feedback of its own -- see
`docs/architecture/CAUSAL_DECOMPOSITION.md` Section 1 and `LIMITATIONS.md`
for the full accounting. This is the project's single highest-priority
open scientific issue, deliberately left unresolved through five
implementation phases per explicit instruction to keep it open rather
than freeze engineering progress or tune it away.
