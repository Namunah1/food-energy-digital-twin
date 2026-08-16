"""
energy.py
---------
Energy subsystem for the Global Food-Energy Systemic Risk ABM.

Framework : Gambhir et al. (2025) Fig.1/2 + Homer-Dixon et al. (2015) Fig.3
Phase     : 3 — Energy system + bidirectional coupling

Per-node energy state:
  ES_index_i(t) = energy stress index  [0, 1]
  p_energy_i(t) = energy price index   (baseline = 1.0)

Two coupling arrows (EQUATIONS.md §3):
  Arrow 1  Energy → Food (cost-push, §3a):
    high ES_i raises fertiliser/machinery costs → reduces A_i by elasticity ε_EF
    and feeds into global price update (prices.py already has 0.45×ES_global hook)

  Arrow 2  Food → Energy (biofuel land competition, §3b):
    when p_energy > θ_biofuel threshold AND σ_i > σ_safe_i,
    agent reallocates ξ_i fraction of cropland to biofuel feedstock
    → reduces L_food (done in agent._produce_plant_food via xi_biofuel)
    → reduces ES_index by biofuel contribution fraction

Per EQUATIONS.md §14:
  ES_i(t) = clip(
      (demand_growth_i / production_capacity_i)
      + EROI_penalty_i
      + import_risk_i
      - renewable_offset_i
    , 0, 1)

Deep causes tracked (Homer-Dixon §3):
  - EROI proxy: declining with step (0.3% per year, consistent with IEA trends)
  - Fossil dependence: fraction of energy_fuel / (energy_fuel + energy_renew + energy_elec)
  - Import risk: political_risk × (1 - self_sufficiency)
"""

import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model import FoodEnergyModel

# ── Energy stress accumulation constants ──────────────────────────────────────
DEMAND_GROWTH_RATE  = 0.018   # 1.8%/yr global demand growth (IEA)
EROI_DECLINE_RATE   = 0.003   # 0.3%/yr EROI decline (IEA conventional oil)
RENEW_OFFSET_MAX    = 0.30    # max renewable offset to ES_index
FOSSIL_SHARE_WEIGHT = 0.40    # weight of fossil dependence in ES
IMPORT_RISK_WEIGHT  = 0.25    # weight of import risk in ES

# ── Energy price dynamics ─────────────────────────────────────────────────────
ENERGY_PRICE_SENSITIVITY = 2.0   # price elasticity to ES_index
ENERGY_REVERSION_RATE    = 0.10  # mean reversion to baseline (1.0)
ENERGY_PRICE_FLOOR       = 0.20
ENERGY_PRICE_CEILING     = 6.00

# ── Coupling: Energy → Food ───────────────────────────────────────────────────
# A_i is reduced by ε_EF × ES_index (cost-push reduces TFP)
# Value: 0.40 means 100% energy stress → 40% TFP reduction
EPSILON_EF = 0.40

# ── Coupling: Food → Energy (biofuel, §3b) ────────────────────────────────────
BIOFUEL_PRICE_THRESHOLD = 1.40  # p_energy > 1.40 activates biofuel reallocation
BIOFUEL_MAX_LAND_SHARE  = 0.15  # max 15% of cropland → biofuel
BIOFUEL_ENERGY_OFFSET   = 0.08  # biofuel contribution to ES reduction per 10% land share
BIOFUEL_FOOD_PENALTY    = 0.12  # food supply reduction per unit biofuel land share

# ── Stage 1 LFBB threshold (EQUATIONS.md §14) ─────────────────────────────────
ES_OVERLOAD_THRESHOLD = 0.70   # ES_index > 0.70 → energy system overloaded (LFBB)


class EnergyModule:
    """
    Manages per-node energy stress and bidirectional food-energy coupling.

    Called by model.step() before agent steps (because energy stress modifies
    agent production inputs for the current tick).

    Usage (in model.py):
        self.energy_module = EnergyModule()
        # In step():
        #   if self.energy_module: self.energy_module.step(self)
    """

    def __init__(self, seed: int = 42):
        self.rng   = np.random.default_rng(seed)
        self._step = 0

        # Global EROI penalty (shared accumulator — declines each step)
        self._eroi_penalty_global = 0.0

        # Node-level energy price index (name → price)
        self._energy_price: dict[str, float] = {}

    # =========================================================================
    # Main step (called before agents each tick)
    # =========================================================================

    def step(self, model: "FoodEnergyModel"):
        """
        For each agent:
          1. Compute ES_index from demand growth, EROI penalty, import risk,
             renewable offset
          2. Update energy price
          3. Apply Energy→Food cost-push (modify A_i)
          4. Apply Food→Energy biofuel coupling (modify xi_biofuel, ES_index)
          5. Set overload flag (LFBB hook for Phase 4)
        """
        self._step += 1

        # EROI declines globally each step
        self._eroi_penalty_global = min(
            0.50,
            self._eroi_penalty_global + EROI_DECLINE_RATE
        )

        agents = list(model.agent_map.values())

        for agent in agents:
            # ── 1. Compute ES_index ───────────────────────────────────────────
            es = self._compute_es_index(
                agent, single_channel_mode=getattr(model, "climate_single_channel_mode", False))
            agent.energy_stress_index = es

            # ── 2. Energy price ───────────────────────────────────────────────
            p_e = self._update_energy_price(agent.name, es)

            # ── 3. Arrow 1: Energy → Food cost-push ───────────────────────────
            self._apply_energy_to_food(agent, es)

            # ── 4. Arrow 2: Food → Energy biofuel coupling ────────────────────
            self._apply_food_to_energy(agent, es, p_e)

            # ── 5. LFBB overload flag ─────────────────────────────────────────
            agent.overload_energy = (es >= ES_OVERLOAD_THRESHOLD)

    # =========================================================================
    # ES_index computation (§14)
    # =========================================================================

    def _compute_es_index(self, agent, single_channel_mode: bool = False) -> float:
        """
        ES_i(t) = clip(
            demand_growth_component
            + eroi_penalty
            + import_risk_component
            - renewable_offset
        , 0, 1)

        Proxy components (real EROI data unavailable at country level):
          demand_growth  = step × DEMAND_GROWTH_RATE × fossil_share
          eroi_penalty   = global EROI decline × fossil_share
          import_risk    = political_risk × (1 - self_sufficiency_energy)
          renew_offset   = E_renew / (E_fuel + E_elec + E_renew + 1) × RENEW_OFFSET_MAX
        """
        E_fuel  = max(agent.energy_fuel,  0.01)
        E_elec  = max(agent.energy_elec,  0.01)
        E_renew = max(agent.energy_renew, 0.01)
        E_total = E_fuel + E_elec + E_renew

        fossil_share = E_fuel / E_total

        # Demand growth component (accumulates over steps)
        demand_growth = (self._step * DEMAND_GROWTH_RATE * fossil_share
                         * FOSSIL_SHARE_WEIGHT)

        # EROI penalty (global, weighted by local fossil dependence)
        eroi_component = self._eroi_penalty_global * fossil_share

        # Import risk (political risk × energy import dependence proxy)
        # Self-sufficiency proxy: higher E_fuel relative to population = more self-sufficient
        energy_per_cap = E_total / max(agent.population, 1.0)
        ref_energy_per_cap = 70.0 / 1e8  # reference: 70 TWh per 100M people
        self_suff_energy = min(1.0, energy_per_cap / max(ref_energy_per_cap, 1e-15))
        import_risk = IMPORT_RISK_WEIGHT * agent.political_risk * (1.0 - self_suff_energy)

        # Renewable offset
        renew_share  = E_renew / E_total
        renew_offset = renew_share * RENEW_OFFSET_MAX

        # Climate vulnerability adds to energy stress (extreme weather disrupts supply).
        # PHASE C (this session): when single_channel_mode is True, this term
        # is scaled by the node's OWN energy-food coupling strength (ε_ef,
        # Phase 1's per-country calibration, 0.18-0.52) instead of a flat
        # 0.10 for every node regardless of its actual hydro/irrigation
        # energy dependence -- a node with weak energy-food coupling
        # plausibly has weak climate-to-energy transmission too, and a flat
        # constant asserted no such distinction. Default (False) preserves
        # the original flat-0.10 formula exactly.
        if single_channel_mode:
            climate_stress = 0.10 * getattr(agent, "epsilon_ef", 0.35) * (1.0 - agent.climate_modifier)
        else:
            climate_stress = 0.10 * (1.0 - agent.climate_modifier)

        es = demand_growth + eroi_component + import_risk + climate_stress - renew_offset
        return float(np.clip(es, 0.0, 1.0))

    # =========================================================================
    # Energy price
    # =========================================================================

    def _update_energy_price(self, node_name: str, es: float) -> float:
        """
        p_energy(t+1) = p_energy(t) × exp(κ_e × ES)
                       + θ_rev × (1.0 − p_energy(t))
        Clamped to [0.20, 6.00].
        """
        p_prev = self._energy_price.get(node_name, 1.0)

        # Exponential response to energy stress
        p_new = p_prev * np.exp(ENERGY_PRICE_SENSITIVITY * (es - 0.30))
        # Mean reversion to 1.0
        p_new += ENERGY_REVERSION_RATE * (1.0 - p_new)
        p_new  = float(np.clip(p_new, ENERGY_PRICE_FLOOR, ENERGY_PRICE_CEILING))

        self._energy_price[node_name] = p_new
        return p_new

    def energy_price(self, node_name: str) -> float:
        """Public accessor for per-node energy price."""
        return self._energy_price.get(node_name, 1.0)

    # =========================================================================
    # Arrow 1: Energy → Food (cost-push)
    # =========================================================================

    def _apply_energy_to_food(self, agent, es: float):
        """
        Gambhir Fig.1/2: direct energy cost into agriculture and
        indirect cost through fertiliser = 40-50% of variable cropping costs.

        Implementation: temporarily reduce effective A_i for this step.
        A_i_eff = A_i × (1 − ε_EF × ES_i)

        We modify A_i in-place each step and restore from baseline each step,
        so it acts as a flow modifier not a permanent state change.
        """
        # Restore from last step's modification
        if not hasattr(agent, '_A_i_base'):
            agent._A_i_base = agent.A_i

        # Per-country EPSILON_EF from node_parameters.epsilon_ef (IEA/FAO calibrated).
        # Falls back to global EPSILON_EF constant if not set on agent (e.g. old pickles).
        # See data/processed/node_parameters.csv and docs/BUGS_FIXED.md (BUG-028 addendum,
        # IEA agricultural energy expenditure calibration).
        eps_ef = getattr(agent, 'epsilon_ef', EPSILON_EF)

        # Apply ES cost-push
        cost_push_factor = 1.0 - eps_ef * es
        agent.A_i = agent._A_i_base * max(cost_push_factor, 0.20)

    # =========================================================================
    # Arrow 2: Food → Energy (biofuel land competition, Homer-Dixon Fig.3)
    # =========================================================================

    def _apply_food_to_energy(self, agent, es: float, p_energy: float):
        """
        When energy price is high AND the agent has food security surplus,
        cropland is reallocated to biofuel production.

        xi_biofuel(t) = biofuel land share [0, BIOFUEL_MAX_LAND_SHARE]
          Increases when: p_energy > threshold AND σ_i > sigma_safe_i
          Decreases when: p_energy < threshold OR σ_i < sigma_safe_i

        Effects:
          - Reduces L_food in agent (agent.xi_biofuel used in _produce_plant_food)
          - Reduces ES_index (biofuel displaces fossil fuel demand partially)
        """
        sigma = agent.food_security

        if p_energy > BIOFUEL_PRICE_THRESHOLD and sigma > agent.sigma_safe_i:
            # Incentive to produce biofuel: ramp up xi_biofuel
            target_xi = min(
                BIOFUEL_MAX_LAND_SHARE,
                (p_energy - BIOFUEL_PRICE_THRESHOLD) * 0.10,
            )
            agent.xi_biofuel = min(agent.xi_biofuel + 0.02, target_xi)
        else:
            # Revert biofuel allocation
            agent.xi_biofuel = max(0.0, agent.xi_biofuel - 0.01)

        # ES reduction from biofuel contribution
        biofuel_es_offset = agent.xi_biofuel * (BIOFUEL_ENERGY_OFFSET / 0.10)
        agent.energy_stress_index = float(
            np.clip(agent.energy_stress_index - biofuel_es_offset, 0.0, 1.0)
        )

    # =========================================================================
    # Shock interface (called by STC engine or scenarios.py)
    # =========================================================================

    def apply_energy_shock(
        self,
        model: "FoodEnergyModel",
        scope: float = 0.30,
        severity: float = 0.40,
        mode: str = "supply_cut",
    ):
        """
        Inject an energy stress shock.

        mode options:
          'supply_cut'  : reduce E_fuel for affected nodes (e.g. Russia gas cut)
          'price_spike' : directly spike energy price (speculation / sanctions)
          'eroi_jump'   : accelerate EROI decline (resource scarcity)
        """
        agents = list(model.agent_map.values())
        n_affected = max(1, int(scope * len(agents)))
        indices = model.rng.choice(len(agents), size=n_affected, replace=False)
        affected = [agents[i] for i in indices]

        for agent in affected:
            if mode == "supply_cut":
                agent.energy_fuel = max(
                    1.0, agent.energy_fuel * (1.0 - severity)
                )
            elif mode == "price_spike":
                name = agent.name
                p_cur = self._energy_price.get(name, 1.0)
                self._energy_price[name] = min(
                    ENERGY_PRICE_CEILING, p_cur * (1.0 + severity)
                )
            elif mode == "eroi_jump":
                self._eroi_penalty_global = min(
                    0.80, self._eroi_penalty_global + severity * 0.50
                )

        print(
            f"[EnergyModule] Shock '{mode}' severity={severity:.2f} "
            f"on {len(affected)} nodes | EROI_global={self._eroi_penalty_global:.3f}"
        )

    # =========================================================================
    # Diagnostics
    # =========================================================================

    def global_energy_stress(self, model: "FoodEnergyModel") -> float:
        """Mean ES_index across all agents."""
        agents = list(model.agent_map.values())
        if not agents:
            return 0.0
        return float(np.mean([a.energy_stress_index for a in agents]))

    def n_overloaded(self, model: "FoodEnergyModel") -> int:
        """Count of nodes with ES_index >= ES_OVERLOAD_THRESHOLD."""
        return sum(
            1 for a in model.agent_map.values()
            if getattr(a, "overload_energy", False)
        )

    def summary(self, model: "FoodEnergyModel") -> dict:
        agents = list(model.agent_map.values())
        es_vals = [a.energy_stress_index for a in agents]
        xi_vals = [a.xi_biofuel for a in agents]
        pe_vals = [self._energy_price.get(a.name, 1.0) for a in agents]
        return {
            "eroi_penalty_global":   round(self._eroi_penalty_global, 4),
            "mean_ES_index":         round(float(np.mean(es_vals)), 4),
            "max_ES_index":          round(float(np.max(es_vals)), 4),
            "n_energy_overloaded":   self.n_overloaded(model),
            "mean_xi_biofuel":       round(float(np.mean(xi_vals)), 4),
            "mean_energy_price":     round(float(np.mean(pe_vals)), 4),
            "max_energy_price":      round(float(np.max(pe_vals)), 4),
        }
