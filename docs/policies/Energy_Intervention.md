# Policy: Energy Intervention

*Extracted directly from `model/src/scenarios.py::make_energy_intervention_lever`'s real signature and docstring via Python introspection -- not hand-transcribed.*

## Signature

```python
make_energy_intervention_lever(node_name: Optional[str] = None, release_fraction: float = 0.2, mode: str = 'supply_cut')
```

## Full documentation (from source)

```
B7: Energy interventions (strategic release / price subsidy).

Per the implementation audit (Part B7 finding): "No new mechanism
required" -- this reuses EnergyModule.apply_energy_shock() UNCHANGED,
with a NEGATIVE severity, which that function's existing arithmetic
already correctly interprets as a supply increase / price decrease
(verified this session by reading its exact formula: `energy_fuel *=
(1 - severity)`, so severity<0 multiplies by >1). This factory exists
only to give that reversal a clear, intention-revealing name and a
single-node targeting option (the underlying function shock-scopes
randomly across `scope * 35` nodes; passing scope=1/35 here targets
approximately one node, since apply_energy_shock has no direct
single-node-by-name interface -- a real, documented limitation of the
reused mechanism, not of this wrapper).
```

## Cross-references

- Source file: `model/src/scenarios.py`
- Traceability entry: `docs/TRACEABILITY_MATRIX.md`
- Implementation report: see `docs/implementation/` for the phase that built this
- Tests: `tests/model/test_phase_*.py` (search for `make_energy_intervention_lever`)