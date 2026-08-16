# Policy: Import Tariff Subsidy

*Extracted directly from `model/src/scenarios.py::make_import_tariff_lever`'s real signature and docstring via Python introspection -- not hand-transcribed.*

## Signature

```python
make_import_tariff_lever(node_name: str, tariff_multiplier: float = 1.2)
```

## Full documentation (from source)

```
Import tariff (tariff_multiplier > 1.0) or subsidy (< 1.0) on a
specific node's affordability constraint in the gravity trade model.
Consumed by the now-extended trade.py::_gravity_volume (byte-identical
to the original formula when the attribute is unset -- verified in
test_phase_b_policy_levers.py).

Equation: affordable_kcal = K_buyer / (p * tariff_multiplier)^1.2 * 1e12
tariff_multiplier=1.20 represents roughly a 20% import cost increase;
0.80 represents a 20% import subsidy.
```

## Cross-references

- Source file: `model/src/scenarios.py`
- Traceability entry: `docs/TRACEABILITY_MATRIX.md`
- Implementation report: see `docs/implementation/` for the phase that built this
- Tests: `tests/model/test_phase_*.py` (search for `make_import_tariff_lever`)