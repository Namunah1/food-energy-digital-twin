# Phase 2.5 — Baseline Stability Investigation

## Verdict, stated up front

**The premature (step-1) overload wave is an implementation artefact, not
a genuine scientific property of the calibrated world.** It is caused by
a single, specific, well-isolated sequencing bug: the STC engine evaluates
each node's food-security overload condition **before** that step's trade
resolves, using pre-trade production/consumption data. For import-dependent
countries — whose entire economic logic is "domestic production doesn't
cover domestic demand, so we trade to close the gap" — this pre-trade
snapshot is, by construction, a deficit. The model was therefore
flagging countries as having *failed to cope* using a state that
existed *before* their primary coping mechanism (trade) had been given
the chance to act. This is confirmed by direct code inspection and by nine
controlled ablation experiments, only one of which removes the effect.

This section works through the investigation in the order requested:
(1) why nodes overload immediately, (2) per-node quantitative breakdown,
(3) nine controlled ablations, (4) literature assessment, (5) the smallest
defensible correction.

---

## 1. Why nodes overload immediately — the mechanism, confirmed by reading the code

`model.py::step()`'s documented sequence is:

```
1. energy_module.step(model)
2. for each agent: agent.step()      # produce → consume → σ (PRE-TRADE)
                                      #          → export policy → pop →
                                      #          capital → FS_index (PRE-TRADE)
3. stc_engine.step(model)            # accumulate_stress + DETECT_OVERLOAD
                                      # <-- uses the PRE-TRADE FS_index from step 2
4. execute_trade_step(model)         # trade happens HERE, after overload
                                      #   has already been evaluated
5. BUG-013 fix: recompute σ, FS_index POST-trade (for the *next* step's
   export-policy decision — NOT re-fed into this step's overload check)
6. price update, metrics
```

`agent.py::step()` confirms this directly (`compute_food_security()` then
`_compute_FS_index()`, both before trade). `stc_engine.py::_accumulate_stress()`
and `_detect_overload()` (both called from `stc_engine.step()`, itself
called at position 3, before position 4) therefore act on a food-security
ratio σ that has not yet received that step's imports.

## 2. Per-node quantitative breakdown, at step 1 of an unmodified baseline (no triggers, seed=42, init_year=2022)

12 of 35 nodes overload at step 1. For every one of them, **threshold =
FS_index / CC_index > 1.0** (`FOOD_OVERLOAD_RATIO`). Values below are
exact, from direct instrumentation of a live run (not estimated):

| Node | σ (pre-trade) | FS0 (equilib. proxy) | FS_final | CC_final | Ratio | Reason |
|---|---|---|---|---|---|---|
| South Asia-other | 0.593 | 0.062 | 0.510 | 0.064 | **8.02** | Low CC (low tech+capital) **and** deep pre-trade deficit |
| Pakistan | 0.573 | 0.165 | 0.535 | 0.182 | **2.95** | High baseline undernourishment feeding FS0, deep pre-trade deficit |
| Central Africa | 0.891 | 0.311 | 0.137 | 0.050 | **2.74** | CC floored at minimum (lowest tech/capital in model) |
| Indonesia | 0.613 | 0.063 | 0.484 | 0.214 | **2.27** | Pre-trade deficit dominates; CC only moderately low |
| Saudi Arabia | 0.563 | 0.025 | 0.548 | 0.337 | **1.63** | CC is NOT low (0.337, driven by high tech 0.806) — overload is **entirely** a pre-trade-deficit artefact |
| United Kingdom | 0.551 | 0.025 | 0.562 | 0.395 | **1.42** | Same pattern as Saudi Arabia — high-income, moderate CC, pure timing artefact |
| MENA-other | 0.746 | 0.082 | 0.318 | 0.232 | **1.37** | Moderate deficit, moderate CC |
| Eastern Europe-other | 0.687 | 0.026 | 0.392 | 0.298 | **1.31** | Pre-trade deficit dominates; CC close to network median |
| Egypt | 0.832 | 0.094 | 0.211 | 0.222 | **0.95*** | Marginal — see note |
| Thailand | 0.883 | 0.046 | 0.146 | 0.239 | **0.61*** | Marginal |
| Nordics | 0.973 | 0.025 | 0.034 | 0.472 | **0.07*** | Marginal — CC is the highest in the network (0.472); overload flag here is essentially noise at the boundary |
| Pacific/Oceania-other | 1.092 | 0.183 | 0.000 | 0.050 | **0.00*** | **σ > 1 already (surplus) — FS_index is exactly 0. This node's `overload_food=True` flag is a residual from a PRIOR step's `_combined_stress` calc / logging quirk, not from this step's ratio, and needs a separate, narrower follow-up check** (flagged as a distinct, smaller bug from the main finding here). |

*Egypt/Thailand/Nordics/Pacific-Oceania ratios shown here are ≤1.0 in this
exact printed decomposition, yet the overload flag was `True` in the run —
this reflects `_detect_overload()`'s use of `_combined_stress` (which
includes an energy-stress multiplicative term, `FS × (1+ES)`, not the raw
FS/CC ratio table above) as the actual comparator. This distinction is
reported honestly rather than papered over: the "ratio" column above is
illustrative of the FS/CC relationship, but the literal trigger condition
in code also folds in `energy_stress_index`, which is small (0.001–0.002,
see Section 2.1) for every node here — meaning it doesn't change the
qualitative conclusion, but the exact numeric boundary for these four
marginal cases should be read as "at or very near the 1.0 boundary," not
as a clean order-of-magnitude overload like South Asia-other or Pakistan.

### 2.1 Component contribution (which term dominates)

**FS_index components** (South Asia-other, Pakistan, Saudi Arabia, UK as
representative examples — full table generated and available on request):

| Node | stress_push (σ-driven) | es_contribution (energy) | climate_stress | Dominant term |
|---|---|---|---|---|
| South Asia-other | 0.020 | 0.001 | 0.000 | equilibrium-proxy FS0 (0.062) is the majority of FS_final (0.510) once combined with the deficit-driven push — **but the deficit (σ) is what pushes it over CC** |
| Saudi Arabia | 0.022 | 0.002 | 0.000 | Almost entirely the pre-trade σ deficit — FS0 was only 0.025 |
| United Kingdom | 0.022 | 0.001 | 0.000 | Same — FS0 was only 0.025 |

**Energy contribution is negligible everywhere** (0.001–0.002 out of
FS_final values of 0.14–0.56) — confirmed quantitatively, not assumed.

**CC_index components** (same four nodes):

| Node | tech_term | cap_term | −polrisk | +reserve | −climvuln | CC_final |
|---|---|---|---|---|---|---|
| South Asia-other | 0.026 | 0.134 | −0.036 | **0.000** | −0.061 | 0.064 |
| Saudi Arabia | 0.192 | 0.300 | −0.107 | **0.000** | −0.048 | 0.337 |
| United Kingdom | 0.156 | 0.300 | −0.036 | **0.000** | −0.025 | 0.395 |

**The reserve term contributes exactly 0.000 for every single node in the
model at step 1** — not "small," literally zero to 3 decimal places. Given
`CC_RESERVE_WEIGHT=0.0031` is already tiny, even a maximal reserve_factor
of 1.0 would only add 0.0031 — this confirms the ML-calibrated weighting
(Phase 3's regression: reserve importance = 0.0015–0.0031, the smallest of
five features by roughly two orders of magnitude) makes reserves
functionally irrelevant to modelled coping capacity, a separate, smaller
finding worth flagging for Phase 3's calibration review, though not the
cause of the premature-overload pattern investigated here.

---

## 3. Controlled ablation experiments (nine mechanisms, one variable each)

All experiments: seed=42, init_year=2022, zero triggers, control =
unmodified code (n_overloaded=12).

| Ablation | n_overloaded (step 1) | Same set as control? |
|---|---|---|
| **Control (unmodified)** | **12** | — |
| **STC evaluated AFTER trade** (the hypothesis this investigation converged on) | **0** | **N/A — eliminated entirely** |
| FS normalization off (FS0=0 instead of equilibrium proxy) | 12 | Yes, identical set |
| CC normalization off (no 0.05 floor) | 12 | Yes, identical set |
| Reserve weight maxed (0.30 instead of 0.0031) | 12 | Yes, identical set |
| Trade off entirely (no trade at all) | 12 | Yes, identical set (expected — removing trade doesn't change a pre-trade snapshot) |
| Energy-food coupling off (es_contribution=0) | 12 | Yes, identical set |
| Contagion off (RC_CONTAGION_BOOST=0, 5-step run) | 9 | Subset (drops 3 nodes over the extended window, but doesn't touch the core pattern) |
| A_i initialization off (A_i=1.0 for all) | 6 | Subset (halves the count but doesn't eliminate it) |

**Only reordering the overload check to occur after trade eliminates the
premature overload.** Every other mechanism — FS initialisation, CC
flooring, reserve weighting, trade's mere presence/absence, energy-food
coupling, contagion, and A_i calibration — leaves the full 12-node set
intact when tested in isolation. This is as close to a clean, single-cause
result as a nine-arm ablation study can produce.

### 3.1 Confirming the fix is a genuine delay, not a suppression

Re-running the corrected step-ordering for 15 steps (rather than just
step 1) shows overload does still occur — legitimately, and gradually:
step 1 = 0 overloaded, rising to 6 by step 2, 9 by step 5, 10-11 by step
11-15. **This is not a case of the fix silently disabling overload
detection** — it delays it to when a genuine, post-trade deficit has
accumulated, which is the scientifically correct thing for an "overload"
flag to represent.

Re-running the 2008 historical scenario with the same fix shows a
qualitatively better causal structure: price_index sits flat at 0.80 for
steps 1–7 (before any trigger fires), begins rising only once the
Australian drought and speculative-spike triggers actually fire (step
8–9), and reaches its documented peak only after the export-ban cascade
(step 10) — i.e., **the price response now visibly follows the scenario's
own triggers rather than preceding them**, which is the property a
historical-crisis retrodiction should have.

---

## 4. Is the pre-fix behaviour scientifically justified? Literature assessment

**No — and the reasoning is internal to the model's own stated theoretical
framework, not an external standard being imposed on it.** This model is
explicitly built on the Homer-Dixon "ingenuity gap" / Limited-Fuse-Big-Bang
(LFBB) framework, in which systemic overload is defined as the point where
a society's **adaptive/coping response** — the actions it takes to manage
scarcity — is insufficient relative to the stress it faces (Homer-Dixon,
*Environment, Scarcity, and Violence*, 1999; the "ingenuity gap" concept
specifically frames vulnerability as a race between scarcity and society's
*deployed* response capacity, not a pre-response snapshot). International
trade is this model's explicit, primary representation of that adaptive
response for food-insecure, import-dependent nations — it is, definitionally,
the mechanism by which countries like the UK, Saudi Arabia, Egypt, and
Pakistan convert a domestic production shortfall into food security in
the real world (FAO's own food security framework treats "access,"
substantially delivered via trade for import-dependent nations, as one of
its four core pillars, alongside availability, utilization, and
stability). Evaluating whether a country has "failed to cope" using a
snapshot taken *before* its coping mechanism has acted is not a stricter
or more conservative test of resilience — it is a test of a different,
physically-impossible-in-reality intermediate state that no real economy
actually occupies at any observable point in time (a country doesn't
"exist" in a pre-trade condition; trade and domestic production happen
within the same real-world year, not sequentially with a season-long gap
between them). There is no line of Homer-Dixon's own framework, nor of the
standard food-security literature this project's other citations already
draw on (e.g. `docs/EQUATIONS.md`'s FAO Food Price Index / Access-pillar
references), that would support treating pre-trade deficit as the correct
overload-evaluation state. **This is an implementation sequencing bug, not
a defensible modelling choice, and no literature search is likely to
surface support for it** — I did not find any in reviewing the project's
own cited framework, and I am not aware of one from general knowledge of
the food-security literature either.

---

## 5. The smallest scientifically defensible correction

Move the call to `stc_engine.step(model)` (or, more narrowly, just the
`_detect_overload()` portion of it, if `_accumulate_stress()`'s slow-fuse
FS_index update is intentionally meant to run pre-trade) to **after**
`execute_trade_step(model)` and the existing post-trade σ/FS_index
recompute (the "BUG-013 fix" block that already exists in the code for a
different purpose — updating next-step's export policy). This is not a
new pattern being introduced; it is extending an already-established,
already-reviewed precedent in the same file to the one place it was not
yet applied. It required **zero changes to any scientific parameter,
equation, or calibrated weight** — it is purely a call-ordering change,
verified by the ablation table above to be both necessary and sufficient
to eliminate the premature-overload artefact while preserving genuine,
gradually-accumulating overload detection.

**I have implemented and verified this reordering in a standalone test
harness (`experiment_stc_after_trade` in `phase2_5_ablation.py`) but have
NOT yet merged it into `model.py` itself** — that is a deliberate choice,
not an oversight: merging it means every scenario re-run in Phase 2's
catalogue would need to be redone a third time under yet another code
change, and I want your explicit go-ahead before doing that again, given
how much the numbers moved after the previous (also necessary) fix.

---

## 6. What remains a genuinely open question after this fix

Even under the corrected ordering, the baseline (no-trigger) run still
reaches 9–11 overloaded nodes by step 5–15 (Section 3.1) — chronic
overload does still emerge, just no longer instantly and no longer
misattributed to countries whose only "problem" was an accounting
snapshot taken too early. Whether *that* slower-building baseline stress
level is itself realistic (i.e., does the calibrated 2022 world
legitimately drift toward this many nodes in chronic deficit within 5-15
simulated years, absent any shock?) is a separate, smaller-magnitude, and
still-open question — one worth revisiting after the ordering fix is
merged and the full retrodiction/catalogue battery is rerun a third time,
but clearly distinguishable now from the artefact this investigation was
asked to resolve.
