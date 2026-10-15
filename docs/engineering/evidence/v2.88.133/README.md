# Evidencia `v2.88.133-beta` — cierre de `G6` a nivel de HANDLER, el panel FA sobrevive a un payload que viola `FundamentalCardDto`, refresco de los goldens win32 del certificado visual y fix del helper del sello de ciclo (fill COMPLETO)

> **Bump:** `2.11.132-beta` → **`2.11.133-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98` y del CLI `v2_99` — **12 scripts** en [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **1 passed**).
>
> **Naturaleza:** incremento **mixto** — **fix de logging** (redacción de credenciales a nivel de `Handler`), **fix de UI AUTO/FA** (guarda de forma del DTO + normalización), **goldens E2E win32** (drift preexistente, contenido idéntico) y **fix de test** (helper del sello de ciclo) · **`Δ motor de decisión = 0`** (sin umbrales/reparto/`TOP_N`/régimen/selección/protección/ejecución) · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (no se amplía ningún endpoint) · **SIN migración** (head `053_dia_d_cycle_verifications`). Tag **unsigned**.
>
> **Base:** `v2.88.132-beta`.

---

## 0. Qué cierra (y qué NO)

**Cierra** cuatro frentes:

1. **`G6` a nivel de HANDLER** ([`auditoria-aislamiento-ejecucion-xtb-2026-10-14.md`](../../auditoria-aislamiento-ejecucion-xtb-2026-10-14.md)): la redacción de credenciales **alcanza de verdad** a los loggers reales (`root`, `uvicorn`, `uvicorn.error`/`access`, `lastResort`) y a los **workers standalone**.
2. **Panel FA robusto ante un payload que VIOLA `FundamentalCardDto`**: deja de **blanquear** `/backtests?tab=run` y de **tumbar** el verificador DÍA-D.
3. **Goldens win32 del certificado visual REFRESCADOS** (drift **+20px** de alto **preexistente**, contenido idéntico; el spec se salta en CI).
4. **Fix del helper del sello de ciclo** ([`test_auto_fill_cycle_seal_pg.py`](../../../../apps/api-python/tests/test_auto_fill_cycle_seal_pg.py)): exige fill **COMPLETO**.

**NO cierra** (se declara): la **ventana PAPER real** (`P3-2`/`P3-3`, ADR-046) — lo que falta es **OPERACIÓN**, no software — ni la rentabilidad/magnitud del P&L.

---

## 1. `G6` CERRADO a nivel de HANDLER — la redacción alcanza a los loggers reales

Núcleo en [`logging_redact.py`](../../../../apps/api-python/src/bolsa_api/logging_redact.py). `install_log_redact()` asociaba el `RedactFilter` con `Logger.addFilter`, que **solo** se evalúa en el logger que **EMITE**; los registros que **propagan** por el árbol invocan los `Handler.filters` de los **ancestros**, **no** sus `Logger.filters`. Por eso `logging.getLogger(__name__)` (el patrón de la app) **nunca** pasaba por el filtro y los secretos llegaban al log montado.

**Fix:**

- adjuntar `RedactFilter` a los **HANDLERS** (`root`, `bolsa_api`, `uvicorn`, `uvicorn.error`/`access` y `logging.lastResort`);
- re-llamar `install_log_redact()` en `lifespan()` ([`main.py`](../../../../apps/api-python/src/bolsa_api/main.py));
- los **workers standalone** ([`scheduler_worker.py`](../../../../apps/api-python/src/bolsa_api/workers/scheduler_worker.py), [`queue_poll_worker.py`](../../../../apps/api-python/src/bolsa_api/workers/queue_poll_worker.py), [`arq_worker.py`](../../../../apps/api-python/src/bolsa_api/workers/arq_worker.py)) lo llaman **al arrancar**, donde **nunca** corre `create_app()`.

**Endurecimiento:** patrones extra (`client_secret`, `jwt_signing_key`, `signing_key`, `private_key`, `refresh_token`, `access_token`, `passphrase`, `app_password`, `db_password`…), redacción de `record.args` (str/dict/tuple), de campos `extra` str y de **tracebacks** (`exc_info` → `exc_text`), tolerante a `repr`.

Cubierto por [`test_logging_redaction.py`](../../../../apps/api-python/tests/test_logging_redaction.py) (propagación real desde un logger descendiente, cobertura del handler `uvicorn.access`, idempotencia, entrypoints de workers) y por [`test_q2_hygiene.py`](../../../../apps/api-python/tests/test_q2_hygiene.py) (reescrito para emitir desde un logger **HIJO**); la fixture `logging_redact_state` ([`conftest.py`](../../../../apps/api-python/tests/conftest.py)) hace snapshot/restore del wiring.

**Residual declarado.** El **bridge XTB** es una **frontera de confianza EXTERNA** al repo: el repo fija las condiciones de invocación y la redacción, **no** la implementación del bridge.

---

## 2. El panel FA sobrevive a un payload que VIOLA `FundamentalCardDto`

**Síntoma:** al pulsar «Verificar D→hoy» desde AUTO, `/backtests?tab=run` **blanqueaba** en `Cannot read properties of undefined (reading forwardPe)` (error boundary) y el host `dia-d-verify-host` **nunca montaba** ⇒ **tumbaba** el verificador DÍA-D.

**Causa raíz:** `FundamentalCardDto` exige `facts`/`derived`/`metadata`; un payload que no los trae era **truthy** (la lista `[]` del fallback genérico del mock), pasaba el `if (!card)` y reventaba en `card.facts`.

**Cierre (producto):**

- guarda de forma **`isFundamentalCardDto`** + normalización en [`use-ensure-instrument-fundamentals.ts`](../../../../apps/web/src/features/instruments/use-ensure-instrument-fundamentals.ts) (fuente **única** para los 3 consumidores);
- y en el **segundo camino** del panel ([`fundamental-card-panel.tsx`](../../../../apps/web/src/features/instruments/fundamental-card-panel.tsx), `ensuredCard ?? query.data?.data`).

Un payload inválido se declara **ausencia** (`status empty`, «Sin datos FA»), **nunca** una tarjeta a medio formar.

**Mock E2E:** [`e2e-mock-routes.ts`](../../../../apps/web/e2e/helpers/e2e-mock-routes.ts) declaraba `{ data: [] }` para `/api/instruments/:id/fundamentals` (viola el DTO); ahora declara `null`, que es lo que el cliente ya tipa (`FundamentalCardDto | null`).

**Falsabilidad.** Con los fuentes revertidos al estado previo, el test reproduce el `TypeError` exacto en `fundamental-card-panel.tsx:391`. 7 casos nuevos (validador de forma + regresión del panel).

---

## 3. Goldens win32 del certificado visual refrescados (drift preexistente)

Las **8 capturas** (cockpit 1366/1024, `position-card`, `position-card-hud`, `auto-desk`) estaban caducadas desde el baseline `aa356b1f`: el **alto** creció **+20px** (ancho intacto) por la evolución UI previa (p. ej. UI5-14 sustituyendo el comodín `-` por «Sin dato todavía»). **No hay cambio de contenido propio**; el spec ya no falla y sigue **saltándose en CI** (`test.skip(CI)`).

---

## 4. Fix del helper del sello de ciclo — exige fill COMPLETO

[`test_auto_fill_cycle_seal_pg.py`](../../../../apps/api-python/tests/test_auto_fill_cycle_seal_pg.py): `test_structural_mode_releases_by_fill_without_durable_evidence` fallaba de forma **determinista** porque `_filling_symbol_for_tick` se conformaba con «algún fill», así que podía elegir un símbolo cuyo schedule llena **solo parcial** (p. ej. 50 de 100). `_settle` cuenta como `applied_qty` la suma del schedule y la liberación con fill **parcial** deja la reserva **viva** (`OPEN`) ⇒ el assert `RELEASED_BY_FILL` **nunca** podía cumplirse. Ahora el helper exige `status == 'filled'` (`cum == quantity`) ⇒ liberación **TOTAL**.

**Falsable:** con la liberación devolviendo `OPEN` el test vuelve a fallar.

---

## 5. Evidencia de verificación (local)

```
E2E integrado .................................. 14/14
E2E axe integrado (modo requerido) ............. 32/32
job mock CI (CI=true) .......................... 133 passed / 0 failed
job python offline ............................. 5066 passed / 1 skipped / 0 failed
pnpm --filter @bolsa/web test .................. 2224 passed
ruff check packages/py apps/api-python ......... OK
mypy (lista CI) ................................ OK
guardián de bump .............................. 1 passed (2.11.133-beta)
```

**No ejecutado localmente (declarado):** `replay-repro` **no es ejecutable en Windows** (CRLF/entorno); `dr-verify` y `security` **no se pudieron correr** en local (**faltan binarios**).

---

## 6. Sello / bump

- Bump `2.11.132-beta` → **`2.11.133-beta`**: `package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98` y del CLI `v2_99` (**12 scripts** en `apps/api-python/scripts/`). Guardián [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) → **1 passed**.
- **`Δ motor de decisión = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0`** (no se amplía ningún endpoint) · **SIN migración** (head de alembic `053_dia_d_cycle_verifications`).

---

## 7. Ficheros del sello

- **Nuevos:** [`docs/engineering/evidence/v2.88.133/README.md`](./README.md).
- **Modificados:** [`logging_redact.py`](../../../../apps/api-python/src/bolsa_api/logging_redact.py) (`G6` a nivel de handler), [`main.py`](../../../../apps/api-python/src/bolsa_api/main.py), los 3 workers ([`scheduler_worker.py`](../../../../apps/api-python/src/bolsa_api/workers/scheduler_worker.py), [`queue_poll_worker.py`](../../../../apps/api-python/src/bolsa_api/workers/queue_poll_worker.py), [`arq_worker.py`](../../../../apps/api-python/src/bolsa_api/workers/arq_worker.py)), [`conftest.py`](../../../../apps/api-python/tests/conftest.py), [`test_logging_redaction.py`](../../../../apps/api-python/tests/test_logging_redaction.py), [`test_q2_hygiene.py`](../../../../apps/api-python/tests/test_q2_hygiene.py), [`fundamental-card-panel.tsx`](../../../../apps/web/src/features/instruments/fundamental-card-panel.tsx), [`use-ensure-instrument-fundamentals.ts`](../../../../apps/web/src/features/instruments/use-ensure-instrument-fundamentals.ts) + sus `.test.tsx`/`.test.ts`, [`e2e-mock-routes.ts`](../../../../apps/web/e2e/helpers/e2e-mock-routes.ts), los 8 goldens win32, [`test_auto_fill_cycle_seal_pg.py`](../../../../apps/api-python/tests/test_auto_fill_cycle_seal_pg.py), `package.json` + `meta.bump` de los 12 CLIs, [`CHANGELOG.md`](../../../../CHANGELOG.md) y el pin [`window-forward.mjs`](../../../../scripts/lib/window-forward.mjs).

---

## 8. Límites declarados (sin fabricar) + falsabilidad

- **Ventana PAPER real (ADR-046):** sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`**. Lo que falta es **OPERACIÓN** (≥4 días de calendario sellando hechos durables, ≥2 regímenes y ≥32 ciclos medibles con `cycle_id`), **no** software. **El pin de la ventana (`WINDOW_CONFIG`) se re-ancla en este sello** al árbol del commit del sello.
- **No ejecutado en local:** `replay-repro` (no ejecutable en Windows, CRLF/entorno) y `dr-verify`/`security` (faltan binarios). Se declaran, **no** se reclaman.
- **Goldens win32:** el drift era **preexistente** (+20px de alto, contenido idéntico); el spec se **salta en CI**.

**Falsabilidad.**
- `G6`: si `install_log_redact()` dejara de adjuntar el filtro a los **HANDLERS**, si un logger descendiente volviera a colar una credencial, o si un worker arrancara sin el wiring, `test_logging_redaction.py` **rompe**.
- FA: si un payload inválido volviera a renderizar una tarjeta a medio formar (o si `isFundamentalCardDto` fallara), el test de regresión **rompe**.
- Helper del sello de ciclo: si la liberación devolviera `OPEN` con un fill parcial, el test vuelve a **romperse**.
- Bump: si `meta.bump` de cualquier CLI difiere de `package.json`, el guardián **rompe**.

---

## 9. `Release tag CI` del sello — **PENDIENTE**

Esta evidencia se redacta **antes** del tag. La **cita POST-TAG** (tag `v2.88.133-beta` + su `Release tag CI`) se añadirá **tras** ejecutar el tag. **Base:** `v2.88.132-beta`.
