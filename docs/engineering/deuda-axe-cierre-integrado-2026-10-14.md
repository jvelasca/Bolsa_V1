# Deuda `axe` «solo con mocks» — barrido INTEGRADO promovido a GATE DURO del tag, cierre del censo MOCK y 2 arreglos reales — 2026-10-14

> **Alcance:** `apps/web/e2e/**`, `apps/web/src/**` (a11y de componentes que toca el
> barrido), `.github/workflows/release-tag-ci.yml` y este documento. **Sin** bump de
> versión, **sin** commit, **sin** push. No se tocan `.github/workflows/**` distintos de
> `release-tag-ci.yml`, `CHANGELOG.md`, `PROJECT_STATE.md`, `package.json`,
> `audit-pack-*`, `auditoria-aislamiento-*` ni `evidence/**`.

## 1. Veredicto

- **La deuda «barrido `axe` INTEGRADO desktop-only / acotado a 5 rutas» queda CERRADA**: el
  barrido integrado cubre **16 rutas L1 × {desktop 1366×768, móvil 390×844} = 32 tests**,
  **verde** contra el stack real (FastAPI + PostgreSQL).
- **La deuda global «`axe` solo con mocks» queda CERRADA en su eje de GATE**: el barrido
  integrado **deja de ser opt-in y pasa a GATE DURO del tag** (`playwright-integrated-axe`,
  en `certify.needs`), con `E2E_AXE_REQUIRED=1` y guard anti-skip. El gate duro del tag ya
  **no** mide únicamente con mocks.
- **La cobertura MOCK del censo L1 no-AUTO queda COMPLETA**: el barrido mock pasa a
  **17 rutas × 2 viewports + command palette = 35 tests**, **verde**. Se mantiene como gate
  del job mock (mide sin stack real).

## 2. Qué cambió (con falsabilidad)

### 2.1 Barrido INTEGRADO ampliado — `apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts`

- **Añadido el viewport MÓVIL (390×844)** para todas las rutas (antes: solo desktop 1366×768).
  El bucle es ahora `ROUTES × VIEWPORTS`; `/trading` espera el cockpit solo en `≥ md` (en móvil
  el cockpit DECISIÓN está oculto) y usa la tira de salud como señal de montaje.
- **Añadidas 11 rutas L1** del censo mock alcanzables contra el stack real (sin `install*Mocks`):
  `/mesa?view=posiciones`, `/overview`, `/accounts`, `/fiscal`, `/screeners`, `/alerts`,
  `/research`, `/history`, `/backtests`, `/instruments` e `/instruments/:id` (este último con
  el `id` real del catálogo vía fixture Mercado).
- Se pasa el viewport a `ready(page, vp)`, se añade `pathFor(fixtures)` (para `/instruments/:id`)
  y `expectMain` (el `main` de `/backtests` es el host keep-alive del shell).

Rutas integradas finales (16): `/operational-console`, `/decision-journal`, `/mesa`,
`/mesa?view=posiciones`, `/trading`, `/auto-monitor?mode=current`, `/overview`, `/accounts`,
`/fiscal`, `/screeners`, `/alerts`, `/research`, `/history`, `/backtests`, `/instruments`,
`/instruments/:id`.

### 2.2 Barrido MOCK completado — `apps/web/e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts`

- Añadidas las 3 rutas L1 que faltaban del censo **no-AUTO**: `/instruments`,
  `/instruments/:id` (con `installMercadoApiMocks`) y `/decision-journal` (con `installApiMocks`).
- Con esto el censo no-AUTO queda cubierto al completo (el espacio AUTO tiene su propio barrido
  mock `gp-e2e-v28865-auto-axe-mock.spec.ts`).

### 2.3 Arreglo REAL 1 — `scrollable-region-focusable` en `/decision-journal` @móvil

- **Fallo reproducido** (falsabilidad) al añadir `/decision-journal` al barrido mock:

  ```
  Error: [/decision-journal @móvil 390×844] · scrollable-region-focusable [serious] ×1 —
         Scrollable region must have keyboard access
      .h-full.min-h-0.overflow-hidden > .overflow-auto.min-h-0.flex-1
  ```

  El contenedor scrolleable de la tabla de estudios (`apps/web/src/features/decision-journal/
  journal-studies-table.tsx`) desbordaba en 390×844 y no era alcanzable por teclado (ni sus
  descendientes eran focusables en ese layout).
- **Fix:** la región de scroll gana `role="region"`, `aria-label="Estudios del Decision
  Journal"` y `tabIndex={0}` — **mismo criterio** ya aplicado a `/backtests`
  (`backtests-page-run-tab.tsx`) y a `operations-panel.tsx`. Cambio **solo de semántica/teclado**;
  representación visual idéntica.
- **Verificación:** el mismo test pasa tras el fix (evidencia §3).

### 2.4 Arreglo REAL 2 (habilitador del barrido) — `meta` en el mock de instrumento suelto

- **Fallo reproducido** al añadir `/instruments/:id` al barrido mock: la ficha revienta en el
  error boundary —

  ```
  heading "Algo falló en la interfaz" [level=1]
  paragraph: Cannot read properties of undefined (reading 'priceSummary')
  ```

  El mock de `/api/instruments/:id` no devolvía `meta`, pero `InstrumentDetailResponseDto`
  exige `meta` (`priceSummary`/`lastSync`). Sin arreglo, el barrido axe **nunca** veía la
  jerarquía real de la ficha.
- **Fix:** `apps/web/e2e/helpers/e2e-mock-routes.ts` — el mock de instrumento suelto añade
  `meta: { lastSync, priceSummary }`. Tras el fix la ficha monta su `h1` y el barrido corre.

### 2.5 Fixture integrado determinista — `apps/web/e2e/helpers/database.ts`

- **Fallo reproducido:** el seed integrado de posición fallaba de forma **no determinista** con
  `POST /api/portfolio/trade failed (403): {"detail":"risk_veto"}`. Causa: el helper escogía
  `instruments[0]` a ciegas y el catálogo real puede traer instrumentos vetados por **DS-05**
  (p. ej. ACS con un salto del +802 % hoy → `sanity_opening_veto_reason`).
- **Fix:** nuevo `selectOpenableInstrument()` que prefiltra por `GET /api/instruments/:id/data-status`
  con el **mismo criterio del gate**: sin advertencia `movimiento`/`split` y con `lastBarDate`
  ≤ 5 días (alineado con `DATA_FRESHNESS_MAX_AGE_SECONDS` / `EOD_STALE_MAX_DAYS`). Beneficia a
  los 3 specs que consumen el fixture (`gp-v167`, `gp-v170` y este).
- **Nota:** es un endurecimiento del **fixture E2E**, no de la lógica de producto ni del gate.

### 2.6 Modo REQUERIDO del barrido integrado — `E2E_AXE_REQUIRED=1` (2026-10-14, promoción a gate duro)

- En `apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts` se añade el espejo exacto del patrón
  `E2E_S5_REQUIRED` del puente AUTO S5:

  ```ts
  function axeRequired(): boolean {
    return process.env.E2E_AXE_REQUIRED === "1";
  }
  function declareGap(reason: string): void {
    if (axeRequired()) {
      throw new Error(`E2E_AXE_REQUIRED=1: precondición del barrido axe integrado ausente — ${reason}`);
    }
    test.skip(true, reason);
  }
  ```

- `beforeEach` usa `declareGap(environmentSkip)` (en vez de `test.skip(...)`) y el camino de
  «fixtures no alcanzables» pasa a ser **FALLO explícito** en modo requerido. Con
  `E2E_AXE_REQUIRED=1`, CUALQUIER precondición ausente (entorno integrado no disponible o
  fixtures/rutas no alcanzables) es **FALLO**, nunca `skipped`.
- **Falsabilidad (contraste real):**
  - Sin `E2E_AXE_REQUIRED` (default, sin `E2E_INTEGRATION`): `32 skipped`, exit 0.
  - Con `E2E_AXE_REQUIRED=1` (sin `E2E_INTEGRATION`): **FALLO** por cada test, con el mensaje
    `E2E_AXE_REQUIRED=1: precondición del barrido axe integrado ausente — …`, exit ≠ 0.

### 2.7 Nuevo job GATE DURO — `playwright-integrated-axe` (`.github/workflows/release-tag-ci.yml`)

- Nuevo job `playwright-integrated-axe` (`name: playwright (integrated axe)`) que **replica la
  estructura exacta** de `playwright-integrated-auto-s5`: mismo runner `ubuntu-latest`, mismo
  service `postgres:16-alpine` (bolsa/bolsa_dev/bolsa_v1, 5432), mismo `env` de BD/JWT y los
  mismos steps de preparación (checkout@v5 → pnpm/action-setup@v5 10.12.1 → setup-node@v5
  node 22 + cache pnpm → astral-sh/setup-uv@v5 → `pnpm install --frozen-lockfile` → `uv sync`
  → exponer `.venv/bin` en `$GITHUB_PATH` → `@bolsa/shared build` → `.env` → `alembic upgrade
  head` → `db:generate` + `db:seed` → arranque de API con bucle de health → instalar chromium).
- Sus dos steps finales, espejo del guard de S5:
  - `Run integrated axe E2E (fail if skipped)` — `working-directory: apps/web`, env
    `E2E_RUN=1 E2E_INTEGRATION=1 E2E_ALLOW_DEV_DB=1 E2E_AXE_REQUIRED=1`, `set -o pipefail` y
    `pnpm exec playwright test gp-e2e-ui5-0-axe-integrated | tee /tmp/axe-integrated.log`.
  - `Fail on skipped axe integrated (no skip silencioso)` — `if: always()`; falla si
    `/tmp/axe-integrated.log` está vacío (`! -s`) o contiene `skipped`/`SKIPPED`.
- **Bloquea el tag:** el job está en `certify.needs`, en la condición `Fail if any required job
  failed`, en los `echo` de diagnóstico, en las env `JOB_PLAYWRIGHT_INTEGRATED_AXE` y en el
  JSON `jobs` del summary artifact.
- **Sin duplicar:** se **quita** `gp-e2e-ui5-0-axe-integrated` del comando del job opt-in
  `playwright-integrated` (queda con `gp-v164-ui gp-v167 gp-v168 gp-v170-list gp-v187
  gp-v288-s5`), porque su medición ahora vive en el job gate.

## 3. Evidencia (salida REAL de los comandos)

```
# Barrido MOCK (API mockeada, Vite auto-reuse)
$env:E2E_RUN="1"; pnpm --filter @bolsa/web e2e -- gp-e2e-ui5-0-axe-touched-routes-mock
  Running 35 tests using 8 workers
  35 passed (32.2s)

# Barrido INTEGRADO (FastAPI + PostgreSQL reales), MODO REQUERIDO (gate duro del tag)
$env:E2E_RUN="1"; $env:E2E_INTEGRATION="1"; $env:E2E_ALLOW_DEV_DB="1"; $env:E2E_AXE_REQUIRED="1"
pnpm --filter @bolsa/web exec playwright test gp-e2e-ui5-0-axe-integrated
  Running 32 tests using 8 workers
  32 passed (40.1s)

# Falsabilidad del modo requerido (contraste, sin stack integrado declarado):
#   sin E2E_AXE_REQUIRED  → 32 skipped            (exit 0)
#   con E2E_AXE_REQUIRED=1 → FALLO por test       (exit ≠ 0)
#     "E2E_AXE_REQUIRED=1: precondición del barrido axe integrado ausente — Set E2E_INTEGRATION=1…"

# Validación del workflow (YAML carga + cableado del gate)
$ python -c "import yaml; d=yaml.safe_load(open('.github/workflows/release-tag-ci.yml',encoding='utf-8')); print(len(d['jobs'])); print(d['jobs']['certify']['needs'])"
  14
  ['security','shared','spine','frontend','python','playwright-mock',
   'playwright-integrated-auto-s5','playwright-integrated-axe','lifecycle-pg',
   'replay-repro','dr-verify','a7-gate']

# Typecheck
$ pnpm --filter @bolsa/web typecheck
  tsc -b --noEmit   → OK

# Lint
$ pnpm --filter @bolsa/web lint
  ✖ 23 problems (0 errors, 23 warnings)   # avisos preexistentes

# Tests unitarios web
$ pnpm --filter @bolsa/web test
  Test Files  299 passed (299)
       Tests  2195 passed (2195)
```

Estados intermedios que prueban la **falsabilidad** de los arreglos (logs locales, no versionados):
`e2e-mock-expanded-1.log` (fallo `scrollable-region-focusable` + error boundary de
`/instruments/:id`) → `e2e-mock-expanded-2.log` (verde tras los dos fixes).

## 4. Límites declarados / deuda que queda ABIERTA

1. **El job `playwright-integrated-axe` NO se ha podido validar de extremo a extremo en CI
   localmente.** Se validó el YAML (carga correctamente y `certify.needs` lo incluye) y el
   spec en **modo requerido** contra el stack real local (`32 passed`). La validación REAL del
   job (service PG del runner, `tee`/guard) será el **próximo push de tag** o un
   `workflow_dispatch` con `run_e2e_integration=true`; a partir de ahí **bloquea el tag**.
   Nota: un `workflow_dispatch` **sin** `run_e2e_integration` NO ejecuta el job opt-in
   `playwright-integrated`, pero **sí** ejecuta `playwright-integrated-axe` (es incondicional),
   así que ese dispatch también sirve para validarlo.
2. **Rutas del censo mock NO cubiertas en integrado:** `/confirm` (exige una cola F3 sembrada) y
   el **command palette** (overlay con Ctrl/Cmd+K). Se declaran como límite del eje integrado;
   permanecen cubiertas por el barrido **mock**. No se mockean dentro del spec integrado para no
   romper su contrato «sin mocks de `/api/*`».
3. **Dependencia del catálogo real:** el fixture integrado filtra instrumentos vetados por DS-05;
   si **todo** el catálogo estuviera vetado (datos caducados), el seed fallaría **fail-closed**
   (no se inventan datos). No es un fallo de producto.
4. **Espacio AUTO** (`/auto/*`) no se barre en integrado; tiene su barrido mock propio
   (`gp-e2e-v28865-auto-axe-mock.spec.ts`), que **no** comprueba `heading-order`.
5. **`heading-order` en integrado**: se mantiene la regla explícita (`withRules(["heading-order"])`)
   en las 16 rutas × 2 viewports; resultado 0 saltos. Si una ruta futura introdujera un salto, el
   gate **fallaría** (no hay skip posible en modo requerido).
6. Sin **bump** de versión, sin **commit** y sin **push**: el sello/versión lo decide el flujo de
   release (fuera de este alcance).

## 5. Ficheros tocados

- `.github/workflows/release-tag-ci.yml` — job nuevo `playwright-integrated-axe` (gate duro) +
  cableado en `certify` + retirada del axe del job opt-in.
- `apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts` — móvil + 11 rutas nuevas + `pathFor`/`expectMain`
  + modo REQUERIDO `E2E_AXE_REQUIRED=1` (`axeRequired`/`declareGap`).
- `apps/web/e2e/gp-e2e-ui5-0-axe-touched-routes-mock.spec.ts` — 3 rutas nuevas (censo mock completo).
- `apps/web/e2e/helpers/e2e-mock-routes.ts` — `meta` del mock de instrumento suelto.
- `apps/web/e2e/helpers/database.ts` — `selectOpenableInstrument()` (seed determinista).
- `apps/web/src/features/decision-journal/journal-studies-table.tsx` — región de scroll focusable.
- `docs/engineering/deuda-axe-cierre-integrado-2026-10-14.md` — este documento.
