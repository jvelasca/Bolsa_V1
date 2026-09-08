# Traspaso de relevo — E2 V2.14 (P2-01): drift durable de órdenes → incidente `live_drift`

Fecha: 2026-09-08 · Rama `v2-14-financial-execution` · Repo `C:/Users/josea/Documents/Informatica/Typescript/Bolsa_V1`

> Continúa E2 el corte `2942fec1` (E2-PARTIAL dedup OPEN). **E2 NO está cerrado**:
> falta P1-02 (reconcile de posición LR-1 al tick de fondo) y el test PG 2-sesión
> real de la batería C1. Este traspaso documenta solo el trozo P2-01 que YA quedó
> verificado y committeado.

---

## RESULTADO P2-01 — writable durable de drift de órdenes (H7) → incidente `live_drift`

Contexto: el poll del recovery worker (`_reconcile_open_orders`, H7) reconciliaba
`live_orders` vs broker-truth y **solo logueaba** el `LiveOrderDrift`; nada se
persistía. Este trozo convierte el drift **accionable** en incidente durable
`live_drift` por cuenta (DEX-3), bajo un gate explícito.

### Decisiones (confirmadas operativamente)

1. **Strict kinds** (solo drift confirmado por broker abre incidente):
   `cancel_broker_side` (el venue confirmó cancel tras nuestras espaldas),
   `fill_unseen` (el venue reporta un fill que la máquina aún no ve),
   `state_mismatch`. **`query_unavailable` (el bridge no contestó, transitorio) NO
   abre incidente** → evita vetos de apertura falsos por timeouts.
2. **Un OPEN por cuenta** y kind (`live_drift`): se reusa la semántica
   `get_active`/`put` de `PostgresOperationalIncidentStore` (dedup 1-por-(account,
   kind) del P2-2/`2942fec1`). Replay no duplica ni sobrescribe el snapshot.
3. **Gate bajo go** fail-closed: env `LIVE_LIVE_DRIFT_DURABLE_WRITER_ENABLED`
   (default OFF) → el wiring **no cambia el runtime de V2.13** (sigue log-only)
   hasta que el operador lo habilite.
4. **No auto-heal**: nunca cierra/muta libros/máquina; la cadena
   review→resolve→clear la hace el operador (igual DEX-3).

### Archivos

- NUEVO `packages/py/application/src/bolsa_application/order_live_drift_incident.py`
  — decisión `drift_is_actionable`, agregador `actionable_accounts`, gate
  `live_drift_durable_writer_enabled()`, `publish_order_live_drifts(report, holder)`.
- NUEVO `packages/py/application/tests/test_order_live_drift_incident.py` — 7 tests.
- MOD `apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py` —
  `_drift_incident_holder(session)` (PG store solo si gate ON) + `_reconcile_open_orders`
  acepta `incident_holder` opcional y publica bajo go.

### Verificación

- ruff 0 (check) · ruff format 0 (check) sobre los 3 ficheros.
- pytest 7 passed (nuevos) + 25 passed (suite adyacente `test_live_order_recovery_worker`,
  `test_dex3_operational_incident`, `test_live_order_machine_reconcile`).

## Remanente honesto (E2 NO cerrado)

1. **P1-02 — reconcile POSICIÓN continuo en TICK (NUEVO commit)**: a diferencia del
   corte P2-01, este traspaso lo **entrega a nivel lógica+gate**. El detector LR-1
   ya existía pero solo corría en el path HTTP de apertura; se ha añadido que el
   recovery worker lo ejecute cada tick bajo el MISMO go
   (`LIVE_LIVE_DRIFT_DURABLE_WRITER_ENABLED`) y venue efectivo `live`. Legibilidad:
   `packages/py/application/src/bolsa_application/reconcile_live_positions.py`
   (`reconcile_and_open_position_incidents` + `SyncOpeningIncidentsOpener`) con
   tests (`test_reconcile_live_positions.py`, 5), y wiring en
   `live_order_recovery_worker._reconcile_live_positions_once` + gate
   `_live_position_reconcile_active` (+2 tests). **Verificado a nivel lógica/gate/
   imports (ruff + pytest); el path DB real (PG) NO se ha ejecutado (C1 exige su
   propio go la batería sobre PostgreSQL real)**.
2. **Test PG 2-sesión dedup OPEN determinista real** sobre PostgreSQL en C1 (el
   presente se probó en stub de sesión; C1 requiere PG real con su go).
3. **C1**: aplicar migración 022 al PG compartido + batería multi-worker (incl. este
   P1-02 sobre PG real) + Release-tag CI (solo con go del operador y observando
   `conclusion=success`).

FIN DEL TRASPASO P2-01 + P1-02-lógica (E2 sigue PARTIAL → pendiente C1)

---

## ADDENDO C1 (2026-09-08) — batería real-PG VERDE sobre PostgreSQL (E2 ya no PARTIAL en PG)

Bajo `go` del operador se ejecutó la batería de PostgreSQL **real** (no stub) del E2.
Nuevo test durable: `apps/api-python/tests/test_e2_v2_14_incident_dedup_pg.py`.

### Qué se validó contra PostgreSQL real (head `022_live_orders_exec`)

1. **Dedup de OPEN multi-worker real (es el test PG 2-sesión que pedía C1)**:
   dos sesiones concurrentes (`asyncio.gather`) abren el mismo
   `(account_id, kind='live_drift')` vía `publish_order_live_drifts` → materializan
   **exactamente 1 fila OPEN** (quien pierde la carrera parcial-unique deduplica hacia
   el winner; `IntegrityError`→rollback→`get_active`; sin 2º OPEN, sin auto-heal).
2. **query_unavailable NO abre** incidente (strict kinds) sobre la BD real.
3. **P1-02/LR-1 durable**: `sync_opening_incidents` ante LR-1 `unavailable` abre
   `live_unavailable`; DOS pasadas consecutivas ⇒ 1 OPEN (idempotente por `(account,kind)`).
4. **CHECKs financieros 021 vigentes bajo 022**: insert deliberado `filled=120 >
quantity=100`/`remaining=-20` es rechazado por CONSTRAINT con IntegrityError y la
   fila NO queda materializada (2ª línea de defensa de BD intacta).

### Resultado

```
4 passed in ~0.9s   (apps/api-python/tests/test_e2_v2_14_incident_dedup_pg.py)
14 passed           (junto a test_live_order_recovery_worker.py, sin regresión)
```

### Aislamiento (no se tocó la shared)

- Migración 001→022 aplicada en **`bolsa_c1_scratch`** (BD dedicada creada ad-hoc),
  apuntando `DATABASE_URL` ahí. `bolsa_v1` (shared, ya estaba en 022 previamente)
  **no** fue migrada por esta faena ni tiene filas suyas.
- Tras la batería: scratch limpia (0 filas residuales de las cuentas uuid-sufijadas).

### Cómo re-correr

```
cd apps/api-python
$env:DATABASE_URL='postgresql+psycopg://bolsa:bolsa_dev@localhost:5432/bolsa_c1_scratch'
$env:E2_PG_REQUIRED='1'     # fail hard si la BD no está en head 022
uv run pytest tests/test_e2_v2_14_incident_dedup_pg.py -v
```

---

## STAMP C1 Release-tag (2026-09-08) — Release-tag CI `conclusion=success` REAL

Certificación auténtica de V2.14 obtenida empujando el tag Release real y leyendo
el resultado de GitHub Actions (disciplina Release-tag CI honesta: GREEN solo con
`conclusion=success` observado, nunca documental).

- **Rama en origin:** `v2-14-financial-execution` → `78dd3f9a`
- **Tag Release:** `v2.14-beta` → `78dd3f9a` (movido con el fix de mypy)
- **Run:** `34208259186` · ref `refs/tags/v2.14-beta` · head `78dd3f9a`
- **Status artifact (certify job):** `status: "GREEN"` — jobs:
  `security`=success, `shared`=success, `spine`=success, `frontend`=success,
  `python`=success (ruff+import-linter+mypy+pytest offline), `playwright-mock`
  =success, `lifecycle-pg`=success (alembic upgrade head → 022 + battery PG real).
  (`playwright-integrated` es opt-in por dispatch; no es `needs` de certify.)

Primer run (`34207066169`) falló `python→Mypy` (3 errores), corregidos en `78dd3f9a`
(no-any-return en `_non_empty`, unused-ignore, attr-defined `on_conflict_do_nothing`).
Segundo run GREEN confirmado por el artifact
`actions/artifacts/release-tag-ci-summary.json`.

V2.14 queda auditable en GitHub: rama `v2-14-financial-execution` y tag `v2.14-beta`
sobre el corte completo (E1..E2-full + C1 real-PG).
