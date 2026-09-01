# RELEVO — tag v1.55-beta → auditoría / CI (2026-09-01)

> **Padre:** [`traspaso-relevo-v1-55-operational-hardening-2026-09-01.md`](./traspaso-relevo-v1-55-operational-hardening-2026-09-01.md) · [`traspaso-relevo-tag-v1-54-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-54-beta-2026-09-01.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CI failure (shared)** — run [33508291486](https://github.com/jvelasca/Bolsa_V1/actions/runs/33508291486) — tip `v1.55-beta` → `90999dad` — Ruff unblock OK; **pendiente auditoría externa adversarial**.
> **Arranque auditor:** [`arranque-auditor-v1-55-beta-2026-09-01.md`](./arranque-auditor-v1-55-beta-2026-09-01.md).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · scheduler · browser E2E · package bump.

---

## 0. Confirmación

Sobre tip previo `v1.54-beta` → `e057a8cc`:

| Pieza                      | Entrega                                                                                   |
| -------------------------- | ----------------------------------------------------------------------------------------- |
| GP-SESSION-01..04          | Invariantes qty/entry/stops/T1 fill/trail monotonic/CLOSED qty=0/journal chain            |
| GP-SESSION-05..10          | Sesiones adversas: stop loss · T1 parcial · T2 exit · trailing monotónico · crash · recon |
| GP-GOLDEN-DAY-01           | Jornada completa EXPECTED=ACTUAL                                                          |
| PositionOperationalView    | Proyección canónica DTO (`operatingState` · `primaryAction` · `levels` · `stopHistory`)   |
| PaperDailyReport secciones | DECISIONES · OPERATIVA · RESULTADO · NO OPERADAS                                          |
| Mesa 5 cubos               | 🔴 REQUIERE ACCIÓN · 🟠 PROTEGER · 🟢 POSICIONES · 🔵 OPORTUNIDADES · ⚪ NO OPERAR        |
| Consola excepciones        | Solo incidentes · recon · birth_failed · UNKNOWN (no inbox duplicado)                     |
| V1.54 Operating Desk       | intacto (remap cubos Mesa; wire autoDesk/exceptionFacts sin regresión)                    |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta`.

## 1. Release

| Pieza      | Valor                                                                                                              |
| ---------- | ------------------------------------------------------------------------------------------------------------------ |
| Tag tip    | `v1.55-beta` → `90999dad`                                                                                          |
| Previo tip | `v1.54-beta` → `e057a8cc` (CI GREEN)                                                                               |
| CI tag     | **failure** — [Release tag CI](https://github.com/jvelasca/Bolsa_V1/actions/runs/33508291486) · `headSha=90999dad` |

Jobs del push `v1.55-beta` (2026-09-01), snapshot parcial:

| Job            | Resultado                                             |
| -------------- | ----------------------------------------------------- |
| python         | success (Ruff unblock: retag `90999dad`)              |
| shared         | **failure** (`operational-honesty-scenarios` test 15) |
| frontend       | success                                               |
| decision-spine | success                                               |
| security       | success                                               |
| certify        | **failure** (aggregate)                               |

## 2. Pre-flight

Ver [`plan-v155-operational-hardening-2026-09-01.md`](./plan-v155-operational-hardening-2026-09-01.md). Local post close-out: pytest **25** · shared vitest **34** · web vitest **29** · ruff OK · tsc OK · Release-tag CI **in_progress** (run 33508291486).

## 3. Next

1. **Auditoría adversarial post-V1.55** — [`arranque-auditor-v1-55-beta-2026-09-01.md`](./arranque-auditor-v1-55-beta-2026-09-01.md).
2. **NO LIVE** · scheduler · package bump parked.
