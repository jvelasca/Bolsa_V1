# Thaw P1–P5 measurement — live DEMO DB · 2026-08-25

> **AsOf:** 2026-08-25T11:21Z · API `127.0.0.1:8000` · Postgres `bolsa_v1` (docker `bolsa-postgres`).  
> **Padres:** [checklist](./camino-d-auto-thaw-checklist-2026-08-04.md) · [ADR-023](../adr/023-camino-d-thaw.md) · [audit E1.5](./thaw-readiness-audit-2026-08-25.md).  
> **Regla:** medir ≠ thaw. `PAPER_D_EXECUTE` **off**. ADR-023 sigue **Proposed**.

---

## Verdict

**P1–P5 FAIL.** Thaw sigue **NOT READY**.

| #   | Umbral                          | Medido                                                                        | Pass?       |
| --- | ------------------------------- | ----------------------------------------------------------------------------- | ----------- |
| P1  | ≥60 días con dictámenes         | **28** distinct `as_of_bar_date` (histórico completo)                         | ❌          |
| P2  | ≥50 SEMI Confirm fills DEMO     | **0** `confirm` sessions · **0** journal entries · **0** buys en seed         | ❌          |
| P3  | Precisión BUY ≥70%              | `buyPrecision5d` = **null** (`matureBuySample=0`, `alarmaBuyCount=0`)         | ❌          |
| P4  | Recall ≥55%                     | `buyRecall5d` = **0.0** (`recallCaught=0` / `recallMoveSample=4650`)          | ❌          |
| P5  | MaxDD DEMO ≤ min(10%, 1.2× Lab) | Cash proxy seed **0.2%** (solo deposit+fee; **0 trades**) · Lab MaxDD **n/d** | ⚠ no válido |

---

## Evidence detail

### A0 telemetry (`GET /api/instrument-daily-opinions/telemetry?lookbackDays=120`)

```json
{
  "asOf": "2026-08-25",
  "lookbackDays": 120,
  "daysWithOpinions": 28,
  "opinionRows": 2504,
  "alarmaCount": 0,
  "alarmaBuyCount": 0,
  "matureBuySample": 0,
  "buyPrecision5d": null,
  "buyRecall5d": 0.0,
  "recallMoveSample": 4650,
  "recallCaught": 0,
  "criteriaVersion": "1.1.0"
}
```

Health risk block (same moment): `paperDExecuteEnv: false`, kill switch off.

### P1 — días con dictámenes

```sql
SELECT COUNT(DISTINCT as_of_bar_date), MIN(as_of_bar_date), MAX(as_of_bar_date), COUNT(*)
FROM instrument_daily_opinions;
-- 28 | 2026-07-22 | 2026-08-25 | 2504
```

Stances presentes: `hold_watch` 1690 · `review_strategy` 624 · `no_trade` 190 · **`buy` = 0**.

Gap: faltan ≥**32** días laborables con opiniones (y, para P3, alarmas `stance=buy`).

### P2 — SEMI Confirm fills

| Fuente                                             |              Count |
| -------------------------------------------------- | -----------------: |
| `decision_sessions` kind=`confirm`                 |                  0 |
| `decision_sessions` kind=`propose`                 | 16 (status `open`) |
| `decision_journal_entries`                         |                  0 |
| `ledger_entries` type buy · `default-account-seed` |                  0 |
| `transactions` vía cartera seed                    |                  0 |

Ningún fill SEMI Confirm en DEMO seed. Umbral 50 **imposible** con el estado actual.

### P3 / P4 — precisión / recall BUY-alarma

Canal alarma A0 exige `stance=buy` (+ estrellas). En BD **no hay** filas `buy` → muestra madura 0 → precisión nula; recall 0% sobre 4650 moves ≥+2%/5d.

### P5 — MaxDD DEMO

Cuenta: `default-account-seed` («Cuenta demo EUR», simulated).

| Dato                 | Valor                        |
| -------------------- | ---------------------------- |
| Equity actual        | 99800 EUR                    |
| Ledger entries       | 2 (`deposit` + `fee`)        |
| MaxDD cash proxy     | **0.2%** (100000 → 99800)    |
| Lab MaxDD comparable | **no medido** en esta pasada |

0.2% ≤ 10% numéricamente, pero **no es MaxDD de operativa DEMO** (sin buys). Criterio P5 **no se considera ✅**.

---

## Qué falta para reintentar thaw

1. **P1:** acumular dictámenes hasta ≥60 días distintos (seguir corrida Estudio/Asesor).
2. **P2:** ≥50 fills SEMI Confirm reales en cuenta DEMO (no cuentas de test/idempotency).
3. **P3/P4:** generar / registrar alarmas `stance=buy` con madurez ≥5 barras; re-correr A0 hasta precisión ≥70% y recall ≥55%.
4. **P5:** equity curve con trades DEMO + MaxDD Lab de referencia; adjuntar ambos.
5. Luego: palabra **thaw** de nuevo → Accept ADR-023 + amend freeze + opt-in `PAPER_D_EXECUTE` en DEMO controlada.

---

## Freeze

LAB ≠ TRADING · LLM no ejecuta · `PAPER_D_EXECUTE` **off** · ADR-023 **Proposed** · medición ≠ autorización.
