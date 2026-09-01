# RELEVO — V1.54 Operating Desk (2026-09-01)

> **Padre:** [`spec-v154-operating-desk-2026-09-01.md`](./spec-v154-operating-desk-2026-09-01.md) · tip certificado previo **`v1.52-beta` → `1da5eb3f`** · V1.53 tip **pendiente**.  
> **Estado:** **DOCS** — sin tag. Package `1.35.0-beta` congelado. **No** LIVE.

---

## 0. Qué abre

| Pieza                                         | Estado  |
| --------------------------------------------- | ------- |
| GP-DESK-UI-01..03 autoDesk → EntryOpportunity | TODO    |
| GP-DESK-UI-04..06 excepciones cubo 🔴         | TODO    |
| GP-DESK-UI-07..09 web wire + vitest           | TODO    |
| V1.53 Golden Session (pytest)                 | intacto |
| V1.41 Daily Desk cuatro cubos                 | intacto |

```text
DailyOpsReport.autoDesk
  → buildDailyDeskInbox (+ overlay)
  → mesa-hoy-page → daily-desk-inbox
       🟢 EntryOpportunity thin
       🔴 birth_failed · recon drift|unavailable · UNKNOWN
```

## 1. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · sin backend motor · package `1.35.0-beta` · sin E2E.

## 2. OUT / parked

- Redesign Daily Desk · scheduler · LIVE · package bump · rankingEngineId · browser E2E

## 3. Next

1. Pre-flight bloque V1.53 + regresión V1.48/V1.52.
2. **P1** shared compositor `autoDesk` → inbox rows.
3. **P2** excepciones 🔴 + GP-DESK-UI-01..06.
4. **P3** web `mesa-hoy-page` + `daily-desk-inbox` — **NO LIVE**.
