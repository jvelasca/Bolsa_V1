# RESPUESTA Y CERTIFICACIÓN — auditoría externa V2.14.2 (2026-09-08)

> **Padre:** [engineering-index](./engineering-index-2026-08-03.md) (hijo de la cadena V2.14.2: [audit-interno-lectura-v2-14](./audit-interno-lectura-v2-14-2026-09-08.md) · [relevo V2.14.2](./traspaso-relevo-tag-v2-14-2-beta-2026-09-08.md) · [relevo V2.14.1](./traspaso-relevo-tag-v2-14-1-beta-2026-09-08.md)).
> **Tip / estado auditado:** `main` @ [`2a98886c`](https://github.com/jvelasca/Bolsa_V1/commit/2a98886c492cb3c855b09a7f219e58510d152100) == tag `v2.14.2-beta` · package `1.43.2-beta` · Alembic `023_ohlcv_bars_unique_reconcile`.
> **Método:** respuesta a la auditoría externa V2.14.2 **sobre el código real** (no sobre documentación antigua), verificada por lectura **y** por evidencia real de GitHub CI (vía `gh`), observando el run, no afirmando.
> **Fecha:** 2026-09-08. **Alcance del presente documento:** certificación + triage. **Cero cambios de código** (solo docs).

---

## 0. Resumen ejecutivo (qué cambia tras verificar GitHub)

La auditoría externa V2.14.2 es de altísima calidad y conceptualmente correcta en casi todo. Pero un pilar de sus conclusiones — el **P1-02 (CI V2.14.2 no certificada por tag)** — es un **falso positivo** derivado de no haber podido acceder al estado real de GitHub.

Al verificar con `gh`, el cuadro real es:

- El tag **`v2.14.2-beta` → `2a98886c`** **sí existe** en `origin` (es exactamente HEAD de `main`).
- El **Release-tag CI** de ese tag/commit **corrió GREEN**: run `34224783087` (2026-09-08), `conclusion=success`, con el job agregador **`certify` en success**.
- Por tanto **V2.14.2 sí está certificada GREEN de forma real**, y NO se necesita un ciclo nuevo de tag/release para afirmarlo.

Impacto en las dos prioridades que el auditor marcó (sección "Lo que yo haría"):

| Prioridad sugerida por el auditor                                     | Veredicto post-verificación                                                                                                                                                   |
| --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Cerrar account-less isolation (P1-01)                              | **Deuda real, no urgente hoy.** Condición single-owner bootstrap; solo explotable con ≥2º owner real. Se documenta para V2.15 (ver §4.1). Sin commit de código en esta faena. |
| 2. Certificar realmente V2.14.2 (crear tag y ejecutar Release-tag CI) | **Ya está hecho.** Tag existe y Release-tag CI corrió GREEN (run `34224783087`). No hay que re-certificar. Ver §1.                                                            |

El resto de la valoración del auditor (P2s de endurecimiento y la lista "no P0 demostrado") se mantiene y se tria en §3–§4.

---

## 1. Certificación Release-tag CI — V2.14.2 GREEN (respuesta directa al P1-02)

### 1.1 Evidencia real (GitHub Actions)

Run: **[Release tag CI `34224783087`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34224783087)** — disparado por `push` del tag `v2.14.2-beta` (evento `push`, rama/tag `v2.14.2-beta`), completado `2026-09-08T12:12:25Z`, `conclusion=success`.

| Job (`name`)                                          | `conclusion`                    |
| ----------------------------------------------------- | ------------------------------- |
| security (gitleaks)                                   | success                         |
| shared (build/typecheck/test)                         | success                         |
| decision-spine                                        | success                         |
| frontend (typecheck/lint/test/build + contract:check) | success                         |
| playwright (mock E2E)                                 | success                         |
| python (ruff/imports/mypy/pytest offline)             | success                         |
| lifecycle-pg (Alembic + auth + golden restart)        | success                         |
| **certify (aggregate + artifact)**                    | success                         |
| playwright (integrated E2E, opt-in)                   | **skipped** (opt-in por diseño) |

Fuentes: `git ls-remote --tags origin` devuelve `2a98886c…  refs/tags/v2.14.2-beta`; `gh run view 34224783087 --json jobs,conclusion` devuelve el conjunto de arriba. Job `certify` = paso "Fail if any required job failed" (skipped, porque ningún job obligatorio falló) + "Write summary artifact" success → **GREEN**.

### 1.2 Nota honesta sobre el único job no-ejecutado

`playwright (integrated E2E, opt-in)` aparece `skipped` porque dispara solo bajo `workflow_dispatch && run_e2e_integration` (ver `.github/workflows/release-tag-ci.yml`). Es **comportamiento esperado del workflow**, no un fallo ni una excepción a la certificación. No forma parte del gate de tag por defecto.

### 1.3 Verificación de que el commit 2a98886c es el definitivo

`main` y el tag apuntan al mismo commit y es el que contiene el último arreglo:

```
V2.14.2 C1: fix ruff I001 (import order, config pyproject.toml) hallados por Python CI quality    (2a98886c)
V2.14.2 elevation to main + bump 1.43.2-beta                                                       (58cc2e85)
V2.14.2 A1 cierre: account-isolation extendida a rutas de LECTURA/estudio + tests                     (5b1fa809)
```

El Release-tag CI `34224783087` pertenece exactamente a `2a98886c` (titulo "V2.14.2 C1: fix ruff I001 …"). La disciplina interna "observar el run real antes de afirmar GREEN" está cumplida.

**Conclusión §1:** P1-02 resuelto por evidencia real. V2.14.2 **sí** está Release-tag-CI GREEN.

---

## 2. Triage por secciones del informe (lo que el auditor da por bueno vs lo que hay que mirar)

### 2.1 CONFIRMADO-correcto (el auditor acierta; el repo respalda; NO tocar)

| Item auditor                                                               | Evidencia verificada                                                                                                                                                                                                                     | Estado                               |
| -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| OHLCV → schema `023` (P1 que ya era el mejor arreglo)                      | [relevo V2.14.1](./traspaso-relevo-tag-v2-14-1-beta-2026-09-08.md) + `audit-interno-lectura` adenda: migración `023_ohlcv_bars_unique_reconcile` + `UniqueConstraint` en `OhlcvBarRow`. El contrato esquema↔`ON CONFLICT` ya no diverge. | **Cerrado.** No rehacer.             |
| UNKNOWN → NO re-POST + recovery con `SKIP LOCKED`/lease                    | `live_order.py` (`forbid_repost_from_unknown`, terminales, `filled > quantity`) · `PostgresLiveOrderStore.claim_unknown_batch` (`SELECT FOR UPDATE SKIP LOCKED`, `recovery_claimed_at`).                                                 | **Cerrado / congelado.** No rehacer. |
| ExecutionEvent fail-closed (`permit=False` por defecto)                    | Cadena confirmada en `audit-interno-lectura` §3: la materialización financiera exige consentimiento explícito.                                                                                                                           | **Cerrado.** No rehacer.             |
| OperationalIncident dedup (partial-UNIQUE + rollback + `get_active`)       | Batería real-PG V2.14 ya probó la carrera con 2 sesiones.                                                                                                                                                                                | **Cerrado.** No rehacer.             |
| Reconciliación continua sin auto-heal (DRIFT → INCIDENT → VETO → operador) | Confirmado en `audit-interno-lectura`.                                                                                                                                                                                                   | **Cerrado.** No rehacer.             |
| FSM live (estados, terminales, no `UNKNOWN→SUBMIT`)                        | `live_order.py` verificado.                                                                                                                                                                                                              | **Cerrado.** No rehacer.             |
| Paper Desk (dry_run / gates separados)                                     | Confirmado.                                                                                                                                                                                                                              | **Cerrado.** No rehacer.             |

### 2.2 FALSO POSITIVO (este documento es su corrección)

**P1-02 — "CI V2.14.2 no certificado por tag".** Refutado en §1: el tag existe y el Release-tag CI `34224783087` corrió GREEN con `certify` en success. El auditor razonó sobre la ausencia de un run que en realidad existe; probablemente por no disponer del acceso GitHub que ahora sí tenemos.

### 2.3 MENOR verificable (no afecta a runtime, sí a determinismo)

**README línea 7** todavía dice `tip main → da181b76/código V2.14.1`, cuando el HEAD real es `2a98886c` (V2.14.2). Es la misma advertencia cosmética ya constatada en el relevo V2.14.1 (la documentación apuntaba un SHA dos commits por debajo del HEAD de entonces). `docs/CURRENT_SYSTEM.md` sí está a V2.14.2. Ver §5 (decisión: no commit dedicado).

### 2.4 Confirmación de lo que el auditor NO marca y conviene mantener

`claim_expires_at` es deuda real (ver §4.4) — coincide con el auditor. El resto de su "mapa de riesgos" P2 (liveness/readiness, provenance obligatoria, T1/T2, FSM declarativa, matriz de cobertura CI) son deuda de endurecimiento legítima y se concentran en §4.

---

## 3. Revisión de la valoración numérica sugerida (≈ 8.8/10)

La valoración agregada del auditor es razonable y, con la corrección de P1-02, **mejora** ligeramente en CI/CD (pasaría de 9.0 con incertidumbre a 9.0+ certificado real sin asterisco).

| Área                       | Auditor | Comentario tras verificar                                                                             |
| -------------------------- | ------- | ----------------------------------------------------------------------------------------------------- |
| CI/CD                      | 9.0/10  | **Sube/solidifica**: Release-tag CI `34224783087` GREEN real (certify success).                       |
| Preparación LIVE real      | 6.5/10  | Se mantiene: sigue sin capital, `LIVE_EXECUTION_UNLOCKED` off, XTB cancel PARKED. Correcto para Beta. |
| Documentación / provenance | 7.5/10  | Se mantiene con el único matiz README tip (§5).                                                       |

Ninguna de las áreas "muy buenas" del auditor (FSM · live_orders · ExecutionEvent · ledger · outbox · reconciliación · capas · dedup) cambia: siguen siendo exactamente lo que no hay que tocar agresivamente.

---

## 4. Catálogo de deuda real para V2.15 (SOLO ENLISTADO — sin código en esta faena)

> Marcas por convención del [audit-interno-lectura-v2-14](./audit-interno-lectura-v2-14-2026-09-08.md): `[lectura]` = se cierra por lectura · `[runtime]` = requiere PG real / 2 workers / broker real.

### 4.1 P1-01 (heredado del auditor) — account-less → consulta global cuando `account_id=None` — `[lectura]` · deuda no urgente

Confirmado en el código real:

- `require_owned_account_if_present` ([`dependencies.py:400-412`](./../api-python/src/bolsa_api/api/dependencies.py)) y `require_account_header_access` (`:388-397`) hacen `if account_id is None: return None` y dejan pasar, sin error ni filtro downstream.
- Los repos de LECTURA/estudio solo filtran `if account_id: stmt = stmt.where(DecisionSessionRow.account_id == account_id)` (p. ej. [`cognitive_repository.py:148-158`](./../py/infrastructure/src/bolsa_infrastructure/database/repositories/cognitive_repository.py) para decision-sessions). `account_id=None` ⇒ SELECT sin filtro de cuenta (todas las filas de todos los owners). Mismo patrón en memory/trials/edge-reports/effectiveness; opiniones diarias/telemetría ni siquiera filtran por cuenta.
- Las tablas cognitivas tienen `account_id` **nullable** (DecisionSessionRow/MemoryRow/TrialRecordRow/EdgeReportRow/ConfidenceStateRow/JournalEntryRow).

**Por qué NO urge (decisión tomada):** el sistema sigue siendo **single-owner bootstrap** (`user_bootstrap.py` crea un solo owner, `APP_OWNER_ID` por defecto `"app"`; sin registro público). El `user_id` del account iguala al principal (F7c). Con un único owner real, `account_id=None` no expone a un segundo owner porque no existe. El leakage cross-account solo sería explotable con ≥2º owner real → **`[runtime-aislamiento]`**.

**Decisión para V2.15:** no introducir enum `GLOBAL/ACCOUNT/ACCOUNT_OPTIONAL` ni romper los flujos demo/global FE. Documentar la deuda (este apartado) y resolverla **junto con el primer soporte multi-owner real**, no antes. El "account-scoping centralizado en repos" propuesto por el auditor encaja en ese momento, no ahora.

**Rutas más afectadas** (catálogo para el V2.15): live-route `GET /api/ai/decision-sessions` y análogos (`ai_governance.py`) + `LoadEffectivenessFromStore` (`cognitive_persistence.py`) + opiniones diarias/telemetría/EOD (`instrument_daily_opinion_repository.py`, `daily_opinion_telemetry.py`).

### 4.2 Health: separar Liveness / Readiness — `[lectura]` · P2

Confirmado: hay un único `GET /api/health` y el estado global es binario `ok`/`degraded` = `(not db_ok) or any(c.status == "error")` ([`health.py:252-258`](./../api-python/src/bolsa_api/api/v1/routes/health.py)). Un componente `degraded` (redis/worker_arq/auth/smtp) **no** tumba el global; tampoco existe `/live` ni `/ready`. Proponemos para V2.15 `[runtime]` readiness operacional (DB + Alembic head + worker heartbeat + risk + bridge/recon si LIVE + unlock policy), no solo liveness HTTP.

### 4.3 Provenance: `PRODUCT_VERSION` / `API_CONTRACT_VERSION` obligatorias en release — `[lectura]` · P2

Confirmado: en [`provenance.py`](./../api-python/src/bolsa_api/provenance.py), `product = _env("PRODUCT_VERSION")` y `api_contract = _env("API_CONTRACT_VERSION")` pueden ser `None` (mejor ausente que inventado, por diseño); `package`, `git_sha` (fallback `git rev-parse`), `schema_revision` (Alembic head) sí se auto-descubren. Para release industrial: que el build inyecte estas env y `/health` identifique el binario sin ambigüedad.

### 4.4 live_orders: columnas muertas `claim_expires_at` / `attempt_count` / `last_error` — `[lectura]` · P2 (confirmado)

Verificado: la migración `022_live_orders_exec` añade `attempt_count`/`last_error`/`claim_expires_at`, pero **no hay lector ni escritor** en la ruta live. El reclaim real usa solo `recovery_worker_id` + `recovery_claimed_at` + `updated_at` (`claim_unknown_batch`, [`live_order_store.py:570-599`](./../py/application/src/bolsa_application/live_order_store.py)); `live_order_to_row_fields`/`put` omiten esas tres columnas; único uso es un assert de esquema en `test_live_order_store_pg.py`. **No afecta** a la exclusividad actual (coincide con el auditor, M1). Opción V2.15 preferida del auditor: darles semántica única real de lease (claim_id/worker/claimed_at/expires_at/attempt/last_error), o eliminarlas — nunca la bicefalia DB-vs-mecanismo.

### 4.5 T1/T2 (plan/lifecycle) hardened — `[lectura]` · P2 (confirmado, y delimitado)

El FSM **live** está sano. La observación del auditor vive en dos módulos "plan", no en live-orders:

- `position_state.py::_advance_target_leg` (`:86-102`): un T1 `failed` puede saltar luego a `executed`; `pending → failed` retorna igual (silenciado).
- `domain/lifecycle/__init__.py`: `open → T1_EXECUTED` es legal sin `T1_TRIGGERED` previo; la validación de tiempos solo exige `after` si el evento previo **existe**.

No demostrable como explotable por las rutas LIVE actuales, pero en V2.15 conviene `TRIGGERED → EXECUTED` como invariante fuerte del lifecycle durable y vetar `failed → executed` en `_advance_target_leg`.

### 4.6 FSM declarativa + cobertura de transiciones — `[lectura]/[runtime]` · P2

Coincide con la observación interna P2 del audit-interno (`NON_TERMINAL_LIVE_STATUSES` se auto-deriva del grafo; literal nuevo sin arista quedaría auto-bloqueado). En V2.15: modelo declarativo común LiveOrder/PaperOrder/Position/Lifecycle + tests de cobertura total de transiciones + invariante transversal (diferencia deliberada Paper esté documentada).

### 4.7 Matriz de cobertura CI (no confundir "pytest pasó" con "todo probado") — `[lectura]` · P2

Confirmado que el job `python` offline excluye deliberadamente (via `--ignore`) `test_account_isolation.py`, `test_auth.py`, `test_health.py`, `test_workspaces.py`, `test_lifecycle_auth.py`, etc. Muchos reaparecen en `lifecycle-pg`, pero **`test_account_isolation.py` / `test_auth.py` / `test_health.py` / `test_workspaces.py` no corren en ningún job del tag-trigger**. Sugerencia del auditor (matriz Test→Offline/PG/E2E/Multi-worker) es una mejora de CI documental razonable para V2.15.

### 4.8 Baterías runtime/chaos para LIVE real — `[runtime]` (fuera de lectura; correcto el auditor)

El auditor estuvo acertado: NO es LIVE trading certificado. Faltan (solo listadas, coinciden con su punto 17): PG real multi-worker con SKIP LOCKED/ON CONFLICT/deadlocks; broker real (submit/timeout/partial/cancel/duplicate/out-of-order); reconciliación LOCAL≠BROKER en todas las combinaciones; crash recovery (DB commit→crash→restart→recovery); kill/unlock con `LIVE_EXECUTION_UNLOCKED=false`. Esto es, por definición, `[runtime]`.

---

## 5. README tip obsoleto (P2 cosmético) — decisión

Revisado: [README.md línea 7](../README.md) apunta `tip main → da181b76/código V2.14.1`, pero HEAD real es `2a98886c` (V2.14.2). Es la advertencia cosmética ya conocida y **no afecta a runtime**.

**Decisión de hoy** (heredada de V2.14.1 y coherente con la preferencia del usuario de no comitear retoques): **no crear un commit dedicado solo a ese retoque**. Se documenta aquí como deuda P2 estética; la próxima faena de docs que toque README re-apuntará el tip al SHA que sea entonces HEAD.

---

## 6. Guías "no tocar" heredadas (línea roja)

- El trabajo preexistente del worktree NO es de esta faena: `.md` de `docs/engineering/*`, `apps/web/e2e/*`, `playwright.config.ts`, `src/features/trading/lists-tab/*`, `open-instrument-in-trading.ts`, `packages/shared/src/cognitive/live-order.ts`. No usar `git add -A`.
- No crear commits de código, ni subir ramas/tags, ni inventar valoraciones "GREEN" sin run real. Esta faena es **solo documentación**.

---

FIN DEL DOCUMENTO — Respuesta y certificación V2.14.2 preparada tras verificar GitHub real (tag + run `34224783087` GREEN). P1-02 resuelto como falso positivo; deuda real de endurecimiento catalogada para V2.15 sin tocar código.
