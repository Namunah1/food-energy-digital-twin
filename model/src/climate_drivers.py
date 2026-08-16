"""
climate_drivers.py — PHASE C (this session)
=============================================
Continuous rainfall/temperature-anomaly driver processes, per Digital
Twin Architecture spec Part C1, and soil-quality state, per Part C2.

DATA STATUS — read before using this module for any published claim:
No real rainfall or temperature time series exists anywhere in this
repository. Confirmed this session:
    find data/raw -iname "*rain*" -o -iname "*precip*" -o -iname "*temp*"
returns nothing. `PHASE4_IMPLEMENTATION_AUDIT.md` and the Digital Twin
spec's Section 12 both flag CHIRPS (rainfall) and Berkeley Earth/NOAA
GHCN (temperature) as the proposed real sources — neither has been
acquired or integrated. This module implements the MECHANISM (equations
+ per-node/per-tick application) and is tested against a clearly-labelled
SYNTHETIC placeholder series. Real ingestion is future work: build a
data_pipeline.py extension that produces per-node rainfall/temperature
CSVs in the same shape node_panel.csv already uses, then replace
`generate_synthetic_climatology()` below with a real-data loader. Do not
present ContinuousClimateDriver's default output as calibrated.

TRIPLE-COUNTING: this module sets agent.drought_index / agent.heatwave_index
exactly as a discrete trigger already does (agent.py's existing attributes,
unchanged schema) — it does NOT introduce a new counting pathway. The
triple-counting finding from PHASE2_5B_CAUSAL_DECOMPOSITION.md (§7/§9) is
resolved separately and independently via model.climate_single_channel_mode
(see model.py, stc_engine.py, energy.py) — per the Digital Twin spec's own
instruction ("resolve the triple-counting issue as part of the same
change, not after"), any caller wiring up ContinuousClimateDriver for real
use SHOULD also set climate_single_channel_mode=True, and
test_phase_c_climate_drivers.py verifies this combination explicitly.
"""
import numpy as np


# ── Equations (Digital Twin spec Part C1) ──────────────────────────────────

def compute_drought_index(rainfall_climatology: float, rainfall_current: float) -> float:
    """
    drought_index = clip((rainfall_climatology - rainfall_current) /
                          rainfall_climatology, 0, 1)
    """
    if rainfall_climatology <= 0:
        return 0.0
    return float(np.clip(
        (rainfall_climatology - rainfall_current) / rainfall_climatology, 0.0, 1.0
    ))


def compute_heat_stress(temp_anomaly: float, heat_threshold: float = 1.0,
                         heat_range: float = 3.0) -> float:
    """
    heat_stress = clip((temp_anomaly - heat_threshold) / heat_range, 0, 1)

    heat_threshold: temperature anomaly (°C above baseline) below which no
        stress is registered. Default 1.0°C is a placeholder, not a
        calibrated agronomic threshold — flagged as LOW confidence per the
        Digital Twin spec's own tiering (Section 12), same status as every
        other unsourced constant in this module.
    """
    return float(np.clip((temp_anomaly - heat_threshold) / heat_range, 0.0, 1.0))


# ── Synthetic placeholder data generator (NOT real climatology) ────────────

def generate_synthetic_climatology(node_names: list, seed: int = 7) -> dict:
    """
    Produces a per-node baseline rainfall climatology and a simple
    autoregressive anomaly generator, FOR TESTING ONLY. Explicitly not
    real CHIRPS data — see module docstring. Structure mirrors what a real
    data loader would need to return, so swapping in real data later is a
    drop-in replacement of this function's output shape, not a redesign.
    """
    rng = np.random.default_rng(seed)
    climatology = {}
    for name in node_names:
        climatology[name] = {
            "rainfall_climatology_mm": float(rng.uniform(400, 1400)),
            "temp_anomaly_baseline_c": float(rng.uniform(-0.3, 0.3)),
        }
    return climatology


class ContinuousClimateDriver:
    """
    PHASE C: pluggable, optional model.step() component (see model.py's
    `self.climate_driver` slot, None by default). When attached, replaces
    the trigger-only discrete drought_index/heatwave_index with a
    continuous, per-tick-updated value derived from a rainfall/temperature
    series.

    Parameters
    ----------
    climatology : dict[node_name -> {"rainfall_climatology_mm": float,
                  "temp_anomaly_baseline_c": float}]
        Per-node long-run baseline. Use generate_synthetic_climatology()
        for testing; a real loader should return the same shape.
    rainfall_series, temp_anomaly_series : dict[node_name -> list[float]],
        optional. Per-tick current-year values, indexed by step. If a
        node/step combination is missing, falls back to the climatology
        baseline (zero anomaly) rather than raising — a driver with
        incomplete data should degrade to "no signal," not crash a run.
    sensitivity_multiplier_source : "flat" | "epsilon_ef"
        "flat": every node's drought/heat signal maps 1:1 to drought_index/
            heatwave_index (matches the discrete-trigger mechanism's
            existing behaviour).
        "epsilon_ef": scales each node's SENSITIVITY to its own rainfall/
            temperature anomaly by its irrigation dependence proxy. No
            real irrigation-share dataset is present (FAO AQUASTAT,
            flagged in the Digital Twin spec Part C1, is not yet
            integrated) -- as an honestly-labelled interim proxy, this
            uses the existing per-node `W_i` (water availability index,
            Phase 1 calibration) inverted (low W_i = more irrigation-
            dependent = more rainfall-sensitive is the DIRECTION asserted,
            not empirically validated this session).
    """

    def __init__(self, climatology: dict,
                 rainfall_series: dict | None = None,
                 temp_anomaly_series: dict | None = None,
                 sensitivity_multiplier_source: str = "flat"):
        self.climatology = climatology
        self.rainfall_series = rainfall_series or {}
        self.temp_anomaly_series = temp_anomaly_series or {}
        self.sensitivity_multiplier_source = sensitivity_multiplier_source
        assert sensitivity_multiplier_source in ("flat", "epsilon_ef")

    def _sensitivity(self, agent) -> float:
        if self.sensitivity_multiplier_source == "flat":
            return 1.0
        # "epsilon_ef" mode: interim proxy, see class docstring
        # BUGFIX (Phase C increment 2, this session): reads `agent.water`
        # (the real attribute name, agent.py:145) -- an earlier version of
        # this method incorrectly read a nonexistent `water_availability`
        # attribute, which meant this mode silently always returned the
        # 1.0 no-op default. Not caught by increment 1's tests because
        # they only exercised the default "flat" mode. No existing
        # scenario used "epsilon_ef" mode (it's opt-in, never the
        # default), so this fix changes zero currently-running behaviour.
        w = getattr(agent, "water", None)
        if w is None:
            return 1.0
        return float(np.clip(1.5 - w, 0.3, 1.5))

    def step(self, model):
        t = model.steps
        for name, agent in model.agent_map.items():
            clim = self.climatology.get(name)
            if clim is None:
                continue  # no data for this node -- leave drought/heatwave untouched
            sens = self._sensitivity(agent)

            rainfall_now = self.rainfall_series.get(name, [None])[min(t, len(self.rainfall_series.get(name, [None])) - 1)] \
                if name in self.rainfall_series and len(self.rainfall_series[name]) > 0 else None
            if rainfall_now is not None:
                d = compute_drought_index(clim["rainfall_climatology_mm"], rainfall_now)
                agent.drought_index = float(np.clip(d * sens, 0.0, 1.0))

            temp_now = self.temp_anomaly_series.get(name, [None])[min(t, len(self.temp_anomaly_series.get(name, [None])) - 1)] \
                if name in self.temp_anomaly_series and len(self.temp_anomaly_series[name]) > 0 else None
            if temp_now is not None:
                h = compute_heat_stress(temp_now)
                agent.heatwave_index = float(np.clip(h * sens, 0.0, 1.0))


# ── Soil quality (Digital Twin spec Part C2) ────────────────────────────────

SOIL_REGEN_RATE = 0.02        # per step, fraction of gap to Q=1.0 closed by natural regeneration
SOIL_DEGRADATION_RATE = 0.03  # per step, per unit of "intensity" above 1.0


class SoilQualityDriver:
    """
    PHASE C: optional model.step() component tracking Q_soil_i(t), per
    Digital Twin spec Part C2. Like ContinuousClimateDriver, attached via
    an optional model slot (model.soil_driver, None by default -- add
    analogous to climate_driver if/when wired into model.py's step()).

    CALIBRATION STATUS: LOW confidence (Digital Twin spec Section 12) --
    no real degradation-rate time series was sourced this session (FAO
    Global Soil Organic Carbon map / ISRIC SoilGrids, per the spec, are
    real candidate sources but were not acquired). SOIL_REGEN_RATE and
    SOIL_DEGRADATION_RATE above are illustrative placeholders, not
    calibrated constants -- flagged explicitly here and in every place
    Q_soil is consumed, consistent with the "do not force an ML fit
    without an independent validation target" principle from the
    Scientific Design Specification §13.

    Equation:
        Q_soil,i(t+1) = Q_soil,i(t) + SOIL_REGEN_RATE*(1 - Q_soil,i(t))
                        - SOIL_DEGRADATION_RATE * max(0, intensity_i(t) - 1)
        intensity_i(t) = current production / node's own historical mean
                          production (a land-use-intensity proxy, not a
                          direct measurement)
    """

    def __init__(self):
        self._historical_mean_production: dict = {}

    def step(self, model):
        for name, agent in model.agent_map.items():
            if not hasattr(agent, "soil_quality"):
                agent.soil_quality = 1.0  # initial condition: undegraded

            prod = getattr(agent, "annual_production", None)
            if prod is None or prod <= 0:
                continue

            hist = self._historical_mean_production.setdefault(name, prod)
            intensity = prod / hist if hist > 0 else 1.0
            # update running mean (simple exponential smoothing)
            self._historical_mean_production[name] = 0.95 * hist + 0.05 * prod

            q = agent.soil_quality
            q_new = q + SOIL_REGEN_RATE * (1.0 - q) - SOIL_DEGRADATION_RATE * max(0.0, intensity - 1.0)
            agent.soil_quality = float(np.clip(q_new, 0.05, 1.0))
