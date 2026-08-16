# Global Policy: EROI Decline

## Purpose

Represents the secular, long-run decline in global Energy Return on
Investment (EROI) as easily-accessible fossil fuel reserves deplete and
extraction shifts to lower-quality sources -- a real, well-documented
physical trend in the energy literature, applied here as a slow,
monotonic background pressure on every node's energy stress.

## Equation

```
EROI_penalty(t+1) = min(0.50, EROI_penalty(t) + EROI_DECLINE_RATE)
```

Feeds into each node's energy stress index (`ES_index`) via the
`eroi_component` term -- see `docs/architecture/CAUSAL_DECOMPOSITION.md`
Section 7 for the full ES_index equation.

## Current value

`EROI_DECLINE_RATE = 0.003` (0.3%/year), `model/src/energy.py`.

## Scientific source

Comment in source: "IEA conventional oil" -- a real, cited directional
basis (IEA World Energy Outlook reports document declining EROI for
conventional oil extraction), but the exact 0.3%/year figure's precise
sourcing was not independently re-verified this session; treat as
directionally-grounded, not independently re-audited.

## Affected nodes

All 35, uniformly (this is a single global accumulator,
`EnergyModule._eroi_penalty_global`, shared across every node's
`ES_index` calculation -- not node-differentiated).

## Affected variables

`agent.energy_stress_index` (all nodes); indirectly, production (via the
energy-food coupling Arrow 1) and FS_index accumulation.

## Sensitivity

Second-ranked (after `RC_PRICE_AMPLIFICATION`) in the Sobol sensitivity
analysis for population-at-risk outcomes specifically (total-order
sensitivity ST=0.432, `docs/validation/VALIDATION_REPORT_INITIAL.md`
Section 3) -- a real, reproducible, model-wide finding.

## Known structural property (not a bug, a documented design note)

This term is monotonically non-decreasing and never resets -- it
represents a real secular trend, not a per-scenario shock. Combined with
`ES_index`'s separate `demand_growth` term (linear in elapsed simulated
steps, documented in `docs/architecture/CAUSAL_DECOMPOSITION.md` Section 7
as "capable of unrealistic runaway behaviour" over long horizons), this
is flagged as the item most in need of attention before any multi-decade
policy-search run -- see `LIMITATIONS.md`.

## Optimisation space

Not exposed as a searchable policy lever (a model-calibration constant,
not an intervention). The corresponding POLICY response to rising energy
stress is `make_energy_intervention_lever` (`docs/policies/ENERGY_INTERVENTION.md`),
which acts on a node's `energy_fuel` supply directly rather than this
background trend constant.
