# Arranque auditor — V1.79 Stateful Position Lifecycle (2026-09-02)

> **Padre:** [`spec-v179-stateful-position-lifecycle-2026-09-02.md`](./spec-v179-stateful-position-lifecycle-2026-09-02.md) · partida **V1.78** [`e1dcfba8`](https://github.com/jvelasca/Bolsa_V1/commit/e1dcfba8)

## Punta de partida

- Producto: **V1.78** Session Golden MERCADO→EXIT (E2E mock locales; sin CI GREEN)
- Brecha: GP-V178-04..08 son fixtures independientes; EXIT_REQUIRED ≠ CLOSED; recovery stale no aserta desaparición del deny
- Regla: **NINGÚN estado ambiguo → COMPRAR** · dryRun honesto ≠ execute ledger · **no** enum `EXIT_EXECUTED`

## Qué auditar

| Paso          | Evidencia                                                                                            |
| ------------- | ---------------------------------------------------------------------------------------------------- |
| CANDIDATO     | AAPL entry surface · sin positionId · 0 COMPRAR                                                      |
| ENTRY         | Hoy AUTO armado · ejecución off · dryRun · paperDExecute=false · 0 COMPRAR                           |
| STALE         | BLOCKED + ENTRY_STALE_DATA · 0 COMPRAR                                                               |
| RECOVERY      | deny **ausente** · 0 ENTRY_STALE_DATA · 0 BLOCKED de ese ítem · 0 COMPRAR                            |
| OPEN          | IDs congelados · phase posicion · stop/T1/T2 · 0 COMPRAR                                             |
| T1_READY      | data-pov-state=T1_READY · Reducir · remaining 10                                                     |
| T1_EXECUTED   | data-pov-state=T1_EXECUTED · remaining 5 · qty nacimiento 10                                         |
| TRAILING      | data-pov-state=TRAILING · Proteger                                                                   |
| RECON DRIFT   | data-recon=CRITICAL · Revisar · IDs intactos                                                         |
| RECON CLEAN   | data-recon=CLEAN · 0 COMPRAR                                                                         |
| EXIT_REQUIRED | data-pov-state=EXIT_REQUIRED · Salir                                                                 |
| CLOSED        | remainingQuantity=0 · operatingState=CLOSED · sin star-card abierta · Journal decisionId · 0 COMPRAR |

Un solo test `GP-V179-01`. Identidad AAPL de punta a punta. V1.73–V1.78 intactos.

## Pre-flight (local 2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v179
# → 1 passed

E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178"
# → 28 passed (3 integrated skipped)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

## No declarar

- CI GREEN · LIVE · bump `1.35.0-beta`
- `dryRun=false` browser · scheduler prod · fills ledger
- Enum `EXIT_EXECUTED` (CLOSED + `POSITION_CLOSED` es el terminal de dominio)
