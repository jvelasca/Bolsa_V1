# Plan — V1.71 Identity & Certification

> **AsOf:** 2026-09-02 · Spec: [`spec-v171-identity-certification-2026-09-02.md`](./spec-v171-identity-certification-2026-09-02.md)

## Entregables

1. Python POV: `recon_status` desde OI-6 en `GET /portfolio`; raise en origin/state desconocidos
2. Cliente POV: source `canonical` \| `blob` · overlay live recon sobre wire · warn DEV en blob
3. Decision Surface: copy `REVISAR` · headlines T2/DRIFT · `assertNever`
4. `gateIntegratedE2eEnvironment` + fixture buy fail-closed + identidad DOM
5. `focusInstrumentsInMercado` + unificación de call-sites
6. Goldens TS/Python + docs + CURRENT_SYSTEM con reservas (no CI GREEN)

## Verificación

Pre-flight spec §3 · E2E integrado **opt-in** (no stamp CI).
