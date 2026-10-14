# Evidencia `v2.88.132-beta` — cierre de los residuos de aislamiento XTB (`G3` endurecido + `G4`/`G6` cerrados por test hermético y falsable) y arreglo del gate `axe` integrado (primer run real en CI ROJO)

> **Bump:** `2.11.131-beta` → **`2.11.132-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98` y del CLI `v2_99` — **12 scripts** en [`apps/api-python/scripts`](../../../../apps/api-python/scripts/); guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) **1 passed**).
>
> **Naturaleza:** incremento **mixto** — **verificación/tests** (dos suites **herméticas** nuevas: `test_live_order_recovery_isolation.py` y `test_logging_redaction.py`, + endurecimiento del detector AST del invariante AUTO) y **a11y de UI** + **E2E** (gate `axe` integrado). **`Δ motor de decisión = 0`** (no se toca umbral, reparto, `TOP_N`, régimen, selección, protección ni ejecución) · **`Δ decisión = 0`** · **`Δ contrato HTTP = 0`** (no se amplía ningún endpoint; el arreglo de `/history` es solo semántica accesible en la UI) · **SIN migración** (head `053_dia_d_cycle_verifications`). Tag **unsigned**.
>
> **Base:** `v2.88.131-beta`.

---

## 0. Qué cierra (y qué NO)

**Cierra** dos frentes:

1. **Residuos de aislamiento de ejecución XTB** ([`auditoria-aislamiento-ejecucion-xtb-2026-10-14.md`](../../auditoria-aislamiento-ejecucion-xtb-2026-10-14.md) §3/§5/§7): `G3` (`P3`) **ENDURECIDO** (detector de dispatch dinámico **NO literal**) y `G4`/`G6` (`P3`) **CERRADOS** con test **hermético y falsable** (sin PostgreSQL, sin red, `file:line` anclado).
2. **Gate `axe` integrado** ([`deuda-axe-cierre-integrado-2026-10-14.md`](../../deuda-axe-cierre-integrado-2026-10-14.md) §6): el job `playwright-integrated-axe` (gate duro del tag) salió **ROJO** en su primer run real; se diagnosticó la **causa raíz** (precondición de datos de mercado) y se cerró con **fixtures propias en dos niveles** + el arreglo real `scrollable-region-focusable` de `/history` @móvil.

**NO cierra** (se declara): la **ventana PAPER real** (`P3-2`/`P3-3`, ADR-046) ni la **rentabilidad/magnitud** del P&L (son **OPERACIÓN** + medición longitudinal); el **`G3` residual** (`getattr(<objeto-local>, <variable>)` sobre objeto de datos, ~46 falsos positivos); y el límite del gate `axe` (la BD de CI **sin barras** no ve violaciones que solo afloran **con datos**).

---

## 1. Cierre de los residuos de aislamiento XTB (`G3`/`G4`/`G6`)

### 1.1 `G3` ENDURECIDO — dispatch dinámico NO literal en el invariante AST

Núcleo de detección en [`test_a8_m0_auto_live_invariant.py`](../../../../packages/py/application/tests/test_a8_m0_auto_live_invariant.py). El detector pasó de marcar solo formas **literales** a marcar también las **NO literales**:

| Forma detectada | Señal |
| --- | --- |
| `getattr(<receptor módulo importado>, <nombre NO literal>)` (o receptor con identificador = nombre prohibido) | `getattr:dynamic` |
| `importlib.import_module(...)` / `__import__(...)` / `eval(...)` / `exec(...)` con argumento **no literal** | dispatch dinámico |
| Composiciones **estáticas** (`ast.BinOp` `+` / `ast.JoinedStr`) cuyo texto reconstruible es un nombre prohibido | `composed-name:<valor>` |

Helpers: `_string_literal`, `_composed_static_string`, `_module_bound_names`. Fijado por **16 tests unitarios puros** (`TestDynamicDispatchSymbols`). Los barridos del monorepo siguen en **0 hallazgos**.

**Residual declarado.** `getattr(<objeto de datos local>, <variable>)` (p. ej. `getattr(self, field_name)`, `getattr(row, name)`, `getattr(bar, attr)`) queda **fuera**: es indistinguible del acceso dinámico benigno sin análisis de flujo de datos, y marcarlo rompería el barrido con **~46 falsos positivos** sobre el árbol actual. Se declara como **límite del invariante**, no como ausencia de barrera.

### 1.2 `G4` CERRADO — LiveOrderRecoveryWorker: nace ON, read-only, apply financiero fail-closed

Suite NUEVA [`test_live_order_recovery_isolation.py`](../../../../apps/api-python/tests/test_live_order_recovery_isolation.py) (**34 casos**), **hermética** (sin PG, sin red, sin `get_settings` real) que ejercita el código real ([`live_order_recovery_worker.py`](../../../../apps/api-python/src/bolsa_api/background/live_order_recovery_worker.py)):

- `_worker_enabled()` nace **ON** — `LIVE_RECOVERY_WORKER_ENABLED` default `"1"`; solo `0|false|no|off` lo apaga (cualquier otro valor o su ausencia ⇒ ON);
- el worker es **read-only** (AST del módulo real: **cero** `.submit(...)`, **sin** `resolve_broker_adapter` ni `XtbBrokerAdapter`); la única salida de `UNKNOWN` es `query_broker_order`;
- el apply financiero es **fail-closed OFF** — `LIVE_ORDER_RECOVERY_FINANCIAL_APPLY_ENABLED`; SOLO `1|true|yes|on` (case-insensitive) lo enciende.

**Robustez de invocación.** Los 3 tests `async` llevan `@pytest.mark.asyncio` **explícito** porque el job de CI invoca pytest **desde la raíz** con rutas de **varias raíces** (`packages/py/...` + `apps/api-python/tests`), así que el `rootdir` es el repo y el `asyncio_mode = "auto"` de `apps/api-python/pyproject.toml` **no** aplica; sin el marcador los tres caían con `async def functions are not natively supported`.

### 1.3 `G6` CERRADO — redacción de credenciales en logs y en `repr`

Suite NUEVA [`test_logging_redaction.py`](../../../../apps/api-python/tests/test_logging_redaction.py) (**19 casos**) que fija:

- `redact_text` / `RedactFilter` ([`logging_redact.py`](../../../../apps/api-python/src/bolsa_api/logging_redact.py)) sobre `msg`/`args` (tupla y mapping);
- la redacción de `repr(Settings)` y del DSN vía `_redact_dsn_credentials` ([`config.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/config.py));
- que `.gitignore` excluye `.env`.

**Residual declarado.** El **bridge XTB** es una **frontera de confianza EXTERNA** al repo: el repo fija las condiciones de invocación y la redacción, **no** la implementación del bridge.

### 1.4 Evidencia local (salida real de los comandos)

```
$ uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
All checks passed!

$ uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
Success: no issues found in 555 source files

$ uv run --no-sync python -m pytest packages/py/application/tests/test_a8_m0_auto_live_invariant.py -q -p no:randomly
58 passed        # 42 invariante + 16 unit del detector

$ uv run --no-sync python -m pytest packages/py/application/tests/test_a8_m0_auto_live_invariant.py apps/api-python/tests/test_risk_control_auth.py -q -p no:randomly
66 passed        # 58 AST + 8 auth

$ uv run --no-sync python -m pytest apps/api-python/tests/test_live_order_recovery_isolation.py apps/api-python/tests/test_logging_redaction.py -q -p no:randomly
53 passed        # 34 (G4) + 19 (G6)

$ uv run --no-sync python -m pytest packages/py/application/tests/test_a8_m0_auto_live_invariant.py packages/py/application/tests/test_auto_chain_durable_reader.py apps/api-python/tests/test_dia_d_bump_guard.py apps/api-python/tests/test_live_order_recovery_isolation.py apps/api-python/tests/test_logging_redaction.py -q -p no:randomly
125 passed      # invocación MULTI-RAÍZ (rootdir = repo): fija que G4 corre verde con el marcador async

$ uv run --no-sync python scripts/ci/test_selection.py --report
# universo            : 625
# ejecutado por el CI : 625
# NO ejecutado        : 0
#   declarado         : 0
#   SIN DECLARAR      : 0
# entradas obsoletas  : 0

$ uv run --no-sync python -m pytest packages/py/application/tests -q -p no:randomly
2760 passed
```

---

## 2. Arreglo del gate `axe` integrado (primer run real en CI ROJO)

### 2.1 Síntoma (job real)

El job `playwright-integrated-axe` (gate duro del tag, en `certify.needs`) se validó de verdad en el `workflow_dispatch` run **`38598160604`** (job ID **`115970162301`**) y salió **ROJO** en el paso `Run integrated axe E2E`: **`1 failed`** y los otros **62 no ejecutados**. El **guard anti-skip pasó** ⇒ no fue un skip mudo: el fallo es del barrido, no de un `skipped`.

### 2.2 Causa raíz (con dos síntomas)

- El `beforeAll` del barrido **sembraba posición abierta** vía `POST /api/portfolio/trade`, que pasa por el gate de apertura (`check_opening` → **DS-05 frescura de barras**). El CI siembra el catálogo **solo con instrumentos** (`pnpm db:seed` = [`packages/database/prisma/seed.ts`](../../../../packages/database/prisma/seed.ts), **cero barras**) ⇒ **todos** los instrumentos caducados ⇒ `403 risk_veto` ⇒ `beforeAll` roto ⇒ el barrido a11y entero se cae por una **precondición de datos de mercado ajena a la accesibilidad**.
- **Síntoma 2 (flake, no causa):** `GET /paper-desk/daily-report` devolvió `404 Cuenta no encontrada` en el retry (carrera lectura-tras-escritura del fixture Hoy).

### 2.3 Cierre — fixtures en dos niveles, sin `buy`

[`gp-e2e-ui5-0-axe-integrated.spec.ts`](../../../../apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts) deja de consumir los fixtures compartidos y usa fixtures **propias**:

- **Nivel 1 (GATE DURO):** entorno integrado sano + catálogo real **no vacío** + cuentas efímeras (`POST /api/accounts`, prefijos `e2e-v168-*` / `e2e-v167-*`). Ausencia ⇒ **FALLO** (vía `declareGap`), nunca `skipped`.
- **Nivel 2 (enriquecimiento DECLARADO):** `POST /api/workspaces` real para `/trading`; si el entorno no lo permite, el barrido **NO se salta**: mide el estado real y emite `::warning::barrido axe integrado — hueco declarado: …` en el log del job.

Desaparece el `buy` (y con él el veto) y desaparece la lectura de `/paper-desk/daily-report` (y con ella el flake). Commit **`4ee01267`**.

### 2.4 Hallazgo REAL destapado con datos — `scrollable-region-focusable` en `/history` @móvil

```
[/history @móvil 390×844] · scrollable-region-focusable [serious] ×1 —
  Scrollable region must have keyboard access
    .overflow-x-auto
```

Corregido en [`history-page.tsx`](../../../../apps/web/src/features/history/history-page.tsx) (tabla de movimientos y de operaciones): `role="region"` + `aria-label` + `tabIndex={0}` — **mismo criterio** que [`journal-studies-table.tsx`](../../../../apps/web/src/features/decision-journal/journal-studies-table.tsx). Cambio solo de **semántica/teclado**; representación **idéntica**.

### 2.4-bis Segundo hallazgo real en CI: `button-name` del `Dialog` (flake) y cierre

En el `Release tag CI` `workflow_dispatch` run **`38600619089`** (sobre `main`, disparado `2026-10-14T16:44:21Z`, tras el commit `4ee01267`) el job `playwright (integrated axe)` (id **`115978625527`**) salió **ROJO en el intento 1** y **VERDE en el reintento** (conclusión actual del job: `success`):

```
Error: [/trading @desktop] · button-name [critical] ×1 — Buttons must have discernible text
  "html": "<button type=\"button\" class=\"rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground\">"
  selector: .p-1.hover\:text-foreground.rounded
```

**Causa raíz:** el botón de cierre del `Dialog` compartido ([`dialog.tsx`](../../../../apps/web/src/components/ui/dialog.tsx)) es **icono-solo** (`<X className="h-4 w-4" />`) **sin nombre accesible**; su hermano [`slide-over.tsx`](../../../../apps/web/src/components/ui/slide-over.tsx) ya lo tenía (`aria-label="Cerrar panel"`). El barrido de la clase exacta `rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground` da **9 apariciones**, y `dialog.tsx` era la **ÚNICA** sin nombre accesible (`:64`).

**Por qué era flake (real, no falso positivo):** el `Dialog` se monta globalmente ([`platform-shell.tsx`](../../../../apps/web/src/components/layout/platform-shell.tsx)) y solo está en el árbol accesible **si hay un diálogo abierto**; el reintento pasó **precisamente porque el diálogo no estaba abierto** ⇒ rojo **real pero intermitente**. El run global quedó **`in_progress`** (sin cerrar) porque el job `playwright (mock E2E)` quedó **atascado en cola** (infra del runner, ajeno al sello).

**Cierre:** `aria-label="Cerrar"` en el botón de cierre de `dialog.tsx` (**línea 65**), línea única añadida, en el commit del sello. Falsabilidad: si el `Dialog` vuelve a quedar sin nombre accesible, `button-name` rompe el barrido en cuanto un diálogo esté abierto.

**Límite declarado (importante):** el barrido mide el **estado MONTADO** de cada ruta; los **estados modales** (diálogos y slide-overs) solo quedan cubiertos **si ocurren** durante el barrido. **NO** se fuerza la apertura de diálogos ⇒ esta clase de violación puede quedar **latente**. Queda como **deuda declarada** (un leg determinista que abra el `Dialog` compartido y lo barra), **no** como cobertura lograda; **NO** se siembran barras ni workspaces sintéticos en CI.

### 2.5 Evidencia local (salida real)

```
# Barrido INTEGRADO en MODO REQUERIDO (mismo env que el job de CI), con datos reales
$env:E2E_RUN="1"; $env:E2E_INTEGRATION="1"; $env:E2E_ALLOW_DEV_DB="1"; $env:E2E_AXE_REQUIRED="1"
pnpm --filter @bolsa/web exec playwright test gp-e2e-ui5-0-axe-integrated
  Running 32 tests using 8 workers
  32 passed (36.3s)
#   (antes del arreglo de /history: 31 passed + 1 failed = /history @móvil)

$ pnpm --filter @bolsa/web test        → 299 ficheros / 2195 passed
$ pnpm --filter @bolsa/web typecheck   → OK
$ pnpm --filter @bolsa/web lint        → 0 errores / 23 warnings (preexistentes)
$ pnpm exec prettier --check <ficheros tocados> → limpio
```

### 2.6 Límite declarado (honesto)

Con la BD de CI **sin barras**, el barrido integrado mide los **estados ESTRUCTURALES** de las **16 rutas** × {desktop 1366×768, móvil 390×844} = **32 tests**. Las violaciones que solo afloran **CON datos** (como la de `/history`) **no** son visibles desde el job: viven en el hermano **mock** ([`gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`](../../../../apps/web/e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts)) y en la ejecución **local** documentada. **NO** se siembran barras sintéticas en CI (decisión de datos de mercado, ajena a un gate de accesibilidad).

---

## 3. Sello / bump

- Bump `2.11.131-beta` → **`2.11.132-beta`**: `package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97`, del certificador `v2_98` y del CLI `v2_99` (**12 scripts** en `apps/api-python/scripts/`). Guardián [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) → **1 passed**.
- **`Δ motor de decisión = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0`** (no se amplía ningún endpoint; el arreglo de `/history` es solo semántica accesible en la UI) · **SIN migración** (head de alembic `053_dia_d_cycle_verifications`).

---

## 4. Ficheros del sello

- **Nuevos:** [`apps/api-python/tests/test_live_order_recovery_isolation.py`](../../../../apps/api-python/tests/test_live_order_recovery_isolation.py), [`apps/api-python/tests/test_logging_redaction.py`](../../../../apps/api-python/tests/test_logging_redaction.py) y [`docs/engineering/evidence/v2.88.132/README.md`](./README.md).
- **Modificados:** [`test_a8_m0_auto_live_invariant.py`](../../../../packages/py/application/tests/test_a8_m0_auto_live_invariant.py) (endurecimiento `G3` no literal), [`gp-e2e-ui5-0-axe-integrated.spec.ts`](../../../../apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts) (fixtures en dos niveles), [`history-page.tsx`](../../../../apps/web/src/features/history/history-page.tsx) (región de scroll focusable), [`dialog.tsx`](../../../../apps/web/src/components/ui/dialog.tsx) (`aria-label="Cerrar"` en el botón de cierre; 2º hallazgo real en CI, §2.4-bis), `package.json` + `meta.bump` de los 12 CLIs y docs.

---

## 5. Límites declarados (sin fabricar) + falsabilidad

- **`G3` residual.** `getattr(<objeto-local>, <variable>)` sobre un objeto de datos sigue **fuera** del alcance del invariante (límite declarado, no ausencia de barrera).
- **Bridge XTB externo.** Su implementación vive **fuera** del repo (frontera de confianza); el repo fija las condiciones de invocación y la redacción, no el bridge.
- **Gate `axe` integrado.** La BD de CI **sin barras** ⇒ mide estados estructurales; las violaciones que solo afloran con datos no son visibles desde el job (viven en el hermano mock + ejecución local); **no** se siembran barras sintéticas en CI.
- **NO certifica la operación real** ni la rentabilidad: la ventana PAPER y la magnitud del P&L siguen **NO MEDIDAS**.

**Falsabilidad.**
- `G4`: si `_worker_enabled()` dejara de nacer ON, si `financial_apply_enabled()` se encendiera con un valor distinto de `1|true|yes|on`, o si el worker introdujera un `.submit(...)`/`resolve_broker_adapter` (re-POST), `test_live_order_recovery_isolation.py` **rompe**.
- `G6`: si `redact_text` dejara de tapar una credencial, si `repr(Settings)` re-expusiera los secretos, si el DSN dejara de ocultar `user:pass@`, o si `.env` saliera de `.gitignore`, `test_logging_redaction.py` **rompe**.
- `G3`: si una referencia nominal, literal o **construida** (composición estática / `getattr` no literal sobre módulo) dejara de detectarse, `TestDynamicDispatchSymbols` **rompe**.
- Gate `axe`: en modo requerido (`E2E_AXE_REQUIRED=1`) cualquier precondición ausente es **FALLO** explícito, nunca `skipped`; si `/history` perdiera el foco de la región de scroll, el barrido **rompe**.
- Bump: si `meta.bump` de cualquier CLI difiere de `package.json`, el guardián **rompe**.

---

## 6. `Release tag CI` del sello — **se cita en el commit POST-TAG**

**Tag** `v2.88.132-beta`. El **`Release tag CI`** del tag **se cita en el commit POST-TAG** (patrón del repo: el run del tag se publica una vez empujado el tag). **Run de validación previo al sello:** `38600619089` (job `playwright (integrated axe)` id **`115978625527`**), disparado tras el fix **`4ee01267`**: salió **ROJO en el intento 1** por `button-name` en `/trading @desktop` (botón de cierre del `Dialog`, §2.4-bis) y **VERDE en el reintento** (conclusión actual del job: `success`); **el run global quedó sin cerrar** (`in_progress`) porque el job `playwright (mock E2E)` quedó **atascado en cola** (infra del runner, ajeno al sello y a la accesibilidad), y **la causa raíz se cerró** con el arreglo del `Dialog` (`aria-label="Cerrar"`). **Run del gate `axe` que destapó el ROJO inicial:** `38598160604` (job `115970162301`). **Base:** `v2.88.131-beta`.
