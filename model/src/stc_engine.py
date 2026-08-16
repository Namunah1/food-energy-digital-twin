"""
stc_engine.py
-------------
Stress-Trigger-Crisis (STC) Engine.

Framework : Homer-Dixon et al. (2015) §3–§4 + Gambhir et al. (2025) Fig.1/2
Phase     : 4 — Replace flat shock schedule with genuine SS/LFBB/RC architecture

This engine implements the two-stage architecture from Homer-Dixon Fig.1:

  STAGE 1 (SS + LFBB):
    Slow processes within largely discrete systems.
    Per-node food stress (FS_index) and energy stress (ES_index) accumulate
    over time. When a stress index crosses the overload threshold, the system
    is in a pre-critical state (the long-fuse has been lit).

  STAGE 2 (SS + RC):
    Proximate triggers push overloaded systems into discrete crises.
    Crises cascade outward through the trade network (RC mechanism).
    The export-ban contagion in trade.py is the primary RC channel;
    this engine adds explicit cross-system cascade logic.

Deep causes (Homer-Dixon §3) tracked as model-level diagnostics:
  D1. Scale index    : Σ(K_i × E_fuel_i) / baseline
  D2. Connectivity   : active trade edge fraction
  D3. Homogeneity    : HHI of production technology mix

Trigger registry:
  Each trigger is a dict:
    {
      name       : str,
      step       : int,           # when it fires (model.steps == step)
      type       : str,           # 'climate' | 'geopolitical' | 'speculative' | 'pandemic'
      scope      : float,         # fraction of nodes affected
      severity   : float,         # 0–1 stress bump to FS/ES/price
      food_shock : float,         # price shock factor (1.0 = none)
      energy_shock: float,        # energy price spike factor
      target_node: str | None,    # epicentre node (None = random)
    }

Coping capacity (CC_index, §5):
  CC_i = clip(
    technology_i × capital_factor × (1 - political_risk_i)
    × reserve_factor × (1 - climate_vuln_i)
  , 0.05, 1.0)

Overload condition (LFBB, §4):
  overload_food_i   = FS_index_i / CC_i > 1.0
  overload_energy_i = ES_index_i > 0.70  (set by energy.py)

Ramifying cascade (RC, §4):
  On overload, increase contagion probability on adjacent edges for N_RC steps.
"""

import numpy as np
import networkx as nx
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from model import FoodEnergyModel

# ── Overload thresholds ───────────────────────────────────────────────────────
FOOD_OVERLOAD_RATIO    = 1.0    # FS_index / CC_index > 1.0 → food overload (LFBB)

# ── Stress accumulation ────────────────────────────────────────────────────────
FS_ACCUMULATION_RATE   = 0.05   # FS_index drifts up by 5% of (1−σ) each step
FS_DECAY_RATE          = 0.10   # recovery rate when σ > σ_safe

# ── Coping capacity weights ────────────────────────────────────────────────────
CC_TECH_WEIGHT     = 0.4749  # BUG-016/017 FIX: ML-calibrated from corrected
CC_CAPITAL_WEIGHT  = 0.3002  # resilience-based CC target (reserve adequacy +
CC_POLRISK_WEIGHT  = 0.1066  # trade diversification + govt capacity), via
CC_RESERVE_WEIGHT  = 0.0031  # ml_calibration.calibrate_cc(). Previously the
CC_CLIMVULN_WEIGHT = 0.1152  # runtime model used hand-tuned defaults (0.30,
                              # 0.30, 0.20, 0.10, 0.10) that were NEVER
                              # actually replaced by the Phase 6 calibration
                              # output, despite the paper's framing implying
                              # they were. See data/processed/
                              # cc_calibration_summary.json for the full
                              # calibration run (val R²=0.876, val MAE=0.028).
                              # Note CC_RESERVE_WEIGHT dropping to ~0 reflects
                              # that reserve_factor (computed from agent.reserves)
                              # had near-zero marginal predictive value once
                              # technology and capital were already in the
                              # model — a genuine calibration finding, not
                              # an error.

# ── Ramifying cascade ──────────────────────────────────────────────────────────
RC_CONTAGION_BOOST    = 0.25   # added to BAN_CONTAGION_RATE during cascade
RC_DURATION_STEPS     = 4      # cascade window (steps)
RC_PRICE_AMPLIFICATION = 0.021 # BUG-009 FIX (audit Fix #12, HIGH): calibrated
                                # from real FAO FPI surge data rather than
                                # asserted. 2008 crisis: FPI rose from ~94.6
                                # (2007) to ~117.7 (2008 annual avg) = ~24%
                                # increase. With ~12 nodes typically
                                # overloaded at cascade onset (the model's own
                                # structural finding), target cumulative RC
                                # factor ≈1.25 implies per-node amplification
                                # (1.25-1)/12 ≈ 0.021. The previous value
                                # (0.10) produced a ×2.2 single-step shock —
                                # an order of magnitude beyond any real annual
                                # FPI move and the cause of post-fix price
                                # ceiling saturation (4.8+) once the price-
                                # floor degeneracy (BUG-006) was independently
                                # fixed and could no longer mask it.

# ── Homer-Dixon deep-cause tracking ───────────────────────────────────────────
SCALE_GROWTH_RATE = 0.02     # global economic throughput grows 2%/yr
HOMOG_DRIFT_RATE  = 0.005    # technology homogeneity creeps up each step


class STCEngine:
    """
    Stress-Trigger-Crisis engine implementing the Homer-Dixon (2015) framework.

    Instantiate and attach to model:
        model.stc_engine = STCEngine(triggers=[...], ss_mode='multiplicative')

    Parameters
    ----------
    triggers   : list of trigger dicts (see module docstring)
    ss_mode    : 'multiplicative' (AND logic) | 'additive' (OR logic)
                 Controls how multiple simultaneous stresses combine (§4 SS)
    """

    def __init__(
        self,
        triggers: list = None,
        ss_mode: str = "multiplicative",
    ):
        self.triggers = triggers or []
        self.ss_mode  = ss_mode

        # ── State ─────────────────────────────────────────────────────────────
        self._fired_triggers: set = set()
        self._cascade_active_until: int = -1  # step until which RC boost is on
        self._n_overloaded_food_last: int = 0

        # ── Deep-cause accumulators ────────────────────────────────────────────
        self._scale_index       = 1.0
        self._connectivity_prev = 1.0
        self._homog_index       = 0.0

        # ── Stress history for LFBB timing analysis ────────────────────────────
        self.fs_history:  list[dict] = []   # {step: n_overloaded_food}
        self.es_history:  list[dict] = []   # {step: n_overloaded_energy}
        self.crisis_log:  list[dict] = []   # crisis events

    # =========================================================================
    # Main step (called by model.step() after agent steps, before trade)
    # =========================================================================

    def step(self, model: "FoodEnergyModel"):
        """
        STC engine lifecycle each tick:
          1. Update deep causes (scale, connectivity, homogeneity)
          2. Accumulate per-node FS_index and CC_index (LFBB slow build-up)
          3. Determine SS combination (multiplicative or additive)
          4. Fire any pending triggers (proximate trigger injection)
          5. Detect LFBB overload and log crises
          6. Apply RC cascade boost to trade network
        """
        t = model.steps

        # ── 1. Deep causes ─────────────────────────────────────────────────────
        self._update_deep_causes(model)

        # ── 2. Stress accumulation and CC_index ────────────────────────────────
        self._accumulate_stress(model)

        # ── 3. Simultaneous stresses combination ──────────────────────────────
        self._combine_simultaneous_stresses(model)

        # ── 4. Trigger injection ───────────────────────────────────────────────
        for trigger in self.triggers:
            if trigger["step"] == t and trigger["name"] not in self._fired_triggers:
                self._fire_trigger(model, trigger)
                self._fired_triggers.add(trigger["name"])

        # ── 5. Overload detection (LFBB) ───────────────────────────────────────
        n_food_overloaded = self._detect_overload(model, t)

        # ── 6. RC cascade boost ────────────────────────────────────────────────
        # BUG-007 FIX: warm-up reduced from t<2 to t<1 (1-step numerical
        # settle margin only) now that FS_index/CC_index start from
        # equilibrium proxies rather than zero — see agent.py
        # _init_equilibrium_stress() and _detect_overload() above.
        if t < 1:
            model._cascade_active    = False
            model._rc_contagion_boost = 0.0
            self._n_overloaded_food_last = n_food_overloaded
            return

        if n_food_overloaded > self._n_overloaded_food_last:
            # New nodes just tipped into overload → activate RC window
            self._cascade_active_until = t + RC_DURATION_STEPS
            self._apply_rc_price_amplification(model, n_food_overloaded)
            print(
                f"[STC] ⚡ RC cascade activated at step {t} | "
                f"food_overloaded={n_food_overloaded} | "
                f"active until t={self._cascade_active_until}"
            )

        self._n_overloaded_food_last = n_food_overloaded

        # Set cascade flag on model (read by trade.py for contagion boost)
        model._cascade_active = (t <= self._cascade_active_until)
        model._rc_contagion_boost = RC_CONTAGION_BOOST if model._cascade_active else 0.0

        # ── Record history ─────────────────────────────────────────────────────
        self.fs_history.append({
            "step": t,
            "n_overloaded_food":   n_food_overloaded,
            "n_overloaded_energy": sum(
                1 for a in model.agent_map.values()
                if getattr(a, "overload_energy", False)
            ),
            "mean_FS":  float(np.mean([a.FS_index for a in model.agent_map.values()])),
            "mean_CC":  float(np.mean([a.CC_index for a in model.agent_map.values()])),
            "scale":    round(self._scale_index, 4),
            "homog":    round(self._homog_index, 4),
        })

    # =========================================================================
    # Deep causes (Homer-Dixon §3)
    # =========================================================================

    def _update_deep_causes(self, model: "FoodEnergyModel"):
        """
        D1. Scale  : rising global throughput (economy × energy)
        D2. Connect: trade network density (computed per step)
        D3. Homog  : technology homogeneity (HHI of T_i)
        """
        # Scale grows each step (GDP/energy throughput expansion)
        self._scale_index *= (1.0 + SCALE_GROWTH_RATE)

        # Connectivity from trade network
        G = model.network
        active = sum(1 for _, _, d in G.edges(data=True) if d.get("active", True))
        max_e  = max(G.number_of_nodes() * (G.number_of_nodes() - 1), 1)
        self._connectivity_prev = active / max_e

        # Technology homogeneity: HHI of T_i values
        T_vals = [a.technology for a in model.agent_map.values()]
        T_total = sum(T_vals)
        if T_total > 0:
            shares = [t / T_total for t in T_vals]
            self._homog_index = float(np.clip(
                sum(s ** 2 for s in shares) + HOMOG_DRIFT_RATE,
                0.0, 1.0
            ))

    # =========================================================================
    # Stress accumulation (LFBB — slow build-up)
    # =========================================================================

    def _accumulate_stress(self, model: "FoodEnergyModel"):
        """
        Per-node stress (FS_index) accumulates slowly toward overload.

        FS_index_i(t+1) =
            FS_index_i(t) + FS_ACCUMULATION_RATE × max(0, 1 − σ_i)
            − FS_DECAY_RATE × max(0, σ_i − σ_safe_i)

        CC_index_i(t) = composite coping capacity (§5)

        This is the "long fuse" burning.
        """
        for agent in model.agent_map.values():
            sigma  = agent.food_security
            sigma_safe = agent.sigma_safe_i

            # Stress accumulation (long fuse burning)
            stress_push = FS_ACCUMULATION_RATE * max(0.0, 1.0 - sigma)

            # Stress recovery (coping capacity working)
            stress_pull = FS_DECAY_RATE * max(0.0, sigma - sigma_safe)

            # Energy stress contribution to food stress (intersystemic)
            es_contribution = 0.20 * getattr(agent, "energy_stress_index", 0.0)

            # Biophysical stress from climate.
            # PHASE C (this session): when model.climate_single_channel_mode
            # is True, this term is zeroed -- production already transmits
            # the climate hit into FS_index via stress_push (through σ),
            # so this additive term was pure double-counting of the SAME
            # climate_modifier value with no new information (see
            # PHASE2_5B_CAUSAL_DECOMPOSITION.md §7/§9). Default (False)
            # preserves the original formula exactly.
            if getattr(model, "climate_single_channel_mode", False):
                climate_stress = 0.0
            else:
                climate_stress = 0.15 * (1.0 - agent.climate_modifier)

            # FS_index update (EQUATIONS.md §6)
            agent.FS_index = float(np.clip(
                agent.FS_index + stress_push + es_contribution + climate_stress - stress_pull,
                0.0, 2.0  # allow >1 for extreme stress states
            ))

            # Coping capacity (§5)
            cap_factor = min(1.0, agent.capital / 1000.0)
            reserve_factor = min(
                1.0,
                agent.reserves / max(agent._caloric_demand_yr * 0.15, 1.0)
            )
            tech_norm = min(1.0, agent.technology / 2.0)

            agent.CC_index = float(np.clip(
                CC_TECH_WEIGHT     * tech_norm
                + CC_CAPITAL_WEIGHT  * cap_factor
                - CC_POLRISK_WEIGHT  * agent.political_risk
                + CC_RESERVE_WEIGHT  * reserve_factor
                - CC_CLIMVULN_WEIGHT * agent.climate_vuln,
                0.05, 1.0
            ))

    # =========================================================================
    # Simultaneous stresses combination (Homer-Dixon §4, SS archetype)
    # =========================================================================

    def _combine_simultaneous_stresses(self, model: "FoodEnergyModel"):
        """
        SS archetype: multiple stresses combine within each system.

        Multiplicative (AND logic): total_stress = FS × ES
            → both stresses must be present for overload
        Additive (OR logic): total_stress = 0.5×FS + 0.5×ES
            → either stress alone can trigger overload

        The combined stress ratio FS_combined / CC is used for overload detection.
        """
        for agent in model.agent_map.values():
            es = getattr(agent, "energy_stress_index", 0.0)
            fs = agent.FS_index

            if self.ss_mode == "multiplicative":
                # Synergistic (AND): if both are elevated, combined > either alone
                combined = fs * (1.0 + es)
            else:
                # Additive (OR): either stress sufficient
                combined = fs + 0.5 * es

            # Store combined stress for overload test
            agent._combined_stress = combined

    # =========================================================================
    # Trigger injection (proximate trigger → Stage 2 transition)
    # =========================================================================

    def _fire_trigger(self, model: "FoodEnergyModel", trigger: dict):
        """
        Inject a proximate trigger event.
        The trigger pushes already-stressed systems into discrete crises (Stage 2).
        """
        name        = trigger["name"]
        t_type      = trigger.get("type", "climate")
        scope       = trigger.get("scope",       0.30)
        severity    = trigger.get("severity",    0.40)
        food_shock  = trigger.get("food_shock",  1.0)
        energy_shock = trigger.get("energy_shock", 1.0)
        target_node = trigger.get("target_node", None)

        print(
            f"[STC] 🔥 TRIGGER '{name}' fired at step {model.steps} | "
            f"type={t_type} | scope={scope:.0%} | severity={severity:.2f}"
        )

        # ── Climate trigger ────────────────────────────────────────────────────
        if t_type == "climate":
            model.apply_climate_shock(
                scope=scope, severity=severity,
                mode="drought", seed_node=target_node
            )

        # ── Geopolitical trigger (trade disruption + price spike) ──────────────
        elif t_type == "geopolitical":
            if target_node and target_node in model.agent_map:
                model.disable_trade_edges(target_node)
            if food_shock > 1.0:
                model.apply_price_shock(food_shock)
            if energy_shock > 1.0 and model.energy_module is not None:
                model.energy_module.apply_energy_shock(
                    model, scope=scope, severity=severity, mode="price_spike"
                )
            model.sanction_penalty = max(model.sanction_penalty, 0.20)

        # ── Speculative trigger (price spike only) ─────────────────────────────
        elif t_type == "speculative":
            if food_shock > 1.0:
                model.apply_price_shock(food_shock)

        # ── Pandemic trigger (logistics disruption) ────────────────────────────
        elif t_type == "pandemic":
            agents = list(model.agent_map.values())
            n_aff  = max(1, int(scope * len(agents)))
            indices = model.rng.choice(len(agents), size=n_aff, replace=False)
            for i in indices:
                agents[i].logistics_disruption = min(
                    1.0, agents[i].logistics_disruption + severity
                )

        # ── Log ───────────────────────────────────────────────────────────────
        self.crisis_log.append({
            "step":         model.steps,
            "trigger_name": name,
            "type":         t_type,
            "food_shock":   food_shock,
            "energy_shock": energy_shock,
        })

    # =========================================================================
    # LFBB overload detection
    # =========================================================================

    def _detect_overload(self, model: "FoodEnergyModel", t: int) -> int:
        """
        Overload condition (Homer-Dixon §4):
          overload_food_i = (FS_index_i + combined_stress_i) / CC_i > 1.0

        BUG-007 FIX: previously required a 3-step warm-up before any overload
        could fire, motivated only by the fact that FS_index started at 0 for
        all nodes (an unmotivated initialisation, not a theoretical
        requirement — see agent.py _init_equilibrium_stress()). Now that
        FS_index is initialised from each node's equilibrium proxy
        (undernourishment_baseline_pct/100), a 1-step numerical safety
        margin is kept only to let CC_index settle from its first
        _accumulate_stress() call — not to artificially delay genuine
        structural overload.
        """
        n_overloaded = 0
        min_steps_for_overload = 1   # BUG-007 FIX: was 3 (unmotivated); now a
                                      # 1-step numerical settle margin only

        for agent in model.agent_map.values():
            combined   = getattr(agent, "_combined_stress", agent.FS_index)
            cc         = max(agent.CC_index, 0.05)
            ratio      = combined / cc

            was_overloaded = agent.overload_food

            # Only allow overload after warm-up period AND with real accumulated stress
            if t >= min_steps_for_overload:
                agent.overload_food = (ratio > FOOD_OVERLOAD_RATIO)
            else:
                agent.overload_food = False   # suppress during warm-up

            if agent.overload_food:
                n_overloaded += 1

            # Log new overload events (only after warm-up)
            if agent.overload_food and not was_overloaded and t >= min_steps_for_overload:
                self.crisis_log.append({
                    "step":     t,
                    "type":     "LFBB_overload_food",
                    "node":     agent.name,
                    "ratio":    round(ratio, 3),
                    "FS_index": round(agent.FS_index, 3),
                    "CC_index": round(cc, 3),
                    "sigma":    round(agent.food_security, 3),
                })
                print(
                    f"[STC] ⚠ LFBB overload: {agent.name} | "
                    f"FS/CC={ratio:.2f} | σ={agent.food_security:.3f}"
                )

        return n_overloaded

    # =========================================================================
    # RC price amplification
    # =========================================================================

    def _apply_rc_price_amplification(
        self, model: "FoodEnergyModel", n_overloaded: int
    ):
        """
        Stage 2 RC mechanism: each new overloaded node adds a price
        amplification shock (cascades through tightly coupled network).
        RC_PRICE_AMPLIFICATION × n_overloaded
        """
        factor = 1.0 + RC_PRICE_AMPLIFICATION * n_overloaded
        if factor > 1.0:
            model.price_system.shock(factor)
            print(
                f"[STC] RC price amplification ×{factor:.3f} "
                f"({n_overloaded} new overloaded nodes)"
            )

    # =========================================================================
    # Diagnostics and output
    # =========================================================================

    def summary(self) -> dict:
        """Summary of the STC engine state across the run."""
        if not self.fs_history:
            return {}
        max_food_overload   = max(r["n_overloaded_food"]   for r in self.fs_history)
        max_energy_overload = max(r["n_overloaded_energy"] for r in self.fs_history)
        n_crises = sum(
            1 for e in self.crisis_log if e.get("type") == "LFBB_overload_food"
        )
        n_triggers_fired = len(self._fired_triggers)
        return {
            "ss_mode":              self.ss_mode,
            "n_triggers_registered":len(self.triggers),
            "n_triggers_fired":     n_triggers_fired,
            "max_food_overloaded":  max_food_overload,
            "max_energy_overloaded":max_energy_overload,
            "n_LFBB_overload_events":n_crises,
            "n_crisis_log_entries": len(self.crisis_log),
            "scale_index_final":    round(self._scale_index, 4),
            "homog_index_final":    round(self._homog_index, 4),
            "connectivity_final":   round(self._connectivity_prev, 4),
        }

    def crisis_dataframe(self):
        """Return crisis log as a DataFrame."""
        import pandas as pd
        return pd.DataFrame(self.crisis_log)

    def stress_history_dataframe(self):
        """Return per-step stress history as a DataFrame."""
        import pandas as pd
        return pd.DataFrame(self.fs_history)


# ============================================================================
# Pre-built trigger sets for Phase 8 retrodiction and Phase 9 scenarios
# ============================================================================

def triggers_2008_food_energy(step_offset: int = 0):
    """
    Homer-Dixon Fig.3: 2008 food-energy crisis triggers.
    Stage 1 stress builds for steps 0-14 (slow processes).
    Proximate trigger fires at step 15 (Australian drought + speculation).

    BUG-008 FIX (audit Fix #1): step_offset lets callers reposition these
    triggers when init_year is set to a temporally-coherent pre-crisis year
    (e.g. init_year=2000, step_offset=8 → trigger fires at simulated step 15
    which corresponds to calendar year 2000+15=2015... so instead callers
    should choose init_year such that init_year + 15 == 2008, i.e.
    init_year=1993). Since the data panel only covers 2000-2023, the
    practical resolution (used in run_phase8 below) is to SHORTEN the
    stage-1 build-up window via step_offset rather than push init_year
    before the data coverage starts: init_year=2000, step_offset=-7 shifts
    the trigger from step 15 to step 8, landing on calendar year 2008 while
    keeping initial conditions temporally coherent (2000-era population,
    capital, technology — not 2022-era).
    """
    return [
        {
            "name":        "2008_speculative_spike",
            "step":        15 + step_offset,
            "type":        "speculative",
            "scope":       0.60,
            "severity":    0.45,
            "food_shock":  1.65,   # ~65% food price surge (2007-2008)
            "energy_shock":1.50,
            "target_node": None,
        },
        {
            "name":        "2008_australian_drought",
            "step":        15 + step_offset,
            "type":        "climate",
            "scope":       0.20,
            # FAO-EMPIRICAL SEVERITY (replaces previous hardcoded 0.70):
            # Australia chi_shock 2006 = 0.4834 (chi_i=0.5166, i.e. 48.3% cereal
            # yield loss vs 2005 baseline). Source: FAO Crops & Livestock Production
            # data as extracted in data/raw/fao/historical_food_production.csv and
            # data/raw/fao/chi_shock_summary.csv. Triangulated against Crisis_Episode_
            # Anchors: Australian wheat 2006 ~10.8Mt vs ~25Mt prior year (-57%), which
            # equals chi_shock ≈ 0.48. Using 0.48 (average of 2006/2007 shocks to
            # capture the multi-year Millennium Drought effect that accumulated stress).
            "severity":    0.48,
            "food_shock":  1.0,
            "energy_shock":1.0,
            "target_node": "Australia",
        },
        {
            "name":        "2008_export_bans_cascade",
            "step":        17 + step_offset,
            "type":        "geopolitical",
            "scope":       0.30,
            "severity":    0.30,
            "food_shock":  1.20,
            "energy_shock":1.0,
            "target_node": None,
        },
    ]


def triggers_2022_ukraine(step_offset: int = 0):
    """
    Gambhir Fig.2: 2022 food-energy crisis triggers.
    Stage 1 stress builds for steps 0-10 (post-COVID, weather extremes).
    Russia invasion fires at step 10 (proximate trigger).

    BUG-008 FIX (audit Fix #1): step_offset repositions these triggers when
    init_year is set to a temporally-coherent pre-crisis year. With
    init_year=2018 and step_offset=-6, the trigger fires at step 4
    (calendar year 2022), shortening the stage-1 build window from the
    original arbitrary 10 steps while keeping initial conditions anchored
    to real 2018 population/capital/technology rather than 2022 values.
    """
    return [
        {
            "name":        "2022_russia_invasion",
            "step":        10 + step_offset,
            "type":        "geopolitical",
            "scope":       0.45,
            "severity":    0.55,
            "food_shock":  1.45,   # ~45% food price surge
            "energy_shock":1.80,   # ~80% gas price surge
            "target_node": "Russia",
        },
        {
            "name":        "2022_ukraine_block",
            "step":        10 + step_offset,
            "type":        "geopolitical",
            "scope":       0.0,
            # FAO-EMPIRICAL SEVERITY (replaces previous hardcoded 0.0):
            # Ukraine 2022 cereal chi_shock = 0.023 (chi_i=0.977 vs 2021 baseline).
            # However, the export disruption was larger than yield alone: Crisis_Episode_
            # Anchors documents -30% total grain+oilseed harvest AND Black Sea export
            # blockage (90% of exports via Black Sea pre-war). The yield-only chi_shock
            # (0.023) understates the export volume shock. Calibrating to the export-
            # volume shock: 0.30 (the -30% documented in Ukrainian Agri Council data).
            # Source: data/raw/fao/chi_shock_summary.csv + Crisis_Episode_Anchors sheet.
            "severity":    0.30,
            "food_shock":  1.0,
            "energy_shock":1.0,
            "target_node": "Ukraine",
        },
        {
            "name":        "2022_global_inflation_cascade",
            "step":        13 + step_offset,
            "type":        "speculative",
            "scope":       0.50,
            "severity":    0.30,
            "food_shock":  1.15,
            "energy_shock":1.0,
            "target_node": None,
        },
    ]


def triggers_2004_niger_sahel(step_offset: int = 0):
    """
    2004-2005 Niger/Sahel food crisis.

    NOTE: originally scoped as a "2003" episode, but real FAO Crops
    Production data (extracted and cross-checked this session) does not
    support a 2003 yield shock -- Niger, Mali, and Chad all show flat or
    *rising* cereal yields in 2003 relative to a 2000-2002 baseline. The
    real, well-documented shock is 2004: Niger cereal yield fell 19.25%
    relative to its 2002-2003 level (0.4229 t/ha -> 0.3415 t/ha), driven by
    drought compounded by a major desert locust invasion of West Africa.
    2005 yield actually recovered (chi_shock=-0.032) -- the 2005 famine
    phase was a stock-depletion crisis following the 2004 harvest failure,
    not a second production shock. This makes it a genuinely different
    type of crisis than 2008/2022 to retrodict: a *regional* supply-chain
    and reserve-depletion failure, not a global price shock.

    IMPORTANT SCORING NOTE: unlike 2008/2022, this crisis did NOT produce a
    global FAO FPI spike (real 2004 FPI=0.656, 2005=0.674, both well below
    the 2014-2016=1.0 baseline -- this was a regional, not global, event).
    Do not score this episode against global max_price_index the way 2008/
    2022 are scored; validate against West Africa (ECOWAS) regional PAR/
    overload metrics instead. See retrodiction.py's episode scoring for
    the corresponding adjustment.

    init_year=2002 (near-term pre-crisis baseline, not 2000 -- yields swing
    enough year-to-year in this region that a 4-year-old baseline understates
    the actual shock magnitude).

    Source: FAO Crops Production data (Production_Crops_Livestock_E_All_
    Data.csv), Cereals primary, Yield element, Niger/Mali/Chad, extracted
    and verified this session. Real FPI: FAO Food Price Index historical
    table (en.wikipedia.org/wiki/FAO_Food_Price_Index, cross-checked
    against this model's own REAL_FPI_2008 constant: 117.5/99.97=1.1753
    vs. the existing 1.177 -- matches within rounding, confirming the
    normalization method).
    """
    return [
        {
            "name":        "2004_niger_drought_locust",
            "step":        2 + step_offset,   # year 2004 (init_year=2002 + 2)
            "type":        "climate",
            "scope":       0.15,   # West Africa bloc is 15 countries; shock is
                                    # concentrated in the Sahel subset (Niger,
                                    # Mali, Chad, Burkina Faso), not uniform
            # FAO-EMPIRICAL SEVERITY: Niger cereal chi_shock 2004 (vs 2002-03
            # baseline) = 0.1925. Real crisis reporting (FEWS NET, OCHA)
            # describes this as one of the most severe Sahel production
            # failures on record for the period, compounded by the locust
            # invasion's non-yield losses (stored grain, pasture) not
            # captured by yield data alone -- calibrating slightly above the
            # raw yield chi_shock to reflect this, consistent with how the
            # 2022 Ukraine trigger calibrates to export-volume shock rather
            # than yield-only chi_shock when documented non-yield losses exist.
            "severity":    0.25,
            "food_shock":  1.20,
            "energy_shock":1.0,
            "target_node": "West Africa (ECOWAS)",
        },
        {
            "name":        "2005_niger_stock_depletion",
            "step":        3 + step_offset,   # year 2005 (init_year=2002 + 3)
            "type":        "speculative",       # models the stock-depletion/
                                                  # price-spike dynamic, not a
                                                  # fresh production shock
                                                  # (2005 yield recovered)
            "scope":       0.10,
            "severity":    0.20,
            "food_shock":  1.10,
            "energy_shock":1.0,
            "target_node": "West Africa (ECOWAS)",
        },
    ]


def triggers_2010_russia_drought(step_offset: int = 0):
    """
    2010-11 Russia drought + export ban + Arab Spring price surge.

    init_year=2008 (matches the existing 2008 episode's endpoint, giving a
    temporally coherent 2-year build window with real 2008-2010 data).

    Source: FAO Crops Production data, Cereals primary, Yield, Russian
    Federation, extracted this session. Real chi_shock 2010 (vs 2008
    baseline) = 0.2281 -- matches well-documented accounts of Russia's 2010
    heatwave/drought causing a ~25-30% grain harvest decline and the
    resulting August 2010 export ban. Real FPI: 2010=1.067, 2011=1.319
    (FAO historical table, cross-checked against this model's own
    REAL_FPI_2008 constant -- see triggers_2004_niger_sahel docstring for
    the verification method).
    """
    return [
        {
            "name":        "2010_russia_drought",
            "step":        2 + step_offset,   # year 2010 (init_year=2008 + 2)
            "type":        "climate",
            "scope":       0.35,
            # FAO-EMPIRICAL SEVERITY: real cereal chi_shock = 0.2281
            "severity":    0.23,
            "food_shock":  1.20,
            "energy_shock":1.0,
            "target_node": "Russia",
        },
        {
            "name":        "2010_russia_export_ban",
            "step":        2 + step_offset,   # same year (2010) as the drought
            "type":        "geopolitical",
            "scope":       0.0,
            # Russia's August 2010 export ban covered effectively all wheat
            # exports for the remainder of the season -- a near-total
            # export-volume shock, distinct from (and larger than) the
            # underlying yield shock, same pattern as 2022 Ukraine.
            "severity":    0.80,
            "food_shock":  1.0,
            "energy_shock":1.0,
            "target_node": "Russia",
        },
        {
            "name":        "2011_arab_spring_demand_shock",
            "step":        3 + step_offset,   # year 2011 (init_year=2008 + 3)
            "type":        "speculative",
            "scope":       0.40,
            "severity":    0.35,
            "food_shock":  1.25,
            "energy_shock":1.10,
            "target_node": None,
        },
    ]


def triggers_2011_horn_africa_drought(step_offset: int = 0):
    """
    2011 Horn of Africa drought / famine (Somalia, Kenya, Ethiopia).

    Added for Phase 2 of the scenario catalogue (this session). This is a
    DIFFERENT event from `triggers_2010_russia_drought` (which is the
    global-scale 2010-11 Russia/Arab-Spring episode already retrodicted in
    this codebase as "retro_2011") -- that naming collision in the existing
    docs is worth flagging explicitly: "2011" in this codebase's existing
    retrodiction.py refers to the Russia/Arab Spring price peak, NOT this
    East Africa drought. Both are real, distinct, roughly-concurrent 2011
    events; this function models the regional one.

    DATA LIMITATION (checked this session, not present before): unlike
    2008/2022/2010-Russia, `node_panel.csv`'s `cereal_yield_t_ha` /
    `chi_shock` columns are NaN for the "East Africa" bloc in 2010 and 2011
    (checked directly: `node_panel[(node=='East Africa') & year.isin(
    [2010,2011])]` returns NaN chi_i/chi_shock). There is therefore NO
    FAO-yield-derived empirical severity available for this episode, unlike
    every other trigger in this file. Severity below is calibrated from
    documented humanitarian-crisis facts instead (UN declared famine in
    two regions of southern Somalia, 20 July 2011; FEWS NET / UNHCR
    reporting describes it as the worst drought in the region in ~60
    years; UN OCHA estimated 13 million people across Somalia, Ethiopia,
    Djibouti and Kenya were affected) -- this is the same class of
    documented-but-not-FAO-yield-sourced calibration already used for the
    COVID trade-disruption leg of `triggers_2019_covid_locust`, applied
    here for consistency rather than inventing a fake yield number.

    init_year=2009 (2-year pre-crisis build window, matching the 2-year
    convention used for the other 2010s-era episodes).
    """
    return [
        {
            "name":        "2011_horn_africa_drought",
            "step":        2 + step_offset,   # year 2011 (init_year=2009 + 2)
            "type":        "climate",
            "scope":       0.15,   # East Africa bloc has 21 members; the
                                    # famine was concentrated in Somalia and
                                    # adjacent areas of Kenya/Ethiopia, not
                                    # uniform across the whole bloc
            # DOCUMENTED-ASSUMPTION SEVERITY (not FAO-yield-sourced -- see
            # docstring). Calibrated qualitatively against the "worst
            # drought in 60 years" / UN-declared-famine severity language,
            # positioned above the 2004 Niger regional episode (chi_shock-
            # sourced severity 0.25) given the higher documented death toll
            # and famine (not just crisis) classification.
            "severity":    0.32,
            "food_shock":  1.15,
            "energy_shock":1.0,
            "target_node": "East Africa",
        },
        {
            "name":        "2011_horn_africa_reserve_collapse",
            "step":        3 + step_offset,   # stock-depletion follow-on,
                                                # same pattern as the 2005
                                                # Niger stock-depletion leg
            "type":        "speculative",
            "scope":       0.10,
            "severity":    0.22,
            "food_shock":  1.10,
            "energy_shock":1.0,
            "target_node": "East Africa",
        },
    ]


# ============================================================================
# Counterfactual trigger sets -- Phase 2 scientific experiments.
# These are NOT predictions. Each reuses the same STC engine mechanics as
# the historical triggers above; the "counterfactual" element is stated
# explicitly in each docstring (a real shock magnitude applied to a
# different initial year / different target / different co-occurrence than
# actually happened).
# ============================================================================

def triggers_covid_in_2000(step_offset: int = 0):
    """
    COUNTERFACTUAL: "What if a COVID-2020-magnitude shock had occurred in
    2000 instead of 2020?"

    Reuses the exact trigger magnitudes from `triggers_2019_covid_locust`
    unchanged. The only thing this counterfactual varies is the model's
    INITIAL CONDITIONS: run with init_year=2000 (real 2000 population,
    capital, technology, reserves, A_i) instead of init_year=2018. This
    isolates one question: does the same shock magnitude produce a
    different outcome purely because the world's structural resilience
    (technology, capital, reserve buffers) was different in 2000 than in
    2018? It is not a claim that a COVID-like pathogen shock was plausible
    or likely in 2000 -- it is a structural-resilience experiment.

    init_year=2000, step_offset=-2 fires the trigger at step 0 instead of
    step 2 (there is no "pre-crisis build year" available before the
    panel's earliest year).
    """
    return triggers_2019_covid_locust(step_offset=step_offset)


def triggers_ukraine_in_2010(step_offset: int = 0):
    """
    COUNTERFACTUAL: "What if the 2022 Russia-Ukraine war-scale trade shock
    had occurred in 2010 instead of 2022?"

    Reuses the exact `triggers_2022_ukraine` magnitudes unchanged (45%
    food-shock / 80% energy-shock on Russia, 30% export-volume shock on
    Ukraine, 15% global inflation cascade). Run with init_year=2008 (the
    same real pre-2010 baseline already used for the 2010-11 Russia-drought
    retrodiction), instead of init_year=2018. Tests whether the 2010-era
    trade network (before a decade of further trade concentration) and
    2010-era reserve levels absorb or amplify the same conflict-scale shock
    differently than the real 2022 network did. Not a claim that the war
    itself could have happened in 2010.
    """
    return triggers_2022_ukraine(step_offset=step_offset)


def triggers_china_fertilizer_ban(step_offset: int = 0):
    """
    COUNTERFACTUAL: China fertilizer export restriction.

    MODELLING LIMITATION, stated up front: this model has NO explicit
    fertilizer-stock or fertilizer-price state variable. `fertiliser_kg_ha`
    (from World Bank data) is used only once, at calibration time, to help
    derive the static T_i technology index (`data_pipeline.py::derive_Ti`)
    -- it is not a live per-tick input the STC engine can shock. The
    documented mechanism this model DOES have for input-cost pass-through
    is the energy-food coupling (epsilon_ef): `energy.py` itself notes
    fertilizer is "40-50% of variable cropping costs" and treats fertilizer
    cost shocks as part of the energy-stress -> food-TFP channel (Arrow 1),
    because nitrogen fertilizer production is gas-intensive.

    This counterfactual therefore proxies a fertilizer export ban as an
    energy-shock-channel geopolitical trigger targeting China's outgoing
    trade edges, rather than a literal fertilizer-market simulation. This
    is a real, disclosed modelling approximation, not a hidden one -- any
    reviewer should read the result as "a China-origin input-cost shock
    routed through the model's existing energy-food coupling," not as a
    dedicated fertilizer-market model.

    China accounted for real, documented restrictions on phosphate exports
    in 2021 (export inspections that sharply cut volumes); this
    counterfactual scales that real 2021 event up to a fuller, sustained
    export ban (severity chosen to represent a near-complete restriction,
    the same "near-total export-volume shock" pattern already used for
    Russia 2010 and Ukraine 2022 above) -- this scaling-up is the
    counterfactual/hypothetical element, not the existence of the 2021
    event itself.

    init_year=2022 (near-term, current network structure).
    """
    return [
        {
            "name":        "china_fertilizer_export_ban",
            "step":        2 + step_offset,
            "type":        "geopolitical",
            "scope":       0.0,
            "severity":    0.70,   # near-total restriction, scaled up from
                                    # the real but partial 2021 phosphate
                                    # export inspection regime
            "food_shock":  1.0,
            "energy_shock":1.35,   # routed through the energy-food coupling
                                    # channel per the docstring above, not a
                                    # dedicated fertilizer-price variable
            "target_node": "China",
        },
        {
            "name":        "fertilizer_cost_cascade",
            "step":        4 + step_offset,
            "type":        "speculative",
            "scope":       0.55,   # broad -- fertilizer is a globally
                                    # traded input, unlike a single crop
            "severity":    0.30,
            "food_shock":  1.18,
            "energy_shock":1.10,
            "target_node": None,
        },
    ]


def triggers_global_oil_crisis(step_offset: int = 0):
    """
    COUNTERFACTUAL: A 1973-oil-embargo-scale global oil price shock,
    occurring against TODAY's (2022-network) trade structure.

    Calibration anchor: the real 1973 OPEC oil embargo produced
    approximately a quadrupling of oil prices (a well-documented,
    non-FAO-panel historical fact -- this model's data panel does not
    cover 1973, so this cannot be run as a retrodiction the way
    2008/2022/2010/2011/2020 are; it is presented purely as a stylised
    magnitude-matched experiment). This is explicitly a hypothetical
    "what would a shock of that historically-documented size do to the
    CURRENT network" experiment, not a retrodiction of 1973 itself.

    init_year=2022 (current network).
    """
    return [
        {
            "name":        "global_oil_price_quadrupling",
            "step":        2 + step_offset,
            "type":        "geopolitical",
            "scope":       1.0,   # global, no single target node -- unlike
                                    # every historical trigger above, a
                                    # 1973-style embargo was not routed
                                    # through one exporter's bilateral edges
            "severity":    0.60,
            "food_shock":  1.10,   # food effect is indirect (via energy
                                    # -food coupling), so kept modest here
            "energy_shock":2.20,   # ~4x real oil price historically; kept
                                    # below a literal 4x on the model's
                                    # energy_shock multiplier scale because
                                    # that scale is not directly the oil
                                    # price itself but a composite energy-
                                    # cost index -- documented judgement
                                    # call, not an empirical figure
            "target_node": None,
        },
    ]


def triggers_compound_climate_shock(step_offset: int = 0):
    """
    COUNTERFACTUAL: Simultaneous, real, historically-documented drought
    magnitudes hitting three major breadbasket nodes IN THE SAME YEAR.

    Each individual component below is a REAL, FAO-panel-sourced chi_shock
    magnitude, taken from a different real year in which that country
    actually experienced it:
      - Australia: chi_shock=0.4834 (2006, Millennium Drought) -- same
        empirical figure already used in `triggers_2008_food_energy`.
      - Russia:    chi_shock=0.2281 (2010 drought) -- same empirical
        figure already used in `triggers_2010_russia_drought`.
      - United States: chi_shock=0.1213 (2009, the largest single-year US
        cereal-yield chi_shock present in this data panel; checked this
        session against `node_panel.csv`). This is a smaller shock than
        the widely-cited 2012 US drought, which is NOT well captured by
        this panel's yield-shock methodology -- flagged as a data
        limitation, not silently substituted with an invented number.

    THE COUNTERFACTUAL ELEMENT IS SOLELY THE CO-OCCURRENCE: these three
    events happened in three different real years (2006, 2010, 2009); this
    experiment asks what the network-cascade consequence would be if
    magnitudes of that real, documented size hit all three simultaneously.
    init_year=2022 (current network).
    """
    return [
        {
            "name":        "compound_australia_drought",
            "step":        2 + step_offset,
            "type":        "climate",
            "scope":       0.20,
            "severity":    0.48,
            "food_shock":  1.0,
            "energy_shock":1.0,
            "target_node": "Australia",
        },
        {
            "name":        "compound_russia_drought",
            "step":        2 + step_offset,
            "type":        "climate",
            "scope":       0.35,
            "severity":    0.23,
            "food_shock":  1.0,
            "energy_shock":1.0,
            "target_node": "Russia",
        },
        {
            "name":        "compound_us_drought",
            "step":        2 + step_offset,
            "type":        "climate",
            "scope":       0.40,
            "severity":    0.12,
            "food_shock":  1.0,
            "energy_shock":1.0,
            "target_node": "United States",
        },
        {
            "name":        "compound_speculative_amplification",
            "step":        4 + step_offset,
            "type":        "speculative",
            "scope":       0.65,
            "severity":    0.35,
            "food_shock":  1.25,
            "energy_shock":1.0,
            "target_node": None,
        },
    ]


def triggers_2019_covid_locust(step_offset: int = 0):
    """
    2019-20 COVID-19 supply-chain disruption + East Africa desert locust
    invasion.

    init_year=2018 (matches the existing 2022 episode's init_year for
    consistency; gives a temporally coherent 2-year build window).

    Source: FAO Crops Production data, Cereals primary, Yield, East Africa
    (ECOWAS-style bloc average, per the modelling convention used
    consistently for all regional blocs in this project -- note this
    dilutes the locust shock relative to the hardest-hit member country,
    Somalia, whose real chi_shock was 0.26-0.29 in 2019-2020; the bloc
    average (chi_shock~0.03) is used here for methodological consistency
    with how every other regional bloc in this model is calibrated, at the
    cost of understating peak severity -- documented tradeoff, not an
    oversight). COVID trade-disruption severity is not separately
    FAO-sourced (it's a logistics/demand shock, not a yield shock) and
    remains a documented assumption pending a dedicated trade-disruption
    data source.

    Real FPI: 2019=0.951, 2020=0.981 (FAO historical table).
    """
    return [
        {
            "name":        "2020_east_africa_locust",
            "step":        2 + step_offset,   # year 2020 (init_year=2018 + 2)
            "type":        "climate",
            "scope":       0.10,
            # FAO-EMPIRICAL SEVERITY: East Africa bloc-average cereal
            # chi_shock 2019-2020 (vs 2018 baseline) ~0.03 -- a real but
            # diluted signal (see docstring re: Somalia's much larger
            # localized shock). Calibrating above the raw bloc-average to
            # partially reflect the locust invasion's documented non-yield
            # damage (pasture, stored grain) while keeping the bloc-average
            # as the primary empirical anchor per the consistency decision.
            "severity":    0.15,
            "food_shock":  1.10,
            "energy_shock":1.0,
            "target_node": "East Africa",
        },
        {
            "name":        "2020_covid_trade_disruption",
            "step":        2 + step_offset,   # year 2020 -- COVID disruption
                                                # overlapped the locust peak
            "type":        "geopolitical",     # modelled as a trade/logistics
                                                 # shock, not climate
            "scope":       0.60,   # broad -- global logistics disruption
            # ASSUMPTION (not FAO-sourced -- COVID is a logistics/demand
            # shock, not a yield shock; documented pending a dedicated
            # trade-disruption data source, e.g. shipping/port throughput
            # data)
            "severity":    0.25,
            "food_shock":  1.08,
            "energy_shock":0.85,   # oil demand collapsed in 2020
            "target_node": None,
        },
    ]
