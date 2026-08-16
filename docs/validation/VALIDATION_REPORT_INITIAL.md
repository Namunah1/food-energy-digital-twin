# Phase 3 — Validation Report

## 0. A finding that has to be stated before any numbers: two conflicting "ground truths" exist in the repository

The two uploaded zips contain **three different versions of the same
validation claim**, and they disagree with each other materially:

| Document | Location | 2008 peak-FPI error | Status of that document |
|---|---|---|---|
| `JOURNAL_PAPER.md` | `sro/...delivery/backend/model_src/...` | **2.4%** (claims PASS) | Narrative prose, **not** regenerated after later bug fixes; no accompanying verification artefact |
| `FINAL_VERIFICATION_REPORT.md` | same repo, session log | **31.2%** (explicitly still FAIL) | A session changelog, itself superseded by later fixes described within it |
| `report/manuscript.md` + `report/table_05_retrodiction.csv` + `report/verification_report.csv` | `Food_Energy_SRA_PUBLICATION_FREEZE` | **83.3%** (FAIL) | **The only version with an automated cross-check**: `verification_report.csv` re-derives every number in the manuscript from the regenerated data files and reports 68/68 checks passing |

**I am treating the third source — the publication-freeze manuscript,
cross-verified against its own regenerated data — as authoritative**,
because it is the only one of the three whose numbers are demonstrably
self-consistent with the current code and data rather than asserted in
prose. This means the 2.4%-error claim currently sitting in your live
delivery app's vendored docs (`sro/.../JOURNAL_PAPER.md`) **is stale and
should not be shown to an ASABE audience** — it describes a version of the
model that predates the ε_ef per-country calibration, the RC_PRICE_AMP
recalibration to 0.021, and the corrected FAO FPI(0) initialisation, all of
which are present in the current code (I confirmed `RC_PRICE_AMP = 0.021`
and per-country `epsilon_ef` are identical between the live delivery
backend and the publication-freeze source — the **code** is in sync; only
the **narrative documentation** in the live app has fallen behind).

**Action needed before Phase 7 (scientific report) is finalised:** either
regenerate `JOURNAL_PAPER.md` from the current pipeline output, or replace
it with the publication-freeze `manuscript.md`. I have not silently done
this for you — that decision (and confirming the freeze numbers are what
you want to stand behind) should be explicit, since it changes the paper's
central validation claim from "success" to "partial, honestly-scored
failure with diagnosed causes."

---

## 1. Retrodiction Results (from `table_05_retrodiction.csv`, verified)

| Criterion | Real 2008 | Model 2008 | Error | Pass? | Real 2022 | Model 2022 | Error | Pass? |
|---|---|---|---|---|---|---|---|---|
| Peak FPI (normalised) | 1.177 | 2.157 ± 0.455 | 83.3% | **FAIL** | 1.445 | 1.575 ± 0.255 | 9.0% | **PASS** |
| Peak export ban rate | 0.25 | 0.571 | — | FAIL | 0.20 | 0.457 | — | PASS |
| Trigger-dependency ratio | >3× | 3.0× | — | FAIL (boundary) | >3× | 3.0× | — | FAIL (boundary) |
| PAR (order of magnitude) | 0.93bn | 0.49bn (0.53×) | — | PASS | 0.83bn | 0.41bn (0.50×) | — | PASS |
| Homer-Dixon 4 properties | 4/4 | 2/4 | — | FAIL | 4/4 | 2/4 | — | FAIL |
| Stability (no-trigger FPI) | <1.20 | 2.760 ± 0.254 | — | FAIL | <1.20 | 2.760 ± 0.254 | — | FAIL |

**Pattern-oriented model (POM) score: 0.417** (verified value from
`verification_report.csv`), against the target of ≥0.70 stated in the
model's own methodology.

### 1.1 Interpreting the 2022 result honestly
The 2022 Ukraine-crisis peak FPI is within 9.0% of the real FAO value —
this is a genuine, reproducible pass, and it is the strongest single
validation result in the model. Export-ban rate and PAR both pass for
2022 as well (3 of 6 criteria pass for 2022).

### 1.2 Interpreting the 2008 result honestly
The 2008 episode is currently the model's weakest result (83.3% peak-FPI
error, up from the 31.2% reported mid-session in `FINAL_VERIFICATION_REPORT.md` —
i.e., a later fix that improved something else appears to have made the
2008 fit *worse*, not better; this trade-off is real and should be reported
as such, not hidden). Only the PAR criterion passes for 2008 (1 of 6).
The documented cause (Section 3.4 of the publication-freeze manuscript) is
that the technology multiplier A_i remains fixed at 2022 calibration for
the 2008 run rather than being re-derived from year-2000 FAO crop-production
data — a known, named limitation, not an unexplained failure.

### 1.3 The stability (no-trigger) failure is a genuine structural finding, not a bug
Both episodes report the *same* no-trigger stability FPI (2.760 ± 0.254)
against a target of <1.20. Because this occurs even with **zero** injected
triggers, it means the model's baseline dynamics alone — with no crisis
scenario applied at all — produce sustained price elevation. Given that
Phase 1 documentation identifies 12 of 35 nodes (Central Africa, East
Africa, Nigeria, Pakistan, and others) as structurally under-resourced
even in their calibrated starting state, this is consistent with — but not
proof of — a genuine structural-vulnerability finding rather than a
calibration bug. It should be reported as an open question requiring
further investigation (e.g., isolating whether the STC engine's
FS_index accumulation rate alone, absent any trigger, is high enough to
force chronic overload), not asserted as settled either way.

### 1.4 The trigger-dependency test fails at the boundary, not by a wide margin
Both episodes show a 3.0× stressed-vs-healthy overload ratio against a
pass threshold of >3×. This is a **boundary failure**, not a large miss —
worth flagging distinctly from the 83.3%/9.0% FPI errors, since a reviewer
will read "3.0× vs >3×" very differently from "FAIL" without that context.

---

## 2. Coping-Capacity (CC) Calibration — genuinely strong result

From `verification_report.csv`, cross-checked against
`table_02_cc_weights.csv`:

- Cross-validated R² = **0.8592**, MAE = **0.0291**
- Training R² = 0.9395 (train/CV gap = 0.080 — a moderate but disclosed
  overfitting gap, consistent with the manuscript's own framing of this as
  a calibration aid on a small sample, not a discovery tool)
- Feature-importance weights (sum to 1.0): technology **0.4934**, capital
  **0.2691**, political risk **0.1152**, climate vulnerability **0.1206**,
  reserve adequacy **0.0015**

This is the strongest quantitative result in the validation package: it is
a real, held-out cross-validated regression metric, not a retrodiction
score subject to the annual-timestep limitation. It supports the claim
that "technology and capital together explain the large majority of
coping-capacity variance" (0.4934 + 0.2691 = 0.7625), a genuine,
data-supported finding.

**One caveat that must accompany this result in any publication:** the CC
target itself is derived from FAO undernourishment data (per
`docs/EQUATIONS.md`), and the same undernourishment values also appear as
`undernourishment_baseline_pct` in `node_parameters.csv`, which is used
elsewhere for cross-checking. This should be double-checked for circularity
before publication — if the CC regression target and a downstream
validation check both trace back to the same undernourishment series, that
is not independent validation. I have not been able to confirm from the
files reviewed so far whether this circularity exists; it is a concrete
item for a code-level audit before Phase 7 finalisation, not something I am
asserting is a problem.

---

## 3. Sensitivity Analysis — reproducible, strong finding

- OAT: RC_PRICE_AMP range = 1.7338 vs. second-ranked EROI_DECLINE range =
  0.0084 → **ratio = 206×** (verified)
- Sobol: RC_PRICE_AMP total-order sensitivity ST = 0.635 for price outcomes
  (dominant); EROI_DECLINE dominant for population-at-risk (ST = 0.432)

This is the one result that is consistent across all three documents
reviewed (journal paper, verification report, publication-freeze
manuscript) — the magnitude of the dominance ratio differs (journal paper
says 100×, freeze says 206×) because the underlying calibration changed
between runs, but the *qualitative* finding — RC cascade amplification
dominates every other parameter by roughly two orders of magnitude — is
robust across every version of the model I found in the repository. This
is the single scientific claim I'd recommend leading with, precisely
because it survived recalibration.

---

## 4. What "improve it only if scientifically justified" means here

Per your instruction, I have **not** attempted to improve the 2008
retrodiction score in this pass — doing so would mean changing model
parameters to fit a known historical target, which is calibration-to-target
rather than validation, unless done through the same principled route
already used elsewhere in this project (e.g., the A_i-from-FAO-2000-data
fix that is *named but not yet implemented* in the freeze). If you want me
to implement that specific, already-diagnosed fix (re-deriving A_i(2000)
from FAO crop production data for the 2008 run, exactly as the
verification report specifies), that is a legitimate next step — but it is
a code change I should make transparently and re-verify with the same
`verification_report.csv` cross-check pattern already established in this
repo, not something to fold silently into a documentation pass.

---

## 5. Honest summary for an ASABE reviewer

- **Real, strong result:** CC calibration (R²=0.86 CV) and the RC cascade
  dominance finding (>200× other parameters), both reproducible.
- **Real, partial result:** 2022 retrodiction passes 3/6 criteria including
  the headline FPI metric (9.0% error); this is presentable as-is.
- **Real, honest failure requiring a limitations section:** 2008
  retrodiction (1/6 criteria), with a named, specific, uncorrected cause.
- **Unresolved, needs a decision before Phase 7:** which manuscript is
  "the" scientific report — the stale 2.4%-error version currently
  shipped in the live app, or the verified 83.3%-error freeze version.
  I recommend the latter; shipping the former to an international
  scientific audience would not survive a reviewer re-running the code.
