# RELEVO — V2.15.4 (Bloque A + Bloque C: aislamiento account-less) — 2026-09-09

> **Padre:** auditoría de certificación externa **V2.15.3** (tag `5ef9016b` / `v2.15.3-beta`) → plan `auditoría_certificación_v2.15.3_c87386b2.plan.md`, secuencia **V2.15.4 → V2.15.5 → V2.16**.
> **Este fichero**: relevo de bloque de **implementación** (working-tree en `main`, sobre `5ef9016b`). **NO es una elevación** — no hay bump ni tag ni run `certify` real todavía.
> **Núcleo congelado (intacto):** FSM / live_orders / ExecutionEvent / ledger / outbox / reconciliation / mandates / core_r / supervised_f3. Solo se endurece la **superficie account-scoped de estudio/lectura cognitiva**.

## 1. Definición del P1 (lo que cierra)

El auditor externo (veredicto) elevó a **P1 activo** el patrón residual de aislamiento (`C2-06`): un recurso `ACCOUNT_SCOPED` de lectura/estudio que recibe `account_id=None` **degradaba a lectura global** (todas las cuentas + filas huérfanas con `account_id IS NULL`).

**Superficie exacta (verificada 1ª mano, no solo informe):**

- Único repo con filtro truthy `if account_id:` → `cognitive_repository.py` (8 sitios): `get_decision_session_by_decision_id:120`, `list_decision_sessions:153`, `list_decision_memory:204`, `count_trials:260`, `list_trials:278`, `list_open_confidence_states:359`, `latest_edge_report:415`, `persistence_stats:447`.
- 5 tablas cognitive con `account_id` **nullable y sin FK** (tables.py): `decision_sessions` `:623`, `decision_memory` `:602`, `trial_records` `:700`, `confidence_states` `:713`, `edge_reports` `:737`. Filas `NULL` legítimas SOLO vía desempeño de cuenta borrada (`account_repository.delete_simulated_account` `:539-549`, audit/journal).
- Entrada HTTP account-less: `ai_governance.py` (`GET /ai/effectiveness L132/`, `GET /ai/decision-sessions L184`, `GET /ai/decision-sessions/learning-summary L217`) e `investor_profiles.py` `refresh-observed` (`L207`, lee `list_decision_memory L223`).
- Interno (no HTTP): `dependencies.py _EdgeReportAdapter.latest_edge_report(L1391-1407)` — pipeline propose, se deja intacto (ver deuda).

## 2. Política aprobada (pregunta resuelta por el owner)

- **`account_id=None` en recurso ACCOUNT_SCOPED de lectura → scope a la cuenta por defecto ACTIVA del principal (owner F7c).** Nunca global.
  - Sin cuenta propia activa → fail-closed: la ruta devuelve vacío / insuficiente, nunca vuelve a invocar el repo con `None`.
- **Filas huérfanas `account_id IS NULL` → excluidas de las lecturas list ACCOUNT_SCOPED** (son audit/journal preservado; excluidas porque el filtro es `== default_account`). Siguen legibles por id con owner-check (journal), no en listados.

## 3. Archivos (faena V2.15.4) — diffs en working-tree sobre `5ef9016b`

| Fichero                                                  | Cambio                                                                                                                                                                                                                                                                                 |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `packages/py/infrastructure/.../account_repository.py`   | `resolve_default_account_for_owner()`: por owner F7c → default visible `is_default` → activa más antigua del owner → `None`. Evita colapso del `is_default` global entre tenants.                                                                                                      |
| `apps/api-python/src/bolsa_api/api/dependencies.py`      | `resolve_account_scope_or_default()`: `account_id` ajeno → 404 (reusa `require_account_access`); ausente → default del principal; sin cuenta propia → `None`.                                                                                                                          |
| `apps/api-python/.../api/v1/routes/ai_governance.py`     | 3 reads acount-less ya NO global (`effectiveness`, `decision-sessions` list, `learning-summary`) **+ 4 escrituras acount-less atribuidas al default** (`POST /ai/decision-memory`, `/ai/trials`, `/ai/edge-reports`, `/ai/recommendations/propose`); sin cuenta propia activa → `400`. |
| `apps/api-python/.../api/v1/routes/investor_profiles.py` | `refresh-observed`: acount-less → default; `accountId` ajeno → 404 (antes no verificaba owner del account).                                                                                                                                                                            |
| `apps/api-python/tests/test_account_isolation.py`        | helpers mémoire/session + **4 tests account-less 2-owners reales**.                                                                                                                                                                                                                    |
| `.github/workflows/release-tag-ci.yml`                   | **Gate real-PG obligatorio** "account-isolation gate V2.15.4" dentro de `lifecycle-pg` (dependencia de `certify` → fail-closed automático).                                                                                                                                            |

## 4. Verificación realizada (PG real local con config de CI-test del repo — sin secretos personales)

- `pytest apps/api-python/tests/test_account_isolation.py` → **23 passed** (19 previos + 4 nuevos 2-owners: decision-sessions×2, effectiveness, refresh-observed-404).
- Regression tras cerrar las escrituras acount-less: `test_account_isolation.py` + `test_ai_authoring.py` → **26 passed**.
- Gate CI completo (los 4 ficheros que correrá el step nuevo) → **43 passed** en PG real.
- `ruff` limpio · `py_compile` OK · `uv run mypy` → **Success** en los 4 ficheros fuente editados.

## 5. Deuda téc. heredada (estado al cierre de este relevo)

1. **Escrituras cognitivas HTTP acount-less — CERRADA en este bloque (decisión owner).**
   - `ai_governance.py` `POST /ai/decision-memory`, `/ai/trials`, `/ai/edge-reports`, `/ai/recommendations/propose`: ahora resuelven `account_id=None` al **default del principal** (`resolve_account_scope_or_default`); sin cuenta propia activa → `400`. No se crean más filas `NULL` invisibles desde HTTP.
   - Verificado: isolation + `test_ai_authoring` → **26 passed** en PG real; ruff + mypy OK.

2. **Pipeline interno** `_EdgeReportAdapter.latest_edge_report(account_id=None)` (propose/spine) lee "último edge" global. No se tocó (automation bajo owner bootstrap, single-tenant). Reconocer antes de multi-tenant real.

3. Endpoint fetch-then-check by-id (`get/replay/outcome`) con `rec.account_id is None` pasa la guard (huérfano legible). Intencional (journal); revisar si se quiere bloquear a no-owner.

## 6. Siguiente bloque — V2.15.5 (DR industrial)

El plan `auditoría_certificación_v2.15.3_c87386b2.plan.md` define V2.15.5 con:

- Fingerprinting **incremental / por bloques** (no re-hash MD5 del `string_agg` entero → escala a catálogos grandes).
- Snapshot **atómico `REPEATABLE READ`** (P1 residual latente de la dr-verify: la lectura de las 18 tablas no es transaccional; tamaño+volatilidad = riesgo de imagen inconsistente).
- Fingerprinting/`md5` de **datos de mercado OHLCV** (fuente de verdad) además de las entidades financieras.
- Cierre del **C2-01** (validación SQL-name de `--target-db` ANTES del DDL destructivo en `db-restore.mjs`).
- Backup **3-2-1**, métricas **RPO/RTO**, restore-test completo **periódico** (no solo en CI-vacía).

## 7. Acción/estado al cierre de este relevo

- Commit V2.15.4 en `main` (sobre `5ef9016b`): los 6 ficheros fuente/test/CI + este doc de relevo. Sin bump de versión ni tag (la elevación es faena aparte, con run real de Release-tag CI `certify=success`).

## 8. TRASPASO — arranque del agente V2.15.5 (DR industrial)

Contexto mínimo para abrir la siguiente versión en un agente nuevo:

- Repo DFS: los destinos de V2.15.5 son **solo infraestructura DR en `scripts/`** (`db-dr-verify.mjs`, `db-restore.mjs`, `db-dump.mjs`, `scripts/lib/backup.mjs`, `scripts/lib/db.mjs`, `scripts/lib/docker.mjs`) y sus referencias `.github/workflows/release-tag-ci.yml` + el doc de auditoría `auditoría_certificación_v2.15.3_c87386b2.plan.md` (sección V2.15.5). El core financiero sigue congelado.
- Comandos de verificación existentes para no romper nada:
  - Batería DR: `pnpm db:dr:test` (en local usa `docker exec bolsa-postgres`; en CI usa `node scripts/db-dr-verify.mjs` con `BOLSA_DR_TCP=1`).
  - Tests real-PG de aislamiento (a no romper): `uv run python -m pytest apps/api-python/tests/test_account_isolation.py` con el env CI-test (DATABASE_URL `postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1`, `ENVIRONMENT=testing`, `JWT_SIGNING_KEY`, `APP_AUTH_SECRET`, `PYTHONPATH=src` desde `apps/api-python`).
- Destinos/checks V2.15.5 (del plan): snapshot atómico `REPEATABLE READ` para el fingerprint de las 18+ tablas; fingerprint incremental por bloques; `md5` de OHLCV (mercado); cierre C2-01 (`--target-db` validado ANTES del DDL destructivo); 3-2-1 + RPO/RTO; restore-test periódico.
- Punto de fricción conocido: la dr-verify actual lee 18 tablas en una tx no transaccional → primero implementar la tx READ COMMITTED/REPEATABLE READ, validarla con datos, y recién después tocar el `md5(string_agg)` por bloques.

FIN DEL RELEVO — bloque **V2.15.4 (Bloque A + C + deuda #1)** commiteado y **verificado en PG real** (isolation 23 · +ai_authoring 26 · gate CI 43 verdes). Preparado para abrir **V2.15.5 (DR industrial)** en un agente nuevo.
