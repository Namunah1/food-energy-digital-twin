# Global Policies — Handbook Index

**Read this first, before any individual global-policy document**: most
of the "example" global policies commonly discussed for a food-system
Digital Twin (carbon tax, interest rate, pandemic severity dial, UN food
aid budget, FAO reserve release, migration, global shipping capacity)
are **not implemented as distinct, named global policy mechanisms** in
this codebase. This is stated plainly here rather than fabricated
per-policy documents for things that don't exist.

## What IS real: global-scope constants and mechanisms

| Policy/mechanism | File | Constant/function | Current value | Affected variables | Affected nodes |
|---|---|---|---|---|---|
| RC price amplification | `stc_engine.py` | `RC_PRICE_AMPLIFICATION` | 0.021 | Global price index | All 35 (via shared global price) |
| EROI decline (global energy trend) | `energy.py` | `EROI_DECLINE_RATE` | 0.003/yr | Energy stress index | All 35 |
| Export-ban contagion rate | `trade.py` | `BAN_CONTAGION_RATE` | 0.30 | Neighbour export policy | All 35, network-propagated |
| Global reserve pool (mutual insurance) | `scenarios.py` | `make_global_reserve_pool_lever` | Policy-set (levy_rate, threshold) | Node-level `food_imperish` | All 35, one-time redistribution |
| Renewable energy push | `scenarios.py` | `make_renewable_push_lever` | Policy-set (boost_multiplier) | `energy_renew`, `xi_biofuel` | All 35 uniformly |
| Trade diversification | `political_economy.py` | `apply_diversification` | Policy-set (rho_cut, boost) | Network-wide `rho_ij`, `C_ij` | All 35, network-wide |
| Global oil/energy shock | `energy.py` | `apply_energy_shock` (reversible) | Trigger/policy-set | `energy_fuel`, energy price | Scope-configurable subset |

Each of these has its own document in this directory with the full
equation, calibration source, and optimisation-space bounds.

## What is PROPOSED, not implemented (per the Digital Twin architecture document)

| Proposed policy | Where proposed | Why not implemented |
|---|---|---|
| Carbon tax | Not previously specified anywhere in this project | No mechanism, no data source identified |
| Interest rate / global inflation | Not previously specified | No mechanism |
| Pandemic severity (as a tunable global dial) | Implicit in the `pandemic` trigger type | A real, node-scoped trigger type exists (`stc_engine.py`'s `pandemic` branch), but there is no single GLOBAL "pandemic severity" dial -- each pandemic scenario is configured per-trigger, not globally |
| UN food aid (budget-level) | `docs/architecture/DIGITAL_TWIN_ARCHITECTURE.md` Part B2 | The mechanism (node-to-node aid transfer) is real and implemented; a global UN-level BUDGET POOL distinct from the reserve pool is not |
| FAO reserve release | `docs/architecture/DIGITAL_TWIN_ARCHITECTURE.md` Part B1 | Implemented as `make_global_reserve_pool_lever`, described above -- the FAO-specific framing is illustrative naming, not a distinct mechanism |
| Migration | Not previously specified anywhere in this project | No mechanism, no data source, no population-movement logic exists |
| Global shipping capacity | Related to `logistics_disruption`, which exists per-edge but has no aggregate global dial | Partial: the underlying per-edge mechanism is real; a single global "shipping capacity" scalar is not |
| Global fertilizer supply (N/P/K aggregate) | `resource_drivers.py::FertilizerDriver` | The per-node stock mechanism is real; there is no single global aggregate supply dial distinct from summing node-level fertilizer_N/P/K |
| Water stress (global) | `resource_drivers.py::WaterStockDriver` | Per-node only; no global aggregate |

## Individual documents in this directory

- `RC_PRICE_AMPLIFICATION.md`
- `EROI_DECLINE.md`
- `EXPORT_BAN_CONTAGION.md`

The remaining real mechanisms in the table above (global reserve pool,
renewable push, trade diversification, energy shock/release) are
node-agnostic POLICY LEVERS rather than passive global parameters -- they
are documented in `docs/policies/` instead (Part 3 of this consolidation),
since that is the more accurate categorisation: a lever the optimiser can
set, not a background physical constant.
