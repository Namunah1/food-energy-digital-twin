# Global Policy: Export-Ban Contagion

## Purpose

Represents beggar-thy-neighbour dynamics: when one node bans exports,
neighbouring nodes' own food security drops (lost imports), making them
probabilistically more likely to ban exports themselves -- a real,
historically-documented pattern (e.g. the cascading export restrictions
during the 2008 and 2010-11 crises).

## Equation

```
P(contagion) = clip(BAN_CONTAGION_RATE * max(0, 1 - sigma_j), 0, BAN_CONTAGION_CAP)
```

Applied per-neighbour, per-tick, when a node's `export_fraction` drops to
zero (`trade.py::_propagate_export_ban`). Full mechanism trace:
`docs/architecture/CAUSAL_DECOMPOSITION.md` Section 6.

## Current value

`BAN_CONTAGION_RATE = 0.30`, `BAN_CONTAGION_CAP = 0.80` (`model/src/trade.py`).

## Scientific source

Hand-set constants -- **not independently calibrated against real
2008/2010/2022 export-ban propagation speed data.** Stated explicitly in
`docs/architecture/CAUSAL_DECOMPOSITION.md` Section 6's assessment.

## Affected nodes

Probabilistically, any node with an outgoing trade edge from a
newly-banning node -- i.e. potentially all 35, though realised effect
concentrates on each banning node's real trading partners
(`network_weights.csv`).

## Affected variables

`agent.export_ban`, `agent.export_fraction` (set to 0 for the affected
neighbour) -- provisionally, for one tick; the next tick's
`update_export_policy()` re-derives these from the neighbour's own
actual food security, so a contagion-induced ban only persists if
independently justified.

## Sensitivity

Not individually Sobol-tested this session (the sensitivity study
covered `RC_PRICE_AMPLIFICATION` and `EROI_DECLINE_RATE` specifically,
per `docs/validation/VALIDATION_REPORT_INITIAL.md` Section 3 -- this
constant was not included in that sweep). Flagged as real, tractable
future work rather than an invented sensitivity figure.

## Known positive property (a genuine, documented stabilising feature)

Unlike `RC_PRICE_AMPLIFICATION`, this mechanism has a real, structural
self-correction: a contagion-induced ban only persists if the affected
node's own sigma independently justifies it the following tick. This is
called out in `docs/architecture/CAUSAL_DECOMPOSITION.md` Section 6 as
"a real, useful self-correcting property."

## Optimisation space

Not a searchable policy lever -- the corresponding POLICY response is
`make_coordinated_export_restriction_lever` (`docs/policies/COORDINATED_EXPORT_RESTRICTION.md`),
which lets a decision-maker deliberately coordinate export restrictions
across named nodes (using the same underlying mechanism this contagion
constant governs unintentionally).
