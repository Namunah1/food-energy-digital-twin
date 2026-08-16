# Policy: Fertilizer Redistribution

*Extracted directly from `model/src/resource_drivers.py::make_fertilizer_redistribution_lever`'s real signature and docstring via Python introspection -- not hand-transcribed.*

## Signature

```python
make_fertilizer_redistribution_lever(donor_name: str, recipient_name: str, nutrient: str = 'N', transfer_fraction: float = 0.2)
```

## Full documentation (from source)

```
B4 REAL (upgrades the Phase B INTERIM proxy): direct transfer of a
named nutrient stock between two nodes, analogous to make_food_aid_lever
but operating on FertilizerDriver's fertilizer_N/P/K state instead of
food_imperish. Requires a FertilizerDriver to be attached to the model
(raises a clear error otherwise, rather than silently no-op'ing on a
nonexistent attribute).
```

## Cross-references

- Source file: `model/src/resource_drivers.py`
- Traceability entry: `docs/TRACEABILITY_MATRIX.md`
- Implementation report: see `docs/implementation/` for the phase that built this
- Tests: `tests/model/test_phase_*.py` (search for `make_fertilizer_redistribution_lever`)