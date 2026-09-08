# Auditoría interna por LECTURA — V2.14 Financial Execution Core

> **Tip auditado:** `main` @ [`e76a1942`](https://github.com/jvelasca/Bolsa_V1/commit/e76a1942) (elevation V2.14 · 1.43.0-beta · Alembic `022_live_orders_exec`).
> **Método:** lectura / verificación estática (sin PostgreSQL, sin 2 workers, sin broker real). Reproducible en cualquier entorno.
> **Fecha:** 2026-09-08. **Autor:** auditoría interna de preparación previa al auditor externo.
> **Propósito:** este documento es el trabajo de _self-research_ que se contrastará con el plan del auditor externo (bloques A–I). Cada verificación se marca como `[lectura]` (cerrada aquí) o `[runtime]` (requiere PG real / 2 workers / broker — fuera de esta tanda).

Alcance cubierto: árboles/aplica en los 6 bloques pedidos por el auditor (capas, FSM, concurrencia/dedup, account-isolation, contrato API, UI-truth + test-coverage). No entra en el rendimiento del investigador: cada hallazgo lleva cita `fichero:línea`.

---

## Adenda 2026-09-08 (post-verificación runtime): schema-drift OHLCV causaba "histórico no disponible"

> Complemento honesto a este informe de LECTURA. Al seguir el síntoma real en la UI
> ("los activos no se ven / histórico no disponible"), la verificación **runtime** detectó
> una causa **de esquema** que la lectura no podía cerrar (marcada como `[runtime]`):
> `ohlcv_repository.upsert_bars` (cd451fea) usa `ON CONFLICT (instrument_id,timeframe,timestamp)`
> pero las migraciones Alembic no creaban ese índice único → el sync de mercado abortaba en
> runtime (`InvalidColumnReference`), la BD quedaba sin barras y la UI sin datos. **Remediado**:
> migración `023_ohlcv_bars_unique_reconcile` (+`UniqueConstraint` en `OhlcvBarRow`) y repoblado
> el histórico real (35 activos IBEX · 2021→hoy · freshness `current`). Guards real-PG y
> provenance/tests actualizados a head `023_ohlcv_bars_unique_reconcile`. Este hallazgo subraya
> que el contrato esquema↔repositorio debe cerrarse también **en runtime contra PG real**, no solo por lectura.

---

## Resumen ejecutivo

- **Sin hallazgo P0 demostrable por lectura.** La materialización financiera está **GATED** (`permit=False` por defecto, no materializa sin consentimiento); la dedup OPEN está anclada a un partial-UNIQUE en PG y a `SKIP LOCKED`+lease; la cadena Confirm→submit es secuencial y no encontré camino que salte VALIDATION/RISK/CONFIRM llamando al `submit` del adapter en una sola petición.
- **Hallazgo P1-P2 en aislamiento de cuenta — remediado en las vías de EJECUCIÓN (2026-09-08).** Un grupo de endpoints "operador/automación/IA" leía `account_id` de query/body **sin** `require_account_access`, con el dominio (`resolve_scope`) sin re-filtrar por owner. Ya se han aplicado los gates `require_account_access` a las 4 rutas que ejecutan (confirm / evaluate-exits / execute-auto / paper-desk cycle). **Residual**: las rutas de LECTURA/estudio (effectiveness, decision-sessions, decision-memory, trials, edge-reports, propose, daily-report, instrument_daily_opinions) siguen sin gate — solo explotable con ≥2º owner real (hoy single-owner bootstrap). Ver A1 en la tabla.
- **Áreas muy sólidas por lectura**: capas (import-linter 4/0), FSM live/paper/lifecycle, dedup/concurrencia, y contrato FE↔BE endurecido: incidents y submit-intents ya cuentan con G12/G13 en `contract-check.ts` (2026-09-08). Residual P2.6: fidelidad de optionality/value sigue sin gateare por diseño.
- **Límite de honestidad:** lo que no cierra por lectura se marca `[runtime]` y queda fuera (carreras cross-PID, comportamiento ON CONFLICT bajo contención alta, estado físico de la BD, reconciliaciones contra broker-truth real, doble-writer de cancelación).

---

## 1. Separación de capas — ✅ VERDE [lectura]

`uv run lint-imports --config packages/py/.importlinter` → **4 contratos KEPT, 0 broken** (540 ficheros, 2777 dependencias):

- Domain no importa infra/analytics/application ni SDKs LLM — KEPT.
- SDKs LLM solo vía `bolsa_ai` (Proxy First) — KEPT.
- `bolsa_ai` no entra en domain — KEPT.
- `analytics` y `market` independientes — KEPT.

Verificación del _wiring_ de la cadena de ejecución (que el compositor real inyecte los lookups de los gates):

- `apps/api-python/src/bolsa_api/api/dependencies.py:1461-1469` `get_confirm_intent_use_case` inyecta `portfolio_summary=get_portfolio_summary_use_case(session)` y `ohlcv=get_ohlcv_repository(session)` (además `broker_adapter=None` → lazy venue). Consumida por `POST /ai/intents/confirm` (`ai_governance.py:392-397`).
- `dependencies.py:768-772` `I1 POST /portfolio/trade` (`check_opening` en buys) también inyecta `portfolio_summary` + `ohlcv`.
- Conclusión: el llamado "riesgo por wiring" (que `risk_veto`/revalidación de precio queden mudos si el caller no inyecta `portfolio_summary`/`ohlcv`) **no se da en las vías productivas**. El constructor admite `None` (fail-open del wiring), así que es una observación de API defensiva, P3 — no P0.

---

## 2. FSM y transiciones — ✅ VERDE (con observaciones P2) [lectura]

**Live order** (`packages/py/analytics/src/bolsa_analytics/cognitive/live_order.py`) — sano:

- `UNKNOWN → {WORKING,REJECTED,FILLED,PARTIAL,CANCELLED,CANCEL_REQUESTED}`, **sin** arista hacia re-POST/submitting. `forbid_repost_from_unknown` presente.
- `can_transition_live_order` (`:177-179`) bloquea salir de terminal (`FILLED/REJECTED/CANCELLED`).
- `transition_live_order` (`:202-223`) recalculiza `remaining = quantity - filled`, rechaza `filled > quantity`, preserva `filled + remaining == quantity` (Decimal 6dp). `forbid_execute_trade_for_partial` (`:258-263`) impide ejecutar trade sobre `PARTIAL`.
- Observación P2 [`lectura`]: `NON_TERMINAL_LIVE_STATUSES` (`:92-96`) se deriva del grafo, por lo que un literal nuevo añadido al `LiveOrderStatus` sin añadirlo como clave del grafo quedaría **auto-bloqueado silenciosamente** (trampa de mantenimiento, no bug actual).

**Paper order** (`cognitive/paper_order.py`) — guardas de cantidad presentes; divergencia deliberada:

- `UNKNOWN → {ACK,PARTIAL,FILLED,REJECTED,CANCELLED,EXPIRED}` (`:69-73`) permite resolver `UNKNOWN` a cierres directamente **sin** consulta previa al "broker" (a diferencia de la política live/protege no-POST). Es la máquina PAPER (sin bróker real) → riesgo menor, pero es un desalineamiento intencional con la política live. P2.

**Position / T1-T2** (`cognitive/position_state.py`) — observación de máquina T1/T2:

- `_advance_target_leg` (`:86-102`) permite que un T1 `failed` salte después a `executed` (no vetado en banda), y silencia `pending → failed` (retorna igual sin error). Depende del caller para no hacerlo; rutas live no pasan por aquí (es estado T1/T2 de plan). P2 [`lectura`].

**Lifecycle durable T1/T2/trail/exit** (`packages/py/domain/src/bolsa_domain/lifecycle/__init__.py`) — sólido en qty, observación de secuencia:

- `open → T1_EXECUTED` es legal sin `T1_TRIGGERED` previo: `_validate_time` (`:672-684`) solo compara tiempos con eventos **ya existentes**, no obliga a que el TRIGGERED preceda. Cantidad protegida (POSITION_CLOSED usa `remaining_before` exacto, `:735-742`). `stop_worsens` (H2) correcto por lectura. P2 [`lectura`].

**Operational Incident** (`cognitive/operational_incident.py`) — correcto: `clear` solo si recon `clean`; `incident_blocks_opening`.

**Cadena de gates en `confirm_recommendation.py`** — secuencial y correcta [`lectura`]:

- Orden en `_run_trade_path`: Identity (identity contract / expired / orphan / precio) → `OpeningGate.allows_opening(risk_veto)` → `RiskGate.reject_reason(risk_signature)` → `ExitGate.semi_exit_permission` → recién `_run_submit_and_sync` → `submit`. verificación de capas en §1 confirma el wiring.
- `_run_submit_and_sync` (`:900-970`): `find_existing_fill → apply_idempotent_replay (no submit)` y `try_recover_in_flight (no submit)` cortan ANTES de un segundo submit. El submit durable pasa por `record_before_submit`. **El replay idempotente post-crash del `submit_intent` durable no se audita aquí: marcado `[runtime]`** (P1-gate de verificación, no hallazgo de bug por lectura).

---

## 3. Concurrencia / dedup / idempotencia — ✅ VERDE (huecos de diseño en terminal) [lectura]

- **Partial-UNIQUE incidentes activos**: `tables.py:1366-1372` `Index("operational_incidents_active_account_kind_idx", account_id, kind, unique=True, postgresql_where: status IN ('open','in_review','resolved'))`. `operational_incident_store.py:205-222` resuelve IntegrityError con `rollback` + `get_active` → dedup sin fabricar 2º OPEN.
- **Recovery fail-closed**: `live_order_store.py:558-599` `claim_unknown_batch` usa `with_for_update(skip_locked=True)` + lease por columnas `recovery_worker_id/claimed_at` (excluye claim frescos de cualquier worker hasta `stale_after_seconds`). Nunca re-POST.
- **Idempotencia financiera GATED**: `execution_event.py:142-170` `apply_fill_idempotent(store, ..., permit: bool = False)`: captura la traza (`execution_id` PK `ON CONFLICT DO NOTHING`), y **NO materializa** (Posición/Ledger) sin `permit=True`. Default fail-closed.
- **Huecos de diseño (no bugs por lectura)**:
  - El partial-UNIQUE de incidentes **no cubre `cleared`**: pueden coexistir N filas `cleared` del mismo `(account,kind)` + el `open` activo. Intencionado (histórico append-friendly), pero fuera de "1 fila por incidente". P2.
  - El catch de `IntegrityError` del `put` `get_active` solo read-checkea `_ACTIVE` (`open/in_review/resolved`); una colisión por re-abrir un incident **no activo** relanzaría (no deduplicaría). No alcanzable hoy (aperturas siempre crean `open`). P3.
  - `live_orders` upsert `ON CONFLICT DO UPDATE` (`live_order_store.py:519-528`) **no valida la FSM en BD** (last-write-wins). La validación vive en dominio antes del `put`. P2 defensivo. (Los tests `_pg` ya cubren check-constraint de `filled>quantity`: `test_e2_v2_14_incident_dedup_pg` reject.)
- **Tests real-PG presentes** (nombre `_pg`/`_e2`), que **solo** se ejecutan con `DATABASE_URL` en head 022; en CI offline se skippean: `test_e2_v2_14_incident_dedup_pg.py` (dos sesiones concurrentes → 1 OPEN), `test_live_order_recovery_concurrency_pg.py` (SKIP LOCKED determinista + 2 workers disjoint). Todo lo demás de contienda real queda `[runtime]`.

---

## 4. Account isolation / auth — 🟠 el único hallazgo medio-alto [lectura]

**Lo correcto (VERDE):**

- `require_account_access` (`dependencies.py:370-398`) → `get_account(account_id, owner_user_id=get_request_principal(...))`; 404 si no visible. Se aplica como `Depends` en `accounts.py` (summary/ledger/tax/operations/**incidents**/daily-ops), `portfolio.py`/`pending_orders.py` (header `X-Account-Id` vía `require_account_header_access`), `lifecycle.py` (modelo fuerte: `require_jwt_principal` sin fallback + `_assert_account_owned`).
- Legacy `user_id IS NULL` **nunca visible** (`account_repository.py:41-43`); no hay lista/comprobación a ciegas en los paths gateados.
- Inválida de pertenencia devuelve 404/403, nunca 500.

**El hallazgo (AMARILLO, provisional):**

- `_load_scope`/`resolve_scope` (`account_repository.py:109-119`) carga por `account_id` + `status=="active"` **sin filtrar owner** — la pertenencia depende por completo del gate HTTP.
- Grupo de endpoints que leen `account_id` de query/body **sin** `require_account_access`/`require_jwt_principal` y alcanzan `resolve_scope`/queries de cuenta:
  - `POST /ai/intents/confirm` — el endpoint que **puede ejecutar un trade live** (`ai_governance.py:388-404`; `use_case.execute(account_id=body.account_id, execute=body.execute)`).
  - `paper_desk.py` POST /cycle, GET /daily-report (resumen + `ledgerToday`+`tradesToday`+week de la cuenta).
  - `position_policies.py` `evaluate_position_exits(account_id, execute_trades)` (puede ejecutar trades; solo `PAPER_D_EXECUTE` env para no-dry).
  - `position_automation.py` `POST /execute-auto` (protect/exit).
  - `instrument_daily_opinions.py` auto-propose / eod-batch (incluye digest/email de la cuenta).
  - `risk.py` and `ai_governance` learning-summary.
- `require_role` (`roles.py:14`) existe pero **no se usa**: todo JWT válido alcanza esos endpoints; el aislamiento se apoya solo en `account.user_id == principal`.

**Clasificación:** provisional **P1** (no P0) porque hoy el modelo es **single-owner** (1 único principal real desde bootstrap `user.id == account.user_id == owner`), así que la vía cross-account **no es explotable con runtime actual** — pero es la anomalía estructural que un despliegue multi-owner convertiría en P0. No se puede demostrar cross-account con 2 owners reales por lectura → `[runtime-aislamiento]`. Acción propuesta: aplicar `require_account_access` a ese grupo de endpoints operator/auto/IA (o un resolver que inyecte owner distinto del principal) y convertir los incidents/submit-intents en centinelas del contrato (ver §5).

---

## 5. Contrato API — ✅ VERDE (con candidatos a endurecer) [lectura]

- El FE tipa HTTP desde el **generado** `apps/web/src/api/schema.d.ts`, pero la respuesta de conceptos críticos (incidents, submit-intents) se sobre-escribe con **tipos manuales** de `@bolsa/shared` (`api.ts:1804,1818`).
- **Gate de contratos** `apps/web/src/api/contract-check.ts` (G1..G11) garantiza igualdad de CLAVES con el OpenAPI para 11 centinelas (incl. `PositionDto` en G9). La **optionalidad/nullable no está gateada por diseño** (`contract-check.ts:18-19`).
- Comparación campo-a-campo (Python DTO ↔ TS manual ↔ `schema.d.ts`):
  - `OperationalIncidentV1` ↔ `OperationalIncidentDto` (`accounts.py:558`) → **coincide** en 12 campos; única divergencia: `snapshot` opcional en el dump vs requerido-null en el manual. Cosmético.
  - `SubmitIntentListItemV1` ↔ `SubmitIntentListItemDto` (`accounts.py:603-617`) → mismas claves, divergencia solo de optionalidad.
  - `PositionDto` → **coincide** (protegido por G9).
  - `ExecutionStateV1`, `LiveOrderV1` → proyección/espejo de dominio, no wire-DTO → no aplica.
- **Conclusión:** no hay "dos verdades" de nombres de campo en runtime. Pero **incidents y submit-intents NO están en el gate (G1..G11)**. Acción recomendada (P2): añadirlos como **G12/G13** al `contract-check.ts` para que un cambio de backend en esos DTO rompa CI igual que Position.

---

## 6. UI "dice la verdad" — ✅ VERDE (corte de lectura)

El FE ya sostiene el invariante "lo que el operador cree = lo que el sistema sabe" con módulos dedicados y tests de invariantes cross-surface:

- `packages/shared/src/cognitive/operational-truth.ts`, `operational-context.ts`, `data-freshness.ts`, `operational-readiness.ts`, `operational-honesty-scenarios.test.ts`.
- Tests de igualdad entre superficies: `same-*-across-surfaces.test.ts` (position-operating-truth, execution-state, operational-truth, trade-story, exit-route, operational-plan, entry-operating), `execution-state-golden-path.test.ts`, `position-operating-truth*.test.ts`.
- Veredicto de lectura: estado visual derivado de estado real; no encontré en lectura una ruta que muestre un estado no respaldado. La única vía de "engaño" pasaría por un bugeado del mapping FE o un drift de backend no reflejado — que es justo lo que el gate G9 y los tests cross-surface intentan cerrar.

---

## 7. Cobertura de tests (qué protege cada pipeline) — observación [lectura]

- CI Python offline (`python-ci.yml`) **excluye por `--ignore`** los tests que entran a PostgreSQL/lifespan (auth, isolation `*_isolation`, golden `_v188..196`, `_pg`, `integration/`). Por tanto "CI VERDE" ≠ "sistema verificado"; lo que SIEMPRE corre offline son unit de domain/market/analytics + API sin DB.
- Lo que requiere DB real (PG en head 022) y **está fuera del job offline**: `test_live_order_store_pg`, `test_e2_v2_14_incident_dedup_pg`, `test_live_order_recovery_concurrency_pg`, `test_lifecycle_outbox_worker_pg`, `test_financial_integrity_pg`, `apps/api-python/tests/integration/`. En CI/release se ejecutan contra PG real (job propio).

---

## Tabla de hallazgos y severidad

| #   | Severidad          | Hallazgo                                                                                                                                          | Evidencia                                                                                                                                                                                                                                                                                   | Estado                                                                                                                                                                                           |
| --- | ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| A1  | **P1-condicional** | Endpoints operator/auto/IA leen `account_id` sin gate + dominio confía en gate HTTP (cross-account si existiera 2º owner real)                    | ejecución gateada: `ai_governance.py`(confirm), `position_policies.py`(evaluate-exits), `position_automation.py`(execute-auto), `paper_desk.py`(cycle); residual lectura/estudio: effectiveness/decision-sessions/memory/trials/edge-reports/propose/daily-report/instrument_daily_opinions | **[cerrado parcial]** gates `require_account_access` en rutas de EJECUCIÓN (2026-09-08); residual rutas de LECTURA/estudio sin gate → solo explotable con ≥2º owner real `[runtime-aislamiento]` |
| A2  | P2                 | Machine `live/position_state/paper` detalles: `failed→executed` no vetado; `UNKNOWN`(paper)→cierre sin poll; literal nuevo del grafo auto-bloquea | `position_state.py:86-102`, `paper_order.py:69-73`, `live_order.py:92-96`                                                                                                                                                                                                                   | [lectura]                                                                                                                                                                                        |
| A3  | P2                 | Dirigir `open→T1_EXECUTED` sin `T1_TRIGGERED` previo (validación solo de tiempos)                                                                 | `domain/lifecycle/__init__.py:672-684`                                                                                                                                                                                                                                                      | [lectura]                                                                                                                                                                                        |
| A4  | P2                 | Partial-UNIQUE de incidentes no cubre `cleared`; dedup solo protege estados activos                                                               | `tables.py:1366-1372`, `operational_incident_store.py:205-222`                                                                                                                                                                                                                              | [lectura] diseño                                                                                                                                                                                 |
| A5  | P2                 | Incidents/submit-intents fuera del gate de contrato (G1..G11) → candidatos G12/G13                                                                | `contract-check.ts`, `api.ts:1804,1818`                                                                                                                                                                                                                                                     | G12 (`OperationalIncidentV1`) y G13 (`SubmitIntentListItemV1`) **implementados** en `contract-check.ts` (2026-09-08); deuda residual P2.6: fidelidad de optionality/value NO gateada por diseño  |
| A6  | P2-defensivo       | `live_orders` upsert last-write-wins sin validar FSM en BD (valida dominio). Considerar CHECK/casos de contienda                                  | `live_order_store.py:519-528`                                                                                                                                                                                                                                                               | [lectura]/[runtime]                                                                                                                                                                              |
| A7  | P1-gate            | Replay idempotente post-crash de `submit_intent` durable y doble-writer de cancelación **no demostrados por lectura**                             | `confirm_recommendation.py:900-970`, `live_order_store.py:292-295`                                                                                                                                                                                                                          | **[runtime]** pendiente → requiere PG real/2 workers                                                                                                                                             |
| A8  | P3                 | API del use-case permite construir `ConfirmRecommendationIntent` sin lookups (fail-open del wiring)                                               | `confirm_recommendation.py` (`portfolio_summary`/`ohlcv` optional)                                                                                                                                                                                                                          | [lectura] defensivo                                                                                                                                                                              |

## Valoración por área (preliminar, para contrastar con el auditor externo)

| Área                                 | Estado                                              | Nota                                                                                         |
| ------------------------------------ | --------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| Arquitectura / capas                 | 9/10                                                | import-linter 4/0; wiring confirm cubierto                                                   |
| FSM / transiciones                   | 9/10                                                | sin camino que salte gates por lectura; detalles P2                                          |
| Concurrencia / dedup                 | 9/10                                                | partial-UNIQUE + SKIP LOCKED + GATE `permit=False`; lo real queda [runtime]                  |
| Aislamiento de cuenta                | 8.5/10                                              | gates ejecución aplicados (2026-09-08); residual rutas de lectura/estudio solo con ≥2º owner |
| Contrato API                         | 9/10                                                | G12/G13 implementados (2026-09-08); residual P2.6 optionality por diseño                     |
| UI dice la verdad                    | 9/10                                                | invariantes cross-surface con tests dedicados                                                |
| Persistencia / integridad financiera | 9/10                                                | GATED; constraints; falta [runtime] para carreras reales                                     |
| Cobertura de tests                   | 8/10                                                | depende del job con PG real; offline verde no basta                                          |
| **Preparación LIVE**                 | **NO CERTIFICADA** (necesita A7 + series [runtime]) | independiente de la calidad general                                                          |

## Lo que NO se puede cerrar por lectura (deuda para el auditor / fases [runtime])

- Replay idempotente post-crash del `submit_intent` durable y doble-writer de cancelación (A7).
- SKIP LOCKED / ON CONFLICT bajo contención real cross-PID (2 workers/leases).
- Estado físico de la BD (que la migración 022 haya creado los índices con el mismo nombre/where que el ORM).
- Reconciliaciones contra broker-truth real y semántica de `filled` real del bridge XTB.
- Aislamiento cross-account con ≥2 owners reales (hoy no hay 2º principal).

---

## Anexo — pasada de co-verificación independiente (2026-09-08)

Contraste de los hallazgos A1..A8 con subagentes de lectura independientes (paralelos, por hallazgo). Objetivo: intentar refutar cada hallazgo y no dar por bueno el informe sin segunda pasada. Método: se entregó a cada subagente el hallazgo con cita y se le pidió CONFIRMAR/REFUTAR/PARCIAL con `fichero:línea`, reportando además candidatos contradictorios.

Resultado: **ningún subagente refutó las conclusiones del informe; ninguno elevó un hallazgo a P0.** El valor de la pasada fue **(a)** reafirmar A1 y A5 con segunda lectura y **(b)** traer **3 matices nuevos de diseño/default** que el informe no había anotado — aquí quedan como registro (P2/P3, no alteran severidades):

- **M1 [P2, `claim_expires_at` observacional]**: en `live_order_store.claim_unknown_batch` (`live_order_store.py:558-599`) el claim escribe `recovery_worker_id`/`recovery_claimed_at` y reapropia por `recovery_claimed_at <= stale`; pero `claim_expires_at`/`attempt_count`/`last_error` **(`tables.py:1300-1316`) no se pueblan ni se leen** pese a que su docstring afirma "se pueblan en el claim". No afecta a la exclusividad (el lease operativo está firme), pero puede confundir el diagnóstico: un operador leería que el lease expira por `claim_expires_at` cuando en realidad expira por `recovery_claimed_at`. No es una carrera de doble-claim. Deuda B2/E1 "DIFERIDA" ya marcada en `CHANGELOG`.
- **M2 [P3/precisión de default, kill-switch OFF]**: el único freno de la vía LIVE por default es `LIVE_EXECUTION_UNLOCKED=false` (`live_execution_unlocked()` en `live_execution_runtime.py`, fail-closed); el `RISK_KILL_SWITCH` está **OFF por default** (`config.py:150-152`) y **no** participa en detener la vía. La comprobación vive en el borde del POST del adapter (`broker_adapter.py:218-258`) y no en la ruta. Por eso el informe prefería decir "no-POST fail-closed" en vez de depender de un kill-switch que no está activo: la redacción del informe (§ejecución GATED y A4) es correcta si se entiende que el freno es el flag de unlock, no el kill-switch. Precisión anotada.
- **M3 [P3/precisión de default, gates de reconciliación]**: la reconciliación durable de **posición** (P1-02/LR-1) entra en acción solo con el writer `live_drift` durable ON por env (`order_live_drift_incident.py:41-56`, default OFF) + venue `live`; la de **órdenes UNKNOWN** requiere `XTB_BRIDGE_URL` configurado, o el worker deja el UNKNOWN vivo (solo bump `updated_at`, `live_order_recovery_worker.py:84-89`). Consistente con "GATED"; no cambia severidad pero matiza que el default productivo de reconcil-signaler está apagado.

### Notas de honestidad de la pasada

- La co-verificación **no** ejecuta los `[runtime]` (A7, PG real, 2 workers, broky-truth): siguen pendientes y son los que certifican "LIVE readiness".
- Detecté que la hipótesis entregada a los subagentes A2/A3 empleaba una jerga propia del plan/resumen (`TargetLegHooks`, `ops_live_ctx`, `ix_execution_event_partial`, `live_pending_orders`) que **no existe en este árbol ni en el informe**. Los subagentes la refutaron correctamente buscando esos símbolos y volviendo al esquema real (`execution_id` PK + `ON CONFLICT DO NOTHING`, `recovery_worker_id`, tabla `live_orders`). Esa jerga NO forma parte del informe; se descarta como referente. (Advertencia contra trasponer nombres de `CHANGELOG`/planes al código sin verificar.)
