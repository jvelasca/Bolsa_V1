# RELEVO — v2.14.1-beta elevado a `main` (hotfixes de propositura V2.14) — 2026-09-08

> **Padre:** [índice #96–97](./engineering-index-2026-08-03.md) · cierre auditoría V2.14 + hotfixes [`traspaso-relevo-cierre-auditoria-v214-hotfixes-2026-09-08.md`](./traspaso-relevo-cierre-auditoria-v214-hotfixes-2026-09-08.md) (base de hechos de esta faena).
> **Estado:** **CERRADO.** V2.14.1 (hotfix elevation) elevado a `main` con **bump de package `1.43.1-beta`** (hotfixes de hoy **localmente commiteados** pasan a auditable desde GitHub).
> **Tip código (código de los hotfixes)**: [`da181b76`](https://github.com/jvelasca/Bolsa_V1/commit/da181b76) == cierre auditoría/hotfixes. Commit de elevación/bump encima en `main`.

## 1. Elevación V2.14.1 (auditable desde GitHub)

| Pieza                   | Valor                                                                                                                                                                 |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Base                    | `main` en `e76a1942` (V2.14 elevation, `1.43.0-beta`)                                                                                                                 |
| Hotfixes (ya en `main`) | `dbc0ad1f` provenance+contract G12/G13 · `cd9e3524` A1 account-isolation rutas EJECUCIÓN · `326c0a8a` reconcile OHLCV → schema `023`                                  |
| Código tip              | `da181b76` (docs cierre auditoría + hotfixes)                                                                                                                         |
| Commit elevación        | bump + docs de esta tag (este commit)                                                                                                                                 |
| Bump                    | `1.43.0-beta` → **`1.43.1-beta`**                                                                                                                                     |
| Tag                     | [`v2.14.1-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.14.1-beta) → `da181b76` (código de los hotfixes, igual que `v2.14-beta` → código pre-elevación) |
| Previo                  | V2.14 [`e76a1942`](https://github.com/jvelasca/Bolsa_V1/commit/e76a1942) == tip `1.43.0-beta` == tag previo `v2.14-beta` → `78dd3f9a`                                 |
| Alembic head            | `023_ohlcv_bars_unique_reconcile` (schema-drift reconciliado)                                                                                                         |

## 2. Qué incluye V2.14.1 (los 3 hotfixes de propositura, detalle en el cierre)

1. **Provenance self-reported + contract gate G12/G13** (`dbc0ad1f`): `GET /api/health → provenance` desde fuentes únicas sin DB · `bolsa_api.provenance` · `contract-check.ts` G12 `OperationalIncidentV1` + G13 `SubmitIntentListItemV1` · openapi/schema regenerados.
2. **A1 account-isolation en rutas de EJECUCIÓN** (`cd9e3524`): `require_account_access` en confirm intents / evaluate-exits / execute-auto / paper-desk cycle. Rutas de LECTURA sin gate (deuda residual A1, solo ≥2º owner real).
3. **Reconciliación upsert OHLCV → schema `023_ohlcv_bars_unique_reconcile`** (`326c0a8a`): índice único que faltaba (drift) + histórico repoblado (44.7k barras 1d, 35 activos IBEX, freshness current).

## 3. Estado / riesgos abiertos (no bloquean la elevación)

- Deuda **A1 residual**: rutas de LECTURA/estudio sin `require_account_access` (solo explotable con ≥2º owner real; hoy single-owner bootstrap). Endpoints listados en el informe de lectura A1.
- **Deuda P2.6**: fidelidad optionality/value de los DTOs (a propósito no cubiertas por G12/G13).
- Tests preexistentes que asumen head `004` (`test_f3b_alembic_data_epoch.py`, `test_ledger_entries_reference_unique.py`) — fuera de la transición 022→023, reconciliar aparte.
- Redis "degraded" y "worker_arq down" locales: solo relevantes si se prueban colas Arq/Redis.

FIN DEL RELEVO — V2.14.1 (hotfixes de propositura V2.14) elevados a `main`, auditable desde GitHub.
