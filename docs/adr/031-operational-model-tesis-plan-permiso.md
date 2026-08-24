# ADR-031: Modelo operativo — tesis ≠ plan ≠ permiso (TradePlan v0)

**Estado:** Aceptado  
**Fecha:** 2026-08-24  
**Contexto:** Hoja de ruta operativa post-`v1.7.0-beta` (auditoría externa + auditoría propia). El Decision Spine (Fase 0) ya es autoridad de **permiso**. Falta el objeto de **plan condicional** (RFC-008 Execution Engine) y comprimir la mañana a 2–5 acciones firmables.

**Depende de:** [RFC-008](../rfc/008-cognitive-decision-architecture.md) · [ADR-019](./019-dual-universes-lab-vs-trading.md) · [ADR-029](./029-order-proposal-decision-journal.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [estudio SEMI](../engineering/estudio-flujo-semi-vs-tops-2026-08-21.md).

---

## 1. Decisión

Tres capas, un solo spine. **No** se crea un segundo motor de decisión.

| Capa        | Objeto                                              | Pregunta                                                              | Autoridad                 |
| ----------- | --------------------------------------------------- | --------------------------------------------------------------------- | ------------------------- |
| **Tesis**   | `DecisionPackage`                                   | ¿Qué creemos y con qué evidencia?                                     | `run_decision_runtime`    |
| **Plan**    | `TradePlan` v0 (extiende la tesis, no la sustituye) | Si ocurre X, ¿qué haríamos? (estado, stop, size, caducidad, `whyNot`) | mapper determinista       |
| **Permiso** | `check_opening`                                     | ¿Podemos llenar ahora?                                                | Risk Engine (SEMI = AUTO) |

```text
QUALITY / OPPORTUNITY     →  score TA + TOP + opinion (calculan; no son BUY)
SETUP                     →  Wyckoff / DÍA D / CORE-R (evidencia; no motor paralelo)
ENTRY READINESS           →  WATCH | ARMED | TRIGGERED | BLOCKED | EXPIRED
TRADEPLAN                 →  DecisionPackage + EntryPlan mínimo + size + expiry + whyNot
PERMISSION                →  check_opening (único veto de fill)
ACTION QUEUE              →  proyección UI (Hoy) sobre Decision Board + cola F3
```

**Ranking ≠ BUY.** Un TOP o un dictamen `buy` es candidato. BUY operativo = `TradePlan.status == TRIGGERED` **y** `check_opening` ALLOW **y** firma humana (SEMI).

**0 operaciones hoy** con gates correctos es una métrica de calidad, no un fallo.

---

## 2. TradePlan v0 (mínimo; no el mockup de 40 campos)

Campos canónicos:

- identidad: `decisionId`, `instrumentId`, dirección
- `status`: `WATCH` \| `ARMED` \| `TRIGGERED` \| `BLOCKED` \| `EXPIRED`
- entry: zona + trigger **o** no listo
- `structuralStop` obligatorio para `TRIGGERED`; no se acerca el stop para caber en el riesgo — se reduce size o se rechaza
- `quantity` = `risk_amount / (entry − stop)` cuando hay stop válido
- `expiresAt` (TTL de sesión; típico barra diaria + 1)
- `whyNot[]`: `fit` / `freshness` / `mandate` / `entry` / `no_stop` / `expired` / `orphan`

**No** en v0: T2, trailing, thesis-health, MFE/MAE, attribution, familias Entry Engine completas, `NO_NEW_LONGS` por régimen (Ciclo 4+).

Jerarquía de perfil (ya cierta en código; solo nombrar):

`InvestorProfile` → `TradingPolicy` → Mandate (DS-03) → `ExecutionPolicy` (SEMI/AUTO) → `PositionPolicy`

LLM **nunca** calcula SL/TP/size ni salta un gate. Como mucho, revisor narrativo (fuera de v0).

---

## 3. Integridad SEMI (Ciclo 1) — decisiones

1. **TTL:** `Recommendation.expiresAt` en el pasado → `rejected_by_gate` / `expired`; no fill.
2. **Precio:** aperturas con OHLCV cableado revalidan último `close` vs `suggestedPrice` (desviación relativa máxima 2 %). Fuera de banda → `stale_price`.
3. **pending_orders:** el fill ya no llama `ExecuteTrade` desde el monitor FE. Pasa por `FillPendingOrder` → `check_opening` (compras / aperturas) → ledger.
4. **Doble confirm concurrente:** la clave de idempotencia sigue siendo `decision_id`; test de carrera verifica un solo fill lógico.
5. **H3 orphan (aperturas):** con `cognitive_store` cableado (producción), una apertura sin `DecisionPackage` de sesión → `orphan_opening_blocked` fail-closed. Exits sin package siguen `unknown_position_side`. Wiring de test sin store conserva el comportamiento legado (mismo patrón que `ohlcv=None`).

---

## 4. Daily Command (Ciclo 3)

**No** es una god-page ni una sexta puerta. Las 5 puertas aprobadas (Trading · Señales · Confirmar · Libro + Lab fuera) se mantienen.

**Hoy** = strip de compresión en la mesa (`TradingLayout`) sobre `GetDecisionBoard` + cola F3. Click → panel Why / Why not + firmar (drawer Confirmar existente).

---

## 5. Golden scenarios (papel; tests v0 cubren A/B/C/H)

| Id    | Nombre                        | Entrada                                                                         | Resultado                                                 |
| ----- | ----------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------- |
| **A** | Breakout perfecto             | Bull, calidad alta, entry ready, stop estructural, Fit OK                       | `TRIGGERED` + size > 0                                    |
| **B** | Gran activo / mala entrada    | Quality alta, `entry_ready=False`                                               | `WATCH` (no BUY)                                          |
| **C** | Gran setup / veto cartera     | Fit concentración/sector                                                        | `BLOCKED`                                                 |
| **D** | Stop demasiado lejos          | Size se reduce; no se mueve el stop (Ciclo 4 si hace falta size-down vs reject) | documentado; v0 size por fórmula, reject si stop inválido |
| **E** | Posición ganadora T1          | Protección / trail                                                              | **Diferido** Ciclo 5                                      |
| **F** | Tesis se degrada, precio > SL | `REVIEW`                                                                        | **Diferido** Ciclo 5                                      |
| **G** | Régimen BULL → BEAR           | `NO_NEW_LONGS`                                                                  | **Diferido** Ciclo 4                                      |
| **H** | Plan caducado                 | `expiresAt` pasado                                                              | `EXPIRED` / confirm no ejecuta                            |

---

## 6. Qué queda diferido (Ciclo 4+)

No abrir sin fase propia:

- Familias Entry Engine (Breakout / Pullback / Wyckoff como contrato `EntrySetup`) y veto de régimen `NO_NEW_LONGS`
- Position Manager, Thesis Health, Exit Radar, trailing, T1 parcial, time-stop, bracket
- MFE/MAE, attribution, expectancy por setup
- Shadow AUTO / `PAPER_D_EXECUTE` / broker live
- Reescritura de `bolsa_application/`, microservicios, LLM en la decisión crítica
- F9-B, purge storage E8

Freeze vigente: LAB ≠ TRADING · LLM no ejecuta · ranking IO puede seguir en cliente hasta Actionability en servidor.

---

## 7. Consecuencias

- Un ADR más no compite con `CURRENT_SYSTEM`: este documento fija **política**; el estado vivo sigue en [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
- Código: tipos en `@bolsa/shared` + mapper puro en `bolsa_analytics.cognitive.trade_plan`; confirm/fill no duplican autoridad de `check_opening`.
