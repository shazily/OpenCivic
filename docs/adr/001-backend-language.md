# ADR-001: Backend language — Python (FastAPI)

**Status:** Accepted  
**Date:** 2026-05-24

## Decision
Python 3.12 with FastAPI.

## Context
Platform requires: data processing, ML/AI integrations, database connectors, async API.

## Rationale
Best data ecosystem: pandas, SQLAlchemy, LangChain, sentence-transformers, PyHive, DuckDB all native Python. Async with asyncio + uvicorn. FastAPI auto-generates OpenAPI 3.1.

## Alternatives considered
- Node.js: fights data manipulation at every turn
- Go: best concurrency, hardest to hire for data work
- Python+Go hybrid: unnecessary complexity for v1

## Consequences
All connector, worker, and API code in Python. No mixing.
