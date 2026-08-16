"""
phase2_5_ablation.py
---------------------
Controlled ablation experiments for the baseline (no-trigger) premature
overload investigation. Each experiment changes exactly ONE mechanism
relative to the unmodified control, using seed=42, init_year=2022,
zero triggers, and reports n_overloaded_food after step 1 (the step
where the premature wave is observed in every scenario run so far).
"""
import sys, copy
sys.path.insert(0, '.')
import numpy as np
from model import FoodEnergyModel
from trade import execute_trade_step
import stc_engine as stc_mod
from stc_engine import STCEngine


def run_control(seed=42, init_year=2022, n_steps=1):
    m = FoodEnergyModel(scenario='ctrl', seed=seed, init_year=init_year)
    m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')
    for _ in range(n_steps):
        m.step()
    overloaded = [n for n, a in m.agent_map.items() if a.overload_food]
    return overloaded, m


def experiment_stc_after_trade(seed=42, init_year=2022):
    """
    Hypothesis test: does moving the STC engine's overload check to AFTER
    trade resolves (instead of before, as the code currently does) remove
    the premature overload of import-dependent nodes?
    Manually replicates FoodEnergyModel.step()'s sequence with stc_engine
    moved after trade + the post-trade sigma/FS_index recompute.
    """
    m = FoodEnergyModel(scenario='post_trade_stc', seed=seed, init_year=init_year)
    m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')

    agents = list(m.agent_map.values())
    if m.energy_module is not None:
        m.energy_module.step(m)
    for agent in agents:
        agent.step()                      # pre-trade produce/consume/sigma/FS_index

    # Trade FIRST (moved up)
    pre = {n: a.food_imperish for n, a in m.agent_map.items()}
    execute_trade_step(m)
    post = {n: a.food_imperish for n, a in m.agent_map.items()}
    trade_volume = sum(max(0.0, post[n] - pre[n]) for n in m.agent_map)

    # Post-trade sigma/FS_index recompute (BUG-013 fix logic)
    for agent in agents:
        agent.compute_food_security()
        agent._compute_FS_index()

    # STC engine NOW (moved after trade, using post-trade FS_index)
    m.stc_engine.step(m)

    overloaded = [n for n, a in m.agent_map.items() if a.overload_food]
    return overloaded, m


def experiment_disable_fs_equilibrium_init(seed=42, init_year=2022):
    """FS normalization off: revert to FS_index(0)=0 instead of the
    undernourishment-baseline equilibrium proxy."""
    m = FoodEnergyModel(scenario='no_fs_init', seed=seed, init_year=init_year)
    for a in m.agent_map.values():
        a.FS_index = 0.0   # override the equilibrium proxy after __init__
    m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')
    m.step()
    overloaded = [n for n, a in m.agent_map.items() if a.overload_food]
    return overloaded, m


def experiment_disable_cc_floor(seed=42, init_year=2022):
    """CC normalization off: remove the CC_index floor clip (0.05) that
    prevents near-zero-tech/high-risk nodes from having a near-zero
    denominator in the overload ratio."""
    orig = stc_mod.STCEngine._accumulate_stress

    def patched(self, model):
        orig(self, model)
        for a in model.agent_map.values():
            # Undo the floor: recompute without the 0.05 lower clip
            tech_norm = min(1.0, a.technology / 2.0)
            cap_factor = min(1.0, a.capital / 1000.0)
            reserve_factor = min(1.0, a.reserves / max(a._caloric_demand_yr * 0.15, 1.0))
            raw = (stc_mod.CC_TECH_WEIGHT * tech_norm
                   + stc_mod.CC_CAPITAL_WEIGHT * cap_factor
                   - stc_mod.CC_POLRISK_WEIGHT * a.political_risk
                   + stc_mod.CC_RESERVE_WEIGHT * reserve_factor
                   - stc_mod.CC_CLIMVULN_WEIGHT * a.climate_vuln)
            a.CC_index = float(np.clip(raw, -1.0, 1.0))  # only clip ceiling, no 0.05 floor

    stc_mod.STCEngine._accumulate_stress = patched
    try:
        m = FoodEnergyModel(scenario='no_cc_floor', seed=seed, init_year=init_year)
        m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')
        m.step()
        overloaded = [n for n, a in m.agent_map.items() if a.overload_food]
    finally:
        stc_mod.STCEngine._accumulate_stress = orig
    return overloaded, m


def experiment_reserve_weight_maxed(seed=42, init_year=2022):
    """Reserve normalization test: what if CC_RESERVE_WEIGHT were much
    larger (0.30 instead of 0.0031), i.e. reserves actually mattered a lot
    for coping capacity? Tests whether the near-zero calibrated reserve
    weight is what's suppressing CC for import-dependent nodes."""
    orig_w = stc_mod.CC_RESERVE_WEIGHT
    stc_mod.CC_RESERVE_WEIGHT = 0.30
    try:
        m = FoodEnergyModel(scenario='reserve_maxed', seed=seed, init_year=init_year)
        m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')
        m.step()
        overloaded = [n for n, a in m.agent_map.items() if a.overload_food]
    finally:
        stc_mod.CC_RESERVE_WEIGHT = orig_w
    return overloaded, m


def experiment_no_trade_ever(seed=42, init_year=2022, n_steps=1):
    """Trade off entirely: execute_trade_step never runs."""
    import trade as trade_mod
    orig = trade_mod.execute_trade_step
    trade_mod.execute_trade_step = lambda model: None
    import model as model_mod
    model_mod.execute_trade_step = lambda model: None
    try:
        m = FoodEnergyModel(scenario='no_trade', seed=seed, init_year=init_year)
        m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')
        for _ in range(n_steps):
            m.step()
        overloaded = [n for n, a in m.agent_map.items() if a.overload_food]
    finally:
        trade_mod.execute_trade_step = orig
        model_mod.execute_trade_step = orig
    return overloaded, m


def experiment_no_energy_food_coupling(seed=42, init_year=2022):
    """Energy-food coupling off: zero the es_contribution term in FS
    accumulation (0.20 * energy_stress_index)."""
    orig = stc_mod.STCEngine._accumulate_stress
    import inspect
    src = inspect.getsource(orig)
    # Monkeypatch by re-running the same logic with es_contribution forced to 0
    def patched(self, model):
        for agent in model.agent_map.values():
            sigma = agent.food_security
            sigma_safe = agent.sigma_safe_i
            stress_push = stc_mod.FS_ACCUMULATION_RATE * max(0.0, 1.0 - sigma)
            stress_pull = stc_mod.FS_DECAY_RATE * max(0.0, sigma - sigma_safe)
            es_contribution = 0.0   # <-- ABLATED
            climate_stress = 0.15 * (1.0 - agent.climate_modifier)
            agent.FS_index = float(np.clip(
                agent.FS_index + stress_push + es_contribution + climate_stress - stress_pull,
                0.0, 2.0))
            cap_factor = min(1.0, agent.capital / 1000.0)
            reserve_factor = min(1.0, agent.reserves / max(agent._caloric_demand_yr * 0.15, 1.0))
            tech_norm = min(1.0, agent.technology / 2.0)
            agent.CC_index = float(np.clip(
                stc_mod.CC_TECH_WEIGHT * tech_norm
                + stc_mod.CC_CAPITAL_WEIGHT * cap_factor
                - stc_mod.CC_POLRISK_WEIGHT * agent.political_risk
                + stc_mod.CC_RESERVE_WEIGHT * reserve_factor
                - stc_mod.CC_CLIMVULN_WEIGHT * agent.climate_vuln,
                0.05, 1.0))
    stc_mod.STCEngine._accumulate_stress = patched
    try:
        m = FoodEnergyModel(scenario='no_ef_coupling', seed=seed, init_year=init_year)
        m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')
        m.step()
        overloaded = [n for n, a in m.agent_map.items() if a.overload_food]
    finally:
        stc_mod.STCEngine._accumulate_stress = orig
    return overloaded, m


def experiment_no_contagion(seed=42, init_year=2022, n_steps=5):
    """Contagion off: RC_CONTAGION_BOOST forced to 0 (no export-ban-driven
    trade friction boost during a cascade window). Run 5 steps since
    contagion has no effect at step 1 (t<1 warm-up)."""
    orig = stc_mod.RC_CONTAGION_BOOST
    stc_mod.RC_CONTAGION_BOOST = 0.0
    try:
        m = FoodEnergyModel(scenario='no_contagion', seed=seed, init_year=init_year)
        m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')
        for _ in range(n_steps):
            m.step()
        overloaded = [n for n, a in m.agent_map.items() if a.overload_food]
    finally:
        stc_mod.RC_CONTAGION_BOOST = orig
    return overloaded, m


def experiment_no_a_i_rescaling(seed=42, init_year=2022):
    """A_i initialization off: force every node's A_i multiplier to 1.0
    instead of the calibrated/rescaled A_i_implied value."""
    m = FoodEnergyModel(scenario='no_ai', seed=seed, init_year=init_year)
    for a in m.agent_map.values():
        a.A_i = 1.0
    m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')
    m.step()
    overloaded = [n for n, a in m.agent_map.items() if a.overload_food]
    return overloaded, m


if __name__ == "__main__":
    experiments = [
        ("CONTROL (unmodified)", run_control),
        ("STC evaluated AFTER trade (not before)", experiment_stc_after_trade),
        ("FS normalization off (FS0=0, not equilibrium proxy)", experiment_disable_fs_equilibrium_init),
        ("CC normalization off (no 0.05 floor)", experiment_disable_cc_floor),
        ("Reserve weight maxed (0.30 instead of 0.0031)", experiment_reserve_weight_maxed),
        ("Trade off entirely (no trade, 1 step)", experiment_no_trade_ever),
        ("Energy-food coupling off (es_contribution=0)", experiment_no_energy_food_coupling),
        ("Contagion off (5 steps)", experiment_no_contagion),
        ("A_i initialization off (A_i=1.0 for all)", experiment_no_a_i_rescaling),
    ]
    results = {}
    for label, fn in experiments:
        overloaded, m = fn()
        results[label] = overloaded
        print(f"\n{'='*70}\n{label}\nn_overloaded={len(overloaded)}\n{sorted(overloaded)}")

    import json
    with open('/home/claude/proj/phase2_5_ablation_results.json', 'w') as f:
        json.dump({k: sorted(v) for k, v in results.items()}, f, indent=2)
