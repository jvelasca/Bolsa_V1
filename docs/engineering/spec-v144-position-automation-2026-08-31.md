# Spec — V1.44 Position Automation Contract

> **AsOf:** 2026-08-31 · **Estado:** **CONTRATO + CÓDIGO de foundation** (tipos / fábricas / Golden Paths). **No** AUTO execute de posiciones.
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) · [ADR-032](../adr/032-operational-core-tradeplan-positionstate-execution.md) · [ADR-042](../adr/042-operating-excellence.md) · [ADR-043](../adr/043-position-automation.md).
> **Tip certificado previo:** `v1.43-beta` → `5dfac890` (TRAIL SEMI PASS).
> **Plan de código:** [`plan-v144-position-automation-foundation-2026-08-31.md`](./plan-v144-position-automation-foundation-2026-08-31.md).

Este fichero es **una** especificación. No hay hojas rivales de «AUTO 2» vs «Position Engine». El ADR acepta el contrato; V1.44 materializa autorización de policy + JIT **sin** cablear ExecutionRouter de posición.

```text
DOMAIN (intocado)
  → ExitPlan (evento) + OperatingPolicy (qué haríamos)
  → PositionPolicyDecision (autorización)
  → ExitPermission JIT (¿ahora?)
  → [V1.45] ExecutionRouter PAPER
  → PositionRevision + TradeStory
```

---

## 0. Propósito

Cerrar el hueco simétrico a Confirm SEMI:

```text
SEMI:  Event → ExitPlan → Proposal → Human Confirm → PositionRevision
AUTO:  Event → ExitPlan → PositionPolicyDecision → ExitPermission JIT
         → Execution → Fill → PositionRevision
```

V1.44 implementa hasta `PositionPolicyDecision` + permiso JIT. **No** enciende AUTO. **No** auto-promote. Trail calculado **no** tiene autoridad.

### 0.1 Freeze (heredado, intacto)

Confirm = firma · Spine · Router money path · `PAPER_D_EXECUTE` off · AUTO execute off · Ranking ≠ BUY · LLM ≠ execution · `protect_hint` thin ≠ autoridad · sin drag · sin motores nuevos · sin Alembic · sin bump `package.json` · Mercado = terminal · Hoy = atención.

### 0.2 Qué no es este documento

- No es AUTO de gestión de posiciones en PAPER (eso es V1.45).
- No crea tablas, endpoints, pantallas ni `PositionEngine2`.
- No thaw, Lab P2, OCO, OpportunityScore, nav L1, broker trailing.

### 0.3 Germen en código (no reinventar)

| Pieza viva                                         | Rol hoy                             | Hueco V1.44                                                 |
| -------------------------------------------------- | ----------------------------------- | ----------------------------------------------------------- |
| `ExitReasonV1` / `buildExitPlanFromPosition`       | Detección de evento + sugerencia    | Falta nombre canónico `PositionEvent`                       |
| `ExitPolicyV1` / `OperatingPolicyV1`               | Fracciones T1/T2 / trail por perfil | Falta `PositionPolicyDecision` como autorización            |
| `checkExitPermission`                              | ALLOW/DENY pre-firma                | Falta JIT (stale / session / drift) en AUTO                 |
| `PositionRevision` `origin=trail\|protect\|reduce` | Historia de stop/status             | ≠ ExecutionRecord ≠ Journal — mantener                      |
| `TradeStory` / `ExecutionState`                    | Timeline / UNKNOWN never retry      | GP-AUTO-01 los compone; no los sustituye                    |
| `check_opening` JIT en Router (entrada)            | Autoriza apertura _ahora_           | Misma filosofía en salida: JIT obligatorio para AUTO futuro |
| OR-4 `reconciliationOpeningVetoReason`             | Drift bloquea **entradas**          | Protective exit ALLOWED — test de contrato AUTO             |
| T1+T2 mismo tick (`TARGET_2` borra `TARGET_1`)     | Ya en `exit-plan.ts`                | Elevar a contrato inequívoco                                |

---

## A. Operating Model

### A.1 Autoridades vs proyecciones

| Pregunta                 | Autoridad                                                    | Proyección                  |
| ------------------------ | ------------------------------------------------------------ | --------------------------- |
| ¿Qué evento hay?         | `ExitPlan.primaryReason` (`ExitReasonV1`)                    | `PositionEvent`             |
| ¿Qué haría la política?  | `OperatingPolicy` + `decidePositionPolicy`                   | `PositionPolicyDecision`    |
| ¿Podemos mutar _ahora_?  | `checkExitPermission` (JIT)                                  | eco en POT / nextAction     |
| ¿El humano firmó (SEMI)? | Confirm                                                      | fase propuesta / confirmada |
| ¿AUTO ejecutó (futuro)?  | ExecutionRouter + fill                                       | `ExecutionState`            |
| ¿Cuál es el stop real?   | `currentStop` tras Confirm o (futuro) Policy+Permission+fill | trailing applied vs hint    |
| ¿Qué cambió?             | `PositionRevision`                                           | TradeStory                  |

**Prohibido:** PositionEngine2, TrailingEngine, AutoExitEngine, tabla nueva de revisiones.

### A.2 PositionEvent

Vista tipada de `ExitReasonV1`. No sustituye ExitPlan.

| Evento         | `ExitReasonV1`        | Notas                      |
| -------------- | --------------------- | -------------------------- |
| STOP           | `STRUCTURAL_STOP`     | Riesgo inmediato           |
| T1             | `TARGET_1`            |                            |
| T2             | `TARGET_2`            | Gana a T1 en el mismo tick |
| TRAIL          | `TRAIL`               | Hint ≠ `currentStop`       |
| INVALIDATION   | `THESIS_INVALIDATION` |                            |
| TIME           | `TIME_STOP`           |                            |
| PORTFOLIO_RISK | `PORTFOLIO_RISK`      |                            |
| MANUAL         | `MANUAL`              |                            |

`revisionOriginFromExitReason`: solo `TRAIL` → `origin=trail`. Resto de protect enqueue → `protect`. Un solo sitio; no strings de UI (`TRAILING`, `TRAIL_STOP`).

### A.3 PositionPolicyDecision

Autorización de policy. **No** es orden. **No** es permiso. **No** persiste en tabla.

```text
verdict: HOLD | PROTECT | TRAIL | REDUCE | EXIT
reasonCode: ExitReasonV1 | null
quantity, newStop, target
riskImpact: none | reduce | protect | exit
policyId: OperatingPolicy.templateId
asOf
authorization: human_confirm | policy
deferReason: queue_next_session | data_stale | null
```

V1.44 `decidePositionPolicy` emite `authorization: "policy"`. SEMI sigue siendo humano (`human_confirm` al firmar). El objeto no sustituye Confirm.

Perfiles (ya en `ExitPolicyV1`):

| Perfil           | T1         | T2           | Trail  |
| ---------------- | ---------- | ------------ | ------ |
| conservative     | reduce 50% | cierra resto | tight  |
| moderate         | reduce 30% | reduce 30%   | medium |
| aggressive_swing | hold (0%)  | reduce 30%   | wide   |

Reglas:

- Clamp: `clampStopNotWorsen` — una mejora avanza; degradar exige override.
- Mercado `session !== open` + evento de **target** (T1/T2/TIME) → `HOLD` + `queue_next_session`. STOP estructural no se convierte en hold.
- `stale` y **sin** riesgo inmediato → `HOLD` + `data_stale`.
- `stale` **y** STOP / invalidation / portfolio risk → `EXIT`/`PROTECT` (política protectora).
- T2 reached **no** ejecuta T1 reduce + T2 reduce. `TARGET_2` borra `TARGET_1` en `collectReasons`.

### A.4 ExitPermission JIT

`check_opening` evalúa el libro _ahora_. La salida AUTO debe hacer lo mismo.

Nuevos reasons: `data_stale` · `market_closed` · `portfolio_drift`.

Señales: `dataStale` · `marketClosed` · `portfolioDrift` · `immediateRisk` · `requireJitContext`.

- Solo aplican si `autoExecute === true`. SEMI humano protectivo sigue H2 (kill switch no niega desriesgo humano).
- `requireJitContext`: dato ausente → DENY fail-closed (salvo acción protectora: STOP / invalidation / portfolio risk / `immediateRisk`).
- Stale + T1/T2/TRAIL sin riesgo inmediato → DENY `data_stale`.
- Mercado cerrado + T1/T2 → DENY `market_closed`. Protective STOP → ALLOW.
- `portfolioDrift` + no protective → DENY (OR-4: nuevas entradas bloqueadas; protective exit permitido). Compat: sin `requireJitContext`, señales omitidas = gate off (tests legado).

### A.5 PositionRevision

Historial de cambios de posición. Append-only en `PositionState.revisions`.

**No** es ExecutionRecord. **No** es Journal. **No** tabla nueva en V1.44.

Trail: hint → Confirm (SEMI) o Policy+Permission (AUTO futuro) → `origin=trail` → `currentStop`. El cálculo del trailing **no** escribe el stop.

### A.6 Just-In-Time Authorization (obligatorio en AUTO futuro)

Antes de ejecutar, re-evaluar — no el snapshot del TradePlan:

- portfolio risk · cash · sector · correlación · régimen · frescura de dato

V1.44 fija el contrato y el fail-closed de frescura/sesión/drift. El cableado completo al Risk Engine de cesta es V1.45.

### A.7 UI (sin cambios de este slice)

Reutilizar el lenguaje visual existente: Mantener / Revisar / Proteger / Salir / Vigilar.

Internamente: TRAIL proposed / armed / applied. Visualmente: **Proteger** + «Stop sugerido: …». No seis estados Trail \*.

Mercado = terminal. Hoy = qué necesita atención.

---

## B. Golden Paths de contrato (V1.44)

Walk de **objetos**. No E2E app. No `ExecutionRouter`. No submit.

### GP-AUTO-01 (moderate)

```text
Position (post-fill)
  → T1 PositionEvent → Policy REDUCE 30% → Permission ALLOW
  → PositionRevision origin=reduce
  → TRAIL → Policy TRAIL newStop (clamp) → Permission ALLOW
  → PositionRevision origin=trail
  → T2 → Policy REDUCE 30% (moderate)
  → close remainder → CLOSED → TradeStory
```

E2E PAPER (Estudio → AUTO ENTRY → … → Daily Journal) = **DoD V1.45**.

### Casos malos

| ID             | Hecho                  | Contrato                                                                       |
| -------------- | ---------------------- | ------------------------------------------------------------------------------ |
| GP-BAD-CRASH   | submit → crash         | `ExecutionState.unknown` · nunca reenviar · mismos ids                         |
| GP-BAD-PARTIAL | 100 → 40 filled        | una posición qty 40 · remaining order 60 · no 2ª posición                      |
| GP-BAD-T1T2    | T1 y T2 mismo tick     | `primaryReason=TARGET_2` · un solo reduce/exit                                 |
| GP-BAD-CLOSED  | T1 + mercado cerrado   | Policy `HOLD` + `queue_next_session` · Permission DENY `market_closed` si AUTO |
| GP-BAD-STALE   | lastPrice viejo + AUTO | no execute; STOP tocado → protective ALLOW                                     |
| GP-BAD-RECON   | broker 100 / ledger 70 | opening veto OR-4 · protective exit ALLOW                                      |

---

## C. Roadmap (no este slice)

| Versión | Qué                                                                                              |
| ------- | ------------------------------------------------------------------------------------------------ |
| V1.45   | PAPER AUTO position: Policy → Permission → ExecutionRouter → fill. GP-AUTO-01 E2E PAPER. NO LIVE |
| V1.46   | Autonomous Paper Desk (semanas) + Daily Report                                                   |
| V1.47   | Auditoría estadística (entry/exit/stop/T1/trail quality)                                         |
| V1.48+  | OpportunityScore · ranking portfolio-aware · ML — solo con datos reales                          |

---

## D. OUT — Lab P2 (parked)

Propuesta de auditoría externa: `backtest_risk_policy_from_trading_policy()` hoy cae a Moderado + `stop_loss_pct=5` en silencio. Derivar `BacktestRiskPolicy` de `OperatingPolicy` (mismo `max_risk_per_trade_pct` / stop real) y mostrar el perfil en el Lab.

**No** se implementa en V1.44. **No** se resuelven P2-1…P2-4 (template_id obligatorio vs fallback; re-etiqueta histórica; ATR bar a bar; EdgeReport gate). Independiente del money path. Siguiente ciclo Lab, no condición de Position Automation.

---

## E. Criterios de cierre V1.44

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run src/cognitive/position-automation-golden-path.test.ts src/cognitive/position-policy-decision.test.ts src/position-revision.test.ts src/exit-permission.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/operations/propose-position-exit.test.ts
pnpm --filter @bolsa/web exec tsc --noEmit
pytest packages/py/analytics/tests/test_position_policy_decision.py packages/py/analytics/tests/test_exit_permission.py -q
```

Diff money path (`execution_router.py`, Confirm, `check_opening`) vacío. Sin submits nuevos.
