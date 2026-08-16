"""
model.py
--------
FoodEnergyModel: Mesa Model for the Global Food-Energy Systemic Risk ABM.

Framework : Gambhir et al. (2025) + Homer-Dixon et al. (2015)
Phase     : 2 — Core food-system ABM, real-data initialized

Architecture:
  - CountryAgent (agent.py)       : production, consumption, population, capital
  - Trade network (trade.py)      : real 35-node full-mesh from network_weights.csv
  - Price system (prices.py)      : FAO FPI-anchored exponential dynamics
  - Metrics (metrics.py)          : 6 resilience indicators + 4 SAV indices

Phase 3 slot: energy.py (energy system + bidirectional coupling)
Phase 4 slot: stc_engine.py (SS/LFBB/RC stress accumulation + triggers)
Phase 5 slot: political_economy.py (trader agents + vulnerability diagnostics)

Data required (must exist in data/processed/):
  node_parameters.csv    ← Phase 1 output
  network_weights.csv    ← Phase 1 output
  fpi_annual.csv         ← Phase 1 output (optional; initialises price)
"""

import numpy as np
import pandas as pd
import networkx as nx
from pathlib import Path

try:
    from mesa import Model
except ImportError:
    class Model:
        def __init__(self, seed=None):
            self.steps = 0

from agent           import CountryAgent
from trade           import build_trade_network, execute_trade_step
from prices          import PriceSystem
from metrics         import MetricsCollector
from energy          import EnergyModule
from stc_engine      import STCEngine
from political_economy import PoliticalEconomyModule

# ── Default data directory (relative to this file's location) ─────────────────
_SRC_DIR  = Path(__file__).resolve().parent
_ROOT_DIR = _SRC_DIR.parent
_DATA_DIR = _ROOT_DIR / "data"


class FoodEnergyModel(Model):
    """
    Global Food-Energy Systemic Risk Agent-Based Model.

    Parameters
    ----------
    data_dir   : path to the project data/ folder (default: auto-detected)
    init_year  : simulation start year mapped to Phase 1 data  (default 2022)
    scenario   : scenario label for output naming
    seed       : RNG seed
    """

    def __init__(
        self,
        data_dir: Path = None,
        init_year: int = 2022,
        scenario: str = "baseline",
        seed: int = 42,
    ):
        # Mesa 3.x reserves 'scenario' and 'steps' — use private names
        super().__init__()

        self._scenario_name = scenario  # use _scenario_name to avoid Mesa conflict
        self.init_year  = init_year
        self.rng        = np.random.default_rng(seed)

        # ── Paths ──────────────────────────────────────────────────────────────
        self.data_dir = Path(data_dir) if data_dir else _DATA_DIR

        proc = self.data_dir / "processed"
        node_params_path = proc / "node_parameters.csv"
        network_path     = proc / "network_weights.csv"
        fpi_path         = proc / "fpi_annual.csv"

        for p in [node_params_path, network_path]:
            if not p.exists():
                raise FileNotFoundError(
                    f"Required Phase 1 file not found: {p}\n"
                    f"Run src/data_pipeline.py to generate Phase 1 data first."
                )

        # ── Phase 3/4/5 hooks ──────────────────────────────────────────────────
        self.sanction_penalty: float = 0.0
        self.trader_module           = None   # Phase 5
        self.stc_engine              = None   # Phase 4
        self._sav_scale_baseline: float | None = None

        # Phase 3: energy module — active by default from Phase 3 onward
        self.energy_module = EnergyModule(seed=seed)

        # Phase 4: STC engine — active with empty trigger list by default
        self.stc_engine = STCEngine(triggers=[], ss_mode="multiplicative")

        # PHASE C (this session): opt-in flag resolving the climate
        # triple-counting finding from PHASE2_5B_CAUSAL_DECOMPOSITION.md
        # (§7/§9): climate_modifier previously fed production, FS_index,
        # AND ES_index simultaneously, with the FS_index term adding no
        # information beyond what production already transmits via σ, and
        # the ES_index term applying a flat penalty regardless of a node's
        # actual hydro/irrigation energy dependency. Default False
        # preserves the EXACT original behaviour (all four channels
        # active, including the redundant one) so every existing
        # retrodiction/scenario result is unaffected unless explicitly
        # opted in — see stc_engine.py::_accumulate_stress and
        # energy.py::EnergyModule._compute_es_index for the two
        # conditional edits this flag gates, and
        # test_phase_c_climate_drivers.py for the backward-compatibility
        # verification.
        self.climate_single_channel_mode = False

        # PHASE C (this session): optional continuous climate driver slot,
        # mirroring the existing energy_module optional-plugin pattern
        # (line ~99 above). None by default -- 100% backward compatible,
        # since no existing scenario sets this. See climate_drivers.py.
        self.climate_driver = None

        # PHASE C (this session): optional soil-quality driver slot, same
        # pattern. None by default.
        self.soil_driver = None

        # PHASE C increment 2 (this session): optional fertilizer and
        # water-stock driver slots, same optional-plugin pattern. None by
        # default -- 100% backward compatible.
        self.fertilizer_driver = None
        self.water_driver = None

        # Phase 5: political economy / trader module — active by default
        self.trader_module = PoliticalEconomyModule(n_traders=5, seed=seed)

        # RC cascade state (set by stc_engine each step)
        self._cascade_active     = False
        self._rc_contagion_boost = 0.0

        # ── Price system ───────────────────────────────────────────────────────
        self.price_system = PriceSystem(
            baseline  = 1.0,
            k         = 1.5,
            fpi_csv   = fpi_path if fpi_path.exists() else None,
            init_year = init_year,
        )

        # ── Load node parameters ───────────────────────────────────────────────
        # BUG-008 FIX (audit Fix #1, CRITICAL — temporal incoherence in
        # retrodiction): previously node_parameters.csv (a fixed 2022
        # snapshot) was loaded unconditionally regardless of init_year. This
        # meant the 2008 retrodiction ran with Ukraine's 2022 grain-export-
        # derived A_i, 2022 capital stocks, 2022 technology levels, etc. — a
        # 2022-configured world retrodicting a 2008 crisis. Fix: when
        # init_year != 2022 and node_panel.csv has coverage for that year
        # (panel spans 2000-2023), rescale the time-varying columns of the
        # static snapshot to that year's real values from the panel. Columns
        # NOT rescaled (A_i TFP multiplier, theta food-category shares,
        # sigma_safe_i, mu_i export policy parameters) remain at their
        # calibrated values, since the panel does not carry independent
        # year-specific calibrations for these structural parameters — this
        # is documented as a remaining limitation (see BUGS_FIXED.md).
        self._node_params = pd.read_csv(node_params_path)

        # ── Load node_panel for kcal_cap_day lookup AND year-rescaling ────────
        node_panel_path = proc / "node_panel.csv"
        self._node_panel = pd.read_csv(node_panel_path) if node_panel_path.exists() else None

        if self._node_panel is not None and init_year != 2022:
            self._node_params = self._rescale_params_to_year(
                self._node_params, self._node_panel, init_year
            )

        # ── Build trade network ────────────────────────────────────────────────
        self.network: nx.DiGraph = build_trade_network(self.data_dir)

        # ── Agent map: node_name → CountryAgent ───────────────────────────────
        self.agent_map: dict[str, CountryAgent] = {}

        # ── Initialise agents ──────────────────────────────────────────────────
        self._create_agents()

        # ── Metrics collector ──────────────────────────────────────────────────
        self.metrics = MetricsCollector()

        # ── Internal trade volume tracker ──────────────────────────────────────
        self._last_trade_volume = 0.0

        print(
            f"[FoodEnergyModel] Initialised {len(self.agent_map)} agents | "
            f"scenario={scenario} | init_year={init_year} | seed={seed}"
        )

    def _get_kcal_cap_day(self, node_name: str) -> float:
        """
        Look up FAO kcal/capita/day for a node from node_panel for init_year.
        Falls back to 2700 (global average) if not available.
        """
        if self._node_panel is None:
            return 2700.0
        mask = (
            (self._node_panel["node"] == node_name) &
            (self._node_panel["year"] == self.init_year)
        )
        rows = self._node_panel[mask]
        if rows.empty or "kcal_cap_day" not in rows.columns:
            return 2700.0
        val = rows["kcal_cap_day"].values[0]
        if pd.isna(val) or val <= 0:
            return 2700.0
        return float(val)

    def _rescale_params_to_year(
        self, params_2022: pd.DataFrame, panel: pd.DataFrame, year: int
    ) -> pd.DataFrame:
        """
        BUG-008 FIX (audit Fix #1): rescale the static 2022 node_parameters
        snapshot to a target retrodiction year using real panel data, so
        retrodiction of a historical crisis (e.g. 2008) does not run on a
        2022-configured world.

        Rescaling rule per column: param_year = param_2022 * (panel_year_val
        / panel_2022_val), i.e. apply the panel's own year-over-year growth
        ratio to each calibrated 2022 parameter. This preserves cross-node
        relative calibration (which the static snapshot encodes) while
        correcting the absolute temporal level. Falls back to the unscaled
        2022 value if panel data is missing for either year (logged once).

        Columns rescaled: P_i (population), K_i (capital), T_i (technology),
        E_fuel_i (fossil energy), L_i (arable land), W_i (water),
        D_i_Mt (caloric demand), A_i (TFP multiplier -- see below).

        Columns intentionally NOT rescaled (remain at 2022 calibration):
        theta_* (food category shares), mu_i / sigma_safe_i (export policy
        parameters), epsilon_i, psi_i, rho_i, clim_vuln_i.

        A_i (TFP multiplier) FIX: previously not rescaled at all -- see
        BUGS_FIXED.md's documented limitation. Real, year-specific A_i is
        now back-calculated from FAO Crops Production data via the same
        SSR-inversion method as BUG-003 (A_i = SSR_i / Cobb-Douglas factor
        product), stored in node_panel.csv's `A_i_implied` column, and
        rescaled here via the same ratio method as every other column.
        Currently populated for 2000 and 2022 (the anchor); other years
        fall back to the 2022 calibration until similarly back-calculated.
        """
        panel_col_map = {
            "P_i":     "population",
            "K_i":     "gdp_bn_usd2015",
            "T_i":     "Ti",
            "E_fuel_i": "fossil_fuel_consumption",
            "L_i":     "Li",
            "W_i":     "Wi",
            "D_i_Mt":  "caloric_demand_kcal_yr",
            "A_i":     "A_i_implied",
        }

        out = params_2022.copy()
        panel_2022 = panel[panel["year"] == 2022].set_index("node")
        panel_year = panel[panel["year"] == year].set_index("node")

        n_rescaled = 0
        n_fallback = 0

        for param_col, panel_col in panel_col_map.items():
            if param_col not in out.columns or panel_col not in panel.columns:
                continue
            for idx, row in out.iterrows():
                node = row["Node"]
                try:
                    v2022 = panel_2022.loc[node, panel_col]
                    vyear = panel_year.loc[node, panel_col]
                    if pd.isna(v2022) or pd.isna(vyear) or v2022 == 0:
                        n_fallback += 1
                        continue
                    ratio = float(vyear) / float(v2022)
                    # Guard against pathological ratios from sparse/noisy data
                    ratio = float(np.clip(ratio, 0.1, 10.0))
                    out.at[idx, param_col] = row[param_col] * ratio
                    n_rescaled += 1
                except (KeyError, TypeError):
                    n_fallback += 1
                    continue

        print(
            f"[FoodEnergyModel] BUG-008 fix: rescaled node parameters "
            f"2022 → {year} ({n_rescaled} values rescaled, "
            f"{n_fallback} fell back to 2022 calibration due to missing panel data)"
        )
        return out

    # =========================================================================
    # Agent creation from real Phase 1 data
    # =========================================================================

    def _create_agents(self):
        """
        Instantiate one CountryAgent per row in node_parameters.csv.

        Every column maps to a documented parameter (see docs/DATA_PROVENANCE.md).
        Missing or NaN values fall back to safe defaults — this is logged so
        the DATA_PROVENANCE.md gap table stays accurate.
        """
        df = self._node_params
        uid = 0

        for _, row in df.iterrows():
            name = str(row["Node"])

            # ── Helper: safe float with fallback ─────────────────────────────
            def _get(col, default=0.0):
                val = row.get(col, np.nan)
                if pd.isna(val) or val is None:
                    return float(default)
                return float(val)

            # ── Demographic ──────────────────────────────────────────────────
            population = _get("P_i", 1e6)
            b_i        = _get("b_i",  0.015)
            d_i        = _get("d_i",  0.009)
            psi_i      = _get("psi_i", 0.02)

            # ── Production inputs ─────────────────────────────────────────────
            land         = _get("L_i",      40.0)
            water        = _get("W_i",       0.7)
            energy_fuel  = _get("E_fuel_i", 70.0)
            energy_elec  = _get("E_elec_i", 20.0)
            energy_renew = 0.0   # will be added from node_panel in Phase 3
            technology   = _get("T_i",       1.0)
            A_i          = _get("A_i",       1.0)

            # ── Economic ──────────────────────────────────────────────────────
            capital = _get("K_i", 500.0)
            gdp     = capital * 1.05   # GDP proxy

            # ── Caloric demand: kcal_cap_day × population × 365 ─────────────
            # D_i_Mt (node_parameters) is total food availability including imports —
            # using it as demand would conflate supply with demand.
            # We derive demand from per-capita intake × population instead.
            # Fallback hierarchy: kcal_cap_day from node_panel → income-class default
            kcal_cap_day = self._get_kcal_cap_day(name)
            if kcal_cap_day <= 0:
                # Fallback: UN minimum adequate intake by node type
                kcal_cap_day = 2700  # global average
            caloric_demand_yr_kcal = population * kcal_cap_day * 365

            # ── Food stocks ───────────────────────────────────────────────────
            food_imperish = _get("F_imperish_i", 0.0)
            food_animal   = _get("F_a_i",        0.0)
            food_perish   = _get("F_perish_i",   0.0)
            reserves      = _get("R_i",          0.0)

            # F_imperish_i in node_parameters is in Mt; convert to kcal
            # 1 Mt ≈ 3.5e12 kcal
            if food_imperish > 0:
                food_imperish *= 3.5e12
                food_animal   *= 3.5e12
                food_perish   *= 3.5e12
                reserves      *= 3.5e12
            else:
                # Seed stocks: 3-year buffer of non-perishable demand
                food_imperish = 3.0 * caloric_demand_yr_kcal * 0.676
                food_animal   = 3.0 * caloric_demand_yr_kcal * 0.194
                food_perish   = 0.05 * caloric_demand_yr_kcal * 0.130
                reserves      = 0.15 * food_imperish

            # ── Export policy ─────────────────────────────────────────────────
            mu_i         = _get("mu_i",         0.40)
            sigma_safe_i = _get("sigma_safe_i", 1.30)

            # ── Risk ──────────────────────────────────────────────────────────
            political_risk          = _get("rho_i",                0.33)
            climate_vuln            = _get("clim_vuln_i",          0.33)
            undernourishment_baseline = _get("undernourishment_baseline_pct", 2.5)

            # ── Theta fractions ───────────────────────────────────────────────
            theta_imperish = _get("theta_imperish_i", 0.676)
            theta_animal   = _get("theta_animal_i",   0.194)
            theta_perish   = _get("theta_perish_i",   0.130)

            # ── Per-country energy-food coupling ──────────────────────────────
            # IEA/FAO calibrated epsilon_ef from node_parameters.csv.
            # Default 0.40 (IEA global estimate) for nodes without specific data.
            epsilon_ef = _get("epsilon_ef", 0.40)

            # ── Node type ─────────────────────────────────────────────────────
            node_type = str(row.get("Type", "hub_country"))

            agent = CountryAgent(
                model           = self,
                uid             = uid,
                name            = name,
                node_type       = node_type,
                population      = population,
                b_i             = b_i,
                d_i             = d_i,
                psi_i           = psi_i,
                land            = land,
                water           = water,
                energy_fuel     = energy_fuel,
                energy_elec     = energy_elec,
                energy_renew    = energy_renew,
                technology      = technology,
                A_i             = A_i,
                capital         = capital,
                gdp             = gdp,
                food_imperish   = food_imperish,
                food_animal     = food_animal,
                food_perish     = food_perish,
                reserves        = reserves,
                caloric_demand_yr = caloric_demand_yr_kcal,
                mu_i            = mu_i,
                sigma_safe_i    = sigma_safe_i,
                political_risk  = political_risk,
                climate_vuln    = climate_vuln,
                undernourishment_baseline = undernourishment_baseline,
                theta_imperish  = theta_imperish,
                theta_animal    = theta_animal,
                theta_perish    = theta_perish,
                epsilon_ef      = epsilon_ef,
            )

            self.agent_map[name] = agent
            uid += 1

        # Warn about nodes in network but not in param table (and vice versa)
        net_nodes = set(self.network.nodes())
        param_nodes = set(self.agent_map.keys())
        orphan_net  = net_nodes  - param_nodes
        orphan_param = param_nodes - net_nodes

        if orphan_net:
            print(f"[FoodEnergyModel] ⚠ Network nodes without agent params: {orphan_net}")
        if orphan_param:
            print(f"[FoodEnergyModel] ⚠ Agent params without network node: {orphan_param}")

    # =========================================================================
    # Price ratio (read by agents for FS_index)
    # =========================================================================

    @property
    def price_ratio(self) -> float:
        return self.price_system.price_ratio

    # =========================================================================
    # Step
    # =========================================================================

    def step(self):
        """
        One simulation tick (= one year):

          Phase 3 slot → energy module (before agents, since it modifies inputs)
          1. Each agent: produce → consume → food_security (pre-trade) →
                         export_policy (pre-trade) → population → capital →
                         FS_index
          2. Trade flows resolve across network (uses pre-trade export_fraction)
          2b. BUG-013 FIX (audit CRITICAL — σ simultaneity error): recompute
              food_security for every agent from POST-TRADE stocks. Previously
              σ_i was computed once, pre-trade, and never updated — so a node
              that received imports this step still showed its pre-trade
              (lower) food security in metrics and FS_index, and the NEXT
              step's export policy was set from data that predates the trade
              that just occurred. This systematically understated food
              security for import-dependent nodes and overstated it for
              exporters left holding pre-export stock levels in their own
              metrics. The fix recomputes σ_i post-trade; export policy for
              the FOLLOWING step then correctly reflects this step's trade
              outcome (export policy cannot causally react within the same
              step it's used to gate trade — that would require simultaneous
              equation solving — but the lag is now one step, not permanent).
          Phase 4 slot → STC engine (stress accumulation, overload check,
              triggers) — MOVED to after trade + the post-trade σ/FS_index
              recompute above. SESSION FIX (Phase 2.5, this session, see
              "PHASE2_5_BASELINE_STABILITY_INVESTIGATION.md"): this used to
              run BEFORE trade, evaluating each node's LFBB overload
              condition on PRE-TRADE food security. For import-dependent
              nodes, a pre-trade deficit is true by construction — that is
              the entire reason they trade — so every import-dependent node
              was being flagged as "failed to cope" using a snapshot taken
              before its coping mechanism (trade) had acted. This was
              confirmed to be the dominant cause of a premature, step-1
              overload wave present in nearly every historical and
              counterfactual scenario tested (12/35 nodes overloaded at
              step 1 of an unmodified, trigger-free baseline run — reduced
              to 0/35 by this reordering alone; verified via 9 controlled
              single-mechanism ablations, of which this was the only one
              that removed the effect; see the investigation doc for the
              full ablation table). This is a sequencing correction, not a
              parameter recalibration — no calibrated weight, threshold, or
              equation coefficient was changed. One direct consequence:
              trigger-driven trade-edge disruptions and price shocks (fired
              inside stc_engine.step()) now take effect starting the trade
              resolution of the FOLLOWING step rather than the same step —
              the same one-step propagation lag already accepted by the
              BUG-013 fix above, for the same reason (avoiding an
              incoherent same-step "undo" of trade that already executed).
          3. Price update (supply-demand + energy cost-push)
          4. Metrics recorded
        """
        agents = list(self.agent_map.values())

        # ── Phase 3: energy module (no-op until Phase 3) ──────────────────────
        if self.energy_module is not None:
            self.energy_module.step(self)

        # ── PHASE C (this session): continuous climate drivers, if configured ──
        # None by default (see __init__) -- no-op for every existing scenario.
        if self.climate_driver is not None:
            self.climate_driver.step(self)

        # ── PHASE C (this session): soil quality driver, if configured ─────────
        # Runs AFTER agent production (needs annual_production from the
        # PREVIOUS step to compute this step's intensity proxy) -- so this
        # call is placed after the agent-step loop below, not here. See the
        # second insertion point, after "# --- 1. Agent steps".

        # ── 1. Agent steps (production, pre-trade σ, export policy, pop, capital) ─
        for agent in agents:
            agent.step()

        # ── PHASE C (this session): soil quality driver, if configured ─────────
        # Placed here (after production, before trade) so this step's
        # intensity proxy uses this step's just-computed annual_production.
        if self.soil_driver is not None:
            self.soil_driver.step(self)

        # ── PHASE C increment 2 (this session): fertilizer and water drivers ───
        # Same placement rationale as soil_driver (need this step's
        # annual_production for the depletion/intensity proxy).
        if self.fertilizer_driver is not None:
            self.fertilizer_driver.step(self)
        if self.water_driver is not None:
            self.water_driver.step(self)

        # ── 2. Trade ──────────────────────────────────────────────────────────
        pre  = {n: a.food_imperish for n, a in self.agent_map.items()}
        execute_trade_step(self)
        post = {n: a.food_imperish for n, a in self.agent_map.items()}

        trade_volume = sum(
            max(0.0, post[n] - pre[n]) for n in self.agent_map
        )
        self._last_trade_volume = trade_volume

        # ── 2b. BUG-013 FIX: recompute σ_i post-trade ─────────────────────────
        # This updates agent.food_security (and agent.undernourished) to
        # reflect the food actually received/sent this step. export_fraction
        # is intentionally NOT re-run here: re-running update_export_policy()
        # after trade has already executed using THIS step's export_fraction
        # would be incoherent (you cannot un-export food already sent). The
        # corrected, post-trade σ instead feeds into FS_index below and into
        # next step's export_policy via agent.step() at the top of the next
        # tick — closing the loop with a one-step lag rather than leaving it
        # permanently open.
        for agent in agents:
            agent.compute_food_security()
            agent._compute_FS_index()  # BUG-013 FIX: keep FS_index consistent
                                        # with post-trade σ (EQUATIONS.md §6
                                        # formula depends on food_security)

        # ── Phase 4: STC engine (no-op until Phase 4) ─────────────────────────
        # SESSION FIX (Phase 2.5): moved here, after trade + the post-trade
        # recompute directly above, so _accumulate_stress()/_detect_overload()
        # act on each node's actual, trade-corrected food security rather
        # than a pre-trade snapshot. See docstring above for full rationale.
        if self.stc_engine is not None:
            self.stc_engine.step(self)

        # ── 3. Price update ────────────────────────────────────────────────────
        total_supply = sum(a.annual_production for a in agents)
        total_demand = sum(a.caloric_demand()  for a in agents)

        # Phase 3 energy stress hook (0 until Phase 3)
        energy_stress_global = float(np.mean([
            getattr(a, "energy_stress_index", 0.0) for a in agents
        ]))

        self.price_system.update(total_supply, total_demand, energy_stress_global)

        # ── Phase 5: political economy (after trade, before metrics) ──────────
        if self.trader_module is not None:
            self.trader_module.step(self)

        # ── 4. Metrics ─────────────────────────────────────────────────────────
        self.metrics.record(self, trade_volume)

        # SESSION FIX (Phase 2, this session): removed the redundant
        # `self.steps += 1` that used to be here. Mesa's base `Model` class
        # (ALL 3.x releases, confirmed by reading mesa/model.py directly:
        # `Model.__init__` reassigns `self.step = self._wrapped_step`, and
        # `_wrapped_step` itself does `self.steps += 1` BEFORE calling the
        # user-defined step body) already increments `self.steps` exactly
        # once per external `model.step()` call. This explicit second
        # increment caused `self.steps` to advance by 2 per call whenever
        # this code runs under any Mesa 3.x install (which this codebase
        # requires anyway, since `agent.py`'s `CountryAgent.__init__` uses
        # the Mesa-3-only single-argument `Agent(model)` constructor --
        # there is no Mesa version where the old double-increment AND the
        # Agent constructor both work correctly). This silently desynced
        # every trigger's `step` field from the calendar-year timing
        # documented in every trigger's own docstring throughout
        # stc_engine.py, and silently changed the effective RC_DURATION_STEPS
        # / warm-up windows measured in calls-to-step(), not `self.steps`
        # units. Fixed by deletion, not by adjusting trigger step numbers,
        # so every existing trigger's documented "step N = year Y" comment
        # is now literally true again.

    def run(self, n_steps: int, verbose: bool = True):
        """Run the model for n_steps ticks, printing progress."""
        for i in range(n_steps):
            self.step()
            if verbose and (i == 0 or (i + 1) % 5 == 0):
                m = self.metrics._records[-1]
                print(
                    f"  Step {self.steps:>3} | "
                    f"GFS={m['GFS']:.3f} | "
                    f"U={m['U_undernourished']:.3f} | "
                    f"PAR={m['PAR_millions']:.1f}M | "
                    f"Price={m['price_index']:.3f} | "
                    f"EB={m['EB_export_ban_rate']:.2f}"
                )

    # =========================================================================
    # State snapshot (for retrodiction / scenario comparison)
    # =========================================================================

    def node_dataframe(self) -> pd.DataFrame:
        """Return a DataFrame of current per-node state."""
        return self.metrics.node_snapshot(self)

    def metrics_dataframe(self) -> pd.DataFrame:
        """Return all recorded step metrics."""
        return self.metrics.to_dataframe()

    def summary(self) -> dict:
        """Quick run summary."""
        return {
            "scenario":  self._scenario_name,
            "steps_run": self.steps,
            **self.metrics.summary(),
        }

    # =========================================================================
    # Shock / intervention interface (used by scenarios.py and stc_engine.py)
    # =========================================================================

    def apply_climate_shock(
        self,
        scope: float = 0.3,
        severity: float = 0.5,
        mode: str = "drought",
        seed_node: str = None,
    ):
        """
        Inject a climate stress into a subset of agents.
        scope    : fraction of nodes affected
        severity : stress index value injected [0,1]
        mode     : 'drought' | 'heatwave' | 'flood' | 'compound'
        seed_node: epicentre node name (if None, random selection)
        """
        agents = list(self.agent_map.values())
        n_affected = max(1, int(scope * len(agents)))

        if seed_node and seed_node in self.agent_map:
            # BFS ordering from epicentre
            try:
                order = list(nx.bfs_tree(self.network, seed_node).nodes())
                affected = [self.agent_map[n] for n in order[:n_affected]
                            if n in self.agent_map]
            except Exception:
                affected = list(self.rng.choice(agents, size=n_affected, replace=False))
        else:
            indices = self.rng.choice(len(agents), size=n_affected, replace=False)
            affected = [agents[i] for i in indices]

        for agent in affected:
            if mode in ("drought", "compound"):
                agent.drought_index  = min(1.0, agent.drought_index  + severity)
            if mode in ("heatwave", "compound"):
                agent.heatwave_index = min(1.0, agent.heatwave_index + severity)
            if mode in ("flood", "compound"):
                agent.flood_index    = min(1.0, agent.flood_index    + severity)

        print(
            f"[Shock] Climate '{mode}' severity={severity:.2f} "
            f"applied to {len(affected)} nodes"
        )

    def apply_price_shock(self, factor: float):
        """Directly spike the global food price (proximate trigger hook)."""
        self.price_system.shock(factor)
        print(f"[Shock] Price shock ×{factor:.2f} → p={self.price_system.price:.3f}")

    def disable_trade_edges(self, node: str):
        """Disable all outgoing edges from a node (export ban / conflict)."""
        disabled = 0
        for src, dst in list(self.network.out_edges(node)):
            self.network[src][dst]["active"] = False
            disabled += 1
        print(f"[Shock] Disabled {disabled} outgoing edges from '{node}'")

    def __repr__(self):
        return (
            f"FoodEnergyModel(scenario={self._scenario_name}, "
            f"step={self.steps}, nodes={len(self.agent_map)})"
        )
