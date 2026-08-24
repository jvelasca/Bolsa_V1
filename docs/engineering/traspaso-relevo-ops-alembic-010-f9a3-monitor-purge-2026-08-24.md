# RELEVO / TRASPASO — Alembic 010 + F9-A3 CI + monitor Purge V2 (2026-08-24)

> **Padre:** [traspaso-relevo-order-proposal-journal-cierre-f1-f3-2026-08-24.md](./traspaso-relevo-order-proposal-journal-cierre-f1-f3-2026-08-24.md) · [plan-r9-f9-analytics-market-2026-08-24.md](./plan-r9-f9-analytics-market-2026-08-24.md) · [monitor-purge-ops-checklist-2026-08-24.md](./monitor-purge-ops-checklist-2026-08-24.md).
> **Propósito:** texto de paso tras las tres tareas inmediatas post F1–F3 / F9-A.
> **AsOf:** 2026-08-24.

---

## 1. Estado verificado (firma)

| Campo             | Valor                                                                         |
| ----------------- | ----------------------------------------------------------------------------- |
| **HEAD**          | `8a1e64d` = `origin/main`                                                     |
| **Tag**           | `v1.7.0-beta` → `e3b943a` (intacto)                                           |
| **Alembic `010`** | **APLICADO** en `bolsa_v1` (ya estaba en head; `upgrade head` no-op)          |
| **F9-A3**         | **HECHO** — step Import-linter en `python-ci.yml` (pendiente commit)          |
| **Purge V2**      | MONITOR T+2 · E8 **N** · **0 purges** · batería **19/19** · verify **EXIT 0** |
| **F9-B**          | **PARKED** — no abrir sin ADR                                                 |

---

## 2. Entregables de este slice

| Tarea                                  | Resultado                                                                                                                                      |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Alembic `010_decision_journal_entries` | `alembic_version=010_decision_journal_entries` · tabla `decision_journal_entries` (9 columnas, JSONB payload) · 3 índices + pkey · **0 filas** |
| F9-A3 CI                               | `.github/workflows/python-ci.yml` step `Import-linter` + path filter del propio workflow                                                       |
| lint-imports local                     | **4 kept, 0 broken** (442 files, 2160 deps) vía `importlinter.cli`                                                                             |
| Monitor Purge §4                       | vitest **19/19**                                                                                                                               |
| `verify_ledger_balance_chain.py`       | **EXIT 0**                                                                                                                                     |

**NO TOUCH respetado:** F9-B · purge storage · motor money · gobernanza IA.

---

## 3. Brief arranque (nuevo chat)

> CONTEXTO: HEAD `8a1e64d` = `origin/main`. Tag `v1.7.0-beta` → `e3b943a`. Ciclo 1 F1–F3 CERRADO. F9-A COMPLETO (A1+A2+A3 CI pendiente commit). Alembic `010` en `bolsa_v1`. Purge V2 MONITOR.
> **LEE PRIMERO:** este doc · backlog §0 · `PROJECT_STATE.md` · `CURRENT_SYSTEM.md`.
> **Siguiente:** aprobación commit F9-A3 CI + update-last docs · T+4 semanas Purge (~2026-09-19).
> **NO tocar:** F9-B sin ADR · purge storage · motor money · gobernanza IA.

---

## 4. Enlaces

- ADR-029 · ADR-030
- Plan OP/J · Plan F9
- Audit-pack 24d · Monitor checklist
- Relevo padre: `traspaso-relevo-order-proposal-journal-cierre-f1-f3-2026-08-24.md`
