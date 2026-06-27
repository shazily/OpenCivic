# OpenCivic — Production Readiness Gates

> Last updated: 2026-06-11. All gates must pass before a regulated production promotion.

## Release tiers

| Tier | Audience | Minimum gates |
|------|----------|---------------|
| **Pilot** | Single agency, IT on call | Keycloak SSO E2E, `./deploy.sh pilot up` |
| **Production** | Regulated buyer (central bank, NSO) | All gates below green for 7 consecutive days |

## Mandatory CI gates (`.github/workflows/ci.yml`)

| Job | Command / check | Status |
|-----|-----------------|--------|
| Backend test | `pytest tests/ -m "not live and not gateway and not pilot" --cov-fail-under=60` | Required |
| Backend lint | `ruff check app/` | Required |
| Security | `pip-audit -r requirements.txt` (zero HIGH/CRITICAL) | Required |
| Security | `bandit -r app/` | Advisory |
| Frontend | `npm run lint && npm run type-check && npm run build` | Required |
| Gateway | `pytest -m gateway` against nginx:8088 | Required |
| **Release smoke** | `backend/scripts/verify_release.py` + Playwright `smoke.spec.ts` | Required |
| **Pilot auth** | `pytest -m pilot` + Playwright `pilot-auth.spec.ts` (Keycloak overlay) | Required |
| Helm | `python scripts/helm_smoke.py` | Required |
| Docker | Trivy CRITICAL/HIGH scan | Required |

## Runtime verification (pre-promotion)

```bash
# Dev stack (dev-token auth)
./deploy.sh dev up

# API lifecycle smoke (dataset upload → ingest → publish → search)
cd backend && python scripts/verify_release.py --gateway-url http://127.0.0.1:8088

# UI smoke (dev role sign-in)
cd frontend && npm run test:e2e:ci

# Pilot stack (Keycloak SSO, no dev tokens)
./deploy.sh pilot up
cd frontend && OPENCIVIC_PILOT_AUTH=true npm run test:e2e:pilot
```

CI uses `./scripts/ci_release_smoke.sh` to bootstrap Docker Compose and run the same checks.

## Phase completion (must be ≥ 95% for production)

| Phase | Production requirement |
|-------|------------------------|
| Auth (Keycloak SSO, MFA, SCIM) | Pilot CI job green; `DEV_AUTH_ENABLED=false` in prod |
| Deploy (HA, pgBackRest, DR drill) | Verified restore < RTO target (Sprint C) |
| AI | `AI_MODE=disabled` or Ollama air-gap; injection pipeline on all LLM calls |
| Observability | LGTM stack healthy, alert rules firing in staging |

## Production environment checklist

### Identity and secrets

- [ ] `DEPLOYMENT_MODE` set (`cloud` / `selfhosted` / `airgap`)
- [ ] All `CHANGE_ME` secrets rotated; `DEV_AUTH_ENABLED=false`
- [ ] Keycloak realm per tenant; MFA enforced for admin/publisher/steward
- [ ] `KEYCLOAK_CLIENT_SECRET` from Vault/K8s secrets (not in `.env` on disk)
- [ ] `KEYCLOAK_PUBLIC_URL` set to browser-reachable HTTPS origin (e.g. `https://auth.example.gov`)
- [ ] `SECRET_KEY` ≥ 32 chars; unique per environment
- [ ] SCIM webhook secret configured if Azure AD/Okta deprovisioning is enabled

### Network and edge

- [ ] TLS 1.3 on Nginx; HSTS enabled
- [ ] APISIX rate limits per tenant; `EDGE_AUTH_ENABLED=true` for production edge
- [ ] CORS allowlist matches tenant portal domains only (no wildcard)
- [ ] Coraza WAF rules enabled on Nginx

### Data and storage

- [ ] Postgres HA (Patroni) or managed RDS with PITR
- [ ] pgBackRest backups verified weekly (automated restore test — Sprint C)
- [ ] Minio/S3 bucket encryption at rest; lifecycle policies for WAL archives
- [ ] ClamAV sidecar on uploads (`CLAMAV_ENABLED=true`)

### Application

- [ ] `AI_MODE` matches compliance posture (`assist` default; `disabled` for air-gap without Ollama)
- [ ] Celery workers healthy on all six queues; Flower reachable only to IT admin
- [ ] Qdrant collection provisioned per tenant (semantic search degrades gracefully if down)
- [ ] No known CVEs in `pip-audit` / Trivy production images

### Verification before go-live

- [ ] `backend/scripts/verify_release.py` passes against staging gateway URL
- [ ] Playwright pilot auth E2E passes on staging with real IdP (or Keycloak staging realm)
- [ ] `./deploy.sh` smoke completes without manual intervention
- [ ] Runbook documents RTO/RPO and on-call escalation

## Known dependency exceptions

The API image audits `requirements.txt` only. AI workers use `requirements-ai.txt` (sentence-transformers / transformers stack) with a separate audit before worker image promotion.

Documented `pip-audit --ignore-vuln` entries in CI (transitive, no stable fix at pin time):

| ID | Package | Reason |
|----|---------|--------|
| CVE-2026-30922 | pyasn1 | Transitive via python-jose 3.4.0 (`pyasn1<0.5`); upgrade when python-jose releases |

## Coverage gate note

CI enforces `--cov-fail-under=60` while the platform target remains 80%. Raise the gate as test coverage grows; do not promote to production below 80% without explicit risk acceptance.

## What is NOT production-ready until explicitly signed off

- OData stubs (`$filter`, full server semantics)
- Connector sync history derived from state (not event store)
- Queue depth trend sparklines (synthetic data)
- Governance PDF minimal stub
- Semantic search when Qdrant unavailable (degraded mode only)
