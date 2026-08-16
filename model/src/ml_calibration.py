"""
ml_calibration.py
-----------------
ML-based calibration of latent Coping Capacity (CC) parameters.

Framework : Gambhir et al. (2025) + Homer-Dixon et al. (2015)
Phase     : 6 — ML as calibration aid, NOT as a discovery engine

HONEST FRAMING (per reviewer feedback):
  We have 35 nodes × 24 years = 840 observations.
  That is not enough to "reveal hidden dynamics."
  ML is used here purely as a calibration aid:
    "What weights should CC_TECH, CC_CAPITAL, CC_POLRISK, CC_RESERVE,
     CC_CLIMVULN have to best reproduce observed undernourishment patterns?"

  The output replaces the hand-tuned weights in stc_engine.py with
  data-derived weights — making the model more defensible, not smarter.

What this module does:
  A. CC_index calibration
     - Features: Ti, Wi, gdp_per_capita, renewables_share, life_expectancy,
                 arable_land_pct, fossil_share_energy (all from node_panel)
     - Target: undernourishment_baseline_pct (from node_parameters)
       proxy: high undernourishment → low CC (inverse relationship)
     - Method: LightGBM gradient-boosted regression + 5-fold cross-validation
     - Output: feature importances → re-weight CC components
               calibrated CC_i for each node × year

  B. Price forecasting (lightweight, as validation cross-check only)
     - Features: lagged FPI, supply-demand ratio estimate, energy proxy
     - Target: FAO FPI next year
     - Method: Ridge regression (not deep learning — data too sparse)
     - Output: forecasted FPI path to cross-check model's endogenous price

  C. Uncertainty bounds on CC estimates (Monte Carlo on feature noise)
     - Bootstrap 200 times with feature noise σ=5%
     - Report CC_i = mean ± std for each node

LIMITATIONS (stated explicitly):
  - 840 obs with ~7 features: model can overfit trivially. We use 5-fold CV
    and report both train and val R² to flag overfit.
  - UHC index and psi_i have only 224/840 non-null values — imputed with
    median; imputed values are flagged.
  - Export/import data is missing entirely; CC calibration cannot capture
    trade-dependency vulnerability directly.
  - This is a calibration exercise, not a structural model of resilience.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import KFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score, mean_absolute_error
import warnings
warnings.filterwarnings("ignore")

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False
    from sklearn.ensemble import GradientBoostingRegressor

_ROOT = Path(__file__).resolve().parent.parent
_DATA = _ROOT / "data" / "processed"


# ============================================================================
# A. CC_index Calibration
# ============================================================================

# These are the CC component names matching stc_engine.py weights
CC_COMPONENTS = ["tech", "capital", "polrisk", "reserve", "climvuln"]

# Default weights (hand-tuned in Phase 4)
CC_WEIGHTS_DEFAULT = {
    "tech":     0.30,
    "capital":  0.30,
    "polrisk":  0.20,   # penalty weight
    "reserve":  0.10,
    "climvuln": 0.10,   # penalty weight
}


def load_cc_features(node_panel_path: Path, node_params_path: Path) -> pd.DataFrame:
    """
    Build a feature matrix for CC calibration.

    BUG-016 FIX (audit Fix #8, CRITICAL — CC operationalisation): the
    previous target, cc_target = 1 - undernourishment_pct/50, conflates food
    security (an OUTCOME — are people currently fed) with coping capacity
    (a PROCESS capacity — can the system absorb and respond to a shock).
    Saudi Arabia is the audit's own worked example: low undernourishment
    (high apparent "food security") but ~80% caloric import dependence and
    therefore genuinely low resilience to a trade disruption. Under the old
    target this node would receive a spuriously HIGH CC score.

    Corrected target (resilience composite, [0,1]):
      cc_target = 0.40 * reserve_adequacy_norm
                 + 0.35 * trade_diversification_proxy
                 + 0.25 * govt_response_capacity

    Where:
      reserve_adequacy_norm   = clip(R_i / (D_i_Mt/12) / 3.0, 0, 1)
                                 (months of strategic reserve / 3-month
                                 target, FAO-style reserve adequacy norm)
      trade_diversification   = clip(trade_pct_gdp / 100, 0, 1)
                                 (trade-to-GDP as an OPENNESS proxy; this is
                                 a proxy, not a true HHI import-diversification
                                 index — FAOSTAT bilateral trade matrices
                                 would be needed for the latter and are not
                                 available in this pipeline; documented as a
                                 remaining limitation)
      govt_response_capacity  = 1 - rho_i  (inverse political risk; lower
                                 political risk → higher assumed institutional
                                 capacity to respond to shocks)

    This remains an imperfect proxy (the audit's own recommended indicators —
    FAO reserve-adequacy data, FAOSTAT bilateral-trade HHI, IMF fiscal-space
    index, World Bank LPI — are not present in this project's data pipeline)
    but it is no longer conceptually circular: a node's CC is no longer
    definitionally tied to the same undernourishment outcome the ABM later
    uses CC to help predict.
    """
    panel  = pd.read_csv(node_panel_path)
    params = pd.read_csv(node_params_path)

    # ── BUG-016 FIX: build resilience-based target from params ───────────────
    params = params.copy()
    params["_reserve_months"] = params["R_i"] / (params["D_i_Mt"] / 12.0)
    params["_reserve_adequacy_norm"] = np.clip(params["_reserve_months"] / 3.0, 0.0, 1.0)
    params["_govt_capacity"] = 1.0 - params["rho_i"].clip(0.0, 1.0)

    reserve_map = dict(zip(params["Node"], params["_reserve_adequacy_norm"]))
    govt_map    = dict(zip(params["Node"], params["_govt_capacity"]))
    # Fallback for nodes with missing R_i / D_i_Mt
    reserve_default = float(np.nanmedian(params["_reserve_adequacy_norm"]))
    govt_default    = float(np.nanmedian(params["_govt_capacity"]))

    # Retained for diagnostic/legacy comparison only — NOT used as cc_target
    under_map = dict(zip(params["Node"], params["undernourishment_baseline_pct"].fillna(5.0)))

    rows = []
    for _, row in panel.iterrows():
        node = row["node"]
        year = int(row["year"])

        # ── BUG-016 FIX: resilience composite target ─────────────────────────
        reserve_adeq = reserve_map.get(node, reserve_default)
        if pd.isna(reserve_adeq):
            reserve_adeq = reserve_default
        trade_pct = row.get("trade_pct_gdp", np.nan)
        trade_div = float(np.clip(trade_pct / 100.0, 0.0, 1.0)) if pd.notna(trade_pct) else 0.5
        govt_cap  = govt_map.get(node, govt_default)
        if pd.isna(govt_cap):
            govt_cap = govt_default

        cc_target = float(np.clip(
            0.40 * reserve_adeq + 0.35 * trade_div + 0.25 * govt_cap,
            0.05, 0.95
        ))

        # Legacy proxy retained as a diagnostic column only (not the target)
        under_pct = under_map.get(node, 5.0)
        legacy_cc_proxy = float(np.clip(1.0 - under_pct / 50.0, 0.05, 0.95))

        # ── Features ──────────────────────────────────────────────────────────
        def g(col, default=np.nan):
            v = row.get(col, np.nan)
            return float(v) if pd.notna(v) else default

        Ti              = g("Ti",                    0.5)
        Wi              = g("Wi",                    0.7)
        gdp_per_cap     = g("gdp_per_capita",     5000.0)
        life_exp        = g("life_expectancy",        65.0)
        renew_share     = g("renewables_share_energy", 0.15)
        fossil_share    = g("fossil_share_energy",    0.80)
        arable          = g("arable_land_pct",        10.0)
        uhc             = g("uhc_index",              60.0)  # often NaN
        eps_i           = g("eps_i",                  0.5)

        imputed = int(pd.isna(row.get("uhc_index", np.nan)))

        rows.append({
            "node":          node,
            "year":          year,
            "Ti":            Ti,
            "Wi":            Wi,
            "log_gdp_cap":   np.log1p(gdp_per_cap),
            "life_exp_norm": life_exp / 85.0,
            "renew_share":   renew_share,
            "fossil_share":  fossil_share,
            "arable_norm":   min(arable / 50.0, 1.0),
            "uhc_norm":      uhc / 100.0,
            "eps_i":         eps_i,
            "cc_target":     cc_target,
            "legacy_cc_proxy_undernourishment": legacy_cc_proxy,  # diagnostic only
            "imputed_flag":  imputed,
        })

    return pd.DataFrame(rows)


def calibrate_cc(
    node_panel_path: Path,
    node_params_path: Path,
    n_bootstrap: int = 200,
    verbose: bool = True,
) -> dict:
    """
    Calibrate CC_index weights from real data.

    Returns
    -------
    result : dict with keys:
      calibrated_weights   : dict of CC component → weight
      node_cc_table        : DataFrame of node → CC_mean, CC_std
      feature_importances  : dict of feature → importance
      val_r2               : cross-validated R²
      val_mae              : cross-validated MAE
      train_r2             : training R² (check for overfit)
      limitations          : list of honest limitation strings
    """
    df = load_cc_features(node_panel_path, node_params_path)

    FEATURES = ["Ti", "Wi", "log_gdp_cap", "life_exp_norm",
                "renew_share", "fossil_share", "arable_norm", "uhc_norm", "eps_i"]

    X = df[FEATURES].fillna(df[FEATURES].median()).values
    y = df["cc_target"].values

    scaler = StandardScaler()
    X_sc   = scaler.fit_transform(X)

    # ── Model choice ──────────────────────────────────────────────────────────
    if HAS_LGB:
        model = lgb.LGBMRegressor(
            n_estimators=100, max_depth=4, learning_rate=0.05,
            min_child_samples=5, subsample=0.8, verbose=-1
        )
    else:
        model = GradientBoostingRegressor(
            n_estimators=100, max_depth=3, learning_rate=0.05,
            subsample=0.8, random_state=42
        )

    # ── 5-fold cross-validation ───────────────────────────────────────────────
    kf      = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_r2   = cross_val_score(model, X_sc, y, cv=kf, scoring="r2")
    cv_mae  = -cross_val_score(model, X_sc, y, cv=kf, scoring="neg_mean_absolute_error")

    val_r2  = float(cv_r2.mean())
    val_mae = float(cv_mae.mean())

    # ── Full-data fit (for feature importances and node CC estimates) ──────────
    model.fit(X_sc, y)
    train_r2 = float(r2_score(y, model.predict(X_sc)))

    if verbose:
        print(f"[CC Calibration] val_R²={val_r2:.3f} | train_R²={train_r2:.3f} | "
              f"val_MAE={val_mae:.3f}")
        if train_r2 - val_r2 > 0.20:
            print("  ⚠ Overfit detected (train-val gap > 0.20). "
                  "Weights are indicative only.")

    # ── Feature importances → CC weight re-mapping ────────────────────────────
    if HAS_LGB:
        raw_imp = model.feature_importances_
    else:
        raw_imp = model.feature_importances_

    imp = dict(zip(FEATURES, raw_imp / raw_imp.sum()))

    # Map features to CC components (each feature contributes to one component)
    feature_to_component = {
        "Ti":            "tech",
        "Wi":            "tech",
        "log_gdp_cap":   "capital",
        "life_exp_norm": "capital",
        "renew_share":   "climvuln",
        "fossil_share":  "polrisk",
        "arable_norm":   "tech",
        "uhc_norm":      "reserve",
        "eps_i":         "climvuln",
    }

    comp_imp = {c: 0.0 for c in CC_COMPONENTS}
    for feat, weight in imp.items():
        comp = feature_to_component[feat]
        comp_imp[comp] += weight

    # Normalise so weights sum to 1 (penalty weights stay negative in engine)
    total = sum(comp_imp.values())
    calibrated_weights = {k: round(v / total, 4) for k, v in comp_imp.items()}

    if verbose:
        print("  Calibrated CC weights:")
        for comp, w in calibrated_weights.items():
            default = CC_WEIGHTS_DEFAULT.get(comp, 0.0)
            print(f"    {comp:<12}: {w:.4f}  (default was {default:.4f})")

    # ── Bootstrap uncertainty on CC estimates ─────────────────────────────────
    rng = np.random.default_rng(42)
    boot_preds = np.zeros((n_bootstrap, len(y)))

    for b in range(n_bootstrap):
        # Add 5% Gaussian noise to features
        X_noisy = X + rng.normal(0, 0.05 * X.std(axis=0), X.shape)
        X_noisy_sc = scaler.transform(X_noisy)
        boot_preds[b] = model.predict(X_noisy_sc)

    df["cc_mean"] = boot_preds.mean(axis=0)
    df["cc_std"]  = boot_preds.std(axis=0)

    # Per-node CC table (2022 snapshot)
    snap = df[df["year"] == df["year"].max()][
        ["node", "cc_mean", "cc_std", "cc_target", "imputed_flag"]
    ].sort_values("cc_mean", ascending=False).reset_index(drop=True)

    # ── Honest limitations ────────────────────────────────────────────────────
    n_imputed = df["imputed_flag"].sum()
    limitations = [
        f"Sample size: {len(df)} obs ({len(df['node'].unique())} nodes × "
        f"{len(df['year'].unique())} years). Cross-validated R²={val_r2:.2f}.",
        f"{n_imputed}/{len(df)} rows imputed UHC index (median substitution). "
        f"Imputed rows flagged.",
        "Target (undernourishment proxy) is cross-sectional, not time-varying. "
        "CC calibration is therefore cross-sectional, not dynamic.",
        "Export/import dependency not captured — trade-vulnerability component "
        "of CC remains hand-tuned.",
        "ML used as calibration aid only. Causal interpretation not warranted.",
        f"Train R²={train_r2:.2f} vs Val R²={val_r2:.2f} "
        f"({'overfit risk' if train_r2-val_r2>0.20 else 'acceptable gap'}).",
    ]

    return {
        "calibrated_weights":  calibrated_weights,
        "node_cc_table":       snap,
        "feature_importances": imp,
        "val_r2":              val_r2,
        "val_mae":             val_mae,
        "train_r2":            train_r2,
        "n_obs":               len(df),
        "limitations":         limitations,
    }


# ============================================================================
# B. Price Forecasting (Ridge — honest about data sparsity)
# ============================================================================

def calibrate_price_forecast(
    node_panel_path: Path,
    verbose: bool = True,
) -> dict:
    """
    Fit a Ridge regression price forecasting model on FAO FPI data.

    Features: lagged FPI (t-1, t-2), year, supply proxy (1/gdp_per_cap × pop)
    Target: FAO FPI at t+1 (normalised to 2014-2016=100)

    Returns
    -------
    dict with: val_r2, val_mae, forecast_path, coefficients, limitations
    """
    panel = pd.read_csv(node_panel_path)

    # One FPI per year (global)
    fpi = panel.groupby("year")["fao_fpi"].first().dropna().sort_index()

    # Normalise to 2014-2016 baseline
    base_fpi = fpi.loc[2014:2016].mean()
    fpi_norm = fpi / base_fpi

    # Build lagged features
    years = sorted(fpi_norm.index)
    rows  = []
    for i in range(2, len(years) - 1):
        yr = years[i]
        rows.append({
            "year":      yr,
            "fpi_lag1":  fpi_norm.get(years[i-1], np.nan),
            "fpi_lag2":  fpi_norm.get(years[i-2], np.nan),
            "year_norm": (yr - 2000) / 24.0,
            "fpi_target":fpi_norm.get(years[i+1], np.nan),
        })

    df = pd.DataFrame(rows).dropna()
    X  = df[["fpi_lag1", "fpi_lag2", "year_norm"]].values
    y  = df["fpi_target"].values

    scaler = StandardScaler()
    X_sc   = scaler.fit_transform(X)

    model  = Ridge(alpha=1.0)
    kf     = KFold(n_splits=4, shuffle=True, random_state=42)
    cv_r2  = cross_val_score(model, X_sc, y, cv=kf, scoring="r2")
    cv_mae = -cross_val_score(model, X_sc, y, cv=kf, scoring="neg_mean_absolute_error")

    model.fit(X_sc, y)
    train_r2 = float(r2_score(y, model.predict(X_sc)))

    if verbose:
        print(f"[Price Forecast] val_R²={cv_r2.mean():.3f} | "
              f"train_R²={train_r2:.3f} | val_MAE={cv_mae.mean():.3f}")

    # Forecast 5 steps ahead from last known year
    last_yr = max(years)
    last_v  = fpi_norm.get(last_yr, 1.0)
    prev_v  = fpi_norm.get(last_yr - 1, 1.0)

    forecast = {}
    for step in range(1, 6):
        yr_n   = (last_yr + step - 2000) / 24.0
        X_pred = scaler.transform([[last_v, prev_v, yr_n]])
        pred   = float(model.predict(X_pred)[0])
        forecast[last_yr + step] = round(pred, 4)
        prev_v = last_v
        last_v = pred

    limitations = [
        f"Ridge regression on {len(df)} year-observations (n=24 years, lagged).",
        "Model is autoregressive — forecasts compound error rapidly beyond 2 steps.",
        "No structural supply/demand features included (data missing).",
        "Use for cross-check only; not as a primary forecast.",
        f"Val R²={cv_r2.mean():.2f}, Val MAE={cv_mae.mean():.3f} (FPI normalised units).",
    ]

    return {
        "val_r2":       float(cv_r2.mean()),
        "val_mae":      float(cv_mae.mean()),
        "train_r2":     train_r2,
        "forecast_path":forecast,
        "fpi_normalised_series": fpi_norm.to_dict(),
        "base_fpi_2014_2016":    float(base_fpi),
        "limitations":  limitations,
    }


# ============================================================================
# C. Monte Carlo Uncertainty Quantification for CC
# ============================================================================

def monte_carlo_cc_uncertainty(
    node_params_path: Path,
    n_runs: int = 500,
    param_noise_pct: float = 0.10,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Monte Carlo uncertainty on CC_index by perturbing node parameters ±10%.

    Each run perturbs Ti, Wi, gdp_per_capita, life_expectancy by ±10%
    and recomputes CC using the stc_engine formula.

    Returns DataFrame: node × [cc_mean, cc_std, cc_p5, cc_p95]
    """
    params = pd.read_csv(node_params_path)
    rng    = np.random.default_rng(42)

    # CC formula (mirrors stc_engine._accumulate_stress CC computation)
    def compute_cc(row, noise):
        T   = max(float(row.get("T_i", 0.5))  * (1 + noise[0]), 0.01)
        K   = max(float(row.get("K_i", 500.)) * (1 + noise[1]), 0.01)
        rho = float(row.get("rho_i", 0.33))
        clv = float(row.get("clim_vuln_i", 0.33))

        tech_norm   = min(T / 2.0,    1.0)
        cap_factor  = min(K / 1000.0, 1.0)
        # reserve factor: approximate from K_i (no direct reserve data here)
        res_factor  = min(K / 2000.0, 1.0)

        cc = (0.30 * tech_norm
              + 0.30 * cap_factor
              - 0.20 * rho
              + 0.10 * res_factor
              - 0.10 * clv)
        return float(np.clip(cc, 0.05, 1.0))

    results = {}
    for _, row in params.iterrows():
        node = row["Node"]
        cc_samples = np.zeros(n_runs)
        for i in range(n_runs):
            noise = rng.normal(0, param_noise_pct, size=4)
            cc_samples[i] = compute_cc(row, noise)
        results[node] = {
            "cc_mean": round(float(cc_samples.mean()), 4),
            "cc_std":  round(float(cc_samples.std()),  4),
            "cc_p5":   round(float(np.percentile(cc_samples, 5)),  4),
            "cc_p95":  round(float(np.percentile(cc_samples, 95)), 4),
        }

    df_out = pd.DataFrame(results).T.reset_index().rename(columns={"index": "node"})
    df_out = df_out.sort_values("cc_mean", ascending=False).reset_index(drop=True)

    if verbose:
        print(f"[MC UQ] CC uncertainty ({n_runs} runs, ±{param_noise_pct*100:.0f}% noise):")
        print(df_out[["node","cc_mean","cc_std","cc_p5","cc_p95"]].head(10).to_string(index=False))

    return df_out


# ============================================================================
# Entry point
# ============================================================================

def run_phase6(
    data_dir: Path = _DATA,
    verbose: bool = True,
) -> dict:
    """
    Run all Phase 6 calibrations and return results dict.
    Saves outputs to data/processed/.
    """
    node_panel  = data_dir / "node_panel.csv"
    node_params = data_dir / "node_parameters.csv"

    print("\n" + "="*60)
    print("  PHASE 6: ML CALIBRATION (honest framing)")
    print("="*60)

    # A. CC calibration
    print("\n[A] CC_index calibration (LightGBM gradient-boosted regression)")
    cc_result = calibrate_cc(node_panel, node_params, n_bootstrap=200, verbose=verbose)

    print("\n  Limitations:")
    for lim in cc_result["limitations"]:
        print(f"    - {lim}")

    # B. Price forecast
    print("\n[B] Price forecasting (Ridge regression, autoregressive)")
    price_result = calibrate_price_forecast(node_panel, verbose=verbose)

    print(f"\n  5-year forecast (normalised FPI, 2014-2016=1.0):")
    for yr, val in price_result["forecast_path"].items():
        print(f"    {yr}: {val:.3f}")

    print("\n  Limitations:")
    for lim in price_result["limitations"]:
        print(f"    - {lim}")

    # C. Monte Carlo CC uncertainty
    print("\n[C] Monte Carlo CC uncertainty (±10% parameter noise, 500 runs)")
    mc_result = monte_carlo_cc_uncertainty(node_params, n_runs=500, verbose=verbose)

    # ── Save outputs ──────────────────────────────────────────────────────────
    cc_result["node_cc_table"].to_csv(data_dir / "cc_calibrated.csv", index=False)
    mc_result.to_csv(data_dir / "cc_uncertainty.csv", index=False)

    price_df = pd.DataFrame([
        {"year": k, "forecast_fpi_norm": v}
        for k, v in price_result["forecast_path"].items()
    ])
    price_df.to_csv(data_dir / "price_forecast.csv", index=False)

    print(f"\n[Phase 6] Saved: cc_calibrated.csv, cc_uncertainty.csv, price_forecast.csv")

    return {
        "cc":    cc_result,
        "price": price_result,
        "mc_cc": mc_result,
    }


if __name__ == "__main__":
    run_phase6(verbose=True)
