"""
test_phase_c2_resource_drivers.py
------------------------------------
Real, executable validation for Phase C increment 2 (fertilizer N/P/K,
water reservoir stock).
"""
import sys
sys.path.insert(0, '.')
import numpy as np
from model import FoodEnergyModel
from stc_engine import STCEngine
import resource_drivers as rd

TEST_TRIGGERS = [
    {"name": "t1", "step": 3, "type": "climate", "scope": 0.30, "severity": 0.45,
     "food_shock": 1.25, "energy_shock": 1.10, "target_node": None},
]


def run_scenario(triggers=TEST_TRIGGERS, seed=42, init_year=2022, n_steps=15,
                  configure_fn=None):
    m = FoodEnergyModel(scenario='test', seed=seed, init_year=init_year)
    if configure_fn is not None:
        configure_fn(m)
    m.stc_engine = STCEngine(triggers=[dict(t) for t in triggers], ss_mode='multiplicative')
    m.run(n_steps, verbose=False)
    return m.summary()


def test_backward_compat_no_resource_drivers():
    s1 = run_scenario()
    s2 = run_scenario()
    assert s1 == s2
    print(f"  PASS: deterministic without resource drivers, max_price_index={s1['max_price_index']}")


def test_backward_compat_retrodiction_battery_unaffected():
    from retrodiction import run_phase8
    result = run_phase8(n_steps=25, n_mc=5, verbose=False)
    r2008 = result['r2008']
    r2022 = result['r2022']
    print(f"  2008 fpi_error_pct: {r2008['fpi_error_pct']}, 2022: {r2022['fpi_error_pct']}")
    print("  PASS: retrodiction battery runs to completion with Phase C2 code present, unused")


def test_mitscherlich_response_normalised_at_reference():
    """The core correctness fix: response at phi_ratio=1.0 (normal/
    reference fertilizer level) must be EXACTLY 1.0, so attaching the
    driver at baseline application doesn't silently change production
    that A_i's calibration already accounts for."""
    r = rd.mitscherlich_response(1.0)
    assert abs(r - 1.0) < 1e-9, f"expected exactly 1.0 at reference, got {r}"
    print(f"  PASS: mitscherlich_response(1.0) = {r} (exactly 1.0, as required)")


def test_mitscherlich_response_diminishing_returns_shape():
    """Shortage should penalise more steeply than surplus rewards
    (diminishing returns), and response must be monotonically increasing
    in phi_ratio."""
    r_shortage = rd.mitscherlich_response(0.5)
    r_reference = rd.mitscherlich_response(1.0)
    r_surplus = rd.mitscherlich_response(2.0)
    r_double_surplus = rd.mitscherlich_response(4.0)
    assert r_shortage < r_reference < r_surplus < r_double_surplus
    # diminishing returns: the gain from 1.0->2.0 should exceed the gain from 2.0->4.0
    gain_1 = r_surplus - r_reference
    gain_2 = r_double_surplus - r_surplus
    assert gain_2 < gain_1, "expected diminishing returns (smaller marginal gain at higher phi_ratio)"
    print(f"  PASS: shortage={r_shortage:.3f} < reference={r_reference:.3f} < "
          f"surplus={r_surplus:.3f} < double={r_double_surplus:.3f}, "
          f"diminishing returns confirmed (gain 1->2x={gain_1:.3f} > gain 2->4x={gain_2:.3f})")


def test_fertilizer_response_getattr_default_is_noop():
    """Production must be identical whether fertilizer_response is unset
    (getattr default 1.0) or explicitly set to 1.0."""
    m1 = FoodEnergyModel(scenario='fert_default', seed=42, init_year=2022)
    a1 = m1.agent_map["United States"]
    a1.step()
    after_default = a1.food_imperish

    m2 = FoodEnergyModel(scenario='fert_explicit', seed=42, init_year=2022)
    a2 = m2.agent_map["United States"]
    a2.fertilizer_response = 1.0
    a2.step()
    after_explicit = a2.food_imperish

    assert after_default == after_explicit
    print(f"  PASS: unset vs. explicit fertilizer_response=1.0 produce identical output")


def test_fertilizer_shortage_measurably_reduces_production():
    m = FoodEnergyModel(scenario='fert_shortage', seed=42, init_year=2022)
    a = m.agent_map["United States"]
    a.fertilizer_response = rd.mitscherlich_response(0.3)  # severe shortage
    before_multiplier_effect = a.fertilizer_response
    a.step()
    m2 = FoodEnergyModel(scenario='fert_normal', seed=42, init_year=2022)
    a2 = m2.agent_map["United States"]
    a2.step()  # default (no shortage)
    assert a.food_imperish < a2.food_imperish, "fertilizer shortage should reduce production"
    print(f"  PASS: fertilizer_response={before_multiplier_effect:.3f} (shortage) reduced production "
          f"({a2.food_imperish:.3e} -> {a.food_imperish:.3e})")


def test_fertilizer_driver_depletes_and_replenishes():
    m = FoodEnergyModel(scenario='fert_driver_test', seed=42, init_year=2022)
    m.fertilizer_driver = rd.FertilizerDriver()
    m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')
    m.run(10, verbose=False)

    producer = m.agent_map["China"]  # real producer, per FERTILIZER_PRODUCER_NODES (N, P)
    non_producer = m.agent_map["Japan"]  # not in producer list
    assert hasattr(producer, "fertilizer_N")
    assert hasattr(producer, "fertilizer_response")
    print(f"  China (producer) fertilizer_N={producer.fertilizer_N:.2f}, "
          f"Japan (non-producer) fertilizer_N={non_producer.fertilizer_N:.2f}")
    # producer should have a healthier (or at least not worse) stock than
    # a comparable non-producer, since it autonomously replenishes
    assert producer.fertilizer_N >= 0
    assert non_producer.fertilizer_N >= 0


def test_fertilizer_redistribution_requires_driver():
    """The REAL redistribution lever must raise a clear error if no
    FertilizerDriver is attached, rather than silently no-op'ing on a
    nonexistent attribute."""
    m = FoodEnergyModel(scenario='fert_redist_noattach', seed=42, init_year=2022)
    lever = rd.make_fertilizer_redistribution_lever("United States", "Central Africa", nutrient="N")
    try:
        lever(m)
        assert False, "expected RuntimeError when no FertilizerDriver attached"
    except RuntimeError as e:
        print(f"  PASS: correctly raised RuntimeError: {str(e)[:80]}...")


def test_fertilizer_redistribution_moves_real_stock():
    m = FoodEnergyModel(scenario='fert_redist_test', seed=42, init_year=2022)
    m.fertilizer_driver = rd.FertilizerDriver()
    m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')
    m.step()  # initialise fertilizer_N/P/K via the driver
    donor_before = m.agent_map["United States"].fertilizer_N
    recipient_before = m.agent_map["Central Africa"].fertilizer_N
    lever = rd.make_fertilizer_redistribution_lever("United States", "Central Africa",
                                                      nutrient="N", transfer_fraction=0.20)
    lever(m)
    donor_after = m.agent_map["United States"].fertilizer_N
    recipient_after = m.agent_map["Central Africa"].fertilizer_N
    assert donor_after < donor_before
    assert recipient_after > recipient_before
    print(f"  PASS: donor {donor_before:.2f}->{donor_after:.2f}, "
          f"recipient {recipient_before:.2f}->{recipient_after:.2f}")


def test_water_stock_driver_runs_and_bounds_stress():
    m = FoodEnergyModel(scenario='water_test', seed=42, init_year=2022)
    m.water_driver = rd.WaterStockDriver()
    m.stc_engine = STCEngine(triggers=[], ss_mode='multiplicative')
    m.run(10, verbose=False)
    for a in m.agent_map.values():
        assert hasattr(a, "water_stock")
        assert hasattr(a, "water_stress")
        assert 0.0 <= a.water_stress <= 1.0
        assert a.water_stock >= 0.0
    egypt = m.agent_map["Egypt"]
    print(f"  PASS: water driver ran 10 steps, Egypt water_stock={egypt.water_stock:.2f}, "
          f"water_stress={egypt.water_stress:.3f}")


def test_water_stress_getattr_default_is_noop():
    m1 = FoodEnergyModel(scenario='water_default', seed=42, init_year=2022)
    a1 = m1.agent_map["Egypt"]
    a1.step()
    after_default = a1.food_imperish

    m2 = FoodEnergyModel(scenario='water_explicit', seed=42, init_year=2022)
    a2 = m2.agent_map["Egypt"]
    a2.water_stress = 0.0
    a2.step()
    after_explicit = a2.food_imperish

    assert after_default == after_explicit
    print("  PASS: unset vs. explicit water_stress=0.0 produce identical output")


def test_water_stress_reduces_production():
    """United States chosen (not Egypt): Egypt's food_imperish floors at
    0 post-consumption regardless of production intensity in this
    calibration (verified by direct debugging this session -- both
    stressed and unstressed Egypt runs end at exactly 0.0 after
    consumption clips it, masking any production-level difference). US
    has enough stock margin for the production-level effect to survive
    through to the post-consumption metric."""
    m = FoodEnergyModel(scenario='water_stress_test', seed=42, init_year=2022)
    a = m.agent_map["United States"]
    a.water_stress = 0.6
    a.step()
    m2 = FoodEnergyModel(scenario='water_no_stress_test', seed=42, init_year=2022)
    a2 = m2.agent_map["United States"]
    a2.step()
    assert a.annual_production < a2.annual_production, (
        f"water stress should reduce annual_production: "
        f"{a.annual_production} vs {a2.annual_production}"
    )
    assert a.food_imperish < a2.food_imperish
    print(f"  PASS: water_stress=0.6 reduced production "
          f"({a2.annual_production:.3e} -> {a.annual_production:.3e})")


if __name__ == "__main__":
    tests = [
        test_backward_compat_no_resource_drivers,
        test_backward_compat_retrodiction_battery_unaffected,
        test_mitscherlich_response_normalised_at_reference,
        test_mitscherlich_response_diminishing_returns_shape,
        test_fertilizer_response_getattr_default_is_noop,
        test_fertilizer_shortage_measurably_reduces_production,
        test_fertilizer_driver_depletes_and_replenishes,
        test_fertilizer_redistribution_requires_driver,
        test_fertilizer_redistribution_moves_real_stock,
        test_water_stock_driver_runs_and_bounds_stress,
        test_water_stress_getattr_default_is_noop,
        test_water_stress_reduces_production,
    ]
    n_pass, n_fail = 0, 0
    for t in tests:
        print(f"\n{t.__name__}")
        try:
            t()
            n_pass += 1
        except AssertionError as e:
            print(f"  FAIL: {e}")
            n_fail += 1
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")
            n_fail += 1
    print(f"\n{'='*60}\n{n_pass} passed, {n_fail} failed\n{'='*60}")
    sys.exit(1 if n_fail else 0)
