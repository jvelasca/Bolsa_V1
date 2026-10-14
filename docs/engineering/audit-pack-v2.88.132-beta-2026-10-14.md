# Audit pack — `v2.88.132-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-14 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.132-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, dónde está la evidencia, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** documento de **evidencia/enlace**, no de producto. **`Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0`** (verificación/tests + a11y de UI + E2E + docs). Tag **unsigned**.
>
> **✅ Estado (POST-TAG):** la **identidad inmutable** del tag (§1: `lightweight` ⇒ commit `49f578408dc094a3db8b29459195032b6eb82f8b`) y el **run de CI del sello** (§4: `38602858232`) ya están **citados**; este pack queda **completo**.

---

## 0. TL;DR — auditar en un comando

```bash
git clone --branch v2.88.132-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

> El `<SHA_DEL_SELLO>` exacto es **`49f578408dc094a3db8b29459195032b6eb82f8b`** (ver §1).

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag** | `v2.88.132-beta` — **lightweight** (**unsigned**) |
| **Objeto de tag** | **no hay objeto de tag** (lightweight: el nombre apunta **directo** al commit) |
| **Commit apuntado** | `49f578408dc094a3db8b29459195032b6eb82f8b` (`v2.88.132 sello: …`; el commit previo del fix del gate `axe` es `4ee01267`; el 2º arreglo —`aria-label` del `Dialog`, §2.4-bis de la evidencia— va en el commit del sello) |
| **Base (tag anterior)** | `v2.88.131-beta` → commit `6fec78b1611f8eb4024e7070cee960d3aec73b8e` |
| **Versión monorepo** | `2.11.132-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `053_dia_d_cycle_verifications` (**sin migración**) |
| **Firma** | **unsigned** |

> **Nota (flujo del repo).** Los sellos de este repo citan el **run del `Release tag CI`** en un **commit POST-TAG** (push del tag + publicación de la evidencia). Aquí, por tanto, la identidad del objeto de tag y el SHA apuntado **se completaron en el commit POST-TAG** (ya citados en §1/§4); todo lo demás es auditable ya.

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.132-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | `git checkout 49f578408dc094a3db8b29459195032b6eb82f8b` (**ver §1**) |
| Ver el árbol en la web | [tree/v2.88.132-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.132-beta) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`evidence/v2.88.132/README.md`](./evidence/v2.88.132/README.md) | Evidencia del sello: cierre de `G3` (endurecido) + `G4`/`G6` (test hermético/falsable), arreglo del gate `axe` integrado, verificación y **límites declarados** |
| 2 | [`CHANGELOG.md` §`2.11.132-beta`](../../CHANGELOG.md) | Nota de release: alcance, deltas, límites y verificación local |
| 3 | [`PROJECT_STATE.md`](./PROJECT_STATE.md) (AsOf `V2.88.132-beta`) | Estado vivo + **agenda funcional** (qué sigue abierto) |
| 4 | [`auditoria-aislamiento-ejecucion-xtb-2026-10-14.md`](./auditoria-aislamiento-ejecucion-xtb-2026-10-14.md) | Auditoría estática de aislamiento XTB: barreras B1–B7, huecos `G1`–`G6` y sus **cierres** (§5/§7) |
| 5 | [`deuda-axe-cierre-integrado-2026-10-14.md`](./deuda-axe-cierre-integrado-2026-10-14.md) | Deuda `axe`: gate integrado, **§6** con el diagnóstico del primer run real ROJO y su cierre, y **§6.7** con el 2º hallazgo (`button-name` del `Dialog`) |
| 6 | [`test_live_order_recovery_isolation.py`](../../apps/api-python/tests/test_live_order_recovery_isolation.py) | Suite hermética `G4` (34 casos): worker ON/read-only, apply financiero fail-closed |
| 7 | [`test_logging_redaction.py`](../../apps/api-python/tests/test_logging_redaction.py) | Suite hermética `G6` (19 casos): redacción de credenciales y DSN |
| 8 | [`test_a8_m0_auto_live_invariant.py`](../../packages/py/application/tests/test_a8_m0_auto_live_invariant.py) | Invariante AST (censo AUTO + spine + detector de **dispatch dinámico NO literal**) |

---

## 4. CI público (citable)

**Run del `Release tag CI` del sello:** [`38602858232`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38602858232) — **VERDE** (~11m19s, `2026-10-14T17:00:00Z` → `17:11:19Z`; **todos los jobs `success`, incluido el agregado `certify`**, con `playwright (integrated E2E, opt-in)` = `skipped` **por diseño**). El **gate duro** `playwright (integrated axe)` (job `115986220473`) queda **`success`** (`17:00:04Z` → `17:03:53Z`) y `replay-repro` **REPRODUCIDO** ⇒ `Δ decisión = 0` confirmado por CI. **Sello CERRADO.**

**Runs reales ya conocidos y citables (referencias del flujo, NO el sello):**

- **`workflow_dispatch` run [`38598160604`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38598160604)** (job ID `115970162301`): **el primer run real del gate `axe` integrado salió ROJO** en el paso `Run integrated axe E2E` (`1 failed` + 62 no ejecutados; el guard anti-skip pasó). Es la **evidencia del síntoma** que motivó el arreglo (§2.1/§2.2 de la evidencia).
- **`workflow_dispatch` run `38600619089`** (job `playwright (integrated axe)` id `115978625527`): disparado **tras el fix `4ee01267`** (validación previa al sello). El job salió **ROJO en el intento 1** por `button-name` en `/trading @desktop` (botón de cierre del `Dialog` sin nombre accesible) y **VERDE en el reintento** (conclusión actual del job: `success`); **el run global CERRÓ VERDE** (`completed`/`success`, 14m16s, `2026-10-14T16:58:37Z`; `playwright (mock E2E)` y `certify` verdes). Causa raíz cerrada con `aria-label="Cerrar"` en [`dialog.tsx`](../../apps/web/src/components/ui/dialog.tsx) (evidencia §2.4-bis).

**Referencia de la base** `v2.88.131-beta`: `Release tag CI` [run `38594446027`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38594446027) — `success` (~13m22s).

---

## 5. Qué **certifica** esta versión

Cierra los **residuos de aislamiento XTB** y arregla el **gate `axe` integrado**, sin tocar motor de decisión, decisión ni contrato HTTP:

- **`G3` ENDURECIDO — el invariante AST ya no es ciego al dispatch dinámico NO literal.** [`test_a8_m0_auto_live_invariant.py`](../../packages/py/application/tests/test_a8_m0_auto_live_invariant.py) marca `getattr(<receptor módulo importado>, <nombre no literal>)` ⇒ `getattr:dynamic`; `importlib.import_module`/`__import__`/`eval`/`exec` con argumento no literal; y **composiciones estáticas** (`ast.BinOp` `+` / `ast.JoinedStr`) que reconstruyen un nombre prohibido ⇒ `composed-name:<valor>` (helpers `_string_literal`/`_composed_static_string`/`_module_bound_names`). Fijado por **16 tests unitarios puros** (`TestDynamicDispatchSymbols`).
- **`G4` CERRADO — LiveOrderRecoveryWorker: nace ON, read-only, apply financiero fail-closed.** [`test_live_order_recovery_isolation.py`](../../apps/api-python/tests/test_live_order_recovery_isolation.py) (**34 casos**) fija que `_worker_enabled()` nace **ON** (`LIVE_RECOVERY_WORKER_ENABLED` default `"1"`), que el worker es **read-only** (AST del módulo real: cero `.submit(...)`, sin `resolve_broker_adapter`/`XtbBrokerAdapter`; `UNKNOWN` solo sale por `query_broker_order`) y que el apply financiero es **fail-closed OFF** (`LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED`, SOLO `1|true|yes|on`).
- **`G6` CERRADO — redacción de credenciales en logs y en `repr`.** [`test_logging_redaction.py`](../../apps/api-python/tests/test_logging_redaction.py) (**19 casos**) fija `redact_text`/`RedactFilter` ([`logging_redact.py`](../../apps/api-python/src/bolsa_api/logging_redact.py)), la redacción de `repr(Settings)` y del DSN ([`config.py`](../../packages/py/infrastructure/src/bolsa_infrastructure/config.py)) y que `.gitignore` excluye `.env`.
- **Gate `axe` INTEGRADO ARREGLADO.** El job `playwright-integrated-axe` (gate duro del tag) salió **ROJO** en su primer run real por una **precondición de datos de mercado** (el `beforeAll` sembraba posición abierta y el gate de apertura `DS-05` vetaba todo instrumento porque la BD de CI no tiene barras); [`gp-e2e-ui5-0-axe-integrated.spec.ts`](../../apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts) usa ahora **fixtures propias en dos niveles** (gate duro + enriquecimiento declarado) y desaparecen el `buy` y la lectura de `/paper-desk/daily-report`. Además, el barrido **con datos** destapó y se corrigió `scrollable-region-focusable` en [`history-page.tsx`](../../apps/web/src/features/history/history-page.tsx). En un **2º run real** (`38600619089`, job `115978625527`) el gate volvió a salir **ROJO en el intento 1** por `button-name` en `/trading @desktop` —el botón de cierre del `Dialog` compartido ([`dialog.tsx`](../../apps/web/src/components/ui/dialog.tsx)) era **icono-solo sin nombre accesible**, único de **9 apariciones** de la clase exacta sin `aria-label`— y **VERDE en el reintento** (flake real: el `Dialog` solo está en el árbol accesible si hay un diálogo abierto); se cerró con `aria-label="Cerrar"` en `dialog.tsx` (línea 65).

**Deltas:** `Δ motor de decisión = 0` · `Δ decisión = 0` · **sin migración** (`053_dia_d_cycle_verifications`) · **`Δ contrato HTTP = 0`** (no se amplía ningún endpoint; el arreglo de `/history` es solo semántica accesible en la UI). Cambio de `packages/py/application/tests` + `apps/api-python/tests` + `apps/web/e2e` + `apps/web/src/features/history` + `package.json`/CLIs + docs.

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **`G3` residual.** `getattr(<objeto-local>, <variable>)` sobre un objeto de datos sigue **fuera** del alcance del invariante (límite declarado, no ausencia de barrera; ~46 falsos positivos si se marcara).
2. **Bridge XTB externo.** El bridge es una **frontera de confianza EXTERNA** al repo; el repo fija las condiciones de invocación y la redacción, no su implementación.
3. **Gate `axe` integrado con BD de CI sin barras.** Mide los **estados estructurales** de 16 rutas × {desktop 1366×768, móvil 390×844} = 32 tests; las violaciones que solo afloran **con datos** (como la de `/history`) **no** son visibles desde el job (viven en el hermano mock y en la ejecución local documentada). **NO** se siembran barras sintéticas en CI. Además, el barrido mide el **estado MONTADO**: los **estados modales** (diálogos/slide-overs) solo quedan cubiertos **si ocurren** durante el barrido (no se fuerza su apertura) ⇒ esa clase de violación —como el `button-name` del `Dialog`— puede quedar **latente** (deuda declarada).
4. **NO cierra la ventana PAPER real** (`P3-2`/`P3-3`, ADR-046) ni la **rentabilidad/magnitud** del P&L: son **OPERACIÓN** + medición longitudinal (≥4 días de calendario, ≥2 regímenes, ≥32 ciclos medibles con `cycle_id`).
5. **Habilitación real:** `AUTO_ORCHESTRATOR_ENABLED`/`AUTO_SIMULATION_WORKER_ENABLED` nacen **OFF** (SIM-only).

---

## 7. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se falsa |
| --- | --- | --- |
| 1 | `_worker_enabled()` nace ON y el apply financiero es fail-closed OFF | `test_live_order_recovery_isolation.py` falla si el default cambia o si el apply se enciende con otro valor |
| 2 | El worker es read-only (sin re-POST) | el AST del módulo falla si aparece un `.submit(...)`/`resolve_broker_adapter`/`XtbBrokerAdapter` |
| 3 | La redacción tapa las credenciales y el DSN | `test_logging_redaction.py` falla si `redact_text`/`repr(Settings)`/`_redact_dsn_credentials` dejan de tapar |
| 4 | El invariante detecta dispatch dinámico NO literal | `TestDynamicDispatchSymbols` falla si una forma literal/construida deja de detectarse |
| 5 | El gate `axe` en modo requerido no se salta | con `E2E_AXE_REQUIRED=1` toda precondición ausente es FALLO, no `skipped` |
| 6 | Sin migración: head `053_dia_d_cycle_verifications` | `alembic heads` (desde `packages/py/infrastructure`) da otro head |
| 7 | `Δ contrato HTTP = 0` | `pnpm --filter @bolsa/web contract:check` falla (OpenAPI desincronizado) |
| 8 | Bump coherente | guardián [`test_dia_d_bump_guard`](../../apps/api-python/tests/test_dia_d_bump_guard.py) falla si un CLI difiere de `package.json` |

---

## 8. Reproducir la verificación (local, sin credenciales)

```bash
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
  packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync python -m pytest packages/py/application/tests -q
uv run --no-sync python -m pytest packages/py/application/tests/test_a8_m0_auto_live_invariant.py \
  apps/api-python/tests/test_risk_control_auth.py -q
uv run --no-sync python -m pytest apps/api-python/tests/test_live_order_recovery_isolation.py \
  apps/api-python/tests/test_logging_redaction.py -q
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
uv run --no-sync python scripts/ci/test_selection.py --report
```

**Barrido `axe` integrado en modo requerido (stack real, env del job):**

```bash
E2E_RUN=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 E2E_AXE_REQUIRED=1 \
  pnpm --filter @bolsa/web exec playwright test gp-e2e-ui5-0-axe-integrated
```

**Resultados medidos de referencia (local):** `ruff` **All checks passed** · `mypy` **no issues in 555 source files** · `test_a8_m0_auto_live_invariant.py` **58 passed** · AST + auth **66 passed** · las dos suites nuevas **53 passed** (34 + 19) · invocación MULTI-RAÍZ de 5 ficheros **125 passed** · censo **625/625 · 0 sin declarar · 0 obsoletas** · `pytest packages/py/application/tests` **2760 passed** · barrido `axe` integrado **32 passed** (36.3s) · `pnpm --filter @bolsa/web test` **299 ficheros / 2195 passed** · `typecheck` **OK** · `lint` **0 errores / 23 warnings** (preexistentes) · guardián de bump **1 passed** (`2.11.132-beta`) · `alembic heads` `053_dia_d_cycle_verifications` (**sin migración**).
