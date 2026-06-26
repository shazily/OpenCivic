# ADR-002: Multi-tenancy — hybrid three-tier model

**Status:** Accepted  
**Date:** 2026-05-24

## Decision
Standard tenants: shared schema + RLS. Professional: schema-per-tenant. Enterprise: DB-per-tenant. RLS on every table in every tier.

## Rationale
Single model cannot optimise for both scale (thousands of small tenants) and isolation (central banks requiring legal separation). RLS as defence-in-depth regardless of tier.

## Consequences
Provisioning worker must know which tier. Application sets search_path and app.tenant_id on every transaction. No cross-schema queries — ever.
