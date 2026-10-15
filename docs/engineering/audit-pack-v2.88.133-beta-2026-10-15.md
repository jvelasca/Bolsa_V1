# Audit pack — `v2.88.133-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-15 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.133-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, dónde está la evidencia, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** documento de **evidencia/enlace**, no de producto. **`Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0`** (fix de logging + fix de UI AUTO/FA + goldens E2E win32 + fix de test). Tag **unsigned**.
>
> **✅ Estado (POST-TAG):** la **identidad inmutable** del tag (§1: `lightweight` ⇒ commit `530fa674290e23b0a23f074dc160f5f7c0681bf2`) y el **run de CI del sello** (§4: `38704219628`) ya están **citados**; este pack queda **completo**.

---

## 0. TL;DR — auditar en un comando

```bash
git clone --branch v2.88.133-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

> El `<SHA_DEL_SELLO>` exacto es **`530fa674290e23b0a23f074dc160f5f7c0681bf2`** (ver §1).

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag** | `v2.88.133-beta` — **lightweight** (**unsigned**) |
| **Objeto de tag** | **no hay objeto de tag** (lightweight: el nombre apunta **directo** al commit) |
| **Commit apuntado** | `530fa674290e23b0a23f074dc160f5f7c0681bf2` (`v2.88.133 sello: …`); el **re-anclaje del pin** de la ventana es el commit **inmediatamente posterior** `ops(window)` (`freeze OK`) |
| **Base (tag anterior)** | `v2.88.132-beta` → commit `49f578408dc094a3db8b29459195032b6eb82f8b` |
| **Versión monorepo** | `2.11.133-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `053_dia_d_cycle_verifications` (**sin migración**) |
| **Firma** | **unsigned** |

> **Nota (flujo del repo).** Los sellos de este repo citan el **run del `Release tag CI`** en un **commit POST-TAG** (push del tag + publicación de la evidencia). Aquí, por tanto, la identidad del objeto de tag y el SHA apuntado **se completaron en el commit POST-TAG** (ya citados en §1/§4); todo lo demás es auditable ya.

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.133-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | `git checkout 530fa674290e23b0a23f074dc160f5f7c0681bf2` (**ver §1**) |
| Ver el árbol en la web | [tree/v2.88.133-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.133-beta) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`evidence/v2.88.133/README.md`](./evidence/v2.88.133/README.md) | Evidencia del sello: `G6` a nivel de HANDLER, robustez del panel FA ante un DTO violado, refresco de goldens win32 y fix del helper del sello de ciclo, con **límites declarados** |
| 2 | [`CHANGELOG.md` §`2.11.133-beta`](../../CHANGELOG.md) | Nota de release: alcance, deltas, límites y verificación local |
| 3 | [`PROJECT_STATE.md`](./PROJECT_STATE.md) (AsOf `V2.88.133-beta`) | Estado vivo + **agenda funcional** (qué sigue abierto) |
| 4 | [`auditoria-aislamiento-ejecucion-xtb-2026-10-14.md`](./auditoria-aislamiento-ejecucion-xtb-2026-10-14.md) | Auditoría estática de aislamiento XTB: barreras B1–B7, huecos `G1`–`G6` y sus **cierres** (§5/§7) — contexto del `G6` que este sello cierra a nivel de handler |
| 5 | [`test_logging_redaction.py`](../../apps/api-python/tests/test_logging_redaction.py) | Suite `G6`: redacción de credenciales por **propagación real** desde un logger descendiente + handler `uvicorn.access` + entrypoints de workers |
| 6 | [`test_q2_hygiene.py`](../../apps/api-python/tests/test_q2_hygiene.py) | Higiene: emisión desde un logger **HIJO** (no el que monta el filtro) ⇒ cubre el fallo que `G6` cierra |
| 7 | [`fundamental-card-panel.test.tsx`](../../apps/web/src/features/instruments/fundamental-card-panel.test.tsx) + [`use-ensure-instrument-fundamentals.test.ts`](../../apps/web/src/features/instruments/use-ensure-instrument-fundamentals.test.ts) | Guarda de forma `isFundamentalCardDto` + regresión del panel FA (un payload inválido ⇒ **ausencia**, nunca tarjeta a medio formar) |
| 8 | [`test_auto_fill_cycle_seal_pg.py`](../../apps/api-python/tests/test_auto_fill_cycle_seal_pg.py) | Helper del sello de ciclo exige fill **COMPLETO** (`status == 'filled'`) |
| 9 | [`respuesta-auditoria-v2.88.133-beta-2026-10-15.md`](./respuesta-auditoria-v2.88.133-beta-2026-10-15.md) | **Respuesta a la revisión externa**: verificación propia del sello (§4: 6/7 afirmaciones sostenidas + el **pin** re-anclado POST-TAG) y pendientes `P1`-`P4` con **criterio falsable** (§6) |

---

## 4. CI público (citable)

**Run del `Release tag CI` del sello:** [`38704219628`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38704219628) — **VERDE** (~13m23s, `2026-10-15T08:14:12Z` → `08:27:35Z`; **todos los jobs `success`, incluido el agregado `certify`** —job `116324738769`—, con `playwright (integrated E2E, opt-in)` = `skipped` **por diseño**). El **gate duro** `playwright (integrated axe)` (job `116319502643`) queda **`success`** y `replay-repro` **REPRODUCIDO** (job `116319502482`) ⇒ `Δ decisión = 0` confirmado por CI; `lifecycle-pg` (job `116319502387`) y `playwright (mock E2E)` (job `116319502244`) **`success`**. **Sello CERRADO.**

**Referencia de la base** `v2.88.132-beta`: `Release tag CI` [run `38602858232`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38602858232) — `success` (~11m19s).

---

## 5. Qué **certifica** esta versión

Cierra el `G6` a nivel de handler y blinda el panel FA, sin tocar motor de decisión, decisión ni contrato HTTP:

- **`G6` CERRADO a nivel de HANDLER.** [`logging_redact.py`](../../apps/api-python/src/bolsa_api/logging_redact.py): `install_log_redact()` asociaba el `RedactFilter` con `Logger.addFilter`, que **solo** se evalúa en el logger que **EMITE**; los registros que **propagan** por el árbol invocan los `Handler.filters` de los ancestros, **no** sus `Logger.filters` ⇒ `logging.getLogger(__name__)` **nunca** pasaba por el filtro. Se adjunta el filtro a los **HANDLERS** (`root`, `bolsa_api`, `uvicorn`, `uvicorn.error`/`access` y `logging.lastResort`); se re-llama `install_log_redact()` en `lifespan()` y en los **workers standalone** ([`scheduler_worker.py`](../../apps/api-python/src/bolsa_api/workers/scheduler_worker.py), [`queue_poll_worker.py`](../../apps/api-python/src/bolsa_api/workers/queue_poll_worker.py), [`arq_worker.py`](../../apps/api-python/src/bolsa_api/workers/arq_worker.py)), donde **nunca** corre `create_app()`. **Endurecimiento:** patrones extra y redacción de `record.args`, de campos `extra` str y de **tracebacks**.
- **Panel FA robusto ante un payload que VIOLA `FundamentalCardDto`.** `/backtests?tab=run` blanqueaba (`Cannot read properties of undefined (reading forwardPe)`) y el host `dia-d-verify-host` **nunca** montaba ⇒ tumbaba el verificador DÍA-D. Cierre: guarda de forma `isFundamentalCardDto` + normalización en [`use-ensure-instrument-fundamentals.ts`](../../apps/web/src/features/instruments/use-ensure-instrument-fundamentals.ts) y en el segundo camino del panel ([`fundamental-card-panel.tsx`](../../apps/web/src/features/instruments/fundamental-card-panel.tsx)); el mock E2E pasa de `{ data: [] }` a `null`.
- **Goldens win32 del certificado visual REFRESCADOS (drift preexistente).** Las 8 capturas (cockpit 1366/1024, `position-card`, `position-card-hud`, `auto-desk`) estaban caducadas desde el baseline `aa356b1f`: el **alto** creció **+20px** (ancho intacto), **sin cambio propio de contenido**; el spec sigue **saltándose en CI** (`test.skip(CI)`).
- **Fix del helper del sello de ciclo.** [`test_auto_fill_cycle_seal_pg.py`](../../apps/api-python/tests/test_auto_fill_cycle_seal_pg.py): el helper exige fill **COMPLETO** (`status == 'filled'`), no un parcial ⇒ la reserva se libera **BY_FILL** de forma determinista.

**Deltas:** `Δ motor de decisión = 0` · `Δ decisión = 0` · **`Δ contrato HTTP = 0`** (no se amplía ningún endpoint) · **sin migración** (`053_dia_d_cycle_verifications`). Cambio de `apps/api-python/src` + `apps/api-python/tests` + `apps/web/src` + `apps/web/e2e` (goldens) + `package.json`/CLIs + docs + pin.

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **Ventana PAPER real (`P3-2`/`P3-3`, ADR-046): `0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`.** Lo que falta es **OPERACIÓN** (≥4 días de calendario sellando hechos durables, ≥2 regímenes y ≥32 ciclos medibles con `cycle_id`), **no** software.
2. **Bridge XTB externo.** El bridge es una **frontera de confianza EXTERNA** al repo; el repo fija las condiciones de invocación y la redacción, **no** su implementación (`G6` residual).
3. **`G3` residual.** `getattr(<objeto-local>, <variable>)` sobre un objeto de datos sigue **fuera** del alcance del invariante (límite declarado, no ausencia de barrera).
4. **No ejecutado en local (declarado).** `replay-repro` **no es ejecutable en Windows** (CRLF/entorno); `dr-verify` y `security` **no se pudieron correr** en local (**faltan binarios**). Se cubren en CI (§4).
5. **Goldens win32.** El drift era **preexistente** (+20px de alto, contenido idéntico); el spec se **salta en CI**.
6. **Habilitación real:** `AUTO_ORCHESTRATOR_ENABLED`/`AUTO_SIMULATION_WORKER_ENABLED` nacen **OFF** (SIM-only).

> **Trazabilidad de la revisión externa (2026-10-15).** Los cuatro pendientes operativos (`P1` ventana PAPER, `P2` evidencia por valor de ESTUDIO, `P3` DÍA-D ligado al ciclo, `P4` barreras fail-closed) y la **verificación propia del sello** (6/7 afirmaciones sostenidas; el **pin** se re-ancló en el commit POST-TAG `fcfc57f0`) están en §4/§6 de [`respuesta-auditoria-v2.88.133-beta-2026-10-15.md`](./respuesta-auditoria-v2.88.133-beta-2026-10-15.md). Discrepancias documentales declaradas allí: `dias=42/4` vs `0/4`, `verdict` es `READY`/`INCONCLUSIVE` (no `CERTIFIED`) y el campo real es `PAPER_EVIDENCE_SNAPSHOT_ENABLED`.

---

## 7. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se falsa |
| --- | --- | --- |
| 1 | La redacción alcanza a los loggers reales (handler, no solo el logger emisor) | `test_logging_redaction.py`/`test_q2_hygiene.py` fallan si un logger **descendiente** vuelve a colar una credencial o si un worker arranca sin el wiring |
| 2 | El panel FA no blanquea ante un DTO violado | el test de regresión falla si un payload inválido vuelve a renderizar una tarjeta a medio formar (o si `isFundamentalCardDto` falla) |
| 3 | El helper del sello de ciclo exige fill COMPLETO | el assert `RELEASED_BY_FILL` vuelve a fallar si la liberación devuelve `OPEN` con un fill parcial |
| 4 | Sin migración: head `053_dia_d_cycle_verifications` | `alembic heads` (desde `packages/py/infrastructure`) da otro head |
| 5 | `Δ contrato HTTP = 0` | `pnpm --filter @bolsa/web contract:check` falla (OpenAPI desincronizado) |
| 6 | Bump coherente | guardián [`test_dia_d_bump_guard`](../../apps/api-python/tests/test_dia_d_bump_guard.py) falla si un CLI difiere de `package.json` |

---

## 8. Reproducir la verificación (local, sin credenciales)

```bash
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
  packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync python -m pytest apps/api-python/tests/test_logging_redaction.py \
  apps/api-python/tests/test_q2_hygiene.py -q
uv run --no-sync python -m pytest apps/api-python/tests/test_auto_fill_cycle_seal_pg.py -q
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
pnpm --filter @bolsa/web test
```

**Resultados medidos de referencia (local):** E2E integrado **14/14** · E2E `axe` integrado en modo requerido **32/32** · job mock CI (`CI=true`) **133 passed / 0 failed** · job python offline **5066 passed / 1 skipped / 0 failed** · `pnpm --filter @bolsa/web test` **2224 passed** · `ruff`/`mypy` **OK** · guardián de bump **1 passed** (`2.11.133-beta`) · `alembic heads` `053_dia_d_cycle_verifications` (**sin migración**).
