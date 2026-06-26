# OpenCivic

Enterprise-grade, open-source, AI-native open data portal for governments, central banks, and regulators.

## Quick start (local dev)

```bash
cp .env.example .env
# Edit .env — replace all CHANGE_ME values
./deploy.sh up    # starts backend (Docker) + frontend — one command
./deploy.sh down  # stops everything
```

Frontend: http://localhost:3100  
Gateway (recommended): http://localhost:8088 — API via nginx → APISIX  
API direct: http://localhost:8100/api/v1/health/live  
API docs: http://localhost:8100/api/v1/docs  

On Windows, the frontend runs on the host (Docker `npm install` is unreliable there). On Linux/macOS, Docker frontend is tried first with automatic fallback to the host.

Ports are set in `.env` (`OPENCIVIC_GATEWAY_PORT`, `OPENCIVIC_API_PORT`, `OPENCIVIC_FRONTEND_PORT`). Default gateway is **8088** because **8080** is often taken by other Docker stacks.

Full production stack (20+ services): `./deploy.sh prod up` — use only when you need Keycloak, Celery, observability, etc.

## Documentation

- [Platform Specification](OPENCIVIC_PLATFORM_SPEC.md) — complete architecture, decisions, rules
- [ADRs](docs/adr/) — all architecture decision records
- [Runbooks](docs/runbooks/) — operational procedures
- [API Reference](docs/api/) — endpoint documentation

## Stack

| Layer | Technology |
|---|---|
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 |
| Database | PostgreSQL 16, PgBouncer, pgBackRest |
| Cache/Queue | Valkey (BSD), Celery 5 |
| Vector | Qdrant (Apache 2.0) |
| Storage | Minio (S3-compatible) |
| Auth | Keycloak (per-tenant realms) |
| Gateway | Apache APISIX |
| Frontend | Next.js 14, React 18, TypeScript, shadcn/ui |
| AI | LLMProvider abstraction (OpenAI/Anthropic/Ollama) |
| Observability | Loki + Grafana + Tempo + OpenTelemetry |

All licences: MIT, Apache 2.0, BSD, or PostgreSQL. Zero proprietary dependencies.

## Deployment modes

- **selfhosted**: `./deploy.sh up` — Docker Compose, your infrastructure
- **cloud**: `helm install opencivic` — Kubernetes, multi-region
- **airgap**: `DEPLOYMENT_MODE=airgap ./deploy.sh up` — no external network calls, Ollama LLM

## Development

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

```bash
cd frontend
npm install
npm run dev
```

## Security

Read `OPENCIVIC_PLATFORM_SPEC.md` Section 21 before contributing.  
Security issues: security@opencivic.io  
Bug bounty: HackerOne programme (link TBD)

## Licence

MIT — see LICENSE
