# deployment/

**What's real here:** `Dockerfile.backend`, `Dockerfile.frontend` (copies
of the working Dockerfiles referenced by the repo-root `docker-compose.yml`
— use that file for local/single-machine deployment; it is tested and
matches the "current, real architecture" described in
`docs/architecture/DEPLOYMENT_ARCHITECTURE.md` Section 17).

**What's NOT here, and why:** Kubernetes manifests, a job queue
configuration (NATS JetStream), KEDA autoscaling policies, and a Postgres
migration for the experiment store. `docs/architecture/DEPLOYMENT_ARCHITECTURE.md`
contains a complete, reasoned design for all of these (Sections 1-5), but
**no YAML manifests or migration scripts were ever written** — that
document is an architecture proposal, not an implementation. Building
those manifests is real, substantial future work, not a packaging task —
flagged explicitly here rather than fabricating placeholder YAML that
would imply more deployment maturity than actually exists.
