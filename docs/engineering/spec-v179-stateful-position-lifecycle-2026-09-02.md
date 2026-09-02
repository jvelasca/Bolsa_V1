# Spec — V1.79 Stateful Position Lifecycle Certification (mock)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + E2E mock locales; **sin stamp CI GREEN**).  
> **Padre:** [`spec-v178-session-golden-mercado-exit-2026-09-02.md`](./spec-v178-session-golden-mercado-exit-2026-09-02.md) · relevo [`traspaso-relevo-v1-78-session-golden-mercado-exit-2026-09-02.md`](./traspaso-relevo-v1-78-session-golden-mercado-exit-2026-09-02.md).  
> **Partida tip:** **V1.78** Session Golden MERCADO→EXIT [`e1dcfba8`](https://github.com/jvelasca/Bolsa_V1/commit/e1dcfba8) (docs stamp `22871141`). **No** LIVE.

Certificación **stateful mock E2E**: un único test muta el mock en caliente sobre **la misma identidad AAPL**. No es el golden pytest Paper Desk (V1.53/V1.55) ni un reloj de sesión de producción. Cierra la brecha de V1.78: fixtures independientes ≠ lifecycle.

```text
CANDIDATO → ENTRY dryRun → STALE → RECOVERY
→ POSITION OPEN → T1_READY → T1_EXECUTED → TRAILING
→ RECON DRIFT → RECON CLEAN → EXIT_REQUIRED → CLOSED
```

Regla absoluta: **NINGÚN estado ambiguo → COMPRAR**.  
Tras OPEN, IDs congelados: `instrumentId` · `positionId` · `tradePlanId` · `decisionId`.  
`Paper execution` = wire **honesto dryRun** (`dryRun=true` · `paperDExecute=false`) — **no** fills ledger · **no** `dryRun=false` browser.

**EXIT_EXECUTED no es un `operatingState` nuevo.** El dominio ya tiene `EXIT_REQUIRED` y terminal `CLOSED` + evento `POSITION_CLOSED`. Se certifica la **representación de cierre**, no la ejecución.

```text
P0  GP-V179-01 — Un test stateful AAPL: candidato→ENTRY→STALE→recovery→OPEN→T1_READY→T1_EXECUTED→TRAILING→recon→EXIT_REQUIRED→CLOSED
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler prod · sin bump `1.35.0-beta` · sin `dryRun=false` browser · sin stamp CI GREEN obligatorio.  
V1.72–V1.78 intactos (WHY · multi-instrument · Paper Day · stale/UNKNOWN · session reliability · golden fixtures independientes).

## 1. Identidad única

V1.79 usa **AAPL** (`inst-aapl`) de punta a punta. Envelopes Hoy V1.74/V1.75 (MSFT) **no se tocan**.

| Tramo                     | Verdad                                                                                             |
| ------------------------- | -------------------------------------------------------------------------------------------------- |
| CANDIDATO / ENTRY / STALE | Hoy + Mercado **sin** `positionId` · study `dec-e2e-lifecycle-1`                                   |
| OPEN … EXIT_REQUIRED      | Nace `pos-e2e-lifecycle-1` / `tp-e2e-lifecycle-1` / mismo `decisionId`                             |
| CLOSED                    | `remainingQuantity = 0` · `operatingState = CLOSED` · portfolio actualizado · Journal misma cadena |

## 2. Semántica por transición

| Transición    | Contrato visible (mínimo)                                                                                                             |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| CANDIDATO     | Mercado entry surface · sin `data-position-id` · 0 COMPRAR                                                                            |
| ENTRY dryRun  | Hoy AUTO armado · ejecución off · `dryRun=true` · `paperDExecute=false` · 0 COMPRAR                                                   |
| STALE         | deny `BLOCKED` + `ENTRY_STALE_DATA` · 0 COMPRAR                                                                                       |
| RECOVERY      | deny **ausente** · 0 nodos `ENTRY_STALE_DATA` · 0 `BLOCKED` de ese ítem · oportunidades ≥ 1 · 0 COMPRAR                               |
| POSITION OPEN | cockpit `posicion` · IDs congelados · stop/T1/T2 · 0 COMPRAR                                                                          |
| T1_READY      | `data-pov-state=T1_READY` · Reducir · remaining 10                                                                                    |
| T1_EXECUTED   | `data-pov-state=T1_EXECUTED` · remaining 5 · qty nacimiento 10 · evento `T1_EXECUTED` (fillId fixture, no ledger)                     |
| TRAILING      | `data-pov-state=TRAILING` · Proteger · stopHistory trail · remaining 5                                                                |
| RECON DRIFT   | `data-recon=CRITICAL` · Revisar · 0 COMPRAR · IDs intactos                                                                            |
| RECON CLEAN   | `data-recon=CLEAN` · primaryAction coherente · 0 COMPRAR                                                                              |
| EXIT_REQUIRED | `data-pov-state=EXIT_REQUIRED` · Salir · IDs intactos                                                                                 |
| CLOSED        | wire `remainingQuantity=0` · `operatingState=CLOSED` · cockpit **sin** star-card abierta · Journal `decisionId` congelado · 0 COMPRAR |

## 3. IN

| ID         | Pri | Comportamiento                                                                                                                                                                                     |
| ---------- | --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GP-V179-01 | P0  | Un test: muta flags en caliente (`setFlag` → re-seed → `reload`). Identidad AAPL. Capas `assertIdentityTruth` + `assertOperationalTruth` + `assertFinancialTruth` + `assertPositionCertification`. |

### Invariantes

```
autoDesk.dryRun === true
autoDesk.paperDExecute === false
mismo instrumentId AAPL en todo el recorrido
tras OPEN: positionId/tradePlanId/decisionId congelados
ENTRY_STALE_DATA ⇒ BLOCKED ∧ recovery ⇒ deny ausente
CLOSED ⇒ remainingQuantity == 0 ∧ no COMPRAR ∧ no star-card abierta
V1.73–V1.78 mock siguen verdes
```

## 4. Entregables

1. Split `apps/web/e2e/integration.ts` → `e2e/helpers/*` + barrel
2. Stages `candidate` \| `open` \| `t1_ready` \| `t1_executed` \| `trailing` \| `exit_required` \| `closed`
3. Overlay Hoy lifecycle AAPL (`deskMode` lifecycle / lifecycle_stale)
4. `apps/web/e2e/gp-v179-stateful-position-lifecycle-mock.spec.ts` (GP-V179-01)
5. Docs cierre: auditor · relevo · CURRENT_SYSTEM · engineering-index

## 5. OUT

- LIVE · scheduler · bump · `dryRun=false` browser · fills ledger
- Enum `EXIT_EXECUTED` · T2_READY obligatorio · rewrite motor
- Stamp CI GREEN remoto
- Cambiar semántica de `hasOpenPositionQuantity`

## 6. Pre-flight (local 2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v179
# → 1 passed

E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178"
# → 28 passed (3 integrated skipped)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```
