# Policy: Climate Adaptation Funding

*Extracted directly from `model/src/scenarios.py::make_climate_adaptation_lever`'s real signature and docstring via Python introspection -- not hand-transcribed.*

## Signature

```python
make_climate_adaptation_lever(node_name: str, effectiveness: float = 0.3)
```

## Full documentation (from source)

```
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
```

## Cross-references

- Source file: `model/src/scenarios.py`
- Traceability entry: `docs/TRACEABILITY_MATRIX.md`
- Implementation report: see `docs/implementation/` for the phase that built this
- Tests: `tests/model/test_phase_*.py` (search for `make_climate_adaptation_lever`)