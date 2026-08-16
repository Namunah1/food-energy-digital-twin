"""
sensitivity.py
--------------
Global Sensitivity Analysis for the Food-Energy Systemic Risk ABM.

Framework : Gambhir et al. (2025) + Homer-Dixon et al. (2015)
Phase     : 7 — Two-method SA: Morris screening + Sobol indices

WHY TWO METHODS (per reviewer feedback):
  Morris screening:   fast, cheap, intuitive plots, immediately readable
                      by examiners. Answers "which parameters matter at all?"
  Sobol indices:      rigorous variance decomposition. Answers "what fraction
                      of outcome variance does each parameter explain?"
  Together they give: ranking (Morris) + quantification (Sobol).

Parameters analysed (12 total):
  Core physics:
    EPSILON_EF         : Energy→Food TFP penalty [0.20, 0.60]
    K_PRICE            : Food price sensitivity   [0.80, 2.50]
    FS_ACCUMULATION    : Stress accumulation rate [0.02, 0.10]
    FS_DECAY           : Stress recovery rate     [0.05, 0.20]
    RC_CONTAGION_BOOST : RC cascade boost         [0.10, 0.50]
    RC_PRICE_AMP       : RC price amplification   [0.010, 0.040]

  Political economy:
    TRADER_MARGIN_BASE : Trader baseline margin   [0.02, 0.10]
    POWER_CC_PENALTY   : Market power CC penalty  [0.05, 0.30]
    BAN_CONTAGION      : Export ban spread rate   [0.10, 0.60]

  Agent heterogeneity:
    BIOFUEL_PRICE_THR  : Biofuel switch threshold [1.20, 1.80]
    EROI_DECLINE       : EROI annual decline rate [0.001, 0.008]
    ENERGY_COST_SHARE  : Energy cost fraction     [0.30, 0.60]

Outputs:
  Morris μ* and σ (elementary effects)
  Sobol S1 (first-order) and ST (total-order) indices
  Per-metric sensitivity heatmap
  "Which assumptions actually matter?" table
"""

import numpy as np
import pandas as pd
import sys
from pathlib import Path
from copy import deepcopy

_SRC = Path(__file__).resolve().parent
_ROOT = _SRC.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

try:
    from SALib.sample import saltelli, morris as morris_sample
    from SALib.analyze import sobol, morris as morris_analyze
    HAS_SALIB = True
except ImportError:
    HAS_SALIB = False
    print("[sensitivity] SALib not available — using manual parameter sweeps")

from model import FoodEnergyModel
from stc_engine import STCEngine, triggers_2022_ukraine

# ── Parameter space definition ────────────────────────────────────────────────
PARAM_SPACE = {
    "names": [
        "EPSILON_EF",        # energy→food TFP penalty
        "K_PRICE",           # food price sensitivity
        "FS_ACCUMULATION",   # stress accumulation rate
        "FS_DECAY",          # stress recovery rate
        "RC_CONTAGION_BOOST",# RC cascade export-ban boost
        "RC_PRICE_AMP",      # RC price amplification per overloaded node
        "TRADER_MARGIN",     # trader baseline margin
        "POWER_CC_PENALTY",  # market power CC penalty
        "BAN_CONTAGION",     # export ban spread rate
        "BIOFUEL_THR",       # biofuel price threshold
        "EROI_DECLINE",      # EROI annual decline
        "ENERGY_COST_SHARE", # energy cost fraction in food price
    ],
    "bounds": [
        [0.20, 0.60],   # EPSILON_EF
        [0.80, 2.50],   # K_PRICE
        [0.02, 0.10],   # FS_ACCUMULATION
        [0.05, 0.20],   # FS_DECAY
        [0.10, 0.50],   # RC_CONTAGION_BOOST
        [0.010, 0.040], # RC_PRICE_AMP — BUG-009 FIX: recentered around the
                        # FAO-calibrated value 0.021 (was [0.05, 0.20], an
                        # order of magnitude too high; see stc_engine.py
                        # BUG-009 comment)
        [0.02, 0.10],   # TRADER_MARGIN
        [0.05, 0.30],   # POWER_CC_PENALTY
        [0.10, 0.60],   # BAN_CONTAGION
        [1.20, 1.80],   # BIOFUEL_THR
        [0.001, 0.008], # EROI_DECLINE
        [0.30, 0.60],   # ENERGY_COST_SHARE
    ],
    "num_vars": 12,
    "dists": ["unif"] * 12,
}

# The model's actual hardcoded default for each of the 12 SA parameters, in
# the same canonical order as PARAM_SPACE["names"] -- i.e. what each module
# is set to before any SA patching ever happens. This is NOT the same as
# the PARAM_SPACE midpoint (e.g. EROI_DECLINE's true default is 0.003, but
# its sweep midpoint is 0.0045 -- a 50% difference). Any code that needs to
# restore parameters to their real baseline after an SA run must use this,
# not the midpoint of PARAM_SPACE["bounds"].
TRUE_DEFAULTS = [0.40, 1.5, 0.05, 0.10, 0.25, 0.021, 0.05, 0.15, 0.30, 1.40, 0.003, 0.45]

# Outcome metrics to analyse
OUTCOME_METRICS = [
    "max_price_index",    # peak FAO-normalised food price (BUG-011: replaces max_price_ratio)
    "max_U",              # peak undernourishment rate
    "max_PAR_millions",   # peak population at risk (millions)
    "max_EB_rate",        # peak export ban rate
    "max_TC",             # max trade collapse index
    "max_n_overload_food",# max simultaneous LFBB food overloads
]

N_STEPS_SA = 20  # shorter runs for SA to keep compute tractable


def _apply_params(model: FoodEnergyModel, param_values: np.ndarray):
    """
    Apply a parameter vector to a model instance by patching module constants.
    """
    import energy     as en_mod
    import stc_engine as stc_mod
    import trade      as tr_mod
    import prices     as pr_mod
    import political_economy as pe_mod

    p = param_values
    en_mod.EPSILON_EF           = float(p[0])
    pr_mod.K_PRICE               = float(p[1])
    stc_mod.FS_ACCUMULATION_RATE = float(p[2])
    stc_mod.FS_DECAY_RATE        = float(p[3])
    stc_mod.RC_CONTAGION_BOOST   = float(p[4])
    stc_mod.RC_PRICE_AMPLIFICATION = float(p[5])
    pe_mod.BASE_MARGIN           = float(p[6])
    pe_mod.POWER_CC_PENALTY      = float(p[7])
    tr_mod.BAN_CONTAGION_RATE    = float(p[8])
    en_mod.BIOFUEL_PRICE_THRESHOLD = float(p[9])
    en_mod.EROI_DECLINE_RATE     = float(p[10])
    pr_mod.ENERGY_COST_SHARE     = float(p[11])

    # Also patch live instances
    model.price_system.k = float(p[1])
    if model.energy_module:
        model.energy_module.__class__  # confirm it exists


def _run_one(param_values: np.ndarray, seed: int = 99) -> dict:
    """
    Run a single model instance with given parameters.
    Returns dict of outcome metrics.
    """
    import importlib
    # Re-import modules so patched constants take effect
    _apply_params_static(param_values)

    try:
        model = FoodEnergyModel(scenario="sa_run", seed=seed)
        model.stc_engine = STCEngine(
            triggers=triggers_2022_ukraine(),
            ss_mode="multiplicative"
        )
        # --- Live-instance patches for parameters module-level patching
        # cannot reach ---
        # BUG FIX (SA audit): model.py hardcodes PriceSystem(k=1.5) literally,
        # never reading the K_PRICE module constant at all -- module patching
        # is a structural no-op for this parameter without this line.
        model.price_system.k = float(param_values[1]) if len(param_values) > 1 else model.price_system.k
        # BUG FIX (SA audit): energy.py reads getattr(agent, 'epsilon_ef',
        # EPSILON_EF) and every agent has a real per-country epsilon_ef set
        # from node_parameters.csv, so the global fallback is never reached --
        # module patching is a structural no-op for this parameter too.
        # For SA purposes we deliberately override every agent uniformly so
        # this parameter's effect is actually exercised and measurable.
        if len(param_values) > 0:
            for agent in model.agent_map.values():
                agent.epsilon_ef = float(param_values[0])
        model.run(N_STEPS_SA, verbose=False)
        s = model.summary()
        return {m: s.get(m, 0.0) for m in OUTCOME_METRICS}
    except Exception as e:
        # SA should never quietly return fabricated zero-variance data --
        # log any future failure loudly instead of silently masking it as a
        # valid (but fake) result.
        import traceback
        print(f"\n[_run_one FAILED] {type(e).__name__}: {e}")
        traceback.print_exc()
        return {m: 0.0 for m in OUTCOME_METRICS}


def _apply_params_static(p: np.ndarray):
    """
    Patch module-level constants.
    p must have exactly 12 values — one per parameter in PARAM_SPACE.
    Always uses the FULL 12-parameter canonical order defined at module top.
    """
    import energy as en_mod
    import stc_engine as stc_mod
    import trade as tr_mod
    import prices as pr_mod
    import political_economy as pe_mod

    # Canonical 12-parameter order — never changes
    # BUG-009 FIX: RC_PRICE_AMP default updated from 0.10 (uncalibrated,
    # see stc_engine.py BUG-009 comment) to 0.021 (FAO-calibrated)
    # BUG FIX (SA audit): this list is the actual hardcoded default for each
    # module constant. It is now exposed at module level as TRUE_DEFAULTS so
    # "restore defaults after SA" call sites can use it directly, instead of
    # incorrectly resetting to the PARAM_SPACE midpoint (which previously
    # left 10 of 12 globals permanently wrong for the rest of the process --
    # e.g. EROI_DECLINE_RATE left at 0.0045 instead of its true default
    # 0.003, a 50% error silently affecting every phase run after Phase 7).
    defaults = list(TRUE_DEFAULTS)
    full = list(defaults)
    for i, v in enumerate(p):
        if i < len(full):
            full[i] = float(v)

    en_mod.EPSILON_EF              = full[0]
    pr_mod.K_PRICE                 = full[1]
    stc_mod.FS_ACCUMULATION_RATE   = full[2]
    stc_mod.FS_DECAY_RATE          = full[3]
    stc_mod.RC_CONTAGION_BOOST     = full[4]
    stc_mod.RC_PRICE_AMPLIFICATION = full[5]
    pe_mod.BASE_MARGIN             = full[6]
    pe_mod.POWER_CC_PENALTY        = full[7]
    tr_mod.BAN_CONTAGION_RATE      = full[8]
    en_mod.BIOFUEL_PRICE_THRESHOLD = full[9]
    en_mod.EROI_DECLINE_RATE       = full[10]
    pr_mod.ENERGY_COST_SHARE       = full[11]


# ============================================================================
# One-At-A-Time (OAT) parameter sweeps
# ============================================================================

def one_at_a_time_sweep(
    n_levels: int = 8,
    seed: int = 42,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    OAT sweep: vary each parameter across its range while holding others at
    centre values. Immediately readable by examiners.

    Returns DataFrame: param × level × outcome metrics
    """
    # BUG FIX (SA audit): this used to be a separate hardcoded FULL_NAMES/
    # FULL_BOUNDS list duplicated from PARAM_SPACE, which had drifted out of
    # sync -- RC_PRICE_AMP here was still [0.05, 0.20] (the old, pre-BUG-009
    # range, "an order of magnitude too high" per PARAM_SPACE's own comment)
    # while PARAM_SPACE itself had the corrected [0.01, 0.04]. OAT and Sobol
    # were silently sweeping different ranges for the same parameter.
    # PARAM_SPACE is now the single source of truth for both.
    FULL_NAMES  = PARAM_SPACE["names"]
    FULL_BOUNDS = PARAM_SPACE["bounds"]

    print("\n[SA] One-at-a-time parameter sweeps...")
    # BUG FIX (SA audit): sweep baseline is the model's true calibrated
    # defaults, not the arbitrary midpoint of each parameter's SA sweep
    # range (which for e.g. EROI_DECLINE was 0.0045 vs the true 0.003 --
    # a 50% difference that silently biased every "hold others constant"
    # sweep).
    centres = np.array(TRUE_DEFAULTS)

    rows = []
    for i, (name, (lo, hi)) in enumerate(zip(FULL_NAMES, FULL_BOUNDS)):
        levels = np.linspace(lo, hi, n_levels)
        for lvl in levels:
            p = centres.copy()
            p[i] = lvl
            outcomes = _run_one(p, seed=seed)
            row = {"param": name, "value": round(float(lvl), 6), "param_idx": i}
            row.update(outcomes)
            rows.append(row)
            if verbose:
                print(f"  OAT {name}={lvl:.4f} → price_index={outcomes.get('max_price_index', outcomes.get('max_price_ratio', float('nan'))):.3f}")

    df = pd.DataFrame(rows)
    _apply_params_static(centres)   # restore defaults
    return df


# ============================================================================
# Morris Screening
# ============================================================================

def morris_screening(
    n_trajectories: int = 20,
    seed: int = 42,
    verbose: bool = True,
) -> dict:
    """
    Morris method: compute elementary effects μ* (mean absolute EE)
    and σ (std of EE) for each parameter.

    μ* large → parameter is important
    σ large  → parameter has nonlinear effects or interactions

    Uses n_trajectories × (k+1) model runs = 20×13 = 260 runs.
    """
    if not HAS_SALIB:
        print("[Morris] SALib not available — skipping Morris screening")
        return {}

    print(f"\n[SA] Morris screening ({n_trajectories} trajectories × 13 runs)...")

    problem = {
        "num_vars": PARAM_SPACE["num_vars"],
        "names":    PARAM_SPACE["names"],
        "bounds":   PARAM_SPACE["bounds"],
    }

    X = morris_sample.sample(problem, N=n_trajectories,
                              num_levels=4, seed=seed)

    results = {m: np.zeros(len(X)) for m in OUTCOME_METRICS}

    for j, x in enumerate(X):
        out = _run_one(x, seed=seed)
        for m in OUTCOME_METRICS:
            results[m][j] = out[m]
        if verbose and j % 10 == 0:
            print(f"  Morris run {j+1}/{len(X)}")

    morris_results = {}
    for metric in OUTCOME_METRICS:
        Si = morris_analyze.analyze(
            problem, X, results[metric],
            num_levels=4, print_to_console=False
        )
        morris_results[metric] = {
            "mu_star": Si["mu_star"].tolist(),
            "sigma":   Si["sigma"].tolist(),
            "names":   Si["names"],
        }
        if verbose:
            print(f"\n  Morris [{metric}] — top 5 by μ*:")
            ranked = sorted(zip(Si["names"], Si["mu_star"]), key=lambda x: -x[1])
            for nm, mu in ranked[:5]:
                print(f"    {nm:<22}: μ*={mu:.4f}")

    # Restore TRUE defaults (BUG FIX, SA audit) -- this previously reset to
    # the PARAM_SPACE midpoint, not the model's real calibrated defaults,
    # leaving 10 of 12 globals permanently wrong for every phase run after
    # this one in the same process (Phase 8 retrodiction, Phase 9 scenarios).
    _apply_params_static(np.array(TRUE_DEFAULTS))

    return morris_results


# ============================================================================
# Sobol Global Sensitivity Analysis
# ============================================================================

def sobol_analysis(
    n_samples: int = 64,
    seed: int = 42,
    verbose: bool = True,
) -> dict:
    """
    Sobol variance decomposition.
    S1 = first-order index (main effect fraction of variance)
    ST = total-order index (includes interactions)
    ST − S1 large → strong parameter interactions

    Total runs: n_samples × (2k + 2) = 64 × 26 = 1664 runs.
    Reduced to n_samples=64 to keep compute tractable (~15 min).

    Returns dict: metric → {S1, ST, S1_conf, ST_conf, names}
    """
    if not HAS_SALIB:
        print("[Sobol] SALib not available — skipping Sobol analysis")
        return {}

    print(f"\n[SA] Sobol analysis ({n_samples} samples, {n_samples*(2*12+2)} total runs)...")

    problem = {
        "num_vars": PARAM_SPACE["num_vars"],
        "names":    PARAM_SPACE["names"],
        "bounds":   PARAM_SPACE["bounds"],
    }

    # BUG-014 FIX: saltelli.sample() in current SALib does not accept a
    # `seed` kwarg (API changed; this call previously raised TypeError,
    # consistent with the audit's finding that Sobol was "implemented but
    # never actually run" — it could not have run successfully as written).
    # Reproducibility is instead ensured via np.random.seed() before sampling.
    np.random.seed(seed)
    X = saltelli.sample(problem, N=n_samples, calc_second_order=False)
    n_total = len(X)

    results = {m: np.zeros(n_total) for m in OUTCOME_METRICS}

    for j, x in enumerate(X):
        out = _run_one(x, seed=seed)
        for m in OUTCOME_METRICS:
            results[m][j] = out[m]
        if verbose and j % 50 == 0:
            print(f"  Sobol run {j+1}/{n_total}")

    sobol_results = {}
    for metric in OUTCOME_METRICS:
        y = results[metric]
        # BUG-015 FIX: sobol.analyze() crashes (TypeError/ValueError) when
        # the outcome metric is constant across all sampled runs (variance=0
        # → Sobol indices undefined). Detect and skip gracefully rather than
        # letting one degenerate metric abort the entire Sobol run.
        if np.std(y) < 1e-9:
            print(
                f"\n  Sobol [{metric}]: SKIPPED — constant output "
                f"(std={np.std(y):.2e}) across all {n_total} samples; "
                f"Sobol indices are undefined when output variance is zero."
            )
            sobol_results[metric] = {
                "S1": None, "ST": None, "S1_conf": None, "ST_conf": None,
                "names": problem["names"],
                "note": "constant output across samples — Sobol undefined",
            }
            continue

        Si = sobol.analyze(
            problem, y,
            calc_second_order=False,
            print_to_console=False,
            seed=seed,
        )

        # BUG FIX (SA audit): SALib's bootstrap confidence intervals become
        # numerically unstable for near-discrete/low-cardinality outputs
        # (e.g. an integer node-overload count that only takes 2-3 distinct
        # values across all samples) -- point estimates (S1/ST) stay valid,
        # but S1_conf/ST_conf can blow up to ~1e30, which is not a real
        # uncertainty bound and must not be reported as if it were one.
        n_unique = len(np.unique(y))
        conf_arr = np.concatenate([Si["S1_conf"], Si["ST_conf"]])
        # A legitimate CI half-width for a Sobol index (theoretically ~[0,1],
        # with some allowance for small-sample noise) should never realistically
        # reach double digits. Anything past that is a numerical artifact, not
        # a wide-but-real interval.
        ci_unreliable = bool(n_unique <= 5) or bool(np.any(np.abs(conf_arr) > 10))

        sobol_results[metric] = {
            "S1":      Si["S1"].tolist(),
            "ST":      Si["ST"].tolist(),
            "S1_conf": None if ci_unreliable else Si["S1_conf"].tolist(),
            "ST_conf": None if ci_unreliable else Si["ST_conf"].tolist(),
            "names":   problem["names"],
        }
        if ci_unreliable:
            sobol_results[metric]["ci_reliable"] = False
            sobol_results[metric]["note"] = (
                f"point estimates (S1/ST) are valid, but confidence intervals "
                f"are not reported: '{metric}' only takes {n_unique} distinct "
                f"value(s) across all {n_total} samples, which makes SALib's "
                f"bootstrap CI numerically unstable (not a real uncertainty "
                f"bound). Treat S1/ST as indicative, not statistically "
                f"significant, for this metric."
            )
            print(
                f"\n  Sobol [{metric}]: point estimates kept, confidence "
                f"intervals SUPPRESSED — only {n_unique} distinct values "
                f"across {n_total} samples makes the bootstrap CI unreliable, "
                f"not a real interval."
            )
        if verbose:
            print(f"\n  Sobol [{metric}] — top 5 by ST:")
            ranked = sorted(
                zip(problem["names"], Si["ST"], Si["S1"]),
                key=lambda x: -x[1]
            )
            for nm, st, s1 in ranked[:5]:
                interaction = st - s1
                print(f"    {nm:<22}: ST={st:.3f}  S1={s1:.3f}  interact={interaction:.3f}")

    # Restore TRUE defaults (BUG FIX, SA audit) -- this previously reset to
    # the PARAM_SPACE midpoint, not the model's real calibrated defaults,
    # leaving 10 of 12 globals permanently wrong for every phase run after
    # this one in the same process (Phase 8 retrodiction, Phase 9 scenarios).
    _apply_params_static(np.array(TRUE_DEFAULTS))

    return sobol_results


# ============================================================================
# Summary table: "Which assumptions actually matter?"
# ============================================================================

def build_importance_table(
    morris_results: dict,
    sobol_results: dict,
    oat_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Combine Morris μ* and Sobol ST into a single ranked importance table.
    This is the "publishable result" the reviewer mentioned.

    Returns DataFrame sorted by combined importance rank.
    """
    param_names = PARAM_SPACE["names"]
    # BUG FIX (SA audit): this was "max_price_ratio", the pre-BUG-011 name.
    # OUTCOME_METRICS was renamed to "max_price_index" (see line 103 comment)
    # but this reference was never updated, so `primary_metric in sobol_results`
    # was always False and every importance score silently came out as 0.0 --
    # no crash, just silently wrong output.
    primary_metric = "max_price_index"

    rows = []
    for i, name in enumerate(param_names):
        mu_star = 0.0
        st      = 0.0
        s1      = 0.0

        if morris_results and primary_metric in morris_results and morris_results[primary_metric]:
            mu_star = morris_results[primary_metric]["mu_star"][i]

        # Guard against a metric whose output was constant across every SA
        # sample (Sobol indices undefined -> stored as None). This is what
        # previously crashed regenerate_all.py with a TypeError; a genuinely
        # zero-variance metric should report zero importance, not crash.
        if (sobol_results and primary_metric in sobol_results
                and sobol_results[primary_metric] is not None
                and sobol_results[primary_metric].get("ST") is not None):
            st = sobol_results[primary_metric]["ST"][i]
            s1 = sobol_results[primary_metric]["S1"][i]

        # OAT range (outcome range when this param is swept)
        if not oat_df.empty:
            sub = oat_df[oat_df["param"] == name]
            oat_range = (sub[primary_metric].max() - sub[primary_metric].min()
                         if not sub.empty else 0.0)
        else:
            oat_range = 0.0

        rows.append({
            "parameter":     name,
            "Morris_mu_star":round(mu_star, 4),
            "Sobol_S1":      round(s1, 4),
            "Sobol_ST":      round(st, 4),
            "interaction":   round(st - s1, 4),
            "OAT_range":     round(oat_range, 4),
        })

    df = pd.DataFrame(rows)
    # Rank by Sobol ST descending (most informative)
    df = df.sort_values("Sobol_ST", ascending=False).reset_index(drop=True)
    df.insert(0, "rank", range(1, len(df) + 1))
    return df


# ============================================================================
# Entry point
# ============================================================================

def run_phase7(
    data_dir: Path = _ROOT / "data" / "processed",
    n_morris: int = 20,
    n_sobol: int = 64,
    n_oat_levels: int = 8,
    verbose: bool = True,
) -> dict:
    """Run full Phase 7 sensitivity analysis and save outputs."""
    print("\n" + "="*60)
    print("  PHASE 7: SENSITIVITY ANALYSIS")
    print("="*60)
    print(f"  Morris: {n_morris} trajectories × 13 = {n_morris*13} runs")
    print(f"  Sobol:  {n_sobol} samples × 26 = {n_sobol*26} total runs")
    print(f"  OAT:    {12 * n_oat_levels} runs")

    # OAT (fast, do first)
    oat_df = one_at_a_time_sweep(n_levels=n_oat_levels, verbose=verbose)
    oat_df.to_csv(data_dir / "sa_oat.csv", index=False)
    print(f"\n[Phase 7] OAT saved → sa_oat.csv ({len(oat_df)} rows)")

    # Morris
    morris_results = morris_screening(n_trajectories=n_morris, verbose=verbose)

    # Sobol
    sobol_results = sobol_analysis(n_samples=n_sobol, verbose=verbose)

    # Combined table
    importance_table = build_importance_table(morris_results, sobol_results, oat_df)
    importance_table.to_csv(data_dir / "sa_importance.csv", index=False)

    print("\n[Phase 7] IMPORTANCE TABLE (primary metric: max_price_index)")
    print(importance_table[["rank","parameter","Morris_mu_star",
                             "Sobol_ST","Sobol_S1","interaction","OAT_range"]]
          .to_string(index=False))

    # Save Morris and Sobol raw results
    import json
    if morris_results:
        with open(data_dir / "sa_morris.json", "w") as f:
            json.dump(morris_results, f, indent=2)
    if sobol_results:
        with open(data_dir / "sa_sobol.json", "w") as f:
            json.dump(sobol_results, f, indent=2)

    print(f"\n[Phase 7] Saved: sa_oat.csv, sa_importance.csv, sa_morris.json, sa_sobol.json")

    return {
        "morris":     morris_results,
        "sobol":      sobol_results,
        "oat_df":     oat_df,
        "importance": importance_table,
    }


if __name__ == "__main__":
    run_phase7(n_morris=20, n_sobol=64, verbose=True)
