# Relevo — Cierre auditoría V2.14 + hotfixes de propositura (para agente de 2026-09-08 en adelante)

Entorno: repo en `C:/Users/josea/Documents/Informatica/Typescript/Bolsa_V1`, `main` + worktree local.
Rama base: `main` en `e76a1942` (V2.14 elevation · 1.43.0-beta). Los hotfixes de hoy están commiteados **de forma local** encima (no elevados, no tag, sin bump de package).

> Propósito del documento: dejar el estado que cualquier agente siguiente pueda continuar sin rehacer
> ni pisar nada: commits de hoy, el bug de datos resuelto (schema 023), qué queda preexistente en el
> worktree que NO es de esta sesión, y verificación replicable.

---

## 1. Commits de hoy (2026-09-08) — VERIFICADO, no rehacer

Encima de `e76a1942` V2.14 (elevation). Todos "fix interno V2.14 · sin bump/tag".

- `dbc0ad1f` **Provenance self-reported + contract gate G12/G13**. `GET /api/health → provenance`
  (PRODUCT/PACKAGE/GIT_SHA/DB_SCHEMA/API_CONTRACT desde fuentes únicas, sin DB) ·
  `bolsa_api.provenance`. README/CHANGELOG/CURRENT_SYSTEM alineados a V2.14. `contract-check.ts`
  G12 `OperationalIncidentV1` +G13 `SubmitIntentListItemV1`. openapi.json/schema.d.ts regenerados y
  sincronizados; fix `UnicodeEncodeError` de dump_openapi (Windows cp1252). `.gitignore` `**/logs/*.jsonl`.
- `cd9e3524` **A1 account-isolation en rutas de EJECUCIÓN + informe de lectura**. `require_account_access`
  en `POST /ai/intents/confirm`, `/position-policies/evaluate-exits`, `/position-automation/execute-auto`,
  `/paper-desk/cycle`. Informe `docs/engineering/audit-interno-lectura-v2-14-2026-09-08.md` (con A1/A5 y
  anexo M1/M2/M3 de co-verificación). Residual rutas de LECTURA/estudio sin gate (solo ≥2º owner real).
- `326c0a8a` **Reconciliación upsert OHLCV → schema `023_ohlcv_bars_unique_reconcile`** (ver §2) · guards
  tests real-PG/provenance bumped de 022→023 · adenda en informe + CHANGELOG [Unreleased].

Referencias de diagnóstico de esta tanda: transcript del agente shell de traceback y del agente de
mapeo de guards (2026-09-08).

## 2. POR QUÉ "no se veían activos/géticos" y su remedio (schema-drift real)

Causa raíz (verificada por runtime, no solo lectura): `ohlcv_repository.upsert_bars` usa
`ON CONFLICT (instrument_id,timeframe,timestamp)` (commit cd451fea) pero las migraciones Alembic NO
creaban ese índice único (solo PK id) → cada sync de mercado abortaba (`InvalidColumnReference`), la BD
local quedaba con 0 barras → freshness `empty`, listas vacías y gráficos con "histórico no disponible".

Remedio YA aplicado y commiteado:

1. Migración `packages/py/infrastructure/alembic/versions/023_ohlcv_bars_unique_reconcile.py` (índice
   único `ohlcv_bars_instrument_timeframe_ts_uidx`) + declaración en `OhlcvBarRow.__table_args__`.
2. Head de la BD dev local llevado a `023` (`alembic upgrade head` — pedía go y fue autorizado).
3. Histórico repoblado contra la BD local (sync de los 35 instrumentos IBEX vía `SyncInstrumentDailyBars`,
   con **commit explícito por sesión** — el `upsert` no commitea solo; el endpoint HTTP `POST /sync` sí
   vía `get_db_session.commit()`). Resultado: 44.7k barras `1d` (2021-09-08 → 2026-09-08); cada activo con
   `barCount≈1278`, `freshness=current`, `lastBar=2026-09-08`. UI validada: `/instruments` muestra 35
   filas con precio/Δ% y /instruments/{id} con barras + gráfico TradingView.

**Lección operativa para el agente siguiente**: en un entorno que arranca desde `db-ensure`/alembic puro,
una BD recién creada NO tiene índices que vienen del esquema legacy (Prisma). Al migrar a head 023 esto
queda cerrado; si algún día se añade otra columna que exija constraint nuevo, verificar el índice real en
PG antes de confiar en `ON CONFLICT`.

## 3. PENDIENTE / RIESGOS ABIERTOS (si retomas)

- **No commitear un "nuevo"**: revisar si se quiere **elevar/etiquetar** estos 3 hotfixes (V2.14.x / bump)
  o dejarlos como fix interno. Hoy la disciplina ha sido "sin bump, sin tag". Si el agente quiere llegar a
  GitHub, primero `git push` + observar CI GREEN real (disciplina V2.10.1: no afirmar GREEN sin
  `conclusion=success`).
- Deuda residual A1 (documentada): rutas de LECTURA/estudio de accounts operan sin `require_account_access`
  (solo explotable con ≥2º owner real; hoy single-owner bootstrap). Endpoints listados en el informe A1.
- Deuda residual P2.6 (a propósito no cubierta por G12/G13): fidelidad de optionality/value de los DTOs.
- `test_f3b_alembic_data_epoch.py` y `test_ledger_entries_reference_unique.py` asumen head `004`; ya eran
  no-conformes con el árbol lineal global (preexistentes; **NO los toqué**). Si algún día se ejecutan
  end-to-end contra la BD a 023 romperán; reconciliar ahí aparte (fuera de la transición 022→023).
- Redis "degraded" y "worker_arq down" en el `/health` local: relevantes solo si vas a probar features que
  dependen de colas Arq/Redis. El stack dev (API :8000 + Web :5173 + scheduler + queue poll) está arriba
  y el catálogo/mercados cargan igualmente.

## 4. LÍNEA ROJA PARA NO PISAR

- Preservar en el worktree SIN tocar lo preexistente de esta sesión (NO son míos ni de estos hotfixes):
  los `.md` de `docs/engineering/*` modificados (CRLF/EOF), `apps/web/e2e/*`, `playwright.config.ts`,
  `src/features/trading/lists-tab/*`, `open-instrument-in-trading.ts`, `packages/shared/src/cognitive/
live-order.ts`. No usé `git add -A`; cada faena se stageó con paths explícitos.
- `apps/api-python/logs/**` y `packages/py/application/logs/**` (`.jsonl`) NO se versionan (ver `.gitignore`).
- No subir ramas ni tags ni afirmar "GREEN" sin ver el run real.

---

FIN DEL RELEVO (preparado por sesión de auditoría+hotfix V2.14 el 2026-09-08)
