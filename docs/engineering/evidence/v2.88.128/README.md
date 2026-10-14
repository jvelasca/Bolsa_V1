# Evidencia `v2.88.128-beta` — cierre de `G2`/`G3`/`G5` de la auditoría de aislamiento XTB y runbook de la ventana PAPER (los tres ejes son OPERACIÓN, no software)

> **Bump:** `2.11.127-beta` → **`2.11.128-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97` y del certificador `v2_98`; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) verde).
>
> **Naturaleza:** incremento **solo de tests + docs** — **`Δ producto = 0`**, **`Δ decisión = 0`**, **`Δ motor = 0`** · **SIN migración** (head `053_dia_d_cycle_verifications`) · **SIN cambio de contrato HTTP**. Tag **unsigned**.
>
> **Base:** `v2.88.127-beta`.

---

## 1. `G2` + `G3` CERRADOS — el invariante AST cubre TODO el monorepo y detecta dispatch dinámico

**Antes:** el invariante AST acotaba su barrido a `bolsa_application/**` + `apps/*/src` (`G2`) y solo veía referencias **nominales** (import/attr/`.submit`), quedando ciego ante el **dispatch dinámico** (`G3`).

**Ahora** ([`test_a8_m0_auto_live_invariant.py`](../../../../packages/py/application/tests/test_a8_m0_auto_live_invariant.py)):

- **`G2`** — nuevo `test_no_other_package_references_live_money_path` (`:289-313`): censa `packages/py/{analytics,infrastructure,market,domain,ai}/src` (raíces en `_OTHER_PACKAGE_ROOTS`, `:64-70`) con **allowlist invertida VACÍA** (la vía real solo puede vivir en `bolsa_application`).
- **`G3`** — `_dynamic_dispatch_symbols` (`:134-174`; nombres prohibidos en `_FORBIDDEN_DYNAMIC_NAMES`, `:59-61`) marca `getattr(obj, "<nombre prohibido>")`, `importlib.import_module(...)`, `__import__(...)`, `eval(...)`/`exec(...)` y **literales string IGUALES** a los nombres prohibidos.
- `_reference_money` (`:204-211`) **une** el censo nominal con el dinámico ⇒ todo barrido (apps, otros paquetes y spine AUTO) aplica las dos señales.

**Hallazgo:** el invariante ampliado **NO** encontró referencias reales fuera de la allowlist; [`bolsa_analytics/cognitive/broker_adapter.py`](../../../../packages/py/analytics/src/bolsa_analytics/cognitive/broker_adapter.py) solo **menciona** `XtbBrokerAdapter` en su docstring (`:1-6`), sin referenciar la vía real.

**`G3` residual (declarado).** Los nombres **NO literales** (`getattr(mod, var)`, `importlib.import_module(build)`, strings concatenados) siguen fuera del alcance del AST.

**Mapeo criterio → test:** `test_no_other_package_references_live_money_path` (barrido `G2`), `_dynamic_dispatch_symbols` (detector `G3`) y las guardas anti-podredumbre del propio fichero.

---

## 2. `G5` CERRADO — la auth de las rutas de control de riesgo se fija por test

**Antes:** la auditoría **no había verificado** la auth de `POST /api/risk/broker-venue` / `/kill-switch` (`G5`).

**Ahora** ([`test_risk_control_auth.py`](../../../../apps/api-python/tests/test_risk_control_auth.py), 4 tests / **8 casos**): con `APP_PASSWORD` puesto, las tres rutas de control —`POST /kill-switch` ([`risk.py:119`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/risk.py)), `POST /kill-switch/durable-release` (`:135`) y `POST /broker-venue` (`:207`); router `prefix="/risk"` ([`risk.py:49`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/risk.py))— exigen JWT ⇒ **401** sin credencial porque **ninguna** vive en `PUBLIC_PREFIXES`; con JWT válido ⇒ **200**; en dev sin `APP_PASSWORD` la auth está **OFF por diseño** (prod **fail-closed**, [`config.py:243-256`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/config.py)).

El test es **hermético/offline** (`REDIS_URL=""` ⇒ runtime no-op; la única lectura de BD del middleware se sustituye por un doble). **No** se cambia el middleware ni se añade auth: solo se verifica y se fija.

---

## 3. Runbook de la ventana PAPER (ADR-046)

[`plan-ventana-paper-arranque-operativo-2026-10-14.md`](../../plan-ventana-paper-arranque-operativo-2026-10-14.md): **veredicto verificado por lectura de código** — los **tres** ejes (días/regímenes/ciclos medibles) son falta de **OPERACIÓN**, no hueco de software. La cadena AUTO **sí** sella `cycle_id` de punta a punta (`auto_v2_entry.py:1806-1826` → `auto_simulation_worker.py:1739,1773,1800,2753-2770` → `simulated_settlement.py` / `sim_finance_context.py` / `sim_durable_store.py` → columna+índice en `tables.py:2327`) y el escritor/lector de régimen AUTO-10 está cableado (`auto_simulation_worker.py:2989-3032,6853-6887,158`). El `cycle_id=0` observado viene de lanes **manual/legacy** y de que el pipeline V2 **nunca corrió** en la cuenta declarada. El runbook da la secuencia operativa (`pnpm run window:preflight` / `run-day` / `status` / `unlock`) y los criterios falsables (§D).

**Caveat honesto:** **NO** se probó **runtime** contra PostgreSQL; la falsación está en el propio doc (§D/§E).

---

## 4. Verificación (local)

| Comprobación | Resultado |
|--------------|-----------|
| Invariante AST + auth (`uv run --no-sync python -m pytest packages/py/application/tests/test_a8_m0_auto_live_invariant.py apps/api-python/tests/test_risk_control_auth.py -q`) | **49 passed** (41 AST + 8 auth) |
| Censo de selección (`uv run --no-sync python scripts/ci/test_selection.py --report`) | **universo 621 / ejecutado 621 / NO ejecutado 0 / declarado 0 / SIN DECLARAR 0 / obsoletas 0** |
| Guardas de censo + bump (`... python -m pytest apps/api-python/tests/test_ci_test_selection_census.py apps/api-python/tests/test_dia_d_bump_guard.py -q`) | **6 passed** |
| `ruff check packages/py/application/tests/test_a8_m0_auto_live_invariant.py` | **All checks passed!** |
| Guardián de bump (`uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q`) | **1 passed** (`2.11.128-beta`) |
| `grep` de `2.11.127-beta` tras el bump | Solo en documentos **históricos** (entrada `CHANGELOG` de `2.11.127-beta`, `PROJECT_STATE` de `v2.88.127`, `evidence/v2.88.127` y `audit-pack-v2.88.127`), **ninguno** ligado al bump |
| Suites completas `ruff`/`mypy`/`pytest`, `pnpm --filter @bolsa/web test`, `contract:gen`/`contract:check` | **NO ejecutado localmente** en esta pasada (sellado de tests + docs); los cubre el `Release tag CI` del tag |

---

## 5. Límites declarados (sin fabricar) + falsabilidad

- **`G3` residual:** los nombres **NO literales** (`getattr(mod, var)`, `importlib.import_module(build)`, strings concatenados) siguen fuera del alcance del AST; declarado, no cerrado.
- **`G4`/`G6` CONFIRMADOS/declarados** (verificados hoy, **readonly**, **no** cerrados): el recovery worker nace **ON** pero es **read-only** ([`live_order_recovery_worker.py:74-76`](../../../../apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py); read-only declarado en `:17-19`) con el apply financiero **fail-closed OFF** (`:86-93`); y no hay fugas de credenciales en el repo (`.gitignore` excluye `.env`; [`logging_redact.py`](../../../../apps/api-python/src/bolsa_api/logging_redact.py); [`config.py:292-321`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/config.py); bridge XTB externo).
- **Ventana PAPER: sigue `NO MEDIDO`.** El runbook describe los bloqueadores, que son de **OPERACIÓN** (≥4 días de calendario, ≥2 regímenes, ≥32 ciclos medibles con `cycle_id`).
- **Caveat:** **no** se probó **runtime** contra PostgreSQL; la falsación está en el propio runbook (§D/§E).

**Falsabilidad.**

- **`G2`/`G3`:** si un módulo de `packages/py/{analytics,infrastructure,market,domain,ai}/src` referenciara la vía real (nominal o por dispatch dinámico **literal**), `test_no_other_package_references_live_money_path` **rompe**.
- **`G5`:** si alguna de las tres rutas entrara en `PUBLIC_PREFIXES`, o si dejara de exigir JWT con auth ON, `test_risk_control_auth.py` **rompe**.
- **PAPER:** re-ejecutar el certificador `v2_98` sobre la BD real; en cuanto cualquier cuenta acumule **≥4 días de calendario** con **≥2 regímenes** y **≥32 ciclos con `cycle_id`**, el certificado **deja** de ser `INCONCLUSIVE`.

---

## 6. `Release tag CI` del sello — **VERDE**

**Tag** `v2.88.128-beta` (anotado, unsigned) ⇒ objeto `b347d76ab5b20073b7eed714aacce9d24cdc82e8` ⇒ commit `0d0a8c153831cba79fe06c89196d115a90ada656`. **Base:** `v2.88.127-beta` (`38c26ae9`).

**`Release tag CI`:** [run **38560567905**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38560567905) — **`success`** en **~11m56s** (2026-10-14T12:00:07Z → 12:12:03Z). Jobs decisivos: `replay-repro` = `success` (el artefacto congelado se reproduce ⇒ `Δ decisión = 0`), `lifecycle-pg` = `success` (el nuevo `test_risk_control_auth.py` pasa contra el stack real), `python (offline)` = `success` (recoge el invariante AST ampliado por commit). `playwright (integrated E2E, opt-in)` = `skipped` por diseño.

**Artefactos:** `release-tag-ci-summary` (429 B, id `11893430893`) y `replay-oos-durable-v2.88.7` (306 720 B, id `11891634452`).

Audit pack POST-TAG: [`audit-pack-v2.88.128-beta-2026-10-14.md`](../../audit-pack-v2.88.128-beta-2026-10-14.md).
