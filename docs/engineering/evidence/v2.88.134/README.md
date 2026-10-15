# Evidencia `v2.88.134-beta` — respuesta a la auditoría externa del sello `v2.88.133-beta` (verificación propia del sello y trazado de los pendientes operativos `P1`-`P4`)

> **Bump:** `2.11.133-beta` → **`2.11.134-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98` y del CLI `v2_99` — **12 scripts** en [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **1 passed**).
>
> **Naturaleza:** incremento **de documentación + bump de versión** (`meta.bump` de 12 CLIs) — **no** toca motor, decisión, contrato HTTP ni esquema. Se añade el **documento de respuesta a la auditoría externa** y se **enlaza** desde el estado vivo y el audit-pack del sello anterior. · **`Δ motor de decisión = 0`** · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (no se amplía ningún endpoint) · **SIN migración** (head `053_dia_d_cycle_verifications`). Tag **unsigned**.
>
> **Base:** `v2.88.133-beta`.

---

## 0. Qué cierra (y qué NO)

**Cierra** dos frentes documentales:

1. **Respuesta a la revisión externa del sello `v2.88.133-beta`**: documento único de respuesta con identidad del sello, qué certifica / qué NO, y respuesta **punto por punto** al veredicto externo (todos **ACEPTO**).
2. **Verificación propia del sello** (frente B) sobre el código real: **6 de 7 afirmaciones SOSTENIDAS**, con **una PARCIAL** (el pin de la ventana se re-ancló en commit **POST-TAG**, no en el commit sellado). Se trazó también el **plan operativo** de los pendientes `P1`-`P4` con criterio **falsable**.

**NO cierra** (se declara): la **ventana PAPER real** (`P3-2`/`P3-3`, ADR-046) — lo que falta es **OPERACIÓN**, no software — ni la rentabilidad/magnitud del P&L.

---

## 1. Documento de respuesta a la auditoría externa

Nuevo: [`docs/engineering/respuesta-auditoria-v2.88.133-beta-2026-10-15.md`](../../respuesta-auditoria-v2.88.133-beta-2026-10-15.md). Contenido:

- **§0 Veredicto de una línea:** se **acepta** el veredicto externo — sello técnico **VERDE** (lo respalda el `Release tag CI` [run `38704219628`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38704219628)) y **certificación OPERATIVA de AUTO ABIERTA por falta de OPERACIÓN**, no de software. **No se refuta ningún punto.**
- **§1-§3** Identidad inmutable del sello · qué certifica (en su alcance declarado) · qué NO certifica (límites declarados sin fabricar).
- **§4 Verificación propia del sello (frente B):** 7 puntos con evidencia `file:line`.
- **§5 Hallazgo:** el pin de la ventana se re-ancló **después** del tag.
- **§6 Pendientes `P1`-`P4`** con criterio **falsable** + comandos reales.
- **§7 Discrepancias documentales** declaradas (`dias=42/4` vs `0/4`; `READY`/`INCONCLUSIVE`; `PAPER_EVIDENCE_SNAPSHOT_ENABLED`).
- **§8 Siguiente paso** (operación, no programación).

---

## 2. Verificación propia del sello (frente B) — 6 SOSTENIDAS, 1 PARCIAL

Comprobación **estática** sobre el árbol del sello (`apps`/`packages` de `HEAD` idénticos al tag `530fa674`; `git diff --stat 530fa674 HEAD -- apps packages` = vacío).

| # | Afirmación | Estado | Evidencia (`file:line`) |
| --- | --- | --- | --- |
| 1 | `G6` a nivel de **HANDLER**: el `RedactFilter` se adjunta a los handlers (`root`/`bolsa_api`/`uvicorn`/`uvicorn.error`/`uvicorn.access`/`lastResort`); se llama en `lifespan()` y en los 3 workers | **SOSTENIDA** | [`logging_redact.py:111-149`](../../../../apps/api-python/src/bolsa_api/logging_redact.py); [`main.py:46`,`:169`](../../../../apps/api-python/src/bolsa_api/main.py); [`scheduler_worker.py:135`](../../../../apps/api-python/src/bolsa_api/workers/scheduler_worker.py), [`queue_poll_worker.py:81`](../../../../apps/api-python/src/bolsa_api/workers/queue_poll_worker.py), [`arq_worker.py:104`](../../../../apps/api-python/src/bolsa_api/workers/arq_worker.py) |
| 2 | Panel FA robusto ante un payload que viola `FundamentalCardDto` (guarda `isFundamentalCardDto` + normalización; mock E2E declara `null`) | **SOSTENIDA** | [`use-ensure-instrument-fundamentals.ts:45-53`](../../../../apps/web/src/features/instruments/use-ensure-instrument-fundamentals.ts), [`fundamental-card-panel.tsx:338-340`](../../../../apps/web/src/features/instruments/fundamental-card-panel.tsx), [`e2e-mock-routes.ts:1284-1285`](../../../../apps/web/e2e/helpers/e2e-mock-routes.ts) |
| 3 | Helper del sello de ciclo exige fill **COMPLETO** (`status == 'filled'`) | **SOSTENIDA** | [`test_auto_fill_cycle_seal_pg.py:162`](../../../../apps/api-python/tests/test_auto_fill_cycle_seal_pg.py) |
| 4 | UI AUTO (3 bloques + vistas) y verificación DÍA-D fail-closed (solo con estrategia **EJECUTADA**), con tests | **SOSTENIDA** | [`auto-operation-story-panel.tsx:454`](../../../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx); [`auto-operar-verify-action.tsx:63-65`](../../../../apps/web/src/features/auto/auto-operar-verify-action.tsx); [`auto-operar-verify-action.test.tsx:105-133`](../../../../apps/web/src/features/auto/auto-operar-verify-action.test.tsx) |
| 5 | Pin de la ventana PAPER re-anclado al árbol del sello | **PARCIAL** | §3 |
| 6 | CI: `integrated E2E` opt-in (skip por diseño), `replay-repro`, gate `axe`, `certify` | **SOSTENIDA** | [`.github/workflows/release-tag-ci.yml:164-167`](../../../../.github/workflows/release-tag-ci.yml), `:464`, `:1586`, `:1903` |
| 7 | Tag lightweight ⇒ resuelve directo al commit | **SOSTENIDA** | `git cat-file -t v2.88.133-beta` = `commit` |

---

## 3. Hallazgo — el pin se re-ancló **después** del tag (punto 5, PARCIAL)

- En el **commit del tag** `530fa674`, `WINDOW_CONFIG` **aún** declaraba el pin del sello anterior (`commit:'05dc2d5b'`, `appsHash:'5696698e…'`). El commit sellado **no congelaba su propio árbol**; con él, `freezeCheck` habría dado `TREE_MOVED`.
- El re-anclaje vive en el commit **POST-TAG** `fcfc57f0` (`ops(window)`, `freeze OK`), que fija `commit:'530fa674'`, `appsHash:'07fa362c…'`, `packagesHash:'d48ac37b…'` ([`window-forward.mjs:297-299`](../../../../scripts/lib/window-forward.mjs)).
- En `HEAD` el pin **coincide** con `git rev-parse HEAD:apps`/`HEAD:packages` ⇒ **freeze OK**.
- **Consecuencia declarada:** un auditor que use el **árbol del tag literal** para este punto obtendrá **NO SOSTENIDA**; el pin es correcto a partir del commit inmediatamente posterior. No es defecto de motor ni de operación (`scripts/` **no** participa del freeze del motor).

> **Nota sobre este sello.** Aunque **no** hay cambio de producto, el **`meta.bump` de los 12 CLIs vive en `apps/api-python/scripts/`**, que **sí** pertenece al árbol `apps`: al commitear el sello, `HEAD:apps` pasa de `07fa362c…` a **`86052343…`** (`packages` **no** cambia: `d48ac37b…`). Por eso el pin **sí** se mueve y se **re-ancla en el commit POST-TAG** a `commit:'7cef7fcc'`, `appsHash:'86052343…'`, `packagesHash:'d48ac37b…'` ([`window-forward.mjs`](../../../../scripts/lib/window-forward.mjs)); `scripts/` no participa del pin, así que re-anclar no mueve a su vez el árbol. El campo `commit` del pin es una etiqueta; el contraste real del freeze son los dos tree hashes.

---

## 4. Pendientes `P1`-`P4` (OPERACIÓN) y criterio falsable

| Pendiente | Criterio FALSABLE (cierra / rompe) | Ancla |
| --- | --- | --- |
| **`P1`** Ventana PAPER real (ADR-046) | **Cierra** con `v2_98` → `days≥4`, `episodes≥2`, `measurableCycles≥32`, `missing` vacío y `verdict==READY`. **Rompe** si tras ≥4 días reales siguen `episodes=0` **y** hay ciclos con `cycle_id` | Umbrales [`operability_window.py:88-90`](../../../../packages/py/application/src/bolsa_application/operability_window.py); criterios [`paper_window_certification.py:167-207`](../../../../packages/py/application/src/bolsa_application/paper_window_certification.py) |
| **`P2`** Evidencia por valor de ESTUDIO | **Cierra** cuando `v2_99` reporta valores medidos `>0/35` y cadenas que alcanzan `FILL`/`CYCLE_CLOSED` con `pnl.reconciled==true` | [`v2_99_auto_estudio_chain_evidence.py:202-227`](../../../../apps/api-python/scripts/v2_99_auto_estudio_chain_evidence.py); [`auto_chain_durable_reader.py`](../../../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) |
| **`P3`** Vincular DÍA-D al ciclo correcto | **Cierra** con una fila real en `dia_d_cycle_verifications` cuyo `cycle_id` case con un ciclo AUTO y `executedVsDiaD.matches != null` | [`plan-v2-88-112-...`](../../plan-v2-88-112-dia-d-enlazado-ciclo-2026-10-11.md); tabla `053_dia_d_cycle_verifications` |
| **`P4`** Barreras fail-closed | **Se valida** mientras con los *defaults* (`venue=paper`, sin las dos env LIVE) ninguna ruta AUTO/SIM produce `submit` real | [`auto_simulation_worker.py`](../../../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py); [`auditoria-aislamiento-...`](../../auditoria-aislamiento-ejecucion-xtb-2026-10-14.md) |

**Regla de cierre común:** cada `P#` se declara **CERRADO** solo con evidencia medida (un exit code `0` **no** es certificación: los CLIs salen `0` al declarar el hueco).

---

## 5. Estado medido de la ventana (preflight de hoy, 2026-10-15)

- **Pin/freeze:** `HEAD:apps` = `07fa362c…` = pin; `HEAD:packages` = `d48ac37b…` = pin ⇒ **freeze OK**.
- **API:** `/api/health/ready` → `status: ready`, esquema en head `053_dia_d_cycle_verifications`, PostgreSQL **OK**.
- **Ledger de la ventana:** `medidos=0 veto=1 declarados=0 duros=0`, gate `NO_MEDIDO` (un día registrado: `20261014` `NO_MEDIDO_REGIMEN`).
- **Preflight de HOY:** `operationalRegime = BEAR_TREND`, `entriesAllowedLong = false` ⇒ **LONG VETADAS** (exit 2 declarado). `window:run-day` **no** produciría un día medible. Es el **mismo bloqueo** que el 2026-10-14: es de **MERCADO**, no de software.

> **Consecuencia:** `P1` no puede avanzar con el mercado en veto y `P2`/`P3` dependen de `P1`. Lo que falta es **operar** en ≥4 fechas de calendario con LONG permitidas.

---

## 6. Evidencia de verificación (local)

```
guardián de bump .............................. 1 passed (2.11.134-beta)
```

**No ejecutado en local (declarado):** `replay-repro` no es ejecutable en Windows (CRLF/entorno); `dr-verify` y `security` no se pudieron correr en local (faltan binarios). Se cubren en CI.

---

## 7. Sello / bump

- Bump `2.11.133-beta` → **`2.11.134-beta`**: `package.json` + `meta.bump` de los 12 CLIs. Guardián [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) → **1 passed**.
- **`Δ motor de decisión = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0`** (no se amplía ningún endpoint) · **SIN migración** (head `053_dia_d_cycle_verifications`).

---

## 8. Ficheros del sello

- **Nuevos:** [`docs/engineering/evidence/v2.88.134/README.md`](./README.md) y el documento de respuesta [`docs/engineering/respuesta-auditoria-v2.88.133-beta-2026-10-15.md`](../../respuesta-auditoria-v2.88.133-beta-2026-10-15.md); el audit-pack POST-TAG [`audit-pack-v2.88.134-beta-2026-10-15.md`](../../audit-pack-v2.88.134-beta-2026-10-15.md).
- **Modificados:** `package.json` + `meta.bump` de los 12 CLIs; [`CHANGELOG.md`](../../../../CHANGELOG.md); [`PROJECT_STATE.md`](../../PROJECT_STATE.md); [`audit-pack-v2.88.133-beta-2026-10-15.md`](../../audit-pack-v2.88.133-beta-2026-10-15.md) (traza de la revisión externa).

---

## 9. Límites declarados (sin fabricar) + falsabilidad

- **Ventana PAPER real (ADR-046):** sigue **`0/4 días`, `0/2 regímenes`, `0/32 ciclos` ⇒ `INCONCLUSIVE`**. Lo que falta es **OPERACIÓN**, no software. Hoy y ayer el mercado (**BEAR_TREND**) veta LONG.
- **Este sello es docs-only:** no reclama ningún cambio de producto; su valor es la **trazabilidad** de la respuesta a la auditoría externa.

**Falsabilidad.**
- Si `meta.bump` de cualquier CLI difiere de `package.json`, el guardián **rompe**.
- Si `/api/health/ready` no está `ready` o el esquema no está en head `053`, el preflight/`run-day` lo declara.
- El resto de afirmaciones técnicas se falsan como en [`evidence/v2.88.133/README.md` §8](./../v2.88.133/README.md).

---

## 10. `Release tag CI` del sello

**Tag** `v2.88.134-beta` (**lightweight**, unsigned) ⇒ apunta **directamente** al commit del sello **`7cef7fcce0befbae54bd2e6062e357f116c0c3f4`**. El `Release tag CI` del tag, [run **`38708375980`**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38708375980), salió **VERDE** (~14m30s, `2026-10-15T08:49:03Z` → `09:03:33Z`; **todos los jobs `success`**, incluido `certify`, con `playwright (integrated E2E, opt-in)` = `skipped` por diseño; el gate duro `playwright (integrated axe)` **`success`**; `replay-repro` **REPRODUCIDO** ⇒ `Δ decisión = 0` confirmado por CI). El **re-anclaje del pin** (`WINDOW_CONFIG`) se aplica en el commit **POST-TAG** (`freeze OK`). **Base:** `v2.88.133-beta`.
