# Respuesta a auditoría externa — sello `v2.88.133-beta` (2026-10-15)

> **Fecha:** 2026-10-15 · **Lector:** auditoría / revisión externa.
> **Sello auditado:** `v2.88.133-beta` (**lightweight**, unsigned) ⇒ commit `530fa674290e23b0a23f074dc160f5f7c0681bf2`; package `2.11.133-beta`; Alembic head `053_dia_d_cycle_verifications`. Base: `v2.88.132-beta` → `49f578408dc094a3db8b29459195032b6eb82f8b`.
> **Naturaleza:** documento de **evidencia/respuesta**, **no de producto**. **`Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0` · sin migración**.
> **Regla rectora del hueco (`UNKNOWN ≠ 0`):** un dato ausente se declara hueco, **jamás** se rellena con `0` ni con verde; una afirmación que no se puede sostener se declara **abierta** con su remediación.
> **Material de apoyo:** [`audit-pack-v2.88.133-beta-2026-10-15.md`](./audit-pack-v2.88.133-beta-2026-10-15.md) · [`evidence/v2.88.133/README.md`](./evidence/v2.88.133/README.md) · [`evidence/v2.88.131/README.md`](./evidence/v2.88.131/README.md) · [`evidencia-readonly-auto-paper-2026-10-14.md`](./evidencia-readonly-auto-paper-2026-10-14.md) · [`plan-ventana-paper-arranque-operativo-2026-10-14.md`](./plan-ventana-paper-arranque-operativo-2026-10-14.md) · [`auditoria-aislamiento-ejecucion-xtb-2026-10-14.md`](./auditoria-aislamiento-ejecucion-xtb-2026-10-14.md) · [`adr/046-protocolo-longitudinal-paper.md`](../adr/046-protocolo-longitudinal-paper.md).

---

## 0. Veredicto de una línea

**SE ACEPTA el veredicto externo**: el **sello técnico de CI está VERDE** y aporta mejoras reales (UI AUTO, verificación DÍA-D, seguridad de logs `G6`, reproducción determinista) — lo respalda el `Release tag CI` [run `38704219628`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38704219628) — **y la certificación OPERATIVA integral de AUTO sigue ABIERTA por falta de OPERACIÓN, no de software**. La medición del 2026-10-14 (35 valores ESTUDIO, 0/35 con ciclos medidos, 0 fills con `cycle_id`, ventana PAPER `INCONCLUSIVE`, ADR-046 `0/4`·`0/2`·`0/32`) coincide con lo que el propio repo declara. **No se refuta ningún punto del veredicto**; se confirma con `file:line`, se añade la **verificación propia del sello** (§4) y se deja trazado como pendientes `P1`-`P4` con criterio falsable (§6).

---

## 1. Identidad inmutable del sello (lo que se responde)

| Elemento | Valor | Origen |
| --- | --- | --- |
| Tag | `v2.88.133-beta` — **lightweight** (**unsigned**) | `git rev-parse` / `git cat-file -t` (lightweight ⇒ resuelve directo al commit) |
| Commit apuntado | `530fa674290e23b0a23f074dc160f5f7c0681bf2` | [audit-pack §1](./audit-pack-v2.88.133-beta-2026-10-15.md) |
| Base (tag anterior) | `v2.88.132-beta` → `49f578408dc094a3db8b29459195032b6eb82f8b` | ídem |
| Versión monorepo | `2.11.133-beta` | [`package.json`](../../package.json) |
| Alembic head | `053_dia_d_cycle_verifications` (**sin migración**) | ídem |
| `Release tag CI` del sello | [run `38704219628`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38704219628) **VERDE** (~13m23s; `certify` incluido, job `116324738769`) | [audit-pack §4](./audit-pack-v2.88.133-beta-2026-10-15.md) |

Esta tabla **cita** lo ya publicado; no re-mide CI en esta respuesta (el veredicto del run se toma de la documentación del sello, marcado como tal).

---

## 2. Qué certifica esta versión (en su alcance declarado)

Se acepta como **certificado dentro de su alcance**, con `file:line`:

1. **`G6` CERRADO a nivel de HANDLER — la redacción alcanza a los loggers reales.** El `RedactFilter` se adjunta a los **HANDLERS** (`root`, `bolsa_api`, `uvicorn`, `uvicorn.error`/`access`, `logging.lastResort`), no solo al logger emisor; se re-instala en `lifespan()` y en los **workers standalone** (donde no corre `create_app()`), con endurecimiento de patrones, `record.args`, campos `extra` y tracebacks. Origen: [`evidence/v2.88.133/README.md` §1](./evidence/v2.88.133/README.md); [`CHANGELOG.md`](../../CHANGELOG.md) (`2.11.133-beta`).
2. **El panel FA sobrevive a un payload que VIOLA `FundamentalCardDto`** — deja de blanquear `/backtests?tab=run` y de tumbar el verificador DÍA-D (`isFundamentalCardDto` + normalización; payload inválido ⇒ **ausencia**, nunca tarjeta a medio formar). Origen: [`evidence/v2.88.133/README.md` §2](./evidence/v2.88.133/README.md).
3. **Goldens win32 del certificado visual refrescados** (drift **preexistente**, +20px de alto, contenido idéntico; el spec se salta en CI). Origen: [`evidence/v2.88.133/README.md` §3](./evidence/v2.88.133/README.md).
4. **Fix del helper del sello de ciclo** (exige fill **COMPLETO**, `status == 'filled'`). Origen: [`evidence/v2.88.133/README.md` §4](./evidence/v2.88.133/README.md).
5. **`Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0` · sin migración**, con `replay-repro` **REPRODUCIDO** en CI ⇒ `Δ decisión = 0` confirmado por CI.
6. **Efectos operativos colaterales reales:** la verificación manual DÍA-D vuelve a ser lanzable desde AUTO (el host `dia-d-verify-host` vuelve a montar) y la redacción de secretos deja de ser nominal.

**Falsabilidad del bloque técnico:** [audit-pack §7](./audit-pack-v2.88.133-beta-2026-10-15.md) (7 filas) y [`evidence/v2.88.133/README.md` §8](./evidence/v2.88.133/README.md).

---

## 3. Qué NO certifica esta versión (límites declarados — sin fabricar)

1. **La certificación OPERATIVA integral de AUTO sigue ABIERTA.** La **ventana PAPER longitudinal** (`P3-2`/`P3-3`, ADR-046) está **`INCONCLUSIVE`**: `0/4 días`, `0/2 regímenes`, `0/32 ciclos`. Lo que falta es **OPERACIÓN**, no software. Origen: [audit-pack §6](./audit-pack-v2.88.133-beta-2026-10-15.md); [`CHANGELOG.md` límites](../../CHANGELOG.md).
2. **La evidencia por valor de ESTUDIO existe como instrumento, no como material.** El lector durable y el CLI `v2_99` están entregados y probados ([`evidence/v2.88.131/README.md`](./evidence/v2.88.131/README.md)), pero la medición real es **0/35 valores con ciclos medidos** ([`evidencia-readonly-auto-paper-2026-10-14.md` §2.1](./evidencia-readonly-auto-paper-2026-10-14.md)).
3. **El enlace DÍA-D↔ciclo AUTO existe como contrato durable, no como hecho observado.** Tabla `dia_d_cycle_verifications` + enlace entregados en `v2.88.112` ([`plan-v2-88-112-dia-d-enlazado-ciclo-2026-10-11.md`](./plan-v2-88-112-dia-d-enlazado-ciclo-2026-10-11.md)), pero hoy no hay enlace demostrado con un ciclo AUTO real ([`evidencia-readonly-...` §4](./evidencia-readonly-auto-paper-2026-10-14.md)).
4. **El bridge XTB es una frontera de confianza EXTERNA** al repo; el repo fija las condiciones de invocación y la redacción, **no** su implementación.
5. **`G3` residual declarado:** `getattr(<objeto-local>, <variable>)` sobre objeto de datos queda fuera del invariante (límite declarado, no ausencia de barrera) ([`auditoria-aislamiento-ejecucion-xtb-2026-10-14.md`](./auditoria-aislamiento-ejecucion-xtb-2026-10-14.md)).
6. **No ejecutado en local (declarado):** `replay-repro` no es ejecutable en Windows (CRLF/entorno); `dr-verify` y `security` no se pudieron correr por falta de binarios. Se cubren en CI.
7. **Habilitación real:** `AUTO_ORCHESTRATOR_ENABLED`/`AUTO_SIMULATION_WORKER_ENABLED` nacen **OFF** (SIM-only); el default del código se mantiene OFF para preservar `Δ motor = 0`.

**Nota de honestidad (no se reinterpreta):** esto **no** es un juicio de **rentabilidad/magnitud del P&L**; eso queda **NO MEDIDO**.

---

## 4. Verificación propia del sello (frente B) — 7 puntos

Comprobación **estática** del código en el árbol actual (`HEAD` = `5774510f`; `apps`/`packages` idénticos al tag `530fa674`, verificado con `git diff --stat 530fa674 HEAD -- apps packages` = vacío). Resultado: **6 SOSTENIDOS, 1 PARCIAL**.

| # | Afirmación | Estado | Evidencia (`file:line`) |
| --- | --- | --- | --- |
| 1 | `G6`: el filtro se adjunta a los **HANDLERS** (idempotente), cubre `root`/`bolsa_api`/`uvicorn`/`uvicorn.error`/`uvicorn.access`/`lastResort`, y se llama en `lifespan()` y en los 3 workers | **SOSTENIDA** | [`logging_redact.py:111-149`](../../apps/api-python/src/bolsa_api/logging_redact.py); [`main.py:46`,`:169`](../../apps/api-python/src/bolsa_api/main.py); [`scheduler_worker.py:135`](../../apps/api-python/src/bolsa_api/workers/scheduler_worker.py), [`queue_poll_worker.py:81`](../../apps/api-python/src/bolsa_api/workers/queue_poll_worker.py), [`arq_worker.py:104`](../../apps/api-python/src/bolsa_api/workers/arq_worker.py) |
| 2 | Panel FA: guarda de forma `isFundamentalCardDto` en la fuente única y en el segundo camino del panel; mock E2E declara `null` | **SOSTENIDA** | [`use-ensure-instrument-fundamentals.ts:45-53`,`:125`](../../apps/web/src/features/instruments/use-ensure-instrument-fundamentals.ts); [`fundamental-card-panel.tsx:338-340`](../../apps/web/src/features/instruments/fundamental-card-panel.tsx); [`e2e-mock-routes.ts:1284-1285`](../../apps/web/e2e/helpers/e2e-mock-routes.ts) |
| 3 | Helper del sello de ciclo exige fill **COMPLETO** (`status == 'filled'`), no parcial | **SOSTENIDA** | [`test_auto_fill_cycle_seal_pg.py:162`](../../apps/api-python/tests/test_auto_fill_cycle_seal_pg.py) |
| 4 | UI AUTO (3 bloques + vistas) y verificación DÍA-D fail-closed (solo con estrategia **EJECUTADA**), con tests | **SOSTENIDA** | [`auto-operation-story-panel.tsx:454`,`:482`,`:523`](../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx); [`auto-operar-verify-action.tsx:63-65`](../../apps/web/src/features/auto/auto-operar-verify-action.tsx); [`auto-operar-verify-action.test.tsx:105-133`](../../apps/web/src/features/auto/auto-operar-verify-action.test.tsx) |
| 5 | Pin de la ventana PAPER re-anclado al árbol del sello | **PARCIAL** | Ver §5 |
| 6 | CI: `integrated E2E` opt-in (skip por diseño), `replay-repro`, gate `axe` y `certify` existen | **SOSTENIDA** | [`.github/workflows/release-tag-ci.yml:164-167`](../../.github/workflows/release-tag-ci.yml), `:464` (axe), `:1586` (replay-repro), `:1903` (certify) |
| 7 | Tag lightweight ⇒ resuelve directo al commit | **SOSTENIDA** | `git cat-file -t v2.88.133-beta` = `commit` |

---

## 5. Hallazgo de verificación — el pin se re-ancló **después** del tag (punto 5)

- En el **commit del tag** `530fa674`, `WINDOW_CONFIG` **aún** declaraba el pin del sello anterior (`commit:'05dc2d5b'`, `appsHash:'5696698e…'`). Es decir: el commit sellado **no congelaba su propio árbol**; con él, `freezeCheck` habría dado `TREE_MOVED`.
- El re-anclaje al árbol del sello vive en el commit **POST-TAG** `fcfc57f0` (`ops(window)`, `freeze OK`), que fija `commit:'530fa674'`, `appsHash:'07fa362c…'`, `packagesHash:'d48ac37b…'` ([`window-forward.mjs:297-299`](../../scripts/lib/window-forward.mjs)).
- En `HEAD` el pin **coincide** con `git rev-parse HEAD:apps`/`HEAD:packages`.
- **Consecuencia declarada:** un auditor que use el **árbol del tag literal** para este punto obtendrá **NO SOSTENIDA**; el pin es correcto **a partir del commit inmediatamente posterior**. La documentación del sello ya declaraba este orden ("se re-ancla en el commit inmediatamente posterior"), por lo que la afirmación del sello es coherente, pero el **sello no es autocontenido** respecto del pin. No es un defecto de motor ni de operación (`scripts/` no participa del freeze del motor).

---

## 6. Pendientes `P1`-`P4` con criterio falsable

Los `P1`-`P4` son las etiquetas de la revisión externa; se mapean a los artefactos con que el repo ya los rastrea. **Todos son de OPERACIÓN**, no de software.

| Pendiente | Contenido | Estado real hoy | Criterio FALSABLE (qué lo cierra / lo rompe) | Ancla |
| --- | --- | --- | --- | --- |
| **`P1`** | Ventana PAPER real (ADR-046) | `INCONCLUSIVE` — `0/4`·`0/2`·`0/32` | **Cierra** cuando `v2_98` imprime `days≥4`, `episodes≥2`, `measurableCycles≥32`, `missing` **vacío** y `verdict==READY`. **Se rompe** si tras ≥4 días reales siguen `episodes=0` **y** hay ciclos con `cycle_id` (sería hueco de software; hoy no se cumple) | Umbrales [`operability_window.py:88-90`](../../packages/py/application/src/bolsa_application/operability_window.py); criterios [`paper_window_certification.py:167-207`](../../packages/py/application/src/bolsa_application/paper_window_certification.py) |
| **`P2`** | Evidencia por cada valor de ESTUDIO | Instrumento entregado; material `0/35` | **Cierra** cuando `v2_99` sobre la cuenta declarada reporta valores medidos `>0/35` y cadenas que alcanzan `FILL`/`CYCLE_CLOSED` con `pnl.reconciled==true` | [`v2_99_auto_estudio_chain_evidence.py:202-227`](../../apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py); [`auto_chain_durable_reader.py`](../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) |
| **`P3`** | Vincular DÍA-D al ciclo correcto | Mecanismo durable entregado; sin enlace observado | **Cierra** cuando exista una fila real en `dia_d_cycle_verifications` cuyo `cycle_id` case con un ciclo AUTO y `executedVsDiaD.matches != null`. **Se rompe** si el eslabón DÍA-D fabricara veredicto con una sola fuente (`matches` debe ser `null`, no `same`) | [`plan-v2-88-112-...`](./plan-v2-88-112-dia-d-enlazado-ciclo-2026-10-11.md); tabla `053_dia_d_cycle_verifications` |
| **`P4`** | Mantener barreras fail-closed | Barreras `B1`-`B7` **AISLADO**; `G1`-`G6` cerrados (residual `G3` + bridge externo); flags de motor **OFF** | **Se valida** mientras con los *defaults* (`venue=paper`, sin las dos env LIVE) ninguna ruta AUTO/SIM produce `submit` real. **Se rompe** si una ruta por defecto alcanza dinero real o si el `SimOnlyScope` se forja | [`auto_simulation_worker.py` `require_sim_only_scope`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py); [`auditoria-aislamiento-...`](./auditoria-aislamiento-ejecucion-xtb-2026-10-14.md) |

**Regla de cierre común:** cada `P#` se declara **CERRADO** solo con evidencia medida (no con un exit code `0`: los CLIs salen `0` al declarar el hueco, por diseño).

### 6.1 Plan de ejecución por pendiente (comandos reales)

- **`P1`** — precondición `/auto` de freeze; luego un comando por día de pared:
  `git rev-parse HEAD:apps HEAD:packages` (== pin) → `node scripts/window-forward-runner.mjs --dry-run run-day` (`freeze OK`) → `pnpm run window:preflight` → `pnpm run window:run-day` → `pnpm run window:status`, en **≥4 fechas de calendario distintas** y sin forzar régimen (`AUTO_ENGINE_SIM_V2_REGIME` **no** se fija). Cierre: `v2_98` (§6, `P1`).
- **`P2`** — `uv run --no-sync python apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py --account-id 1484e253d2d54645945a6b1d7 --engine-id auto-sim --limit 100 --json --out operability_runs/estudio-chain/estudio-chain.json`; comprobar 9 etapas (`SIGNAL → TOP_N → RISK → RESERVATION → ORDER → FILL → PROTECTION → SETTLEMENT → CYCLE_CLOSED`), identidad **EJECUTADA** y `pnl.reconciled==true`.
- **`P3`** — lanzar «Verificar D→hoy» desde `/auto/operar` y leer el enlace por ciclo (`GET /auto/dia-d-verifications?cycleId=<id>`); cierre falsable `executedVsDiaD.matches != null`.
- **`P4`** — confirmar `BROKER_VENUE=paper`, `SimOnlyScope`, ausencia de doble env LIVE y flags de motor OFF; falsable por `test_live_execution_runtime.py` / `test_a8_m0_live_dry_run_never_submits.py`.

> El `operatorEnv` del runner inyecta hoy **3 flags** ([`window-forward.mjs:307-311`](../../scripts/lib/window-forward.mjs)): `AUTO_ENGINE_SIM_REAL_PRICE=1`, `AUTO_OPERATIONAL_AUDIT=1`, `BROKER_VENUE=paper`. El driver periódico de snapshots longitudinales (`auto_paper_evidence_snapshot`, ADR-046 §8) es **off-by-default** y se enciende como **política de ventana** en el proceso de crons; su campo real es `PAPER_EVIDENCE_SNAPSHOT_ENABLED` ([`config.py:143`](../../packages/py/infrastructure/src/bolsa_infrastructure/config.py)).

---

## 7. Discrepancias documentales detectadas (declaradas, no reinterpretadas)

1. **`dias=42/4` (runbook) vs `dias=0/4` (audit-pack/CHANGELOG/PROJECT_STATE).** El runbook cita una salida previa `dias=42/4 episodios=0/2 ciclos=0/32` ([`plan-ventana-paper-...` §A](./plan-ventana-paper-arranque-operativo-2026-10-14.md)); la medición de hoy para la cuenta declarada es `dias=0/4` (lectura completada, material vacío: `journalEntriesRead=0`). La diferencia está **explicada** en la evidencia read-only ([`evidencia-readonly-...` §3](./evidencia-readonly-auto-paper-2026-10-14.md)); el número más reciente y estricto es `0/4`.
2. **`CERTIFIED` no existe como literal.** El certificador emite `READY`/`INCONCLUSIVE` ([`paper_window_certification.py:190-191`](../../packages/py/application/src/bolsa_application/paper_window_certification.py)); decir "el certificador da `CERTIFIED`" (como hace el plan §D) es impreciso. El criterio de cierre de `P1` debe leerse como `verdict==READY`.
3. **`PAPER_EVIDENCE_SNAPSHOT` vs `PAPER_EVIDENCE_SNAPSHOT_ENABLED`.** El alias desnudo solo figura en docs; el campo de configuración real es `PAPER_EVIDENCE_SNAPSHOT_ENABLED` ([`config.py:143`](../../packages/py/infrastructure/src/bolsa_infrastructure/config.py)).
4. **Encuadre de `P2`/`P3`/`P4`:** el instrumento (`v2_99`/lector durable), el enlace durable DÍA-D↔ciclo (`v2.88.112`) y las barreras fail-closed **ya están entregados y probados**; lo pendiente es **material operativo** y límites **declarados**, no desarrollo. Se redacta así para no sugerir que falta software.
5. **«0 fills con `cycle_id`» no es hueco de software.** La forense clasifica los carriles con material como **artefactos de teardown de tests**, y el sellado `executionId → cycle_id` quedó probado por test hermético ([`evidencia-readonly-...` §11](./evidencia-readonly-auto-paper-2026-10-14.md), §14.b).

---

## 8. Siguiente paso recomendado

El **único** bloqueador medido para arrancar `P1` es el **pin** (ya re-anclado, `freeze OK`) y el **régimen de mercado** (hoy `BEAR_TREND` con LONG vetadas ⇒ día `NO_MEDIDO_REGIMEN`). Por tanto el siguiente paso es **operar**, no programar:

1. Correr `window:run-day` en **≥4 fechas de mercado operables y distintas** y conservar los artefactos (`window:status`, certificados `v2_98`).
2. Re-ejecutar `v2_99`/`v2_98` por día hasta `≥4 días / ≥2 regímenes / ≥32 ciclos` con `cycle_id`.
3. Tras el **primer ciclo real**, verificar el sellado `executionId → sim_fill_finance_context.cycle_id` y el enlace DÍA-D↔ciclo (`P3`).
4. `P4` no requiere acción nueva: solo **mantener OFF** los flags de motor y no introducir rutas que alcancen el bridge con los defaults.

Hasta que (1)-(3) se cumplan con material real, la **certificación OPERATIVA integral de AUTO** se mantiene **NO ALCANZADA** y **así se declara**.
