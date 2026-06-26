# ADR-003: Valkey not Redis

**Status:** Accepted  
**Date:** 2026-05-24

## Decision
Valkey as drop-in Redis replacement.

## Rationale
Redis changed licence to RSALv2/SSPL in 2024 — not OSI open source. Flagged in every enterprise legal review. Valkey is BSD-licensed, Linux Foundation governed, protocol-compatible.

## Consequences
No code changes — same redis-py client. Just a different container image.
