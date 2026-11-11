# Auditoría independiente — `v2.88.188-beta`

> **Objeto auditado:** tag anotado `v2.88.188-beta` (objeto `2cc673dcefc5c621250ebec087fb8501e450d5ad`)
> → commit `53285f18d60a232233d4b9e67721444336845cba`; `package.json` `2.11.188-beta`.
> **Fecha del informe:** 2026-11-11. **Ejecutor:** agente, con trabajo de aislamiento, ejecución y
> medición propios. **Alcance:** identidad/publicación + revisión estática del delta contra
> `v2.88.187-beta` + suites del CI ejecutadas **desde el tag** + replay reproducible con PostgreSQL
> aislado.
> **Fuera de alcance (declarado en §9):** contenedores Postgres/Redis de los jobs `lifecycle-pg`,
> `dr-verify`, `a7-gate` y `decision-spine`; E2E integrated/live; repetición de la ventana PAPER;
> re-medición del bundle.

---

## 1. Veredicto

| Campo | Valor |
|---|---|
| **Veredicto** | **`PASS`** (verde, con menores y observaciones) |
| Bloqueantes | **0** |
| Mayores | **0** |
| Menores | **4** (`m-1` cifra del diff; `m-2` comando `ruff` no reproducible tal cual; `m-3` goldens pixel win32 obsoletos en DECISIÓN; `m-4` test que no ejerce lo que su nombre afirma) |
| Observaciones | **6** |

El árbol del tag hace lo que el expediente declara en los cinco focos auditados y lo hace sin tocar
motor, reglas, umbrales, sizing ni replay: el diff no entra en `packages/py/**` ni en ningún fichero
cuyo nombre contenga `engine`/`threshold`/`sizing`/`replay` (los dos scripts `v2_87`/`v2_89` que
aparecen solo cambian el literal `meta.bump`). El replay del sello se reprodujo **byte a byte**, dos
veces, sobre una base aislada sembrada con el fixture congelado.

Los cuatro menores son **documentales o de activo de test**: ninguno cambia comportamiento de producto.
Aplicando literalmente el criterio del plan (bloqueante = contradice la certificación; mayor = la
funcionalidad certificada no se comporta como se declara), **no se cumple ningún disparador de mayor**,
por lo que el veredicto es `PASS` y no `PASS CON HALLAZGOS`.

---

## 2. Identidad y publicación

Ejecutado en un worktree **detached y aislado**, fuera del árbol de trabajo (`..\_audit_v2.88.188`),
para que `.venv`, `node_modules`, `dist`, `test-results` y logs no contaminen la evidencia.

| Afirmación | Comprobación ejecutada | Resultado |
|---|---|---|
| El tag existe en el remoto y es el mismo objeto | `git ls-remote --tags origin v2.88.188-beta` vs `git rev-parse` | **OK** — `2cc673dc…` en ambos |
| El tag es **anotado** y apunta a `53285f18` | `git cat-file -p v2.88.188-beta` | **OK** — `object 53285f18…`, `type commit`, tagger `jvelasca`, `1794383985 +0100` (= `2026-11-11T07:59:45Z`) |
| El árbol auditado es el del tag y está limpio | `git rev-parse HEAD`, `git status --porcelain` | **OK** — `53285f18…`; 0 líneas de estado |
| El pin del freeze es el árbol del tag | `git rev-parse "HEAD:apps" "HEAD:packages"` | **OK** — `apps 5310f21d…` / `packages 7c31fca3…` |
| El pin commiteado coincide | `pnpm window:freeze` | **`freeze OK (53285f18)`** + los dos tree hashes |
| El `commit` del pin resuelve al árbol del sello | `git cat-file`/diff de `scripts/lib/window-forward.mjs` | **OK** — `commit: '90d07886'` con `appsHash`/`packagesHash` iguales a `HEAD:apps`/`HEAD:packages`; aviso explícito de que la etiqueta `commit` es anterior a los commits de release y que el freeze real son los dos tree hashes |
| Release publicada, no borrador, no prerelease | `gh release view v2.88.188-beta --json …` | **OK** — `isDraft: false`, `isPrerelease: false`, `targetCommitish: main`, `2026-11-11T08:01:59Z` |
| El CI del tag está verde y cubre los gates | `gh run view 42983709708 --json jobs` | **OK** — `success`; **14 jobs `success`**, único `skipped`: `playwright (integrated E2E, opt-in)`; `certify` `success` |
| El artefacto de certificación dice GREEN sobre este sha | `gh run download 42983709708 -n release-tag-ci-summary` | **OK** — `status: "GREEN"`, `sha 53285f18…`, `ref refs/tags/v2.88.188-beta`, `asOf 2026-11-11T08:13:49Z`, 12 jobs |
| Bump correcto | `git diff b6adc871 HEAD` | **OK** — **14** literales `meta.bump` de **13** scripts + `package.json`; el literal congelado `2.11.0-beta` de `v2_87` **no** aparece en ninguna línea `+` |
| Sin migración nueva | `revision`/`down_revision` en `packages/py/infrastructure/alembic/versions` | **OK** — última revisión `066_account_evidence_policy` (`down_revision 065_auto_engine_intent`); no hay `067` |
| Contrato HTTP sin cambio | `git diff --name-only … -- openapi.json "**/schema.d.ts"` + `contract:check` | **OK** — 0 ficheros; `contract:check OK — openapi.json y schema.d.ts coinciden con el commit` |

### 2.1 Diff real contra `.187` (origen del hallazgo `m-1`)

| Medición | Comando | Resultado |
|---|---|---|
| Diff del **tag** | `git diff --shortstat v2.88.187-beta v2.88.188-beta` | **57 files changed, 4046 insertions(+), 459 deletions(-)** |
| Diff del último commit **funcional** | `git diff --shortstat v2.88.187-beta b6adc871` | **41 files changed, 3723 insertions(+), 441 deletions(-)** |
| Diff sin `docs/` ni `CHANGELOG` | `git diff --shortstat … -- . ":(exclude)docs" ":(exclude)CHANGELOG.md"` | 40 ficheros, +2828/−434 |
| Diferencia entre ambos | `git diff --name-only b6adc871 HEAD` | 16 ficheros: `CHANGELOG.md` (+92), `package.json` (1 línea), `scripts/lib/window-forward.mjs` (+11/−3, re-anclaje del pin), 2 documentos de evidencia/entrega, `PROJECT_STATE.md` y **14 literales de versión** en 13 scripts de `apps/` |

Conclusión: la cifra declarada **es exactamente el diff de `b6adc871`**, no el del tag. La diferencia
son solo chores de release; **ni un fichero de motor, contrato o migración**. Ver `m-1`.

### 2.2 Secuencia tag → Release → CI (observación `o-6`)

| Evento | Instante (UTC) |
|---|---|
| Tag creado (tagger) | `07:59:45` |
| `Release tag CI` arranca | `08:01:01` |
| **GitHub Release publicada** | `08:01:59` |
| `Release tag CI` termina verde (artefacto `asOf`) | `08:13:49` (`08:13:53` el run) |

La Release salió **12 minutos antes** de que el CI del tag terminara. A diferencia de `.187` (donde esto
fue hallazgo `m-4`), aquí **está declarado**: el bloque `AsOf` del `CHANGELOG` y la §2 de la evidencia
dicen «el certificador es el `Release tag CI` del tag (**PENDIENTE** al escribir este bloque; se cita
POST-TAG)». Se registra como observación, no como hallazgo.

---

## 3. Método y comandos ejecutados

```powershell
git worktree add --detach ..\_audit_v2.88.188 v2.88.188-beta
pnpm install --frozen-lockfile
pnpm --filter @bolsa/shared build ; pnpm --filter @bolsa/shared typecheck ; pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/web typecheck ; pnpm --filter @bolsa/web lint ; pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web contract:check ; pnpm --filter @bolsa/web build
pnpm typecheck ; pnpm window:test ; pnpm window:freeze ; pnpm dev:test ; pnpm ci:timings:test
uv sync
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src `
        packages/py/application/src apps/api-python/src --follow-imports=silent
# pytest: el `run: >` del job `python` del tag, extraído literalmente del workflow
uv run pytest <183 tokens del step> [-q]
uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
pnpm --filter @bolsa/web exec playwright install chromium
$env:E2E_RUN="1"; pnpm e2e -- "gp-e2e|gp-e2e-s5|gp-v173|…|gp-v186|gp-v190"
# replay
docker run -d --name bolsa-audit-188 -p 55432:5432 postgres:16-alpine …
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py seed --fixture docs/engineering/evidence/v2.88.7/replay-input-fixture.ndjson
uv run --no-sync python apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py --json --watch "<20 símbolos>" --out artifacts/replay-oos-durable-v2.88.7.json
uv run --no-sync python apps/api-python/scripts/replay_oos_input_fixture.py assert-artifact --file artifacts/replay-oos-durable-v2.88.7.json
```

Toolchain local: git 2.54, node **24** (CI usa 22), pnpm 10.12.1, uv, Python **3.12.13** (CI 3.12.3),
Docker, gh. Los desvíos de plataforma se tratan en §5.6/§9 y **no** se presentan como certificación.

---

## 4. Hallazgos

### 4.1 Bloqueantes

**Ninguno.** No se cumple ningún disparador del plan: la identidad del tag es la declarada, el replay
reproduce byte a byte, no hay cambio oculto en motor/decisión, los cierres siguen funcionando con
entradas bloqueadas y `UNKNOWN` no se convierte en `0`.

### 4.2 Mayores

**Ninguno.** La funcionalidad certificada se comporta como declara el expediente en los cinco focos.

### 4.3 Menores

#### `m-1` — La cifra del diff publicada no es la del tag (es la del último commit funcional)

- **Declarado** en `CHANGELOG.md` §`2.11.188-beta`, `PROJECT_STATE.md` (bloque `AsOf`), evidencia §1 y
  entrega §5: «**41 ficheros, +3.723/−441** contra `v2.88.187-beta`».
- **Medido**: `v2.88.187-beta → v2.88.188-beta` = **57 ficheros, +4.046/−459**. La cifra publicada
  coincide **exactamente** con `v2.88.187-beta → b6adc871` (`41 files changed, 3723 insertions(+),
  441 deletions(-)`), es decir, con el árbol **anterior** a los commits de release.
- **Efecto**: un auditor externo que repita el comando obtiene otro número y no puede cerrar el
  contraste sin descubrir por su cuenta que faltan 16 ficheros de chore. **Sin efecto funcional**: los
  16 ficheros son `CHANGELOG`, `PROJECT_STATE`, 2 documentos de evidencia, el re-anclaje del pin y 14
  literales de versión.
- **Reproducción**: los tres `git diff --shortstat` de §2.1.

#### `m-2` — El comando `ruff` documentado no reproduce el verde tal como está escrito

- **Declarado** (evidencia §4): `ruff check packages/py apps/api-python` → **All checks passed**.
- **Medido**: sin `--config pyproject.toml`, ruff 0.16.2 (el pineado en `[tool.uv]`) devuelve
  **901 errores `I001`** (import block un-sorted), porque cada subpaquete tiene su propio
  `pyproject.toml` con `known-first-party` distinto. Con el argumento que usa el CI —
  `--config pyproject.toml` — devuelve **`All checks passed!`**.
- **Efecto**: documental; el gate del tag usa la forma correcta. Quien copie el comando de la evidencia
  verá un rojo que no existe.

#### `m-3` — Los goldens pixel `win32` de `operativa-cockpit` están obsoletos tras la reorganización de DECISIÓN

- **Medido** en el árbol del tag, con `E2E_RUN=1` y el **mismo filtro del CI**:
  `4 failed`, `135 passed`, `61 skipped`. Las cuatro rojas son del certificado visual:
  `gp-e2e-v29-cabin-visual-mock.spec.ts` (`1366 light`, `1366 dark`, `1920 light`, `1024 light`).
- El error es **geométrico, no de antialiasing**: `expected 353×1349, received 353×1317` (1366) y
  `403×1298 → 403×1266` (1920): **−32 px constantes**.
- **Causa localizada**: en `.188` se **extrae `AutoDeskPanel` de la tarjeta** de decisión
  (`git diff v2.88.187-beta HEAD -- …/operativa-cockpit-card.tsx` muestra la eliminación del bloque
  `L4 — ¿Por qué? · AUTO` y de `<AutoDeskPanel …>`), lo que reduce la altura de la tarjeta. Los
  goldens `apps/web/e2e/gp-e2e-v29-cabin-visual-mock.spec.ts-snapshots/*-win32.png` **no se
  regeneraron** (último commit que los toca: `7ea7f946`, `2026-10-15`).
- **Por qué el CI no lo ve**: el propio spec hace
  `test.skip(Boolean(process.env.CI), "pixel goldens are host-OS (win32); CI linux certifies contrast + v28 DOM")`.
  El verde del tag **no cubre** este activo.
- **Efecto**: certificación visual local roja en la superficie que el sello reorganiza; sin efecto en
  runtime. Se corrige con un `--update-snapshots` **en win32** y revisión del diff de imagen.

#### `m-4` — El test que declara «no desactiva la CTA de Confirm» no renderiza ninguna CTA de Confirm

- `operativa-cockpit-card.test.tsx` › *«muestra el aviso y no desactiva la CTA de Confirm»* monta la
  fase `vigilar` y afirma `getByTestId("operativa-cockpit-cta-vigilar")`. En esa fase **no existe**
  `operativa-cockpit-cta-confirm` (solo aparece en `propuesta` o `disparada` con cola).
- **La propiedad es cierta por código** (`showConfirm` no depende de `entriesBlocked`; el botón no
  lleva `disabled`) y está verificada a mano en este informe, pero **el test no la ejerce**: su nombre
  promete más de lo que mide. Es un problema de calidad de evidencia, no de comportamiento.

### 4.4 Observaciones

- **`o-1` — «12 jobs + certify» es el gate, no el total.** `certify.needs` lista **12** jobs;
  el run tuvo **14 `success`**. El extra es `playwright (live AUTO daily chain)`, que el workflow
  declara **no-gate** con comentario explícito (líneas ~520-525) y que también salió verde. El
  artefacto `release-tag-ci-summary` lista solo los 12 del gate. Correcto por diseño, pero el recuento
  publicado no coincide con el del run.
- **`o-2` — El job mock tuvo 1 `flaky`.** El log del CI dice `136 passed`, `91 skipped`, **`1 flaky`**:
  `GP-V190-04: zoom mueve data-visible-range y el reset lo restaura`. Pasó al reintentar, pero la
  evidencia cita solo «136 passed» y ni el artefacto ni el README registran reintentos.
- **`o-3` — El test de «puertas laterales» es textual.** `entries-blocked-side-doors.test.ts` hace
  `expect(src).toMatch(/…/)` sobre el código fuente (5 casos). Detecta que el cableado existe, **no**
  que el botón correcto quede habilitado: la aserción
  `disabled=\{busy \|\| entriesBlocked\}` pasaría igual si se aplicara al botón de venta. La conducta
  se verificó a mano en este informe (ver §5.4) y es correcta.
- **`o-4` — Puerta lateral residual, preexistente: el acordeón de listas bloquea el diálogo entero.**
  En `list-item-accordion.tsx` los dos abridores (`Operar`, `Nueva operación`) llevan
  `disabled={entriesBlocked}` desde `a8101ab7` (`2026-08-31`, **no** lo introduce `.188`), de modo que
  con entradas bloqueadas no se puede abrir el diálogo —ni para vender— desde la lista. El cierre
  sigue disponible por DECISIÓN (`PositionExitDrawerActions`) y por el diálogo abierto desde otras
  rutas. No contradice el texto del sello («sin desactivar Confirm»), pero la frase «ninguna ruta de
  venta/cierre queda deshabilitada» es más ancha que la realidad.
- **`o-5` — Chip de tendencia vacío cuando no hay `display` ni `value`.** `buildTrendLines` usa
  `trend.display ?? trend.value ?? ""` y la banda pinta ese hueco como valor vacío con tono `unknown`;
  el hueco **sí** se declara en `gaps` («Tendencia sin dato») y **no** se convierte en `0`. Cosmético.
- **`o-6` — La Release precede al CI del tag.** Ver §2.2. Declarado en el expediente; se registra para
  que el contraste quede completo.

---

## 5. Delta funcional por área

### 5.1 DECISIÓN: 2 bloques fijos + 5 plegables — **VERDE**

| Comprobación | Evidencia |
|---|---|
| 2 bloques **fijos** | `trading-operativa-panel.tsx`: `OperativaAnalisisDiario` (banda) y `OperativaCockpitCard` en `operativa-col-decision`, sin `TradingOperativaSection` |
| 5 bloques **plegables** | `sectionId="lab"` (*Seguimiento Lab*), `"mandato"`, `"evidencia"`, `"resultados"` (*Aprendizaje*) y `"auto"` (*AUTO*), cada uno en `TradingOperativaSection` |
| Arrancan colapsados | `DEFAULT_OPERATIVA_SECTIONS` = `false` × 5; `merge` del `persist` rellena los cinco sobre guardados viejos y **conserva** claves desconocidas sin romper |
| Un asunto por bloque | `AUTO` sale a `operativa-auto-panel.tsx`; el mandato fusiona timeline (`MandateTimelinePanel`) y ficha; `churn` ahora es `summarizeMandateChurn({ instrumentId, accountId })` y ya no contradice al timeline |
| **Una sola puerta de acción** | `git diff` del panel elimina los botones propios `operativa-proponer-f3`, `operativa-cola-confirm` y el alta a Estudio duplicada. La CTA vive solo en la tarjeta: `showPropose` → `operativa-cockpit-cta-preparar`; `showConfirm` → `operativa-cockpit-cta-confirm`. El aviso de bloqueo es un `<p>`, no una segunda CTA |
| Persistencia de estado y alto | `toggleOperativaSection` / `setOperativaSectionHeight` con `clamp(72, 900)`; el asa escribe al soltar |

### 5.2 Maximizado y container queries — **VERDE**

- `maximizeOperativa` fija `operativaMaximized` y **desmaximiza** Listas/Gráfico/Operaciones en la
  misma escritura; `toggleLists`/`toggleCharts`/`toggleOperations` también limpian `operativaMaximized`.
- `trading-layout.tsx` hace **early return** con un único `DockZone` «DECISIÓN» y
  `<TradingOperativaPanel maximized />`; no se montan Listas, Gráfico, Operaciones ni health strip.
- **Ancho real del panel, no del viewport**: `index.css` define
  `.operativa-panel-scroll { container-type: inline-size; container-name: operativa-panel }` y reparte
  en `@container operativa-panel (min-width: 52rem)` (2 columnas) y `(min-width: 78rem)` (3 columnas).
- **< 768 px**: `narrow = useMediaQuery("(max-width: 767px)")`; el dock lateral es `hidden md:flex`, así
  que la vista maximizada es la única puerta, y `maximizable={!narrow}` oculta un «Restaurar» que no
  tendría destino. La entrada existe siempre en el menú de vista
  (`app-top-bar.tsx`: «Operativa maximizada»).
- Maximizado, la sección crece (`height: auto`) y **no** pinta el asa; en dock normal mantiene alto fijo
  y asa. Cubierto por `trading-operativa-section.test.tsx` (2 casos, ambos con aserciones reales sobre
  `data-maximized` y el `role="separator"`).

### 5.3 Banda `InstrumentDailyAnalysisV1` — **VERDE**

| Comprobación | Evidencia |
|---|---|
| Proyección **pura** | `instrument-daily-analysis.ts` solo importa tipos + `strategySlotToIndicatorDetails` + copia de fase + helpers de `operational-plan-view`. Cero motores, cero `fetch`, cero cálculo de tendencia/régimen/indicadores |
| **`UNKNOWN` ≠ `0`** | `Select-String` sobre el fichero: **0** coincidencias de `?? 0`, `|| 0`, `Number(`, `parseFloat`, `toFixed`, `* 100`. Los nulos se conservan y la UI usa `absentDataLabel()` |
| Huecos declarados | `collectGaps`: «Fuera de Estudio», «Sin análisis diario todavía», «Parte diario caducado», «Tendencia sin dato», `tracking.gap` («Sin Finalista #1 todavía», «Estrategia sin indicadores declarados») y «Plan sin niveles» |
| `entry === null` con posición | `buildEntry` devuelve `null` si `phase === "posicion"` |
| `exit === null` sin posición | `buildExit` devuelve `null` si `phase !== "posicion"` |
| Trailing **no** se promueve a stop | `exit.stop = plan.stopVigente`; el trailing solo aporta `trailingLabel` (`trailing.statusLabel ?? "Recogido en el stop vigente"`) |
| Banda colapsable y por encima de la tarjeta | `OperativaAnalisisDiario` se monta antes de `OperativaCockpitCard`, dentro del bloque fijo de decisión |

Tests: 10 casos en `instrument-daily-analysis.test.ts` (incluye «tono desconocido», «fuera de Estudio»,
«parte caducado y estrategia sin indicadores», reutilización de `indicatorSpecs` con parámetros) y 4 de
componente en `operativa-analisis-diario.test.tsx` (tendencia/seguimiento/entrada, sin parte, escalera de
salida con trailing, fuera de Estudio).

### 5.4 Cierres con entradas bloqueadas — **VERDE**

- **Aviso**: `<p data-testid="operativa-cockpit-blocked-hint">Entradas bloqueadas · Confirm solo para
  cierres</p>` cuando `entriesBlocked` y la fase no es `confirmada` y la etiqueta no es ya la de bloqueo.
- **Confirm habilitado**: `showConfirm` depende de `requiresHumanConfirm` + fase, **nunca** de
  `entriesBlocked`; el botón `operativa-cockpit-cta-confirm` **no** lleva `disabled`.
- **Solo compra gateada**, verificado en código (no solo por el test textual):
  - `order-dialog.tsx`: `VENTA` → `disabled={busy}`; `COMPRA` → `disabled={busy || entriesBlocked}`, y
    `requestAction`/`confirmPendingAction` re-validan `side === "buy" && entriesBlocked`.
  - `chart-quick-trade-buttons.tsx`: `V` (venta) sin `disabled`; `C` (compra) `disabled={entriesBlocked}`.
  - `chart-instrument-ai-button.tsx`, `instrument-detail-page.tsx`, `trading-alarm-inbox-button.tsx`:
    cablean `entriesBlocked` al propose/buy.
  - `operativa-cockpit-card.tsx`: `canPropose` incluye `!entriesBlocked`; las salidas
    (`PositionExitDrawerActions`) no se gatean.
- Inventario de puertas laterales: las seis del plan están cableadas (chart IA, alarm inbox, order
  dialog, venta rápida, detalle de instrumento, acordeón de listas). Limitaciones del test: `o-3`; puerta
  residual preexistente: `o-4`.

### 5.5 Observabilidad `api-exit` — **VERDE**

| Comprobación | Evidencia |
|---|---|
| Motivos | `api-exit:<code>` (incluye `0`), `api-exit:signal:<SIG>`, `api-exit:spawn-error`, `api-exit:unknown` |
| Hechos estructurados | `apiExitFacts` devuelve `role`, `pid`, `code`, `signal`, `uptimeMs`, `lastLines`; **no inventa** campos ausentes (`sin pid ni uptime no inventa campos`) |
| Última salida conservada | `lastLines` respeta CRLF, recorta y descarta vacías |
| Handler correcto | `apiChild.on('close', …)` con `apiSupervised`/`shuttingDown`; comentario explícito de por qué `close` y no `exit` (stdio drenado). `process.exit` solo dentro de `shutdown` |
| Los tres destinos | `logError('dev', line, payload)` cuando `reason` empieza por `api-exit:` → consola + `logs/agent/events.log` (nivel `error`); `writeAgentLog('dev', { status: 'stopped', ...payload })` → `logs/agent/dev.json` |
| Documentación coherente | `dev-logs.md` §«Caída de la API» reproduce la tabla de motivos, el formato de línea y los campos de `dev.json`; `DEV_STARTUP.md` enlaza la receta |
| Guardián | `pnpm dev:test` → **9 pass** (los 9 casos de `api-exit.test.mjs`) |

Límite: `api-exit:spawn-error` se construye **inline** en `run-dev.mjs` y **no** tiene caso unitario
propio (el motivo y los hechos sí están cubiertos por partes).

### 5.6 Suites ejecutadas **desde el tag** — **VERDE con límites**

| Comprobación | CI del tag | Local (Windows, node 24 / py 3.12.13) | Lectura |
|---|---|---|---|
| `vitest` web | 377 ficheros / **2800 passed** | **377 / 2800** | coincide |
| `vitest` shared | — | **104 ficheros / 914 passed + 1 todo** | verde |
| `typecheck` | 4/4 | **4 successful / 4** | coincide |
| `lint` | **23 problems (0 errors)** | **23 (0 errors)** | coincide |
| `contract:check` | OK | **OK** | coincide |
| `build` web | verde | **✓ built in 4.73 s** | verde |
| `ruff` (`--config pyproject.toml`) | All checks passed | **All checks passed!** | coincide (ver `m-2`) |
| `lint-imports` | **4 kept, 0 broken** | **no ejecutable en esta máquina** (Application Control bloquea el binario, `os error 4551`) | límite §9 |
| `mypy` (scope CI) | 599 ficheros | **599, no issues** | coincide |
| `pytest` offline | **6515 passed, 111 skipped** | **6511 passed, 111 skipped** | 4 de diferencia = módulo no recolectable (ver abajo) |
| `window:test` | — | **86 pass** | coincide con la evidencia |
| `dev:test` | — | **9 pass** | coincide |
| `ci:timings:test` | — | **19 pass** | verde |
| bump guard | 2 passed | **2 passed** | coincide |
| `window:freeze` | verde | **freeze OK (53285f18)** | coincide |
| Playwright mock | **136 passed + 1 flaky, 91 skipped** | **135 passed, 4 failed, 61 skipped** | las 4 rojas = `m-3` |

**Reconciliación exacta de `pytest`** (no se presenta como certificación, se presenta como
reconciliación):

1. Ejecutando el `run: >` **literal** del workflow, esta máquina recolecta **6393** y pasa **6282**: el
   propio arnés local **descarta en silencio `packages/py/domain/tests`** (229 tests) cuando se combinan
   los 7 directorios con los 73 ficheros explícitos.
2. Ejecutando los **7 directorios** con la **misma lista de 95 `--ignore`**, recolecta **6622** y pasa
   **6511** con **111 skipped**.
3. El único módulo excluido es `packages/py/analytics/tests/test_vectorbt_optuna.py` (**4 tests**), que
   no se puede importar en esta máquina porque `llvmlite.dll` existe pero **no carga** (restricción del
   host, no del repo).
4. **6511 + 4 = 6515** y `111 = 111`: el resultado del CI queda explicado **sin residuo**.

### 5.7 Replay reproducible (`Δ motor = 0`) — **VERDE**

| Paso | Resultado |
|---|---|
| PostgreSQL aislado | `postgres:16-alpine` en **55432** (contenedor `bolsa-audit-188`), sin tocar el `bolsa-postgres` de desarrollo |
| Sembrado del fixture congelado | `# sembrado 20 instrumentos, 25700 barras D1` |
| Regeneración con el script del sello | `v2_87_replay_oos_durable_cycle.py` → `exit=0`, **79 s** |
| `assert-artifact` | `exit=0` → **`VEREDICTO REPRODUCIDO (render del sello, byte a byte)`** |
| Digest del render (CRLF, Windows) | **3.488.758 B**, `sha256 01429BCC849F009DF47CB0FB11B34800BC8EB7A69071F88DC8FF032DD92B7476` — **idéntico al sello** |
| Digest del contenido (LF, lo que ve el CI) | **3.383.461 B**, `sha256 E9B7376BFE885C86CA4E56C0F37D79129B1EF8ECD325F2CE043A2D1AEF7F5625` — **idéntico al sello** |
| Determinismo | segunda corrida independiente: **fichero idéntico** (`Compare-Object` vacío) y **mismo sha256** |

Esto es lo que sostiene `Δ motor = 0` con medición, no con afirmación: el artefacto del sello se
regenera bit a bit desde el fixture.

---

## 6. Contraste documental

| Afirmación del expediente | Medición | Estado |
|---|---|---|
| Tag `v2.88.188-beta` = `53285f18`, anotado, Release no-prerelease, CI `success` | §2 | **Confirmado** |
| `12 jobs + certify`, único `skipped` el E2E integrado | 14 `success` + 1 `skipped` + `certify`; **12** en `certify.needs` | **Confirmado con matiz** (`o-1`) |
| Artefacto `status: GREEN`, `sha 53285f18` | descargado y leído | **Confirmado** |
| `Δ motor = 0` / `Δ decisión = 0` | diff sin motores + replay byte a byte | **Confirmado** |
| Sin migración (`066`), sin cambio de contrato | §2 | **Confirmado** |
| Bump 14 literales de 13 scripts; `2.11.0-beta` intacto | §2 | **Confirmado** |
| Pin `apps 5310f21d…` / `packages 7c31fca3…`, `freeze OK` | §2 | **Confirmado** |
| `41 ficheros, +3.723/−441` | **57 / +4.046/−459** | **No reproducido** → `m-1` |
| `vitest` 377/2800, `typecheck` 4/4, `lint` 23 avisos, `contract:check` OK | §5.6 | **Confirmado** |
| `ruff` All checks passed (comando sin `--config`) | 901 `I001` sin `--config`; verde con él | **No reproducible tal cual** → `m-2` |
| `lint-imports` 4 kept, 0 broken | log del CI | **Confirmado en CI**; no ejecutable aquí |
| `mypy` 599 | 599 | **Confirmado** |
| `window:test` 86, `dev:test` 9, bump guard 2, `freeze` OK | ejecutados | **Confirmado** |
| `pytest` 6515/111 | 6511/111 + 4 no recolectables | **Reconciliado** (§5.6) |
| Falsabilidad de `api-exit` en vivo | no repetida (stack no levantado; se declara límite) | **No verificado aquí** |
| Playwright mock 136 passed | 135 + 4 rojas de golden win32 | **`m-3`**, invisible al CI por diseño |

---

## 7. Deuda declarada por el sello (no es hallazgo)

| Extremo | Estado |
|---|---|
| AUTO **OFF**, PAPER **`INCONCLUSIVE`**, 100 % SIM, sin órdenes reales | declarado; coherente con el código auditado |
| La banda **proyecta** artefactos y **no** eleva evidencia operativa | declarado y cierto: no calcula nada |
| La ventana PAPER queda **`STALE`** tras el re-anclaje del pin | declarado |
| E2E live/integrated un `skipped` no certifica | declarado; sigue siendo el único `skipped` del run |

---

## 8. Criterio de veredicto aplicado

| Disparador del plan | ¿Se cumple? |
|---|---|
| La evidencia contradice la certificación (identidad del tag) | **No** |
| Replay no reproducible | **No** — reproduce byte a byte, dos veces |
| Cambio oculto en motor/decisión | **No** — diff y replay lo desmienten |
| Cierre que deja de funcionar con entradas bloqueadas | **No** |
| `UNKNOWN` convertido en `0` | **No** |
| La funcionalidad certificada no se comporta como se declara (mayor) | **No** |

Con 0 bloqueantes y 0 mayores, el veredicto es **`PASS`**. Los cuatro menores son corregibles sin
tocar producto: dos de documentación (`m-1`, `m-2`), uno de activo visual (`m-3`) y uno de calidad de
test (`m-4`).

**Recomendación POST-TAG** (no ejecutada): corregir la cifra del diff en los cuatro documentos, añadir
`--config pyproject.toml` al comando documentado de `ruff`, regenerar los goldens `win32` de
`operativa-cockpit` en un host Windows y revisar el diff de imagen, y renombrar o reforzar el test de
`m-4` para que monte una fase con `Confirm`. Nada de eso exige mover el tag.

---

## 9. Límites de esta auditoría

- **Plataforma**: Windows + node 24 + Python 3.12.13 frente a Linux + node 22 + Python 3.12.3 del CI. Los
  recuentos se reconcilian, pero **no equivalen** a la certificación; el certificador sigue siendo el
  job del tag.
- **`lint-imports`**: no ejecutable en esta máquina (Application Control bloquea el binario). Se cita el
  resultado del log del CI, no una medición propia.
- **`test_vectorbt_optuna.py`**: 4 tests no recolectables (`llvmlite.dll` no carga). Es un límite del
  host; el CI los ejecutó.
- **Playwright**: solo el job mock. Los jobs integrated/live y el E2E opt-in **no** se repitieron: exigen
  API, PostgreSQL y barras. El `skipped` del opt-in **no** se cuenta como verde.
- **`lifecycle-pg`, `dr-verify`, `a7-gate`, `decision-spine`**: no repetidos (requieren sus contenedores y
  baterías propias).
- **`api-exit` en vivo**: no se mató la API de un stack arrancado desde el worktree; la conducta se
  verificó por código y por los 9 casos unitarios. La falsabilidad en vivo queda como límite declarado.
- **Ventana PAPER / rentabilidad**: fuera de alcance por definición (AUTO OFF, PAPER `INCONCLUSIVE`).
- **Aislamiento**: todo se ejecutó en `..\_audit_v2.88.188` (tag, detached). El árbol principal no se
  tocó; este informe se escribe en `main` como **POST-TAG sin commit** hasta decisión explícita.
