"""
calibrate_rc_price_amp.py
--------------------------
Replaces the hand-derived RC_PRICE_AMPLIFICATION = 0.021 (originally
back-solved from the 2008 crisis alone, against the pre-fix trade network
and climate data -- see stc_engine.py's BUG-009 comment) with a real
joint optimization against BOTH 2008 and 2022 real FAO FPI targets,
using the corrected ND-GAIN climate data and winsorized FAO trade network.

Why joint, not single-crisis: fitting to one historical episode risks
re-creating the same problem this replaces (a value that happens to
match one crisis by chance, not because the price mechanism is right).
Fitting to two independent crises with different trigger types
(biophysical/energy-price-driven for 2008, geopolitical/export-driven
for 2022) is a much stronger constraint.

Usage:
    python3 calibrate_rc_price_amp.py
"""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

_SRC = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import stc_engine as stc_mod
from retrodiction import (
    _run_retrodiction_episode, _run_monte_carlo_episode,
    REAL_FPI_2008, REAL_FPI_2022, N_MC_RETRO,
)
from stc_engine import triggers_2008_food_energy, triggers_2022_ukraine

INIT_YEAR_2008, STEP_OFFSET_2008 = 2000, -7
INIT_YEAR_2022, STEP_OFFSET_2022 = 2018, -6
N_STEPS = 25

# Equal weighting by default -- both crises should fit comparably well.
# If you want to prioritize one (e.g. 2022 has better data coverage),
# adjust these.
WEIGHT_2008 = 0.5
WEIGHT_2022 = 0.5


def _fpi_for(rc_amp: float, seed: int = 42) -> tuple[float, float]:
    """Single deterministic run (fast) for both episodes at a candidate
    RC_PRICE_AMPLIFICATION value. Returns (model_fpi_2008, model_fpi_2022)."""
    stc_mod.RC_PRICE_AMPLIFICATION = float(rc_amp)

    s2008, _ = _run_retrodiction_episode(
        lambda: triggers_2008_food_energy(step_offset=STEP_OFFSET_2008),
        "calib_2008", N_STEPS, seed=seed, init_year=INIT_YEAR_2008,
    )
    s2022, _ = _run_retrodiction_episode(
        lambda: triggers_2022_ukraine(step_offset=STEP_OFFSET_2022),
        "calib_2022", N_STEPS, seed=seed, init_year=INIT_YEAR_2022,
    )
    return s2008.get("max_price_index", 0.0), s2022.get("max_price_index", 0.0)


def objective(rc_amp: float) -> float:
    """Weighted sum of squared relative errors against both real FPI
    targets. Squared (not absolute) so the optimizer is smooth near the
    optimum; relative (not absolute) error so both crises are weighted
    by their own scale, not FPI's raw magnitude."""
    fpi_2008, fpi_2022 = _fpi_for(rc_amp)
    err_2008 = (fpi_2008 - REAL_FPI_2008) / REAL_FPI_2008
    err_2022 = (fpi_2022 - REAL_FPI_2022) / REAL_FPI_2022
    return WEIGHT_2008 * err_2008**2 + WEIGHT_2022 * err_2022**2


def main():
    print("=" * 60)
    print("  RC_PRICE_AMPLIFICATION joint calibration")
    print("  (replacing hand-derived single-crisis value)")
    print("=" * 60)
    print(f"  Real targets: 2008 FPI={REAL_FPI_2008}, 2022 FPI={REAL_FPI_2022}")
    print(f"  Search bounds: [0.005, 0.06]  (SA sweep range was [0.01, 0.04])")
    print()

    # Old value for comparison
    old_val = 0.021
    old_2008, old_2022 = _fpi_for(old_val)
    print(f"  OLD value {old_val}: model FPI 2008={old_2008:.3f} "
          f"(target {REAL_FPI_2008}, err={abs(old_2008-REAL_FPI_2008)/REAL_FPI_2008*100:.1f}%), "
          f"2022={old_2022:.3f} (target {REAL_FPI_2022}, "
          f"err={abs(old_2022-REAL_FPI_2022)/REAL_FPI_2022*100:.1f}%)")
    print()

    print("  Optimizing (bounded scalar search)...")
    res = minimize_scalar(
        objective, bounds=(0.005, 0.06), method="bounded",
        options={"xatol": 1e-4},
    )
    best_val = float(res.x)
    best_2008, best_2022 = _fpi_for(best_val)
    err_2008 = abs(best_2008 - REAL_FPI_2008) / REAL_FPI_2008 * 100
    err_2022 = abs(best_2022 - REAL_FPI_2022) / REAL_FPI_2022 * 100

    print()
    print(f"  NEW calibrated value: {best_val:.5f}")
    print(f"    2008: model={best_2008:.3f}, target={REAL_FPI_2008}, error={err_2008:.1f}%")
    print(f"    2022: model={best_2022:.3f}, target={REAL_FPI_2022}, error={err_2022:.1f}%")
    print()

    # Validate with full Monte Carlo at the new value (single deterministic
    # run above is for speed during search; confirm with real uncertainty
    # bounds before trusting it)
    print(f"  Validating with {N_MC_RETRO} Monte Carlo runs at the new value...")
    stc_mod.RC_PRICE_AMPLIFICATION = best_val
    mc_2008 = _run_monte_carlo_episode(
        lambda: triggers_2008_food_energy(step_offset=STEP_OFFSET_2008),
        "calib_2008_mc", N_STEPS, n_runs=N_MC_RETRO, init_year=INIT_YEAR_2008,
    )
    mc_2022 = _run_monte_carlo_episode(
        lambda: triggers_2022_ukraine(step_offset=STEP_OFFSET_2022),
        "calib_2022_mc", N_STEPS, n_runs=N_MC_RETRO, init_year=INIT_YEAR_2022,
    )
    m2008 = mc_2008.get("max_price_index", {})
    m2022 = mc_2022.get("max_price_index", {})
    print(f"    2008 MC: {m2008.get('mean',0):.3f} ± {m2008.get('std',0):.3f}")
    print(f"    2022 MC: {m2022.get('mean',0):.3f} ± {m2022.get('std',0):.3f}")

    print()
    print("  ACTION REQUIRED: update stc_engine.py manually:")
    print(f"    RC_PRICE_AMPLIFICATION = {best_val:.5f}  # jointly calibrated")
    print(f"    against 2008 AND 2022 real FPI (was 0.021, hand-derived from")
    print(f"    2008 alone against pre-fix data -- see calibrate_rc_price_amp.py)")


if __name__ == "__main__":
    main()
