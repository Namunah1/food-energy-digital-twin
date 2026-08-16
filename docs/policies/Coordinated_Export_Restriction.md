# Policy: Coordinated Export Restriction

*Extracted directly from `model/src/scenarios.py::make_coordinated_export_restriction_lever`'s real signature and docstring via Python introspection -- not hand-transcribed.*

## Signature

```python
make_coordinated_export_restriction_lever(target_nodes: list, export_fraction_cap: float = 0.1)
```

## Full documentation (from source)

```
B3: Coordinated export restriction across N named nodes
simultaneously.

Per the Digital Twin spec Part B3: "already fully representable via
the existing 3-regime export policy... the only addition needed is a
policy-layer wrapper that applies the same override to multiple
nodes in one call" -- this IS that wrapper. No new mechanism; reuses
the exact override pattern the `2022_ukraine_block` trigger already
uses (agent.export_fraction direct assignment), generalised to a
node list.
```

## Cross-references

- Source file: `model/src/scenarios.py`
- Traceability entry: `docs/TRACEABILITY_MATRIX.md`
- Implementation report: see `docs/implementation/` for the phase that built this
- Tests: `tests/model/test_phase_*.py` (search for `make_coordinated_export_restriction_lever`)