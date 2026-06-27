# UI parity checklist (per PR / iteration)

Copy into PR description when touching features.

## Platform change?

- [ ] API contract documented in OpenAPI  
- [ ] If user-facing: Tier 1 UI uses `PageHeader` + `AppShell` surface  
- [ ] i18n keys added (not hardcoded strings)  
- [ ] Empty and error states use `EmptyState` / alert pattern  

## Golden path touch?

- [ ] Catalog, dataset, publish, review, or approval  
- [ ] Tier 2: loading skeleton, responsive check, keyboard nav  
- [ ] Playwright test updated  

## Never

- [ ] New bespoke header/nav shell  
- [ ] Inline styles instead of design tokens  
- [ ] Ship admin page with only raw `<h1>` and no layout primitives  
