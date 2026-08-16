# Policy: Global Reserve Pool

*Extracted directly from `model/src/scenarios.py::make_global_reserve_pool_lever`'s real signature and docstring via Python introspection -- not hand-transcribed.*

## Signature

```python
make_global_reserve_pool_lever(levy_threshold_margin: float = 0.1, levy_rate: float = 0.2)
```

## Full documentation (from source)

```
B1 + B8: FAO-style global strategic reserve pool.

IMPLEMENTATION SCOPE NOTE: response_fn levers are called ONCE, before
model.run() starts (confirmed this session: scenarios.py:827,
"applied before run"). A genuinely continuous, every-tick-recalculated
global pool would require a new per-tick hook into model.step()'s
core loop -- which is the same hot path modified carefully in Phase
2.5 and is explicitly out of scope for "extend, don't rewrite."
This is therefore the ONE-TIME REDISTRIBUTION variant: at setup,
nodes with sigma comfortably above their own safety margin contribute
a fraction of their imperishable stock to a pool, which is
immediately redistributed to nodes below their safety margin,
proportional to need. This is a real, testable implementation of the
policy concept (mutual insurance pooling, distinct from the per-node
reserve mandate which only reclassifies a node's OWN stock), not a
placeholder.

Equations:
    contribution_i = min(0.5*F_imperish,i, levy_rate * F_imperish,i *
                          min(1, sigma_i - sigma_safe,i))   [only if sigma_i > sigma_safe,i + margin]
    need_j = max(0, sigma_safe,j - sigma_j) * D_j
    draw_j = pool_total * (need_j / sum_k need_k)
```

## Cross-references

- Source file: `model/src/scenarios.py`
- Traceability entry: `docs/TRACEABILITY_MATRIX.md`
- Implementation report: see `docs/implementation/` for the phase that built this
- Tests: `tests/model/test_phase_*.py` (search for `make_global_reserve_pool_lever`)