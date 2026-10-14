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

> **Actualización 2026-10-14 (tras el PRIMER run real del gate en CI):** los límites 1 y 3
> quedan revisados en **§6** — el job se ejecutó de verdad, salió **rojo**, se diagnosticó la
> causa raíz (precondición de datos de mercado) y se cerró.

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
- `apps/web/src/components/ui/dialog.tsx` — `aria-label="Cerrar"` en el botón de cierre (2º hallazgo real en CI, §6.7).
- `docs/engineering/deuda-axe-cierre-integrado-2026-10-14.md` — este documento.

## 6. PRIMER run real del gate en CI — rojo, causa raíz y cierre (2026-10-14)

El job `playwright-integrated-axe` **sí** se validó de extremo a extremo: `workflow_dispatch`
`38598160604` (job ID `115970162301`). Resultado: **ROJO** en el paso `Run integrated axe E2E`
—`1 failed`, los otros **62 no ejecutados**— y verde el guard anti-skip (por eso el fallo es
del barrido, no de un skip mudo).

### 6.1 Síntoma exacto (log real del job)

```
1) … › 0 critical/serious + heading-order en /operational-console @desktop
   Error: POST /api/portfolio/trade failed (403): {"detail":"risk_veto"}. Open position seed is required.
     at apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts:394:21   ← ensureMercadoIntegrationFixture

1) … › 0 critical/serious + heading-order en /operational-console @desktop (retry #1)
   Error: GET /paper-desk/daily-report failed (404): {"detail":"Cuenta no encontrada"}
     at apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts:393:17   ← ensureHoyIntegrationFixture
```

Un **`beforeAll` roto** marca el test 1 `✘` y el resto `-` (no ejecutado): el barrido a11y
entero se cayó por una precondición que no tiene nada que ver con accesibilidad.

### 6.2 Causa raíz (única, con dos síntomas)

- `PLAN` sembrar una posición abierta (`buy`) pasa por el gate de apertura (`check_opening` →
  **DS-05 frescura**): el catálogo de CI se siembra con `pnpm db:seed`, que **solo inserta
  instrumentos** (`packages/database/prisma/seed.ts`, 104 líneas, **cero barras**). Sin barras,
  **todos** los instrumentos quedan caducados, `selectOpenableInstrument` no encuentra ningún
  candidato fresco y su fallback fail-closed (no inventar datos, §2.5) devuelve un instrumento
  vetado → `403 risk_veto`. En local **no** se reproduce porque la BD de desarrollo tiene barras
  ingeridas con fecha reciente.
- **Síntoma 2 (flake, no causa):** la lectura `GET /paper-desk/daily-report` justo después de
  `POST /api/accounts` devolvió `404 Cuenta no encontrada` en el retry (carrera
  lectura-tras-escritura del fixture Hoy, preexistente).
- **Diagnóstico de diseño:** un **gate de accesibilidad** no puede depender de la
  **frescura de datos de mercado**. Acoplar ambos hace que un cambio legítimo del gate de
  apertura (o, como aquí, el estado normal de una BD de CI sin barras) tumbe la certificación
  a11y por un motivo ajeno.

### 6.3 Cierre — fixtures en dos niveles, sin `buy`

`apps/web/e2e/gp-e2e-ui5-0-axe-integrated.spec.ts` deja de consumir
`ensureMercadoIntegrationFixture` / `ensureHoyIntegrationFixture` y construye fixtures propias
por HTTP **sin posición abierta**:

- **Nivel 1 (GATE DURO):** entorno integrado sano (`gateIntegratedE2eEnvironment`) + catálogo
  real no vacío + cuentas efímeras (`POST /api/accounts`, prefijos `e2e-v168-*` / `e2e-v167-*`).
  Ausencia ⇒ **FALLO** con `E2E_AXE_REQUIRED=1` (vía `declareGap`), nunca `skipped`.
- **Nivel 2 (enriquecimiento, DECLARADO):** `POST /api/workspaces` real para `/trading`. Si el
  entorno no lo permite, el barrido **no** se salta: se mide el estado real de la ruta y el
  hueco se emite como `::warning::barrido axe integrado — hueco declarado: …` en el log del job.
- Desaparece la lectura de `/paper-desk/daily-report` (era el único punto del flake 6.2) y con
  ella la carrera: no queda ninguna lectura dependiente de datos para las rutas medidas.

### 6.4 Arreglo REAL 3 — `scrollable-region-focusable` en `/history` @móvil

Al correr el barrido **con datos** (cartera/ledger reales) el viewport móvil destapó una
violación que el entorno vacío de CI **no** puede ver:

```
[/history @móvil 390×844] · scrollable-region-focusable [serious] ×1 —
  Scrollable region must have keyboard access
    .overflow-x-auto
```

`apps/web/src/features/history/history-page.tsx` (tabla de movimientos y de operaciones) gana
`role="region"` + `aria-label` + `tabIndex={0}` — **mismo criterio** que el arreglo 1
(§2.3). Cambio solo de semántica/teclado; representación idéntica.

### 6.5 Evidencia del cierre (salida real)

```
# Barrido INTEGRADO en MODO REQUERIDO (mismo env que el job de CI), con datos reales
$env:E2E_RUN="1"; $env:E2E_INTEGRATION="1"; $env:E2E_ALLOW_DEV_DB="1"; $env:E2E_AXE_REQUIRED="1"
pnpm --filter @bolsa/web exec playwright test gp-e2e-ui5-0-axe-integrated
  Running 32 tests using 8 workers
  32 passed (36.3s)
#   (antes del arreglo 6.4: 31 passed + 1 failed = /history @móvil)

# Suite unitaria web afectada
pnpm --filter @bolsa/web test            → 299 files / 2195 tests passed
```

Tras el arreglo del `button-name` del `Dialog` (**§6.7**) el mismo barrido re-verificó en **modo
requerido** con **32 passed** (38.3s), `/trading @desktop` **ok** y **0 violaciones `button-name`**;
`pnpm --filter @bolsa/web test` **299 ficheros / 2195 passed**, `typecheck` **OK** y `lint`
**0 errores / 23 warnings** (preexistentes); `prettier --check` del fichero tocado, limpio.

### 6.6 Límite que queda declarado (honesto)

Con la BD de CI **sin barras**, el barrido integrado mide los **estados estructurales** de las
16 rutas (sin filas de cartera/ledger): las violaciones que solo afloran **con datos** (como el
6.4) no son visibles desde el job. Esa cobertura con datos vive en el hermano **mock**
(`gp-e2e-ui5-0-axe-touched-routes-mock`, con `install*Mocks`) y en la ejecución **local**
documentada. Cerrar ese hueco exigiría sembrar barras sintéticas en la BD de CI —decisión de
datos de mercado, fuera de un gate de accesibilidad— y **no** se hace aquí.

### 6.7 SEGUNDO run real del gate en CI — rojo INTERMITENTE por `button-name` (botón de cierre del `Dialog`) y cierre

Tras el fix `4ee01267`, el `Release tag CI` `workflow_dispatch` **`38600619089`** (sobre `main`,
disparado `2026-10-14T16:44:21Z`) volvió a ejecutar el job `playwright (integrated axe)`
(id **`115978625527`**) →
https://github.com/jvelasca/Bolsa_V1/actions/runs/38600619089/job/115978625527.
Resultado: **ROJO en el intento 1** y **VERDE en el reintento** (la conclusión actual del job es
`success`). Es un hallazgo **distinto** del §6 (no es la precondición de datos de mercado).

#### Síntoma exacto (log real del job, intento 1)

```
Error: [/trading @desktop] · button-name [critical] ×1 — Buttons must have discernible text
  "html": "<button type=\"button\" class=\"rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground\">"
  selector: .p-1.hover\:text-foreground.rounded
```

El **run global CERRÓ VERDE**: `completed` / `success` en 14m16s (`2026-10-14T16:58:37Z`), con
`playwright (mock E2E)` y el agregado `certify` verdes (`playwright (integrated E2E, opt-in)` =
`skipped` por diseño). **Corrección honesta:** una **lectura intermedia** de la vigilancia vio el
job `playwright (mock E2E)` aún `queued` y se redactó «sin cerrar / atascado en cola»; el veredicto
**final** es `success`, el de arriba.

#### Causa raíz — botón icono-solo sin nombre accesible en el `Dialog` compartido

El botón de cierre del componente compartido **`Dialog`**
([`dialog.tsx`](apps/web/src/components/ui/dialog.tsx)) es un botón **icono-solo**
(`<X className="h-4 w-4" />`) **sin nombre accesible**. Su hermano
[`slide-over.tsx`](apps/web/src/components/ui/slide-over.tsx) ya lo tenía (`aria-label="Cerrar panel"`).

#### Barrido de hermanos (completitud) — 9 apariciones de la clase exacta

**9 apariciones** de la clase exacta `rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground` en el árbol; `dialog.tsx` era la **ÚNICA** sin nombre accesible:

| Fichero:línea | Nombre accesible |
| --- | --- |
| [`slide-over.tsx`](apps/web/src/components/ui/slide-over.tsx) :86 | `aria-label="Cerrar panel"` |
| [`dialog.tsx`](apps/web/src/components/ui/dialog.tsx) :64 | ❌ → **ARREGLADO** `aria-label="Cerrar"` |
| [`workspace-picker-dialog.tsx`](apps/web/src/features/workspace/workspace-picker-dialog.tsx) :281 | `title="Renombrar"` |
| [`instruments-hub-filter-bar.tsx`](apps/web/src/features/instruments/instruments-hub-filter-bar.tsx) :242 | `title` + `aria-label="Configurar filtros favoritos"` |
| [`instruments-hub-detail-panel.tsx`](apps/web/src/features/instruments/instruments-hub-detail-panel.tsx) :314 y :338 | `title="Desplegar detalle"` |
| [`decision-ficha-panel.tsx`](apps/web/src/features/decision-journal/decision-ficha-panel.tsx) :729 y :757 | `title="Desplegar ficha"` |
| [`backtest-favorites-menu.tsx`](apps/web/src/features/backtests/backtest-favorites-menu.tsx) :152 | `title` + `aria-label="${title}: más opciones y favoritos"` |

#### Por qué era un FLAKE (real, no falso positivo)

El `Dialog` se monta globalmente en
[`platform-shell.tsx`](apps/web/src/components/layout/platform-shell.tsx) (p. ej.
`WorkspacePickerDialog`) y solo está en el árbol accesible **si hay un diálogo abierto**; en el
entorno del job (BD de CI **sin barras** y con el Nivel 2 de fixtures declarado como hueco) puede
quedar abierto, mientras que en local (con datos/workspaces) no. El **reintento pasó precisamente
porque el diálogo no estaba abierto** ⇒ el rojo era **real pero intermitente**; el arreglo
elimina la **causa**, no el síntoma.

#### Cierre

`aria-label="Cerrar"` en el botón de cierre de
[`dialog.tsx`](apps/web/src/components/ui/dialog.tsx) (**línea 65**), **línea única** añadida, en
el commit del sello. **Falsabilidad:** si el `Dialog` vuelve a quedar sin nombre accesible,
`button-name` vuelve a romper el barrido en cuanto un diálogo esté abierto.

#### Evidencia local DESPUÉS del arreglo (salida real)

```
# Barrido integrado en MODO REQUERIDO (mismo env que el job de CI)
pnpm --filter @bolsa/web exec playwright test gp-e2e-ui5-0-axe-integrated
  Running 32 tests using 8 workers
  32 passed (38.3s)          # /trading @desktop ok · 0 violaciones button-name

pnpm --filter @bolsa/web test        → 299 ficheros / 2195 passed
pnpm --filter @bolsa/web typecheck   → OK
pnpm --filter @bolsa/web lint        → 0 errores / 23 warnings (preexistentes)
pnpm exec prettier --check <fichero tocado> → limpio
```

#### Límite declarado (honesto, importante)

El barrido integrado mide el **estado MONTADO** de cada ruta; los **estados modales** (diálogos
y slide-overs) solo quedan cubiertos **si ocurren** durante el barrido. **NO** se fuerza la
apertura de diálogos en el barrido ⇒ esta clase de violación puede quedar **latente** hasta que un
modal se abra. Queda como **deuda declarada** (mejora futura: un leg determinista que abra el
`Dialog` compartido y lo barra), **no** como cobertura lograda. **NO** se siembran barras ni
workspaces sintéticos en CI (decisión de datos de mercado).

