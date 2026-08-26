# ADR-036: Decision Journal 2.0 — vista Tesis (presentación, no SoT)

**Estado:** Accepted (implementación J0–J4)  
**Fecha:** 2026-08-26  
**Contexto:** Tag `v1.13-beta`. El Decision Journal (ADR-029) es un audit trail append-only. La UX de usuario básico necesita una **ficha de tesis** por activo sin duplicar TradePlan/Position ni inventar geometría.

**Depende de:** [ADR-029](./029-order-proposal-decision-journal.md) · [ADR-031](./031-operational-model-tesis-plan-permiso.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).

---

## 1. Decisión

El Decision Journal en `/decision-journal` tiene **tres pestañas**:

| Pestaña               | Qué es                                                                 | SoT                                                                                     |
| --------------------- | ---------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| **Tesis**             | Lista + ficha de la última sesión `propose` por instrumento            | Proyección de `decision_sessions` + `DecisionPackage` + `TradePlan` + Position/ExitPlan |
| **Evolución**         | Serie read-only de snapshots `propose` por instrumento + diff N vs N-1 | Misma proyección que Tesis, **time series** (sin nueva tabla)                           |
| **Historial técnico** | Timeline ADR-029                                                       | `decision_journal_entries` append-only                                                  |

`DecisionJournalStudyViewV1` es un **ViewModel**. No hay tabla Alembic nueva. No se copian SL/TP/tesis al journal.

```text
DecisionPackage + TradePlan + Position/ExitPlan + DecisionSession
        ↓  mapper puro (shared + application)
DecisionJournalStudyViewV1
        ↓
UI Tesis / Ficha de decisión
```

## 2. Honestidad de geometría

- `WATCH` / `BLOCKED` / `EXPIRED` / `whyNot: no_stop` / sin plan → STOP = — · TP = — · copy: _No existe todavía un plan operativo._
- `TradePlan.entry` es un precio único; **no** hay rango de entrada.
- Indicadores del motor: RSI, ADX/DI, SMA, ATR. **No** SuperTrend ni MACD salvo que existan en el snapshot.
- Consenso visual = recuento de `assessments[].bias`, etiquetado «N evaluaciones», no «N indicadores».
- `userThesis` queda `null` (no hay notas de usuario en el spine). El dictamen diario (ADR-022) **no** es «mi tesis».

## 3. Mapper de estado (usuario ← interno)

Precedencia documentada en `mapJournalStudyStatus` (`decision-journal-study.ts`). El enum de UI **no se persiste**.

## 4. Consecuencias

- Confirm, SubmitIntent, OperationalIncident y DEX-1…DEX-5 **no se tocan**.
- Journal Writer sigue siendo append-only; Tesis y Evolución son solo lectura.
- Operational Console / UI de incidentes Mesa: fuera de este ADR.

---

## 5. Addendum — Evolución de tesis (E0–E4, 2026-08-26)

**Estado:** Accepted (implementación E0–E4).

La pestaña **Evolución** responde «**por qué cambió**» entre snapshots `propose` consecutivos del mismo instrumento. **No** es una nueva SoT ni sustituye el dictamen diario (ADR-022) ni la «Evolución» de Instruments.

### Contrato

- `DecisionJournalStudyHistoryV1` — `{ instrumentId, studies: DecisionJournalStudyViewV1[], total }`
- `JournalStudyDeltaV1` + `mapJournalStudyDelta(prev, next)` — diff honesto, null-safe, buckets `motor` | `plan` | `health`
- Copy: primera sesión → «Primera tesis registrada»; diff vacío → «Sin cambios materializados en el snapshot»

### API

`GET /api/accounts/{accountId}/decision-studies/{instrumentId}/history?limit&offset` — lista **todas** las sesiones `kind=propose` del instrumento (`created_at` desc), `build_study_view` por cada una.

### Honestidad Evolución

- WATCH / sin plan válido → **no** fabricar diff de SL/TP/entrada
- Motor/plan solo desde payloads de sesión; journal events **no** se mezclan como estudios
- Copy UI: «Evolución de análisis IA» (≠ dictamen diario Instruments)

### Fuera de alcance

Alembic · `userThesis` · causas inventadas · reabrir DEX/Confirm.
