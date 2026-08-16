# Phase 2 — Prerequisite: 2008 Validation Investigation

## Required by the mission brief before any new scenario could be built.
## What was found is much larger than the originally-diagnosed issue.

## 1. The originally-diagnosed cause (A_i not rescaled to year 2000) is FALSE as applied to the current code

I checked this directly rather than assuming the existing documents were
right. `model.py::_rescale_params_to_year()` already maps `"A_i"` to the
`A_i_implied` column of `node_panel.csv`, and I confirmed by direct lookup
that `A_i_implied` **is populated for the year 2000** for the node the 2008
trigger targets (Australia: 1.9336 in 2000 vs. 0.7629 in 2022 — a real,
different, correctly-applied value). Across all 35 nodes × 8 rescaled
columns (280 lookups), only 6 fall back to the 2022 value for 2000, and
none of those 6 are `A_i` — they are `E_fuel_i` (4 African blocs with no
energy-endowment coverage in the source panel) and `W_i` (Thailand,
Bangladesh). **The fix that `FINAL_VERIFICATION_REPORT.md` and
`report/manuscript.md` describe as still-needed is already implemented and
active in the code.** This is a case where the project's own documentation
had fallen out of sync with its own code — a second instance of the
documentation-drift problem flagged in the Phase 3 validation report, not
a new modelling gap.

**Conclusion on the instruction "if justified, implement transparently":**
not applicable — there was nothing left to implement. I did not tune any
parameter to chase a better fit.

## 2. What I found instead: a Mesa-version step-counting bug that invalidated every timed trigger in the model

While building and testing the new counterfactual triggers for this phase,
three brand-new trigger sets (China fertilizer ban, global oil crisis,
compound climate shock) produced **byte-for-byte identical price
trajectories to the no-trigger baseline**, across all 30 Monte Carlo
seeds. That is not a subtle effect being masked by noise — it means the
triggers were not firing at all, and I did not stop until I knew why.

**Root cause, confirmed by reading Mesa's own source directly:**
`agent.py`'s `CountryAgent.__init__` calls `super().__init__(model)` — the
single-argument constructor that only exists in Mesa 3.x (Mesa 2.x
requires `Agent(unique_id, model)`), so this codebase requires Mesa 3.x to
run at all. But **every Mesa 3.x release** (confirmed in both 3.1.4 and
3.5.1) wraps the model's `step()` method at `Model.__init__` time:

```python
self._user_step = self.step
self.step = self._wrapped_step
...
def _wrapped_step(self, *args, **kwargs):
    """Automatically increments time and steps after calling the user's step method."""
    self.steps += 1
    ...
    self._user_step(*args, **kwargs)
```

`model.py`'s own `FoodEnergyModel.step()` **also** ends with an explicit
`self.steps += 1`. Under any Mesa 3.x install, every call to
`model.step()` therefore incremented `self.steps` **by 2, not 1** — I
verified this directly by instrumenting a live model instance (steps went
0→2→4→6→8→10 across 5 explicit `step()` calls). Every trigger `step` field
in `stc_engine.py` is documented in its own docstring as a calendar-year
offset ("step 2 = year 2008", etc.) on the assumption that one call to
`step()` advances `self.steps` by exactly 1. That assumption was false
under the dependency stack actually available to run this code (`mesa>=2.0`
in `requirements.txt` resolves to the latest 3.x on a fresh `pip install`,
which is what both I and, most likely, prior sessions were running under).

**This means every timed trigger in the entire model — not just my three
new counterfactuals — was firing at half the intended calendar rate**,
and RC_DURATION_STEPS / warm-up windows measured in step() calls were
running for twice as many actual "years" as documented. This is a strictly
larger and more consequential finding than the A_i question I was asked to
investigate, and it directly implicates **every retrodiction number I
reported in the Phase 3 validation report**, since that battery was also
run under this same environment.

## 3. The fix (transparent, one deletion, no scientific parameters touched)

Removed the redundant `self.steps += 1` at the end of `model.py::step()`
(Mesa's own wrapper already provides it). Verified directly: `self.steps`
now advances by exactly 1 per call, 0→1→2→3→4→5. Re-verified that a
previously-silent trigger (`china_fertilizer_export_ban`, step=2) now
fires and prints `TRIGGER 'china_fertilizer_export_ban' fired at step 2`
exactly where its docstring says it should.

**This is the "already-documented historical initialization fix" question
answered honestly: the fix that was actually needed was not the one named
in the existing docs, but a real one, found by testing rather than by
reading, and it is a one-line, fully-transparent, non-parameter-tuning
correction.**

## 4. Old (buggy) vs. new (fixed) retrodiction — every number changed, and not for the better

Both runs used identical code otherwise, identical data, identical N_MC=30,
identical seeds. The only difference is the one-line fix above.

| Episode | Metric | Buggy (double-step) | Fixed (correct step) | Real historical value |
|---|---|---|---|---|
| 2008 | Peak FPI (norm.) | 0.806 ± 0.023 (31.5% err) | **1.588 ± 0.0** (34.9% err) | 1.177 |
| 2008 | Peak export-ban rate | 0.343 | 0.343 | 0.25 |
| 2008 | PAR (bn) | 0.363 | 0.373 | 0.925 |
| 2022 | Peak FPI (norm.) | 1.577 ± 0.26 (**9.1% err, PASS**) | **1.994 ± 0.25 (38.0% err, FAIL)** | 1.445 |
| 2022 | Peak export-ban rate | 0.457 | 0.457 | 0.20 |
| 2022 | PAR (bn) | 0.415 (PASS) | 0.432 (PASS) | 0.828 |
| 2010-11 Russia/Arab Spring | Peak FPI | 2.077 ± ? (57.4% err) | 2.126 ± ? (61.2% err) | 1.319 |
| 2019-20 COVID+locust | Peak FPI | 1.171 (19.4% err) | 1.394 (42.1% err) | 0.981 |
| **POM score (20-criterion)** | — | **0.300** | **0.300** (same value, different composition — see below) | target ≥0.70 |
| Stability (no-trigger) test | all_pass | (not separately re-run pre-fix in this session) | **FAIL** — price_ratio 2.09±0.19 vs target <1.20 | — |
| Network hub validation | hub_check_pass | — | **FAIL** — only 4/10 real top pagerank-hub countries recovered | — |

**The headline change: the 2022 episode's peak-FPI criterion — the single
strongest "pass" result I reported to you in the Phase 3 validation
report — was itself a product of the step-doubling bug.** With correct
timing it fails (38.0% error against a 15% tolerance). I want to be very
direct about this: I am not softening it, and I am not the source of the
original error — the bug predates this session — but the number I
personally reported to you a message ago was wrong, and this table is the
correction.

The overall POM score happens to land at the same 0.300 by coincidence
(different individual criteria pass/fail under the fix — e.g. `2011_par`
newly passes, `2022_score1_fpi` newly fails), not because the fix was a
wash. Full corrected criterion-by-criterion results:

```
2008: fpi=FAIL  eb=PASS  par=FAIL  hd=FAIL  trigger_dep=FAIL
2022: fpi=FAIL  eb=PASS  par=PASS  hd=FAIL  trigger_dep=FAIL
2011: fpi=FAIL  eb=FAIL  par=PASS  hd=FAIL
2020: fpi=FAIL  eb=PASS  par=PASS  hd=FAIL
stability: FAIL   network_hubs: FAIL
```

## 5. What this means for the project, stated plainly

1. **The Phase 3 validation report I gave you needs to be treated as
   superseded by this document** for the 2008/2022/2011/2020 FPI numbers
   specifically. The export-ban-rate and PAR results are essentially
   unchanged by the fix (those criteria don't depend as sensitively on
   exact step timing), so those parts of Phase 3 stand.
2. **This is a reproducibility-critical finding for Phase 6/8.** Anyone
   who clones this repo, runs `pip install -r requirements.txt` (which
   permits any Mesa ≥2.0), and executes `regenerate_all.py` today will
   silently get the buggy, double-stepped numbers — because that is what
   "the latest available Mesa 3.x" gives you, and nothing in the code
   detects or warns about it. `requirements.txt` should pin an exact Mesa
   version, and ideally the test suite should include an assertion that
   `model.steps == 1` after exactly one `model.step()` call, so this class
   of bug cannot recur silently.
3. **The corrected results are honestly worse, not better**, which is
   itself evidence this fix was not a fit-improving parameter tune — a
   parameter tune would have been chosen and tuned toward improving the
   score, not discovered as a side effect of debugging a completely
   different problem (why three brand-new counterfactual triggers produced
   zero effect).

All numbers used in the Phase 2 scenario catalogue that follows are
computed under the **fixed** code.
