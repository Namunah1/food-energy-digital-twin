# Policy: Food Aid

*Extracted directly from `model/src/scenarios.py::make_food_aid_lever`'s real signature and docstring via Python introspection -- not hand-transcribed.*

## Signature

```python
make_food_aid_lever(donor_name: str, recipient_name: str, aid_fraction: float = 0.05)
```

## Full documentation (from source)

```
B2: International food aid -- a direct node-to-node stock transfer
that BYPASSES the trade network's gravity model entirely (no
capacity, cost, or affordability constraint), consistent with
real-world food aid being economically distinct from trade precisely
because it isn't subject to those constraints (Digital Twin spec
Part B2).

Equation: aid = aid_fraction * donor.food_imperish;
          donor.food_imperish -= aid; recipient.food_imperish += aid
```

## Cross-references

- Source file: `model/src/scenarios.py`
- Traceability entry: `docs/TRACEABILITY_MATRIX.md`
- Implementation report: see `docs/implementation/` for the phase that built this
- Tests: `tests/model/test_phase_*.py` (search for `make_food_aid_lever`)