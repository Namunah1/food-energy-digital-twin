# FAQ

## Is this model validated?

Partially, honestly reported. Population-at-risk passes 3 of 4 scored
historical episodes. Peak food-price magnitude currently fails all 4 —
traced to a specific, documented mechanism (the RC price-amplification
loop's missing negative feedback), not an unexplained gap. See
`README.md`'s Validation status section and `docs/validation/` for the
full history, including a correction the project made to its own
earlier (wrong) claim of a passing result.

## Why does the README say validation got *worse* at some point?

Because it did, and hiding that would make the repository less useful to
anyone trying to reproduce or build on this work. A sequencing fix
(`docs/validation/PHASE2_5_MERGE_CHANGE_REPORT.md`) was scientifically
justified (it corrected a real bug: overload was evaluated before trade
resolved each tick) but, once merged, full-episode price-retrodiction
error increased. This was reported plainly, the fix was kept (reverting
would have reintroduced a confirmed bug), and the resulting new question
(why does a more correct sequencing produce worse long-horizon numbers?)
became its own investigation (`docs/architecture/CAUSAL_DECOMPOSITION.md`).

## Can I trust the climate/fertilizer/water driver outputs?

Not as calibrated scientific claims, no — not yet. They are real,
correctly-implemented mechanisms (verified with real before/after
production comparisons, real unit tests, real bug fixes found during
development) running on explicitly synthetic placeholder data. Every
module's docstring says so. See `LIMITATIONS.md` for exactly which real
data sources would need to be integrated first.

## Why 35 nodes instead of ~195 countries?

21 individually-modelled hub countries (major producers/importers) plus
14 regional-bloc aggregates covering the remaining ~216 countries — a
deliberate resolution trade-off made early in this project, documented
with its consequences in `docs/nodes/NODE_DOCUMENTATION.md` Section 4
("bloc-level aggregation cannot resolve within-bloc heterogeneity").

## Why isn't [feature X] built yet?

Check `docs/IMPLEMENTATION_AUDIT.md` first — it's a file-by-file map of
specification section to implementation status, built specifically to
answer this question without guessing. If it's genuinely not there,
`LIMITATIONS.md`'s "What was explicitly, deliberately not built" section
explains the reasoning for the largest deliberate omissions.

## Why does the reserve-mandate policy lever seem weak in the search results?

By design of the underlying mechanism, not a search-layer bug: it
reclassifies a node's *existing* reserve stock into usable food supply.
For a node with near-zero reserves to begin with (several structurally
fragile nodes, documented in `docs/nodes/NODE_DOCUMENTATION.md`), there's
nothing to reclassify. Confirmed empirically in
`docs/implementation/PHASE_A_IMPLEMENTATION_REPORT.md`.

## How do I know if a number in this repository is real or a placeholder?

Every real (calibrated-against-actual-data) result is grounded in a
specific file under `data/processed/` or `data/raw/`, referenced from the
report that produced it. Every placeholder/synthetic/illustrative value
is labelled as such in the module docstring where it's defined, in the
report describing it, and usually in the returned API response itself
(e.g. `cost_model_note`, `"status": "INTERIM"`). If you find a number
presented without one of these three anchors, that's a documentation gap
worth filing an issue about — see `docs/IMPLEMENTATION_AUDIT.md`'s method
for how to trace it back to source.

## Is the frontend production-ready?

The API layer and page routing are verified (build succeeds, real
backend/frontend servers tested together, see
`docs/implementation/PHASE_E_IMPLEMENTATION_REPORT.md`). Full
client-side interactive behaviour was not verified with a headless
browser in this environment — flagged explicitly, not silently assumed.

## What's the fastest way to understand the whole project?

`README.md` → `ARCHITECTURE.md` → `docs/architecture/CAUSAL_DECOMPOSITION.md`
→ `docs/IMPLEMENTATION_AUDIT.md`. That path covers what the system does,
why it's built the way it is, and what's real vs. proposed, in under an
hour of reading.
