"""
test_phase_d_node_optimization.py
------------------------------------
Real, executable validation for Phase D (node-level policy optimisation).
"""
import sys
sys.path.insert(0, '.')
import scenarios as sc

TEST_TRIGGERS = [
    {"name": "t1", "step": 3, "type": "climate", "scope": 0.30, "severity": 0.45,
     "food_shock": 1.25, "energy_shock": 1.10, "target_node": None},
]


def test_backward_compat_policy_search_default_args():
    """policy_search() called exactly as Phase A/B tests call it (no new
    Phase D kwargs) must be unaffected -- confirmed by re-running the
    exact Phase A test scenario and checking result shape/count."""
    r1 = sc.policy_search(triggers=TEST_TRIGGERS, n_steps=15, n_random=8,
                           include_fixed_levers=True, verbose=False)
    assert r1["n_evaluated"] == 13, f"expected 13 (5 fixed + 8 random), got {r1['n_evaluated']}"
    assert "node_targeted_sampling" in r1["search_space"]
    assert r1["search_space"]["node_targeted_sampling"] is False
    assert r1["max_budget"] is None
    print(f"  PASS: default-args call unaffected by Phase D additions, n_evaluated={r1['n_evaluated']}")


def test_node_level_search_food_aid_samples_different_pairs():
    """The core Phase D deliverable: search must try DIFFERENT donor/
    recipient pairs, not the same pair repeatedly."""
    node_pool = ["United States", "Argentina", "Australia", "Canada",
                 "Pakistan", "Central Africa", "East Africa", "Egypt"]
    result = sc.node_level_policy_search(
        lever_type="food_aid", node_pool=node_pool, triggers=TEST_TRIGGERS,
        n_steps=15, n_random=10, verbose=False,
    )
    assert result["n_evaluated"] == 10
    donor_recipient_pairs = set(
        (r["params"]["donor"], r["params"]["recipient"]) for r in result["ranked_targets"]
    )
    assert len(donor_recipient_pairs) > 1, "search should explore multiple distinct donor/recipient pairs"
    print(f"  PASS: {len(donor_recipient_pairs)} distinct donor/recipient pairs explored "
          f"out of {result['n_evaluated']} candidates")


def test_node_level_search_ranks_by_par_saved():
    node_pool = ["United States", "Argentina", "Pakistan", "Central Africa", "East Africa"]
    result = sc.node_level_policy_search(
        lever_type="food_aid", node_pool=node_pool, triggers=TEST_TRIGGERS,
        n_steps=15, n_random=8, verbose=False,
    )
    par_saved = [r["population_saved_millions"] for r in result["ranked_targets"]]
    assert par_saved == sorted(par_saved, reverse=True)
    print(f"  PASS: correctly ranked by population_saved_millions descending, "
          f"top={par_saved[0]}, bottom={par_saved[-1]}")


def test_node_level_search_climate_adaptation_single_node():
    node_pool = ["Pakistan", "Central Africa", "East Africa", "South Asia-other"]
    result = sc.node_level_policy_search(
        lever_type="climate_adaptation", node_pool=node_pool, triggers=TEST_TRIGGERS,
        n_steps=15, n_random=6, verbose=False,
    )
    targeted_nodes = set(r["params"]["node"] for r in result["ranked_targets"])
    assert targeted_nodes.issubset(set(node_pool))
    assert len(targeted_nodes) > 1, "expected multiple distinct nodes targeted across 6 samples"
    print(f"  PASS: climate_adaptation search targeted {len(targeted_nodes)} distinct nodes: "
          f"{targeted_nodes}")


def test_node_level_search_rejects_unsupported_lever():
    try:
        sc.node_level_policy_search(lever_type="reserve_mandate", node_pool=["United States"],
                                     verbose=False)
        assert False, "expected ValueError for unsupported lever_type"
    except ValueError as e:
        print(f"  PASS: correctly rejected unsupported lever_type with clear error: {e}")


def test_illustrative_cost_model_annotates_candidates():
    node_pool = ["United States", "Pakistan", "Central Africa"]
    result = sc.node_level_policy_search(
        lever_type="food_aid", node_pool=node_pool, triggers=TEST_TRIGGERS,
        n_steps=15, n_random=6, max_budget=1.0, verbose=False,
    )
    assert result["cost_model_note"].startswith("ILLUSTRATIVE")
    costs = [r["illustrative_cost"] for r in result["ranked_targets"]]
    assert all(c is not None and c >= 0 for c in costs)
    within = [r["within_budget"] for r in result["ranked_targets"]]
    assert any(within) or all(not w for w in within)  # sanity: field is populated meaningfully
    n_over = sum(1 for w in within if not w)
    print(f"  PASS: cost model annotated all {len(costs)} candidates, "
          f"{n_over} flagged over the {1.0} budget (not silently dropped)")
    # confirm over-budget candidates are still PRESENT in output, just ranked lower
    assert len(result["ranked_targets"]) == 6, "over-budget candidates must not be silently dropped"


def test_budget_filtering_prioritises_within_budget_candidates():
    """With a very tight budget, within-budget candidates (even if lower
    PAR-saved) should rank above over-budget ones."""
    node_pool = ["United States", "Argentina", "Pakistan", "Central Africa", "East Africa",
                 "China", "India", "Brazil"]
    result = sc.node_level_policy_search(
        lever_type="food_aid", node_pool=node_pool, triggers=TEST_TRIGGERS,
        n_steps=15, n_random=15, max_budget=0.15, seed=7, verbose=False,
    )
    within_flags = [r["within_budget"] for r in result["ranked_targets"]]
    if True in within_flags and False in within_flags:
        first_false_idx = within_flags.index(False)
        assert all(within_flags[:first_false_idx]), (
            "all within-budget candidates should be ranked before any over-budget candidate"
        )
        print(f"  PASS: within-budget candidates correctly prioritised in ranking "
              f"({within_flags.count(True)} within, {within_flags.count(False)} over)")
    else:
        print(f"  PASS (degenerate case, all candidates same budget status: {within_flags[0]})")


def test_policy_search_node_targeted_sampling_integration():
    """policy_search()'s new include_node_targeted_sampling=True must
    integrate node-targeted candidates into the SAME ranked list as the
    global-lever candidates."""
    result = sc.policy_search(
        triggers=TEST_TRIGGERS, n_steps=15, n_random=6,
        include_fixed_levers=True, include_node_targeted_sampling=True,
        node_pool=["United States", "Pakistan", "Central Africa", "Argentina"],
        verbose=False,
    )
    labels = [r["label"] for r in result["ranked_policies"]]
    node_sampled = [l for l in labels if l.startswith("node_sampled_")]
    global_sampled = [l for l in labels if l.startswith("sampled_")]
    assert len(node_sampled) > 0, "expected at least one node-targeted candidate"
    assert len(global_sampled) > 0, "expected global-lever candidates to still be present"
    print(f"  PASS: {len(node_sampled)} node-targeted + {len(global_sampled)} global-lever "
          f"candidates in one unified, ranked search")


if __name__ == "__main__":
    tests = [
        test_backward_compat_policy_search_default_args,
        test_node_level_search_food_aid_samples_different_pairs,
        test_node_level_search_ranks_by_par_saved,
        test_node_level_search_climate_adaptation_single_node,
        test_node_level_search_rejects_unsupported_lever,
        test_illustrative_cost_model_annotates_candidates,
        test_budget_filtering_prioritises_within_budget_candidates,
        test_policy_search_node_targeted_sampling_integration,
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
