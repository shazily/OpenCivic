# OpenCivic — Production Readiness Gates

> Last updated: 2026-06-26. All gates must pass before a regulated production promotion.

## Release tiers

| Tier | Audience | Minimum gates |
|------|----------|---------------|
| **Pilot** | Single agency, IT on call | Dev/Keycloak login, manual smoke, `./deploy.sh up` |
| **Production** | Regulated buyer (central bank, NSO) | All gates below green for 7 consecutive days |

## Mandatory CI gates (`.github/workflows/ci.yml`)

| Job | Command / check | Status |
|-----|-----------------|--------|
| Backend test | `pytest tests/ -m "not live and not gateway and not pilot" --cov-fail-under=80` | Required |
| Backend lint | `ruff check app/` | Required |
| Security | `pip-audit -r requirements.txt` (zero HIGH/CRITICAL) | Required |
| Security | `bandit -r app/` | Advisory |
| Frontend | `npm run lint && npm run type-check && npm run build` | Required |
| Gateway | `pytest -m gateway` against nginx:8088 | Required |
| Helm | `python scripts/helm_smoke.py` | Required |
| Docker | Trivy CRITICAL/HIGH scan | Required |

## Runtime verification (pre-promotion)

```bash
./deploy.sh up
cd backend && pytest tests/ -v --cov-fail-under=80
python scripts/verify_release.py
cd frontend && npm run build && npm run test:e2e
```

## Phase completion (must be ≥ 95% for production)

| Phase | Production requirement |
|-------|------------------------|
| Auth (Keycloak SSO, MFA, SCIM) | Full browser login E2E, no dev-token in prod |
| Deploy (HA, pgBackRest, DR drill) | Verified restore < RTO target |
| AI | `AI_MODE=disabled` or Ollama air-gap; injection pipeline on all LLM calls |
| Observability | LGTM stack healthy, alert rules firing in staging |

## Production environment checklist

- [ ] `DEPLOYMENT_MODE` set (`cloud` / `selfhosted` / `airgap`)
- [ ] All `CHANGE_ME` secrets rotated; `DEV_AUTH_ENABLED=false`
- [ ] Keycloak realm per tenant; MFA enforced for admin/publisher/steward
- [ ] TLS 1.3 on Nginx; HSTS enabled
- [ ] Postgres HA (Patroni) or managed RDS with PITR
- [ ] pgBackRest backups verified weekly (automated restore test)
- [ ] APISIX rate limits per tenant; `EDGE_AUTH_ENABLED=true`
- [ ] ClamAV sidecar on uploads
- [ ] No known CVEs in `pip-audit` / Trivy production images

## Known dependency exceptions

The API image audits `requirements.txt` only. AI workers use `requirements-ai.txt` (sentence-transformers / transformers stack) with a separate audit before worker image promotion.

Documented `pip-audit --ignore-vuln` entries in CI (transitive, no stable fix at pin time):

| ID | Package | Reason |
|----|---------|--------|
| CVE-2026-30922 | pyasn1 | Transitive via python-jose 3.4.0 (`pyasn1<0.5`); upgrade when python-jose releases |

## What is NOT production-ready until explicitly signed off

- OData stubs (`$filter`, full server semantics)
- Connector sync history derived from state (not event store)
- Queue depth trend sparklines (synthetic data)
- Governance PDF minimal stub
- Semantic search when Qdrant unavailable (degraded mode only)
