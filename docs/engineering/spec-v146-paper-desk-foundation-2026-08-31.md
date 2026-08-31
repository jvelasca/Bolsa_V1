# Spec — V1.46 Autonomous Paper Desk Foundation

> **AsOf:** 2026-08-31 · **Estado:** **CÓDIGO** (ciclo de sesión + Daily Report AUTO).  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · tip `v1.45-beta` → `6ca5ec12`.  
> **Plan:** [`plan-v146-paper-desk-foundation-2026-08-31.md`](./plan-v146-paper-desk-foundation-2026-08-31.md).

Un **ciclo PAPER por sesión**, no runner de semanas. **No** LIVE. `PAPER_D_EXECUTE` default **off**.

```text
PaperDeskCycle
  → EntryTick (propose; execute solo PAPER_D + !dryRun)
  → PositionTick (ExecutePositionPolicyAuto por OPEN)
  → PaperDailyReport / autoDesk → DailyOpsReport
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · arm ≠ execute · no LIVE · Lab ≠ SoT · sin OCO · sin Alembic · sin bump package · sin nav L1 · sin DeskRunner multi-día · sin motores nuevos.

## 1. PaperDeskCycle

`dry_run` default **true**. Env off + execute → blocked (`paper_auto_env_blocked`). PositionTick reutiliza V1.45. EntryTick vía puerto (Estudio/Paper-D o stub honesto).

## 2. PaperDailyReport / autoDesk

Sección opcional en DailyOpsReport: propuestas/ejecuciones entrada, mutaciones posición, denies JIT, notes (`dryRun`, env off). Schema no rompe sin `autoDesk`.

## 3. HTTP

- `POST /api/paper-desk/cycle` — dryRun default true
- `GET /api/paper-desk/daily-report` — cycle dry-run + report (salvo execute=true + env). **Superseded V1.47:** GET ya no acepta `execute`; ver [`spec-v147-paper-desk-runtime-truth-2026-09-01.md`](./spec-v147-paper-desk-runtime-truth-2026-09-01.md).

## 4. OUT

Scheduler semanas · browser E2E · LIVE · Lab retrofit · OCO · package bump.
