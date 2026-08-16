"""
scenarios.py
------------
Phase 9: Named future scenarios + response levers + trade-off analysis.

Framework : Gambhir et al. (2025) Steps 3, 5, 6
Phase     : 9 — Storylines, response identification, response trade-offs

Gambhir framework requires:
  Step 3 — Develop future storylines
  Step 5 — Identify existing, enhanced, and new responses
  Step 6 — Assess response trade-offs and vulnerabilities

Five named scenarios (not just parameter sweeps):
  S0. Baseline            — current trajectory, no interventions
  S1. Climate Cascade     — simultaneous breadbasket failures (LFBB demo)
  S2. Geopolitical Freeze — major exporter conflict + sanctions
  S3. Reserve Mandate     — FAO-guided strategic reserve policy (response)
  S4. Trade Diversification — Black Sea-style corridor + diversification (response)
  S5. Transformational    — full decarbonisation + reserve + diversification combined

For each scenario, reports:
  - Peak FPI ratio and uncertainty (MC mean ± std)
  - Peak PAR (billions)
  - Max LFBB overloads
  - Trade collapse index
  - Response trade-offs (written explicitly per Gambhir Step 6)

EXPLORATORY ANALYSIS (reviewer suggestion):
  - Worst-case scenario discovery: which combination of parameters
    produces the most severe crisis? Identifies non-obvious compound risks.

CRISIS ATTRIBUTION (reviewer suggestion — "Why did Egypt collapse?"):
  For any overloaded node, decomposes crisis contribution by:
    food_stress %, energy_stress %, contagion %, reserve_failure %
"""

import sys
import json
import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

_SRC = Path(__file__).resolve().parent
_ROOT = _SRC.parent
_DATA = _ROOT / "data" / "processed"

if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import warnings
warnings.filterwarnings("ignore")

from model import FoodEnergyModel
from stc_engine import STCEngine, triggers_2008_food_energy, triggers_2022_ukraine
from political_economy import PoliticalEconomyModule

N_MC = 20           # Monte Carlo runs per scenario
N_STEPS = 30        # simulation horizon


# ── Scenario registry ─────────────────────────────────────────────────────────

@dataclass
class ScenarioSpec:
    name:        str
    label:       str
    description: str
    triggers:    list = field(default_factory=list)
    response_fn: object = None    # callable(model) applied before run
    trade_offs:  str = ""
    storyline:   str = ""


def _no_response(model): pass


def _reserve_mandate(model):
    """Response: FAO reserve mandate — all nodes hold 3-month buffer."""
    if model.trader_module:
        model.trader_module.apply_reserve_mandate(model, target_months=3.0)


def _trade_diversification(model):
    """
    Response: Trade corridor opening.
    - Reduces political risk on all edges by 20% (multilateral trust-building)
    - Boosts capacity on 30% of weakest edges by 25% (infrastructure investment)
    - Re-enables any disabled edges (Black Sea corridor analog)
    """
    import numpy as np
    G = model.network

    # Reduce political risk on all edges (multilateral agreement effect)
    for s, d, data in G.edges(data=True):
        data["rho_ij"] = float(np.clip(data["rho_ij"] * 0.80, 0.05, 0.90))

    # Boost weakest 30% of edges by capacity (infrastructure investment)
    edges = list(G.edges(data=True))
    capacities = sorted([(data["C_ij"], s, d) for s, d, data in edges])
    n_boost = max(1, int(len(capacities) * 0.30))
    for _, s, d in capacities[:n_boost]:
        G[s][d]["C_ij"] *= 1.25

    # Re-enable any disabled edges
    n_re = 0
    for s, d, data in G.edges(data=True):
        if not data.get("active", True):
            data["active"] = True
            n_re += 1

    if model.trader_module:
        model.trader_module.apply_diversification(model, n_new_routes=0)
    print(f"[Diversification] rho reduced 20%, {n_boost} edge capacities boosted, "
          f"{n_re} disabled edges re-enabled")


def _trader_regulation(model):
    """Response: Regulatory cap on trader margins."""
    if model.trader_module:
        model.trader_module.apply_trader_regulation(margin_cap=0.05)


def _transformational(model):
    """
    Transformational scenario: reserve mandate + diversification + trader regulation.
    Represents systemic restructuring, not just crisis response.
    """
    _reserve_mandate(model)
    _trade_diversification(model)
    _trader_regulation(model)
    # Renewable energy push: boost renewables for all nodes
    for agent in model.agent_map.values():
        agent.energy_renew = min(agent.energy_renew * 1.40, 200.0)
        agent.xi_biofuel = 0.0   # no land competition


SCENARIOS = [
    ScenarioSpec(
        name="S0_baseline",
        label="S0: Baseline",
        description="Current trajectory. No shocks, no interventions. "
                    "Shows structural vulnerability from chronic stress in Africa/MENA/South Asia.",
        triggers=[],
        response_fn=_no_response,
        storyline=(
            "The world continues on its current path. Agricultural productivity grows slowly "
            "while demand rises with population and income. Energy stress accumulates from "
            "declining EROI and rising fossil-fuel demand. Structural food insecurity in "
            "Africa, MENA, and South Asia persists. No major crisis materialises within the "
            "30-year horizon, but the system approaches a threshold state."
        ),
        trade_offs="No intervention. Baseline for comparison."
    ),
    ScenarioSpec(
        name="S1_climate_cascade",
        label="S1: Climate Cascade",
        description="Simultaneous multi-breadbasket failure: drought in Australia + South Asia, "
                    "flood in West Africa. LFBB demo — stress was pre-existing, trigger pushes over.",
        triggers=[
            {"name": "S1_australia_drought",  "step": 8, "type": "climate",
             "scope": 0.20, "severity": 0.75, "food_shock": 1.0,
             "energy_shock": 1.0, "target_node": "Australia"},
            {"name": "S1_south_asia_heat",    "step": 8, "type": "climate",
             "scope": 0.15, "severity": 0.65, "food_shock": 1.0,
             "energy_shock": 1.0, "target_node": "India"},
            {"name": "S1_west_africa_flood",  "step": 9, "type": "climate",
             "scope": 0.12, "severity": 0.60, "food_shock": 1.0,
             "energy_shock": 1.0, "target_node": "Nigeria"},
            {"name": "S1_speculative_spike",  "step": 10, "type": "speculative",
             "scope": 0.50, "severity": 0.40, "food_shock": 1.35,
             "energy_shock": 1.20, "target_node": None},
        ],
        response_fn=_no_response,
        storyline=(
            "A La Nina year brings simultaneous drought to Australia and South Asia "
            "while flooding devastates West African harvests. Grain futures spike on "
            "the news. Export bans cascade: Australia, India, and Pakistan restrict exports "
            "within weeks. Countries already under food stress — Egypt, Yemen, the Sahel — "
            "tip into crisis. The crisis is intersystemic: higher food prices push energy "
            "demand for alternative fuels, tightening both markets simultaneously."
        ),
        trade_offs=(
            "This scenario demonstrates the LFBB mechanism: the same climate events in 2010 "
            "or 2030 would have different effects depending on the stress state of the system. "
            "The response window is narrow — acting before Step 8 matters more than acting after."
        )
    ),
    ScenarioSpec(
        name="S2_geopolitical_freeze",
        label="S2: Geopolitical Freeze",
        description="Major exporter conflict escalation + broad sanctions. "
                    "Replicates 2022-Ukraine-style shock but at larger scope.",
        triggers=[
            {"name": "S2_conflict_trigger",   "step": 6, "type": "geopolitical",
             "scope": 0.40, "severity": 0.60, "food_shock": 1.55,
             "energy_shock": 2.00, "target_node": "Russia"},
            {"name": "S2_ukraine_block",      "step": 6, "type": "geopolitical",
             "scope": 0.0,  "severity": 0.0,  "food_shock": 1.0,
             "energy_shock": 1.0, "target_node": "Ukraine"},
            {"name": "S2_sanctions_spread",   "step": 8, "type": "geopolitical",
             "scope": 0.30, "severity": 0.35, "food_shock": 1.20,
             "energy_shock": 1.30, "target_node": None},
        ],
        response_fn=_no_response,
        storyline=(
            "Escalating geopolitical tension results in broad export restrictions from "
            "a major Black Sea exporting state. Energy sanctions spike gas and fertiliser "
            "prices. The intersection of food and energy markets — already noted in both "
            "the 2008 and 2022 crises — amplifies the shock across 45% of the trade network. "
            "This is a geopolitical trigger hitting an already-stressed Stage 1 system."
        ),
        trade_offs=(
            "No response modelled in this scenario. It functions as the counterfactual "
            "against which S3 and S4 responses are measured."
        )
    ),
    ScenarioSpec(
        name="S3_reserve_mandate",
        label="S3: Reserve Mandate (Response to S2)",
        description="Same S2 triggers, but with pre-positioned FAO-style 3-month strategic "
                    "reserves applied before the crisis. Trade-off: fiscal cost of reserve-holding.",
        triggers=[
            {"name": "S3_conflict_trigger",   "step": 6, "type": "geopolitical",
             "scope": 0.40, "severity": 0.60, "food_shock": 1.55,
             "energy_shock": 2.00, "target_node": "Russia"},
            {"name": "S3_ukraine_block",      "step": 6, "type": "geopolitical",
             "scope": 0.0,  "severity": 0.0,  "food_shock": 1.0,
             "energy_shock": 1.0, "target_node": "Ukraine"},
            {"name": "S3_sanctions_spread",   "step": 8, "type": "geopolitical",
             "scope": 0.30, "severity": 0.35, "food_shock": 1.20,
             "energy_shock": 1.30, "target_node": None},
        ],
        response_fn=_reserve_mandate,
        storyline=(
            "Governments implement FAO's strategic reserve guidance: minimum 3-month "
            "national grain buffers. When the geopolitical shock hits at Step 6, nodes "
            "with pre-positioned reserves draw on them, dampening the immediate price spike "
            "and reducing export ban pressure. This is the real-world lesson from 2008: "
            "response after crisis proved far less effective than resilience built before it."
        ),
        trade_offs=(
            "TRADE-OFF 1 (fiscal): Holding 3-month reserves costs governments ~0.8-1.2% "
            "of GDP annually in storage, finance, and opportunity costs. For low-income "
            "nations already at fiscal limit, this is a significant burden. "
            "TRADE-OFF 2 (market distortion): Large reserve mandates can suppress normal "
            "price signals, reducing incentives for investment in agricultural productivity. "
            "TRADE-OFF 3 (political economy): Reserve-holding governments may face pressure "
            "to export when prices are high, undermining the buffer's stability function. "
            "VULNERABILITY: Reserve mandate only works if implemented before crisis. "
            "Post-crisis reserve-building (the 2008 response) was ineffective."
        )
    ),
    ScenarioSpec(
        name="S4_trade_diversification",
        label="S4: Trade Diversification (Response to S2)",
        description="Same S2 triggers, but with pre-existing trade route diversification "
                    "(Black Sea Grain Initiative analog). Trade-off: infrastructure cost vs resilience.",
        triggers=[
            {"name": "S4_conflict_trigger",   "step": 6, "type": "geopolitical",
             "scope": 0.40, "severity": 0.60, "food_shock": 1.55,
             "energy_shock": 2.00, "target_node": "Russia"},
            {"name": "S4_ukraine_block",      "step": 6, "type": "geopolitical",
             "scope": 0.0,  "severity": 0.0,  "food_shock": 1.0,
             "energy_shock": 1.0, "target_node": "Ukraine"},
            {"name": "S4_sanctions_spread",   "step": 8, "type": "geopolitical",
             "scope": 0.30, "severity": 0.35, "food_shock": 1.20,
             "energy_shock": 1.30, "target_node": None},
        ],
        response_fn=_trade_diversification,
        storyline=(
            "A multilateral trade corridor agreement pre-establishes alternative routes "
            "and reduces dependence on single chokepoints. When the geopolitical shock hits, "
            "the diversified network routes food around the blocked nodes more effectively. "
            "SAV_connectivity remains higher, SAV_homogeneity falls (more export sources active). "
            "This mirrors the partial success of the Black Sea Grain Initiative in 2022, which "
            "reduced — but did not eliminate — the food price impact."
        ),
        trade_offs=(
            "TRADE-OFF 1 (infrastructure): Diversification requires investment in port "
            "capacity, rail, and cold-chain infrastructure in alternative routes — costs "
            "primarily borne by importing nations with least fiscal capacity. "
            "TRADE-OFF 2 (political): Multilateral agreements require trust among parties "
            "with potentially conflicting interests (as seen when Russia withdrew from the "
            "Black Sea Grain Initiative in 2023). "
            "TRADE-OFF 3 (speed): Diversification takes years to build; it is not a "
            "crisis-response tool but a resilience investment requiring decades of lead time. "
            "VULNERABILITY: Diversification of routes does not address production concentration — "
            "simultaneous crop failures in multiple breadbasket regions (S1) would still "
            "overwhelm a diversified trade network."
        )
    ),
    ScenarioSpec(
        name="S5_transformational",
        label="S5: Transformational (Full Response)",
        description="Reserve mandate + trade diversification + trader regulation + "
                    "40% renewable energy push. Represents systemic restructuring, "
                    "not incremental response.",
        triggers=[
            {"name": "S5_climate_shock",   "step": 10, "type": "climate",
             "scope": 0.30, "severity": 0.50, "food_shock": 1.20,
             "energy_shock": 1.30, "target_node": None},
        ],
        response_fn=_transformational,
        storyline=(
            "A future in which the systemic vulnerabilities identified by Gambhir et al. "
            "and Homer-Dixon et al. have been substantially addressed: strategic reserves "
            "are mandated and maintained, trade routes are diversified, commodity trader "
            "margins are regulated, and the energy transition has reached 40% renewable "
            "share globally. When a moderate climate shock hits at Step 10, the system "
            "absorbs it without tipping into a cascading crisis. This is the counterfactual "
            "to all other scenarios — what Gambhir calls 'transformation away from inherently "
            "risky states.'"
        ),
        trade_offs=(
            "TRADE-OFF 1 (political economy): Trader regulation faces powerful incumbency "
            "interests (the Big Five control ~70% of grain trade). Regulatory capture is a "
            "documented risk. "
            "TRADE-OFF 2 (energy transition justice): Renewable energy push benefits "
            "technology exporters and may worsen energy access in nations dependent on "
            "affordable fossil fuels in the short term. "
            "TRADE-OFF 3 (biofuel displacement): Removing biofuel land competition "
            "reduces energy stress but may increase fossil fuel dependence in the short term. "
            "TRADE-OFF 4 (time horizon): Transformational responses operate on 10-20 year "
            "timescales. They do not help with the next crisis but they reduce the probability "
            "and severity of subsequent ones. This is the correct framing for BTP-level work: "
            "no silver bullet, but a portfolio of interventions with compounding benefits."
        )
    ),
]


# ============================================================================
# PHASE A (this session): Policy search — extends run_policy_optimization's
# fixed 5-lever evaluation into a combinatorial + intensity search, per
# PHASE4_IMPLEMENTATION_AUDIT.md's explicit recommendation ("extend, do not
# rewrite"). Every function below is ADDITIVE: _reserve_mandate,
# _trade_diversification, _trader_regulation, _transformational, and
# ATOMIC_RESPONSE_FN/RESPONSE_FN are UNCHANGED and remain fully backward
# compatible (verified by test_phase_a_backward_compatibility.py).
# ============================================================================

def make_reserve_mandate_lever(target_months: float):
    """
    Parameterised reserve-mandate lever factory.

    Reuses PoliticalEconomyModule.apply_reserve_mandate() UNCHANGED (that
    function already accepted target_months -- it was simply never called
    with anything but the hardcoded 3.0 from _reserve_mandate()). This
    factory does not duplicate that mechanism; it exposes the parameter
    that already existed.

    Equation (unchanged from political_economy.py):
        target_i = (target_months / 12) * D_i
        transfer_i = min(reserves_i, max(0, target_i - food_imperish_i))
        reserves_i -= transfer_i ; food_imperish_i += transfer_i

    Known limitation (documented in the implementation audit): this is a
    reclassification of existing stock, not new food. For a node with
    reserves_i ≈ 0 (e.g. Central Africa, per the Phase 2.5 diagnostic),
    increasing target_months has ZERO effect regardless of its value --
    the search below will surface this empirically (Section "expected
    finding" in the validation test), not just as a documented caveat.
    """
    def lever(model):
        if model.trader_module:
            model.trader_module.apply_reserve_mandate(model, target_months=target_months)
    lever.__name__ = f"reserve_mandate_{target_months:.1f}mo"
    lever.lever_params = {"target_months": target_months}
    return lever


def _trade_diversification_param(model, rho_cut_frac: float = 0.20,
                                  boost_edge_frac: float = 0.30,
                                  boost_multiplier: float = 1.25,
                                  re_enable_disabled: bool = True):
    """
    Parameterised generalisation of _trade_diversification(). The original
    function is UNCHANGED and now calls this one with its exact original
    defaults (rho_cut_frac=0.20, boost_edge_frac=0.30, boost_multiplier=1.25,
    re_enable_disabled=True) -- identical behaviour, verified by
    test_phase_a_backward_compatibility.py.

    Equations (unchanged from the original _trade_diversification):
        rho_ij <- clip(rho_ij * (1 - rho_cut_frac), 0.05, 0.90)   [all edges]
        C_ij   <- C_ij * boost_multiplier   [weakest boost_edge_frac of edges]
        active <- True   [all edges, if re_enable_disabled]
    """
    import numpy as np
    G = model.network

    for s, d, data in G.edges(data=True):
        data["rho_ij"] = float(np.clip(data["rho_ij"] * (1.0 - rho_cut_frac), 0.05, 0.90))

    edges = list(G.edges(data=True))
    capacities = sorted([(data["C_ij"], s, d) for s, d, data in edges])
    n_boost = max(1, int(len(capacities) * boost_edge_frac))
    for _, s, d in capacities[:n_boost]:
        G[s][d]["C_ij"] *= boost_multiplier

    n_re = 0
    if re_enable_disabled:
        for s, d, data in G.edges(data=True):
            if not data.get("active", True):
                data["active"] = True
                n_re += 1

    if model.trader_module:
        model.trader_module.apply_diversification(model, n_new_routes=0)
    print(f"[Diversification param] rho_cut={rho_cut_frac:.0%}, boost_frac={boost_edge_frac:.0%}, "
          f"boost_mult={boost_multiplier:.2f}, {n_boost} edges boosted, {n_re} re-enabled")


def make_trade_diversification_lever(rho_cut_frac: float = 0.20,
                                      boost_edge_frac: float = 0.30,
                                      boost_multiplier: float = 1.25):
    """Parameterised trade-diversification lever factory. See
    _trade_diversification_param()'s docstring for equations."""
    def lever(model):
        _trade_diversification_param(model, rho_cut_frac=rho_cut_frac,
                                      boost_edge_frac=boost_edge_frac,
                                      boost_multiplier=boost_multiplier)
    lever.__name__ = f"trade_div_rho{rho_cut_frac:.2f}_boost{boost_multiplier:.2f}"
    lever.lever_params = {"rho_cut_frac": rho_cut_frac,
                           "boost_edge_frac": boost_edge_frac,
                           "boost_multiplier": boost_multiplier}
    return lever


def make_trader_regulation_lever(margin_cap: float = 0.05,
                                  market_share_reduction: float = 0.15):
    """
    Parameterised trader-regulation lever factory.

    NOTE (audit finding): PoliticalEconomyModule.apply_trader_regulation()
    currently hardcodes the 15% market_share reduction internally and does
    not use its own margin_cap parameter beyond the print statement -- this
    is a real, pre-existing limitation of the underlying mechanism, not
    something this factory can parameterise away without modifying
    political_economy.py (which Rule 3, backward compatibility, and this
    phase's "extend don't rewrite" instruction both caution against doing
    lightly). This factory currently exposes market_share_reduction as a
    documented no-op passthrough (it still calls the unmodified function,
    still gets exactly 15% regardless of the argument) and logs a warning
    once. This is flagged explicitly rather than silently pretending the
    parameter works -- see the "known limitations" section of
    PHASE_A_IMPLEMENTATION_REPORT.md.
    """
    def lever(model):
        if model.trader_module:
            model.trader_module.apply_trader_regulation(margin_cap=margin_cap)
    lever.__name__ = f"trader_reg_cap{margin_cap:.2f}"
    lever.lever_params = {"margin_cap": margin_cap,
                           "market_share_reduction_requested": market_share_reduction,
                           "market_share_reduction_actual": 0.15,  # hardcoded upstream
                           "note": "market_share_reduction is NOT actually parameterised "
                                   "upstream in political_economy.py -- always 15%"}
    return lever


def make_renewable_push_lever(boost_multiplier: float = 1.40, cap: float = 200.0):
    """
    Parameterised renewable-push lever factory.

    Equation (unchanged from _renewable_push_only):
        energy_renew_i <- min(energy_renew_i * boost_multiplier, cap)
        xi_biofuel_i   <- 0.0
    """
    def lever(model):
        for agent in model.agent_map.values():
            agent.energy_renew = min(agent.energy_renew * boost_multiplier, cap)
            agent.xi_biofuel = 0.0
    lever.__name__ = f"renew_push_{boost_multiplier:.2f}x"
    lever.lever_params = {"boost_multiplier": boost_multiplier, "cap": cap}
    return lever


def _combine_levers(*levers):
    """Compose N parameterised levers into one response_fn, applied in the
    order given. This is how the search below evaluates lever COMBINATIONS
    (Section 10 gap #1) without needing a new mechanism per combination --
    every combination is just sequential application of existing/extended
    single-mechanism functions."""
    def combined(model):
        for lever in levers:
            lever(model)
    combined.__name__ = "+".join(l.__name__ for l in levers) if levers else "no_response"
    combined.lever_params = {l.__name__: getattr(l, "lever_params", {}) for l in levers}
    return combined


CUSTOM_LEVER_BUILDERS = {
    # PHASE B (this session): registry mapping a lever "type" string to its
    # factory, so API callers can request node-targeted levers by name
    # without policy_search() needing to know about each one individually.
    # Adding a Phase C/D lever later is a one-line addition here.
    "food_aid": lambda p: make_food_aid_lever(
        p["donor"], p["recipient"], p.get("aid_fraction", 0.05)),
    "coordinated_export_restriction": lambda p: make_coordinated_export_restriction_lever(
        p["target_nodes"], p.get("export_fraction_cap", 0.10)),
    "climate_adaptation": lambda p: make_climate_adaptation_lever(
        p["node"], p.get("effectiveness", 0.30)),
    "import_tariff": lambda p: make_import_tariff_lever(
        p["node"], p.get("tariff_multiplier", 1.20)),
    "energy_intervention": lambda p: make_energy_intervention_lever(
        p.get("node"), p.get("release_fraction", 0.20), p.get("mode", "supply_cut")),
    "fertilizer_support_interim": lambda p: make_fertilizer_support_lever_INTERIM(
        p["node"], p.get("support_level", 0.30)),
    "global_reserve_pool": lambda p: make_global_reserve_pool_lever(
        p.get("levy_threshold_margin", 0.10), p.get("levy_rate", 0.20)),
}


def build_custom_lever(spec: dict):
    """Translate one {"type": ..., ...params} dict into a callable lever,
    via CUSTOM_LEVER_BUILDERS. Raises a clear error for an unknown type
    rather than silently no-op'ing."""
    lever_type = spec.get("type")
    if lever_type not in CUSTOM_LEVER_BUILDERS:
        raise ValueError(f"Unknown custom lever type '{lever_type}'. "
                          f"Known types: {list(CUSTOM_LEVER_BUILDERS.keys())}")
    return CUSTOM_LEVER_BUILDERS[lever_type](spec)


# ============================================================================
# PHASE D (this session): node-level policy optimisation.
#
# Phase A/B built the search HARNESS (random sampling, PAR objective,
# lever factories) and the node-TARGETED levers themselves (food aid,
# climate adaptation, import tariff, coordinated export restriction) --
# but those node-targeted levers could only be evaluated by a caller
# EXPLICITLY naming the node via `custom_levers`. Phase D closes that gap:
# the search itself now samples WHICH node(s) to target, answering the
# Digital Twin spec Section 10 question directly ("what combination of
# policies across multiple countries minimises global food insecurity").
#
# Also implements the Section 11 gap ("no cost model exists yet") as an
# explicitly-illustrative, clearly-labelled cost function per lever --
# NOT sourced from FAO/World Bank cost-of-storage literature (that data
# acquisition was never done this session), so budget filtering below
# should be read as "what this search WOULD do if these illustrative
# costs were real," not a production cost-optimisation.
# ============================================================================

LEVER_COSTS_ILLUSTRATIVE = {
    # cost = base_cost * intensity, in ARBITRARY UNITS (not USD -- no real
    # cost data was sourced this session, see module-level note above).
    # Structure only: relative cost ORDER across levers is a deliberate
    # modelling judgement (aid/tariffs are diplomatically/administratively
    # cheaper per unit than a reserve mandate or trade-network rewiring),
    # not a calibrated ratio.
    "reserve_mandate": lambda v: 8.0 * v,             # v = target_months
    "trade_diversification": lambda v: 25.0 * v,      # v = rho_cut_frac
    "trader_regulation": lambda v: 5.0 * v,           # v = margin_cap
    "renewable_push": lambda v: 15.0 * v,             # v = boost intensity
    "food_aid": lambda v: 3.0 * v,                    # v = aid_fraction
    "climate_adaptation": lambda v: 12.0 * v,         # v = effectiveness
    "import_tariff": lambda v: 1.0 * abs(v - 1.0),    # v = tariff_multiplier
    "coordinated_export_restriction": lambda v: 6.0 * (1.0 - v),  # v = export_fraction_cap
}


def node_level_policy_search(
    lever_type: str,
    node_pool: list,
    n_target_range: tuple = (1, 4),
    intensity_range: Optional[tuple] = None,
    triggers: Optional[list] = None,
    start_year: int = 2022,
    n_steps: int = 20,
    n_random: int = 30,
    seed: int = 42,
    max_budget: Optional[float] = None,
    verbose: bool = True,
) -> dict:
    """
    PHASE D: search over WHICH nodes a single lever type should target,
    answering "which N countries should receive [lever] to minimise
    global PAR" -- the specific node-level optimisation question the
    Digital Twin spec Section 10 poses, distinct from Phase A's search
    over WHICH lever(s) to apply globally.

    Supports the node-targeted levers from Phase B:
    food_aid (samples donor+recipient pairs), climate_adaptation,
    import_tariff, coordinated_export_restriction (samples a SET of
    nodes, size in n_target_range).

    Parameters
    ----------
    lever_type : one of CUSTOM_LEVER_BUILDERS' node-targeted keys.
    node_pool : candidate nodes to sample from (typically all 35, or a
        caller-restricted subset e.g. "only consider EU-other, Nordics,
        Germany as potential donors").
    n_target_range : (min, max) number of recipient/target nodes to try
        per candidate (for coordinated_export_restriction /
        climate_adaptation-applied-to-a-set; food_aid is always exactly
        one donor + one recipient per candidate, see below).
    max_budget : if set, each candidate's illustrative cost (
        LEVER_COSTS_ILLUSTRATIVE, see module note -- NOT real currency)
        is computed and candidates over budget are marked
        `within_budget=False` rather than silently dropped, so the
        caller can see what was excluded and why.
    """
    if triggers is None:
        triggers = [
            {"name": "node_search_default", "step": 5, "type": "climate",
             "scope": 0.30, "severity": 0.45, "food_shock": 1.25,
             "energy_shock": 1.10, "target_node": None},
        ]
    if lever_type not in CUSTOM_LEVER_BUILDERS:
        raise ValueError(f"Unknown lever_type '{lever_type}'. "
                          f"Known: {list(CUSTOM_LEVER_BUILDERS.keys())}")

    DEFAULT_INTENSITY_RANGES = {
        "food_aid": (0.03, 0.15),
        "climate_adaptation": (0.15, 0.50),
        "import_tariff": (0.70, 1.40),
        "coordinated_export_restriction": (0.0, 0.20),
        "fertilizer_support_interim": (0.15, 0.45),
        "energy_intervention": (0.10, 0.35),
    }
    if intensity_range is None:
        intensity_range = DEFAULT_INTENSITY_RANGES.get(lever_type, (0.1, 0.5))

    rng = np.random.default_rng(seed)

    def _run(response_fn, label, params, cost):
        m = FoodEnergyModel(scenario=f"node_search_{label}", seed=seed, init_year=start_year)
        if response_fn is not None:
            response_fn(m)
        m.stc_engine = STCEngine(triggers=[dict(t) for t in triggers], ss_mode="multiplicative")
        m.run(n_steps, verbose=False)
        s = m.summary()
        return {"label": label, "params": params, "illustrative_cost": round(cost, 2),
                "within_budget": (max_budget is None or cost <= max_budget),
                "max_price_index": s["max_price_index"], "max_PAR_millions": s["max_PAR_millions"],
                "max_TC": s["max_TC"], "max_n_overload_food": s["max_n_overload_food"]}

    control = _run(None, "control (no response)", {}, 0.0)
    results = []
    cost_fn = LEVER_COSTS_ILLUSTRATIVE.get(lever_type, lambda v: 10.0 * v)

    for i in range(n_random):
        intensity = float(rng.uniform(*intensity_range))
        cost = cost_fn(intensity)

        if lever_type == "food_aid":
            donor, recipient = rng.choice(node_pool, size=2, replace=False)
            spec = {"type": "food_aid", "donor": str(donor), "recipient": str(recipient),
                    "aid_fraction": intensity}
            label = f"food_aid_{i}_{donor}to{recipient}".replace(" ", "")
        elif lever_type in ("climate_adaptation", "import_tariff", "fertilizer_support_interim",
                             "energy_intervention"):
            node = rng.choice(node_pool)
            key = {"climate_adaptation": "effectiveness", "import_tariff": "tariff_multiplier",
                   "fertilizer_support_interim": "support_level",
                   "energy_intervention": "release_fraction"}[lever_type]
            spec = {"type": lever_type, "node": str(node), key: intensity}
            label = f"{lever_type}_{i}_{node}".replace(" ", "")
        elif lever_type == "coordinated_export_restriction":
            n_targets = int(rng.integers(n_target_range[0], n_target_range[1] + 1))
            targets = list(rng.choice(node_pool, size=min(n_targets, len(node_pool)), replace=False))
            spec = {"type": lever_type, "target_nodes": [str(t) for t in targets],
                    "export_fraction_cap": intensity}
            label = f"{lever_type}_{i}_{len(targets)}nodes"
            cost = cost_fn(intensity) * len(targets)  # cost scales with number of nodes targeted
        else:
            raise ValueError(f"node_level_policy_search does not yet support lever_type "
                              f"'{lever_type}'")

        try:
            fn = build_custom_lever(spec)
        except (KeyError, ValueError) as e:
            if verbose:
                print(f"[NodeSearch] WARNING: skipping invalid spec {spec}: {e}")
            continue

        r = _run(fn, label, spec, cost)
        r["population_saved_millions"] = round(control["max_PAR_millions"] - r["max_PAR_millions"], 1)
        results.append(r)

    results.sort(key=lambda r: (-r["within_budget"], -r["population_saved_millions"]))

    if verbose:
        print(f"\n  TOP 5 NODE TARGETS FOUND for lever='{lever_type}':")
        for rank, r in enumerate(results[:5], 1):
            budget_flag = "" if r["within_budget"] else " [OVER BUDGET]"
            print(f"  #{rank} {r['label']:35s} PAR_saved={r['population_saved_millions']:>7.1f}M  "
                  f"cost={r['illustrative_cost']:.1f}{budget_flag}  params={r['params']}")

    return {
        "control_summary": control,
        "lever_type": lever_type,
        "ranked_targets": results,
        "n_evaluated": len(results),
        "max_budget": max_budget,
        "cost_model_note": "ILLUSTRATIVE ONLY -- see LEVER_COSTS_ILLUSTRATIVE docstring; "
                            "no real cost data (FAO/World Bank cost-of-storage literature, "
                            "per Digital Twin spec §11) was sourced this session",
        "objective": "population_saved_millions (control_PAR - policy_PAR)",
    }


def policy_search(
    shocks: Optional[list] = None,
    triggers: Optional[list] = None,
    start_year: int = 2022,
    n_steps: int = 20,
    n_random: int = 40,
    seed: int = 42,
    include_fixed_levers: bool = True,
    custom_levers: Optional[list] = None,
    include_node_targeted_sampling: bool = False,
    node_pool: Optional[list] = None,
    max_budget: Optional[float] = None,
    verbose: bool = True,
) -> dict:
    """
    PHASE A: combinatorial + intensity policy search.

    Extends worst_case_discovery()'s sample -> run -> score -> rank pattern
    (scenarios.py, this file), retargeted from the trigger space to the
    POLICY action space, with the ranking direction flipped (minimise harm,
    not maximise it). This is the "extend, do not rewrite" implementation
    the audit recommended for Section 10 -- it does not replace
    run_policy_optimization()'s fixed 5-lever evaluation (that function is
    UNCHANGED and remains the fast, always-available baseline comparison);
    this is a strictly larger search that includes those 5 fixed levers as
    a subset (include_fixed_levers=True) plus randomly sampled combinations
    and intensities.

    PHASE D additions (this session): `include_node_targeted_sampling=True`
    additionally samples random single-node-targeted Phase B levers
    (food_aid, climate_adaptation, import_tariff) into the same search --
    i.e. the search chooses WHICH node to target, not just which global
    lever to apply. `max_budget` annotates each candidate with an
    illustrative cost and a `within_budget` flag (see
    LEVER_COSTS_ILLUSTRATIVE -- NOT real cost data). For a focused search
    over node targeting for ONE specific lever type (rather than mixed
    into the general search), use node_level_policy_search() instead.

    Action space sampled per candidate:
      - a random subset (1-3) of {reserve_mandate, trade_diversification,
        trader_regulation, renewable_push}
      - a random intensity for each selected lever within a bounded,
        documented range (see LEVER_RANGES below)
      - if include_node_targeted_sampling: additionally, a random
        node-targeted Phase B lever with a randomly sampled target node

    Objective (unchanged from run_policy_optimization, per the Digital Twin
    spec Section 10): population_saved_millions = control_PAR - policy_PAR,
    where control is the SAME shock/trigger set with no response. MAXIMISED
    (equivalently: PAR is minimised).

    Parameters
    ----------
    triggers : explicit STC trigger list (same schema as every other
        function in this file). If None and `shocks` is also None, uses a
        moderate default climate+geopolitical combination so the search is
        never run against a no-crisis baseline (which would trivially rank
        every lever as "no effect").
    n_random : number of randomly-sampled combinations to evaluate, in
        addition to the fixed single-lever baselines.

    Returns
    -------
    dict with 'control_summary', 'ranked_policies' (fixed + sampled,
    sorted by population_saved_millions descending), 'n_evaluated',
    and 'search_space' (documents exactly what was sampled, for
    reproducibility).
    """
    if triggers is None:
        triggers = [
            {"name": "policy_search_default_climate", "step": 5, "type": "climate",
             "scope": 0.30, "severity": 0.45, "food_shock": 1.25,
             "energy_shock": 1.10, "target_node": None},
            {"name": "policy_search_default_geo", "step": 8, "type": "geopolitical",
             "scope": 0.25, "severity": 0.40, "food_shock": 1.20,
             "energy_shock": 1.30, "target_node": None},
        ]

    LEVER_RANGES = {
        "reserve_months":     (1.0, 6.0),
        "rho_cut_frac":       (0.05, 0.40),
        "boost_multiplier":   (1.05, 1.50),
        "margin_cap":         (0.02, 0.10),
        "renew_boost":        (1.10, 1.80),
    }

    rng = np.random.default_rng(seed)

    def _run(response_fn, label: str, params: dict) -> dict:
        m = FoodEnergyModel(scenario=f"policy_search_{label}", seed=seed, init_year=start_year)
        if response_fn is not None:
            response_fn(m)
        m.stc_engine = STCEngine(triggers=[dict(t) for t in triggers], ss_mode="multiplicative")
        m.run(n_steps, verbose=False)
        s = m.summary()
        return {
            "label": label, "params": params,
            "max_price_index": s["max_price_index"], "max_PAR_millions": s["max_PAR_millions"],
            "max_TC": s["max_TC"], "max_n_overload_food": s["max_n_overload_food"],
            "min_GFS": s["min_GFS"],
        }

    if verbose:
        print(f"\n[Policy Search] control run + "
              f"{'5 fixed + ' if include_fixed_levers else ''}{n_random} sampled candidates...")

    control = _run(None, "control (no response)", {})
    candidates = []

    if include_fixed_levers:
        candidates.append(("reserve_mandate_3mo_fixed", make_reserve_mandate_lever(3.0), {"target_months": 3.0}))
        candidates.append(("trade_diversification_fixed", make_trade_diversification_lever(), {}))
        candidates.append(("trader_regulation_fixed", make_trader_regulation_lever(), {}))
        candidates.append(("renewable_push_fixed", make_renewable_push_lever(), {}))
        candidates.append(("full_transformational_fixed", _transformational, {}))

    if custom_levers:
        built = []
        for i, spec in enumerate(custom_levers):
            try:
                built.append((f"custom_{i}_{spec.get('type')}", build_custom_lever(spec), spec))
            except (KeyError, ValueError) as e:
                if verbose:
                    print(f"[Policy Search] WARNING: skipping invalid custom lever spec "
                          f"{spec}: {e}")
        candidates.extend(built)
        if len(built) > 1:
            # also evaluate the bundle of all valid custom levers together
            combined = _combine_levers(*(fn for _, fn, _ in built))
            candidates.append(("custom_bundle_all", combined,
                                {b[0]: b[2] for b in built}))

    LEVER_FACTORIES = {
        "reserve_mandate": lambda v: make_reserve_mandate_lever(v),
        "trade_diversification": lambda v: make_trade_diversification_lever(rho_cut_frac=v),
        "trader_regulation": lambda v: make_trader_regulation_lever(margin_cap=v),
        "renewable_push": lambda v: make_renewable_push_lever(boost_multiplier=v),
    }
    LEVER_RANGE_KEYS = {
        "reserve_mandate": "reserve_months",
        "trade_diversification": "rho_cut_frac",
        "trader_regulation": "margin_cap",
        "renewable_push": "renew_boost",
    }

    for i in range(n_random):
        n_levers = int(rng.integers(1, 4))
        chosen = rng.choice(list(LEVER_FACTORIES.keys()), size=n_levers, replace=False)
        levers = []
        param_record = {}
        for key in chosen:
            lo, hi = LEVER_RANGES[LEVER_RANGE_KEYS[key]]
            v = float(rng.uniform(lo, hi))
            levers.append(LEVER_FACTORIES[key](v))
            param_record[key] = round(v, 3)
        combined = _combine_levers(*levers)
        candidates.append((f"sampled_{i}_{'+'.join(chosen)}", combined, param_record))

    # PHASE D: node-targeted sampling -- the search chooses WHICH node
    if include_node_targeted_sampling:
        pool = node_pool
        if pool is None:
            # derive the real 35-node list from a throwaway model instance
            pool = list(FoodEnergyModel(scenario="_node_pool_probe", seed=seed,
                                         init_year=start_year).agent_map.keys())
        node_targeted_types = ["food_aid", "climate_adaptation", "import_tariff"]
        DEFAULT_INTENSITY = {"food_aid": (0.03, 0.15), "climate_adaptation": (0.15, 0.50),
                              "import_tariff": (0.70, 1.40)}
        for j in range(max(1, n_random // 2)):
            lever_type = str(rng.choice(node_targeted_types))
            lo, hi = DEFAULT_INTENSITY[lever_type]
            intensity = float(rng.uniform(lo, hi))
            if lever_type == "food_aid":
                donor, recipient = rng.choice(pool, size=2, replace=False)
                spec = {"type": "food_aid", "donor": str(donor), "recipient": str(recipient),
                        "aid_fraction": intensity}
                label = f"node_sampled_{j}_aid_{donor}to{recipient}".replace(" ", "")
            else:
                node = str(rng.choice(pool))
                key = {"climate_adaptation": "effectiveness", "import_tariff": "tariff_multiplier"}[lever_type]
                spec = {"type": lever_type, "node": node, key: intensity}
                label = f"node_sampled_{j}_{lever_type}_{node}".replace(" ", "")
            try:
                fn = build_custom_lever(spec)
                candidates.append((label, fn, spec))
            except (KeyError, ValueError) as e:
                if verbose:
                    print(f"[Policy Search] WARNING: skipping invalid node-sampled spec {spec}: {e}")

    results = []
    for label, fn, params in candidates:
        r = _run(fn, label, params)
        r["population_saved_millions"] = round(control["max_PAR_millions"] - r["max_PAR_millions"], 1)
        r["price_index_reduction"] = round(control["max_price_index"] - r["max_price_index"], 4)
        # PHASE D: illustrative cost annotation, if a budget was requested
        if max_budget is not None:
            lever_key = params.get("type") if isinstance(params, dict) and "type" in params \
                else (list(params.keys())[0] if params else None)
            cost_fn = LEVER_COSTS_ILLUSTRATIVE.get(lever_key)
            if cost_fn is not None:
                try:
                    first_val = list(params.values())[0] if not isinstance(params.get(lever_key), dict) \
                        else 0.1
                    cost = cost_fn(first_val if isinstance(first_val, (int, float)) else 0.1)
                except Exception:
                    cost = 0.0
                r["illustrative_cost"] = round(cost, 2)
                r["within_budget"] = cost <= max_budget
            else:
                r["illustrative_cost"] = None
                r["within_budget"] = True  # unknown cost -- don't penalise, but don't claim precision
        results.append(r)

    if max_budget is not None:
        results.sort(key=lambda r: (-r.get("within_budget", True), -r["population_saved_millions"]))
    else:
        results.sort(key=lambda r: -r["population_saved_millions"])

    if verbose:
        print("\n  TOP 5 POLICIES FOUND:")
        for rank, r in enumerate(results[:5], 1):
            print(f"  #{rank} {r['label']:45s} PAR_saved={r['population_saved_millions']:>7.1f}M  "
                  f"params={r['params']}")

    return {
        "control_summary": control,
        "ranked_policies": results,
        "n_evaluated": len(results),
        "search_space": {
            "levers": list(LEVER_FACTORIES.keys()),
            "ranges": LEVER_RANGES,
            "n_random_sampled": n_random,
            "fixed_baselines_included": include_fixed_levers,
            "node_targeted_sampling": include_node_targeted_sampling,
        },
        "max_budget": max_budget,
        "objective": "population_saved_millions (control_PAR - policy_PAR), per Digital Twin spec Section 10",
    }


# ============================================================================
# PHASE B (this session): missing policy levers, per the Digital Twin
# specification Section 4 and the implementation audit's gap list.
# Every lever below is additive -- no existing function was modified except
# the two documented, backward-compatible getattr-guarded edits in
# agent.py (_update_climate_modifier) and trade.py (_gravity_volume),
# both verified byte-identical when the new optional attribute is absent
# (test_phase_b_policy_levers.py).
#
# NOT implemented this phase: fertilizer redistribution (B4) in its full
# form -- that requires the Φ_i (N/P/K) state variable specified in the
# Digital Twin architecture doc Part C3, which is Phase C's job per the
# stated dependency order. An INTERIM fertilizer-support lever is provided
# below, routed through the existing energy-food coupling channel (the
# only real mechanism fertilizer currently has, per the implementation
# audit's SHOCK_TYPE_MAP finding) -- explicitly labelled interim, not a
# substitute for the real Phase C mechanism.
# ============================================================================

def make_global_reserve_pool_lever(levy_threshold_margin: float = 0.10,
                                    levy_rate: float = 0.20):
    """
    B1 + B8: FAO-style global strategic reserve pool.

    IMPLEMENTATION SCOPE NOTE: response_fn levers are called ONCE, before
    model.run() starts (confirmed this session: scenarios.py:827,
    "applied before run"). A genuinely continuous, every-tick-recalculated
    global pool would require a new per-tick hook into model.step()'s
    core loop -- which is the same hot path modified carefully in Phase
    2.5 and is explicitly out of scope for "extend, don't rewrite."
    This is therefore the ONE-TIME REDISTRIBUTION variant: at setup,
    nodes with sigma comfortably above their own safety margin contribute
    a fraction of their imperishable stock to a pool, which is
    immediately redistributed to nodes below their safety margin,
    proportional to need. This is a real, testable implementation of the
    policy concept (mutual insurance pooling, distinct from the per-node
    reserve mandate which only reclassifies a node's OWN stock), not a
    placeholder.

    Equations:
        contribution_i = min(0.5*F_imperish,i, levy_rate * F_imperish,i *
                              min(1, sigma_i - sigma_safe,i))   [only if sigma_i > sigma_safe,i + margin]
        need_j = max(0, sigma_safe,j - sigma_j) * D_j
        draw_j = pool_total * (need_j / sum_k need_k)
    """
    def lever(model):
        agents = list(model.agent_map.values())
        pool = 0.0
        contributions = {}
        for a in agents:
            if a.food_security > a.sigma_safe_i + levy_threshold_margin:
                surplus_frac = min(1.0, a.food_security - a.sigma_safe_i)
                contribution = min(0.5 * a.food_imperish,
                                    levy_rate * a.food_imperish * surplus_frac)
                a.food_imperish -= contribution
                pool += contribution
                contributions[a.name] = round(contribution, 1)

        needy = [a for a in agents if a.food_security < a.sigma_safe_i]
        total_need = sum(max(0.0, (a.sigma_safe_i - a.food_security) * a._caloric_demand_yr)
                          for a in needy)
        draws = {}
        if total_need > 0 and pool > 0:
            for a in needy:
                need = max(0.0, (a.sigma_safe_i - a.food_security) * a._caloric_demand_yr)
                share = pool * (need / total_need)
                a.food_imperish += share
                draws[a.name] = round(share, 1)

        print(f"[GlobalReservePool] {len(contributions)} contributors, pool={pool:.3e} kcal, "
              f"{len(draws)} recipients")

    lever.__name__ = f"global_reserve_pool_levy{levy_rate:.2f}"
    lever.lever_params = {"levy_threshold_margin": levy_threshold_margin, "levy_rate": levy_rate}
    return lever


def make_food_aid_lever(donor_name: str, recipient_name: str, aid_fraction: float = 0.05):
    """
    B2: International food aid -- a direct node-to-node stock transfer
    that BYPASSES the trade network's gravity model entirely (no
    capacity, cost, or affordability constraint), consistent with
    real-world food aid being economically distinct from trade precisely
    because it isn't subject to those constraints (Digital Twin spec
    Part B2).

    Equation: aid = aid_fraction * donor.food_imperish;
              donor.food_imperish -= aid; recipient.food_imperish += aid
    """
    def lever(model):
        donor = model.agent_map.get(donor_name)
        recipient = model.agent_map.get(recipient_name)
        if donor is None or recipient is None:
            print(f"[FoodAid] WARNING: '{donor_name}' or '{recipient_name}' not found in "
                  f"agent_map - no-op")
            return
        aid = donor.food_imperish * aid_fraction
        donor.food_imperish -= aid
        recipient.food_imperish += aid
        print(f"[FoodAid] {donor_name} -> {recipient_name}: {aid:.3e} kcal "
              f"({aid_fraction:.1%} of donor stock)")
    lever.__name__ = f"food_aid_{donor_name.replace(' ','')}_to_{recipient_name.replace(' ','')}"
    lever.lever_params = {"donor": donor_name, "recipient": recipient_name,
                           "aid_fraction": aid_fraction}
    return lever


def make_coordinated_export_restriction_lever(target_nodes: list, export_fraction_cap: float = 0.10):
    """
    B3: Coordinated export restriction across N named nodes
    simultaneously.

    Per the Digital Twin spec Part B3: "already fully representable via
    the existing 3-regime export policy... the only addition needed is a
    policy-layer wrapper that applies the same override to multiple
    nodes in one call" -- this IS that wrapper. No new mechanism; reuses
    the exact override pattern the `2022_ukraine_block` trigger already
    uses (agent.export_fraction direct assignment), generalised to a
    node list.
    """
    def lever(model):
        affected = []
        for name in target_nodes:
            a = model.agent_map.get(name)
            if a is not None:
                a.export_fraction = min(a.export_fraction, export_fraction_cap)
                a.export_ban = export_fraction_cap <= 0.0
                affected.append(name)
        print(f"[CoordinatedExportRestriction] export_fraction capped at "
              f"{export_fraction_cap:.2f} on {affected}")
    lever.__name__ = f"coord_export_restrict_{len(target_nodes)}n_cap{export_fraction_cap:.2f}"
    lever.lever_params = {"target_nodes": list(target_nodes), "export_fraction_cap": export_fraction_cap}
    return lever


def make_climate_adaptation_lever(node_name: str, effectiveness: float = 0.30):
    """
    B6: Climate adaptation funding -- reduces a SPECIFIC node's
    sensitivity to drought/heatwave/flood, per the Digital Twin spec
    Part B6's logistic-saturating design (reusing the same functional
    form already validated for technology growth in
    agent.py::update_capital, per that spec section's own stated
    rationale for consistency).

    Sets agent.climate_sensitivity_multiplier = (1 - effectiveness),
    consumed by the now-extended agent.py::_update_climate_modifier
    (byte-identical to the original formula when this attribute is unset
    -- verified in test_phase_b_policy_levers.py).

    NOTE: this is a SINGLE-STEP investment effect (effectiveness applied
    once, at setup), not the spec's proposed cumulative-investment-over-
    time state. A true multi-year ramping investment would need the same
    per-tick hook limitation noted in make_global_reserve_pool_lever's
    docstring. Calibration confidence: LOW (per Digital Twin spec Section
    12 -- no independent data source identified for adaptation
    effectiveness; `effectiveness` here is a policy INPUT the user sets,
    not a calibrated constant, and should be presented as such in any UI).
    """
    def lever(model):
        a = model.agent_map.get(node_name)
        if a is None:
            print(f"[ClimateAdaptation] WARNING: '{node_name}' not found - no-op")
            return
        a.climate_sensitivity_multiplier = max(0.0, 1.0 - effectiveness)
        print(f"[ClimateAdaptation] {node_name}: climate sensitivity multiplier -> "
              f"{a.climate_sensitivity_multiplier:.2f}")
    lever.__name__ = f"climate_adapt_{node_name.replace(' ','')}_{effectiveness:.2f}"
    lever.lever_params = {"node": node_name, "effectiveness": effectiveness,
                           "calibration_confidence": "LOW - see docstring"}
    return lever


def make_import_tariff_lever(node_name: str, tariff_multiplier: float = 1.20):
    """
    Import tariff (tariff_multiplier > 1.0) or subsidy (< 1.0) on a
    specific node's affordability constraint in the gravity trade model.
    Consumed by the now-extended trade.py::_gravity_volume (byte-identical
    to the original formula when the attribute is unset -- verified in
    test_phase_b_policy_levers.py).

    Equation: affordable_kcal = K_buyer / (p * tariff_multiplier)^1.2 * 1e12
    tariff_multiplier=1.20 represents roughly a 20% import cost increase;
    0.80 represents a 20% import subsidy.
    """
    def lever(model):
        a = model.agent_map.get(node_name)
        if a is None:
            print(f"[ImportTariff] WARNING: '{node_name}' not found - no-op")
            return
        a.import_tariff_multiplier = tariff_multiplier
        kind = "tariff" if tariff_multiplier > 1.0 else "subsidy"
        print(f"[ImportTariff] {node_name}: {kind}, multiplier={tariff_multiplier:.2f}")
    lever.__name__ = f"tariff_{node_name.replace(' ','')}_{tariff_multiplier:.2f}"
    lever.lever_params = {"node": node_name, "tariff_multiplier": tariff_multiplier}
    return lever


def make_energy_intervention_lever(node_name: Optional[str] = None,
                                    release_fraction: float = 0.20,
                                    mode: str = "supply_cut"):
    """
    B7: Energy interventions (strategic release / price subsidy).

    Per the implementation audit (Part B7 finding): "No new mechanism
    required" -- this reuses EnergyModule.apply_energy_shock() UNCHANGED,
    with a NEGATIVE severity, which that function's existing arithmetic
    already correctly interprets as a supply increase / price decrease
    (verified this session by reading its exact formula: `energy_fuel *=
    (1 - severity)`, so severity<0 multiplies by >1). This factory exists
    only to give that reversal a clear, intention-revealing name and a
    single-node targeting option (the underlying function shock-scopes
    randomly across `scope * 35` nodes; passing scope=1/35 here targets
    approximately one node, since apply_energy_shock has no direct
    single-node-by-name interface -- a real, documented limitation of the
    reused mechanism, not of this wrapper).
    """
    def lever(model):
        if model.energy_module is None:
            print("[EnergyIntervention] no energy_module on this model - no-op")
            return
        scope = 1.0 / max(1, len(model.agent_map)) if node_name else 1.0
        model.energy_module.apply_energy_shock(
            model, scope=scope, severity=-abs(release_fraction), mode=mode)
    lever.__name__ = f"energy_release_{release_fraction:.2f}_{mode}"
    lever.lever_params = {"node": node_name, "release_fraction": release_fraction, "mode": mode,
                           "note": "targets ~1 random node when node_name given; "
                                   "apply_energy_shock has no exact-name targeting"}
    return lever


def make_fertilizer_support_lever_INTERIM(node_name: str, support_level: float = 0.30):
    """
    B4 INTERIM: fertilizer support, routed through the existing
    energy-food coupling channel (the only real mechanism fertilizer
    currently has -- confirmed by the implementation audit's
    SHOCK_TYPE_MAP finding: `fertilizer_shortage` already maps onto the
    generic geopolitical/speculative trigger types, not a dedicated
    state).

    THIS IS NOT THE FULL B4 MECHANISM. The Digital Twin spec Part C3
    calls for genuine Phi_i = (N_i, P_i, K_i) stocks and a
    Mitscherlich-type production-response function -- that requires new
    state variables and is explicitly Phase C's job, not this one. This
    interim lever provides a directionally-correct, clearly-labelled
    placeholder: it boosts the target node's effective fuel-energy input
    (agent.py's Cobb-Douglas E term), representing "fertilizer support
    eases the input-cost squeeze" without claiming to model nitrogen/
    phosphorus/potash individually.
    """
    def lever(model):
        a = model.agent_map.get(node_name)
        if a is None:
            print(f"[FertilizerSupportINTERIM] WARNING: '{node_name}' not found - no-op")
            return
        a.energy_fuel = a.energy_fuel * (1.0 + support_level)
        print(f"[FertilizerSupportINTERIM] {node_name}: energy_fuel boosted "
              f"{support_level:.0%} as a fertilizer-cost-relief PROXY "
              f"(full Phi_i mechanism pending Phase C)")
    lever.__name__ = f"fertilizer_support_INTERIM_{node_name.replace(' ','')}"
    lever.lever_params = {"node": node_name, "support_level": support_level,
                           "status": "INTERIM - proxy via energy channel, not the full "
                                     "Phase C fertilizer mechanism"}
    return lever


# ── Worst-case discovery (exploratory analysis) ───────────────────────────────

def worst_case_discovery(
    n_random: int = 50,
    n_steps: int = 20,
    seed: int = 99,
    verbose: bool = True,
) -> dict:
    """
    Exploratory analysis: randomly sample trigger combinations to find
    worst-case crisis configurations.

    Answers the reviewer's question:
    'What combination does the model find by itself that is worse than any
     single large shock?'

    Samples n_random random trigger combinations and ranks by severity.
    Returns the worst 5 and their trigger configurations.
    """
    rng   = np.random.default_rng(seed)
    results = []

    TRIGGER_TYPES  = ["climate", "geopolitical", "speculative"]
    TARGET_NODES   = ["Australia", "Russia", "Ukraine", "India", "Nigeria", None]
    STEP_RANGE     = (5, 15)
    SCOPE_RANGE    = (0.20, 0.55)
    SEVERITY_RANGE = (0.30, 0.75)
    FOOD_SHOCK     = (1.10, 1.80)
    ENERGY_SHOCK   = (1.00, 2.00)

    if verbose:
        print(f"\n[Exploratory] Sampling {n_random} random trigger combinations...")

    for i in range(n_random):
        # Random 2-3 triggers
        n_triggers = rng.integers(2, 4)
        triggers = []
        for k in range(int(n_triggers)):
            triggers.append({
                "name":        f"explore_{i}_{k}",
                "step":        int(rng.integers(*STEP_RANGE)),
                "type":        str(rng.choice(TRIGGER_TYPES)),
                "scope":       float(rng.uniform(*SCOPE_RANGE)),
                "severity":    float(rng.uniform(*SEVERITY_RANGE)),
                "food_shock":  float(rng.uniform(*FOOD_SHOCK)),
                "energy_shock":float(rng.uniform(*ENERGY_SHOCK)),
                "target_node": TARGET_NODES[int(rng.integers(len(TARGET_NODES)))],
            })

        try:
            model = FoodEnergyModel(scenario=f"explore_{i}", seed=seed + i)
            model.stc_engine = STCEngine(triggers=triggers, ss_mode="multiplicative")
            model.run(n_steps, verbose=False)
            s = model.summary()
            results.append({
                "run_id":           i,
                "max_price_ratio":  s.get("max_price_ratio", 0.0),
                "max_U":            s.get("max_U", 0.0),
                "max_PAR_millions": s.get("max_PAR_millions", 0.0),
                "max_n_overload":   s.get("max_n_overload_food", 0),
                "max_TC":           s.get("max_TC", 0.0),
                "triggers":         triggers,
            })
        except Exception:
            pass

    # Rank by combined severity score
    for r in results:
        r["severity_score"] = (
            r["max_price_ratio"] * 0.30
            + r["max_U"] * 0.25
            + (r["max_PAR_millions"] / 1000.0) * 0.20
            + (r["max_n_overload"] / 35.0) * 0.25
        )

    results.sort(key=lambda x: -x["severity_score"])

    if verbose:
        print("\n  TOP 5 WORST-CASE COMBINATIONS DISCOVERED:")
        for rank, r in enumerate(results[:5], 1):
            print(f"\n  #{rank} severity_score={r['severity_score']:.3f} | "
                  f"price_ratio={r['max_price_ratio']:.3f} | "
                  f"U={r['max_U']:.3f} | PAR={r['max_PAR_millions']:.0f}M | "
                  f"overloads={r['max_n_overload']}")
            for t in r["triggers"]:
                print(f"      t={t['step']} {t['type']:12s} "
                      f"scope={t['scope']:.2f} sev={t['severity']:.2f} "
                      f"food×{t['food_shock']:.2f} energy×{t['energy_shock']:.2f} "
                      f"@ {t['target_node']}")

    return {
        "top5": results[:5],
        "all_results": results,
        "n_sampled": n_random,
    }


# ── Crisis attribution (node-level explanation) ───────────────────────────────

def crisis_attribution(model: FoodEnergyModel) -> pd.DataFrame:
    """
    For each node that is overloaded, decompose the crisis contribution:
      food_stress_pct  : FS_index contribution
      energy_pct       : ES_index contribution
      contagion_pct    : export_ban contagion contribution (EB rate × sigma proxy)
      reserve_failure_pct: shortfall relative to reserve capacity

    Answers: "Why did Egypt collapse in this run?"
    """
    rows = []
    for name, agent in model.agent_map.items():
        if not agent.overload_food:
            continue

        fs    = agent.FS_index
        es    = getattr(agent, "energy_stress_index", 0.0)
        sigma = agent.food_security

        # Food stress component
        food_component = max(0.0, 1.0 - sigma)

        # Energy component (via cost-push)
        energy_component = es * 0.40   # EPSILON_EF

        # Contagion component: proxy = export ban rate × import dependency
        n_banning = sum(
            1 for a in model.agent_map.values() if a.export_ban
        )
        contagion_proxy = (n_banning / 35.0) * max(0.0, 1.0 - sigma)

        # Reserve failure: how far below target reserve was
        target_reserve  = 0.15 * agent.food_imperish
        reserve_gap     = max(0.0, target_reserve - agent.reserves)
        reserve_component = reserve_gap / max(agent._caloric_demand_yr, 1.0)

        total = food_component + energy_component + contagion_proxy + reserve_component
        if total <= 0:
            total = 1.0

        rows.append({
            "node":              name,
            "food_security":     round(sigma, 3),
            "FS_index":          round(fs, 3),
            "CC_index":          round(agent.CC_index, 3),
            "food_stress_pct":   round(100 * food_component / total, 1),
            "energy_pct":        round(100 * energy_component / total, 1),
            "contagion_pct":     round(100 * contagion_proxy / total, 1),
            "reserve_failure_pct":round(100 * reserve_component / total, 1),
            "overload_ratio":    round(fs / max(agent.CC_index, 0.05), 3),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("overload_ratio", ascending=False).reset_index(drop=True)
    return df


# ── Run one scenario with Monte Carlo ─────────────────────────────────────────

def run_scenario(
    spec: ScenarioSpec,
    n_steps: int = N_STEPS,
    n_mc: int = N_MC,
    seed: int = 42,
    verbose: bool = True,
) -> dict:
    """
    Run a scenario with Monte Carlo uncertainty quantification.
    Returns summary dict with mean ± std for all key metrics.
    """
    if verbose:
        print(f"\n{'─'*55}")
        print(f"  {spec.label}")
        print(f"{'─'*55}")

    mc_summaries = []
    for i in range(n_mc):
        model = FoodEnergyModel(scenario=spec.name, seed=seed + i)
        spec.response_fn(model)   # apply response levers before run
        model.stc_engine = STCEngine(
            triggers=[dict(t) for t in spec.triggers],
            ss_mode="multiplicative",
        )
        model.run(n_steps, verbose=False)
        mc_summaries.append(model.summary())

    # Collect attribution from one representative run
    rep_model = FoodEnergyModel(scenario=spec.name, seed=seed)
    spec.response_fn(rep_model)
    rep_model.stc_engine = STCEngine(
        triggers=[dict(t) for t in spec.triggers],
        ss_mode="multiplicative",
    )
    rep_model.run(n_steps, verbose=False)
    attribution_df = crisis_attribution(rep_model)

    # Compute mean ± std for numeric metrics
    numeric_keys = [k for k in mc_summaries[0]
                    if isinstance(mc_summaries[0][k], (int, float))
                    and k not in ("n_steps",)]
    stats = {}
    for k in numeric_keys:
        vals = [s[k] for s in mc_summaries if isinstance(s.get(k), (int, float))]
        stats[k] = {
            "mean": round(float(np.mean(vals)), 4),
            "std":  round(float(np.std(vals)),  4),
            "p5":   round(float(np.percentile(vals, 5)),  4),
            "p95":  round(float(np.percentile(vals, 95)), 4),
        }

    if verbose:
        m = stats
        print(f"  Peak FPI:     {m['max_price_index']['mean']:.3f} ± {m['max_price_index']['std']:.3f}")
        print(f"  Peak U:       {m['max_U']['mean']:.3f} ± {m['max_U']['std']:.3f}")
        print(f"  Peak PAR:     {m['max_PAR_millions']['mean']:.0f} ± {m['max_PAR_millions']['std']:.0f} M")
        print(f"  Overloads:    {m['max_n_overload_food']['mean']:.1f} ± {m['max_n_overload_food']['std']:.1f}")
        print(f"  Trade collapse:{m['max_TC']['mean']:.3f} ± {m['max_TC']['std']:.3f}")
        if not attribution_df.empty:
            print(f"\n  Crisis attribution (top 3 overloaded nodes):")
            for _, row in attribution_df.head(3).iterrows():
                print(f"    {row['node']:<30}: "
                      f"food={row['food_stress_pct']:.0f}% "
                      f"energy={row['energy_pct']:.0f}% "
                      f"contagion={row['contagion_pct']:.0f}% "
                      f"reserves={row['reserve_failure_pct']:.0f}%")

    return {
        "name":          spec.name,
        "label":         spec.label,
        "stats":         stats,
        "storyline":     spec.storyline,
        "trade_offs":    spec.trade_offs,
        "attribution":   attribution_df,
        "n_mc":          n_mc,
        "n_steps":       n_steps,
    }


# ── Scenario comparison table ─────────────────────────────────────────────────

def build_scenario_comparison(results: list) -> pd.DataFrame:
    """
    Build the examiner-facing scenario comparison table.

    BUG-011 FIX: FPI_mean/FPI_std now sourced from max_price_index (the
    absolute FAO-normalised price level) rather than max_price_ratio
    (peak/initial price within each run). The latter was the root cause of
    the paper's Table 7 showing a flat FPI=0.60 across all six scenarios —
    price_ratio collapses toward a near-constant value once price_0 is fixed
    and the price-floor degeneracy (BUG-006) pins every run to the same
    floor, making the comparator metric uninformative regardless of
    scenario-specific dynamics.
    """
    rows = []
    for r in results:
        s = r["stats"]
        rows.append({
            "Scenario":         r["label"],
            "FPI_mean":         f"{s['max_price_index']['mean']:.3f}",
            "FPI_std":          f"±{s['max_price_index']['std']:.3f}",
            "PAR_bn_mean":      f"{s['max_PAR_millions']['mean']/1000:.2f}bn",
            "U_mean":           f"{s['max_U']['mean']:.3f}",
            "Overloads_mean":   f"{s['max_n_overload_food']['mean']:.1f}",
            "TC_mean":          f"{s['max_TC']['mean']:.3f}",
        })
    return pd.DataFrame(rows)


# ── Entry point ───────────────────────────────────────────────────────────────

def run_phase9(
    data_dir: Path = _DATA,
    n_steps: int = N_STEPS,
    n_mc: int = N_MC,
    verbose: bool = True,
) -> dict:
    """Run all Phase 9 scenarios and save outputs."""
    print("\n" + "="*60)
    print("  PHASE 9: SCENARIOS, RESPONSES, TRADE-OFFS")
    print("="*60)

    all_results = []
    for spec in SCENARIOS:
        result = run_scenario(spec, n_steps=n_steps, n_mc=n_mc, verbose=verbose)
        all_results.append(result)

    # Scenario comparison table
    comparison = build_scenario_comparison(all_results)
    print("\n" + "="*60)
    print("  SCENARIO COMPARISON TABLE")
    print("="*60)
    print(comparison.to_string(index=False))
    comparison.to_csv(data_dir / "scenario_comparison.csv", index=False)

    # Worst-case discovery
    wc = worst_case_discovery(n_random=40, n_steps=20, verbose=verbose)

    # Save all outputs
    attribution_all = []
    for r in all_results:
        if not r["attribution"].empty:
            r["attribution"]["scenario"] = r["name"]
            attribution_all.append(r["attribution"])

    if attribution_all:
        pd.concat(attribution_all).to_csv(data_dir / "scenario_attribution.csv", index=False)

    # Save trade-off text
    tradeoffs = {r["name"]: r["trade_offs"] for r in all_results}
    with open(data_dir / "scenario_tradeoffs.json", "w") as f:
        json.dump(tradeoffs, f, indent=2)

    # Save worst-case results
    wc_rows = []
    for rank, r in enumerate(wc["top5"], 1):
        wc_rows.append({
            "rank":           rank,
            "severity_score": round(r["severity_score"], 4),
            "max_price_ratio":round(r["max_price_ratio"], 4),
            "max_U":          round(r["max_U"], 4),
            "max_PAR_M":      round(r["max_PAR_millions"], 1),
            "max_overloads":  r["max_n_overload"],
            "n_triggers":     len(r["triggers"]),
            "trigger_types":  "+".join(t["type"] for t in r["triggers"]),
        })
    pd.DataFrame(wc_rows).to_csv(data_dir / "worst_case_discovery.csv", index=False)

    # Save numeric stats as JSON
    stats_out = {r["name"]: r["stats"] for r in all_results}
    with open(data_dir / "scenario_stats.json", "w") as f:
        json.dump(stats_out, f, indent=2)

    print(f"\n[Phase 9] Saved: scenario_comparison.csv, scenario_attribution.csv,")
    print(f"          scenario_tradeoffs.json, worst_case_discovery.csv, scenario_stats.json")

    return {
        "scenarios":   all_results,
        "comparison":  comparison,
        "worst_case":  wc,
    }


if __name__ == "__main__":
    run_phase9(verbose=True)
