# RELEVO — v2.14.2-beta elevado a `main` (cierre A1: account-isolation en LECTURA/estudio) — 2026-09-08

> **Padre:** [engineering-index #98](./engineering-index-2026-08-03.md) · informe A1 [`audit-interno-lectura-v2-14-2026-09-08.md`](./audit-interno-lectura-v2-14-2026-09-08.md) (hallazgo A1) · base de hechos de esta faena.
> **Estado:** **CERRADO.** V2.14.2 elevado a `main` con **bump de package `1.43.2-beta`**.

## 1. Elevación V2.14.2 (auditable desde GitHub)

| Pieza               | Valor                                                                                       |
| ------------------- | ------------------------------------------------------------------------------------------- |
| Base                | `main` en V2.14.1 bump (`1.43.1-beta`)                                                      |
| Código hotfix faena | cierre A1 residual (rutas de LECTURA/estudio gateadas) — offline ruff 0 · pytest collect OK |
| Bump                | `1.43.1-beta` → **`1.43.2-beta`** (este commit)                                             |
| Tag                 | `v2.14.2-beta` (código de la faena)                                                         |
| Alembic head        | `023_ohlcv_bars_unique_reconcile` (sin cambio de esquema en esta faena)                     |

## 2. Qué incluye V2.14.2 (el cierre A1; detalle en índice #98)

1. **`require_owned_account_if_present`** (`dependencies.py`): una lectura/estudio que declare `account_id` que no pertenece al principal → **404**; `account_id` ausente (demo/global) se deja pasar para la UI.
2. **Rutas gateadas con cuenta visible**: `ai_governance` (effectiveness / decision-memory / decision-sessions / learning-summary / session `{id}` + replay / outcome / trials / edge-reports / recommendations propose) · `instrument_daily_opinions` (query / auto-telemetry / auto-propose / eod-batch) · `paper-desk/daily-report` · `risk/ops-self-eval`.
3. Tests de aislamiento por cuenta añadidos en `apps/api-python/tests/test_account_isolation.py` (cuenta ajena → 404). En el informe A1 el hallazgo pasa de **[cerrado parcial]** a **[cerrado]**.

## 3. Estado / riesgos abiertos (no bloquean la elevación)

- **Condición multi-owner cross-account** sigue `[runtime-aislamiento]`: hoy single-owner bootstrap (único principal real), no demonstrable con 2.º owner real; el cierre es **estructural** (gate en las vías), no certificado por runtime multi-owner.
- **Deuda P2.6**: fidelidad optionality/value de los DTOs (fuera del alcance A1/G12/G13).
- Tests preexistentes que asumen head `004` (`test_f3b_alembic_data_epoch.py`, `test_ledger_entries_reference_unique.py`) — reconciliar aparte.

FIN DEL RELEVO — V2.14.2 (cierre A1 account-isolation LECTURA/estudio) elevado a `main`, auditable desde GitHub.
