# Changelog

All notable releases of Bolsa V1.

## [1.48.0-beta] — V2.18 / A7 Iter-1 · C3 — 2026-09-09

Elevación (a elevar por release-tag CI desde `v2.18-beta`) de la **Iter-1 de LIVE Certification / A7**,
**gated exclusivamente al gap C3** (crash-injection): una batería **real-PG** de crash de **proceso real**
sobre el worker de recovery/scheduler que cierra el hueco que la Iter-0 (V2.17) dejó mapeado como 🔴.
Núcleo financiero congelado **intacto** (Alembic head `023_ohlcv_bars_unique_reconcile`, sin migración).
Como se decidió en V2.18 (`fsm_only`), C3 valida invariantes de **order-state/FSM** (≈ una resolución exacta,
sin doble transición ni doble materialización) y **NO** cash/position: la vertiente financiera del crash queda
reservada a Iter-2 bajo el roadmap XL-3 (A3/B2/P2-01 son los puentes hacia ella).

### ¿Qué cambia?

- **Home real-PG C3:** `apps/api-python/tests/chaos/live_a7/` con `test_c3_crash_injection_recovery_worker.py`
  (escenarios A/B) y harness de proceso `_crash_recovery_probe.py`. La batería lanza un **subproceso Python
  real** que reclama y resuelve UNKNOWN sobre `PostgresLiveOrderStore` + `live_order_recovery_worker.resolve_one_unknown`
  (el núcleo no se toca): en C3-A el proceso A es **SIGKILLeado con el claim FOR UPDATE en vivo** y un segundo
  proceso reaparece y resuelve **exactamente una vez**; en C3-B relanzar la recuperación tras un resolve durable
  no duplica (idempotencia del `put` + terminal-not-UNKNOWN). Falla-quieto → `financial_apply_count=0` en ambos.
- **CI:** job **`a7-gate`** en `.github/workflows/release-tag-ci.yml` — Postgres service + BD dedicada
  `bolsa_v1_a7` (drop+create, esquema a head por `ensure_migrated` idempotente en la propia batería) + pytest
  `chaos/live_a7` con `LIVE_A7_PG_REQUIRED=1` (fail duro si skip). `a7-gate` se suma a `needs` de `certify` y al
  resumen del artefacto.
- El job offline `python` (tag y `python-ci.yml`) y `lifecycle-pg`/iso quedan intactos; se añade
  `--ignore=.../chaos/live_a7` al pytest offline para mantenerlo hermético (A7 corre en `a7-gate`).

### Verificación

- Live (Postgres real dedicado): `apps/api-python/tests/chaos/live_a7` → **2 passed** (C3-A y C3-B) tanto en
  primera ejecución (migrando de cero) como en repetición.
- Ruff `apps/api-python packages/py` → limpio. Suites unitarias de worker:
  `test_live_order_recovery_worker.py` + `test_scheduler_worker.py` → **12 passed**.
- Relevo del ciclo (nuevo): `docs/engineering/traspaso-relevo-a7-iter1-c3-v2-18-beta-2026-09-09.md`;
  estado C3 actualizado en `docs/engineering/plan-a7-live-certification-gap-map-2026-09-09.md` (§1-ter/§3/§4/§5).

## [1.47.0-beta] — 2026-09-09

Elevación a `main` de la **Iter-0 de LIVE Certification / A7** (ciclo `v2.17-beta`), de acuerdo con el
veredicto de la **auditoría externa de V2.16.1**: P0=0 / P1=0 / Global 9.3 → abrir A7 y **no añadir
features**. Esta iteración es **SÓLO marco y mapa de gaps documental** (sin código ni tests nuevos):
mapea los 16 escenarios de certificación del auditor contra la cobertura ya existente y registra el home
futuro de la batería. Núcleo financiero congelado **intacto**. Alembic head `023_ohlcv_bars_unique_reconcile`.
Package **`1.47.0-beta`** (bump desde `1.46.1-beta`).

### Iter-0 A7 — entregable documental

- **Marco + gap-map:** [`docs/engineering/plan-a7-live-certification-gap-map-2026-09-09.md`](./docs/engineering/plan-a7-live-certification-gap-map-2026-09-09.md)
  — escenario a escenario (`🟢/🟡/🔴`) con evidencia ruta:línea y dobles a reutilizar.
- **Hallazgo P2-05 cerrado:** la incoherencia documental que marcó la auditoría (doc de relevo aún decía
  "sin push") ya fue resuelta por `b8858c2f` (SHA `1596f4ad`, tag `v2.16.1-beta`, CI `#34331846887` GREEN).
- **Home de la batería (Iter-1):** `packages/py/infrastructure/tests/chaos/live_a7/` (PG-real) con gate en
  el job `lifecycle-pg` del release-tag CI.
- **Backlog A7 (Iter-1+):** C3 crash-injection sobre `scheduler_worker` 🔴; A3 broker timeout/network
  real; B2 partial-fill → materialización; P2-01 Applied durable (APPLYING/APPLIED/FAILED).
- Deuda P3 C2 del núcleo sigue ACCEPTED sin tocar; la deuda pos-p3 `[runtime/aislamiento] LIVE A7` pasa a
  "Iter-0 en curso → Iter-1 backlog" (actualizado en `deuda-p3-nucleo-aceptada-c2-2026-09-09.md`).

### Verificación

Sin cambios de código: **Release-tag CI `#34334824584` GREEN** sobre `v2.17-beta` (`conclusion: success`,
certify ✓), tag remoto apuntando a `79df594c`. Relevo del ciclo:
[`docs/engineering/traspaso-relevo-a7-iter0-v2-17-beta-2026-09-09.md`](./docs/engineering/traspaso-relevo-a7-iter0-v2-17-beta-2026-09-09.md).

## [1.46.1-beta] — 2026-09-09

Elevación a `main` (tag **`v2.16.1-beta`**, commit `1596f4ad`, push a `origin/main`) del ciclo de
cierre de hallazgos residuales de la auditoría sobre `v2.16-beta`: owner-scoping de cuenta por
defecto (**P1-02/03**), **Auditoría 2** (fill_unseen tapado por cancel en el incidente `live_drift`) y
**Auditoría 3** (consentimiento del operador de ExecutionEvent en dos fases, sin salida).
Núcleo financiero congelado **intacto** (deuda P3 C2 aceptada como riesgo medido, ver
[`docs/engineering/deuda-p3-nucleo-aceptada-c2-2026-09-09.md`](./docs/engineering/deuda-p3-nucleo-aceptada-c2-2026-09-09.md)).
Package **`1.46.1-beta`** (bump desde `1.46.0-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**
(sin migración nueva).

### P1-02/P1-03 — owner-scoping del account default (`set_default_account`/`delete_simulated_account`)

- `set_default_account` y `delete_simulated_account` ya no tratan el `is_default` y la promoción
  de siguiente default de forma global-cuenta: se ciñen al **owner** que hace la operación
  (`owner_user_id` desde el principal autenticado en rutas), evitando sobrescribir el default de
  otro tenant o promover una cuenta activa ajena tras borrar un default.
- Rutas `accounts.py` pasan `owner_user_id` resuelto del principal; el purge administrativo
  del ciclo de vida usa `for_purge=True` (scope de sistema) pero la promoción de default sigue
  siendo owner-local (P1-03).
- CI iso: gate `account-isolation` real-PG **43 passed**.

### Auditoría 2 — el incidente `live_drift` ya no tapa un `fill_unseen` posterior

- Cuando una cuenta ya tiene un `live_drift` activo (abierto p. ej. por `cancel_broker_side`) y
  en un tick posterior el recovery entregar un drift de **firma nueva** (order/venue/subtipo,
  p. ej. `fill_unseen`), el snapshot del incidente vigente se **amplía** de forma idempotente
  por firma (`publish_order_live_drifts`, campo `merged`) en lugar de descartarlo con un
  `already_active` silencioso. Un drift ya registrado sigue siendo replay no-op. Nunca se crea
  un 2º OPEN ni se auto-heal.

### Auditoría 3 — consentimiento del operador de ExecutionEvent con salida real (dos fases)

- `apply_fill_idempotent` captura con idempotencia (1ª fase, `permit=False` no materializa).
  Nueva `apply_pending_execution(execution_id, apply_finance)` (2ª fase) retoma la traza ya
  capturada cuando llega el "go" y materializa Position/Ledger sin chocar con
  `duplicate_skipped`; `event_not_found` si la traza no existe (fail-closed) y
  `captured_not_applied` si el apply no fue efectivo (reintentable).

### Verificación

Unit (18 drift + execution) + regresión (60) verdes; e2 PG real en scratch `bolsa_c1_scratch`
(head 023, dedicated) **5/5**, incluido el merge `fill_unseen`; ruff CI-parity 0; mypy src 0.
Shared `bolsa_v1` intacta en 023.

**Release-tag CI `#34331846887` GREEN** sobre `v2.16.1-beta` (`conclusion: success`, certify ✓):
security · shared · decision-spine · lifecycle-pg · dr-verify · python (ruff/mypy/pytest) ·
frontend (+contract) · playwright (mock E2E). Integrated E2E opt-in skipped (no requisito de
GREEN). Repo dispuesto para **auditoría externa** sobre el tag `v2.16.1-beta`.

## [1.46.0-beta] — 2026-09-09

Elevación a `main` de `V2.15.4` (aislamiento account-less) + `V2.15.5` (DR industrial OHLCV/backup 3-2-1) en **un solo tag `v2.16-beta`**; núcleo financiero congelado intacto; sin migración nueva. Producto **BETA / no producción**.
Package **`1.46.0-beta`** (**bump** desde `1.45.3-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**.
Tip: **`302a3220`** (V2.15.5) == código elevado; este commit es el bump/elevación.

### V2.15.4 — aislamiento account-less fiable (P1 C2-06)

Reads/writes **account-less no degradan a global**; sin cuenta propia quedan fail-closed, nunca asumen tenant del owner ajeno:

- `account_repository.resolve_default_account_for_owner`: el default activo visible al owner F7c (evita colapso `is_default` entre tenants).
- `resolve_account_scope_or_default`: `account_id` ajeno → 404; ausente → default del principal; sin cuenta propia → `None` (fail-closed).
- `ai_governance` reads (effectiveness, decision-sessions, learning-summary) y writes (decision-memory, trials, edge-reports, propose): account-less → default del principal; filas huérfanas `NULL` excluidas de listados.
- `investor_profiles` refresh-observed: valida el owner del account; account-less → default.
- CI: gate `account-isolation` real-PG en `lifecycle-pg` (fail-closed vía `certify`).
- Tests: 4 account-less 2-owners (23 ISO + ai_authoring 26 verdes real-PG).

### V2.15.5 — DR industrial: snapshot atómico + digest por bloques + OHLCV + C2-01 + backup 3-2-1/RPO-RTO

Alcance SOLO infraestructura DR (`scripts/`), núcleo financiero congelado:

- **Snapshot atómico `REPEATABLE READ`**: TODAS las tablas (financieras + mercado) se leen en **UNA** transacción `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; … COMMIT;` → imagen consistente. Parser arreglado (psql `-A` emite `|`, no tab) → el digest de tablas no vacías ya reporta cuenta real (antes 0/vacío y el cheque pasaba en vacío).
- **Digest por BLOQUES** (`CHUNK_SIZE=5000`, md5 por bloque ordenado + concat) en vez de `md5(string_agg total)` → memoria acotada y determinista; añade `MARKET_ENTITIES`: `ohlcv_bars` (167k, fuente de verdad), `instruments`, `data_sync_log`.
- **RTO** medido del restore + cobertura volcada a `logs/agent/db-dr-verify.json`.
- **C2-01** (`db-restore`): `--target-db` validado (`^[A-Za-z0-9_.-]+$`) **ANTES** del DDL destructivo.
- **Backup 3-2-1 + RPO/RTO**: espejo a dir env `DB_BACKUP_MIRROR_DIR` (2º medio/árbol) + manifest registra `mirror`; `db-backup-list` muestra RPO y estado espejo. (3er medio off-site: guía MVP de set-up, ver [`docs/engineering/guia-off-site-3er-medio-2026-09-09.md`](./docs/engineering/guia-off-site-3er-medio-2026-09-09.md).)
- `db-backup-cron-win`: tarea programada de **restore-test DR diario** (`db:dr:test` con volumen real) junto al backup diario.

### Verificación real

Batería DR local con volumen real (dump → checksum → restore a scratch → integridad md5 por bloques financiero+mercado) **verde** + aislamiento **43 passed** real-PG + `node --check` OK + C2-01 rechaza inyección antes del DDL (`bolsa_v1` intacta). Gate industrial del tag: job `dr-verify` del Release-tag CI (TCP, fail-closed vía `certify`).

## [1.45.3-beta] — 2026-09-08

Hardening de la auditoría **V2.15.1 C2** (delta en **scripts DR + CI del tag**; núcleo financiero congelado sin tocar; sin migración nueva). Producto **BETA / no producción**.
Package **`1.45.3-beta`** (**bump** desde `1.45.2-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**.
Cierra tres hallazgos de la pasada anterior:

- **C2-02 (P2-alto)** — `scripts/db-dr-verify.mjs` extiende la batería DR con **invariantes financieras de datos**: inventario canónico de 18 tablas (`FINANCIAL_ENTITIES`, fuente `tables.py`), snapshot `COUNT(*)` + digest md5 del contenido canónico ordenado **BEFORE** sobre la principal y comparación **AFTER** sobre la scratch; checks `dr-snapshot-financiero-leido` y `dr-datos-financieros-integridad`. El restore deja de ser solo "estructural ↔ head" y pasa a ser **financieramente verificable**. (md5 en vez de sha256: `sha256()/encode` viven en `pgcrypto`, no en PostgreSQL 16 core por defecto al restaurar la scratch; md5 built-in basta como guard no-adversarial.)
- **C2-12 / C2-13 (P2/P3)** — la faena DR y el readiness schema-aware se elevan al **release-tag CI** para que certifiquen en el runner, no solo en local:
  - transport layer TCP opt-in `BOLSA_DR_TCP=1` (psql/pg*dump de host por `PGHOST/PGPORT/PGUSER/PGPASSWORD`/`DB*\*`) en `docker.mjs`/`backup.mjs`/`db-restore.mjs`/`db-dr-verify.mjs`, con **default Docker intacto** para dev.
  - job nuevo **`dr-verify`** en `release-tag-ci.yml` (`services: postgres:16-alpine` + `postgresql-client` + `alembic upgrade head` + batería DR por TCP), incorporado a `needs:`/fail-if/summary de `certify` → **un DR rojo rompe el tag**.
  - `apps/api-python/tests/test_health.py` (readiness `/health/ready` 200/503 schema-aware) entra en el pytest PG de `lifecycle-pg`.
    Validación local: `pnpm db:dr:test` (Docker) → **8/8 PASS**, incluidas las 2 checks nuevas C2-02. Certificación final del path TCP (runner) vía **Release-tag CI** de este tag.

## [1.45.2-beta] — 2026-09-08

Auditoría externa **V2.15.1 C2** (delta exclusivamente **documental/audit**; núcleo financiero sin tocar). Producto **BETA / no producción**.
Package **`1.45.2-beta`** (**bump** desde `1.45.0-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`** (sin migración nueva).
V2.15.1 C2 re-certificada ≈ **9.1/10 Beta** (ver [`auditoria-v2-15-1-c2`](./docs/engineering/auditoria-v2-15-1-c2-2026-09-08.md)): los tres P1 de V2.15 cerrados; deudas P2/C2-12+13 (DR+readiness no corren en tag-CI) y C2-02 (invariantes financieras en batería DR) decididas antes del "OK final"; account isolation **P2-latente** (no P1-activo, single-owner). Cierres de esta pasada: C2-08 (cash paper/ledger idempotente real-PG, no P1 de doble-abono), C2-06 (sin path de creación por JWT; ops-self-eval cerrado), contrato FE↔BE núcleo **limpio**.

## [1.45.0-beta] — 2026-09-08

V2.15 **C2 · cierre de certificación** a `main` (restore seguro + readiness schema-aware + batería DR). Producto **BETA / no producción**.
Package **`1.45.0-beta`** (**bump** desde `1.44.0-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`** (sin migración nueva).
Núcleo financiero (FSM/live_orders/ExecutionEvent/ledger/outbox/reconciliation) **congelado e intacto**. Relevo [`traspaso-relevo-tag-v2-15-1-c2-cierre-certificacion-2026-09-08.md`](./docs/engineering/traspaso-relevo-tag-v2-15-1-c2-cierre-certificacion-2026-09-08.md).

### Cierre certificación — restore 100 % seguro (P1 V2.15-01/02)

- **`db:restore`**: psql con `-v ON_ERROR_STOP=1` (cualquier error SQL ⇒ failed). Alembic tras el restore se dirige **siempre a `--target-db`** (reescritura de `DATABASE_URL` vía `redirectDatabaseUrlTo`), nunca a `bolsa_v1`. Aborta si el sidecar `.sha256` no coincide.
- `scripts/lib/db.mjs`: `runAlembicUpgrade({ databaseUrl })` + `redirectDatabaseUrlTo(db)`.

### Cierre certificación — readiness schema-aware (P1 V2.15-03)

- **`/api/health/ready`** exige `READY = PostgreSQL AND alembic_version == expected_head` (Alembic): 200/ready solo si ambos; 503 si la BD responde pero el esquema no está al head (fail-closed, nunca "ready" contra una BD vieja). Campo nuevo `schema_status`.
- `session.py::read_db_schema_current` (lee `alembic_version`, mensajes redactados).

### Batería DR y hardening de backups (P2)

- **`pnpm db:dr:test`** (`scripts/db-dr-verify.mjs`): vuelca, verifica checksum, restaura a scratch vía `db-restore --target-db`, comprueba head/esquema consultable y que `bolsa_v1` no cambia; limpia la scratch. GREEN en local.
- `backup.mjs`: sello con ms + escritura exclusiva (O_EXCL), sidecar `<file>.sha256`, `backups-manifest.json`, `DB_BACKUP_KEEP` mínimo ≥1.

### Tests y contrato

- `test_health.py`: ready 200-at-head + 503 schema-mismatch + 503 unmigrated. Contrato `openapi.json`/`schema.d.ts` regenerados (solo `schema_status` + descripciones).

## [1.44.0-beta] — 2026-09-08

V2.15 **1er ciclo de hardening** a `main` (PREVENCIÓN backups + provenance/readiness). Producto **BETA / no producción**.
Package **`1.44.0-beta`** (**bump** desde `1.43.2-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**.
**≠** Accept LIVE · **≠** thaw · **≠** settlement · éxodo LIVE no certificado. Relevo [`traspaso-relevo-v2-15-backups-prevencion-2026-09-08.md`](./docs/engineering/traspaso-relevo-v2-15-backups-prevencion-2026-09-08.md).

### Prevention — backups de `bolsa_v1` (faena 1)

- **`pnpm db:dump` / `db:backup`**: volcado local `db-backups/bolsa_v1-<stamp>.sql[.gz]` vía `docker exec pg_dump`
  (por fuera del contenedor) + poda por retención (`DB_BACKUP_KEEP`, default 14). `db:backup:list` lista.
- **`pnpm db:restore --file … --yes`**: recrea la BD destino y aplica el dump por stdin, re-aplicando Alembic head `023`.
  `--target-db` y `--no-alembic` para pruebas seguras. `db:backup:cron:win` genera tarea `schtasks` diaria.
- `.gitignore db-backups/` (no versiona), `.env.example DB_BACKUP_KEEP`, doc en `docs/DEV_STARTUP.md`.
  Motivo: [incidente pérdida de listas](./docs/engineering/traspaso-incidente-perdida-list-2026-09-08.md).
  Helpers [`scripts/lib/backup.mjs`](./scripts/lib/backup.mjs) · scripts `db-dump/db-restore/db-backup-list/db-backup-cron-win`.

### Hardening V2.15 — first cycle (provenance + readiness)

- **Readiness operacional**: nuevo `GET /api/health/live` (liveness sin BD) y `GET /api/health/ready`
  (readiness, PostgreSQL requerido → 200/ready o 503/not_ready). `/api/health` agregado compatible.
- **Provenance obligatoria en producción**: `require_release_identity_env()` eleva en `create_app` cuando
  `PRODUCT_VERSION`/`API_CONTRACT_VERSION` faltan en `ENVIRONMENT=production` (allowlist dev/test/staging
  las mantiene opcionales para no romper CI/local).
- Tests offline `test_provenance_gate.py` + tests `live/ready` en `test_health.py`; `openapi.json`/`schema.d.ts`
  regenerados (solo aditivo). Rama `stage/v2.15-backups-prevencion-2026-09-08` → merge PR **#59**.
  Núcleo congelado (FSM/live_orders/ExecutionEvent/ledger/outbox/recon) intacto.

## [1.43.2-beta] — 2026-09-08

V2.14.2 **elevation** (cierre A1: account-isolation ampliada a rutas de LECTURA/estudio) a `main`. Producto **BETA / no producción**. Package **`1.43.2-beta`** (**bump** desde `1.43.1-beta`). **≠** Accept LIVE · **≠** thaw · **≠** settlement · éxodo LIVE no certificado.

### Close — A1 account-isolation extendida a rutas de LECTURA/estudio (2026-09-08)

- **Cierre A1 residual (deuda del cierre V2.14.1).** Además de los gates de EJECUCIÓN ya aplicados
  (confirm/evaluate-exits/execute-auto/paper-desk-cycle), quedó la deuda de que los endpoints de
  **lectura/estudio/acount-scope** operaban sin `require_account_access` (solo explotable con ≥2.º
  owner real; hoy single-owner bootstrap). Al añadirse `require_owned_account_if_present`
  (`dependencies.py`), se bloquea (404) toda lectura/estudio que declare una `account_id` que no
  pertenezca al principal del request; `account_id` ausente (demo/global) se preserva para la UI.
- **Rutas gateadas con cuenta visible:**
  - `ai_governance.py`: `GET /ai/effectiveness`, `POST /ai/decision-memory`, `GET /ai/decision-sessions`,
    `GET /ai/decision-sessions/learning-summary`, `GET /ai/decision-sessions/{id}` + `/replay`,
    `POST /ai/decision-sessions/{id}/outcome`, `POST /ai/trials`, `POST /ai/edge-reports`,
    `POST /ai/recommendations/propose`.
  - `instrument_daily_opinions.py`: `POST /instrument-daily-opinions/query`,
    `GET /instrument-daily-opinions/auto-telemetry`, `POST /instrument-daily-opinions/auto-propose`,
    `POST /instrument-daily-opinions/eod-batch`.
  - `paper_desk.py`: `GET /paper-desk/daily-report`.
  - `risk.py`: `GET /risk/ops-self-eval`.
- Tests de aislamiento por cuenta añadidos en `apps/api-python/tests/test_account_isolation.py`
  (effectiveness/decision-sessions/ops-self-eval/daily-report → 404 cuenta ajena). En el informe de
  lectura A1 (`audit-interno-lectura-v2-14-2026-09-08.md`) el hallazgo A1 pasa de **[cerrado parcial]**
  a **[cerrado]** (la nota cross-account multi-owner sigue `[runtime-aislamiento]`: hoy único owner real).

## [1.43.1-beta] — 2026-09-08

V2.14.1 **hotfix elevation** (`provenance self-reported + contract G12/G13` · `A1 account-isolation` · `schema 023 reconcile`) a `main`. Producto **BETA / no producción**. Tip vigente **`main` → [`da181b76`](https://github.com/jvelasca/Bolsa_V1/commit/da181b76)** (cierre auditoría V2.14 · +hotfixes 2026-09-08). Package **`1.43.1-beta`** (**bump** desde `1.43.0-beta`). **≠** Accept LIVE · **≠** thaw · **≠** settlement · éxodo LIVE no certificado.

### Hotfix interno — reconciliación upsert OHLCV → schema `023_ohlcv_bars_unique_reconcile` (2026-09-08)

- **Schema-drift (auditoría interna V2.14):** `ohlcv_repository.upsert_bars` (`ON CONFLICT (instrument_id,timeframe,timestamp)`, cd451fea) exigía un índice único que las migraciones Alembic no creaban (solo PK id) → todo el sync de mercado abortaba (500, `InvalidColumnReference`), la BD quedaba sin barras y la UI mostraba listas vacías e "histórico no disponible". Añadida migración **`023_ohlcv_bars_unique_reconcile`** (+índice único declarado en `OhlcvBarRow`) y repoblado el histórico (44.7k barras 1d, 2021→hoy, para los 35 activos IBEX; freshness `current`). Guards tests real-PG/provenance actualizados a head `023`.

### Hotfix interno — provenance self-reported + contract gate G12/G13 (2026-09-08)

- `GET /api/health → provenance` (PRODUCT/PACKAGE/GIT_SHA/DB_SCHEMA/API_CONTRACT desde fuentes únicas, sin DB) · `bolsa_api.provenance` · `contract-check.ts` **G12** `OperationalIncidentV1` + **G13** `SubmitIntentListItemV1` · openapi.json/schema.d.ts regenerados y sincronizados.

### Hotfix interno — A1 account-isolation en rutas de EJECUCIÓN (2026-09-08)

- `require_account_access` en `POST /ai/intents/confirm`, `/position-policies/evaluate-exits`, `/position-automation/execute-auto`, `/paper-desk/cycle`. Rutas de LECTURA/estudio quedan sin gate (deuda residual A1, explotable solo con ≥2º owner real).

## [1.43.0-beta] — 2026-09-08

V2.14 **Financial Execution Core** elevation a `main`. Producto **BETA / no producción**. Tip vigente **`main` → [`e76a1942`](https://github.com/jvelasca/Bolsa_V1/commit/e76a1942)** (V2.14 elevation · 08/09 09:23 UTC). Package **`1.43.0-beta`** (**bump** desde `1.42.0-beta`). Tip previo **`v2.13-beta` → `da5c4b2a`** / `1.42.0-beta`. Alembic head **`022_live_orders_exec`**. `LIVE_EXECUTION_UNLOCKED` default **off** (sandbox · cero POST bridge). **No** LIVE capital · cancel XTB real **PARKED** (honest-boundary, cero POST en cancel). Capacidad técnica ≠ permiso operativo (separación deliberada). Provenance auto-reportada vía `GET /api/health → provenance`.

### V2.14 — Financial Execution Core

- **D0 foundation** [`b54c92d8`](https://github.com/jvelasca/Bolsa_V1/commit/b54c92d8): decree Financial Execution & Full Reconciliation.
- **B1** [`462a30cb`](https://github.com/jvelasca/Bolsa_V1/commit/462a30cb): `Decimal` al boundary financiero (order/cash/position query + drift) — P1-03/P2-02/P2-03.
- **B2** [`67867a04`](https://github.com/jvelasca/Bolsa_V1/commit/67867a04): lease configurable por env (P2-04) + cancel XTB **PARKED** (P2-05).
- **E1** [`f29e452c`](https://github.com/jvelasca/Bolsa_V1/commit/f29e452c): `ExecutionEvent` scaffold idempotente **GATED** (P1-01) + migración **`022_live_orders_exec`** + observabilidad `live_orders` (`attempt_count`/`last_error`/`claim_expires_at`).
- **E2 P2-2** [`2942fec1`](https://github.com/jvelasca/Bolsa_V1/commit/2942fec1): dedup **OPEN** multi-worker en `OperationalIncidentStore` PG (1 incidente, no 2).
- **E2 P2-01** [`0a44764b`](https://github.com/jvelasca/Bolsa_V1/commit/0a44764b): durable order-drift → `OperationalIncident` `live_drift` (gated).
- **E2 P1-02** [`660fbd83`](https://github.com/jvelasca/Bolsa_V1/commit/660fbd83): reconcile **POSICIÓN continuo** (LR-1) en tick recovery, gated.
- **E2 C1 real-PG** [`96778854`](https://github.com/jvelasca/Bolsa_V1/commit/96778854): batería REAL-PG dedup OPEN/drift frente a PostgreSQL.
- **C1 Release-tag CI** [`095a5ab1`](https://github.com/jvelasca/Bolsa_V1/commit/095a5ab1) → [`78dd3f9a`](https://github.com/jvelasca/Bolsa_V1/commit/78dd3f9a): head real-PG `022` + ruff-I001 whole-tree + fix mypy gate (3 errores) hallados por Release-tag CI real.
- **Elevation** [`e76a1942`](https://github.com/jvelasca/Bolsa_V1/commit/e76a1942): V2.14 + bump `1.43.0-beta` — tip auditable desde GitHub.
- Docs: arranque auditor externo [`08cada82`](https://github.com/jvelasca/Bolsa_V1/commit/08cada82) (veredicto V2.13 sin P0/P1) · deuda hallazgos P2/P3 del audit ampliado V2.13 [`0a217468`](https://github.com/jvelasca/Bolsa_V1/commit/0a217468) · relevo de cierre [`c24bbb67`](https://github.com/jvelasca/Bolsa_V1/commit/c24bbb67).

## [1.42.0-beta] — 2026-09-07

V2.13 **live execution gates** + tip formal `v2.13-beta`. Producto **BETA / no producción**. Tip **`v2.13-beta` → `da5c4b2a`**. Package **`1.42.0-beta`** (**bump** desde `1.41.0-beta`). Alembic head **`021_live_orders_fin`**. Release-tag CI tip según último run sobre este tag. Confirm = firma. `LIVE_EXECUTION_UNLOCKED` default **off** (sandbox · cero POST bridge). **No** LIVE capital. **≠** Accept estricto · **≠** thaw venue · **≠** settlement.

### V2.13 — live execution gates (concurrency + financial invariants + honest cancel + reconcile)

- **Baseline** [`34285584`](https://github.com/jvelasca/Bolsa_V1/commit/34285584): live execution gates — XL-3 concurrency + financial invariants + honest cancel + reconcile.
- **V2.13.1 rc** [`0dce2fa9`](https://github.com/jvelasca/Bolsa_V1/commit/0dce2fa9): honesty remediation (audit H1/H2/H4/H5) post-baseline.
- **V2.13.2 rc** [`656c8b37`](https://github.com/jvelasca/Bolsa_V1/commit/656c8b37): broker-query real (H6) + reconcile máquina `live_orders` (H7); docs cierre H3 [`0983391c`](https://github.com/jvelasca/Bolsa_V1/commit/0983391c).
- **Tip formal** [`da5c4b2a`](https://github.com/jvelasca/Bolsa_V1/commit/da5c4b2a): release `v2.13-beta` (`1.42.0-beta`) — broker-query real H6 + reconcile live_orders H7.
- **V2.13.3 rc CI fix** [`4039087f`](https://github.com/jvelasca/Bolsa_V1/commit/4039087f) · [`4c5dee57`](https://github.com/jvelasca/Bolsa_V1/commit/4c5dee57) · [`e4cfbabd`](https://github.com/jvelasca/Bolsa_V1/commit/e4cfbabd) · [`6e279e2d`](https://github.com/jvelasca/Bolsa_V1/commit/6e279e2d): lifecycle-pg fixtures head-guard a `021_live_orders_fin` (set-membership, no prefijo) + mock E2E live-virtual confirm seed a TRIGGERED tradePlan (CTA sandbox cero POST bridge) + revision corta `varchar32`.

## [1.41.0-beta] — 2026-09-07

V2.12 **XL-3 durable core** + scope-out `list_open_orders` / `cancel_order`. Producto **BETA / no producción**. Tip **`v2.12-beta`** → commit de release de esta entrada. Package **`1.41.0-beta`** (**bump** desde `1.40.0-beta`). Tip previo **`v2.11-beta` → `80e891c4`** / `1.40.0-beta` (**inmutable**). Release-tag CI tip según último run sobre este tag. Confirm = firma. `LIVE_EXECUTION_UNLOCKED` default **off** (sandbox · cero POST bridge). **No** LIVE capital. **≠** Accept estricto · **≠** thaw venue · **≠** settlement.

### V2.12 — XL-3 durable core (live_orders PG + UNKNOWN recovery)

- **Tabla `live_orders`** (PK `order_id` · account_id · indicadores 8×) · migración **`020_live_orders`** idempotente (guards table/index; down `019_outbox_position_fifo`).
- **`PostgresLiveOrderStore`** durable cross-PID: put (insert/update) / get / delete / `list_unknown` / `list_open_orders` / `cancel_order`. Mapeo dominio↔fila 1:1 con `account_id`.
- **Worker `live_order_recovery_worker`** (por defecto ON · `LIVE_RECOVERY_WORKER_ENABLED`): cada tick relee `UNKNOWN` y resuelve vía `query_broker` (no re-POST). Fail-closed: sin cliente / `unavailable` / intraducible → la fila queda `UNKNOWN` (refresca `updated_at`). **Nunca** sintetiza `execute_trade`/ledger.
- **Scope-out V2.12:** `list_open_orders` (no terminales via `NON_TERMINAL_LIVE_STATUSES`, ordena `updated_at`, limita) y `cancel_order` (`CANCELLED` solo si el grafo lo permite; idempotente; `reason` documental). Real cancel round-trip XTB **PARKED** (honest-boundary; cero POST en cancel).
- Wiring: `scheduler_worker` arranca el worker; `dependencies.get_confirm_intent_use_case` inyecta `PostgresLiveOrderStore(session)`.
- Dominio `LiveOrder` (PY+TS) UNKNOWN first-class · no re-POST · PARTIAL qty · `account_id` en PY+TS.
- OR-6 fail-closed: live recon no medido → `LIVE_BLOCKED` / `live_unavailable`; adapter `None` → `live_adapter_not_wired` (vocab LR-1 `clean`).
- OE-1 cablea LR-1 + `liveAdapterWired` (bridge URL) en OR-6.
- Sandbox VIRTUAL: `XtbBrokerAdapter` sin unlock → `live_virtual_sandbox` (cero POST bridge); kill switch reconsultado en adapter.
- **Confirm wiring persist-only:** `LiveOrderCoordinator` registra la máquina tras submit LIVE `submitted`/`unknown` y la expone en `result["liveOrder"]`; PAPER/sandbox/rejected/executed(XL-2) no la tocan. Confirm orquestador sigue `<1100` líneas.
- Docs: [roadmap LIVE Execution](./docs/engineering/roadmap-live-execution-core-2026-09-07.md) · [honesty bridge](./docs/engineering/honesty-pack-xtb-bridge-external-2026-09-07.md) · relevo durable core [`traspaso-relevo-xl3-durable-core-2026-09-07.md`](./docs/engineering/traspaso-relevo-xl3-durable-core-2026-09-07.md) · relevo tag [`traspaso-relevo-tag-v2-12-beta-2026-09-07.md`](./docs/engineering/traspaso-relevo-tag-v2-12-beta-2026-09-07.md).

## [1.40.0-beta] — 2026-09-07

V2.11 Confirm LIVE VIRTUAL (UI honesty). Producto **BETA / no producción**. Tip **`v2.11-beta` → `80e891c4`**. Package **`1.40.0-beta`**. Tip previo **`v2.10.1-beta` → `a060af37`** / `1.39.1-beta` (inmutable). Release-tag CI tip **CERTIFICABLE** — [run 34027601775](https://github.com/jvelasca/Bolsa_V1/actions/runs/34027601775) `conclusion=success`. Confirm = firma. CTA live = **Firmar · Ejecutar en LIVE VIRTUAL (simulado)**. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE capital. **NO MÁS PANELES** (híbrido dentro de Confirm · excepción owner). **≠** Accept estricto · **≠** thaw venue · **≠** settlement.

### V2.11 — Confirm LIVE VIRTUAL

- Pasarela híbrida telegrama + por qué + banner **LIVE VIRTUAL · SIMULADO** en Confirm (`live-virtual-*`).
- CTA TS+PY honesty; badge manual ticket alineado.
- E2E mock `gp-e2e-live-virtual-confirm-mock`.
- Pack [`audit-pack-v2-11-live-virtual-confirm-2026-09-07.md`](./docs/engineering/audit-pack-v2-11-live-virtual-confirm-2026-09-07.md) · relevo tag [`traspaso-relevo-tag-v2-11-beta-2026-09-07.md`](./docs/engineering/traspaso-relevo-tag-v2-11-beta-2026-09-07.md) · arranque auditor [`arranque-auditor-v2-11-live-virtual-2026-09-07.md`](./docs/engineering/arranque-auditor-v2-11-live-virtual-2026-09-07.md).

## [1.39.1-beta] — 2026-09-05

V2.10.1 CI certification hotfix + tip de provenance. Producto **BETA / no producción**. Tip **`v2.10.1-beta` → `a060af37`**. Hotfix código **`7156169f`** (tests/selectores; **no** motor). Package **`1.39.1-beta`**. Tip previo **`v2.10-beta` → `6495dd5f`** (inmutable; Release-tag CI [33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `failure`). Código hotfix CI [33981998373](https://github.com/jvelasca/Bolsa_V1/actions/runs/33981998373) `success`. Release-tag CI tip **CERTIFICABLE** — [run 33983574346](https://github.com/jvelasca/Bolsa_V1/actions/runs/33983574346) `conclusion=success`. Confirm = firma. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE. **NO MÁS PANELES**. **PRODUCT FREEZE** en V2.10.1.

### V2.10.1 — CI GREEN / Certification Fix

- **Cluster A:** expand Daily Desk `no_operar` antes de assert deny stale.
- **Cluster B:** `sr-only` `position-decision-stop` / t1 / t2 con Journey HUD.
- Vitest copy alineado a cabina actual.
- Relevo [`traspaso-relevo-v2-10-1-ci-green-2026-09-05.md`](./docs/engineering/traspaso-relevo-v2-10-1-ci-green-2026-09-05.md) · relevo tag [`traspaso-relevo-tag-v2-10-1-beta-2026-09-05.md`](./docs/engineering/traspaso-relevo-tag-v2-10-1-beta-2026-09-05.md).

## [1.39.0-beta] — 2026-09-05

V2.9 Visual and Operational Certification + V2.10 Seed Ops. Producto **BETA / no producción**. Tip **`v2.10-beta`** (sin tip `v2.9-beta` aparte). Partida **`v2.8-beta` → `a9ec6424`**. Package **`1.39.0-beta`**. Confirm = firma. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE. **NO MÁS PANELES**. Release-tag CI **NO CERTIFICABLE** — [run 33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `conclusion=failure`.

### V2.9 — Visual and Operational Certification (2026-09-05)

- **V2.46–V2.51:** ARM chrome `autoActive` · `orphan_recovery_failed` visible · touch 44px · layout zoom 100/125/150 · snapshots/contraste `gp-e2e-v29` (pixel skip CI linux) · teclado cabina.
- Relevo [`traspaso-relevo-v2-9-visual-operational-certification-2026-09-05.md`](./docs/engineering/traspaso-relevo-v2-9-visual-operational-certification-2026-09-05.md).

### V2.10 — Seed Ops (2026-09-05)

- **V2.52–V2.53:** seed birth Confirm + `signedStop` estructural → `PROTECTED` / Planificado · Journal `runtime.mfeMae` · `scripts/ops_seed_cabin_smoke`.
- Relevo [`traspaso-relevo-v2-10-seed-ops-2026-09-05.md`](./docs/engineering/traspaso-relevo-v2-10-seed-ops-2026-09-05.md) · runbook [`runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md`](./docs/engineering/runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md).
- Relevo tag [`traspaso-relevo-tag-v2-10-beta-2026-09-05.md`](./docs/engineering/traspaso-relevo-tag-v2-10-beta-2026-09-05.md).

## [Unreleased]

### V1.60 — UX Mercado (tarjeta estrella DECISIÓN) (2026-09-02)

- **GP-V160-01..04:** tarjeta estrella `PositionOperationalStarCard` + `usePositionOperationalView` — POV canónico en panel DECISIÓN; T2_READY/T2_EXECUTED · RECONCILIATION_DRIFT · stopHistory colapsable · vitest + testids.
- Wire: `operativa-cockpit-card` · `mercadoCockpitPosicionPhaseLabel` · recon chip POV-aware.
- Spec [`spec-v160-ux-mercado-2026-09-02.md`](./docs/engineering/spec-v160-ux-mercado-2026-09-02.md) · relevo [`traspaso-relevo-v1-60-ux-mercado-2026-09-02.md`](./docs/engineering/traspaso-relevo-v1-60-ux-mercado-2026-09-02.md) · arranque auditor [`arranque-auditor-v1-60-ux-mercado-2026-09-02.md`](./docs/engineering/arranque-auditor-v1-60-ux-mercado-2026-09-02.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.60-beta` → `7ac8ad9b`**.

### V1.59 — E2E Integrated (FastAPI + PostgreSQL) (2026-09-02)

- **GP-V159-01..07:** suite integration pytest + `httpx.AsyncClient` + PG real (`@pytest.mark.integration`): trade/portfolio operational · paper-desk dry-run/gate · ops-self-eval recon · decision-journal · incident resolve/clear HTTP · execute-auto dry_run.
- **Harness:** `v159_harness.py` + skip sin PostgreSQL; complementa Golden Session pytest (no sustituye).
- **Fix colateral:** `opening_gate_seed` siembra serie plana 120d (elimina veto sanity split/dividendo en DS-05).
- Spec [`spec-v159-e2e-integrated-2026-09-02.md`](./docs/engineering/spec-v159-e2e-integrated-2026-09-02.md) · relevo [`traspaso-relevo-v1-59-e2e-integrated-2026-09-02.md`](./docs/engineering/traspaso-relevo-v1-59-e2e-integrated-2026-09-02.md) · arranque auditor [`arranque-auditor-v1-59-e2e-integrated-2026-09-02.md`](./docs/engineering/arranque-auditor-v1-59-e2e-integrated-2026-09-02.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.59-beta` → `b5c5c6ab`**.

### V1.58 — Adversarial Execution (2026-09-01)

- **GP-GOLDEN-DAY-ADV-01:** día PAPER encadenado (BUY → dup fill → T1 → crash replay → TRAIL → T2 network skip → retry → dup event → EXIT → recon clean) en `test_paper_desk_golden_day_adversarial.py`.
- **AdversarialSell:** `fail_next(n)` → `skipped`/`network_failure` sin consumir fill id; retry ejecuta.
- **P0b:** `execute_position_policy_auto` marca leg `failed` solo en `blocked`/`rejected`, no en transport skip.
- **GP-V158-STOP-CLOSED:** STRUCTURAL_STOP + `session=CLOSED` vende; T1 + CLOSED → `queue_next_session`. Hallazgo 22 rondas cerrado como contrato PAPER (sin encolar stop a apertura).
- Spec [`spec-v158-adversarial-execution-2026-09-01.md`](./docs/engineering/spec-v158-adversarial-execution-2026-09-01.md) · relevo [`traspaso-relevo-v1-58-adversarial-execution-2026-09-01.md`](./docs/engineering/traspaso-relevo-v1-58-adversarial-execution-2026-09-01.md) · arranque auditor [`arranque-auditor-v1-58-adversarial-execution-2026-09-01.md`](./docs/engineering/arranque-auditor-v1-58-adversarial-execution-2026-09-01.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.58-beta`**.

### V1.57 — Operational Truth (2026-09-01)

- **GP-V157-01:** `T2_EXECUTED` distinto de `T2_READY`; eventos T2 simétricos a T1; desk map `T2_*` → reduced.
- **GP-V157-02:** `buildStopHistory` incluye `protect` / `trail` / `reduce` / `override` / `stop`.
- **GP-V157-03:** `reconStatus === "drift"` → `RECONCILIATION_DRIFT` (TS + Python); cubo Mesa `requiere_accion`.
- **INV-01..10:** batería `test_inv_operational_truth.py`. Exhaustividad `assertNever` en proyección cognitiva.
- Spec [`spec-v157-operational-truth-2026-09-01.md`](./docs/engineering/spec-v157-operational-truth-2026-09-01.md) · relevo [`traspaso-relevo-v1-57-operational-truth-2026-09-01.md`](./docs/engineering/traspaso-relevo-v1-57-operational-truth-2026-09-01.md) · arranque auditor [`arranque-auditor-v1-57-operational-truth-2026-09-01.md`](./docs/engineering/arranque-auditor-v1-57-operational-truth-2026-09-01.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.57-beta`**.

## [1.56-beta] — 2026-09-01

Hardening Residuals post-V1.55. Producto **BETA / no producción**. Tag **`v1.56-beta`**. Partida **`v1.55-beta` → `c23091d9`**. Package congelado **`1.35.0-beta`**. Confirm/DEX/SubmitIntent **intactos**. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE.

### V1.56 — Hardening Residuals (2026-09-01)

- **GP-SESSION-07e:** assert estricto `target2Leg.status == executed`; fix `apply_position_reduce` promueve T2 `triggered`→`executed` en cierre.
- **GP-SESSION-10r:** pytest drift → human `resolve` → `clear` solo recon clean; sin auto-heal.
- **GP-E2E-01..02:** Playwright smoke Journal (`/decision-journal`) + Consola (`/operational-console`); script `pnpm --filter @bolsa/web e2e`; skip default · `E2E_RUN=1` → 2/2.
- Relevo [`traspaso-relevo-tag-v1-56-beta-2026-09-01.md`](./docs/engineering/traspaso-relevo-tag-v1-56-beta-2026-09-01.md) · arranque auditor [`arranque-auditor-v1-56-beta-2026-09-01.md`](./docs/engineering/arranque-auditor-v1-56-beta-2026-09-01.md).
- Pre-flight: pytest GP **26** · shared **34** · web **29** · ruff OK · tsc OK.

## [1.16-beta] — 2026-08-26

Mesa desk V1.16–V1.19 (ADR-037 extensiones) + backend paralelo auditoría V1.15. Producto sigue **BETA / no producción**. Tag **`v1.16-beta` → `f16119b`**. Partida: **`v1.15-beta` → `fc2ed753`**. Spine **`pnpm test:decision-spine` = 485**. Pack: [`audit-pack-estado-global-2026-08-26-v116.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v116.md). Confirm/DEX/SubmitIntent **intactos**. Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. AUTO **off**.

### Docs — Pack auditor v116 Mesa desk (2026-08-26)

- Pack [`audit-pack-estado-global-2026-08-26-v116.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v116.md): stamp global · scorecard MD-1…5 · limitaciones P1/P2.
- Relevo tag [`traspaso-relevo-tag-v1-16-beta-2026-08-26.md`](./docs/engineering/traspaso-relevo-tag-v1-16-beta-2026-08-26.md) — tag `v1.16-beta` → `f16119b`.
- Spine verificado **485**. Limitaciones: chip DS-05 P1 · sanity E2E P1 · what-if sin gates · Libro showRoute post-tag.

### MD-1 — V1.16 Mesa desk cierre (Operational UX II)

- Cabecera operativa · matriz semántica 10 estados · FeatureErrorBoundary Mesa/Confirm/F3.
- Tests shared + web GREEN · smoke browser 5/5 documentado.
- Pendiente P1: chip DS-05 honesto (F1-H).
- Relevo [`traspaso-relevo-mesa-desk-v116-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v116-2026-08-26.md).

### MD-2 — V1.17 Posición + ticket Confirm

- `showRoute` cableado en `/mesa` · invalidación qty/precio F3 · ticket riesgo primero.
- Libro (`/operaciones`) fuera scope — post-tag.
- Relevo [`traspaso-relevo-mesa-desk-v117-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v117-2026-08-26.md).

### MD-3 — V1.18 Evolución + alertas

- Deltas Journal relevantes · panel alertas decisión · orden ADR-037 en `/mesa`.
- Relevo [`traspaso-relevo-mesa-desk-v118-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v118-2026-08-26.md).

### MD-4 — V1.19 What-if + ranking operable

- `sortMesaCandidatesOperable` · `projectMesaWhatIf` read-only · tests ranking.
- Gates reales what-if **fuera** tag (documentado).
- Relevo [`traspaso-relevo-mesa-desk-v119-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v119-2026-08-26.md).

### MD-5 — Backend paralelo (auditoría V1.15)

- Pickle SHA256 · prod allowlist · `PAPER_D_EXECUTE` Router gate · sanity→DS-05 API · EdgeReport · `require_role` doc.
- pytest **72** passed. `sanity_warnings` E2E runtime **P1 post-tag**.
- Relevo [`traspaso-relevo-mesa-desk-backend-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-backend-2026-08-26.md).

## [1.15-beta] — 2026-08-26

Operational UX — **Mesa · Hoy** (ADR-037). Home diaria `/mesa` compone Decision Board, portfolio, studies e incidentes sin endpoints nuevos. Nav: Mesa · Hoy → Trading → … · Consola ops → Herramientas. Journal: vista tabla simplificada + status 3 dimensiones. **BETA / no producción.** Sin cambios en Confirm, TradePlan, SubmitIntent ni DEX.

### Mesa · Hoy (V1.15 Operational UX)

- Ruta `/mesa` · redirect `/` → `/mesa` · ADR [`037-mesa-hoy-operational-ux.md`](./docs/adr/037-mesa-hoy-operational-ux.md).
- Compositor shared `mesa-hoy-model` · `mapMesaStatusDimensions` · tests.
- Secciones: incidentes → sesión → KPIs → atención → posiciones → candidatos → salud ops.
- Deep-links Journal ficha · Hoy strip adelgazado (top-3 + link Mesa).
- Plan [`plan-mesa-hoy-v115-2026-08-26.md`](./docs/engineering/plan-mesa-hoy-v115-2026-08-26.md).

## [1.13-beta] — 2026-08-26

Durable Execution v1.13 (D0 + DEX-1…DEX-5). Producto sigue **BETA / no producción**. Tag anotado **`v1.13-beta` → `c8d5800`** (Release tag CI GREEN). Partida: **`v1.12-beta` → `369b5d1`**. Spine **`pnpm test:decision-spine` = 483**. Pack: [`audit-pack-estado-global-2026-08-26-v113.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v113.md). OR-2 cerrado vía DEX-1+DEX-2. Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. Confirm = única firma. Mesa default **paper**. LIVE **experimental**. AUTO **off**.

### Docs — Pack auditor v113 Durable Execution (2026-08-26)

- Pack [`audit-pack-estado-global-2026-08-26-v113.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v113.md): stamp global · scorecard DEX-1…5 · candidatas post-v1.13.
- Relevo tag [`traspaso-relevo-tag-v1-13-beta-2026-08-26.md`](./docs/engineering/traspaso-relevo-tag-v1-13-beta-2026-08-26.md) — tag `v1.13-beta` al stamp.
- Spine verificado **483**. Cero thaw · cero UI Mesa · cero AUTO · cero broker.

### DEX-5 — Operational invariants (V1.13 Durable Execution)

- Kernel `paper_order`: qty > 0 en build · FILLED rechaza filled < 0 o filled > ordered.
- Predicados `operational_invariants.py` (qty · filled≤ordered · terminal · adverse_exposure).
- Property suite spine `test_dex5_operational_invariants.py` (6 invariantes; sin `hypothesis`).
- Spine **`pnpm test:decision-spine` = 483** (465 → 483).
- Pack v113 stampado en Unreleased Docs · sin UI Mesa incidente · sin thaw.
- Plan [`plan-dex5-operational-invariants-2026-08-26.md`](./docs/engineering/plan-dex5-operational-invariants-2026-08-26.md) · relevo [`traspaso-relevo-dex5-operational-invariants-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex5-operational-invariants-2026-08-26.md).

### DEX-4 — Confirm = orquestador (V1.13 Durable Execution)

- Paquete `bolsa_application/confirm/`: Identity · RiskGate · OpeningGate · ExitGate · Execution · SubmitIntent · PositionSync.
- `ConfirmRecommendationIntent` = orquestador fino (~922 líneas; pre ~1531). API pública y semántica OR-1…OR-4 / DEX-1…3 intactas.
- Tests spine `test_dex4_confirm_orchestrator.py` (2). Spine **`pnpm test:decision-spine` = 465**.
- Sin property suite (DEX-5) · sin pack v113 · sin UI Mesa incidente · sin thaw.
- Plan [`plan-dex4-confirm-orchestrator-2026-08-26.md`](./docs/engineering/plan-dex4-confirm-orchestrator-2026-08-26.md) · relevo [`traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md).

### DEX-3 — OperationalIncident / resolución recon (V1.13 Durable Execution)

- Kernel `OperationalIncident`: open → in_review → resolved → cleared. Resolve exige nota; clear solo si recon `clean`. Sin auto-heal.
- Alembic `014_operational_incidents` + `PostgresOperationalIncidentStore`. Un activo por `(account, kind)`.
- Opening veto `incident:unresolved` (incluso si el drift ya se fue). Exits ALLOW. Confirm / Fill / HTTP / Router cableados.
- Tests spine `test_dex3_operational_incident.py` + kernel analytics. Spine **`pnpm test:decision-spine` = 463**.
- Sin Confirm split · sin UI Mesa · sin pack v113.
- Plan [`plan-dex3-operational-incident-2026-08-26.md`](./docs/engineering/plan-dex3-operational-incident-2026-08-26.md) · relevo [`traspaso-relevo-dex3-operational-incident-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex3-operational-incident-2026-08-26.md).

### DEX-2 — Crash/restart cross-PID (V1.13 Durable Execution)

- Certificación: store/sesión A persiste → kill → store B fresco → Confirm `UNKNOWN` · 0 re-POST · mismos ids / mapeo venue.
- Tests spine `test_dex2_crash_restart_cross_pid.py` (5). Spine **`pnpm test:decision-spine` = 440**.
- Sin Incident UI · sin Confirm split · sin pack v113.
- Plan [`plan-dex2-crash-restart-cross-pid-2026-08-26.md`](./docs/engineering/plan-dex2-crash-restart-cross-pid-2026-08-26.md) · relevo [`traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md).

### DEX-1 — PostgreSQL SubmitIntent (V1.13 Durable Execution)

- Alembic `013_submit_intents` + `SubmitIntentRow` + `PostgresSubmitIntentStore` (commit en put/delete).
- Fases `recorded` → `send_attempted` → `venue_bound`/`filled` + `send_attempted_at`; espejo TS.
- Confirm: put recorded → mark send_attempted → `adapter.submit`; fila durable ⇒ no re-POST.
- DI Confirm → store PG; InMemory en unit tests. Sin DEX-2 kill · sin Incident · sin Confirm split.
- Plan [`plan-dex1-pg-submit-intents-2026-08-26.md`](./docs/engineering/plan-dex1-pg-submit-intents-2026-08-26.md) · relevo [`traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md).

### Docs — Auditoría v1.12 → V1.13 Durable Execution (2026-08-26)

- Triage externo post-`v1.12-beta`: OR-2 **PARTIAL** (InMemory ≠ cross-PID). Tag `v1.12-beta` intacto.
- Roadmap V1.13 DEX-1…DEX-5 · plan DEX-1 PG `submit_intents` · relevo apertura.
- ADR-035 §8 post-audit · `CURRENT_SYSTEM` next = DEX-1 (cerrado en Unreleased DEX-1; DEX-2 cerrado → next DEX-3).

## [1.12-beta] — 2026-08-26

Operational Reliability v1.12 (D0 + OR-1…OR-6). Producto sigue **BETA / no producción**. Tag anotado **`v1.12-beta` → `369b5d1`** (Release tag CI GREEN). Partida: **`v1.11-beta` → `76d0f951`**. Spine **`pnpm test:decision-spine` = 433**. Pack: [`audit-pack-estado-global-2026-08-26-v112.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v112.md). Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. Confirm = única firma. Mesa default **paper**. LIVE **experimental**.

### OR-6 — SEMI operational certification (v1.12)

- Readiness discreto `PAPER_READY` / `PAPER_DEGRADED` / `LIVE_EXPERIMENTAL` / `LIVE_BLOCKED` (un FAIL crítico no se promedia; AUTO no entra).
- CTA firma `Ejecutar en PAPER|LIVE` + badge LIVE; chip mesa aparte del Autoeval OE-1.
- UI preferencia Paper|Live por cuenta (PA-1 API).
- Spine **`pnpm test:decision-spine` = 433** (post-OR-5 = 418).
- ADR-035 · plan [`plan-or6-semi-operational-certification-2026-08-26.md`](./docs/engineering/plan-or6-semi-operational-certification-2026-08-26.md) · relevo [`traspaso-relevo-or6-semi-operational-certification-2026-08-26.md`](./docs/engineering/traspaso-relevo-or6-semi-operational-certification-2026-08-26.md).
- **No** thaw estricto · **no** AUTO on · **no** Alembic · **no** `contract:gen`.

### OR-5 — Broker execution scenario suite (v1.12)

- Certificación spine A–L + retry (OR-1) + crash (OR-2) en `test_or5_broker_execution_scenarios.py`.
- Ancla en `pnpm test:decision-spine`. Paper/mock; sin live accepted; sin mass sim.
- Spine **`pnpm test:decision-spine` = 418** (post-OR-4 = 403).
- ADR-035 · plan [`plan-or5-broker-execution-scenario-suite-2026-08-26.md`](./docs/engineering/plan-or5-broker-execution-scenario-suite-2026-08-26.md) · relevo [`traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md`](./docs/engineering/traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md).
- **No** CTA LIVE (OR-6) · **no** Alembic · **no** `contract:gen` · **no** simulación 1k–10k.

### OR-4 — Reconciliation → opening veto (v1.12)

- `check_opening`: OI-6 `drift` → DENY aperturas; LR-1 `drift`/`unavailable` → DENY solo venue **live**; exits (`exit`/`exit_hint`/`reduce`) ALLOW.
- Confirm / Fill / HTTP gated / Router cablean puertos recon; fail-closed si lookup lanza. Sin auto-heal · sin UI resolución.
- OE-1: OI-6 status honesto (`ok`/`drift`/`error`/`unavailable`; ya no `not_wired` fijo).
- Spine **`pnpm test:decision-spine` = 403** (post-OR-3 = 387).
- ADR-035 · plan [`plan-or4-recon-opening-veto-2026-08-26.md`](./docs/engineering/plan-or4-recon-opening-veto-2026-08-26.md) · relevo [`traspaso-relevo-or4-recon-opening-veto-2026-08-26.md`](./docs/engineering/traspaso-relevo-or4-recon-opening-veto-2026-08-26.md).
- **No** suite A–L (OR-5) · **no** CTA LIVE (OR-6) · **no** Alembic · **no** `contract:gen`.

### OR-3 — Full order state machine (v1.12)

- `PaperOrderStatus`: `CREATED` | `SUBMITTED` | `ACK` | `PARTIAL` | `FILLED` | `REJECTED` | `CANCELLED` | `EXPIRED` | `UNKNOWN` + grafo `ALLOWED_TRANSITIONS` (PY/TS).
- PaperBroker: `CREATED` → `SUBMITTED` pre-send → `FILLED` ok; boom → `UNKNOWN` (no deja CREATED «como si no enviada»).
- Crash recovery OR-2: `paperOrder.status = UNKNOWN`. Campo opcional `filledQuantity` para PARTIAL.
- Spine **`pnpm test:decision-spine` = 387** (post-OR-2 = 382).
- ADR-035 · plan [`plan-or3-order-state-machine-2026-08-26.md`](./docs/engineering/plan-or3-order-state-machine-2026-08-26.md) · relevo [`traspaso-relevo-or3-order-state-machine-2026-08-26.md`](./docs/engineering/traspaso-relevo-or3-order-state-machine-2026-08-26.md).
- **No** veto recon (OR-4) · **no** suite A–L (OR-5) · **no** OCO · **no** `contract:gen`.

### OR-2 — Crash/restart recovery (v1.12)

- Confirm: `DurableSubmitIntent` persistido **antes** de `adapter.submit` (fail-closed si `put` falla).
- Sin fill local y con intento durable → `ExecutionRecord unknown` reconstruido (`crashRecovery`); **no** segundo `adapter.submit`.
- Mapeo `intent_id` ↔ `venue_order_id` (retry live `submitted` = 1 send). Fill local (OR-1) sigue ganando.
- Store = puerto + InMemory de proceso (sin Alembic). Tabla PG / Redis multi-worker parked en v1.12.
- **Post-audit `v1.12-beta`:** estado **PARTIAL** — no sobrevive al PID; PG = DEX-1 (V1.13).
- Spine **`pnpm test:decision-spine` = 382** (post-OR-1 = 372).
- ADR-035 · plan [`plan-or2-crash-restart-2026-08-26.md`](./docs/engineering/plan-or2-crash-restart-2026-08-26.md) · relevo [`traspaso-relevo-or2-crash-restart-2026-08-26.md`](./docs/engineering/traspaso-relevo-or2-crash-restart-2026-08-26.md).
- **No** OR-3 state machine · **no** veto recon (OR-4) · **no** `contract:gen`.

### OR-1 — End-to-end idempotency (v1.12)

- Confirm paper: clave canónica = `decision_id` (sin fallback `confirm-{uuid}`); sin `decision_id` → `error` / `decision_id_required` pre-send.
- `intent_id` / `PaperOrder.order_id` estables (`INT-{slug}` / `ORD-{slug}`) derivados de `decision_id`.
- Short-circuit pre-`adapter.submit` si ya hay fill local (`ExecuteTrade.find_existing_by_idempotency`); replay sin segundo submit ni journal `executed` duplicado.
- Spine **`pnpm test:decision-spine` = 372** (partida v1.11 = 367).
- ADR-035 · plan [`plan-or1-e2e-idempotency-2026-08-26.md`](./docs/engineering/plan-or1-e2e-idempotency-2026-08-26.md) · relevo [`traspaso-relevo-or1-e2e-idempotency-2026-08-26.md`](./docs/engineering/traspaso-relevo-or1-e2e-idempotency-2026-08-26.md).
- **No** Alembic · **no** `contract:gen` · **no** OR-2/OR-3/OR-4 en esta rebanada.

## [1.11-beta] — 2026-08-26

Operational Integrity v1.11 (OI-1…OE-1). Producto sigue **BETA / no producción**. Tag anotado **`v1.11-beta` → `76d0f951`** (Release tag CI GREEN). Partida: **`v1.10-beta` → `047ddb6`**. Spine **`pnpm test:decision-spine` = 367**. Pack: [`audit-pack-estado-global-2026-08-26-v111.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v111.md). Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. Confirm = única firma. Mesa default **paper**.

### OI-1 — Continuidad operativa (v1.11)

- **Manual trade:** `POST /portfolio/trade` y pending sin plan nacen PositionState con override `human_manual`.
- **Pending SELL / manual sell:** cierran o reducen Position persistida vía `post_fill_position_sync`.
- **Confirm honesty:** fill ejecutado no se reporta como error si falla persist/journal posterior (`positionPersist`).
- **Proteger:** Confirm persiste stop operativo (H2); botón «Confirmar protección»; cero ledger.
- **Lab:** `evaluate-exits` con `executeTrades` persiste exit si `trade_executed` (Lab ≠ mesa).
- ADR-034 · plan [`plan-oi1-continuity-2026-08-26.md`](./docs/engineering/plan-oi1-continuity-2026-08-26.md) · spine **273**.

### OI-2 — Risk signature honesty (v1.11)

- **SEMI opening:** `risk_signature` con `require_triggered_plan` — sin TradePlan TRIGGERED → `rejected_by_gate` / `no_tradeplan`.
- **Manual HTTP:** sin cambio (no pasa por `risk_signature`).
- **UI:** copy `no_tradeplan` en F3 risk block y supervised panel.
- Plan [`plan-oi2-risk-signature-honesty-2026-08-26.md`](./docs/engineering/plan-oi2-risk-signature-honesty-2026-08-26.md) · spine **274**.

### OI-3 — ExecutionRecord UNKNOWN ≠ ERROR (v1.11)

- **Confirm:** excepción de `execute_trade` → `trade.status=unknown` + `executionRecord.outcome=unknown` (nunca `error`, nunca `rejected_by_gate`).
- **Gate/skip** antes de enviar → `not_executed`. Fill OK + persist falla → `executed` (OI-1).
- **UI/HELP:** copy «no asumir que no se ejecutó».
- Plan [`plan-oi3-execution-record-2026-08-26.md`](./docs/engineering/plan-oi3-execution-record-2026-08-26.md) · spine **283**.

### OI-4 — PaperOrder CREATED→FILLED (v1.11)

- **Confirm / FillPending:** al enviar nace `paperOrder` CREATED; fill → FILLED. Gate/skip → no hay orden. Excepción de envío → CREATED (fill no confirmado).
- **UI/HELP:** CREATED ≠ FILLED; orden creada no es fill. Venue PAPER ≠ broker.
- Plan [`plan-oi4-order-lifecycle-2026-08-26.md`](./docs/engineering/plan-oi4-order-lifecycle-2026-08-26.md) · spine **291**.

### OI-5 — Position revisions (v1.11)

- **PositionRevision:** historia append-only de stop/status en `PositionState.revisions` (JSON snapshot).
- **applyCurrentStop / applyReduce:** append solo si hay cambio real; mark no; protect → `origin=protect`.
- **UI/HELP:** stop/status con historia auditada; Proteger deja huella.
- Plan [`plan-oi5-position-revisions-2026-08-26.md`](./docs/engineering/plan-oi5-position-revisions-2026-08-26.md) · spine **306**.

### OI-6 — Portfolio reconciliation (v1.11)

- **PortfolioReconciliation:** detect/report cash ↔ ledger ↔ holdings ↔ PositionState (OPEN). Add-on / holding sin OPEN → `expected`.
- **No** auto-heal · **no** broker · **no** Alembic · ≠ ADR-021 DÍA D.
- Use-case `ReconcilePortfolioIntegrity` + spine tests.
- Plan [`plan-oi6-reconciliation-2026-08-26.md`](./docs/engineering/plan-oi6-reconciliation-2026-08-26.md) · spine **317**.

### PaperBroker — venue PAPER (v1.11)

- **PaperBroker.submit:** CREATED → ledger fill → FILLED; excepción → CREATED + `unknown`.
- Confirm / FillPending adjuntan `paperOrder` + `paperBroker` (`venue: PAPER`, ≠ broker live).
- **No** `IBrokerAdapter` · **no** broker live · **no** thaw `PAPER_D_EXECUTE`.
- Plan [`plan-paperbroker-2026-08-26.md`](./docs/engineering/plan-paperbroker-2026-08-26.md) · spine **322**.

### BrokerAdapter — puerto Paper | Live (v1.11)

- **IBrokerAdapter:** Confirm / FillPending envían por el puerto (default paper = PaperBroker).
- **Mock LIVE:** `not_wired` — nunca llama `execute_trade` (≠ broker live / XTB).
- Receipt `brokerAdapter` (`venue: PAPER|LIVE`). Gate/skip → sin receipt.
- **No** live · **no** thaw `PAPER_D_EXECUTE`.
- Plan [`plan-brokeradapter-2026-08-26.md`](./docs/engineering/plan-brokeradapter-2026-08-26.md) · spine **331**.

### PH-1 — Confirm protect honesty (v1.11)

- **Proteger:** si H2/`persist` → `None` (o excepción), Confirm no dice `protect_applied`. `skipped` / `stop_not_applied`. Cero ledger: el éxito es persistir.
- **UI:** log «stop no aplicado»; no saca de cola ni graba mandato.
- Plan [`plan-confirm-protect-honesty-2026-08-26.md`](./docs/engineering/plan-confirm-protect-honesty-2026-08-26.md) · spine **334**.

### XL-1 — Broker live XTB (v1.11)

- **XtbBrokerAdapter:** `venue: LIVE`, `adapter: xtb`; POST bridge `/orders`.
- Fail-closed: mock `live_orders_disabled`; `submitted` ≠ fill.
- Confirm/FillPending: rejected→skipped; submitted→unknown `live_submitted_no_fill`; pending intacta.
- **No** thaw `PAPER_D_EXECUTE` · mesa default paper.
- Plan [`plan-broker-live-xtb-2026-08-26.md`](./docs/engineering/plan-broker-live-xtb-2026-08-26.md) · spine **341**.

### LR-1 — Live reconciliation (v1.11)

- **LiveLedgerReconciliation:** live cash/positions ↔ ledger; `clean`/`drift`/`unavailable`.
- Detect/report only · **no** heal · **no** trade · bridge `GET /account/cash|positions`.
- Plan [`plan-lr1-live-reconciliation-2026-08-26.md`](./docs/engineering/plan-lr1-live-reconciliation-2026-08-26.md).

### XL-2 — XTB fill → ledger (v1.11)

- Bridge `filled` (opt-in FILL) → `execute_trade` → Confirm/FillPending `executed`.
- `submitted` sigue ≠ fill · boom → `unknown` (OI-3).
- Plan [`plan-xl2-xtb-fill-ledger-2026-08-26.md`](./docs/engineering/plan-xl2-xtb-fill-ledger-2026-08-26.md).

### VS-1 — Venue selector Paper | Live (v1.11)

- `BROKER_VENUE` + runtime · DI Confirm/FillPending · mesa toggle Paper|Live.
- Live → Xtb (sin URL → `not_wired`) · default paper · ≠ thaw `PAPER_D_EXECUTE`.
- Plan [`plan-vs1-venue-selector-2026-08-26.md`](./docs/engineering/plan-vs1-venue-selector-2026-08-26.md) · spine **362**.

### RV-1 — Redis persist broker venue (v1.11)

- Key `bolsa:risk:broker_venue` · coalesce `memory ?? redis ?? env ?? paper` · DI async.
- Per-account venue **parked**. Plan [`plan-rv1-redis-venue-2026-08-26.md`](./docs/engineering/plan-rv1-redis-venue-2026-08-26.md).

### JP-1 — PositionState JSONB → columnas hot (v1.11)

- Alembic `012`: `direction` · `current_stop` · `remaining_quantity` · `quantity` · `initial_stop` · `actual_entry`.
- Dual-write + backfill; JSONB `position_state` sigue SoT. Plan [`plan-jp1-position-jsonb-columns-2026-08-26.md`](./docs/engineering/plan-jp1-position-jsonb-columns-2026-08-26.md).

### Thaw stamp — `PAPER_D_EXECUTE` DEMO opt-in (v1.11)

- Docs/ops: DEMO opt-in **autorizado**; repo default **OFF**; ≠ venue Live · ≠ thaw estricto P1–P5.
- Plan [`plan-thaw-paper-d-execute-stamp-2026-08-26.md`](./docs/engineering/plan-thaw-paper-d-execute-stamp-2026-08-26.md).

### PA-1 — Preferencia venue por cuenta (v1.11)

- `settings_json.brokerVenue` (`paper`|`live`); coalesce `memory ?? redis ?? account ?? env ?? paper`.
- Lazy Confirm/Fill; mesa/API risk = override **global**. UI preferencia cuenta **opcional**.
- Plan [`plan-pa1-per-account-venue-2026-08-26.md`](./docs/engineering/plan-pa1-per-account-venue-2026-08-26.md).

### OE-1 — Ops Autoeval SEMI·AUTO (v1.11)

- `GET /api/risk/ops-self-eval` + `scripts/ops_operativa_self_eval.mjs` + chip mesa. Measure ≠ Accept.
- Recon OI-6 en informe `not_wired`. Plan [`plan-oe1-ops-autoeval-2026-08-26.md`](./docs/engineering/plan-oe1-ops-autoeval-2026-08-26.md).

## [1.10-beta] — 2026-08-25

Operational Authority v1.10 (H1→P4 Consola de Mesa P4.1+P4.2). Producto sigue **BETA / no producción**. Tag anotado **`v1.10-beta` → `047ddb6`** (Release tag CI GREEN). Partida: **`v1.9-beta` → `7d90d965`**. Spine **`pnpm test:decision-spine` = 260**. Shared **156**. Pack: [`audit-pack-estado-global-2026-08-25-v110.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v110.md). **No** broker · **No** auto-exit CTA producto · thin 5.x/8.x congelados · Confirm = única firma.

### P4 — Consola de Mesa (P4.1 + P4.2)

- Operaciones enriquecido (R, stop, T1/T2, salida advisory); CTAs Revisar/Reducir/Salir → cola Confirm; barra operativa; cola entradas read-only; «No operar hoy» → Journal; barra estado global; filtros cola; Proteger + preview stop en Confirm.
- Plan: [`plan-p4-consola-mesa-2026-08-25.md`](./docs/engineering/plan-p4-consola-mesa-2026-08-25.md) · ADR-033 §7.

### P3 — Una cadena de salida

- Confirm SEMI `exit_hint`/`reduce`: ExitPlan (`manual`) → ExitPermission → fill. Motivo `exit_permission`. Persist `applyReduce`. Operaciones: columna Salida advisory (sin CTA). Lab `evaluate-exits` intacto.
- Plan: [`plan-p3-cadena-salida-2026-08-25.md`](./docs/engineering/plan-p3-cadena-salida-2026-08-25.md) · ADR-033 §4.

### P2 — Riesgo al firmar

- Ticket F3: qty/stop/pérdida €/R del TradePlan TRIGGERED. % caja deja de ser SoT. Override con motivo. Gate Confirm `risk_signature`.
- Plan: [`plan-p2-riesgo-al-firmar-2026-08-25.md`](./docs/engineering/plan-p2-riesgo-al-firmar-2026-08-25.md) · ADR-033 §6.

### P1 — Position durable + wire fill

- Alembic `011`: tabla `position_states` (snapshot TradePlan + PositionState + `open_transaction_id`). Ledger `positions` intacto.
- Wire: Confirm SEMI apertura y FillPendingOrder (si hay snapshot) → `from_fill` (H2). Operaciones muestra stop / T1 / T2.
- Plan: [`plan-p1-position-durable-2026-08-25.md`](./docs/engineering/plan-p1-position-durable-2026-08-25.md) · ADR-033 §2.

### H2 — Invariantes factories

- Guards ADR-033 §5 en factories TS+Py: `from_fill` exige TRIGGERED (o override); stop no empeora; T2 no ataja T1; short close=`buy`; kill switch asimétrico.
- Cero Alembic · cero wire Confirm · cero UI mesa.
- Plan: [`plan-h2-invariantes-factories-2026-08-25.md`](./docs/engineering/plan-h2-invariantes-factories-2026-08-25.md) · ADR-033.

### H1 — Honesty pending ≠ stop

- UI/HELP: «Orden pendiente a precio» (antes Stop/Limitada). Solo `limitPrice`; no es stop de posición.
- Plan: [`plan-h1-honesty-pending-2026-08-25.md`](./docs/engineering/plan-h1-honesty-pending-2026-08-25.md) · ADR-033.

### Docs — Operational Authority v1.10 (D0)

- Triage auditoría de discontinuidad decisión→posición: factories F1–F4 ≠ autoridad viva; ADR-033 + roadmap v1.10.
- [ADR-033](./docs/adr/033-operational-authority-position-persistence.md) docs-only · [roadmap v1.10](./docs/engineering/roadmap-v110-operational-authority-2026-08-25.md) · fase v1.10 cerrada en tag.

## [1.9-beta] — 2026-08-25

Operational Core v1.9 (modelo post-entrada) + INFRA CI-by-tag. Producto sigue **BETA / no producción**. Tag anotado **`v1.9-beta` → `7d90d965`**. Partida: **`v1.8.1-beta` → `e78fbb9`**. Spine **`pnpm test:decision-spine` = 217**. Shared **134**. Pack: [`audit-pack-estado-global-2026-08-25-v19.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v19.md). **No** broker · **No** auto-exit producto · thin 5.x/8.x congelados.

### ExitPermission (Operational Core)

- Gate puro `checkExitPermission` / `check_exit_permission` (TS + Py): ALLOW/DENY post-ExitPlan.
- Reasons: `not_actionable` · `position_closed` · `kill_switch` · `broker_not_allowed` · `paper_auto_env_blocked` · `execution_blocked` · `missing_exit_plan`.
- **≠** `check_opening` · **≠** auto-exit · **≠** ExecuteTrade · sin wire Confirm / EvaluatePositionExits.
- Plan: [`plan-exit-permission-2026-08-25.md`](./docs/engineering/plan-exit-permission-2026-08-25.md).

### INFRA — CI reproducible por tag

- Workflow [`.github/workflows/release-tag-ci.yml`](./.github/workflows/release-tag-ci.yml): `on: push tags v*` **sin** path-filter + `workflow_dispatch`.
- Gates: gitleaks · shared · `test:decision-spine` · frontend · python offline · job `certify` + artefacto summary.
- Path-filters diarios (`frontend-ci` / `python-ci`) **intactos**.
- Plan: [`plan-infra-ci-by-tag-2026-08-25.md`](./docs/engineering/plan-infra-ci-by-tag-2026-08-25.md).

### F4 — ExecutionPlan → PAPER (Operational Core)

- Objeto nuevo `ExecutionPlan` (TS + Py): factory `buildExecutionPlanFromExitPlan` / `build_execution_plan_from_exit_plan`.
- `venue: PAPER` · status `DRAFT`/`PAPER_READY`→`JOURNALED`→`REPLAYED`→`VALIDATED` · broker → `BLOCKED`.
- Stages puros (refs opcionales, sin I/O). **No** ExecuteTrade · **No** `PAPER_D_EXECUTE` on · **No** OCO.
- Plan: [`plan-f4-execution-plan-paper-2026-08-25.md`](./docs/engineering/plan-f4-execution-plan-paper-2026-08-25.md).

### F3 — ExitPlan (Operational Core)

- Objeto nuevo `ExitPlan` (TS + Py): factory `buildExitPlanFromPosition` / `build_exit_plan_from_position`.
- Razones canónicas · status `IDLE`/`HINT`/`ARMED`/`TRIGGERED`/`DONE` · `suggestedAction` advisory.
- Plan: [`plan-f3-exit-plan-2026-08-25.md`](./docs/engineering/plan-f3-exit-plan-2026-08-25.md).

### F2.1 — PositionState transitions

- API pura `applyMark` / `applyReduce` / `applyCurrentStop` (TS + Py).
- Plan: [`plan-f2-1-position-state-transitions-2026-08-25.md`](./docs/engineering/plan-f2-1-position-state-transitions-2026-08-25.md).

### F2 — PositionState (Operational Core)

- Factory `build_position_state_from_fill` / `buildPositionStateFromFill` → `OPEN`.
- Plan: [`plan-f2-position-state-2026-08-25.md`](./docs/engineering/plan-f2-position-state-2026-08-25.md).

### F1 — TradePlan v1 (Operational Core)

- Campos gap ADR-032 §1 **dentro** de TradePlan.
- Plan: [`plan-f1-tradeplan-v1-2026-08-25.md`](./docs/engineering/plan-f1-tradeplan-v1-2026-08-25.md).

### Docs — auditoría externa v1.8.1 + diseño v1.9

- Consolidación v1.8.1 **cerrada** por auditoría externa. Triage: [`audit-ext-v181-triage-2026-08-25.md`](./docs/engineering/audit-ext-v181-triage-2026-08-25.md).
- ADR-032 + gap + roadmap v1.9. **F1–F4 + ExitPermission + INFRA** en este tag; broker adapter sigue no.

## [1.8.1-beta] — 2026-08-25

Operational Consolidation post-`v1.8.0-beta`. Producto sigue **BETA / no producción**. Tag anotado **`v1.8.1-beta` → `e78fbb9`**. Partida: **`v1.8.0-beta` → `8c8b789`**. Spine battery **`pnpm test:decision-spine` = 161**. Pack: [`audit-pack-estado-global-2026-08-25-v181.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v181.md). **No** módulos thin nuevos. **No** PositionState/ExecutionPlan (ADR-032 docs-only).

### Ciclo C4 — TradePlan shape canónico

- Hoy `readCanonicalTradePlan`: canónico sesiones = `session.tradePlan`; F3 = `extra.payload.tradePlan`. Fallbacks (`extra.tradePlan`, payload top-level) marcados `legacy`, no borrados.
- `HoyQueueItem.planSource`: `live` (objeto TradePlan en canónico o fallback permitido) | `projection` (sin plan → C1 WATCH, nunca BUY/ARMED).
- **No** Pydantic DTO · **no** OpenAPI · **no** `contract:gen` (contrato fuerte = ADR-032 / v1.9). Confirm/propose/spine/`check_opening` intactos. C1/C3/C5 intactos.

### Ciclo C5 — MFE/Expectancy honesty

- `MfeMae.source`: `bars` | `close_proxy` | `none`. Hoy Excursión añade sufijo `proxy` si close_proxy. Proxy no se presenta como peak de barras.
- Expectancy `sampleQuality`: insufficient (n<20) / preliminary (20–49) / developing (50–99) / useful (n≥100). `status: ready` (READY_MIN_N=5) no significa estadísticamente útil.
- UI Expectativa: «muestra insuficiente (n=…)» antes de E±R si insufficient. Sigue `≠ permiso`. Parsers `asMfeMae` / `asExpectancy` fail-soft.
- Advisory ≠ permiso. **No** mezclar proxy y bars en agregados futuros. Sin journal histórica.

### Ciclo C3 — ActionQueue

- `buildActionQueue(board)` devuelve la cola completa ordenada (prioridad D2 + `actionability` del plan vivo; dedup por símbolo post-sort).
- Hoy (`mapDecisionBoardToHoyQueue`, default 8) es un **slice** de esa cola, no una agregación que corta a 8 antes de ordenar. C1 intacto: sin TradePlan vivo → WATCH (nunca BUY/ARMED inventados). Sin HTTP ActionQueue.

### Ciclo C2 — Alembic única autoridad

- Públicos `pnpm db:push` / `db:migrate` / `db:migrate:deploy` fail-closed (`Prisma schema is not authoritative. Use Alembic.`).
- Bootstrap (`setup` / `db-ensure` / `db-check`) aplica schema vía `ensure_migrated`. Prisma queda seed + `db:generate`. ADR-025 enmendado.

### Docs

- ADR-032 Operational Core (v1.9 contrato, **docs-only**, no implementado): TradePlan / PositionState / ExecutionPlan. Thin congelados. NO TRADE first-class.

### Ciclo C1 — Hoy honesty + HELP (v1.8.1 P0)

- Hoy: F3/sesión **sin** TradePlan vivo → `WATCH` (nunca BUY/ARMED heurístico). BLOCKED/WATCH de proyección → `whyNot: legacy_projection` (no `fit` ficticio).
- Ayuda: `HELP_CONTENT_AS_OF = 2026-08-25` — AUTO BETA-D (`ACTIVAR AUTO` + `PAPER_D_EXECUTE` opt-in), Decision Spine, TradePlan, Hoy proyección.
- Roadmap consolidación: [`roadmap-v181-operational-consolidation-2026-08-25.md`](./docs/engineering/roadmap-v181-operational-consolidation-2026-08-25.md). **No** módulos thin nuevos.

## [1.8.0-beta] — 2026-08-25

Post-`v1.7.0-beta` spine growth + integrity + Camino D thaw parcial. Producto sigue **BETA / no producción**. Tag anotado **`v1.8.0-beta` → `8c8b789`**. Partida: **`v1.7.0-beta` → `e3b943a`**. Spine battery **`pnpm test:decision-spine` = 159**.

### Decision Spine — TradePlan / mesa / journal

- TradePlan v0 + Ciclos **4.0–4.9** (stop ATR/swing, EntrySetup, ARMED, Wyckoff formal→effort, Board echo).
- Ciclos **5.0–5.3** thin: Thesis Health · Protect/T1 · Exit Radar · MFE/MAE (advisory; ≠ permiso).
- Ciclo **6** Attribution journal thin · Ciclo **7** Spine honesty.
- Ciclos **8.0–8.2** thin: Expectancy · Trail · Bracket (advisory; sin OCO/broker). **Línea crecimiento thin CERRADA.**

### Integridad execute / honesty

- **I1** ExecuteTrade converge (`check_opening` en buy HTTP).
- **I2** Actionability / Indice Operativo server.
- **I3** Shadow honesty — HTTP `paper_auto` exige `PAPER_D_EXECUTE`.
- **RX1** exits `full_auto` honesty — mismo env gate antes del Router. **No** auto-exit producto.

### Thaw Camino D (ADR-023)

- Medición estricta P1–P5 **FAIL** · perfil **BETA-D Accepted** (P1'–P5' + W2–W4).
- UI Libro AUTO on · execute **opt-in** `PAPER_D_EXECUTE=1` (default repo off).
- **A3-wire** (`d704263`): frase exacta `ACTIVAR AUTO` obligatoria antes de `mode:auto`; disarm al salir. Arm ≠ execute.
- Deuda estricto tracking: runbook + `scripts/thaw_estricto_snapshot.mjs` (W2–W4 vigentes).

### Ops / docs

- `TRUSTED_PROXIES` runbook exact-string · valor prod **OWNER**.
- Pack auditoría: [`audit-pack-estado-global-2026-08-25-v180.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v180.md).

## [1.7.0-beta] — 2026-08-24

Ciclo post-`v1.6.0-beta` (Decision Spine + mesa U0–U6 + gates DS-05/DS-03 + ops + copy Research→Radar). Producto sigue **BETA**. Tag anotado **`v1.7.0-beta`** (pendiente de crear por coordinador sobre commit de stamp). Partida: **`c3964fc`**. Tags `v1.6.0-beta` / `v1.5.0-beta` / `v1.3.0` intactos.

### Track B — split backtests + nav Señales (heredado post-R-13)

- **F4′–F6′** (`240c846`): copy nav **Señales** (`/screeners`); tests href B0; herencia R-13 Track B desbloqueado.
- **B1–B12**: extracción incremental de `backtests-page.tsx` (~4698→321 LOC shell) — constantes/tipos, queries, mutations, derivados, URL sync, navegación, Lista AUTO, play cycle, Lab handlers, tabs run/jobs, `useBacktestPageModel`. Sin cambio de comportamiento; smoke manual backtests sigue recomendado.

### Fase 0 Decision Spine (código + docs)

- **F0.5b** (`3670a09`): PortfolioFit v1 — concentración cesta activo+sector, VETO fail-closed; `MaxSectorExposure` cableada.
- **F0.6b + F0.6-UI** (`8df8a65`, `672e88f`): Decision Board v1 backend + UI solo lectura (`/decision-board`).
- **D1/D2/D3**: risk cesta SEMI=AUTO (`7530556`); DecisionPackage contrato en confirm SEMI (`f7b1f6c`); Lab/Radar **fuera** del spine (`ea0c93f`, ADR-019).
- **Confirm SEMI deuda** (`2281903`): `wait` sin sesión ya no ejecuta sell default; side de `exit_hint`/`reduce` desde package.
- **Prove Spine** (`5e81350`): S0–S3, tests `pnpm test:decision-spine`, golden scenario.
- **H5** (`f56af2f`): perfil inversor SEMI → `check_opening` (mismo SoT AUTO).

### UX mesa U0–U6

- **U0–U4** (`6f26f9d`): tips Ayuda, presets S/R, Confirm drawer, chips Fit.
- **U5** (`04e441e`): proyección orden F3 en chart (post-SEMI preview).
- **U6** (`9e9a346`): preview ticket en Confirm/drawer — notional, comisión, margen (UI-only; sin bypass execute).

### Spine residual — gates en `check_opening`

- **DS-05** (`15e86a4`): Data Freshness Gate fail-closed (umbral 5×24h; SEMI ohlcv + AUTO `signal.timestamp`; exits fuera).
- **DS-03** (`41adb8e`): Account Mandate Gate fail-closed (tenure BD `mandate_tenures`; mismatch estrategia AUTO; exits fuera). Batería `pnpm test:decision-spine` **53**.

### Ops (ejecutable + propietario)

- **Ops residual** (`3c53f4e`…`7363ec6`): saneo símbolos `/` en import índices; fix 404 recurrente `BP.L`; re-sync `idx-ftse100` verificado; backup corrupt drop.
- **Ops propietario** (`5100d23`): secret scanning + push protection enabled vía API; runbook `TRUSTED_PROXIES` prod (valor real sigue en propietario).
- **Higiene dev** (`ea9a985`, dato local `bolsa_v1`): script `cleanup_dev_test_residues.py`; 3 cuentas huérfanas R8C eliminadas; `verify_ledger_balance_chain.py` **EXIT 0**.

### Research→Radar copy (UI)

- CTAs y cross-links **Asesor** (`/research`) vs **Señales** (`/screeners`); helpers `asesorHistoryHref`; sin fusión de páginas ni rutas API. Hereda F4′–F6′. Batería: `daily-nav.test.ts` 8/8.

## [1.6.0-beta] — 2026-08-22

Consolidación BETA post-R-12 (ciclo R-13). Producto sigue **BETA**. Tag anotado **`v1.6.0-beta` → `c3964fc`**. Tags `v1.5.0-beta` / `v1.3.0` intactos. Plan: `docs/engineering/plan-r13-consolidacion-beta-2026-08-22.md`.

### R-13 consolidación (docs + E8 micro)

- Cierre de R-12 como ciclo de reparación. Firma de partida R-13: `origin/main` **`5edbcb5`** (histórica) → **`c3964fc`** (A0–A3). README alineado a **v1.6.0-beta**. Track B producto (god-page / Research→Radar) **bloqueado**.
- A2: tests de contrato/ausencia en `chart-new-tab-setup.test.ts`; **purge** de `normalizeChartNewTabSeed` (0 callers). `extractChartNewTabSeed` / `applyChartNewTabSeed` intactos. Pending-delete alto **sin purge**.

### Auth D4 / JWT (incluido en release; commits post-`v1.5.0-beta`, ya en `main`)

- **R12-ACCOUNTS** (`3c958f1`) paquete `bolsa_application/accounts/`
- **R12-AUTH F1–F3** stamp owner + 404 cuenta ajena + cash/trade scoped
- **F4** ADR-027 Opción C **Aceptado** · **F5–F7a** tabla `users` + JWT + list/get scoped · **F8–F8e** perfiles, trackers, policies, events, workspaces, list-for-list
- **F9** FE login campo `login` opcional · **F10** `session_version` + `/auth/refresh` + rate-limit user
- **F7b** script + apply **local** (103→0 NULL; no prod) · **JWT-only** (`tokens.py` eliminado; SHA-256/HMAC → 401)
- **F7c** match estricto `user_id == principal` · `scan.completed` `ownerUserId` · cron stamp `tracker.user_id`
- Pending-delete E8 tests (`851b545`) · purge V2 métricas T+0 19/19 (**E8 N, sin purge**)

## [1.5.0-beta] — 2026-08-22

R-12 Track C (mesa SEMI frontend) + copy E8 residual + leftover CORE-R + tres gates de contrato/ejecución/workers. Producto sigue **BETA**. Tag anotado **`v1.5.0-beta` → `5e52bd6`**. Tag `v1.3.0` → `b778292` intacto. Plan: `docs/engineering/plan-r12-auditoria-ux-2026-08-21.md`.

### Track C + higiene copy

- Track C **C1** (`5bc51ff`): ruta `/confirm`, nav Confirmar con badge de cola, `openHelpAiPlatform({ panel: "supervised-f3" })` navega SPA (no Ayuda)
- Track C **C2** (`01af9ff`): nav diaria Trading · Señales · Confirmar vs Laboratorio / Asesor; hub Señales; copy Universo en vigilancia
- Track C **C3** (`97e20ab`): AUTO de cuenta «No disponible (BETA)»; copy de mesa sin `PAPER_D_EXECUTE`; execute sigue congelado
- Track C **C4** (`154fcd1`): nav **Libro** (Operaciones + Historial); cabeceras «Libro · …»; sin fusionar páginas
- Track C **C5** (`0eb8976`): HELP + Ayuda sync Confirm `/confirm` · Señales/Libro · AUTO BETA · frase SEMI
- Copy E8 residual (`ce601c9`) + leftover CORE-R (`8dd3caf`): CTAs de firma → `/confirm` dejan de decir Ayuda; atajos list-hub `/screeners` = Señales (Laboratorio); leftover CORE-R Proponer F3 ya en Confirmar

### Gates cerrados

- **R12-409 B1** (`eb24608`): declarar HTTP 409 en OpenAPI para conflictos de `idempotency_key` en deposit/withdraw/trade (`{detail: str}`); regen acotada `openapi.json` + `schema.d.ts`; runtime handler sin cambio
- **EXEC-B-CONC** (`ca60d0a`): `ExecuteTrade` deriva `balance_after` trade/fee desde cash post-lock (`result.summary.portfolio.cash`); elimina lectura pre-lock `get_summary`; chaos refuerza invariante B estricta bajo concurrencia
- **R12-SCHED / R-8C.2** (`5e52bd6`): scheduler = crons only; poll no-ARQ → `bolsa-queue-poll-worker`; ARQ → `bolsa-arq-worker` (queue_poll no-op); `run-dev.mjs` spawnea el proceso correcto según `SCAN_QUEUE_BACKEND`

### Contexto R-12 previo (Track A+B)

- Firma de estado: **GitHub `origin/main`**; implementación Track A+B `48cc255`; partida R-12 `f7a86cc`; premisas esenciales del ciclo R-12
- Alineación documental: README `v1.3.0 BETA`; tag `v1.3.0` → **`b778292`**
- Tests/scripts de verificación residuales (DEFAULT_PORTFOLIO, invariantes C–E, retry HTTP)
- Inventario `pending-delete` (sin purge) + higiene E8 + estudio UX comparativo (Track B **aprobado**, mesa 5 puertas)

## [1.3.0] — 2026-08-21

Endurecimiento del núcleo financiero y del gate CI apuntado por la **auditoría externa sobre v1.2.1** (R-11: C1–C5, C6, D1, D2 — todas cerradas) + deuda de datos/código residual cerrada tras el cierre de R-11. Documenta la política de cargo de custodia (C6) y deja `verify_ledger_balance_chain.py` en **EXIT 0 global**. Tag: `v1.3.0` sobre **`b778292`** (cierre documental; padre `deafa27` = fix test + verify EXIT 0). DEMO / paper; sin broker live.

### Post-R-11 (deuda §3 del traspaso, cierre de release)

- **Test** (`deafa27`) `test_execute_trade_con_fees_reconcilia` corregido: `ExecuteTrade.execute(...)` pide `idempotency_key` (R-10 F1 / R-11 C2); se añade `f"trade-{uuid4().hex[:8]}"` (deuda ajena a R-11, no regresión de gate). Batería coordinador: `test_m2` 7 passed 1 xfailed
- **Dato dev** (fuera de repo) cuenta de simulación huérfana `acc_broken_72ab7c2aa881` ("R8C broken", única de 111 que fallaba la cadena `balance_after` por +0.01 float legacy) **eliminada por path canónico** `close_account`→`delete_simulated_account` (coherente con R-10 F3-sim; **D6 prohíbe backfill** por eso no se reescribió `balance_after`) → `verify_ledger_balance_chain.py` **EXIT 0**

### R-11 — Endurecimiento post-v1.2.1 (C1–C6 + D1 + D2 cerradas a `main`)

- **C1** (`c3327c1`) Custodia **multi-periodo** (R-10.6): tabla `custody_obligations` PK `id` autoincremento + `UNIQUE(account_id, period)` + `created_at`/`updated_at`; migración Alembic `006_custody_obligations_period` (encadena sobre `005`); `upsert` reparado para **no sobrescribir** + `get_pending_by_account`/`get_by_account_period`; `ApplyCustodyFees`/`RunCustodyJob` liquidan primero el PENDING más antiguo antes del periodo nuevo
- **C2** (`17a1107`) **Idempotency_key end-to-end** (R-10.7): DTOs `DepositCashDto`/`WithdrawCashDto`/`TradeRequestDto` con `str_strip_whitespace=True`, `min_length=16`, `max_length=128`; repo `execute_trade` con `idempotency_key: str` obligatoria + rechazo de `""`/whitespace; guard en `ConfirmRecommendationIntent` (uuid4 fallback)
- **C3** (`cda26e9`) **Precisión Decimal end-to-end** (R-10.8): en `ExecuteTrade.execute` `notional`/`cash_before`/`amount`/`trade_balance`/`fee_balance` en `Decimal`, `float` solo en el borde al invocar repo/ledger; invariante secuencial exacta
- **C4** (`157bb45`) `contract:check` **EXIT 0** (R-10.9, Opción A): regen acotada de `apps/web/api/openapi.json` — `idempotencyKey` con `minLength/maxLength` + `TaxProfileDto` con `minimum:0.0`; `schema.d.ts` sin cambio; el 409 sigue solo en runtime (handler global), no en OpenAPI (decisión Opción A)
- **C5** (`6762614`) **`mypy` == 0 en gate CI** (R-10.9): añadida `packages/py/application/src` al step Mypy de `.github/workflows/python-ci.yml`; limpiados **105 errores en 33 ficheros** de la capa application; semántica mínima en `ledger_repository` (`limit: int|None=50`), `market_indices`, `fetch_core_r_pnl_extra_rows` (guard numérico) y `scans.py` (fix de `TypeError` latente: `expected_last_daily_bar()` sin el `exchange` obligatorio; ahora por instrumento)
- **C6** (docs, 2026-08-21) Política de cargo de custodia **`custody_charge_source = DEFAULT_PORTFOLIO`** documentada en ADR 026: la custodia es obligación de cuenta (importe sobre **equity agregado**) pero se cobra **exclusivamente desde la cartera seleccionada/default** (`scope.portfolio`, fallback `is_default`); sin transferencia implícita entre carteras — **solo documenta la regla, sin cambio de comportamiento**
- **Batería global R-11** (verificada por el coordinador): mypy gate `344 files` EXIT 0 · mypy application `95 files` EXIT 0 · ruff 0 · pytest application+market `388` · pytest api-python offline `84`
- **D2** (`db95709`, con C6) **Cierre documental**: docstrings aditivos en `ApplyCustodyFees.execute`/`ExecuteTrade.execute` (accounts.py, 14 ins, 0 lógica) · estado documental en PROJECT_STATE/backlog/index/plan/ADR 026/CHANGELOG
- **D1** (`870fb21`) **Limpieza transversal E8**: `custody_obligation_repository.get_by_account` + `get_by_account_period` (0 callers producción; el segundo nunca se cableó a `ApplyCustodyFees`/`RunCustodyJob`) quitados del repo y de fakes de test · se mantienen `get_pending_by_account`/`upsert` · **sin tocar ítems RIESGO ALTO** · batería D1: ruff 0 · mypy repo gate 0 · pytest custodia 7 · pytest application 279

## [1.2.1] — 2026-08-21

Correcciones de la **auditoría externa post‑v1.2.0** (R-10, F1–F5). Refuerza el núcleo financiero detectado en la pasada: `balance_after` secuencial, custodia con obligación pendiente y fuera del GET, DTOs estrictos, idempotencia exacta y `idempotency_key` obligatoria. DEMO / paper; sin broker live.

### R-10 — Correcciones de la auditoría externa (cerrada, F1–F5)

- **F1** `idempotency_key` **obligatoria** en deposit/withdraw/trade (422 si falta) + contrato/regen OpenAPI y ajuste de consumidores web
- **F2a** `TaxProfileDto` estricto (Pydantic fail-fast 422): `ge=0`, `allow_inf_nan=False`, `fiscal_year_start_month ∈ [1,12]`
- **F2b** Comparación idempotente **exacta normalizada a `Numeric(18,6)`** (eliminada la tolerancia de `0.01`)
- **F3** `balance_after` de trade+fee **secuencial por fila** (cash FINAL ya no en ambas), sin backfill (forward-only)
- **F4a** Custodia **Opción B con obligación pendiente** (tabla `custody_obligation`, `PENDING`/`APPLIED`, ADR 026, migración `005`): si `cash < fee` no descuenta ni marca DONE — registra `PENDING` y cobra el total cuando haya saldo
- **F4b** Custodia **fuera del GET** → job periódico `RunCustodyJob` (scheduler/worker); `GetAccountSummary`/`GetTaxReport` quedan **100% de solo lectura** (desfase de saldo pre‑custodia aceptado mientras corre el job). **Reabre `M-4/T-M4`** (job de custodia dedicado)
- **F5** Cierre: docs de estado (backlog, PROJECT_STATE, engineering-index, plan-r10) + CHANGELOG `[1.2.1]` + limpieza E8 inventariada

### Pendientes de decisión (no bloquean cierre)

- Contrato F2/F4: exponer el 409 + DTOs estrictos en OpenAPI (`contract:gen`) — pendiente
- `pending-delete` riesgo alto (no tocar hasta `purge storage`) · **R-8C.2 scheduler-vs-worker** · gobernanza IA
- **`M-4/T-M4` REACTIVADO y CERRADO por R-10 F4b** (`e12a125`) — la custodia ya es un job dedicado, no muta en GET

### Operativo (FUERA de repo)

- GitHub secret scanning · `TRUSTED_PROXIES` prod · registro BD `BP/.L`→`BP.L` · limpiar `logs/dev`

## [1.2.0] — 2026-08-20

Refactorización y corrección R-7 / R-8 / R-9 completadas (hardening financiero + limpieza + contrato). DEMO / paper; sin broker live.

### R-9 — Núcleo financiero determinista (cerrada, F1–F8)

- **F1** Idempotencia deposit/withdraw aislada por cuenta + `type` (align lookup ↔ UNIQUE por-cuenta)
- **F2** 409 `IDEMPOTENCY_KEY_REUSED` ante `idempotency_key` reutilizada con payload distinto (sin migración)
- **F3** Carrera de custodia idempotente → nunca 500 en contienda (UNIQUE + savepoint + detección de violación)
- **F4** DTOs financieros estrictos (Pydantic fail-fast 422): `ge/gt` + `allow_inf_nan=False` en `CommissionProfileDto` / `CreateInvestmentAccountDto`
- **F5** Sesión con **epoch UTC** (`time.time()`) en vez de `time.monotonic()` (portable multi-host)
- **F6** `balance_after` documentado como **postcondición de app** (no constraint DB) + corrección de docs
- **F7** Suite de **concurrencia/invariantes** en PG real (`test_concurrency_scenarios.py`) + verifiers `scripts/verify/`
- **F8** Limpieza transversal E8: código/aliases muertos en Python + web + shared (pending-delete riesgo alto intacto)
- **F9 (V2)** — arquitectura Python + puente `legacy_portfolio_id`: **DIFERIDA** (requiere ADR + decisión explícita)

### R-7 — Deuda de dinero real (cerrada)

- Doble cargo de custodia en GET concurrentes · deposit/withdraw idempotentes · claim AUTO no quemado
- Ledger con UNIQUE `(account_id, reference_type, reference_id, type)` · reconciliación cash↔ledger · cost-basis FIFO/avg con fee · margen real · max drawdown high-water-mark · `transfer_cash` muerto eliminado · trade+fee idempotente en AUTO execute/confirm · guard FIFO qty==0 + observabilidad PnL CORE-R · `total_unrealized_gain` fail-closed

### R-8 — Prevención de riesgo + contrato (cerrada; incluida en v1.1.0)

- Sesión HttpOnly firmada + logout · rate-limit login/status · invariante `balance_after` por grupo atómico · limpieza transversal baja (R-8D) · fidelidad wire DTOs shared (R-8B.3) · CONTRACT-STALE resuelto (`openapi.json`+`schema.d.ts` regenerados)

### Pendientes de decisión (no bloquean cierre)

- Contrato F2/F4: exponer el 409 + DTOs estrictos en OpenAPI (`contract:gen`) — pendiente
- `pending-delete` riesgo alto (no tocar hasta `purge storage`) · R-8C.2 scheduler-vs-worker · M-4/T-M4 (job dedicado custodia) · gobernanza IA

### Operativo (FUERA de repo)

- GitHub secret scanning · `TRUSTED_PROXIES` prod · registro BD `BP/.L`→`BP.L` · limpiar `logs/dev`

## [1.1.0] — 2026-08-20

Integridad R-7/R-8 y fidelidad de contrato. DEMO / paper; sin broker live.

### Seguridad / sesión (R-8B)

- Cookie de sesión **HttpOnly firmada** + logout + endpoint `authenticated`
- Rate-limit en login/status (R-8B.1)
- Sesión vulnerable a reutilización multi-host corregida (preludio de epoch en R-9.5)

### Robustez financiera (R-7)

- `A-1/A-3` custodia: mutex `claim_custody_charge` + release · `A-2` deposit/withdraw idempotentes por `idempotency_key`
- `L-M3/M-5` ledger UNIQUE por-cuenta+type · `M-1` fallback mark-to-cost · `M-2` `sum_cash_amounts` rest con ledger · `M-3` cost-basis con fee · `M-6` margen real · `M-4/T-M5` fees de custodia fuera de `fees_paid_total` · `M-7` dedup verificación por UNIQUE · `B-1` max drawdown high-water-mark · `B-3` `transfer_cash` eliminado · `B-4` trade+fee idempotente AUTO/confirm · `B-5` guard FIFO qty==0 + obs. PnL CORE-R · `B-2` `total_unrealized_gain` fail-closed
- Invariante `balance_after` por grupo atómico (R-8C) · bootstrap advisory-lock · fidelidad wire DTOs (R-8B.3, fases A–D) · CONTRACT-STALE resuelto

## [Unreleased] — stage 2026-08-06

### Listas / Visualizados

- **Visualizados** = espejo de pestañas abiertas (separado de **Estudio** API)
- Quitar selección cierra tabs (sin resucitar por autosave) · **Por IO** ordena por Índice Operativo
- Columnas opcionales IO/TA/FA/★/Postura · sort por columna (tabs siguen el orden)
- Foco buscar/pestaña: lista **Cartera → Estudio → resto** + scroll bajo cabecera sticky
- Docs: `visualizados-list-ux-2026-08-06.md` · handoff `session-handoff-2026-08-06-visualizados-list-ux.md`

### Arranque (perf)

- Windows: liberar puertos con `netstat` (sin PowerShell Get-NetTCPConnection)
- `GET /api/lists/memberships` batch · sync catálogo con TTL 60s en `GET /lists`
- Monitor / CORE-R: batch `instrument-strategy-tops/query` (menos N+1 al pintar Trading)
- CORE-R shell: primer tick + hydrate diferidos (~1.5–4 s / idle) tras el paint

### Estudio / Operativa (ADR-024 + UI procesos)

- Universo **Estudio** API · Supervisión ON · cadencias Vigilia / Frescura / Redescubrimiento
- UI: subtítulo procesos bajo el nombre · botones **Actualizar** / **Redescubrir** (barra inferior) · chips cadencia V·F·R en banner · sellos locales
- Manual/SEMI/AUTO en barra de estado (`OPERATIVA: …`) → Cuentas · Config (fuera del panel por valor)
- Docs: `docs/engineering/estudio-process-status-ui-2026-08-06.md` · handoff `session-handoff-2026-08-06-estudio-process-ui.md` · HELP sync
- GitHub: [jvelasca/Bolsa_V1](https://github.com/jvelasca/Bolsa_V1) · PR stage [#29](https://github.com/jvelasca/Bolsa_V1/pull/29)

## [1.0.0] — 2026-08-01

Primera release empaquetada (**BETA1 → GitHub V1**). DEMO / paper; sin broker live.

### Producto

- Embudo Backtesting: Coach ★ local · Lab AT · Lista AUTO (frescura v1.3) · Finalistas
- **CORE-P** perfil ↔ Coach/Lab (gate, techo DD, soft-bias espacio, E2E smoke/ASGI)
- **CORE-B** v0.2 memoria Lab (meseta → espacio · `resolveDefaultLabFamily`)
- **CORE-R** v1.8 reevaluación (Monitor, cola, narración; cron local)
- **DÍA D** v0.11 simulación as-of + Evidence (fullBleed no se persiste)
- Análisis del valor / FA·FIE · Tarjeta CAPM footnote · Composite liquidez v1.1
- Trading supervisado F3 (Decision Engine); paper auto dry-run (execute off-by-default)
- Ayuda / trackers sincronizados (`HELP_CONTENT_AS_OF` 2026-08-01)

### Calidad

- `pnpm test:coach` · `test:coach:smoke` · `test:coach:api`
- `pnpm test:operativa` · `test:operativa:smoke`
- `pnpm test:fa`

### Congelado (no en V1)

- Belief UI · Lab Discovery P3–P9 · `PAPER_D_EXECUTE` · CORE-R multi-dispositivo · broker live

### Notas

- Stack: React/Vite + FastAPI + PostgreSQL
- Requiere Node ≥20, pnpm ≥10, Python ≥3.11, Docker Desktop
