# Spec — V1.78 Session Golden MERCADO→EXIT (mock)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + E2E mock locales; **sin stamp CI GREEN**; commit pendiente).  
> **Padre:** [`spec-v177-session-reliability-2026-09-02.md`](./spec-v177-session-reliability-2026-09-02.md) · relevo [`traspaso-relevo-v1-77-session-reliability-2026-09-02.md`](./traspaso-relevo-v1-77-session-reliability-2026-09-02.md).  
> **Partida tip:** **V1.77** Session Reliability [`1f25d351`](https://github.com/jvelasca/Bolsa_V1/commit/1f25d351) (docs stamp `c9301851`). **No** LIVE.

Certificación **journey-style mock E2E** del arco operativo aspiracional MERCADO→EXIT en superficies Hoy + Mercado. No es el golden pytest Paper Desk (V1.53/V1.55) ni un reloj de sesión de producción. Une candidatura de entrada, deny stale, posición, T1, trail, recon y salida — siempre con **verdad operativa** y **0 COMPRAR ambiguo**.

```text
MERCADO (candidato)
→ Hoy ENTRY (dryRun / AUTO off)
→ STALE → recovery
→ POSITION
→ T1
→ TRAIL
→ RECON DRIFT → clean
→ EXIT
```

Regla absoluta: **NINGÚN estado ambiguo → COMPRAR**.  
`Paper execution` en este slice = wire **honesto dryRun** (`dryRun=true` · `paperDExecute=false`) — **no** fills ledger · **no** `dryRun=false` browser.

```text
P0  GP-V178-01 — MERCADO candidato (NVDA entry-only): entry surface · sin positionId · 0 COMPRAR
P0  GP-V178-02 — Hoy ENTRY opportunity + AUTO armado · ejecución off · 0 COMPRAR
P0  GP-V178-03 — Hoy STALE deny → BLOCKED/ENTRY_STALE_DATA · recovery sin inventar COMPRAR
P0  GP-V178-04 — POSITION Mercado: identidad + verdad operativa (phase posicion)
P1  GP-V178-05 — T1_READY: POV Reducir · data-pov-state · 0 COMPRAR · IDs
P1  GP-V178-06 — TRAILING: POV trail/Proteger · 0 COMPRAR · IDs
P1  GP-V178-07 — RECON DRIFT → REVISAR → clean · 0 COMPRAR
P1  GP-V178-08 — EXIT_REQUIRED: POV Salir · 0 COMPRAR · IDs intactos
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler prod · sin bump `1.35.0-beta` · sin `dryRun=false` browser · sin stamp CI GREEN obligatorio.  
V1.72–V1.77 intactos.

## 1. Entregables

1. Flags `deskMode` / `positionStage` + `installGoldenSessionMocks` en `fixtures.ts`
2. Helpers `assertEntryCandidateTruth` · `assertPovOperatingStage` · `applyGoldenPositionStage` en `integration.ts`
3. `apps/web/e2e/gp-v178-session-golden-mercado-exit-mock.spec.ts` (GP-V178-01..08)
4. Docs cierre: auditor · relevo · CURRENT_SYSTEM · engineering-index

## 2. OUT

- LIVE · scheduler · bump · `dryRun=false` browser · fills ledger
- Stamp CI GREEN remoto · T2_READY obligatorio · rewrite motor

## 3. Pre-flight (local 2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v178
# → 8 passed

E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-v173|gp-v174|gp-v175|gp-v176|gp-v177"
# → 20 passed (3 integrated skipped)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```
