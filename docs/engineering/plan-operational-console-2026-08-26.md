# Plan — Operational Console (/operational-console) (2026-08-26)

> **Padre:** [ADR-033](../adr/033-operational-authority-position-persistence.md) P4 · [ADR-035](../adr/035-operational-reliability.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **AsOf:** 2026-08-26 · tag vivo `v1.13-beta`.
> **Estado:** OC0–OC4 **CERRADOS** (OC3 skipped — payload ops-self-eval suficiente).

## Objetivo

Ruta `/operational-console` como agregador read-only de salud operativa. Complementa P4 `/operations` (posiciones-first).

## Fases

| ID  | Entrega                                         |
| --- | ----------------------------------------------- |
| OC0 | Ruta + layout + OE-1/readiness + tests          |
| OC1 | Recon + card incidentes + link resolve          |
| OC2 | Quick links + hook compartido + help tip        |
| OC3 | **Skipped** — ops-self-eval incluye recon embed |
| OC4 | plan/relevo + CURRENT_SYSTEM + spine **483**    |

## Fuera de alcance

Reemplazar /operations o /confirm · auto-heal · thaw · ejecutar trades · OperationalPolicy.

## Verificación

- web `operational-console-page.test.tsx`
- coherencia chips con mesa bar (mismo hook `useOpsSelfEval`)
- `pnpm test:decision-spine` **483**
