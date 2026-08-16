# Policy: Trader Regulation

*Extracted directly from `model/src/political_economy.py::apply_trader_regulation`'s real signature and docstring via Python introspection -- not hand-transcribed.*

## Signature

```python
apply_trader_regulation(self, margin_cap: float = 0.05)
```

## Full documentation (from source)

```
Policy response: cap trader margins (regulatory intervention).
Reduces SAV_power by limiting profit extraction.
```

## Cross-references

- Source file: `model/src/political_economy.py`
- Traceability entry: `docs/TRACEABILITY_MATRIX.md`
- Implementation report: see `docs/implementation/` for the phase that built this
- Tests: `tests/model/test_phase_*.py` (search for `apply_trader_regulation`)