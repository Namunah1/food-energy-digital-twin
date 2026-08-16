# Policy: Fertilizer Support Interim

*Extracted directly from `model/src/scenarios.py::make_fertilizer_support_lever_INTERIM`'s real signature and docstring via Python introspection -- not hand-transcribed.*

## Signature

```python
make_fertilizer_support_lever_INTERIM(node_name: str, support_level: float = 0.3)
```

## Full documentation (from source)

```
B4 INTERIM: fertilizer support, routed through the existing
energy-food coupling channel (the only real mechanism fertilizer
currently has -- confirmed by the implementation audit's
SHOCK_TYPE_MAP finding: `fertilizer_shortage` already maps onto the
generic geopolitical/speculative trigger types, not a dedicated
state).

THIS IS NOT THE FULL B4 MECHANISM. The Digital Twin spec Part C3
calls for genuine Phi_i = (N_i, P_i, K_i) stocks and a
Mitscherlich-type production-response function -- that requires new
state variables and is explicitly Phase C's job, not this one. This
interim lever provides a directionally-correct, clearly-labelled
placeholder: it boosts the target node's effective fuel-energy input
(agent.py's Cobb-Douglas E term), representing "fertilizer support
eases the input-cost squeeze" without claiming to model nitrogen/
phosphorus/potash individually.
```

## Cross-references

- Source file: `model/src/scenarios.py`
- Traceability entry: `docs/TRACEABILITY_MATRIX.md`
- Implementation report: see `docs/implementation/` for the phase that built this
- Tests: `tests/model/test_phase_*.py` (search for `make_fertilizer_support_lever_INTERIM`)