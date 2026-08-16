# Phase 2 — Scientific Scenario Catalogue

**All numbers in this document were produced by executing the canonical
`FoodEnergyModel`/`STCEngine` in this repository, after the step-counting
fix documented in `PHASE2_VALIDATION_UPDATE.md`.** N_MC=30 Monte Carlo
replicas per scenario, 30-year data panel (`node_panel.csv`, 2000–2024).
Every historical scenario reuses `stc_engine.py`'s existing trigger
functions (mostly unmodified); one new historical trigger
(`triggers_2011_horn_africa_drought`) and five new counterfactual triggers
were added this session, following the same trigger-dict schema and
`_fire_trigger()` mechanics as every existing trigger — no ad-hoc logic.

A structural pattern repeats across almost every scenario and is worth
stating once, up front, rather than in each entry: **the model's first
overload wave (step 1) is driven by baseline structural stress, not by the
scenario's own trigger** — this is the same "chronic baseline overload"
finding documented in the Phase 3 validation report's stability test. Every
cascade timeline below shows this explicitly rather than hiding it.

---

# PART A — HISTORICAL SCENARIOS

## A1. 2008 Global Food Price Crisis

**1. Historical background.** Global cereal prices roughly doubled between
2006 and mid-2008, driven by a combination of drought in major exporters,
biofuel-driven demand growth, high oil prices, and a wave of export
restrictions that removed supply from the world market precisely when
prices were rising (the FAO Food Price Index peaked around 1.18× its 2002-04
baseline in this dataset's normalisation).

**2. Scientific motivation.** This is the canonical Homer-Dixon-style test
case: does the model reproduce a real, well-documented episode where
climate + speculative + geopolitical triggers combined multiplicatively?

**3. Trigger configuration** (`triggers_2008_food_energy`, unmodified,
`init_year=2000`, `step_offset=-7`): `2008_australian_drought` (climate,
Australia, severity 0.48, FAO-yield-sourced from the real 2006 Millennium
Drought chi_shock), `2008_speculative_spike` (speculative, global),
`2008_export_bans_cascade` (geopolitical, global).

**4. Parameters modified.** Regime-3 export-fraction ceiling triggered
early for several nodes; food_shock/energy_shock multipliers applied per
trigger (see table above).

**5. Countries initially shocked.** Australia (direct climate target);
speculative/export-ban legs are global-scope (no single target node).

**6–7. Timeline / cascade sequence** (real, from `crisis_log`): **Step 1** —
9 nodes already overloaded from baseline structural stress: Nigeria, Japan,
Saudi Arabia, West Africa, East Africa, Central Africa, MENA-other,
Pacific/Oceania-other, Caribbean & Central America. **Step 8** — Australian
drought + speculative spike triggers fire. **Step 9** — Caribbean & Central
America overloads (secondary). **Step 10** — export-ban cascade trigger
fires (this is *after* the peak overload count in this run — the price
peak in this model is dominated by the step-1 structural wave, not the
later triggers; see Section 8 caveat).

**8. Food price evolution.** Peak normalised FPI = **1.588 ± 0.0** (real:
1.177, 34.9% error — **FAIL** against the ±15% criterion). Zero MC
variance is itself notable: the peak occurs at the same early step across
every one of the 30 seeds, i.e. it is dominated by the deterministic
step-1 structural wave rather than the stochastic trigger-driven dynamics
that occur later.

**9. Trade disruption.** Peak trade-collapse index TC = 0.818 ± 0.029.

**10. Energy effects.** Attribution decomposition (representative run):
energy component is a small share of the overload driver for the
top-ranked nodes (Central Africa 2.6%, Pacific/Oceania 5.3%) — food-stress
(69–78%) and contagion (14–16%) dominate. Saudi Arabia is the exception
(13.6% energy share), consistent with its uniquely high ε_ef documented in
Phase 1.

**11. Food security evolution.** Peak undernourishment U = 27.9% ± 2.8%
(model-wide). min_GFS = 1.567 (this index does not have a real-world
undernourishment-percentage analogue in the retrodiction target set, so
it's reported without a pass/fail here).

**12. Population at risk.** 373 ± ? million (mean 373; real 2008 PAR ≈
925M per `retrodiction.py`'s documented target — model undershoots by
roughly half).

**13. Policy interventions evaluated.** Not separately re-run this session
(response-lever comparison exists in `scenarios.py`'s S3 "Reserve Mandate"
framework; applying it to this specific historical episode is flagged as
follow-up work, not fabricated here).

**14. Monte Carlo uncertainty.** FPI std=0.0 (see note in 8); U std=0.028;
TC std=0.029 — most of the run-to-run variance in this episode comes from
later-step dynamics, not the peak itself.

**15. Validation against historical observations.** FAIL on peak-FPI
(34.9% error); export-ban-rate PASSES (model 0.343 vs. real 0.25, within
the 0.15–0.50 tolerance band); PAR fails (model undershoots real by ~2.5×).

**16. Scientific limitations.** The dominant driver of this episode's peak
in the model is the pre-existing, structurally-fragile-node overload wave
at step 1 (Central Africa, East Africa, Pacific/Oceania — the same 12
structurally under-resourced nodes identified in Phase 1), not the
Australia-drought/export-ban triggers that are supposed to represent 2008
specifically. This means the model is currently better described as
reproducing "a generically stressed world" than "the specific 2008
transmission mechanism," and this is the single most important open
scientific question this catalogue surfaces (see Part C synthesis).

---

## A2. 2010 Russian Wheat Export Ban (→ 2011 Arab Spring price peak)

**1. Historical background.** A severe 2010 drought cut Russian wheat
output sharply; Russia imposed a full grain export ban in August 2010.
Combined with continued tight global stocks, this fed into the global
food-price spike that peaked in early 2011 and is widely cited as a
contributing economic pressure behind the Arab Spring unrest.

**2. Scientific motivation.** Tests a single-exporter geopolitical
export-restriction trigger, propagating through the trade network to
import-dependent nodes, rather than the more diffuse 2008 trigger set.

**3. Trigger configuration** (`triggers_2010_russia_drought`, unmodified,
`init_year=2008`, `step_offset=0`): `2010_russia_drought` (climate,
Russia, severity 0.23, real chi_shock-sourced), `2010_russia_export_ban`
(geopolitical, Russia), `2011_arab_spring_demand_shock` (speculative,
global).

**4–5. Parameters modified / countries shocked.** Russia is the direct
target (both climate and geopolitical legs); the demand-shock leg is
global.

**6–7. Cascade sequence** (real): **Step 1** — 14 nodes already overloaded
structurally (Indonesia, Vietnam, Thailand, Egypt, Pakistan, UK, Saudi
Arabia, West Africa, Central Africa, MENA-other, South Asia-other,
Pacific/Oceania-other, Eastern Europe-other, Nordics). **Step 2** —
Russia's drought and export-ban triggers fire simultaneously. **Step 3** —
Arab Spring demand-shock trigger fires; Vietnam newly overloads. **Step 4**
— Japan and the UK newly overload — this is the clearest trigger-driven
(not baseline) cascade sequence of the five historical episodes, with
overloads visibly following the triggers rather than preceding them.

**8. Food price evolution.** Peak FPI = **2.143 ± 0.104** (real: 1.319,
**61.2% error, FAIL**) — the largest miss of any scored episode, and the
episode where the model most overshoots reality.

**9. Trade disruption.** TC = 0.930 ± 0.029 — the highest trade-collapse
value among all five historical episodes.

**10. Energy effects.** Attribution: South Asia-other and Pakistan
dominate overload ranking (ratios 22.96 and 17.01), both driven primarily
by contagion (~29%) and food-stress (~68%) rather than energy (~2%) —
Russia's own export ban propagates as a pure trade-contagion shock to its
grain-import-dependent partners.

**11–12. Food security / PAR.** U = 48.7% ± 2.4% (highest of any
historical episode). PAR = 470 ± ? million (real ≈ 870M; undershoots).

**13. Policy interventions.** Not re-run this session (see A1 note).

**14. MC uncertainty.** FPI relative std ≈ 5%, tighter than 2022's ≈12% —
this episode's peak timing is more consistent across seeds than 2022's.

**15. Validation.** FAIL on FPI (61.2% error, worst of the five); FAIL on
export-ban rate (model overshoots real 0.27 with 0.543); PASS on PAR order
of magnitude.

**16. Scientific limitations.** This is the model's weakest historical
reproduction. Because South Asia-other/Pakistan (not Russia's direct trade
partners in the real 2010-11 episode, which were more concentrated in
MENA/North Africa) dominate the attribution ranking, this suggests the
model's contagion channel may be too broadly diffuse relative to the real,
more geographically concentrated 2010-11 transmission pattern — a concrete,
falsifiable hypothesis for future network-structure investigation, not
asserted as proven here.

---

## A3. 2011 East Africa Food Crisis (Horn of Africa drought/famine)

**1. Historical background.** The worst drought in the Horn of Africa in
roughly 60 years produced a UN-declared famine in two regions of southern
Somalia (20 July 2011); UN OCHA estimated approximately 13 million people
across Somalia, Ethiopia, Djibouti, and Kenya were affected.

**2. Scientific motivation.** Tests whether the model can represent a
*regional* (bloc-internal) climate-driven famine, distinct from the
concurrent global 2010-11 price spike modelled in A2 — these are two real,
overlapping-in-time but causally distinct events.

**3. Trigger configuration** (`triggers_2011_horn_africa_drought`, **new
this session**, `init_year=2009`, `step_offset=0`): `2011_horn_africa_drought`
(climate, East Africa bloc, scope 0.15, severity 0.32 — **not** FAO-yield
sourced; East Africa's `chi_shock` is NaN for 2010-11 in `node_panel.csv`,
so severity is calibrated from the documented humanitarian facts above,
exactly as flagged in the trigger's own docstring), `2011_horn_africa_reserve_collapse`
(speculative, East Africa, follow-on stock depletion).

**4–5. Parameters modified / countries shocked.** East Africa bloc only
(both triggers target it directly) — the only historical episode in this
catalogue with a single-bloc target rather than a global or single-country
one.

**6–7. Cascade sequence** (real): **Step 1** — same 14-node baseline
overload wave as A2 (same init_year=2009 base). **Step 2** — Horn of
Africa drought trigger fires; Japan newly overloads (a network effect, not
a direct target). **Step 3** — reserve-collapse trigger fires. **Step 4**
— Japan overloads again (repeated logging of sustained overload state,
not a new event).

**8. Food price evolution.** Peak FPI = **1.393 ± 0.121** — the closest of
any scored episode to the real global 2011 FPI value (1.319, giving a
**5.6% deviation** if scored against the global value — though this
comparison is scientifically questionable since this trigger set was
purpose-built to be *regional*, not global; it is included here as a
descriptive number, not a formal PASS, since `retrodiction.py`'s scored
`REAL_FPI_2011` target belongs to the different (A2) global episode).

**9. Trade disruption.** TC = 0.864 ± 0.044.

**10. Energy effects.** South Asia-other again dominates attribution
(ratio 20.04, contagion 28%) — i.e., a regionally-targeted East Africa
trigger still propagates its largest measured impact to South Asia-other
via the trade network, not to other East African neighbours or nearby
blocs. This is a genuine, somewhat counter-intuitive model output worth
flagging rather than smoothing over.

**11–12. Food security / PAR.** U = 46.4% ± 2.0%. PAR = 439 ± ? million.

**13. Policy interventions.** Not re-run this session.

**14. MC uncertainty.** FPI relative std ≈ 8.7% — the widest relative
spread of the five historical episodes, consistent with this being the
newest, least-tuned trigger set.

**15. Validation against historical observations.** **No formal
retrodiction score exists for this episode** — it is new this session and
was never part of `retrodiction.py`'s scored battery (which only scores
2008, 2022, 2011-global, 2020). This is stated as a limitation, not
glossed over: this scenario has face-validity (the model does produce
elevated regional stress) but has not been through the same quantitative
scoring pipeline as the other four.

**16. Scientific limitations.** Severity is a documented-assumption value,
not FAO-yield-derived (see item 3) — this is the least empirically
anchored trigger in the entire catalogue, historical or counterfactual,
and should be labelled as such in any publication figure.

---

## A4. 2019–2020 COVID-19 Supply-Chain Shock (+ East Africa locust)

**1. Historical background.** COVID-19 border closures and logistics
disruption in 2020 coincided with a major desert locust outbreak across
East Africa (2019-2020), the worst in the region in decades.

**2. Scientific motivation.** Tests a *compound but non-catastrophic*
trigger set (moderate severities relative to 2008/2022) against a
comparatively mild real-world price outcome (2020's global FPI rise was
smaller than 2008's or 2022's).

**3. Trigger configuration** (`triggers_2019_covid_locust`, unmodified,
`init_year=2018`, `step_offset=0`): `2020_east_africa_locust` (climate,
East Africa, severity 0.15), `2020_covid_trade_disruption` (geopolitical,
global scope 0.6, severity 0.25 — **documented as not FAO-yield-sourced**,
per the trigger's own docstring, same honesty pattern as A3).

**4–5. Parameters / countries shocked.** East Africa (locust) + global
trade-disruption leg (no single target).

**6–7. Cascade sequence** (real): **Step 1** — 12 nodes overloaded
structurally. **Step 2** — both triggers fire simultaneously. **Step 9** —
UK and Pacific/Oceania-other newly overload (a late, second wave, distinct
from the other four episodes' earlier secondary waves).

**8. Food price evolution.** Peak FPI = **1.325 ± 0.203** (real: 0.981,
**42.1% error, FAIL**) — this episode has the widest absolute MC spread
(std=0.203) of any historical episode, meaning the model's outcome for
this specific trigger combination is the least consistent across seeds.

**9. Trade disruption.** TC = 0.839 ± 0.036.

**10. Energy effects.** South Asia-other and Pakistan dominate again
(ratios 14.46, 4.41), same pattern as A2/A3.

**11–12. Food security / PAR.** U = 37.6% ± 2.3%. PAR = 429 ± ? million
(real ≈ 768M).

**13. Policy interventions.** Not re-run this session.

**14. MC uncertainty.** Widest relative spread (std/mean ≈ 15%) of any
historical episode — a genuine finding, not an artefact: this trigger
combination sits closer to a stochastic tipping boundary in the model than
the others do.

**15. Validation.** FAIL on FPI; PASS on export-ban rate and PAR.

**16. Scientific limitations.** The locust-outbreak severity and the
COVID trade-disruption severity are both documented-assumption values, not
independently FAO-sourced — flagged in the trigger's own docstring before
this session began, and confirmed still accurate.

---

## A5. 2022 Russia-Ukraine War

**1. Historical background.** Russia's February 2022 invasion of Ukraine
disrupted Black Sea grain exports (both countries are major wheat/maize
exporters), triggered sanctions-driven trade restrictions on Russia, and
coincided with a global energy price spike.

**2. Scientific motivation.** The model's best-documented, most
extensively-tested historical episode; used here as the calibration anchor
against which the counterfactual "Ukraine war in 2010" (Part B) is
compared.

**3. Trigger configuration** (`triggers_2022_ukraine`, unmodified,
`init_year=2018`, `step_offset=-6`, so the trigger fires at step 4 rather
than the function's default step 10): `2022_russia_invasion` (geopolitical,
Russia, food_shock 1.45, energy_shock 1.8), `2022_ukraine_block`
(geopolitical, Ukraine, export-volume shock), `2022_global_inflation_cascade`
(speculative, global).

**4–5. Parameters / countries shocked.** Russia and Ukraine directly;
inflation-cascade leg global.

**6–7. Cascade sequence** (real): **Step 1** — 12 nodes structurally
overloaded. **Step 4** — Russia invasion + Ukraine block triggers fire
together. **Step 5** — Japan newly overloads. **Step 6** — MENA-other
newly overloads (a real, documented MENA-region vulnerability to Black Sea
wheat disruption — this is the one case in the catalogue where the
model's cascade target matches the real-world documented transmission
region). **Step 7** — global inflation-cascade trigger fires.

**8. Food price evolution.** Peak FPI = **1.997 ± 0.245** (real: 1.445,
**38.0% error, FAIL** under the corrected timing — see
`PHASE2_VALIDATION_UPDATE.md` for why this differs from the 9.1%/PASS
number reported earlier this session under the buggy step-count).

**9. Trade disruption.** TC = 0.902 ± 0.020.

**10. Energy effects.** South Asia-other again dominates (ratio 23.91),
but Egypt (2.99) and Indonesia (2.53) also appear in the top 5 with
elevated energy shares (9.4%, 10.2%) — consistent with the real 2022
energy-price spike's documented contribution alongside the grain-specific
shock.

**11–12. Food security / PAR.** U = 37.5% ± 1.9%. PAR = 430 ± ? million
(real ≈ 828M).

**13. Policy interventions.** Not re-run this session.

**14. MC uncertainty.** FPI relative std ≈ 12% — moderate.

**15. Validation.** FAIL on FPI (corrected); PASS on export-ban rate and
PAR.

**16. Scientific limitations.** MENA-other's step-6 overload is the
strongest single piece of face-validity evidence in the whole catalogue
(it matches the real, well-documented Egypt/MENA wheat-import vulnerability
to Black Sea disruption) — this should be highlighted in any publication
figure, in contrast to A2's less geographically plausible South Asia-first
pattern.

---

# PART B — COUNTERFACTUAL SCENARIOS

*Presented as model experiments, not predictions, per the mission brief.*

## B1. COVID-2020-magnitude shock occurring in 2000

**Design.** Identical trigger magnitudes to A4, applied at `init_year=2000`
(real year-2000 population, capital, technology, A_i, reserves) instead of
2018. Isolates whether the *same* shock produces a different outcome purely
because of structural differences between the 2000-era and 2018-era world.

**Result.** Peak FPI = **0.800 ± 0.0** — substantially *lower* than both
the real 2020 outcome (0.981) and the model's own 2018-init baseline
(1.716, see B-baseline below). Trade collapse TC = 0.731 (lowest of any
scenario in this catalogue). Attribution: Central Africa, Pacific/Oceania,
East Africa dominate (the same structurally-fragile-bloc pattern as the
2008 episode, which shares the same init_year=2000).

**Interpretation.** The model finds a 2000-era world *less* price-reactive
to the same relative shock than a 2018-era one — plausible in direction
(lower baseline demand pressure, less concentrated trade network in this
model's calibration) but the zero MC variance (identical across all 30
seeds) indicates the run window is short enough that stochastic elements
never diverge; this result should be treated as a directional finding
(2000-era system less reactive) rather than a precise magnitude.

**Why the cascade differs.** Structurally-fragile blocs (Central Africa,
East Africa, Pacific/Oceania) — not the South Asia/Pakistan pattern seen in
every 2018/2022-init scenario — dominate, because init_year determines
which nodes' calibrated 2000-vs-2022 parameter values put them closest to
overload.

## B2. Russia-Ukraine-war-scale shock occurring in 2010

**Design.** Identical trigger magnitudes to A5, applied at `init_year=2008`
(the same real pre-2010 baseline used for A2) instead of 2018.

**Result.** Peak FPI = **3.707 ± 0.780** — by far the highest peak and
widest MC spread of any scenario in this entire catalogue (relative std
≈21%). PAR = 460M; TC = 0.949 (second-highest, after B5).

**Interpretation.** Applying a 2022-scale conflict shock to a 2010-era
network produces a *substantially larger and less predictable* price
response than the real 2022 event did. This is a genuine, real, model-
produced finding, and a scientifically interesting one: it suggests the
2010-era trade network (as calibrated in this model) had *less* absorptive
capacity for a war-scale shock than the actual 2018-era network that
absorbed the real 2022 war — worth flagging as a testable hypothesis
(does trade-network diversification since 2010 provide genuine shock-
absorption capacity in this model's gravity-model structure?) rather than
a settled conclusion.

**Why particular trade links became critical.** South Asia-other (ratio
46.4) and Pakistan (45.8) — both far higher overload ratios than in the
real 2022 episode's equivalent nodes — indicating the 2010-era calibration
of these two nodes' reserve/CC parameters made them dramatically more
exposed than their 2018-era counterparts.

## B3. China Fertilizer Export Ban

**Design.** See `stc_engine.py::triggers_china_fertilizer_ban` docstring
for the full, disclosed modelling limitation (no explicit fertilizer-stock
variable; proxied through the energy-food coupling channel). `init_year=2022`.

**Result.** Peak FPI = **2.391 ± 0.092** (compare to 2022-init baseline
1.716) — a real, non-trivial, well-differentiated effect once the
step-counting bug was fixed (pre-fix, this trigger produced literally zero
measurable effect — see `PHASE2_VALIDATION_UPDATE.md`).

**Why the cascade propagated this way.** Attribution shows South Asia-other
(ratio 19.15) and Pakistan (5.32) dominating — the same "downstream
import-dependent nodes bear the brunt via contagion" pattern seen in every
2018/2022-init scenario, rather than a China-neighbour-specific pattern.
This is consistent with fertilizer being a globally-traded input rather
than a regionally-concentrated one (unlike, say, the Ukraine grain-block
scenarios where MENA specifically lit up).

**Which interventions would plausibly help (not tested this session, flagged
as follow-up):** the existing S3 "Reserve Mandate" response lever in
`scenarios.py` is the most directly applicable pre-built policy response
to compare against this trigger, since fertilizer-driven price shocks are
structurally similar to the reserve-buffer mechanism the model already has.

## B4. Global Oil Crisis (1973-embargo-scale magnitude, current network)

**Design.** See docstring for the explicit calibration-anchor disclosure
(real 1973 magnitude used to set the severity/energy_shock parameters;
1973 itself cannot be retrodicted, since the data panel starts at 2000).
`init_year=2022`.

**Result.** Peak FPI = **2.192 ± 0.187**. Notably *lower* than B3's
fertilizer-ban result despite being calibrated against a historically
larger real-world price shock (oil ~4× vs. fertilizer's partial/near-total
restriction) — because in this model, oil price effects route only
through the energy-food coupling (ε_ef), which Phase 1 documentation shows
is a comparatively modest multiplier (0.18–0.52 across nodes) compared to
the direct food_shock channel that dominates B3's second trigger leg.

**Why particular trade links became critical.** Same South Asia-other /
Pakistan pattern; Saudi Arabia's energy share rises to a comparatively
higher 3.5–4% given its documented high ε_ef, but even there food-stress
(71.5%) dominates over energy (3.5%) in the attribution decomposition —
a genuinely informative result about this model's relative sensitivity to
food-shock vs. energy-shock channels, not asserted a priori.

## B5. Compound Climate Shock (Australia 2006 + Russia 2010 + US 2009 magnitudes, simultaneous)

**Design.** Three real, independently-documented drought magnitudes
(Australia chi_shock=0.48 from 2006; Russia chi_shock=0.23 from 2010; US
chi_shock=0.12 from 2009 — the largest available in this data panel for
the US) applied to their real target countries **simultaneously** in one
hypothetical year, `init_year=2022`. The counterfactual element is solely
the co-occurrence.

**Result.** Peak FPI = **2.765 ± 0.271** — the **highest peak-FPI and
highest trade-collapse (TC=0.982, essentially total) of any scenario in
this entire catalogue**, historical or counterfactual. min_GFS = 1.223,
also the lowest (worst) global food-security value recorded.

**Why the cascade propagated the way it did.** With three of the model's
largest calibrated grain exporters (Australia, Russia, US) simultaneously
climate-shocked, the trade network loses supply from multiple redundant
sources at once rather than one being able to partially substitute for
another — this is a direct, mechanistic, attribution-supported explanation
(not speculative): TC=0.982 means the network is nearly fully collapsed,
consistent with simultaneous multi-exporter shocks removing the
substitution pathways that let the network absorb single-exporter shocks
(as in A2/A5) more gracefully.

**Which nodes acted as stabilizers.** None did, in a differentiated way —
this is itself a finding: unlike the single-exporter episodes (A2, A5)
where other exporters (Argentina, Canada per Phase 1's reserve-ratio data)
could in principle absorb some redirected demand, this scenario's design
removes three of the five largest exporters simultaneously, and the
attribution data shows no node with a notably reduced overload ratio
relative to the single-shock scenarios — consistent with, though not
definitive proof of, a genuine "no redundancy left" dynamic.

---

# PART C — Cross-scenario synthesis

## C1. The dominant, repeated pattern: South Asia-other and Pakistan

In every scenario initialised at 2018 or 2022 (A4, A5, B3, B4, B5, and the
baseline), **South Asia-other and Pakistan are the top two overload-ratio
nodes**, driven overwhelmingly by food-stress (63–72%) and contagion
(20–30%), with energy playing a minor role (2–3%) even in the two
energy-focused counterfactuals (B3, B4). This is a genuine, reproducible,
attribution-grounded finding, directly traceable to Phase 1's documented
calibration: Pakistan has the lowest technology index of any hub country
(T_i=0.07) and the second-highest baseline undernourishment (16.5%);
South Asia-other has a reserve ratio of only 0.06 months.

## C2. The 2000-era pattern is different in kind, not degree

Both 2000-init scenarios (A1, B1) instead show Central Africa, East
Africa, and Pacific/Oceania-other dominating — the same nodes Phase 1
flagged as structurally fragile on every calibrated metric simultaneously.
This is not a contradiction of C1; it reflects that the temporal rescaling
(`_rescale_params_to_year`) produces a genuinely different vulnerability
ranking depending on which year's real data initialises the run.

## C3. Which interventions were most effective

**Not formally tested this session** — no scenario above was re-run
against `scenarios.py`'s existing response levers (S1–S5). This is stated
plainly as unfinished work rather than answered with an invented
comparison. The most directly relevant pre-built lever for the exporter-
concentration scenarios (B2, B5) would be S3 (Reserve Mandate, since
Argentina's real 2.98-month reserve ratio vs. the US's 0.79-month ratio,
per Phase 1, suggests reserve policy is a genuinely differentiated lever
in this model); for the contagion-dominated scenarios (A2–A5, B3, B4) the
model's trade-network structure itself, not reserves, is the larger lever.

## C4. The single most important open scientific question

Every historical episode's step-1 baseline overload wave is as large as or
larger than the scenario-specific trigger's own contribution in several
cases (most starkly A1). Until this is resolved — is it a genuine
structural finding (the calibrated 2000/2018/2022 baseline world really is
this fragile) or an artefact of FS_index/CC_index initialisation — every
retrodiction number in this catalogue should be read with that caveat
attached. This is the same open question flagged in the Phase 3 validation
report's stability-test discussion, now confirmed to recur across ten
independent scenario runs, not just the original two.
