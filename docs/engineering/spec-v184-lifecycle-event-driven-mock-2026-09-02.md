# Spec — V1.84 Lifecycle Event-Driven Mock (E2E)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (código + pre-flight local) · tip stamp remoto pendiente.  
> **Padre:** [`spec-v183-lifecycle-snapshot-truth-2026-09-02.md`](./spec-v183-lifecycle-snapshot-truth-2026-09-02.md) · respuesta auditor [`respuesta-auditor-v183-lifecycle-snapshot-truth-2026-09-02.md`](./respuesta-auditor-v183-lifecycle-snapshot-truth-2026-09-02.md).  
> **Partida tip:** **V1.83** CERRADA · PASS auditor 9,85/10 · [`v1.83-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.83-beta) → [`dc596ee5`](https://github.com/jvelasca/Bolsa_V1/commit/dc596ee5) · CI GREEN [run 33657045026](https://github.com/jvelasca/Bolsa_V1/actions/runs/33657045026). **No** LIVE.

Certificación mock: el lifecycle ya no vive solo como `setStage → DTO`. Un **log append-only** es la fuente de verdad; `POST` (mock) persiste; `GET` portfolio/summary/desk **reduce** el log. Los `events` del DTO = prefijo del log (no regenerados desde un stage vacío).

```text
POST /api/e2e/lifecycle/events → append log → derive stage
GET  /portfolio|/summary|desk ← reduce(log) ≡ Snapshot V1.83
events wire ⊆ log persistido (monotónico)
```

Regla absoluta: **NINGÚN estado ambiguo → COMPRAR**. DryRun honesto. **No** fills ledger. **No** FastAPI real.

```text
P0  GP-V184-01 — Trail: emit OPEN→T1→TRAIL→EXIT→CLOSED vía POST · GET lineage + equity
P0  GP-V184-02 — T2: emit T1→T2→CLOSED · wire events = log · t2 executed
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler · sin bump `1.35.0-beta` · sin `dryRun=false` browser · sin fills ledger.  
V1.73–V1.83 intactos (`setE2eMockPositionStage` sigue para GP-V178..V183). **No** Playwright en `frontend-ci`. **No** integrated E2E obligatorio. **No** motor de producción.

## 1. Contrato

| Pieza             | Contrato                                                                                                            |
| ----------------- | ------------------------------------------------------------------------------------------------------------------- |
| Log               | Append-only en runtime mock · reset en `resetE2eMockRuntimeFlags`                                                   |
| POST mock         | `/api/e2e/lifecycle/events` · body `{ kind, at?, fillId? }` · solo desk lifecycle                                   |
| Kinds             | `POSITION_OPENED` · `T1_TRIGGERED` · `T1_EXECUTED` · `T2_*` · `TRAIL_APPLIED` · `EXIT_REQUIRED` · `POSITION_CLOSED` |
| Reduce            | log → `{ stage, lineagePath }` · snapshot reusa finanzas V1.83                                                      |
| Wire `events`     | Subconjunto del log (`T1_EXECUTED` · `T2_*` · `POSITION_CLOSED`) — **no** template vacío                            |
| Compat            | `setE2eMockPositionStage` **limpia** el log (modo proyección V1.83)                                                 |
| Modo event-driven | `lifecycleEvents.length > 0` → rutas usan reduce(log)                                                               |

## 2. IN

| ID         | Pri | Comportamiento                                                                       |
| ---------- | --- | ------------------------------------------------------------------------------------ |
| GP-V184-01 | P0  | Trail POST emit · GET CLOSED lineage + equity portfolio===summary===desk · 0 COMPRAR |
| GP-V184-02 | P0  | T2 POST emit · CLOSED conserva T1+T2 en wire events = log                            |

### Entregables técnicos

1. `helpers/lifecycle-events.ts` — kinds · reduce · snapshot-from-events
2. Runtime: `lifecycleEvents` · `emitE2eMockLifecycleEvent` · clear en setStage/reset
3. `e2e-mock-routes.ts` — POST events · GET usa log si no vacío
4. `gp-v184-lifecycle-event-driven-mock.spec.ts`
5. Filtro CI `+gp-v184`
6. Docs: spec · plan · CURRENT_SYSTEM · engineering-index §53

### Invariantes

```
POST append-only (no rewrite history)
GET events ⊆ log ∧ orden monotónico
CLOSED ⇒ last wire event POSITION_CLOSED ∧ remaining=0
portfolio.totalEquity === summary.totalEquity === desk.summary.totalEquity
setStage ⇒ log vacío (compat V1.83)
autoDesk.dryRun === true ∧ paperDExecute === false
NO LIVE · no fills · no dryRun=false browser
```

## 3. OUT

- LIVE · scheduler · bump package · `dryRun=false` browser · fills ledger
- FastAPI+PG event store real · integrated E2E obligatorio
- Playwright en `frontend-ci.yml`
- `/portfolio` open-only · CTA T2 redesign
- Reescribir GP-V179/V181/V183 a event-driven (compat por `setStage`)

## 4. Pre-flight (2026-09-02)

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e -- "gp-e2e|gp-v173|gp-v174|gp-v175|gp-v176|gp-v177|gp-v178|gp-v179|gp-v181|gp-v183|gp-v184"
# → 37 passed (3 integrated skipped)

pnpm --filter @bolsa/web exec tsc --noEmit
# → EXIT 0
```

Stamp remoto: pendiente (`v1.84-beta`).
