"""
tests/api/test_endpoints.py
-----------------------------
Real pytest-compatible API test suite (new this consolidation pass —
prior sessions verified endpoints ad hoc via FastAPI TestClient scripts;
this formalizes that into a real, repeatable suite under tests/).

Run from repo root: `pytest tests/api/test_endpoints.py -v`
Requires backend/app on the Python path and model/src importable —
see tests/README.md for the exact PYTHONPATH setup this project's
existing (non-packaged) import convention requires.
"""
import sys
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "model", "src"))

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_countries_list():
    r = client.get("/api/countries")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 35, f"expected 35 nodes, got {len(data)}"


def test_baseline_metrics():
    r = client.get("/api/baseline/metrics?steps=5")
    assert r.status_code == 200
    assert "summary" in r.json()


def test_network():
    r = client.get("/api/network?steps=5")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) == 35
    assert len(data["edges"]) > 0


def test_policy_optimization_original_endpoint_unaffected():
    """Regression check: the pre-existing endpoint (unmodified across
    all five implementation phases) still works exactly as before."""
    r = client.post("/api/policy_optimization", json={
        "shocks": [], "start_year": 2022, "n_steps": 15, "seed": 42
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data["ranked_policies"]) == 5
    assert "note" in data


def test_policy_search_phase_a():
    r = client.post("/api/policy_search", json={
        "shocks": [{"shock_type": "climate_drought", "target_node": None,
                     "start_step": 3, "duration": 4, "severity": 0.45, "scope": 0.3}],
        "start_year": 2022, "n_steps": 15, "n_random": 3, "seed": 42,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["n_evaluated"] == 8  # 5 fixed + 3 random
    assert data["ranked_policies"] == sorted(
        data["ranked_policies"], key=lambda p: -p["population_saved_millions"]
    )


def test_policy_search_phase_b_custom_levers():
    r = client.post("/api/policy_search", json={
        "shocks": [], "start_year": 2022, "n_steps": 15, "n_random": 0, "seed": 42,
        "custom_levers": [
            {"type": "food_aid", "donor": "United States", "recipient": "Pakistan",
             "aid_fraction": 0.08},
        ],
    })
    assert r.status_code == 200
    labels = [p["label"] for p in r.json()["ranked_policies"]]
    assert any("custom_0_food_aid" in l for l in labels)


def test_policy_search_node_level_phase_d():
    r = client.post("/api/policy_search/node_level", json={
        "lever_type": "food_aid",
        "node_pool": ["United States", "Argentina", "Pakistan", "Central Africa"],
        "shocks": [], "start_year": 2022, "n_steps": 15, "n_random": 4, "seed": 42,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["n_evaluated"] == 4
    assert data["cost_model_note"].startswith("ILLUSTRATIVE")


def test_policy_search_node_level_rejects_bad_lever():
    r = client.post("/api/policy_search/node_level", json={
        "lever_type": "not_a_real_lever",
        "node_pool": ["United States", "Pakistan"],
        "shocks": [], "start_year": 2022, "n_steps": 15,
    })
    # Should surface as a 4xx/5xx, not a silent 200 with wrong data
    assert r.status_code >= 400


def test_scenarios_registry():
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    names = [s["name"] for s in r.json()]
    assert "S3_reserve_mandate" in names
    assert "S5_transformational" in names


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
