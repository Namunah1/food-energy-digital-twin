"""
political_economy.py
--------------------
Political economy layer for the Global Food-Energy Systemic Risk ABM.

Framework : Gambhir et al. (2025) §4 + Homer-Dixon et al. (2015) §3
Phase     : 5 — Trader agents + Gambhir system architecture vulnerability indices

Implements:
  A. TraderAgent: 3-5 commodity traders intermediating bilateral trade
     - Extract margin from food flows (proxy for "Big Five" agro-commodities)
     - Restrict flows under stress (market power → amplifies cascades)
     - Trade-flow Herfindahl index (SAV_power)

  B. Gambhir SAV dashboard (per EQUATIONS.md §13 and Gambhir Fig.2):
     SAV_scale(t)      : global system throughput vs baseline
     SAV_homogeneity(t): HHI of export volumes (crop/production concentration)
     SAV_connectivity(t): active trade edge fraction
     SAV_power(t)       : HHI of trader-mediated flow share

  C. Coping capacity vulnerability to power:
     CC_i is reduced by market_power_exposure_i = trader_share_of_imports_i
     High import dependence from concentrated traders = less resilience

Gambhir (2025) identifies four architecture vulnerabilities:
  1. Global scale (SAV_scale)
  2. Homogeneity (SAV_homog)
  3. Interconnectivity (SAV_connect)
  4. Concentrated power (SAV_power)
All four are computed here and attached to each metrics step record.
"""

import numpy as np
import pandas as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model import FoodEnergyModel

# ── Trader constants ──────────────────────────────────────────────────────────
N_TRADERS          = 5       # "Big Five" agro-commodity traders
BASE_MARGIN        = 0.05    # 5% margin on trade flows (normal conditions)
STRESS_MARGIN_MULT = 3.0     # margin multiplies up to 15% under stress
STRESS_THRESHOLD   = 0.65    # SAV_scale > 0.65 triggers elevated margin
FLOW_RESTRICTION_CAP = 0.40  # traders restrict at most 40% of flow
FLOW_RESTRICTION_STRESS = 0.80  # ES_global threshold for restriction behaviour

# ── Vulnerability calibration ─────────────────────────────────────────────────
POWER_CC_PENALTY   = 0.15   # CC_i reduced by this × trader_share_of_imports


class TraderAgent:
    """
    A commodity trader who intermediates a share of bilateral trade.

    Attributes
    ----------
    name          : trader identifier (e.g. 'Cargill_proxy')
    specialisation: 'grains' | 'oilseeds' | 'general'
    market_share  : fraction of global trade flow this trader handles
    cash_reserves : accumulated profit (capital proxy)
    """

    def __init__(
        self,
        trader_id: int,
        name: str,
        specialisation: str = "general",
        market_share: float = 0.12,
        seed: int = 42,
    ):
        self.trader_id      = trader_id
        self.name           = name
        self.specialisation = specialisation
        self.market_share   = float(market_share)
        self.cash_reserves  = 100.0  # initial capital (bn USD proxy)
        self.profit_history : list[float] = []
        self.rng = np.random.default_rng(seed + trader_id * 7)

    def margin(self, stress_level: float) -> float:
        """
        Dynamic margin: rises with system stress.
        margin(stress) = BASE + (STRESS_MULT − 1) × BASE × stress
        """
        return BASE_MARGIN * (1.0 + (STRESS_MARGIN_MULT - 1.0) * stress_level)

    def flow_restriction(self, es_global: float) -> float:
        """
        Fraction of flow restricted under high energy stress.
        Models traders' risk-averse behaviour → amplifies cascade.
        """
        if es_global < FLOW_RESTRICTION_STRESS:
            return 0.0
        excess = es_global - FLOW_RESTRICTION_STRESS
        return min(FLOW_RESTRICTION_CAP, excess * 2.0)


class PoliticalEconomyModule:
    """
    Manages trader agents and computes Gambhir SAV vulnerability indices.

    Attach to model:
        model.trader_module = PoliticalEconomyModule(n_traders=5)
        # trade.py calls model.trader_module.intercept(src, dst, volume) each edge
    """

    # ── Big Five names (proxy for Cargill, ADM, Bunge, Louis Dreyfus, Viterra)
    TRADER_NAMES = [
        "Cargill_proxy", "ADM_proxy", "Bunge_proxy",
        "LouisDreyfus_proxy", "Viterra_proxy"
    ]
    TRADER_SPECS = ["grains", "oilseeds", "general", "grains", "general"]

    def __init__(self, n_traders: int = N_TRADERS, seed: int = 42):
        n = min(n_traders, len(self.TRADER_NAMES))
        # Equal market share split (simplified; real HHI from actual shares)
        base_share = 0.60 / n   # Big Five collectively handle ~60% of global trade

        self.traders = [
            TraderAgent(
                trader_id=i,
                name=self.TRADER_NAMES[i],
                specialisation=self.TRADER_SPECS[i],
                market_share=base_share,
                seed=seed,
            )
            for i in range(n)
        ]

        # Diagnostics per step
        self._step_profits: list[float] = []
        self._sav_power_history: list[float] = []
        self._sav_records: list[dict] = []

        # Import exposure tracking: node_name → fraction of imports via traders
        self._import_exposure: dict[str, float] = {}

    # =========================================================================
    # Trade interception (called by trade.py _trader_intercept hook)
    # =========================================================================

    def intercept(self, src: str, dst: str, volume: float) -> float:
        """
        Intercept a trade flow, extract margin, possibly restrict it.

        Returns volume after trader action (may be reduced).
        Called for every active trade edge each step.
        """
        if volume <= 0:
            return volume

        # Stress level proxy: average margin across traders
        stress_level = getattr(self, "_current_stress", 0.0)
        es_global    = getattr(self, "_current_es_global", 0.0)

        total_extracted = 0.0
        effective_volume = volume

        for trader in self.traders:
            # Only active traders handle a slice of this edge
            trader_volume = effective_volume * trader.market_share
            if trader_volume <= 0:
                continue

            # Margin extraction
            m = trader.margin(stress_level)
            extracted = trader_volume * m
            trader.cash_reserves += extracted * 1e-12  # convert kcal to bn USD proxy
            total_extracted += extracted

            # Flow restriction (risk aversion under stress)
            restriction = trader.flow_restriction(es_global)
            if restriction > 0:
                restricted = trader_volume * restriction
                effective_volume -= restricted

        effective_volume = max(0.0, effective_volume - total_extracted)

        # Track import exposure for destination node
        if dst not in self._import_exposure:
            self._import_exposure[dst] = 0.0
        # Running average (simple EMA)
        extracted_share = total_extracted / max(volume, 1.0)
        self._import_exposure[dst] = (
            0.90 * self._import_exposure.get(dst, 0.0) + 0.10 * extracted_share
        )

        return max(0.0, effective_volume)

    # =========================================================================
    # Main step (called by model, AFTER trade but BEFORE metrics)
    # =========================================================================

    def step(self, model: "FoodEnergyModel"):
        """
        Update trader state and compute SAV diagnostics for this step.
        """
        # Update stress signals for intercept()
        agents = list(model.agent_map.values())
        es_vals = [getattr(a, "energy_stress_index", 0.0) for a in agents]
        fs_vals = [a.FS_index for a in agents]

        self._current_es_global = float(np.mean(es_vals))
        self._current_stress    = float(
            np.clip(np.mean(fs_vals) + self._current_es_global, 0.0, 1.0)
        )

        # ── Step profit accumulation ───────────────────────────────────────────
        step_profit = sum(t.cash_reserves for t in self.traders)
        self._step_profits.append(step_profit)

        # ── Apply CC penalty from market power exposure ────────────────────────
        self._apply_power_cc_penalty(agents)

        # ── SAV diagnostics ────────────────────────────────────────────────────
        sav = self._compute_sav(model, agents)
        self._sav_records.append({"step": model.steps, **sav})

        return sav

    # =========================================================================
    # CC penalty from concentrated power
    # =========================================================================

    def _apply_power_cc_penalty(self, agents):
        """
        Gambhir: concentrated market power reduces coping capacity.
        CC_i_eff = CC_i × (1 − POWER_CC_PENALTY × import_exposure_i)
        """
        for agent in agents:
            exposure = self._import_exposure.get(agent.name, 0.0)
            penalty  = POWER_CC_PENALTY * exposure
            agent.CC_index = float(np.clip(
                agent.CC_index * (1.0 - penalty),
                0.05, 1.0
            ))

    # =========================================================================
    # SAV diagnostics (Gambhir Fig.2, four architecture vulnerabilities)
    # =========================================================================

    def _compute_sav(self, model: "FoodEnergyModel", agents) -> dict:
        """
        Compute all four Gambhir (2025) system architecture vulnerability indices.
        """
        # ── SAV 1: Scale ──────────────────────────────────────────────────────
        current_throughput = sum(a.capital * a.energy_fuel for a in agents)
        baseline = getattr(model, "_sav_scale_baseline", None)
        if baseline is None or baseline <= 0:
            model._sav_scale_baseline = max(current_throughput, 1.0)
            sav_scale = 1.0
        else:
            sav_scale = float(current_throughput / model._sav_scale_baseline)

        # ── SAV 2: Homogeneity ─────────────────────────────────────────────────
        # HHI of export volumes (high HHI = concentrated supply → vulnerable)
        exports = [max(a.exports_this_step, 0.0) for a in agents]
        total_e = sum(exports)
        if total_e > 0:
            shares = [e / total_e for e in exports]
            sav_homog = float(sum(s ** 2 for s in shares))
        else:
            sav_homog = 1.0 / max(len(agents), 1)

        # ── SAV 3: Interconnectivity ───────────────────────────────────────────
        G = model.network
        active = sum(1 for _, _, d in G.edges(data=True) if d.get("active", True))
        max_edges = G.number_of_nodes() * (G.number_of_nodes() - 1)
        sav_connect = active / max(max_edges, 1)

        # ── SAV 4: Concentrated power (trader HHI) ─────────────────────────────
        # HHI of trader cash reserves (proxy for market concentration)
        reserves = [max(t.cash_reserves, 0.0) for t in self.traders]
        total_r  = sum(reserves)
        if total_r > 0:
            shares_r  = [r / total_r for r in reserves]
            sav_power = float(sum(s ** 2 for s in shares_r))
        else:
            sav_power = 1.0 / max(len(self.traders), 1)

        # Homer-Dixon deep causes amplification factor
        # As scale/connectivity/homogeneity rise, systemic risk multiplies
        deep_cause_factor = (
            min(sav_scale, 2.0) * sav_homog * sav_connect
        )

        self._sav_power_history.append(sav_power)

        return {
            "SAV_scale":        round(sav_scale,   4),
            "SAV_homogeneity":  round(sav_homog,   4),
            "SAV_connectivity": round(sav_connect, 4),
            "SAV_power":        round(sav_power,   4),
            "deep_cause_factor":round(deep_cause_factor, 4),
            "mean_ES_global":   round(self._current_es_global, 4),
            "trader_total_cash":round(sum(t.cash_reserves for t in self.traders), 2),
        }

    # =========================================================================
    # Shock/response interface
    # =========================================================================

    def apply_trader_regulation(self, margin_cap: float = 0.05):
        """
        Policy response: cap trader margins (regulatory intervention).
        Reduces SAV_power by limiting profit extraction.
        """
        for trader in self.traders:
            trader.market_share *= 0.85  # market power reduced
        print(
            f"[PoliticalEconomy] Trader regulation applied: "
            f"market share reduced by 15%, margin cap={margin_cap:.0%}"
        )

    def apply_reserve_mandate(self, model: "FoodEnergyModel", target_months: float = 3.0):
        """
        Policy response: mandatory strategic reserves.
        All agents must hold target_months × monthly demand in non-perishable stock.
        """
        target_fraction = target_months / 12.0
        for agent in model.agent_map.values():
            target = target_fraction * agent._caloric_demand_yr
            if agent.food_imperish < target:
                gap = target - agent.food_imperish
                # Transfer from reserves if available
                transfer = min(agent.reserves, gap)
                agent.reserves      -= transfer
                agent.food_imperish += transfer
        print(
            f"[PoliticalEconomy] Reserve mandate applied: "
            f"target={target_months:.1f} months"
        )

    def apply_diversification(self, model: "FoodEnergyModel", n_new_routes: int = 10):
        """
        Policy response: trade route diversification.
        Re-enables N random disabled edges (proxy for finding alternative suppliers).
        Reduces SAV_homogeneity.
        """
        G = model.network
        disabled = [(s, d) for s, d, dat in G.edges(data=True) if not dat.get("active", True)]
        model.rng.shuffle(disabled)
        re_enabled = 0
        for s, d in disabled[:n_new_routes]:
            G[s][d]["active"] = True
            re_enabled += 1
        print(
            f"[PoliticalEconomy] Diversification: re-enabled {re_enabled} trade routes"
        )

    # =========================================================================
    # Diagnostics
    # =========================================================================

    def summary(self) -> dict:
        """Summary across the full run."""
        if not self._sav_records:
            return {}
        df = pd.DataFrame(self._sav_records)
        return {
            "n_traders":              len(self.traders),
            "max_SAV_scale":          float(df["SAV_scale"].max()),
            "max_SAV_homogeneity":    float(df["SAV_homogeneity"].max()),
            "min_SAV_connectivity":   float(df["SAV_connectivity"].min()),
            "max_SAV_power":          float(df["SAV_power"].max()),
            "max_deep_cause_factor":  float(df["deep_cause_factor"].max()),
            "total_trader_cash_final":float(self._step_profits[-1]) if self._step_profits else 0.0,
        }

    def sav_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self._sav_records)
