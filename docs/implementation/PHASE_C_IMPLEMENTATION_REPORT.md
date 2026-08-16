# Phase C Implementation Report — Increment 1: Climate Drivers, Soil Quality, Triple-Counting Resolution

**Scope note:** Phase C as specified covers four subsystems (C1 rainfall/
temperature, C2 soil quality, C3 fertilizer N/P/K, C4 water reservoir
stock). This increment delivers C1 and C2 fully, tested, and resolves the
triple-counting prerequisite the spec required be addressed "as part of
the same change, not after." C3 and C4 are scoped as the next increment
(see "Next" below) rather than rushed — C3 specifically requires a second,
fertilizer-specific trade network per the Digital Twin architecture doc,
which is a larger, distinct piece of work deserving its own increment and
its own test suite, consistent with "implement incrementally, test
continuously."

## What was implemented

### 1. Triple-counting resolution (`model.climate_single_channel_mode`, default `False`)

Per Phase 2.5b's finding: `climate_modifier` fed production, FS_index, and
ES_index simultaneously, with the FS_index term adding no information
beyond what production already transmits via σ, and the ES_index term
applying a flat penalty regardless of a node's actual energy-climate
coupling. Resolved as an **opt-in flag**, not a silent behavioral change:

- **FS_index** (`stc_engine.py`): when enabled, the redundant
  `0.15×(1−climate_modifier)` additive term is zeroed — production's
  effect on σ already reaches FS_index via `stress_push`.
- **ES_index** (`energy.py`): when enabled, the flat `0.10×(1−climate_modifier)`
  term is scaled by each node's own `epsilon_ef` (Phase 1's per-country
  energy-food coupling calibration, 0.18–0.52) instead of applying
  uniformly — a node with weak energy-food coupling gets a
  correspondingly weaker climate-to-energy transmission.
- **Production and capital/disaster-loss channels are unchanged in both
  modes** — these are physically distinct consequences (yield loss,
  infrastructure damage), not redundant with the removed term.

**Why opt-in rather than a direct fix:** flipping the default would
retroactively change every existing historical retrodiction result
without your explicit sign-off, repeating the same kind of large,
unrequested shift the Phase 2.5 STC-sequencing merge caused. This gates
the resolution as available-and-tested but not silently forced onto the
validated baseline.

### 2. Continuous climate drivers (`climate_drivers.py`, new module)

`ContinuousClimateDriver` replaces the trigger-only discrete
`drought_index`/`heatwave_index` with a per-tick value derived from a
rainfall/temperature series, via the exact equations specified: `drought_index
= clip((climatology − current)/climatology, 0, 1)`, `heat_stress =
clip((anomaly − threshold)/range, 0, 1)`. Attached via a new optional
`model.climate_driver` slot (`None` by default), mirroring the existing
`energy_module` optional-plugin pattern already in the codebase — not a
new architectural idiom.

**Data status, stated plainly:** no real rainfall or temperature series
exists anywhere in this repository (re-confirmed this session:
`find data/raw -iname "*rain*" -o -iname "*precip*" -o -iname "*temp*"`
returns nothing). This module ships with `generate_synthetic_climatology()`,
explicitly labelled as placeholder-only in its own docstring and in every
place it's used. **Do not treat any output of this driver as calibrated
until real CHIRPS/Berkeley Earth data is sourced and integrated** — this
was flagged as a data-acquisition task in the Digital Twin spec (Section
12) and remains one; nothing in this implementation session obtained real
climate data.

### 3. Soil quality (`climate_drivers.py::SoilQualityDriver`)

New per-agent `soil_quality` state (default 1.0, undegraded), evolving via
`Q_soil(t+1) = Q_soil(t) + 0.02×(1−Q_soil(t)) − 0.03×max(0, intensity−1)`,
where intensity is a production-relative-to-own-historical-mean proxy.
Wired into the Cobb-Douglas production function as a new multiplicative
term, read via `getattr(self, "soil_quality", 1.0)` — byte-identical to
the original formula when the driver isn't attached. Attached via a new
optional `model.soil_driver` slot, same pattern as above.

**Calibration status: explicitly LOW confidence**, stated in the module
docstring and repeated here — `SOIL_REGEN_RATE`/`SOIL_DEGRADATION_RATE`
are illustrative placeholders, not sourced from FAO's Global Soil Organic
Carbon map or ISRIC SoilGrids (the Digital Twin spec's proposed real
sources, neither acquired this session).

## Real test results

`test_phase_c_climate_drivers.py`: **7/7 passed**, including the two
highest-risk checks:

- **Backward compatibility, verified through the full retrodiction
  battery, not just a summary check**: re-ran all 4 historical episodes
  inside the test itself. 2008 FPI error = 41.15%, 2022 = 109.2% —
  **exact match**, to the decimal, against the Phase B regression-gate
  values reported previously. Zero drift from any Phase C code when the
  new drivers are unattached.
- **Soil quality's production effect is real, not just wired**: default
  (Q_soil=1.0) leaves production unchanged; explicitly degrading to
  Q_soil=0.5 measurably cuts imperishable food production from
  3.226×10¹⁴ to 9.063×10¹³ — checked by direct before/after comparison,
  not inferred.
- **Triple-counting fix verified at the mechanism level, not just the
  aggregate**: with `climate_single_channel_mode=True` and an identical
  drought signal, FS_index came out lower (0.454 vs 0.517) than default
  mode — confirming the fix removes a term rather than silently doing
  nothing or, worse, adding one.
- **Continuous driver correctly derives drought signal from a rainfall
  series**: fed a synthetic series at 50% of climatological normal,
  confirmed mean drought_index ≈ 0.50 across nodes, matching the equation
  by hand.

## Known limitations, stated plainly

- **No real environmental data was acquired this session.** Both new
  drivers are mechanism-only, tested against clearly-labelled synthetic
  placeholders. This is the single largest gap before either driver can
  be used for a real published scenario — flagged in the code itself
  (module docstring), not just in this report.
- **`climate_single_channel_mode` is opt-in, so the RC-amplification and
  retrodiction validation status are entirely unchanged by this phase** —
  consistent with your instruction to keep that issue open without
  freezing engineering progress; this phase didn't touch it and didn't
  need to.
- **Soil quality's intensity proxy is a rough approximation** (current
  production relative to a running exponential mean of the node's own
  past production) — it has no independent validation against a real
  land-degradation dataset, again explicitly LOW confidence per the
  Digital Twin spec's own tiering discipline.
- **`ContinuousClimateDriver`'s `epsilon_ef`-based sensitivity mode uses
  water availability (`W_i`) as an irrigation-dependence proxy** — a
  real FAO AQUASTAT irrigation-share dataset (per the Digital Twin spec)
  was not sourced; this is an honestly-labelled interim substitute, not a
  claim of equivalence.

## Files changed / added

- `model.py` — three new optional slots (`climate_single_channel_mode`,
  `climate_driver`, `soil_driver`), two new no-op-by-default hook calls in
  `step()`
- `agent.py` — one new multiplicative term in the production function
  (`Q_soil`, getattr-defaulted)
- `stc_engine.py` — one conditional branch in `_accumulate_stress`
- `energy.py` — one conditional branch in `_compute_es_index`, one new
  optional parameter threaded through its caller
- `climate_drivers.py` — **new file**: equations, synthetic-data
  generator (clearly labelled), `ContinuousClimateDriver`,
  `SoilQualityDriver`
- `test_phase_c_climate_drivers.py` — **new**, 7 tests

**Nothing existing was rewritten.** Every edit is additive and
getattr/None-default-guarded; the full retrodiction battery, re-run
inside this phase's own test suite, confirms zero behavioral drift.

## Next: Phase C increment 2 (C3/C4) or Phase D

Two options, both legitimate next steps per your "implement incrementally"
instruction — worth a decision before proceeding:

1. **Finish Phase C** (C3 fertilizer N/P/K + the second trade network it
   requires, C4 water reservoir stock) before moving on, keeping the
   phases strictly sequential as originally ordered.
2. **Move to Phase D** (node-level policy optimisation) now, since Phase
   A/B's search infrastructure doesn't depend on C3/C4 being done, and
   circle back to finish Phase C's remaining pieces afterward.

I'd lean toward (1), matching the dependency order as specified, but
flagging the option since C3 in particular is a substantial, self-
contained piece of work (a new trade network, a Mitscherlich-type
production-response function) that will take a comparable amount of
effort to Phase A+B+C1/C2 combined.
