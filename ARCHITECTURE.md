# Architecture Overview

This is a short synthesis; the authoritative, detailed documents are
linked throughout. Read this first if you're orienting yourself, then go
deeper via the links.

## The system in one paragraph

35 agents (21 countries + 14 regional blocs), each running a Cobb-Douglas
production function (land, water, energy, technology, climate, soil,
fertilizer, water-stress -- the last three optional/pluggable), connected
by a real directed trade network (`data/processed/network_weights.csv`).
Each simulated year: energy stress updates, agents produce/consume/set
export policy, trade resolves, food security recomputes post-trade, an
STC (Stress-Trigger-Cascade) engine accumulates systemic stress and
detects overload, a global price updates. A FastAPI backend exposes this
for scenario running and policy search; a Next.js frontend provides
interactive access.

## The three architecture documents, and when to read which

1. **`docs/architecture/CAUSAL_DECOMPOSITION.md`**
   -- read this to understand *how the simulation actually behaves*:
   every subsystem's equations, feedback loops, and stability properties,
   traced from the real code. Start here if you're debugging unexpected
   model behaviour.
2. **`docs/architecture/SCIENTIFIC_DESIGN_SPECIFICATION.md`**
   -- the canonical 20-section blueprint: every state/policy/global/
   climate/resource/trade/geopolitical variable, the optimisation
   objective, calibration and validation strategy, software architecture,
   database schema, API contracts. Start here if you're implementing
   something new.
3. **`docs/architecture/DIGITAL_TWIN_ARCHITECTURE.md`**
   -- the original design proposal for the environmental/resource driver
   expansion and policy-lever taxonomy, written before Phases A-E
   implemented most of it. Start here for the *reasoning* behind why
   each driver/lever was designed the way it was; cross-reference against
   `docs/IMPLEMENTATION_AUDIT.md` for what's actually built vs. still
   proposed.

## Software layers

```
frontend/  (Next.js)  --HTTP-->  backend/  (FastAPI)  --imports-->  model/  (Mesa ABM)
                                       |
                                       v
                                  data/  (FAO, World Bank, OWID, ND-GAIN)
```

`backend/app/model_bridge.py` is the seam: every function in it
translates an HTTP request into a call against the canonical model in
`model/src/` and returns the result unmodified. It contains **zero
scientific computation** -- this separation is deliberate and load-
bearing; see `DEVELOPER_GUIDE.md`.

## Deployment

Current, real, working: `docker-compose up` (two containers, backend +
frontend). Proposed, designed, not yet built: Kubernetes, a job queue,
autoscaling, a Postgres migration -- see
`docs/architecture/DEPLOYMENT_ARCHITECTURE.md` and `deployment/README.md`
for exactly where the line between real and proposed sits.

## The one thing to internalize before changing anything

The model's dominant behaviour is governed by a single feedback loop:
overload count -> price shock -> global price -> every node's
food-security stress -> overload count. It has no intrinsic negative
feedback yet (see `docs/architecture/CAUSAL_DECOMPOSITION.md` Section 1).
Almost every other subsystem is either a tributary into this loop or
downstream of it. Understanding this loop first will make the rest of
the codebase make sense faster than reading files in isolation.
