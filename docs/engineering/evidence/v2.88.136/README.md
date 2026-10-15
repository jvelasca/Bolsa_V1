# Evidencia `v2.88.136-beta` — remediación de la auditoría v111 (11 hallazgos) + cierre del docs-verify `1.61.0-beta`

> **Bump:** `2.11.135-beta` → **`2.11.136-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98`, del CLI `v2_99` y de `v2_100` — **13 scripts** en [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **1 passed**).
>
> **Naturaleza:** incremento **de remediación** (backend + persistencia + seguridad + UI/navegación + documentación) — **no** toca el motor de decisión, umbrales ni el contrato HTTP, y **no** amplía endpoint alguno. · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (`openapi.json`/`schema.d.ts` solo reflejan campos nuevos de DTO existentes; `contract:check` **OK**) · **CON migración `054`** (aditiva): head `053_dia_d_cycle_verifications` → **`054_dia_d_verified_and_alerts`**. Tag **unsigned**.
>
> **Base:** `v2.88.135-beta`.
>
> **Alcance del modelo de cuentas:** **single-user/single-account**. El aislamiento por `account_id` que instala este sello es **endurecimiento defensivo**, **no** una promesa multi-tenant.

---

## 0. Qué cierra (y qué NO)

**Cierra** los **11 hallazgos** de la auditoría v111, repartidos en cuatro frentes:

| Frente | Hallazgos | Qué se remedia |
| --- | --- | --- |
| **DÍA-D** | 1, 2 | La evidencia la resuelve el **servidor** desde hechos durables; unicidad + propiedad del ciclo |
| **Alertas de señal** | 3, 4, 5, 6 | Ownership por cuenta, claim **atómico** por barra y **outbox** durable de entregas |
| **Webhooks** | (seguridad) | **Anti-SSRF**: HTTPS, DNS previo, sin rangos internos ni metadata, sin redirecciones |
| **UI + navegación** | 7, 8, 9, 10, 11 | Alcance por cuenta activa, errores de detalle visibles y `/operations` restaurada |

Y cierra además la **deuda documental** del `docs-verify` de `1.61.0-beta` (fase E).

**NO cierra** (se declara): la **ventana PAPER real** (ADR-046) sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`** — lo que falta es **OPERACIÓN**, no software. Este sello **no demuestra rentabilidad** ni acredita la ventana.

---

## 1. DÍA-D — la evidencia la resuelve el servidor (hallazgos 1-2)

**Problema.** La verificación DÍA-D aceptaba del cliente un cuerpo con instrumento, estrategia, banda, periodo y evidencia, y lo persistía. Es decir: el cliente **fabricaba** los hechos que después se auditaban, y el ciclo no quedaba atado a ninguna cuenta.

**Cambio.**

- El DTO de entrada se reduce a **identidad mínima**; el servidor deriva instrumento, estrategia, banda, periodo y evidencia desde los hechos AUTO durables (`executed_identity` + monitor operacional) vía `resolve_dia_d_cycle_facts`.
- Se persiste `facts_hash`: los hechos que sustentan la verificación quedan **fijados** en la fila.
- `404` cuando el ciclo no existe y `409` cuando la verificación no es procedente (en vez de aceptar un cuerpo del cliente).
- [`dia_d_cycle_verification.py`](../../../../packages/py/application/src/bolsa_application/dia_d_cycle_verification.py) · [`auto_dia_d_verification.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d_verification.py).

**Ownership (hallazgo 2).** Un ciclo ya verificado por **otra** cuenta se **RECHAZA** con `DiaDCycleVerificationOwnershipConflictError`: **nunca** se reasigna ni se duplica. Unicidad + upsert **atómico** por `(account_id, cycle_id, dia_d, end_date, mode)` (`INSERT … ON CONFLICT DO UPDATE` con guarda de propiedad) y búsqueda siempre acotada por `account_id`.

---

## 2. Migración `054_dia_d_verified_and_alerts`

**Aditiva**. Tres cosas:

1. Constraint `(account_id, cycle_id, dia_d, end_date, mode)` + columna `facts_hash` en `dia_d_cycle_verifications`.
2. `account_id` en `signal_alert_subscriptions`.
3. Tabla **outbox** `alert_deliveries`.

**Incidente corregido y fijado por test.** El identificador de revisión original (`054_dia_d_server_verified_and_alert_ownership`, **45 caracteres**) reventaba `upgrade head` con `DataError: StringDataRightTruncation`, porque `alembic_version.version_num` es **`varchar(32)`**. Se acortó a `054_dia_d_verified_and_alerts` (**29**) y [`test_054_dia_d_verified_and_alerts.py`](../../../../packages/py/infrastructure/tests/test_054_dia_d_verified_and_alerts.py) **fija** el límite, el `down_revision` lineal desde `053` y la **head única**.

---

## 3. Alertas de señal (hallazgos 3-6)

### 3.1 Ownership por cuenta

`account_id` en la tabla y **filtro de propiedad** en `list`/`create`/`delete`/`reset`/`evaluate`: ninguna operación cruza cuentas. [`signal_alert_repository.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/signal_alert_repository.py) · [`signal_alerts.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/signal_alerts.py).

### 3.2 Claim ATÓMICO por `(suscripción, barra)`

`mark_bar_triggered` reclamaba leyendo y luego escribiendo: el **worker** y una **evaluación manual** podían despachar la **misma barra dos veces**. Ahora:

- Claim con `last_bar_timestamp IS DISTINCT FROM :bar` + **token de lease** y `processing_started_at`.
- `finish_bar_claim()` confirma la barra **solo** con el token que la reclamó.
- Un **lease caducado** es reclamable por otro proceso (el que murió a mitad no bloquea la barra para siempre).

### 3.3 Patrón OUTBOX durable

Tabla `alert_deliveries` con máquina de estados:

```
PENDING ──▶ DELIVERED
   │
   ├──▶ RETRYABLE_FAILED ──(backoff)──▶ PENDING
   │
   └──▶ DEAD_LETTER  (terminal)
```

- **Backoff** exponencial por intento.
- Truncado **declarado** del error (no se guarda un error infinito).
- `expire` de agotados → `DEAD_LETTER`.
- Una entrega **no se pierde** si el proceso muere entre el claim y el envío.

Cubierto por [`test_signal_alerts_v111_pg.py`](../../../../apps/api-python/tests/test_signal_alerts_v111_pg.py) (PG real: un solo ganador por barra, lease caducado reclamable, máquina de estados completa, dedupe por `(barra, canal)` y ownership).

---

## 4. Webhooks — anti-SSRF

**Puerta única** `assert_public_webhook_target` en [`alert_channels.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/alerts/alert_channels.py):

| Control | Comportamiento |
| --- | --- |
| Esquema | **HTTPS obligatorio** |
| DNS | **Resolución previa** y validación de **todas** las IPs resueltas |
| Rangos | Rechazo de **loopback, privados, link-local, reservados y IPv6 mapeada** |
| Metadata | Rechazo explícito de **`169.254.169.254`** y equivalentes |
| Redirecciones | **Prohibidas** (se valida el destino, no se sigue el `Location`) |
| Red | Timeout y límites de tamaño; allowlist configurable |

Cubierto por **27 casos herméticos** en [`test_alert_channels_ssrf.py`](../../../../packages/py/infrastructure/tests/test_alert_channels_ssrf.py) (incluye fallo de DNS y casos de allowlist).

---

## 5. UI y navegación (hallazgos 7-11)

- **Sesión DÍA-D por cuenta (7-8).** La sesión se persiste y se lee con `accountId`, y se envía **explícitamente** a la persistencia ([`dia-d-trading-session-store.ts`](../../../../apps/web/src/stores/dia-d-trading-session-store.ts)); al guardar se **invalidan** las queries afectadas.
- **Errores de detalle visibles (9-10).** Los fallos de consulta muestran un **error de detalle** en el panel DÍA-D y en el feedback (`dia-d-auto-detail-error`, `dia-d-auto-feedback-detail-error`) en vez de un silencio.
- **Monitor de alertas anclado a la cuenta activa (11).** Query keys por cuenta efectiva y **reset del dedupe** al cambiar de cuenta: el `Set` de deduplicación no arrastra la cuenta anterior.
- **`/operations` restaurada.** Vuelve a montar su página en [`app.tsx`](../../../../apps/web/src/app.tsx) (antes redirigía a Mesa), con test de ruta.

---

## 6. Cierre del `docs-verify` de `1.61.0-beta`

- La matriz de **V2.36** queda consolidada como **§5.1** del **punto de entrada único acumulado** ([`audit-pack-v2.35-consolidado-a13-a14-a15-2026-09-11.md`](../../audit-pack-v2.35-consolidado-a13-a14-a15-2026-09-11.md)), que pasa a cubrir **A13 + A14 + A15 + V2.36**; el pack de fase queda como **detalle ampliado**.
- Alineación de [`CHANGELOG.md`](../../../../CHANGELOG.md), [`docs/CURRENT_SYSTEM.md`](../../../CURRENT_SYSTEM.md), [`PROJECT_STATE.md`](../../PROJECT_STATE.md) y el relevo.
- **Declaración explícita:** **no existe** un `docs-verify` como job ni como script de CI. La verificación documental es **manual** (queda escrito para que nadie la busque y para que su ausencia no se lea como olvido).

---

## 7. Cableado de CI de la certificación PG (`OBS-19`)

**Regla del repo:** un test PG que no corre en ningún job con gate **falla en mudo** si no se le pone `--ignore` en el job offline. Las dos suites nuevas del lote cumplen las dos mitades:

| Suite | Offline (`quality`) | Por commit (`auto-v2-durable-pg`) | Tag (`lifecycle-pg`) |
| --- | --- | --- | --- |
| [`test_dia_d_cycle_verification_pg.py`](../../../../apps/api-python/tests/test_dia_d_cycle_verification_pg.py) | `--ignore` | sí, gate `DIA_D_CYCLE_VERIFICATION_PG_REQUIRED=1` | sí |
| [`test_signal_alerts_v111_pg.py`](../../../../apps/api-python/tests/test_signal_alerts_v111_pg.py) | `--ignore` | sí, gate `SIGNAL_ALERTS_PG_REQUIRED=1` | sí, gate `SIGNAL_ALERTS_PG_REQUIRED=1` |

Ambos jobs PG llevan **guard anti-skip**: un `skipped` invalida la certificación (fallo duro).

### 7.1 Agujero `OBS-19` adicional — declarado y cerrado

[`test_auto_fill_cycle_seal_pg.py`](../../../../apps/api-python/tests/test_auto_fill_cycle_seal_pg.py) (certificador del **sello de ciclo**: exige fill **COMPLETO** y liberación **`BY_FILL`** con el contexto persistido) **no lo ejecutaba ningún job**:

- **no** estaba en ningún `--ignore` ⇒ en el job offline **skipeaba en mudo** (peor que no existir: se veía pasar);
- **no** figuraba en ninguna lista PG;
- su gate `AUTO_FILL_CYCLE_SEAL_PG_REQUIRED` **no estaba declarado en ningún workflow**;
- el **censo** no lo veía como hueco porque el pase de directorio del offline lo «cubría».

**Cierre:** `--ignore` en los dos jobs offline + certificación con gate y guard anti-skip en `auto-v2-durable-pg` (por commit) y `lifecycle-pg` (tag).

---

## 8. Defecto de tooling corregido — precedencia del URL en `alembic/env.py`

**Hallazgo.** La cabecera de [`alembic/env.py`](../../../../packages/py/infrastructure/alembic/env.py) documenta una precedencia explícita (`DATABASE_URL` > `config.attributes["DATABASE_URL"]` > `alembic.ini`), pero la ruta **online** (`run_migrations_online`) construía el engine con `engine_from_config(config.get_section(...))` a secas — **siempre** desde el ini. La ruta **offline** sí usaba `_resolved_url()`, así que el desajuste era invisible en `alembic upgrade head --sql` y **solo** se manifestaba en el uso real: `alembic upgrade head` desde el CLI migraba **otra** base de datos que la que consultaba el proceso, con la BD de **desarrollo** como destino silencioso (el `.env` apunta a ella).

Se descubrió operando este sello: la BD *scratch* quedaba intacta mientras los tests golpeaban la de desarrollo.

**Cambio.** La ruta online inyecta el URL resuelto en la sección del engine:

```python
section = config.get_section(config.config_ini_section, {})
section["sqlalchemy.url"] = _resolved_url()
engine = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
```

**Guardia falsable.** [`test_alembic_env_url_precedence.py`](../../../../packages/py/infrastructure/tests/test_alembic_env_url_precedence.py) (**5 passed**) fija la precedencia, las dos rutas y la rama de conexión inyectada. **Verificada por mutación:** retirando la inyección, `test_online_path_uses_the_resolved_url` **rompe**.

---

## 9. Verificación de este sello (local)

```
ruff check packages/py apps/api-python --config pyproject.toml ...... All checks passed!
mypy (gate bloqueante) .............................................. Success: 0 errores / 555 ficheros
lint-imports --config packages/py/.importlinter ..................... 4 kept / 0 broken
pytest packages/py/application/tests ................................ 2784 passed   (incl. 11 del nuevo test de identidad)
pytest (test_resolve_dia_d_cycle_facts + test_dia_d_cycle_verification + ruta DÍA-D)  35 passed
pytest (ruta DÍA-D + 3 suites PG-gated, con sus gates activos) ............... 32 passed
pytest <gate offline `quality` del YAML> ............................ 5140 passed, 1 skipped, 0 failed
pytest <job `auto-v2-durable-pg` completo, BD recién creada> ........ 122 passed, 0 skipped
pytest <steps `lifecycle-pg` del tag con las entradas nuevas> ....... 176 passed  +  218 passed, 0 skipped
test_dia_d_bump_guard.py ............................................ 1 passed    (2.11.136-beta)
scripts/ci/test_selection.py --report ............................... 634/634 ejecutados, 0 sin declarar
web: pnpm typecheck / vitest / contract:check ....................... OK / 2232 passed (307 ficheros) / OK
```

- **El único skip** del gate offline es la sonda de Ollama ausente (`test_golden_and_ollama.py`: «Ollama respondió vacío o modelo ausente»), **ajeno** a este sello.
- **Los jobs PG se corren con sus gates activos**, así que los `skip` no son posibles: un skip sería **fallo duro**.
- **Cita de los conteos**: los bloques se ejecutaron **extrayendo la lista del propio YAML** (no una lista transcrita a mano), para que el número medido corresponda a lo que corre el job.

### 9.1 Por qué la certificación PG se midió sobre BD *scratch*

La BD local de desarrollo **no podía** alcanzar la head: `sim_fill_finance_context` acumulaba **1588 atributos *dropped*** (columnas muertas que PostgreSQL sigue contando) frente al tope de **1600**, así que cualquier `ADD COLUMN` fallaba con `TooManyColumns` — y ese residuo volvía además **inestable** `test_auto_fill_cycle_seal_pg.py` (liberación `OPEN` en vez de `RELEASED_BY_FILL`).

Por eso la lista PG completa se midió sobre BD **scratch limpia** (el camino que documenta el propio repo en [`a9_scratch_db.py`](../../../../apps/api-python/scripts/a9_scratch_db.py)). **Decisión del owner aplicada:** la BD de desarrollo se **recreó** (drop + create + `alembic upgrade head`) y queda en head `054` con **residuo 0**; la certificación final se repitió sobre una BD **recién creada**, que es el escenario de CI.

---

## 10. Límites declarados (sin fabricar) + falsabilidad

- **Ventana PAPER real (ADR-046):** sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`**. Lo que falta es **OPERACIÓN**.
- **Modelo de cuentas:** **single-user/single-account**. El `account_id` es **defensa**, no multi-tenant.
- **Contrato HTTP:** **sin ampliación** de endpoints; `contract:check` compara contra el commit.
- **Migración:** `054` es **aditiva**; el identificador se mantiene **≤ 32** por límite físico de `alembic_version.version_num`.
- **Tag unsigned.**
- **Arranque en frío de `S5-04` en CI:** el **primer** intento puede seguir superando los 60 s de espera de la evidencia LAB (intermitencia del runner, **ABIERTA** y declarada, §13). Este sello **no** la cierra y **no** tocó `timeouts`, `retries` ni umbrales `ADR-046`.
- **Este sello no demuestra rentabilidad.**

**Falsabilidad.**

- Si un cliente pudiera volver a **fabricar** la evidencia DÍA-D, los tests de la ruta DÍA-D **rompen**.
- Si un ciclo verificado por otra cuenta se **reasignara** en vez de rechazarse, el test de conflicto **rompe**.
- Si el claim dejara de ser atómico (dos ganadores por barra), el test PG de claim **rompe**.
- Si un webhook pudiera apuntar a loopback/privado/metadata, `test_alert_channels_ssrf.py` **rompe**.
- Si un test PG nuevo no se cableara **o** dejara de ignorarse en el offline, el **censo** (`test_ci_test_selection_census.py`) **rompe**.
- Si la ruta online de `env.py` volviera a ignorar `DATABASE_URL`, `test_alembic_env_url_precedence.py` **rompe**.
- Si la identidad del instrumento del ciclo se propagara **cruda** (sin canonizar al id del catálogo), `test_resolve_dia_d_cycle_facts.py` **rompe** (§13).
- Si `meta.bump` de cualquier CLI difiere de `package.json`, el guardián **rompe**.

---

## 11. Ficheros del sello

- **Nuevos:** [`054_dia_d_verified_and_alerts.py`](../../../../packages/py/infrastructure/alembic/versions/054_dia_d_verified_and_alerts.py); [`test_054_dia_d_verified_and_alerts.py`](../../../../packages/py/infrastructure/tests/test_054_dia_d_verified_and_alerts.py); [`test_alert_channels_ssrf.py`](../../../../packages/py/infrastructure/tests/test_alert_channels_ssrf.py); [`test_alembic_env_url_precedence.py`](../../../../packages/py/infrastructure/tests/test_alembic_env_url_precedence.py); [`test_signal_alerts_v111_pg.py`](../../../../apps/api-python/tests/test_signal_alerts_v111_pg.py); [`test_resolve_dia_d_cycle_facts.py`](../../../../packages/py/application/tests/test_resolve_dia_d_cycle_facts.py) (guardia de la regresión de identidad, §13); [`alerts-monitor.test.tsx`](../../../../apps/web/src/features/alerts/alerts-monitor.test.tsx); [`operations-route.test.ts`](../../../../apps/web/src/features/operations/operations-route.test.ts); esta evidencia.
- **Modificados (selección):** [`dia_d_cycle_verification.py`](../../../../packages/py/application/src/bolsa_application/dia_d_cycle_verification.py) · [`signal_alerts.py`](../../../../packages/py/application/src/bolsa_application/signal_alerts.py) · [`auto_chain_durable_reader.py`](../../../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) · [`alert_channels.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/alerts/alert_channels.py) · [`signal_alert_repository.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/signal_alert_repository.py) · [`dia_d_cycle_verification_repository.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/dia_d_cycle_verification_repository.py) · [`tables.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py) · [`config.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/config.py) · [`env.py`](../../../../packages/py/infrastructure/alembic/env.py) · la ruta y los esquemas de DÍA-D y de alertas · la UI de DÍA-D/alerts/operativa · [`app.tsx`](../../../../apps/web/src/app.tsx) · `meta.bump` de 13 CLIs · [`package.json`](../../../../package.json) · [`CHANGELOG.md`](../../../../CHANGELOG.md) · [`PROJECT_STATE.md`](../../PROJECT_STATE.md) · [`CURRENT_SYSTEM.md`](../../../CURRENT_SYSTEM.md) · los packs A13+A14+A15 y V2.36 · el relevo V2.36 · los dos workflows.

---

## 12. `Release tag CI` del sello

**Intento 1 (ROJO, declarado).** Tag `v2.88.136-beta` (lightweight, unsigned) sobre el commit del sello `c4f83568`. `Release tag CI` [run **`38779113120`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38779113120) **ROJO** con **un solo job** en fallo: `playwright (integrated AUTO S5)` (test `GP-V288-S5-04`), que falló **también el reintento**. Todo lo demás **VERDE**: `security (gitleaks)`, `shared`, `decision-spine`, `frontend` (typecheck/lint/test/build + `contract:check`), `python` (ruff/imports/mypy/pytest offline), `playwright (mock E2E)`, `playwright (integrated axe)`, `lifecycle-pg` (**con los gates PG nuevos de este sello**), `replay-repro` (**REPRODUCIDO**), `dr-verify`, `a7-gate`; `playwright (integrated E2E, opt-in)` queda `skipped` (opt-in declarado) y `certify` falla **solo** por agregación (`exit 1` sobre el job rojo).

**No era flakiness: era una regresión REAL de este sello** (el reintento la confirmó). Ver §13.

**Intento 2 (VERDE).** Tras el arreglo, el tag se **movió** al commit de corrección **`71d366e5`** (`git tag -f` + push forzado del ref; **lightweight**, unsigned). `Release tag CI` [run **`38795110802`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38795110802) **VERDE**: **12 jobs `success`** + `certify` `success`, incluido `playwright (integrated AUTO S5)`, y `replay-repro` **`REPRODUCIDO`**.

---

## 13. Incidente de CI (declarado y cerrado): regresión de la identidad DÍA-D

**Síntoma.** `GP-V288-S5-04` falló **dos veces**: el intento 0 en `S5-04 · esperar la evidencia de la sesión LAB` (el botón `Guardar Evidence` no aparece en 60 s — la readiness del arranque en frío del runner ya documentada en `v2.88.135` §10.2) y, lo importante, el **reintento** en `S5-04 · guardar y verificar el enlace durable`: se pulsó guardar, la UI declaró `Guardado`, y **el enlace durable no existía**.

**Causa raíz (medida, no inferida).**

| Pieza | Valor que aporta |
| --- | --- |
| Reserva durable del ciclo (harness de siembra `scripts/dev/seed_auto_cycle_for_ui.py`) | `instrument_id = "ACS"` — el **SÍMBOLO** (`_reservation(instrument=symbol)`) |
| Panel DÍA-D (`trading-dia-d-replay-panel.tsx`) | declara `instrumentId: session.instrumentId` — el **id de catálogo** (UUID) |
| `_declared_conflicts` (contrato v111) | compara **cadenas**: `"8f6c2b1e-…" != "ACS"` ⇒ **`409 cycle_identity_conflict`** |

El panel marca el guardado como **exitoso** porque el archivo local y la Fase 2 **sí** ocurrieron; el fallo del enlace viaja como `cycleLinkError` (aviso declarado, no silencio). Resultado medible: el E2E ve `Guardado` y, después, **cero filas** con el `cycleId` **y** el `instrumentId` del ciclo.

**Por qué es una regresión de ESTE sello.** Antes de v111 la identidad del enlace la declaraba el **navegador** (siempre el id de catálogo) y el servidor la persistía tal cual. v111 —correctamente— movió la derivación al servidor, pero la derivó del valor **crudo** de la reserva. El defecto vivía **latente** en la costura siembra/legacy (el propio docstring del resolver la reconocía) y solo se hizo visible al dejar de aceptar lo declarado por el navegador.

**Arreglo.** NUEVO `canonical_instrument_identity(raw, catalog_row)` en [`auto_chain_durable_reader.py`](../../../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py): cuando el catálogo conoce el instrumento —por `id` **o** por `symbol`— la identidad se canoniza a su **id de catálogo** (la misma que usa el resto del producto y la que el navegador declara como contraste). Sin fila de catálogo se conserva el valor **crudo** y el símbolo es un **hueco declarado**: nunca se inventa identidad (`UNKNOWN ≠ 0`). `resolve_dia_d_cycle_facts` pasa a leer `(id, symbol)` en una sola consulta.

**Guardia falsable (el test que faltaba).** NUEVO [`test_resolve_dia_d_cycle_facts.py`](../../../../packages/py/application/tests/test_resolve_dia_d_cycle_facts.py) — **11 passed**: regla pura de canonización (+ hueco declarado sin catálogo) y el **resolver real** con las costuras de la siembra. Incluye la **reproducción explícita de la regresión**: con la identidad **sin canonizar**, el contraste declarado lanza `DiaDCycleIdentityConflictError` y **no se escribe nada** (`assert repo.calls == []`). Antes de v111 el resolver real no tenía **ningún** test directo (la ruta lo monkeypatcheaba), y ése fue el hueco que dejó pasar la regresión.

**Verificación tras el arreglo (local).** `pytest packages/py/application/tests` **2784 passed** · `test_auto_dia_d_verification_route.py` + los tres PG-gated (`DIA_D_CYCLE_VERIFICATION_PG_REQUIRED=1`, `SIGNAL_ALERTS_PG_REQUIRED=1`, `AUTO_FILL_CYCLE_SEAL_PG_REQUIRED=1`) **32 passed** · `ruff` **`All checks passed!`** · `mypy` **0 errores** · censo **634/634, 0 sin declarar**.

**Cierre.** Tag **movido** al commit del arreglo (`git tag -f` + push forzado del ref; el tag es **lightweight** y **unsigned**, y el sello no estaba publicado ni anunciado). **Intento 2 (VERDE).** `Release tag CI` [run **`38795110802`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38795110802) **VERDE** (~13m43s, `2026-10-15T19:35:11Z` → `19:48:54Z`; **12 jobs `success`** + `certify` `success`; `playwright (integrated E2E, opt-in)` `skipped`, declarado): `playwright (integrated AUTO S5)` **`success`** con `S5-04` verde en el **reintento** (`7.33 s`; «guardar y verificar el enlace durable» `0.49 s`) y `replay-repro` **`REPRODUCIDO`** (`sha256 1E3ADAC2…929A37E7`). El intento 0 de `S5-04` sigue consumiendo `64.96 s` (espera LAB `60.00 s`) — la intermitencia del arranque en frío **sigue ABIERTA** y declarada (§13).

**Base:** `v2.88.135-beta`.
