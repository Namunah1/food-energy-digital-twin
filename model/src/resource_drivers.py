"""
resource_drivers.py — PHASE C increment 2 (this session)
============================================================
Fertilizer N/P/K stocks (Digital Twin spec Part C3) and water reservoir
stock (Part C4).

DATA STATUS — read before using this module for any published claim:
No real fertilizer trade matrix (IFA country-level N/P/K trade) and no
real water-withdrawal-by-sector series (FAO AQUASTAT) were acquired this
session. Same honesty standard as climate_drivers.py's C1 implementation:
this module ships a REAL, correctly-implemented MECHANISM, tested against
CLEARLY-LABELLED placeholder data. The one piece of real, defensible
information used is qualitative, not quantitative: the identity of major
real-world fertilizer-producing nations (nitrogen: China, Russia, United
States, India; phosphorus: Morocco, China, United States; potash: Canada,
Russia, Belarus) is common, verifiable geographic/industrial knowledge,
not a fabricated statistic -- but the exact PRODUCTION QUANTITIES and
TRADE VOLUMES assigned to these nodes below are illustrative placeholders,
explicitly not sourced from IFA data, and must not be read as calibrated.

Deliberately NOT built: a full bilateral gravity-model fertilizer trade
network with fabricated capacity/cost/risk matrices (the Digital Twin
spec's original proposal). Building that with invented numbers would be a
more serious fabrication than this module's simpler, honestly-labelled
producer/consumer stock model. A real bilateral network is future work,
gated on acquiring real IFA trade data -- see FERTILIZER_PRODUCER_NODES
below for the drop-in replacement point.
"""
import numpy as np


# ── Fertilizer production response (Digital Twin spec Part C3) ─────────────

def mitscherlich_response(phi_ratio: float, max_response: float = 1.0,
                           rate_constant: float = 2.0) -> float:
    """
    Mitscherlich's law of diminishing returns (established agronomic
    functional form, not invented for this session): yield response to
    an input approaches a maximum asymptotically, with each additional
    unit of input producing progressively smaller gains.

        raw(phi_ratio) = max_response * (1 - exp(-rate_constant * phi_ratio))

    phi_ratio: current fertilizer stock / reference (calibration-year)
    stock, e.g. 1.0 = "normal" application level, 0.0 = none, 2.0 = double.

    rate_constant=2.0 is a placeholder shape parameter (LOW confidence,
    not fit to real yield-response trial data), chosen only for its
    qualitative diminishing-returns shape.

    NORMALISED so that mitscherlich_response(1.0) == 1.0 exactly: this
    model's A_i (TFP) calibration was already fit against REAL historical
    production, which already reflects historically-normal fertilizer
    application. Without normalising, phi_ratio=1.0 would spuriously
    multiply already-calibrated production by raw(1.0)≈0.86, silently
    double-penalising normal-level fertilizer use that A_i already
    accounts for. Normalising anchors "no change from calibrated
    baseline" at phi_ratio=1.0 and lets the function's shape apply only
    to DEVIATIONS from that baseline (shortage penalises more steeply
    than surplus rewards, consistent with diminishing returns).
    """
    raw = max_response * (1.0 - np.exp(-rate_constant * max(0.0, phi_ratio)))
    raw_at_reference = max_response * (1.0 - np.exp(-rate_constant * 1.0))
    if raw_at_reference <= 0:
        return 1.0
    return float(raw / raw_at_reference)


# ── Placeholder producer/consumer classification (see module docstring) ────

FERTILIZER_PRODUCER_NODES = {
    # node_name -> {"N": bool, "P": bool, "K": bool} -- real-world producer
    # status (qualitative, verifiable); REPLENISHMENT QUANTITIES below are
    # illustrative placeholders, not IFA-sourced.
    "China":           {"N": True,  "P": True,  "K": False},
    "Russia":          {"N": True,  "P": False, "K": True},
    "United States":   {"N": True,  "P": True,  "K": False},
    "India":           {"N": True,  "P": False, "K": False},
    "Canada":          {"N": False, "P": False, "K": True},
    "MENA-other":      {"N": False, "P": True,  "K": False},  # proxies Morocco (in this bloc)
}

DEFAULT_REPLENISHMENT_RATE = 0.08   # fraction of reference stock/step, producer nodes only
DEFAULT_DEPLETION_RATE = 0.10       # fraction of stock consumed per step of normal-intensity production


class FertilizerDriver:
    """
    PHASE C: optional model.step() component (attach via
    model.fertilizer_driver, None by default -- same optional-slot pattern
    as ContinuousClimateDriver/SoilQualityDriver). Manages Φ_i(t) = (N, P,
    K) stocks: producer nodes autonomously replenish; all nodes deplete
    stock proportional to production intensity; the resulting phi_ratio
    (current stock / reference) feeds Mitscherlich response into the
    Cobb-Douglas production function via agent.py's new
    `fertilizer_response` multiplicative term (getattr-defaulted to 1.0,
    byte-identical when this driver isn't attached).

    Equations:
        N_i(t+1) = N_i(t) + replenish_i(t) - depletion_i(t)
        replenish_i(t) = REPLENISH_RATE * N_reference_i   [producer nodes only]
        depletion_i(t) = DEPLETION_RATE * N_i(t) * production_intensity_i(t)
        phi_ratio_i(t) = mean(N_i, P_i, K_i) / mean(N_reference_i, P_reference_i, K_reference_i)
        fertilizer_response_i(t) = mitscherlich_response(phi_ratio_i(t))
    """

    def __init__(self, producer_nodes: dict | None = None,
                 replenishment_rate: float = DEFAULT_REPLENISHMENT_RATE,
                 depletion_rate: float = DEFAULT_DEPLETION_RATE,
                 reference_stock: float = 100.0):
        self.producer_nodes = producer_nodes or FERTILIZER_PRODUCER_NODES
        self.replenishment_rate = replenishment_rate
        self.depletion_rate = depletion_rate
        self.reference_stock = reference_stock  # arbitrary units, same scale for N/P/K
        self._historical_mean_production: dict = {}

    def step(self, model):
        for name, agent in model.agent_map.items():
            if not hasattr(agent, "fertilizer_N"):
                # initial condition: start at reference (i.e. phi_ratio=1.0,
                # "normal" application) for every node, not just producers --
                # depletion/replenishment imbalance emerges from dynamics,
                # not from an artificially advantaged starting point.
                agent.fertilizer_N = self.reference_stock
                agent.fertilizer_P = self.reference_stock
                agent.fertilizer_K = self.reference_stock

            prod = getattr(agent, "annual_production", None)
            hist = self._historical_mean_production.setdefault(name, prod or self.reference_stock)
            intensity = (prod / hist) if (prod and hist > 0) else 1.0
            if prod:
                self._historical_mean_production[name] = 0.95 * hist + 0.05 * prod

            producer_status = self.producer_nodes.get(name, {"N": False, "P": False, "K": False})
            for nutrient in ("N", "P", "K"):
                attr = f"fertilizer_{nutrient}"
                stock = getattr(agent, attr)
                depletion = self.depletion_rate * stock * max(0.1, intensity)
                replenishment = (self.replenishment_rate * self.reference_stock
                                  if producer_status.get(nutrient) else 0.0)
                new_stock = max(0.0, stock + replenishment - depletion)
                setattr(agent, attr, new_stock)

            mean_stock = (agent.fertilizer_N + agent.fertilizer_P + agent.fertilizer_K) / 3.0
            phi_ratio = mean_stock / self.reference_stock
            agent.fertilizer_response = mitscherlich_response(phi_ratio)


def make_fertilizer_redistribution_lever(donor_name: str, recipient_name: str,
                                          nutrient: str = "N", transfer_fraction: float = 0.20):
    """
    B4 REAL (upgrades the Phase B INTERIM proxy): direct transfer of a
    named nutrient stock between two nodes, analogous to make_food_aid_lever
    but operating on FertilizerDriver's fertilizer_N/P/K state instead of
    food_imperish. Requires a FertilizerDriver to be attached to the model
    (raises a clear error otherwise, rather than silently no-op'ing on a
    nonexistent attribute).
    """
    assert nutrient in ("N", "P", "K")

    def lever(model):
        donor = model.agent_map.get(donor_name)
        recipient = model.agent_map.get(recipient_name)
        if donor is None or recipient is None:
            print(f"[FertilizerRedistribution] WARNING: '{donor_name}' or '{recipient_name}' "
                  f"not found - no-op")
            return
        attr = f"fertilizer_{nutrient}"
        if not hasattr(donor, attr):
            raise RuntimeError(
                "make_fertilizer_redistribution_lever requires a FertilizerDriver to be "
                "attached to the model (model.fertilizer_driver = FertilizerDriver()) and "
                "at least one step to have run so fertilizer_N/P/K are initialised. "
                "For a driver-free proxy, use make_fertilizer_support_lever_INTERIM instead."
            )
        transfer = getattr(donor, attr) * transfer_fraction
        setattr(donor, attr, getattr(donor, attr) - transfer)
        setattr(recipient, attr, getattr(recipient, attr) + transfer)
        print(f"[FertilizerRedistribution] {donor_name} -> {recipient_name}: "
              f"{transfer:.2f} units of {nutrient} ({transfer_fraction:.0%} of donor stock)")
    lever.__name__ = f"fert_redist_{nutrient}_{donor_name.replace(' ','')}_to_{recipient_name.replace(' ','')}"
    lever.lever_params = {"donor": donor_name, "recipient": recipient_name,
                           "nutrient": nutrient, "transfer_fraction": transfer_fraction,
                           "requires": "FertilizerDriver attached to model"}
    return lever


# ── Water reservoir stock (Digital Twin spec Part C4) ───────────────────────

DEFAULT_EVAPORATION_RATE = 0.05     # fraction of stock lost per step
DEFAULT_AG_WITHDRAWAL_SHARE = 0.70  # fraction of total withdrawal that is agricultural
                                     # (global average is ~70% per FAO AQUASTAT summary
                                     # statistics -- this single global constant is a
                                     # simplification; per-node shares were not sourced)
DEFAULT_WITHDRAWAL_RATE = 0.06      # fraction of REFERENCE stock withdrawn per step at
                                     # "normal" demand intensity (self-consistently scaled,
                                     # not derived from absolute caloric-demand units --
                                     # see class docstring bugfix note)


class WaterStockDriver:
    """
    PHASE C: optional model.step() component tracking W_stock_i(t), a
    genuine reservoir distinct from the existing static W_i Cobb-Douglas
    input (Phase 1's water AVAILABILITY index). W_i remains the initial
    condition and long-run reference; this driver lets it evolve.

    Equation:
        W_stock_i(t+1) = W_stock_i(t) + rainfall_i(t) - withdrawal_i(t)
                          - evaporation_i(t)
        withdrawal_i(t) = AG_WITHDRAWAL_SHARE * WITHDRAWAL_RATE *
                           reference_stock_i * demand_intensity_i(t)
        evaporation_i(t) = EVAPORATION_RATE * W_stock_i(t)

    BUGFIX (found and fixed this session, before this driver was ever
    shipped as "working"): an earlier version computed withdrawal
    directly from `caloric_demand_yr / 1e12` in absolute units, which for
    low-water-index, high-population nodes (Egypt: init_stock=5.89 vs.
    withdrawal=90.95 in the FIRST step) caused instant, unconditional
    depletion to zero regardless of rainfall -- a genuine units-scale
    bug, not a modelling choice. Fixed by computing withdrawal as a
    FRACTION OF THE NODE'S OWN REFERENCE STOCK (self-consistently scaled,
    same pattern SoilQualityDriver already used correctly for its
    intensity proxy) rather than from an unrelated absolute-unit demand
    figure. Caught by test_water_stock_driver_runs_and_bounds_stress
    and test_water_stress_reduces_production, both of which now pass
    against this corrected version.

    The agricultural share of withdrawal is what feeds back into
    production (via a new water_stress multiplier, agent.py, getattr-
    defaulted to 1.0 when this driver isn't attached).

    CALIBRATION STATUS: LOW confidence, same as SoilQualityDriver --
    real per-node withdrawal-by-sector data (FAO AQUASTAT) and rainfall
    time series (CHIRPS, per ContinuousClimateDriver) were not integrated
    together this session; demand_intensity below uses the node's own
    caloric-demand TREND (current relative to its own historical mean),
    not an absolute-unit withdrawal figure, so the driver is only
    directionally suggestive, not quantitatively calibrated.
    """

    def __init__(self, evaporation_rate: float = DEFAULT_EVAPORATION_RATE,
                 ag_withdrawal_share: float = DEFAULT_AG_WITHDRAWAL_SHARE,
                 withdrawal_rate: float = DEFAULT_WITHDRAWAL_RATE,
                 rainfall_source: "cd.ContinuousClimateDriver | None" = None):
        self.evaporation_rate = evaporation_rate
        self.ag_withdrawal_share = ag_withdrawal_share
        self.withdrawal_rate = withdrawal_rate
        self.rainfall_source = rainfall_source  # optional: reuse a ContinuousClimateDriver's data
        self._historical_mean_demand: dict = {}

    def step(self, model):
        for name, agent in model.agent_map.items():
            if not hasattr(agent, "water_stock"):
                # initial condition: reference stock proportional to the
                # existing static W_i (Phase 1 calibration), scaled to an
                # arbitrary but consistent unit system.
                agent.water_stock = max(agent.water, 0.01) * 100.0
                agent._water_stock_reference = agent.water_stock

            demand = agent._caloric_demand_yr
            hist_demand = self._historical_mean_demand.setdefault(name, demand)
            demand_intensity = demand / hist_demand if hist_demand > 0 else 1.0
            self._historical_mean_demand[name] = 0.95 * hist_demand + 0.05 * demand

            rainfall_inflow = 0.0
            if self.rainfall_source is not None:
                clim = self.rainfall_source.climatology.get(name)
                if clim is not None:
                    drought = getattr(agent, "drought_index", 0.0)
                    # self-consistently scaled: a "normal" (drought=0) year's
                    # inflow exactly offsets evaporation + withdrawal at the
                    # reference stock level, so W_stock is stationary absent
                    # any anomaly -- only deviations (drought>0) drain it.
                    normal_inflow = (self.evaporation_rate * agent._water_stock_reference
                                      + self.ag_withdrawal_share * self.withdrawal_rate
                                      * agent._water_stock_reference)
                    rainfall_inflow = normal_inflow * (1.0 - drought)
            else:
                # no rainfall driver attached -- assume long-run-average
                # inflow exactly offsets evaporation+withdrawal at
                # reference stock, so W_stock drifts only in response to
                # demand-intensity deviations from 1.0, not an arbitrary
                # unattributed trend.
                rainfall_inflow = (self.evaporation_rate * agent._water_stock_reference
                                    + self.ag_withdrawal_share * self.withdrawal_rate
                                    * agent._water_stock_reference)

            withdrawal = (self.ag_withdrawal_share * self.withdrawal_rate
                          * agent._water_stock_reference * demand_intensity)
            evaporation = self.evaporation_rate * agent.water_stock

            agent.water_stock = max(0.0, agent.water_stock + rainfall_inflow
                                     - withdrawal - evaporation)
            agent.water_stress = float(np.clip(
                1.0 - (agent.water_stock / max(agent._water_stock_reference, 1e-6)), 0.0, 1.0
            ))
