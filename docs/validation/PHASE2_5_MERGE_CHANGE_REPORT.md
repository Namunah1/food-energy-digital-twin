# Phase 2.5 Merge — Change Report

## Status: MERGED, but I am recommending against declaring this "frozen as canonical" yet — see Section 5

## 1. What changed

`model.py::step()` — the STC engine's stress-accumulation/overload-detection/
trigger-injection call (`self.stc_engine.step(self)`) was moved from
**before** trade execution to **after** trade execution and the existing
post-trade σ recompute ("BUG-013" block). No calibrated parameter,
threshold, or equation coefficient was touched — this is a call-ordering
change only, exactly as instructed.

## 2. A correction I owe you before the rest of this report

When I reported the Phase 2.5 investigation, I said the fix reduced
step-1 baseline overload from 12 nodes to **0**. That number was wrong,
and I want to be direct about why: my test harness manually replicated
`model.step()`'s internals instead of calling the real, Mesa-wrapped
`step()` method, so `model.steps` never advanced past 0 during the test.
A separate, legitimate 1-step warm-up guard in `_detect_overload()`
(`if t >= min_steps_for_overload`) was therefore suppressing *all*
overload detection in my harness — independent of the trade-ordering fix
entirely. Measured correctly, through the real merged `model.step()`:

**Step-1 baseline (no-trigger) overload: 12 nodes → 8 nodes.** Real,
substantial, but partial — not the complete elimination I reported. The 8
that remain (Central Africa, Eastern Europe-other, Indonesia, MENA-other,
Pakistan, Saudi Arabia, South Asia-other, United Kingdom) show a further
real finding: their post-trade σ is numerically identical to their
pre-trade σ, meaning trade provided them zero measurable relief this
tick — worth a dedicated follow-up (Section 6), not chased further here.

## 3. Why it changed (recap, unaffected by the correction above)

Import-dependent nodes structurally show a production/demand deficit
*before* trade — that is the entire reason they trade. Evaluating LFBB
overload on that pre-trade snapshot flagged them as having failed to cope
using a state that existed before their coping mechanism acted. This
reasoning stands independent of the numeric correction in Section 2.

## 4. Full before/after comparison

### 4.1 Retrodiction battery (N_MC=30, 25 steps, identical seeds/data both runs)

| Metric | Before (pre-trade STC) | After (post-trade STC) | Direction |
|---|---|---|---|
| 2008 peak FPI error | 34.9% | **41.2%** | Worse |
| 2022 peak FPI error | 38.0% | **109.2%** | Much worse |
| 2011 peak FPI error | 61.2% | **163.2%** | Much worse |
| 2020 peak FPI error | 42.1% | **62.4%** | Worse |
| POM score (20-criterion) | 0.300 | 0.300 | Unchanged (same criteria still failing, by larger margins) |
| Stability test price_ratio_mean (no-trigger) | 2.091 | **4.743** (near the model's 5.0 price ceiling) | Much worse |
| Trigger-dependency ratio (2008) | 2.315 | 2.702 | Slightly better (still fails >3× threshold) |
| Network hub validation | 4/10 hub overlap (FAIL) | 4/10 hub overlap (FAIL) | Unchanged (purely structural, unaffected by step-ordering) |

### 4.2 Full Phase 2 catalogue (all 10 scenarios, peak FPI)

| Scenario | FPI before | FPI after | Change |
|---|---|---|---|
| 2008 crisis | 1.588 | 1.705 | +7.4% |
| 2010 Russia export ban | 2.143 | **3.370** | +57.3% |
| 2011 East Africa | 1.393 | 2.068 | +48.5% |
| 2019-20 COVID | 1.325 | 1.551 | +17.1% |
| 2022 Ukraine | 1.997 | **3.042** | +52.3% |
| cf: COVID in 2000 | 0.800 | 0.809 | +1.1% |
| cf: Ukraine war in 2010 | 3.707 | **4.350** | +17.3% |
| cf: China fertilizer ban | 2.391 | 2.846 | +19.0% |
| cf: Global oil crisis | 2.192 | 2.388 | +8.9% |
| cf: Compound climate | 2.765 | 3.351 | +21.2% |
| Baseline (no trigger) | 1.716 | 1.912 | +11.4% |

**Every single scenario got worse, not better.** Trade-collapse (TC) and
population-at-risk (PAR) metrics are essentially unchanged in every
scenario (typically <2% difference) — the degradation is concentrated
entirely in the price/FPI metric.

## 5. Is the causal behaviour now more scientifically defensible? Yes, locally — but validation says no, globally

**Short-horizon causal structure: genuinely improved**, and this is a
real, verified, positive result: re-running the 2008 scenario under the
merged code shows price sitting flat until the Australia-drought/
speculative-spike triggers actually fire (step 8-9), consistent with what
a historical retrodiction should look like, and no longer visibly driven
by a same-step artefact. The step-1 premature-overload count genuinely
fell (12→8).

**Long-horizon (full 25-step episode) quantitative validation got
substantially worse across every scored metric.** This is a real tension,
not something I can resolve by asserting one side of it. Per your own
stated criterion — *"If the corrected model produces a more realistic
temporal ordering while maintaining or improving validation, freeze this
as the new canonical implementation"* — validation did not maintain or
improve; it worsened, in several cases dramatically (2011: 61%→163% error).
**I am therefore not treating this as ready to freeze**, and recommend
holding off on Phase 4 until Section 6 is investigated, per your own
"if any scenario still performs poorly, investigate the remaining causes
separately rather than tuning parameters indiscriminately" instruction —
this is exactly that situation, just surfaced by the merge itself rather
than by a specific scenario.

**The merge itself remains in the code**, as you instructed, and I stand
behind it as the scientifically correct sequencing given the evidence in
the Phase 2.5 investigation — reverting it would reintroduce a confirmed
artefact. The open question is a *different, newly-surfaced* mechanism
(Section 6), not a reason to doubt the ordering fix itself.

## 6. Hypothesis for the long-horizon degradation (flagged for separate investigation, not chased further here)

Traced (partially) to `_apply_rc_price_amplification()`: every time the
*current* overloaded-node count increases relative to the previous step,
the model applies a direct price shock proportional to that **current
total count** (`factor = 1 + 0.021 × n_overloaded`), and this is now
computed from post-trade overload counts. Given Section 2's finding that
trade provides measurably zero relief to several chronically-overloaded
nodes, if overload counts accumulate more persistently across a run under
the corrected ordering than they did before, this mechanism would compound
into materially larger cumulative price shocks over 25 steps — consistent
with the stability test now saturating near the model's hard price ceiling
(4.74 mean, vs. a 5.0 cap) in most seeds. **This is a hypothesis I have
partially traced through the code but not fully confirmed with a
dedicated ablation** — I stopped here deliberately rather than either (a)
asserting it as settled, or (b) adjusting `RC_PRICE_AMPLIFICATION` or any
other parameter to compensate, which would be exactly the "indiscriminate
tuning" you told me not to do.

## 7. Recommendation

1. Keep the sequencing fix merged (done).
2. Do not mark this canonical/frozen yet.
3. Next investigation (separate from this one, same rigor level as Phase
   2.5): trace `_apply_rc_price_amplification`'s interaction with
   post-trade overload persistence across a full 25-step run, with the
   same kind of controlled, single-variable ablation used in Phase 2.5,
   before deciding whether the RC cascade mechanism itself needs a
   (separately justified, transparently documented) correction — not a
   tuned-down amplification constant.
4. Hold Phase 4 until that investigation concludes.
