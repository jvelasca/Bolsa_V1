# Spec — V1.83 Lifecycle Snapshot Truth (mock E2E)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA (código + E2E mock locales)** · **stamp CI GREEN remoto PENDIENTE** tag `v1.83-beta`.  
> **Padre:** [`spec-v182-fixtures-split-2026-09-02.md`](./spec-v182-fixtures-split-2026-09-02.md) · respuesta auditor [`respuesta-auditor-v182-operational-financial-truth-2026-09-02.md`](./respuesta-auditor-v182-operational-financial-truth-2026-09-02.md).  
> **Partida tip:** **V1.82** CERRADA — [`v1.82-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.82-beta) → [`d0ccf235`](https://github.com/jvelasca/Bolsa_V1/commit/d0ccf235) · CI GREEN [run 33651647262](https://github.com/jvelasca/Bolsa_V1/actions/runs/33651647262). **No** LIVE.

Certificación **mock E2E** de verdad operativa y financiera: un `LifecycleSnapshot` es la fuente de verdad de portfolio / summary / paper-desk / journal / POV. `EXIT_REQUIRED` y `CLOSED` **conservan lineage**. Sigue siendo **Stateful Projection** (stage → DTO), no motor de eventos.

```text
setStage → LifecycleSnapshot → portfolio === summary === desk
EXIT_REQUIRED / CLOSED conservan T1 (+ T2 o trail) · events monotónicos
R = PnL / initialRisk · marketValue = lastPrice × remaining
```

Regla absoluta: **NINGÚN estado ambiguo → COMPRAR**. DryRun honesto. **No** fills ledger.

```text
P0  GP-V183-01 — Trail OPEN→T1→TRAIL→EXIT→CLOSED: lineage + invariantes + equity única
P0  GP-V183-02 — T2 path T1→T2_EXECUTED→CLOSED: T1+T2 sobreviven
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler prod · sin bump `1.35.0-beta` · sin `dryRun=false` browser · sin fills ledger.  
V1.72–V1.82 intactos. **No** Playwright en `frontend-ci`. **No** integrated E2E obligatorio. **No** rediseño CTA T2.

## 1. Snapshot

| Pieza                  | Contrato                                                                                                       |
| ---------------------- | -------------------------------------------------------------------------------------------------------------- |
| Identidad              | AAPL congelada (`inst-aapl` / `pos-e2e-lifecycle-1` / `tp-e2e-lifecycle-1` / `dec-e2e-lifecycle-1`)            |
| Finanzas               | `avgCost=100` · `stop=95` · `birthQty=10` · `initialRisk=50` · `lastPrice` por stage · `R = PnL / initialRisk` |
| Path trail             | `open → t1_* → trailing → exit_required → closed` (T1 executed + stopHistory)                                  |
| Path T2                | `… → t1_executed → t2_* → closed` (T1+T2 executed)                                                             |
| CLOSED                 | `remaining=0` · `quantity=0` · `marketValue=0` · último event `POSITION_CLOSED` · **no** borrar prefijo        |
| `/portfolio.positions` | **incluye** registro CLOSED (qty 0). Open-only = P2.                                                           |
| Equity                 | `cash=100_000` · `totalEquity = cash + marketValue(remaining)` · mismo número en portfolio, summary y desk     |

`setE2eMockPositionStage` guarda `lineagePath`: `t2_*` → t2; `trailing`/`exit_required` → trail; `closed` hereda. Default trail (GP-V178 aislado).

## 2. IN

| ID         | Pri | Comportamiento                                                                           |
| ---------- | --- | ---------------------------------------------------------------------------------------- |
| GP-V183-01 | P0  | Trail: invariantes in-process + wire CLOSED lineage + equity portfolio===summary===desk. |
| GP-V183-02 | P0  | T2: CLOSED conserva `t1`/`t2` executed + events T1+T2+POSITION_CLOSED.                   |

GP-V179/V181: CLOSED afirma lineage; T2_EXECUTED HUD R recalibrado a fórmula (`0.4` = PnL/initialRisk a lastPrice 110, remaining 2).

### Entregables técnicos

1. `apps/web/e2e/helpers/lifecycle-snapshot.ts` — SoT
2. `applyGoldenPositionStage` proyecta snapshot (no reconstruye vacío EXIT/CLOSED)
3. `e2e-mock-routes.ts` lifecycleDesk lee `buildLifecycleSnapshot`
4. `gp-v183-lifecycle-snapshot-truth-mock.spec.ts`
5. Filtro CI `+gp-v183`
6. Docs: spec · plan · arranque · relevo · CURRENT_SYSTEM · engineering-index §52 · respuesta auditor V1.82

### Invariantes

```
autoDesk.dryRun === true
autoDesk.paperDExecute === false
EXIT_REQUIRED / CLOSED ⇒ t1 executed (lifecycle) ∧ events incluyen T1_EXECUTED
CLOSED ⇒ remaining == 0 ∧ last event POSITION_CLOSED ∧ 0 COMPRAR
portfolio.totalEquity === summary.totalEquity === desk.summary.totalEquity
marketValue === lastPrice × quantity
unrealizedPnl === (lastPrice − avgCost) × quantity
unrealizedR === unrealizedPnl / initialRisk  (0 si remaining=0)
0 ≤ remainingQuantity ≤ birthQty
NO LIVE · no fills · no dryRun=false browser
```

## 3. OUT

- LIVE · scheduler · bump package · `dryRun=false` browser · fills ledger
- POST/engine event-driven E2E (P2 / V1.84+)
- Integrated E2E obligatorio
- `/portfolio` open-only · endpoint `/portfolio/history`
- Playwright en `frontend-ci.yml`
- Rediseño CTA mesa T2
- Reescribir GP-V178 como journey stateful

## 4. Pre-flight (2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179|gp-v181|gp-v183"
# → 35 passed (3 integrated skipped)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

Stamp remoto: tag `v1.83-beta` tras GREEN (mismo ritual V1.80–V1.82).
