# Relevo — V1.79 Stateful Position Lifecycle Certification

> **AsOf:** 2026-09-02 · **Estado:** CERRADA (código + E2E mock locales) · **Auditor:** [`arranque-auditor-v1-79-stateful-position-lifecycle-2026-09-02.md`](./arranque-auditor-v1-79-stateful-position-lifecycle-2026-09-02.md) · **Partida:** V1.78 `e1dcfba8` · **sin stamp CI GREEN**

## Hecho

- Split `apps/web/e2e/integration.ts` → `e2e/helpers/*` + barrel
- Runtime: `deskMode` lifecycle / lifecycle_stale · stages `candidate`…`closed`
- Helpers: `assertIdentityTruth` · `assertFinancialTruth` · `assertPositionCertification` · `assertClosedPositionTruth`
- E2E mock: `gp-v179-stateful-position-lifecycle-mock.spec.ts` (GP-V179-01) — **1 passed**
- Spec/plan/auditor V1.79 · CURRENT_SYSTEM · engineering-index

## Reservas

- Certificación = **mock E2E** local · **no** stamp CI GREEN
- CLOSED = representación UI + wire (`remainingQuantity=0`) · **no** fills ledger · **no** `dryRun=false` browser
- No enum `EXIT_EXECUTED` (terminal de dominio = `CLOSED` + evento `POSITION_CLOSED`)

## Next candidato

**V1.80** — a decidir (CI GREEN del tip · T2 POV · o split `fixtures.ts`). **NO LIVE**.
