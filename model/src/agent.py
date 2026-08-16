"""
agent.py
--------
CountryAgent for the Global Food-Energy Systemic Risk ABM.

Framework : Gambhir et al. (2025) + Homer-Dixon et al. (2015)
Phase     : 2 — Core food-system ABM, real-data initialized

State vector (per EQUATIONS.md §1):
  Sᵢ = (Pᵢ, Lᵢ, Wᵢ, E_fuelᵢ, E_elecᵢ, E_renewᵢ, Kᵢ, Tᵢ,
         F_perishᵢ, F_imperishᵢ, F_animalᵢ, Rᵢ, ρᵢ, Gᵢ)

Production (§2):
  Qᵢ(t) = Pᵢ × cᵢ × (L/L_ref)^0.30 × W^0.25 × (E_fuel/E_ref)^0.20 × T^0.25 × Cᵢ × r_renew

Food security (§5): flow-based σᵢ
Export policy (§11): 3-regime (survival / precautionary / market)
Population dynamics (§9): per-node vital rates bᵢ, dᵢ from real data
Capital dynamics (§10): with depreciation

Phase 3 hooks: energy stress index, biofuel land-competition ξᵢ (default 0)
Phase 4 hooks: FS_index, CC_index, LFBB overload flag (default inactive)
"""

import numpy as np

try:
    from mesa import Agent
    import mesa as _mesa_check
    _MESA_NEW_API = tuple(int(x) for x in _mesa_check.__version__.split(".")[:2]) >= (3, 0)
except ImportError:
    _MESA_NEW_API = False
    class Agent:
        def __init__(self, model):
            self.model = model

# ── Cobb-Douglas exponents (must sum to 1.0) ─────────────────────────────────
ALPHA = 0.30   # land
BETA  = 0.25   # water
GAMMA = 0.20   # fuel energy  (corrected from 0.15 per EQUATIONS.md §2)
DELTA = 0.25   # technology   (corrected from 0.30 per EQUATIONS.md §2)
assert abs(ALPHA + BETA + GAMMA + DELTA - 1.0) < 1e-9, "Exponents must sum to 1"

# ── Reference endowments ─────────────────────────────────────────────────────
L_REF = 40.0   # median arable land % (Phase 1 calibration)
E_REF = 70.0   # median fuel energy TWh

# ── Renewable energy boost ───────────────────────────────────────────────────
RENEW_BOOST = 0.05   # r_renew = 1 + 0.05 × (E_renew / 100)

# ── Livestock feed-conversion ratios and biological delays (years) ───────────
LIVESTOCK = {
    "poultry": {"eta": 0.30, "tau": 1},
    "pork":    {"eta": 0.15, "tau": 2},
    "beef":    {"eta": 0.07, "tau": 5},
}
MAX_TAU = max(p["tau"] for p in LIVESTOCK.values())

# ── Food security thresholds ─────────────────────────────────────────────────
SIGMA_SECURE  = 1.20
SIGMA_WARNING = 1.00
SIGMA_CRISIS  = 0.80

# ── Reserve ratio ────────────────────────────────────────────────────────────
RESERVE_RATIO = 0.15

# ── Non-perishable stock cap ─────────────────────────────────────────────────
MAX_STOCK_YEARS = 8.0

# ── Export policy constants (§11) ────────────────────────────────────────────
PHI_EXPORT = 0.60   # max precautionary export fraction
EXPORT_CURVE_POW = 1.5


class CountryAgent(Agent):
    """
    Represents one node (country or regional bloc) in the 35-node network.

    Parameters come directly from node_parameters.csv loaded by the model,
    so every parameter has a real-data source (see docs/DATA_PROVENANCE.md).

    Phase 3/4 placeholders: energy_stress_index, CC_index, FS_index, overload_food
    are set to defaults here and overwritten by the STC engine in later phases.
    """

    def __init__(
        self,
        model,
        # ── identifiers ──────────────────────────────────────────────────
        uid: int,
        name: str,
        node_type: str,               # 'hub_country' | 'regional_bloc'
        # ── demographic ──────────────────────────────────────────────────
        population: float,
        b_i: float,                   # birth rate (from OWID data)
        d_i: float,                   # base death rate (from OWID data)
        psi_i: float,                 # famine mortality sensitivity (§9)
        # ── production inputs ─────────────────────────────────────────────
        land: float,                  # arable land % (L_i)
        water: float,                 # water availability [0,1] (W_i)
        energy_fuel: float,           # fossil fuel TWh (E_fuel_i)
        energy_elec: float,           # electricity TWh (E_elec_i)
        energy_renew: float,          # renewables TWh (E_renew_i)  [unused in prod fn directly]
        technology: float,            # technology multiplier T_i
        A_i: float,                   # TFP / land productivity multiplier (from FAO)
        # ── economic ─────────────────────────────────────────────────────
        capital: float,               # K_i (GDP bn USD 2015)
        gdp: float,                   # G_i
        # ── food stocks ──────────────────────────────────────────────────
        food_imperish: float,         # F_imperish_i (Mt kcal equivalent)
        food_animal: float,           # F_a_i
        food_perish: float,           # F_perish_i
        reserves: float,              # R_i
        # ── caloric demand ───────────────────────────────────────────────
        caloric_demand_yr: float,     # D_i in kcal/year (from FAO kcal_cap_day × pop × 365)
        # ── export policy ────────────────────────────────────────────────
        mu_i: float,                  # market-regime max export fraction (§11)
        sigma_safe_i: float,          # safe threshold for precautionary regime (§11)
        # ── risk ─────────────────────────────────────────────────────────
        political_risk: float,        # ρᵢ [0,1] (used by trade.py)
        climate_vuln: float,          # εᵢ coping capacity component
        undernourishment_baseline: float,  # % at baseline (validation anchor)
        # ── theta fractions (food category shares) ────────────────────────
        theta_imperish: float = 0.676,
        theta_animal: float   = 0.194,
        theta_perish: float   = 0.130,
        # ── per-country energy-food coupling ─────────────────────────────
        epsilon_ef: float     = 0.40,  # Energy→Food TFP penalty (IEA/FAO calibrated)
    ):
        super().__init__(model)

        # ── identifiers ──────────────────────────────────────────────────────
        self.uid       = uid
        self.name      = name
        self.node_type = node_type

        # ── demographic ──────────────────────────────────────────────────────
        self.population = float(population)
        self.b_i        = float(b_i)
        self.d_i        = float(d_i)
        self.psi_i      = float(psi_i)

        # ── production inputs ─────────────────────────────────────────────────
        self.land         = float(land)
        self.water        = float(water)
        self.energy_fuel  = float(energy_fuel)
        self.energy_elec  = float(energy_elec)
        self.energy_renew = float(energy_renew)
        self.technology   = float(technology)
        self._technology_baseline = float(technology)  # BUG-006b: ceiling anchor
        self.A_i          = float(A_i)

        # Baseline energy values for recovery (Phase 3 uses these)
        self._energy_fuel_baseline  = float(energy_fuel)
        self._energy_renew_baseline = float(energy_renew)

        # ── economic ─────────────────────────────────────────────────────────
        self.capital = float(capital)
        self.gdp     = float(gdp)

        # ── food stocks ──────────────────────────────────────────────────────
        self.food_imperish = float(food_imperish)
        self.food_animal   = float(food_animal)
        self.food_perish   = float(food_perish)
        self.reserves      = float(reserves)

        # ── caloric demand ────────────────────────────────────────────────────
        self._caloric_demand_yr = float(caloric_demand_yr)

        # ── export policy ─────────────────────────────────────────────────────
        self.mu_i        = float(mu_i)
        self.sigma_safe_i = float(sigma_safe_i)

        # ── risk / coping parameters ──────────────────────────────────────────
        self.political_risk             = float(political_risk)
        self.climate_vuln               = float(climate_vuln)
        self.undernourishment_baseline  = float(undernourishment_baseline)

        # ── per-country energy-food coupling ──────────────────────────────────
        # Per-country EPSILON_EF from node_parameters.epsilon_ef (IEA/FAO calibrated).
        # Default 0.40 (IEA global estimate) for backward compatibility.
        self.epsilon_ef = float(epsilon_ef)

        # ── theta fractions ───────────────────────────────────────────────────
        self.theta_imperish = float(theta_imperish)
        self.theta_animal   = float(theta_animal)
        self.theta_perish   = float(theta_perish)

        # ── climate stress indices (set by STC engine / shock module) ─────────
        self.drought_index    = 0.0
        self.heatwave_index   = 0.0
        self.flood_index      = 0.0
        self.climate_modifier = 1.0

        # ── logistics disruption [0,1] ────────────────────────────────────────
        self.logistics_disruption = 0.0

        # ── derived state (computed each step) ───────────────────────────────
        self.food_security    = 1.5    # σᵢ
        self.annual_production = 0.0
        self.export_fraction  = 0.0   # current regime export fraction
        self.export_ban       = False  # True when export_fraction == 0 (σᵢ ≤ 1.0)

        # ── trade flow accumulators (reset each step) ─────────────────────────
        self.exports_this_step = 0.0
        self.imports_this_step = 0.0
        self.trade_value_exported = 0.0
        self.trade_value_imported = 0.0

        # ── population metrics ────────────────────────────────────────────────
        self.undernourished = False
        self.famine_deaths_cumulative = 0.0

        # ── livestock feed history (biological delays) ────────────────────────
        self._grain_feed_history: list = []

        # ── Phase 3/4 placeholders ────────────────────────────────────────────
        # Energy stress index (set by energy.py in Phase 3)
        self.energy_stress_index = 0.0
        # Biofuel land competition fraction (set by energy.py in Phase 3)
        self.xi_biofuel = 0.0
        # Homer-Dixon indices (set by stc_engine.py in Phase 4)
        #
        # BUG-007 FIX (audit Fix #7, CRITICAL): FS_index previously started at
        # 0.0 for every node regardless of structural fragility, forcing an
        # unmotivated "warm-up suppression" hack (t<3 → no overload allowed)
        # to stop chronic low-CC nodes (e.g. Central Africa, CC≈0.05-0.45)
        # from registering a spurious overload at t=1 before stress had time
        # to "accumulate" from an artificially low starting point. The correct
        # fix is to initialise FS_index near each node's equilibrium stress
        # level given its baseline undernourishment, so chronically fragile
        # nodes start already-elevated (consistent with their real-world
        # status) rather than at a false zero. Equilibrium proxy:
        #   FS_index(0) ≈ undernourishment_baseline_pct / 100
        # i.e. a node with 40% baseline undernourishment starts at FS≈0.40,
        # not FS≈0.0. This is set after __init__ via _init_equilibrium_stress()
        # once undernourishment_baseline is available (see below).
        self.FS_index   = 0.0   # overwritten by _init_equilibrium_stress()
        self.CC_index   = 1.0   # coping capacity index
        self.overload_food   = False  # LFBB overload flag
        self.overload_energy = False

        # BUG-007 FIX: set FS_index to its equilibrium proxy now that
        # undernourishment_baseline is available.
        self._init_equilibrium_stress()

    def _init_equilibrium_stress(self):
        """
        BUG-007 FIX (audit Fix #7): initialise FS_index from an equilibrium
        proxy rather than zero, so chronically food-insecure nodes start near
        their real-world stress level instead of requiring several simulated
        years to "catch up" via accumulation from zero. This removes the
        scientific justification for the warm-up suppression hack in
        stc_engine.py (kept as a numerical safety margin only, not a
        theoretical requirement).

        Proxy: FS_index(0) = undernourishment_baseline_pct / 100, clipped to
        [0, 1]. A node with 0% baseline undernourishment starts at FS=0
        (no accumulated stress); a node with 40% baseline undernourishment
        starts at FS=0.40, consistent with chronic structural fragility
        already being "priced in" at t=0 rather than discovered for the
        first time after 3 simulated years.
        """
        self.FS_index = float(np.clip(self.undernourishment_baseline / 100.0, 0.0, 1.0))

    # =========================================================================
    # Climate modifier (§3)
    # =========================================================================

    def _update_climate_modifier(self):
        """
        Cᵢ(t) = max(0.05, 1 − 0.40×Dᵢ×adapt − 0.35×Hᵢ×adapt − 0.25×Fᵢ×adapt)

        PHASE B (this session): `adapt` is an optional per-agent climate-
        sensitivity multiplier, read via getattr with default 1.0 so this
        is BYTE-IDENTICAL to the original formula for every agent that
        does not have the attribute set (i.e. every existing scenario,
        unchanged). Set only by make_climate_adaptation_lever() in
        scenarios.py — see that function's docstring for the equation
        governing how cumulative investment maps to this multiplier.
        """
        adapt = getattr(self, "climate_sensitivity_multiplier", 1.0)
        self.climate_modifier = max(
            0.05,
            1.0
            - 0.40 * self.drought_index * adapt
            - 0.35 * self.heatwave_index * adapt
            - 0.25 * self.flood_index * adapt,
        )

    # =========================================================================
    # Production — plant food (§2)
    # =========================================================================

    def _produce_plant_food(self) -> float:
        """
        Qᵢ(t) = Pᵢ × cᵢ × A_i × (L_food/L_ref)^α × W^β × (E_fuel/E_ref)^γ × T^δ × Cᵢ × r_renew

        Phase 3 hook: L_food = L × (1 − ξ_biofuel)
        """
        self._update_climate_modifier()

        # Phase 3: land competition reduces effective food-land
        L_food = max(self.land, 0.01) * (1.0 - self.xi_biofuel)
        W      = max(self.water,       0.01)
        E      = max(self.energy_fuel, 0.01)
        T      = max(self.technology,  0.01)
        C      = self.climate_modifier

        # Caloric need per year = demand / population  (already derived from FAO data)
        c_i = self._caloric_demand_yr / max(self.population, 1.0)

        # Renewable boost factor
        r_renew = 1.0 + RENEW_BOOST * (self.energy_renew / 100.0)

        # PHASE C (this session): soil quality multiplier, per Digital Twin
        # spec Part C2. getattr default 1.0 (undegraded) reproduces the
        # original formula exactly when no SoilQualityDriver is attached
        # to the model (the default) -- byte-identical backward
        # compatibility, verified in test_phase_c_climate_drivers.py.
        Q_soil = getattr(self, "soil_quality", 1.0)

        # PHASE C increment 2 (this session): fertilizer response
        # multiplier (Mitscherlich-type, resource_drivers.py), per Digital
        # Twin spec Part C3. getattr default 1.0 reproduces the original
        # formula exactly when no FertilizerDriver is attached.
        F_response = getattr(self, "fertilizer_response", 1.0)

        # PHASE C increment 2 (this session): water stress multiplier
        # (1 - water_stress), per Digital Twin spec Part C4. getattr
        # default 0.0 stress (i.e. multiplier 1.0) reproduces the
        # original formula exactly when no WaterStockDriver is attached.
        water_stress_penalty = 1.0 - getattr(self, "water_stress", 0.0)

        # Population-anchored Cobb-Douglas with A_i (TFP)
        q_plant = (
            self.population
            * c_i
            * self.A_i
            * ((L_food / L_REF) ** ALPHA)
            * (W          ** BETA)
            * ((E / E_REF) ** GAMMA)
            * (T          ** DELTA)
            * C
            * r_renew
            * Q_soil
            * F_response
            * water_stress_penalty
        )

        # Distribute across stock categories (§2)
        self.food_imperish += self.theta_imperish * q_plant
        self.food_perish   += self.theta_perish   * q_plant

        # Stock cap: non-perishable ≤ MAX_STOCK_YEARS × annual non-perishable demand
        cap = MAX_STOCK_YEARS * self._caloric_demand_yr * self.theta_imperish
        self.food_imperish = min(self.food_imperish, cap)

        return q_plant

    # =========================================================================
    # Production — animal food (§4)
    # =========================================================================

    def _produce_animal_food(self) -> float:
        """
        Q_animalᵢ(t) = Σ_s  η_s × Q_grainᵢ(t − τ_s)
        """
        q_animal = 0.0
        hist_len = len(self._grain_feed_history)

        for spec, params in LIVESTOCK.items():
            tau = params["tau"]
            eta = params["eta"]
            if hist_len >= tau:
                past_grain = self._grain_feed_history[-tau]
                q_animal += eta * past_grain

        self.food_animal += q_animal
        return q_animal

    # =========================================================================
    # Consumption
    # =========================================================================

    def _consume_food(self):
        """
        Priority: perishable → non-perishable → animal → reserves.
        Perishables largely spoil each step (only 10% carryover).
        """
        demand = self._caloric_demand_yr
        consumed = 0.0

        # Perishable first (spoils)
        take = min(self.food_perish, demand - consumed)
        self.food_perish -= take
        consumed += take

        # Non-perishable
        if consumed < demand:
            take = min(self.food_imperish, demand - consumed)
            self.food_imperish -= take
            consumed += take

        # Animal products
        if consumed < demand:
            take = min(self.food_animal, demand - consumed)
            self.food_animal -= take
            consumed += take

        # Reserves (last resort)
        if consumed < demand:
            take = min(self.reserves, demand - consumed)
            self.reserves -= take
            consumed += take

        # Perishables spoil (10% carryover)
        self.food_perish = max(0.0, self.food_perish * 0.10)

    # =========================================================================
    # Food security index (§5)
    # =========================================================================

    def compute_food_security(self):
        """
        σᵢ(t) = (Qᵢ + R_draw + stock_bonus) / Dᵢ

        Flow-based: avoids spurious security from accumulated stocks.
        """
        D = max(self._caloric_demand_yr, 1.0)

        R_draw     = min(self.reserves, 0.30 * D)
        stock_bonus = min(
            max(0.0, self.food_imperish - self.theta_imperish * D),
            0.50 * D,
        )
        effective_supply = self.annual_production + R_draw + stock_bonus

        self.food_security  = effective_supply / D
        self.undernourished = self.food_security < SIGMA_WARNING
        return self.food_security

    # =========================================================================
    # Export policy — 3-regime (§11)
    # =========================================================================

    def update_export_policy(self):
        """
        3-regime export policy replaces the binary ban.

        Regime 1 (σᵢ ≤ 1.0):       survival — zero exports
        Regime 2 (1.0 < σᵢ ≤ σ_safe): precautionary — partial ramp
        Regime 3 (σᵢ > σ_safe):      market — export up to μᵢ
        """
        sigma = self.food_security

        if sigma <= SIGMA_WARNING:
            self.export_fraction = 0.0
            self.export_ban = True

        elif sigma <= self.sigma_safe_i:
            s = (sigma - SIGMA_WARNING) / max(self.sigma_safe_i - SIGMA_WARNING, 1e-6)
            self.export_fraction = PHI_EXPORT * (s ** EXPORT_CURVE_POW)
            self.export_ban = False

        else:
            self.export_fraction = min(self.mu_i, 0.90)
            self.export_ban = False

    # =========================================================================
    # Population dynamics (§9)
    # =========================================================================

    def update_population(self):
        """
        Pᵢ(t+1) = Pᵢ(t) × (1 + bᵢ − dᵢ − ψᵢ × max(0, 1 − σᵢ))

        Uses per-node vital rates from OWID data.
        """
        famine_penalty = max(0.0, 1.0 - self.food_security)
        net_rate = self.b_i - self.d_i - self.psi_i * famine_penalty

        famine_deaths = self.psi_i * famine_penalty * self.population
        self.famine_deaths_cumulative += famine_deaths

        self.population = max(1.0, self.population * (1.0 + net_rate))

    # =========================================================================
    # Capital dynamics (§10)
    # =========================================================================

    def update_capital(self):
        """
        Kᵢ(t+1) = Kᵢ(t) + 0.10×ΣXᵢⱼ − 0.10×ΣXⱼᵢ − 0.015×Kᵢ
        Technology improves logarithmically with capital, bounded near each
        node's calibrated ceiling (BUG-006b fix, see below).
        """
        export_gain  = 0.10 * self.trade_value_exported
        import_cost  = 0.10 * self.trade_value_imported
        depreciation = 0.015 * self.capital
        disaster_loss = 0.02 * self.capital * (1.0 - self.climate_modifier)

        self.capital += export_gain - import_cost - depreciation - disaster_loss
        self.capital  = max(0.1, self.capital)

        # Technology (§10)
        # BUG-006b FIX (newly discovered during price-floor audit fix): the
        # original rule `min(T + 0.002*log(K), 5.0)` is unbounded relative to
        # the real calibrated T_i range [0.05, 0.927] (node_parameters.csv).
        # For a high-capital node (e.g. USA, K≈32,000bn), this adds ≈0.021 of
        # technology PER STEP with no brake, compounding toward the 5.0 cap —
        # a 5x+ overshoot of any real-world technology index. Because T_i
        # enters production with exponent δ=0.25, this silently inflated
        # global food production (supply/demand ratio drifted from 1.40 to
        # 1.95+ over a 25-step baseline run), which was the true structural
        # driver of the price-floor degeneracy this fix addresses upstream.
        # Fix: cap technology growth asymptotically at 1.10× each node's own
        # initial calibrated value (allows modest real productivity growth —
        # consistent with historical TFP growth of 1-2%/yr — without runaway
        # compounding far past any observed real-world technology index).
        tech_ceiling = self._technology_baseline * 1.10
        delta_tech   = 0.002 * np.log(max(self.capital, 1.0))
        # Logistic-style approach to ceiling: growth shrinks as T approaches ceiling
        headroom     = max(0.0, tech_ceiling - self.technology) / max(tech_ceiling, 1e-6)
        self.technology = min(self.technology + delta_tech * headroom, tech_ceiling)

        # GDP proxy update (capital-correlated)
        self.gdp = self.capital * 1.05

        # Reset accumulators
        self.exports_this_step    = 0.0
        self.imports_this_step    = 0.0
        self.trade_value_exported = 0.0
        self.trade_value_imported = 0.0

    # =========================================================================
    # Reserve replenishment
    # =========================================================================

    def _replenish_reserves(self):
        """
        Rebuild strategic reserves from surplus non-perishable stocks.
        Target: RESERVE_RATIO × F_imperish
        Transfer up to 5% of current non-perishable stock per step.
        """
        target = RESERVE_RATIO * max(self.food_imperish, 1.0)
        if self.food_imperish > 0 and self.reserves < target:
            transfer = min(0.05 * self.food_imperish, target - self.reserves)
            self.food_imperish -= transfer
            self.reserves      += transfer

    # =========================================================================
    # Phase 3/4 hook — FS_index (§6, computed here for Phase 4 handoff)
    # =========================================================================

    def _compute_FS_index(self):
        """
        FS_indexᵢ(t) = max(0, 1 − σᵢ(t)) × (1 + max(0, p(t)/p(0) − 1))

        ES_index and CC_index are computed by energy.py and stc_engine.py.
        """
        p_ratio = getattr(self.model, "price_ratio", 1.0)
        self.FS_index = max(0.0, 1.0 - self.food_security) * (
            1.0 + max(0.0, p_ratio - 1.0)
        )

    # =========================================================================
    # Full production step
    # =========================================================================

    def produce(self):
        """Called by model each tick: production → consumption → reserves."""
        q_plant = self._produce_plant_food()
        self.annual_production = q_plant

        # Record grain for livestock feed history (theta_imperish share = grain proxy)
        grain_for_feed = self.theta_imperish * q_plant
        self._grain_feed_history.append(grain_for_feed)
        if len(self._grain_feed_history) > MAX_TAU + 1:
            self._grain_feed_history.pop(0)

        q_animal = self._produce_animal_food()
        self.annual_production += q_animal

        self._consume_food()
        self._replenish_reserves()

    # =========================================================================
    # Mesa step
    # =========================================================================

    def step(self):
        """
        Agent lifecycle each tick:
          1. Produce + consume
          2. Compute food security σᵢ
          3. Determine export policy (3-regime)
          4. Update population
          5. Update capital + technology
          6. Compute FS_index (Phase 4 hook)
        """
        self.produce()
        self.compute_food_security()
        self.update_export_policy()
        self.update_population()
        self.update_capital()
        self._compute_FS_index()

    # =========================================================================
    # Utility
    # =========================================================================

    def caloric_demand(self) -> float:
        """Public accessor for caloric demand (kcal/year)."""
        return self._caloric_demand_yr

    def __repr__(self):
        return (
            f"CountryAgent({self.name}, pop={self.population/1e6:.1f}M, "
            f"σ={self.food_security:.3f}, K={self.capital:.1f}bn)"
        )
