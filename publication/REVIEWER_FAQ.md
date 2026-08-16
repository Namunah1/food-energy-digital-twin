# Reviewer FAQ / Expected Questions

Real answers, drawn from the actual investigation history -- not
rehearsed deflections. Where the honest answer is "we don't know yet" or
"this is a real limitation," it says so.

## "Your validation scores are weak -- why should I trust this model at all?"

Because the weak score is the result of rigorous testing, not a sign of
its absence. Population-at-risk -- the metric the policy-search layer
actually optimises -- passes 3 of 4 historical episodes. Price magnitude
fails all 4, and we can name the exact mechanism responsible (RC price
amplification's missing negative feedback,
`docs/architecture/CAUSAL_DECOMPOSITION.md` Section 1) rather than
shrugging at an unexplained gap. A model that can't explain its own
failure modes is a bigger red flag than one that can.

## "Did you tune parameters to make your validation numbers look better?"

No -- and there's a specific counter-example that proves it: a
sequencing fix we made for clear scientific reasons (the premature-
overload investigation) made full-episode validation measurably WORSE
(peak-FPI error went from 38% to 109% on the 2022 episode) once merged.
We kept the fix and reported the regression plainly, because reverting
would have reintroduced a confirmed bug just to make a number look
better. See `docs/validation/PHASE2_5_MERGE_CHANGE_REPORT.md`.

## "Your project's own reports contradict each other on validation numbers -- which do I believe?"

The most recent, and specifically the one with an automated verification
step re-deriving every reported number from regenerated source data --
not a narrative document. We found this exact contradiction ourselves
mid-project (a stale document claimed 2.4% error; a verified
regeneration showed 83.3%; our own live re-run showed yet a third number
after further bug fixes) and resolved it by treating the freshly-executed,
verified run as ground truth, documenting why the others were stale
rather than picking whichever was more flattering. See
`docs/validation/VALIDATION_REPORT_INITIAL.md` Section 0.

## "Isn't 35 nodes too coarse to say anything meaningful about, e.g., Somalia specifically?"

Yes, for sub-national or single-country claims -- this is a stated,
deliberate resolution trade-off (`docs/nodes/NODE_DOCUMENTATION.md`
Section 4), not an oversight. The model is designed for network-level
systemic-risk questions (how does a shock to one major exporter
propagate through global trade) where 35-node resolution is defensible,
not for country-specific policy advice at a finer grain than that.

## "Your environmental drivers (rainfall, fertilizer, water) -- are those real?"

The mechanisms are real and tested (verified with real before/after
production comparisons, and two real bugs were found and fixed during
development -- a fertilizer-response normalisation error, a water-balance
units-scale error). The DATA they run on is explicitly synthetic
placeholder data, stated in every relevant module's docstring and in
`LIMITATIONS.md`. We built the pipeline correctly before having real
data to put through it, and we say so rather than implying otherwise.

## "What would it take to trust the price-magnitude numbers?"

Resolving the RC-amplification feedback gap -- adding a genuine
counteracting term to the dominant positive-feedback loop, not just
tuning its amplification constant down (which we were specifically
instructed not to do, and didn't). This is the explicitly-stated,
highest-priority open item across every recent phase of this project's
own documentation.

## "How do I know your Monte Carlo uncertainty bounds are meaningful and not just noise?"

We don't claim more precision than the model supports. Several scenarios
in the catalogue show zero variance across 30 seeds in specific
short-window runs -- flagged explicitly as an artefact of insufficient
steps for stochastic divergence, not presented as tight confidence, in
`docs/scenarios/SCENARIO_CATALOGUE.md`.

## "This is a lot of self-reported limitations -- is there anything you're confident about?"

The trade-clearing mechanism's structural correctness, the CC_index
(coping capacity) calibration (the one cross-validated subsystem,
R-squared=0.86 against held-out FAO undernourishment data), the
RC-cascade dominance finding (>200x other parameters in Sobol
sensitivity analysis, robust across every version of the model tested),
and the engineering discipline itself -- every phase of new work in this
project's history included a full regression re-run against the
historical validation battery before being considered complete, and
every one of those checks is reproducible by running
`model/src/regenerate_all.py`.
