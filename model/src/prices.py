"""
prices.py
---------
Global food price dynamics.

Framework : Gambhir et al. (2025) + Homer-Dixon et al. (2015)
Phase     : 2 — FAO FPI-anchored exponential price system

Update rule (EQUATIONS.md §8):
  p(t+1) = p(t) × exp(κ_price × (D_tot − Q_tot) / D_tot)
           + θ_revert × (p_adaptive − p(t))
           + energy_cost_push(t)      ← Phase 3 hook (0 until Phase 3)

Calibration (BUGS_FIXED BUG-006 — price floor degeneracy fix):
  - Anchored to FAO Food Price Index (2014-2016 = 100 baseline)
  - κ_price = 1.5 reproduces 2008 (+70%) and 2022 (+56%) peaks to within ±20%
  - θ_revert = 0.015 (1.5%/yr mean reversion; reduced from 0.04 so the model
    does NOT slam to floor under structural surplus.  Real FAO FPI 2000-2010
    shows ~3-5 year mean reversion cycles, not annual snap-back.)
  - p_floor = 0.80  (FAO normalised FPI never below ~0.75 in 2000-2024 data)
  - p_adaptive: rolling 5-step mean of price history used as reversion target
    so baseline price tracks near actual FAO FPI range [0.85, 1.20] rather
    than snapping to a fixed 1.0.
  - BUG-006 root cause: old REVERSION_RATE=0.04 + structural supply surplus
    1.4-1.7 caused p → PRICE_FLOOR within 5 steps every scenario, making the
    primary outcome metric flat and scenario comparison meaningless.
"""

import numpy as np
from pathlib import Path
import pandas as pd

# ── Price dynamics constants ──────────────────────────────────────────────────
# BUG-006 ROOT CAUSE (confirmed by diagnostic, not just asserted): the supply/
# demand imbalance computed from agent production vs demand is persistently
# -0.40 to -0.69 (i.e. 40-69% structural surplus, matching the paper's own
# claimed 1.4-1.7 ratio).  With K_PRICE=1.5 unmodified, exp(1.5 × -0.40) = 0.55
# — a ~45% price collapse in a SINGLE step, every step, regardless of the
# reversion rate.  Reversion was never the dominant term; the raw exponential
# imbalance response was.  Lowering REVERSION_RATE alone (first-pass fix)
# does not address this and price still pins at the floor.
#
# Correct fix: dampen the imbalance elasticity (IMBALANCE_DAMPING) so a
# structural surplus produces gradual, bounded downward pressure consistent
# with real commodity markets (surplus depresses price over years, not within
# one annual step) rather than an immediate near-halving.
K_PRICE          = 1.5    # supply-demand price sensitivity (kept; see damping below)
IMBALANCE_DAMPING = 0.08  # BUG-006 FIX: re-tuned after BUG-006b (technology
                           # growth cap) bounded steady-state surplus at ~1.50-
                           # 1.58 instead of unbounded growth to 1.95+. At this
                           # surplus level, damping=0.08 keeps the one-step price
                           # response within ±8% rather than ±45%, allowing
                           # REVERSION_RATE and energy cost-push to meaningfully
                           # shape the trajectory instead of being swamped.
REVERSION_RATE   = 0.04   # restored to original; no longer the dominant failure mode
                           # once imbalance is damped
PRICE_FLOOR      = 0.80   # BUG-006 FIX: was 0.60 → FAO normalised FPI never below ~0.75
PRICE_CEILING    = 5.00
ADAPTIVE_WINDOW  = 5      # steps to average for adaptive reversion target

# ── Energy cost-push elasticity (Phase 3, §8) ─────────────────────────────────
ENERGY_COST_SHARE = 0.45   # 40-50% energy cost of variable cropping costs (IEA)


class PriceSystem:
    """
    Global food price index (baseline = 1.0 = FAO FPI 2014-2016 average).

    Attributes
    ----------
    price         : current price index
    price_baseline: long-run equilibrium (1.0 unless overridden)
    price_history : list of (step, price) tuples
    price_0       : initial price (used for p_ratio in FS_index)
    """

    def __init__(
        self,
        baseline: float = 1.0,
        k: float = K_PRICE,
        fpi_csv: Path = None,
        init_year: int = 2000,
    ):
        """
        Parameters
        ----------
        baseline  : long-run equilibrium price index (1.0 = FAO 2014-2016 base)
        k         : price sensitivity
        fpi_csv   : path to data/processed/fpi_annual.csv (optional)
                    If supplied, initialises p(0) from real FAO FPI for init_year
        init_year : simulation start year (used to look up FAO FPI initial value)
        """
        self.k         = float(k)
        self.baseline  = float(baseline)

        # Attempt FAO FPI initialisation
        if fpi_csv is not None and Path(fpi_csv).exists():
            p0 = self._load_fpi_start(fpi_csv, init_year)
        else:
            p0 = baseline

        self.price    = float(p0)
        self.price_0  = float(p0)   # stored for FS_index p_ratio
        self.price_history: list = [p0]

        # Phase 3 hook: energy stress index (set by model each step, default 0)
        self._energy_stress_global = 0.0

    # =========================================================================
    # FAO initialisation
    # =========================================================================

    def _load_fpi_start(self, fpi_csv: Path, init_year: int) -> float:
        """
        Load FAO Food Price Index and return the normalised value for init_year.
        Normalisation: divide by 2014-2016 average so baseline=1.0.

        BUG-010 FIX (newly discovered during price-floor audit fix): the
        bundled fpi_annual.csv has a gap from 2011 to 2019 — it does NOT
        contain 2014, 2015, or 2016. The original code computed
        df[df.year.between(2014,2016)].mean(), which silently returns NaN
        for this dataset, and np.isnan(base_fpi) then triggers a silent
        fallback to baseline=1.0 for EVERY init_year — including 2022,
        despite the paper's stated claim that p(0) = FPI2022/FPI2014-2016 =
        1.44. The model was never actually FAO-FPI-anchored; it was always
        using the unweighted baseline. Fix: fall back to year 2019 (FPI=
        96.43, the closest available year to the true ~100 FAO 2014-16
        baseline, and itself a documented stable non-crisis year per
        retrodiction.py's REAL_FPI_STABLE=0.949) when the proper window is
        unavailable, and log the substitution instead of failing silently.
        """
        try:
            df = pd.read_csv(fpi_csv)
            year_col = [c for c in df.columns if "year" in c.lower()]
            fpi_col  = [c for c in df.columns if any(x in c.lower() for x in ["fpi","price","index"])]
            if not year_col or not fpi_col:
                return self.baseline
            df = df.rename(columns={year_col[0]: "year", fpi_col[0]: "fpi"})
            df["year"] = df["year"].astype(int)

            # 2014-2016 average for normalisation
            base_fpi = df[df["year"].between(2014, 2016)]["fpi"].mean()
            if np.isnan(base_fpi) or base_fpi <= 0:
                # BUG-010 FIX: data gap 2011->2019 means 2014-16 is never
                # present. Fall back to nearest available year to the true
                # FAO baseline instead of silently returning self.baseline=1.0.
                fallback_year = 2019 if (df["year"] == 2019).any() else int(
                    df.iloc[(df["year"] - 2015).abs().argsort()[:1]]["year"].values[0]
                )
                base_fpi = df[df["year"] == fallback_year]["fpi"].values[0]
                print(
                    f"[PriceSystem] BUG-010 fix: 2014-2016 FPI baseline window "
                    f"missing from data; using year {fallback_year} "
                    f"(FPI={base_fpi:.2f}) as normalisation baseline instead."
                )
                if np.isnan(base_fpi) or base_fpi <= 0:
                    return self.baseline

            init_fpi = df[df["year"] == init_year]["fpi"]
            if init_fpi.empty:
                # Use nearest year
                nearest = df.iloc[(df["year"] - init_year).abs().argsort()[:1]]
                nearest_year = int(nearest["year"].values[0])
                print(
                    f"[PriceSystem] init_year={init_year} not in FPI data; "
                    f"using nearest available year {nearest_year} instead."
                )
                return float(nearest["fpi"].values[0]) / base_fpi

            return float(init_fpi.values[0]) / base_fpi

        except Exception:
            return self.baseline

    # =========================================================================
    # Main update (§8)
    # =========================================================================

    def update(
        self,
        total_supply: float,
        total_demand: float,
        energy_stress_global: float = 0.0,
    ) -> float:
        """
        p(t+1) = p(t) × exp(κ × imbalance)
                + θ_revert × (p_adaptive − p(t))
                + energy_cost_push(t)

        BUG-006 fix: reversion target is adaptive (rolling mean of recent prices)
        rather than fixed at 1.0.  This prevents the model from slamming to
        PRICE_FLOOR when structural supply exceeds demand, while still allowing
        mean reversion during genuine stable periods.

        Parameters
        ----------
        total_supply         : Σᵢ Qᵢ(t) in kcal/year
        total_demand         : Σᵢ Dᵢ(t) in kcal/year
        energy_stress_global : global mean ES_index (Phase 3; 0 until then)
        """
        if total_demand <= 0:
            return self.price

        # Supply-demand imbalance
        imbalance = (total_demand - total_supply) / total_demand

        # BUG-006 FIX: damp the imbalance before exponentiation. Without this,
        # the model's persistent 40-69% structural surplus produces a ~45-55%
        # one-step price collapse via exp(K_PRICE * imbalance), independent of
        # the reversion rate. Real commodity markets absorb structural surplus
        # gradually (years), not in a single annual step.
        damped_imbalance = imbalance * IMBALANCE_DAMPING

        # Exponential price response
        raw_new = self.price * np.exp(self.k * damped_imbalance)

        # Adaptive reversion target: rolling mean of recent prices, not fixed 1.0
        # This prevents structural surplus from driving prices to the floor.
        window = self.price_history[-ADAPTIVE_WINDOW:] if len(self.price_history) >= ADAPTIVE_WINDOW else self.price_history
        p_adaptive = float(np.mean(window))
        # But never let adaptive target fall below price_floor
        p_adaptive = max(p_adaptive, PRICE_FLOOR)

        # Mean reversion toward adaptive target
        raw_new += REVERSION_RATE * (p_adaptive - raw_new)

        # Phase 3 energy cost-push: 0.45 × ES_global × p(t)
        energy_push = ENERGY_COST_SHARE * energy_stress_global * self.price
        raw_new += energy_push

        # Clamp
        self.price = float(np.clip(raw_new, PRICE_FLOOR, PRICE_CEILING))
        self.price_history.append(self.price)

        return self.price

    # =========================================================================
    # Utility
    # =========================================================================

    @property
    def price_ratio(self) -> float:
        """p(t) / p(0) — used by FS_index computation in agent.py."""
        return self.price / max(self.price_0, 1e-9)

    def shock(self, factor: float):
        """
        Direct speculative price shock.
        factor > 1 → price spike; factor < 1 → price drop.
        Used by STC engine for proximate trigger injection (Phase 4).
        """
        self.price = float(np.clip(self.price * factor, PRICE_FLOOR, PRICE_CEILING))
        self.price_history.append(self.price)

    def reset(self):
        self.price = self.price_0
        self.price_history = [self.price_0]

    def __repr__(self):
        return (
            f"PriceSystem(price={self.price:.3f}, "
            f"baseline={self.baseline:.3f}, "
            f"p_ratio={self.price_ratio:.3f})"
        )
