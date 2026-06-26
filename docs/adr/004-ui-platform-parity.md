# ADR-004: UI / platform parity — hybrid delivery model

**Status:** Accepted  
**Date:** 2026-06-11  
**Context:** Option B (continue platform build) without repeating a full UI rewrite later.

## Decision

Every iteration delivers **one platform workstream** and **one UI parity slice**, bound by shared layout primitives and a three-tier UI quality bar.

Platform features must not merge without at least **Tier 1** UI (functional, uses design system). Golden-path features target **Tier 2** (polished).

## UI quality tiers

| Tier | Name | Rule |
|------|------|------|
| **T0** | API-only | Internal hooks, workers, gateway — no UI required |
| **T1** | Functional | Uses `AppShell`, `PageHeader`, `EmptyState`, `StatCard`; i18n keys; accessible |
| **T2** | Polished | Golden-path only: catalog, dataset detail, publish → review → publish |

No new staff/admin route may ship above T0.

## Shared layout (single source of truth)

All staff surfaces use `AppShell` + surface nav from `lib/navigation/surfaces.ts`:

- **Public** — `PublicHeader` (catalog, dataset pages)
- **Publisher** — dashboard, publish, notifications
- **Steward** — review, approval
- **Admin** — IT console
- **Developer** — API console

Do not add a sixth header pattern.

## Iteration template (hybrid)

Each iteration **must** include:

1. **Platform** — backend, infra, or connector (the “hard” work)
2. **UI parity** — migrate N routes to Tier 1, or 1 golden route to Tier 2
3. **Gate** — pytest + Playwright for touched routes + `npm run build`

Example split: 70% platform / 30% UI parity (time), not 100% platform then 100% UI.

## Golden paths (Tier 2 priority order)

1. Citizen: catalog → dataset → download / preview  
2. Publisher: publish → ingest → submit for review  
3. Steward: review queue → approve → published API live  

All other routes stay Tier 1 until golden paths are Tier 2.

## Definition of done (feature)

- [ ] API + OpenAPI accurate  
- [ ] Tier 1 UI page or section using layout primitives  
- [ ] i18n key in `en.json` (+ ar/fr/es/zh for user-visible strings)  
- [ ] Playwright smoke if route is staff-facing  
- [ ] No hardcoded English in new UI code  

## Consequences

- Slightly slower per-iteration platform velocity  
- No “big bang” UI rewrite  
- New pages inherit branding, nav, empty states automatically  
- Status doc tracks **platform %** and **UI tier %** separately (no blended “92%”)
