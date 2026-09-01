# Spec — V1.55 Operational Hardening

> **AsOf:** 2026-09-01 · **Estado:** **CÓDIGO**.  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v154-operating-desk-2026-09-01.md`](./spec-v154-operating-desk-2026-09-01.md) · tip certificado previo **`v1.54-beta` → `e057a8cc`**. **No** LIVE.

Endurecimiento operativo: Golden Session con invariantes, `PositionOperationalView` como proyección canónica, Daily Report por secciones, Mesa cinco cubos, Consola solo excepciones. **No** motores nuevos · **no** LIVE.

```text
P0  GP-SESSION-01..04 invariantes + GP-SESSION-05..10 + GP-GOLDEN-DAY-01
P1  PositionOperationalView + stopHistory + eventos STOP/T1
P2  PaperDailyReport secciones + Mesa 5 cubos + Consola excepciones + una CTA
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin Alembic · sin bump package (`1.35.0-beta`) · sin scheduler · sin browser E2E · V1.54 intacto salvo remap cubos Mesa.

Regla global: `Ranking ≠ Signal ≠ Proposal ≠ Authorization ≠ Order ≠ Fill`.

## 1. IN — P0 Golden Session

| ID                | Comportamiento                                                                 |
| ----------------- | ------------------------------------------------------------------------------ |
| GP-SESSION-01..04 | Invariantes qty/entry/stops/T1 fill/trail monotonic/CLOSED qty=0/journal chain |
| GP-SESSION-05     | Stop loss Estudio → CLOSED qty=0                                               |
| GP-SESSION-06     | T1 parcial Buy 100 → Sell 30 → remaining 70                                    |
| GP-SESSION-07     | T2 → remaining 0 · target2Leg.executed                                         |
| GP-SESSION-08     | Trailing monotónico · never down                                               |
| GP-SESSION-09     | Crash BUY→FILL→recover → 1 Position                                            |
| GP-SESSION-10     | Recon drift → exceptionFacts → RESOLVED                                        |
| GP-GOLDEN-DAY-01  | Jornada completa EXPECTED=ACTUAL                                               |

## 2. IN — P1 PositionOperationalView

Proyección DTO (no sustituye `PositionState`): `operatingState` ampliado · `primaryAction` · `levels` · `t1`/`t2` · `stopHistory` · `events` (STOP_LEVEL_REACHED / STOP_FILL / POSITION_CLOSED · T1 triggered≠executed).

UI consume proyección; no reinterpreta en React.

## 3. IN — P2 Superficies

| Superficie       | Cambio                                                                             |
| ---------------- | ---------------------------------------------------------------------------------- |
| Mesa             | 🔴 REQUIERE ACCIÓN · 🟠 PROTEGER · 🟢 POSICIONES · 🔵 OPORTUNIDADES · ⚪ NO OPERAR |
| Consola          | Solo excepciones (incidentes · recon · birth_failed · UNKNOWN)                     |
| PaperDailyReport | DECISIONES · OPERATIVA · RESULTADO · NO OPERADAS                                   |
| CTA              | Una acción primaria por posición · AUTO sin COMPRAR                                |

## 4. OUT / parked

LIVE · scheduler · bump package · rankingEngineId · browser E2E · auditoría adversarial post-V1.55 · Alembic tabla nueva.

## 5. Pre-flight

Bloque GP-SESSION + lifecycle + daily report + shared daily-desk + operational-context + ruff + tsc.
