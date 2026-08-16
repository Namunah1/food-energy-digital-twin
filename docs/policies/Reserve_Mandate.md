# Policy: Reserve Mandate

*Extracted directly from `model/src/scenarios.py::make_reserve_mandate_lever`'s real signature and docstring via Python introspection -- not hand-transcribed.*

## Signature

```python
make_reserve_mandate_lever(target_months: float)
```

## Full documentation (from source)

```
Parameterised reserve-mandate lever factory.

Reuses PoliticalEconomyModule.apply_reserve_mandate() UNCHANGED (that
function already accepted target_months -- it was simply never called
with anything but the hardcoded 3.0 from _reserve_mandate()). This
factory does not duplicate that mechanism; it exposes the parameter
that already existed.

Equation (unchanged from political_economy.py):
    target_i = (target_months / 12) * D_i
    transfer_i = min(reserves_i, max(0, target_i - food_imperish_i))
    reserves_i -= transfer_i ; food_imperish_i += transfer_i

Known limitation (documented in the implementation audit): this is a
reclassification of existing stock, not new food. For a node with
reserves_i ≈ 0 (e.g. Central Africa, per the Phase 2.5 diagnostic),
increasing target_months has ZERO effect regardless of its value --
the search below will surface this empirically (Section "expected
finding" in the validation test), not just as a documented caveat.
```

## Cross-references

- Source file: `model/src/scenarios.py`
- Traceability entry: `docs/TRACEABILITY_MATRIX.md`
- Implementation report: see `docs/implementation/` for the phase that built this
- Tests: `tests/model/test_phase_*.py` (search for `make_reserve_mandate_lever`)