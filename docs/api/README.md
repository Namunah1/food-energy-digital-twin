# docs/api/

No hand-written per-endpoint reference was produced this consolidation
pass. Rationale (also in `docs/FINAL_AUDIT.md`): FastAPI already
generates an accurate, always-in-sync reference from the same source of
truth (`backend/app/main.py`'s route decorators and
`backend/app/schemas.py`'s Pydantic models) via its automatic Swagger UI
at `/docs` once the server is running. A hand-written duplicate risks
drifting out of sync with the real code — judged a worse outcome than
directing readers to the live, self-updating one. See `USER_GUIDE.md`
for example requests against the newest endpoints
(`/api/policy_search`, `/api/policy_search/node_level`).
