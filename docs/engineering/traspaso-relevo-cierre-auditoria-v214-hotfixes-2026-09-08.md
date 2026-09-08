# Relevo — Cierre auditoría V2.14 + hotfixes de propositura (para agente de 2026-09-08 en adelante)

Entorno: repo en `C:/Users/josea/Documents/Informatica/Typescript/Bolsa_V1`, `main` + worktree local.
Rama base: `main` en `e76a1942` (V2.14 elevation · 1.43.0-beta). Los hotfixes de hoy están commiteados **de forma local** encima (no elevados, no tag, sin bump de package).

> ⚠️ **ACTUALIZADO en la misma sesión (addendo §5):** esos hotfixes se **elevaron y etiquetaron V2.14.1**
> encima de `e76a1942` y quedaron en remoto con **CI GREEN real** (`main`/tag en `99f049a6`, bump
> `1.43.1-beta`). Leer §3 PENDIENTE sabiendo que su primer punto ya está ejecutado.

> Propósito del documento: dejar el estado que cualquier agente siguiente pueda continuar sin rehacer
> ni pisar nada: commits de hoy, el bug de datos resuelto (schema 023), qué queda preexistente en el
> worktree que NO es de esta sesión, y verificación replicable.

---

## 1. Commits de hoy (2026-09-08) — VERIFICADO, no rehacer

Encima de `e76a1942` V2.14 (elevation). Todos "fix interno V2.14 · sin bump/tag" **en el momento de redactar**; desde el addendo §5 pasaron a **elevación V2.14.1** (`1.43.1-beta`, GREEN).

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

- ~~**No commitear un "nuevo"**: revisar si elevar/etiquetar los 3 hotfixes~~ ➜ **RESUELTO (addendo §5):** elevación **V2.14.1** hecha (`1.43.1-beta`, tag `v2.14.1-beta`, CI **GREEN real** run 34222132121 `conclusion=success`). No volver a elevar.
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

## 5. ADDENDO (misma sesión, 2026-09-08 13:5x CEST) — ELEVACIÓN V2.14.1 EJECUTADA Y CERRADA GREEN

Se elevó y etiquetó V2.14.1. **Estado actual de `main`/remoto ya NO es "sin bump/sin tag"** (esto
sobrescribe el §1 "commit de hoy ... sin bump/tag" y el primer punto del §3 PENDIENTE, que quedaban como
decisión abierta). Cadena completa ya pusheada encima de `e76a1942`:

- `dbc0ad1f` + `cd9e3524` + `326c0a8a` + `da181b76` (hotfixes + docs cierre, ya en remoto).
- `848c31e5` **V2.14.1 elevation · bump `1.43.0-beta` → `1.43.1-beta`** (CHANGELOG/README/CURRENT_SYSTEM/
  engineering-index #97 + doc `traspaso-relevo-tag-v2-14-1-beta-2026-09-08.md`).
- `99f049a6` **C1 fix Ruff I001** hallado por el primer Release-tag CI (run 34221166585, `failure`).

**Tag `v2.14.1-beta` → `99f049a6`** (force-update del ref; el run Release-tag definitivo fue el
**34222132121 → `conclusion: success` GREEN real**, disciplina V2.10.1 cumplida: se observó el run real,
no se afirmó). Los hotfixes dejan de ser "fix interno": pasan a auditable/GREEN desde GitHub.

**Sesión siguiente, NO rehacer, NO volver a elevar:** la elevación V2.14.1 está hecha y verde. No crear
commit nuevo de docs sin necesidad.

**Advertencia cosmética conocida (no bloqueante):** los docs CHANGELOG/README/CURRENT_SYSTEM apuntan el
"tip vigente V2.14.1" a `da181b76`, pero el HEAD real de `main`/tag quedó en `99f049a6` (2 commits por
encima: el bump `848c31e5` y el fix CI `99f049a6`). Es una leve inconsistencia textual: en la próxima
faena de docs conviene re-apuntar el tip al SHA que sea entonces HEAD (hoy `99f049a6`). Decisión del
usuario de hoy: NO añadir más commits dedicados solo a ese retoque cosmético.

---

FIN DEL RELEVO (preparado por sesión de auditoría+hotfix V2.14 el 2026-09-08)
