# Paper Outline

Grounded in what this project actually contains -- every section below
names the real document/data it would draw from. No placeholder results
are suggested; sections that would need work beyond what exists are
marked.

## Working title

"A 35-Node Agent-Based Digital Twin of the Global Food-Energy System:
Historical Retrodiction, Policy Search, and an Honest Accounting of an
Unresolved Feedback Loop"

(The title's honesty is deliberate -- see Novelty statement below. A
paper that oversells validation status will not survive a reviewer
re-running the code, which already happened once during this project's
own development.)

## Abstract (draft structure, not drafted)

One sentence each: the model and its scale; the validation approach and
current honest status (PAR passes 3/4, price magnitude fails 4/4, traced
to a named mechanism); the scenario catalogue; the policy-search
contribution; the one sentence that matters most for reviewer trust -- a
plain statement that the dominant feedback loop lacks an intrinsic
negative term and this is reported, not hidden.

## 1. Introduction

Motivation from real 2008/2010-11/2019-20/2022 food-price crises.
Contribution list, each traceable to a real artifact:
- A causally-decomposed, fully-traced simulation architecture
  (`docs/architecture/CAUSAL_DECOMPOSITION.md`).
- A scenario catalogue spanning 5 historical + 5 counterfactual
  experiments with real Monte Carlo uncertainty
  (`docs/scenarios/SCENARIO_CATALOGUE.md`).
- A policy-search layer answering "which interventions, in which
  countries, minimise population at risk"
  (`docs/implementation/`).
- A methodological contribution independent of this specific model: a
  demonstrated discipline of catching and honestly reporting validation
  regressions rather than tuning them away (the RC-amplification
  finding, `docs/validation/PHASE2_5_MERGE_CHANGE_REPORT.md`) -- this is
  a legitimate, citable point about reproducible ABM development
  practice, not just a limitation to apologise for.

## 2. Related work

**Not drafted this session** -- needs an actual literature search
(Homer-Dixon LFBB framework citations exist implicitly throughout the
codebase's docstrings, but a proper related-work section needs deliberate
positioning against other food-system ABMs, e.g. any existing FAO/IFPRI
computable general equilibrium models, other agent-based food-security
models). Flagged as real work remaining, not filled with placeholder
citations.

## 3. Model architecture

Draw directly from `docs/architecture/CAUSAL_DECOMPOSITION.md` and
`docs/architecture/SCIENTIFIC_DESIGN_SPECIFICATION.md` Section 16
(equations). Include the causal-loop diagram already produced (Phase
2.5b session artifact) or redraw as a static figure for camera-ready.

## 4. Calibration

`docs/DATA_PROVENANCE.md` (FAO, World Bank, OWID, ND-GAIN sources) +
the one genuinely cross-validated subsystem (CC_index, R-squared=0.86,
`docs/validation/VALIDATION_REPORT_INITIAL.md` Section 2) as the
calibration rigor showcase.

## 5. Validation

The full, honest table from `README.md`'s Validation status section.
**Do not soften this for the paper** -- present the POM=0.30 score, the
per-episode breakdown, and the specific named mechanism (RC amplification)
responsible, exactly as documented. This is more credible to an ASABE
reviewer than a suspiciously clean result, and defensible under direct
questioning in a way an inflated claim would not be (see
`publication/REVIEWER_FAQ.md`).

## 6. Scenario catalogue

Summarise `docs/scenarios/SCENARIO_CATALOGUE.md`'s 10 scenarios; the
strongest illustrative results are the MENA-region cascade match in the
2022 Ukraine scenario (face-validity match to real Black Sea grain
disruption transmission) and the compound-climate-shock counterfactual's
near-total trade collapse (TC=0.982) -- both real, computed results.

## 7. Policy optimisation

The `policy_search`/`node_level_policy_search` methodology, the
illustrative-cost caveat stated plainly, and the genuinely interesting
finding that some randomly-sampled interventions produce *negative*
population-saved -- a real result worth its own subsection, since it's
evidence the search explores rather than assumes.

## 8. Limitations

Direct lift from `LIMITATIONS.md`, condensed. Six items, in priority
order: RC-amplification feedback gap, synthetic environmental data,
illustrative costs, spatial resolution (35 nodes), no political-
instability feedback, SQLite single-writer constraint (mention only if
the paper discusses deployment).

## 9. Conclusion and future work

Direct lift from `docs/architecture/SCIENTIFIC_DESIGN_SPECIFICATION.md`
Section 20 and `docs/IMPLEMENTATION_AUDIT.md`'s "next" pointers.

## References

**Not compiled this session** -- needs Homer-Dixon's original LFBB
publications, FAO/World Bank/OWID/ND-GAIN dataset citations (sources
listed in `docs/DATA_PROVENANCE.md`, formal citations not yet compiled),
Mesa framework citation, and the related-work section's sources once
that section is written.

## What's needed before this outline becomes a draft

1. Related work section (real literature search).
2. Formal reference compilation.
3. A decision on whether to submit with the current honest-but-failing
   validation status, or wait for the RC-amplification fix and a
   re-validation pass first -- a genuine strategic choice, not a
   packaging task, flagged for the research team's decision.
4. Author list, affiliations, funding acknowledgment -- none of which
   this session has access to.
