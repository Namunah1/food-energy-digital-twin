"""
metrics.py
----------
Resilience metrics and Gambhir System Architecture Vulnerability (SAV) indices.

Framework : Gambhir et al. (2025) + Homer-Dixon et al. (2015)
Phase     : 2 — Core metrics (all 6 resilience indicators + 4 SAV indices)

Per EQUATIONS.md §13:
  U(t)   = undernourishment rate
  GFS(t) = population-weighted global food security
  TC(t)  = trade collapse index
  EB(t)  = export ban rate
  PAR(t) = population at risk (absolute count)
  FD(t)  = cumulative famine deaths this step

  SAV_scale(t)   = system throughput vs baseline
  SAV_homog(t)   = HHI of exports (proxy for crop/production concentration)
  SAV_connect(t) = active trade edge fraction
  SAV_power(t)   = HHI of trade flows by node (market concentration)

Records are stored as a list of dicts; call to_dataframe() after simulation.
"""

import numpy as np
import pandas as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model import FoodModel


class MetricsCollector:
    """
    Collects per-step metrics across the full simulation run.
    All metric values are Python floats for JSON/CSV compatibility.
    """

    def __init__(self):
        self._records: list[dict] = []
        self._baseline_trade: float | None = None
        self._baseline_supply: float | None = None

    # =========================================================================
    # Main record call (called by model.step())
    # =========================================================================

    def record(self, model: "FoodModel", trade_volume: float):
        """
        Compute and store all metrics for the current step.

        Parameters
        ----------
        model        : FoodModel instance (post-step state)
        trade_volume : total kcal transferred this step (from model.step())
        """
        agents = list(model.agent_map.values())
        N = len(agents)
        if N == 0:
            return

        # ── Set baselines on first call ───────────────────────────────────────
        if self._baseline_trade is None:
            self._baseline_trade = max(trade_volume, 1.0)
        if self._baseline_supply is None:
            self._baseline_supply = max(
                sum(a.annual_production for a in agents), 1.0
            )

        # ── Core resilience metrics (§13) ─────────────────────────────────────
        U   = self._undernourishment_rate(agents)
        GFS = self._global_food_security(agents)
        TC  = self._trade_collapse(trade_volume)
        EB  = self._export_ban_rate(agents)
        PAR = self._population_at_risk(agents)
        FD  = self._famine_deaths_step(agents)

        # ── SAV indices (Gambhir §13) ──────────────────────────────────────────
        SAV_scale   = self._sav_scale(model, agents)
        SAV_homog   = self._sav_homogeneity(agents)
        SAV_connect = self._sav_connectivity(model)
        SAV_power   = self._sav_power(agents)

        # ── Price ─────────────────────────────────────────────────────────────
        price = model.price_system.price
        price_ratio = model.price_system.price_ratio

        # ── Phase 3/4 stress diagnostics (default 0 until those phases) ───────
        mean_FS_index = float(np.mean([a.FS_index for a in agents]))
        mean_ES_index = float(np.mean([
            getattr(a, "energy_stress_index", 0.0) for a in agents
        ]))
        n_overload_food   = int(sum(getattr(a, "overload_food",   False) for a in agents))
        n_overload_energy = int(sum(getattr(a, "overload_energy", False) for a in agents))

        rec = {
            "step":             model.steps,
            # ── Core resilience ────────────────────────────────────────────
            "U_undernourished": round(U,   4),
            "GFS":              round(GFS, 4),
            "TC_trade_collapse":round(TC,  4),
            "EB_export_ban_rate":round(EB, 4),
            "PAR_millions":     round(PAR / 1e6, 2),
            "famine_deaths_step": round(FD, 0),
            # ── Price ──────────────────────────────────────────────────────
            "price_index":      round(price,       4),
            "price_ratio":      round(price_ratio, 4),
            # ── SAV indices ────────────────────────────────────────────────
            "SAV_scale":        round(SAV_scale,   4),
            "SAV_homogeneity":  round(SAV_homog,   4),
            "SAV_connectivity": round(SAV_connect, 4),
            "SAV_power":        round(SAV_power,   4),
            # ── Phase 3/4 diagnostics ──────────────────────────────────────
            "mean_FS_index":    round(mean_FS_index, 4),
            "mean_ES_index":    round(mean_ES_index, 4),
            "n_overload_food":  n_overload_food,
            "n_overload_energy":n_overload_energy,
            # ── Raw supply/demand ──────────────────────────────────────────
            "total_supply_kcal_yr": float(sum(a.annual_production for a in agents)),
            "total_demand_kcal_yr": float(sum(a.caloric_demand()  for a in agents)),
            "trade_volume_kcal":    float(trade_volume),
        }
        self._records.append(rec)

    # =========================================================================
    # Individual metric computations
    # =========================================================================

    def _undernourishment_rate(self, agents) -> float:
        """U(t) = #{i: σᵢ < 1.0} / N"""
        n_under = sum(1 for a in agents if a.food_security < 1.0)
        return n_under / len(agents)

    def _global_food_security(self, agents) -> float:
        """GFS(t) = Σᵢ σᵢ×Pᵢ / ΣPᵢ  (population-weighted)"""
        total_pop = sum(a.population for a in agents)
        if total_pop <= 0:
            return 0.0
        return sum(a.food_security * a.population for a in agents) / total_pop

    def _trade_collapse(self, trade_volume: float) -> float:
        """TC(t) = 1 − Trade(t) / Trade_baseline  ∈ [0, 1]"""
        return float(np.clip(1.0 - trade_volume / self._baseline_trade, 0.0, 1.0))

    def _export_ban_rate(self, agents) -> float:
        """EB(t) = #{i: export_ban=True} / N"""
        n_ban = sum(1 for a in agents if a.export_ban)
        return n_ban / len(agents)

    def _population_at_risk(self, agents) -> float:
        """
        PAR(t) = Σᵢ Pᵢ × undernourishment_fraction_i
        Uses sigma-based undernourishment fraction rather than binary threshold.
        sigma < 0.80 (crisis): full population at risk
        0.80 ≤ sigma < 1.0 (warning): proportional fraction at risk
        sigma ≥ 1.0: zero population at risk
        This avoids counting food-secure-but-not-surplus nodes as crisis nodes.
        """
        total = 0.0
        for a in agents:
            s = a.food_security
            if s >= 1.0:
                fraction = 0.0
            elif s >= 0.80:
                # warning zone: linear interpolation 0→1 as s goes 1.0→0.80
                fraction = (1.0 - s) / 0.20 * 0.30  # max 30% of pop at risk in warning zone
            else:
                # crisis zone: up to full undernourishment fraction
                fraction = min(1.0, (0.80 - s) / 0.80)
            total += a.population * fraction
        return total

    def _famine_deaths_step(self, agents) -> float:
        """FD(t) = Σᵢ psi_i × max(0, 1−σᵢ) × Pᵢ  (this step estimate)"""
        return sum(
            a.psi_i * max(0.0, 1.0 - a.food_security) * a.population
            for a in agents
        )

    # ── SAV indices ───────────────────────────────────────────────────────────

    def _sav_scale(self, model: "FoodModel", agents) -> float:
        """
        SAV_scale(t) = total_energy_GDP_t / total_energy_GDP_baseline
        Proxy: Σ(K_i × E_fuel_i) at current step vs step 0
        """
        current = sum(a.capital * a.energy_fuel for a in agents)
        baseline = getattr(model, "_sav_scale_baseline", None)
        if baseline is None or baseline <= 0:
            model._sav_scale_baseline = max(current, 1.0)
            return 1.0
        return float(current / model._sav_scale_baseline)

    def _sav_homogeneity(self, agents) -> float:
        """
        SAV_homog(t) = HHI of export volumes (concentration of trade sources)
        HHI = Σ (share_i)²  ∈ [1/N, 1]
        """
        exports = [max(a.exports_this_step, 0.0) for a in agents]
        total = sum(exports)
        if total <= 0:
            return 1.0 / len(agents)
        shares = [e / total for e in exports]
        return float(sum(s ** 2 for s in shares))

    def _sav_connectivity(self, model: "FoodModel") -> float:
        """SAV_connect(t) = active_edges / max_edges"""
        from trade import compute_network_density
        return compute_network_density(model)

    def _sav_power(self, agents) -> float:
        """
        SAV_power(t) = HHI of capital holdings (proxy for market concentration)
        Higher HHI = more concentrated power = more systemic risk
        """
        capitals = [max(a.capital, 0.0) for a in agents]
        total = sum(capitals)
        if total <= 0:
            return 1.0 / len(agents)
        shares = [c / total for c in capitals]
        return float(sum(s ** 2 for s in shares))

    # =========================================================================
    # Per-node snapshot (for visualise.py heatmaps)
    # =========================================================================

    def node_snapshot(self, model: "FoodModel") -> pd.DataFrame:
        """
        Return a DataFrame with per-node state at the current step.
        Called by visualize.py for network maps and heatmaps.
        """
        rows = []
        for name, agent in model.agent_map.items():
            rows.append({
                "node":             name,
                "step":             model.steps,
                "food_security":    agent.food_security,
                "export_ban":       int(agent.export_ban),
                "export_fraction":  agent.export_fraction,
                "population_M":     agent.population / 1e6,
                "undernourished":   int(agent.undernourished),
                "capital_bn":       agent.capital,
                "technology":       agent.technology,
                "energy_fuel":      agent.energy_fuel,
                "energy_stress":    getattr(agent, "energy_stress_index", 0.0),
                "FS_index":         agent.FS_index,
                "CC_index":         agent.CC_index,
                "overload_food":    int(getattr(agent, "overload_food", False)),
            })
        return pd.DataFrame(rows)

    # =========================================================================
    # Output
    # =========================================================================

    def to_dataframe(self) -> pd.DataFrame:
        """Return all recorded metrics as a tidy DataFrame."""
        return pd.DataFrame(self._records)

    def summary(self) -> dict:
        """Quick summary statistics across the full run."""
        df = self.to_dataframe()
        if df.empty:
            return {}
        return {
            "n_steps":              len(df),
            "min_GFS":              float(df["GFS"].min()),
            "max_U":                float(df["U_undernourished"].max()),
            "max_price_ratio":      float(df["price_ratio"].max()),
            # BUG-011 FIX: max_price_index is the FAO-normalised absolute
            # price level (2014-2016=1.0), which is what REAL_FPI_2008/2022
            # in retrodiction.py actually represent. max_price_ratio
            # (peak/initial price) is a DIFFERENT quantity — comparing it
            # directly to REAL_FPI_* conflated "how much did price grow
            # during this run" with "what was the absolute FAO FPI level",
            # producing inflated error percentages whenever price_0 != 1.0
            # (e.g. retrodiction runs starting from non-2022 years).
            "max_price_index":      float(df["price_index"].max()),
            "max_PAR_millions":     float(df["PAR_millions"].max()),
            "max_TC":               float(df["TC_trade_collapse"].max()),
            "max_EB_rate":          float(df["EB_export_ban_rate"].max()),
            "max_SAV_homogeneity":  float(df["SAV_homogeneity"].max()),
            "max_n_overload_food":  int(df["n_overload_food"].max()),
        }

    def save(self, path):
        """Save metrics CSV to disk."""
        self.to_dataframe().to_csv(path, index=False)
        print(f"[MetricsCollector] Saved {len(self._records)} step records → {path}")
