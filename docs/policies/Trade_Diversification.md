# Policy: Trade Diversification

*Extracted directly from `model/src/political_economy.py::apply_diversification`'s real signature and docstring via Python introspection -- not hand-transcribed.*

## Signature

```python
apply_diversification(self, model: 'FoodEnergyModel', n_new_routes: int = 10)
```

## Full documentation (from source)

```
Policy response: trade route diversification.
Re-enables N random disabled edges (proxy for finding alternative suppliers).
Reduces SAV_homogeneity.
```

## Cross-references

- Source file: `model/src/political_economy.py`
- Traceability entry: `docs/TRACEABILITY_MATRIX.md`
- Implementation report: see `docs/implementation/` for the phase that built this
- Tests: `tests/model/test_phase_*.py` (search for `apply_diversification`)