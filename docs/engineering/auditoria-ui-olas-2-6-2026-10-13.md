# Auditoría UI — olas 2..6 (re-verificación itemizada)

> **AsOf:** 2026-10-13 · **Versión del árbol:** `2.11.124-beta` (raíz; `apps/web` = `0.1.0`).
> **Revisión 2026-10-14 (pasada de profundidad UI):** se cierra **`O6-06`** —los tres paneles de lifecycle del primer nivel de la consola colapsaban huecos a `0`/verde— con *fix* + gate `findFirstLevelFalseZeros`; se ajustan §6 (§6.1/§6.2), §7 (censo) y §10-§11 en consecuencia. `Δ motor` y `Δ contrato` = 0.
> **Estado:** **AUDITORÍA EN SOLO LECTURA** del código + **censo ejecutable ampliado** + **residuos mecánicos cerrados**. **NO es implementación de rediseño**: no se reescribe UI, no se mueve motor ni contrato HTTP.
> **Naturaleza:** UI / producto / semántica. **`Δ motor = 0`** por construcción (el cambio solo toca `apps/web/**` + este doc).
> **Padres:** [Auditoría UI 6.x global](./auditoria-ui-6-x-global-2026-10-08.md) (partición de olas §5, checklist §1.3, vara §4) · [UI Contract 5.0](./spec-ui-contract-5-0-2026-10-08.md) (registro regla→estado §5, `R-G1`/`R-G2` §2) · [entrega v2.88.91](./entrega-auditoria-externa-mia-v2.88.91-2026-10-08.md) (W2/W3/W4) · [entrega v2.88.92](./entrega-auditoria-externa-mia-v2.88.92-2026-10-08.md) §60 y [entrega v2.88.93](./entrega-auditoria-externa-mia-v2.88.93-2026-10-08.md) §59 (remediación: «ampliar el censo de superficies por oleadas con el mismo gate»).
> **Base del encargo:** «continuar las olas 2..6 de auditoría de interfaz» (paso 4b del veredicto). La OL A 1 (Confirmar·Hoy) ya tiene hallazgos itemizados y está sellada; las OLAS 2..6 solo tenían una fila de backlog y seguían declaradas ABIERTAS aunque su implementación parcial (W2/W3/W4, `v2.88.91-93`) ya se hizo.

---

## 0. Alcance y método

La pregunta de esta fase: **¿siguen abiertas las olas 2..6?** Se re-verifica cada ola contra el **árbol actual** (no contra el tag `v2.88.90`) con la misma vara de la Ol A 1:

- **Variables de medida:** checklist uniforme §1.3 de la [auditoría 6.x](./auditoria-ui-6-x-global-2026-10-08.md) y tabla pantalla→pregunta §1.2.
- **Instrumentos:** lectura `file:line`; **gate falsable** [`first-level-gate.ts`](../../apps/web/src/components/first-level-gate.ts) (`findFirstLevelViolations` / `findFirstLevelDashes` / `findFirstLevelGateLiterals`); **censo ejecutable** [`barrido-global-first-level.test.tsx`](../../apps/web/src/features/barrido-global-first-level.test.tsx) (ampliado en este slice); **helper de hueco** [`absent-data.ts`](../../apps/web/src/components/absent-data.ts).
- **Semáforo:** `verde` (sin hallazgos), `P2` (residuo declarado / diseño), `P1` (fuga de primer nivel), `P0` (firma/acción con lenguaje de backend). Aquí no reaparece ningún `P0` (la Ol A 1 lo absorbió).
- **Sin re-ejecutar `axe` en vivo ni Playwright E2E** (declarado en §12).

### 0.1 Reconciliación con la partición de olas del doc global (§5, `:150-159`)

| Ola §5 | Pantalla | Trabajo §5 | Regla §5 | Implementación asociada |
| --- | --- | --- | --- | --- |
| 2 | Cartera (`/mesa?view=posiciones`, `/history`) | Retirar `Libro`/`Ledger`/`fills` de primer nivel; `—`→Opción B; separar «¿qué tengo?» de «¿qué ha pasado?» | `UI5-13/14/20`, `R-G1` | **W2** (`v2.88.91`) |
| 3 | Mercado (`/trading`) | `h1` visible; toolbar avanzada a 2.º nivel; separar acción de información | `R-G2`, `RT-01`, `UI5-17` | **W3** (`v2.88.91`) |
| 4 | Asesor (`/research`) | Plegar jerga estadística tras «¿Por qué?» | `R-G1`, §8 | **W4** (`v2.88.91`) |
| 5 | Chrome/palette | Un solo mecanismo de profundidad; palette separa nav de ajustes | `RT-04`, `UI5-17` | **W3** (`v2.88.91`, parte chrome) |
| 6 | Consola avanzada (`/operational-console`) | Nivel 3 explícito; sin `—` ni `órdenes UNKNOWN` fuera de nivel 3 | `UI5-14` | **W2** (parte consola) — **incompleta** |

> **Nota de numeración.** Las «olas» del backlog (§5) **no** coinciden 1:1 con las «W» de la entrega `v2.88.91`: `W2` cubrió Cartera+Historial+**Consola**; `W3` cubrió Mercado+**chrome**; `W4` cubrió Asesor. Este documento re-verifica por **pantalla** (olas §5) y reconcilia con W2/W3/W4.

---

## 1. Matriz pantalla → pregunta (vara §1.2 aplicada)

| Ola | Pantalla / ruta | Pregunta principal | ¿La responde? | Segunda pregunta / fuga | Sev. |
| --- | --- | --- | --- | --- | --- |
| 2 | Cartera `/mesa?view=posiciones` | ¿Qué tengo? | **Sí** | «Historial» separado por enlace (`Ver en Cartera`/`Historial`) | verde |
| 2 | Historial `/history` | ¿Qué ha pasado? | **Sí** | — | verde |
| 3 | Mercado `/trading` | ¿Qué está ocurriendo? | **Sí** | Toolbar/decisión pliegadas | verde |
| 4 | Asesor `/research` | ¿Por qué? | **Sí** | Columnas de investigación con valores crudos | P2 |
| 5 | Chrome (barra + rail + palette) | — (soporte) | **Parcial** | La palette sigue mezclando nav + ajustes (mitigado con separador) | P2 |
| 6 | Consola `/operational-console` | (diagnóstico, nivel 3) | **Parcial** | El primer nivel de la consola no está rotulado como nivel 3 | P2 |

---

## 2. Ola 2 · Cartera · Historial (`/mesa?view=posiciones`, `/history`)

**Veredicto: verde (DONE).** La fila §5 pedía retirar `Libro`/`Ledger`/`fills` de primer nivel, sustituir `—` por el vocabulario Opción B y separar «¿qué tengo?» de «¿qué ha pasado?». El árbol actual cumple.

### 2.1 Checklist §1.3

| # | Ítem | Evidencia | Estado |
| --- | --- | --- | --- |
| 1 | `h1` único; primer bloque responde una pregunta | `Posiciones` (`mesa-libro-panel.tsx:39`); `Historial` (`history-page.tsx:178`) | ✅ |
| 2 | Términos prohibidos en primer nivel | Solo identificadores TS (`LedgerEntryDto`, `formatLedgerEntryLabel`, `api.getAccountLedger`); 0 copy | ✅ |
| 3 | `—` / `NO MEDIDO` / `Sin datos` | `formatPriceOrAbsent`/`formatR` → `absentDataLabel()` (`mesa-position-row.tsx:46`, `:383`) | ✅ |
| 4 | Disclosure único (`RT-04`) | `TechnicalDetail` (rutas de detalle) | ✅ |
| 5 | Nav vs acción vs información (`UI5-17`) | `Ver en Cartera`/`Historial` = enlaces; CTAs de posición = botones | ✅ |
| 6 | Semáforo | **verde** | ✅ |

### 2.2 Hallazgos itemizados

| # | Hallazgo | Evidencia (`file:line`) | Regla | Sev. | Veredicto |
| --- | --- | --- | --- | --- | --- |
| O2-01 | Retirado `Libro`/`Ledger` de primer nivel: `h2` = «Posiciones»; `h1` = «Historial»; pestañas «Movimientos contables» / «Operaciones» | `mesa-libro-panel.tsx:39`, `history-page.tsx:178`, `:221-222` | `UI5-20` | — | **cerrado (W2)** |
| O2-02 | Comodín `—` de filas de Posiciones sustituido por vocabulario Opción B | `mesa-position-row.tsx:46`, `:383-396` | `UI5-14` | — | **cerrado (W2)** |
| O2-03 | `Ledger`/`fills` sobreviven como **identificadores TS**, nunca como copy; se auditan con límite de palabra en `history-first-level.test.tsx` | `history-page.tsx:5-6` | `R-G1` | — | aceptado (no es copy) |

**Sin hallazgos abiertos.** La re-verificación confirma DONE.

---

## 3. Ola 3 · Mercado (`/trading`)

**Veredicto: verde (DONE) con 1 residuo P2 declarado.** La fila §5 pedía `h1` con tamaño de puerta, toolbar avanzada a segundo nivel y separar acción de información.

### 3.1 Checklist §1.3

| # | Ítem | Evidencia | Estado |
| --- | --- | --- | --- |
| 1 | `h1` visible y de puerta | `Mercado` a `text-2xl` (`chart-workspace-page.tsx:574`); estado vacío también `text-2xl` (`:483`) | ✅ |
| 2 | Términos prohibidos en primer nivel | 0 en `chart-workspace-page.tsx`, `trading-status-bar.tsx`, `chart-toolbar-*` | ✅ |
| 3 | `—` | `formatPriceOrAbsent` + `absentDataLabel()` (`trading-status-bar.tsx:116-121`) | ✅ |
| 4 | Disclosure único (`RT-04`) | Toolbar plegada en un único menú `Ajustes de vista` (`app-top-bar.tsx:366-405`) | ✅ |
| 5 | Acción ≠ información (`UI5-17`) | Botones de compra/venta agrupados fuera de la barra de status (`chart-workspace-page.tsx:576-590`) | ✅ |
| 6 | Semáforo | **verde** (P2 declarado: O3-01) | ✅ |

### 3.2 Hallazgos itemizados

| # | Hallazgo | Evidencia (`file:line`) | Regla | Sev. | Veredicto |
| --- | --- | --- | --- | --- | --- |
| O3-01 | La barra de estado dibuja el **host del API** en primer nivel (`web → apiHost`) — dato de arquitectura, aunque es un indicador de sistema | `trading-status-bar.tsx:76-87` (consumido en `:143-146`) | `R-G1`/`RT-01` | **P2** | **abierto (diseño):** decidir si el endpoint baja a nivel 2 o se etiqueta «Diagnóstico» |
| O3-02 | Toolbar avanzada a un único menú «Ajustes de vista» (nivel 2); ya no permanente | `app-top-bar.tsx:363-405` | `RT-01`/`UI5-17` | — | **cerrado (W3)** |
| O3-03 | Tooltip de la barra de estado sin abreviaturas crípticas; mecanismo en nivel 2 | `trading-status-bar.tsx:55-66`, `:176-177` | `UI5-20` | — | **cerrado (W3)** |

**Abierto:** O3-01 (P2, decisión de diseño).

---

## 4. Ola 4 · Asesor (`/research`)

**Veredicto: verde (DONE) con 2 residuos P2 declarados y 2 residuos triviales cerrados.** La fila §5 pedía plegar jerga estadística tras «¿Por qué?».

### 4.1 Checklist §1.3

| # | Ítem | Evidencia | Estado |
| --- | --- | --- | --- |
| 1 | `h1` «Asesor»; primer bloque `¿Por qué esta tesis, este riesgo, esta acción?` responde «¿Por qué?» | `research-page.tsx:185`, `:266-274` | ✅ |
| 2 | Términos prohibidos | `campaignId`/`proposedBy`/`presetKey`/`WFE`/`PBO`/`DSR` plegados bajo `TechnicalDetail` (`:331`, `:579`, `:769`) | ✅ |
| 3 | `—` / `Sin datos.` | `Sin datos.` ausente; `formatOrAbsent` en celdas; literal `—` del helper de nivel 3 → **cerrado** | ✅ |
| 4 | Disclosure único (`RT-04`) | `TechnicalDetail`; sin `<details>`/`<summary>` paralelos | ✅ |
| 5 | Acción ≠ navegación ≠ información | Enlaces «Ver en Asesor»/«Abrir backtest» = navegación; chips = información | ✅ |
| 6 | Semáforo | **verde** (P2: O4-01/O4-02) | ✅ |

### 4.2 Hallazgos itemizados

| # | Hallazgo | Evidencia (`file:line`) | Regla | Sev. | Veredicto |
| --- | --- | --- | --- | --- | --- |
| O4-01 | Columna «Propuesto por» del historial muestra el **enum crudo** (`human`/`grid`/`optuna`/`ai`/`system`) en primer nivel | `research-page.tsx:628` (cabecera), `:660` (`{trial.proposedBy}`) | `R-G1`/`UI5-20` | **P2** | **abierto (diseño):** mapear a rótulos humanos («propuesta humana», «rejilla», …) |
| O4-02 | Columna «Configuración» muestra la **clave de preset cruda** (`presetKey`) en primer nivel | `research-page.tsx:657` (`formatOrAbsent(trial.presetKey, …)`) | `R-G1`/`UI5-20` | **P2** | **abierto (diseño):** alias humano o plegar la columna |
| O4-03 | Helper de nivel 3 `formatMetric` devolvía el literal `"—"` fuera del bloque textual `TechnicalDetail` | `research-trial-result-block.tsx:28`, `:191` | `UI5-14` | — | **cerrado (mecánico):** usa `ABSENT_DATA_TECHNICAL_DASH` (rótulo reservado a nivel 3), semántica idéntica |
| O4-04 | El `title` (tooltip) del resumen de evidencia filtraba «Ledger lab» en la celda «Evidencia» de primer nivel | `research-lab-evidence.ts:95` | `UI5-20` | — | **cerrado (mecánico):** «Registro de laboratorio», semántica idéntica |
| O4-05 | Jerga estadística (`Sharpe`, `campaignId`, `WFE/PBO/DSR`, `Params`/`Manifest`) plegada bajo `TechnicalDetail` | `research-page.tsx:331-539`, `research-trial-result-block.tsx:150-209` | `R-G1` | — | **cerrado (W4)** |
| O4-06 | Métricas de laboratorio solo con valor real (`formatOrAbsent`), sin `0` de relleno | `research-page.tsx:352`, `:449` | `UI5-16` | — | **cerrado (W4)** |

**Abiertos:** O4-01, O4-02 (P2, diseño). **Cerrados en este slice:** O4-03, O4-04.

> **Nota de reconciliación.** `research-first-level.test.tsx` declara `proposedBy`/`presetKey`/`runId` como «identificadores que no se pintan como texto — se pinta su valor». O4-01/O4-02 no contradicen eso: el token no se pinta, pero el **valor crudo** sí aparece en primer nivel; se declaran como P2 de diseño (no son violación del gate de tokens).

---

## 5. Ola 5 · Chrome / command palette

**Veredicto: verde (DONE) con 1 residuo P2 declarado.** La fila §5 pedía un solo mecanismo de profundidad y que la palette separase navegación de ajustes.

### 5.1 Checklist §1.3

| # | Ítem | Evidencia | Estado |
| --- | --- | --- | --- |
| 1 | Soporte (no pantalla con pregunta propia) | barra + rail + palette | n/a |
| 2 | Términos prohibidos | `app-top-bar.tsx`, `command-palette.tsx`, `command-registry.ts` limpios; `keywords` (`libro`/`ledger`) son alias de búsqueda, no copy | ✅ |
| 3 | `—` | `absentDataLabel` donde aplica | ✅ |
| 4 | Un solo mecanismo de profundidad (`RT-04`) | `Ajustes de vista` (menú, nivel 2) + `Configuración` (menú) + palette; el **disclosure** único sigue siendo `TechnicalDetail` | ✅ |
| 5 | Nav ≠ config (`UI5-17`) | La palette separa ajustes con divisor (`command-palette.tsx:139-146`) y agrupa por `group` (`command-registry.ts:33`) | ⚠️ parcial |
| 6 | Semáforo | **verde** (P2: O5-01) | ✅ |

### 5.2 Hallazgos itemizados

| # | Hallazgo | Evidencia (`file:line`) | Regla | Sev. | Veredicto |
| --- | --- | --- | --- | --- | --- |
| O5-01 | La palette mantiene **navegación + configuración + densidad + tema + layout** en un mismo listado; el divisor por grupo mitiga pero no separa en secciones con acción visible | `command-palette.tsx:139-146`, `command-registry.ts:33-210` | `UI5-17`/`RT-04` | **P2** | **abierto parcial (W3 mitigó):** separación literal nav vs ajustes |
| O5-02 | Toolbar de Mercado a un único menú; rail en tres grupos (`Producto`/`Administración`/`Diagnóstico`) | `app-top-bar.tsx:363-405`, `admin-rail.tsx:248-262` | `UI5-08` | — | **cerrado (W3)** |
| O5-03 | Chip de modo operativo fuera de `nav[aria-label="Principal"]`, enlaza a `/auto`, no cambia el modo | `operative-mode-chip.tsx:36-56` | `UI5-21` | — | **cerrado** |

**Abierto:** O5-01 (P2, parcial tras W3).

---

## 6. Ola 6 · Consola avanzada (`/operational-console`)

**Veredicto: P2 abierto (PARTIAL).** La fila §5 pedía «Nivel 3 explícito; sin `—` ni `órdenes UNKNOWN` cuando el dato se muestre fuera de nivel 3». La consola **ya** pliega readiness/runtime/autoeval/telemetría tras `TechnicalDetail` y usa vocabulario Opción B, pero **su primer nivel no está rotulado como nivel 3** y conserva jerga de arquitectura.

### 6.1 Checklist §1.3

| # | Ítem | Evidencia | Estado |
| --- | --- | --- | --- |
| 1 | `h1` «Consola operacional» + copy de propósito | `operational-console-page.tsx:79-88` | ✅ |
| 2 | Términos prohibidos | `PAPER_D_EXECUTE` solo tras el `TechnicalDetail` de la página (`:165-177`); `WFE` en primer nivel (ver O6-01) | ⚠️ |
| 3 | `—` / `UNKNOWN` | `—` cerrado (O6-05); los recuentos de los tres paneles de lifecycle se colapsaban a `0`/verde | ✅ **(O6-06 corregido)** |
| 4 | Disclosure único (`RT-04`) | `TechnicalDetail testId="ops-technical-detail"` (`operational-console-page.tsx:165`) | ✅ |
| 5 | Nav vs acción vs información | «Resolver» = acción; «Ir a Cartera · Posiciones» = navegación; chips de estado = información | ✅ |
| 6 | Semáforo | **P2 abierto** | ⚠️ |

### 6.2 Hallazgos itemizados

| # | Hallazgo | Evidencia (`file:line`) | Regla | Sev. | Veredicto |
| --- | --- | --- | --- | --- | --- |
| O6-01 | `AUTO EVIDENCE` se monta en el **primer nivel** de la consola y rotula filas con jerga de ingeniería (`WFE`, `P(R>0)`, conteos de `fills`) | `auto-evidence-section.tsx:381-388` (montaje en `operational-console-page.tsx:134`), `auto-evidence-report.ts:789-799`, `:84-87` | `R-G1`/`UI5-14` | **P2** | **abierto:** mover bajo el disclosure o rotular el bloque como nivel 3 |
| O6-02 | Primer nivel con jerga de arquitectura interna: `PositionState→Lifecycle`, `reconciliation:portfolio_drift`, `OR-4`, `DEX-3`, `OI-6`/`LR-1` | `operational-console-sections.tsx:175`, `:330`, `:528-531`, `:509` | `R-G1`/`RT-02` | **P2** | **abierto:** la consola es la superficie donde `R-G1` **admite** nivel 3, pero debe declararlo (banner «Diagnóstico · nivel 3») |
| O6-03 | Copy de cabecera mezcla propósito humano con abreviaturas (`recon`, «órdenes sin estado conocido») | `operational-console-page.tsx:82-88` | `RT-02` | **P2** | **abierto (menor):** unificar con el nivel 3 declarado |
| O6-04 | `PAPER_D_EXECUTE` presente en `operational-console-sections.tsx` **solo** bajo el `TechnicalDetail` de la página | `operational-console-sections.tsx:461`, `:718` | `R-G1` | — | aceptado: **artefacto de alcance del gate por fichero** (ver §8). No es fuga de nivel 1 |
| O6-05 | Huecos con vocabulario Opción B (`absentDataLabel`), nunca `—` | `operational-console-sections.tsx:112`, `:166`, `:216` | `UI5-14` | — | **cerrado (W2)** |
| O6-06 | Los tres paneles de lifecycle (primer nivel) **colapsaban el hueco a `0`** y pintaban **SLA verde sin dato** (`?? 0`): `UNKNOWN ≠ 0` violado, no solo el guion | `operational-console-sections.tsx:83-101`, `:145-151`, `:247-263`, `:312-324`; `operational-console-page.tsx:70` | `UI5-14`/`RT-02` | **P1** | **cerrado (esta pasada):** la rejilla exige dato (`!stats`/`!report` ⇒ hueco declarado con `absentDataLabel()`) y el gate `findFirstLevelFalseZeros` lo blinda |

> **O6-06 (registrado en la re-verificación de 2026-10-14).** La pasada anterior declaró la ola 6 «P2 abierto» dando por buenos los huecos por el hecho de que no había `—`. Eso confundía dos invariantes distintos: *sin comodín `—`* (cierto) y *sin colapsar el hueco a `0`/verde* (falso). Los tres paneles de lifecycle se montan en el **primer nivel** de la consola (fuera del `TechnicalDetail` de la página), y con la query deshabilitada (`effectiveAccountId` nulo) o sin material aún, `isLoading` es `false` en TanStack v5 ⇒ el guard `!isLoading && !isError` dejaba pasar la rejilla con `data === undefined`, pintando `pending 0`, `dead 0`, `drift 0` y un **SLA `ok` verde**. La ruta no tiene guarda de cuenta. Corregido gateando la rejilla por **presencia de dato** (patrón `loaded` de `auto-risk-summary.ts`) y sustituyendo cada `?? 0` de primer nivel por `absentDataLabel()`; el `pendingConfirm` de «Cola SEMI» y el literal `"unknown"` de `OpsReconSection` se alinean con el vocabulario Opción B.

**Abiertos:** O6-01, O6-02, O6-03 (P2, diseño). La ola 6 **sigue ABIERTA** (es la única con trabajo de diseño pendiente). **O6-06 (P1) queda cerrado** en esta re-verificación.

---

## 7. Censo ejecutable — superficies añadidas por ola (entregable 2)

Se amplía [`barrido-global-first-level.test.tsx`](../../apps/web/src/features/barrido-global-first-level.test.tsx) con un bloque `WAVE_TOKEN_SURFACES` (token + `—` + `Gate` crudo) y `WAVE_DASH_SURFACES` (solo comodín `—`), cada entrada nombrada por ola:

| Ola | Superficies añadidas | Gate aplicado |
| --- | --- | --- |
| 2 | `mesa-positions-summary.tsx`, `mesa-position-row.tsx`, `operations-panel.tsx`, `position-exit-drawer-actions.tsx` | token + `—` + Gate |
| 2 | `history-page.tsx`, `mesa-libro-panel.tsx` | `—` |
| 3 | `trading-status-bar.tsx`, `chart-toolbar-chart-bar.tsx`, `chart-toolbar-global-bar.tsx`, `daily-nav.ts` | token + `—` + Gate |
| 4 | `research-trial-result-block.tsx`, `research-lab-evidence-summary.tsx`, `estudio-opinion-alarm-poller.tsx` | token + `—` + Gate |
| 4 | `research-lab-evidence.ts` | `—` |
| 5 | `admin-rail.tsx`, `operative-mode-chip.tsx`, `platform-shell.tsx` | token + `—` + Gate |
| 6 | `operational-console-page.tsx`, `ops-incidents-and-links.tsx`, `auto-evidence-section.tsx` | token + `—` + Gate |
| 6 | `operational-console-sections.tsx` | `—` |

**Por qué algunos ficheros no entran en el censo de tokens (declarado, no maquillado):**

- `history-page.tsx` — el token `Ledger` colisiona como **subcadena** con identificadores TS (`LedgerEntryDto`, `formatLedgerEntryLabel`, `api.getAccountLedger`); la palabra **visible** se audita con límite de palabra en [`history-first-level.test.tsx`](../../apps/web/src/features/history/history-first-level.test.tsx).
- `research-lab-evidence.ts` — `WFE`/`PBO` viven solo en `compact`, que se pinta **dentro** del `TechnicalDetail` (panel) o en un resumen de nivel 2/3; el token `WFE` de la fila de evidencia se declara en O6-01.
- `operational-console-sections.tsx` — `PAPER_D_EXECUTE` se monta bajo el `TechnicalDetail` de la **página** (`operational-console-page.tsx:165`), no del fichero: artefacto de alcance del gate por fichero, no violación de nivel 1.

**Control de falsabilidad del censo:** sigue verde con las nuevas superficies; se conservan los `it` de control positivo (`findFirstLevelViolations("<p>Recommendation · runId</p>")` detecta; el guion de prosa y el nivel 3 no se marcan).

**Gate de falso-cero (`O6-06`).** Se añade `findFirstLevelFalseZeros` (`first-level-gate.ts`) y el bloque `FALSE_ZERO_SURFACES` al censo: exige que **no haya `?? 0` fuera de un `TechnicalDetail`** en los tres ficheros de la consola cuyo primer nivel se monta fuera del disclosure (`operational-console-page.tsx`, `operational-console-sections.tsx`, `ops-incidents-and-links.tsx`). Es la fuga simétrica del gate de `—`: el guion admite el hueco, el `0` lo niega. Se acompaña de un test de render por panel (`lifecycle-panel-query.test.tsx`) que verifica que, sin dato, los paneles declaran el hueco y **no** pintan recuentos ni SLA verde.

---

## 8. Residuos `—` (entregable 3)

El residuo declarado «barrido de `—` sin cerrar en dashboard/instruments/journal» **ya no tiene comodines vivos** en el árbol actual: un barrido de esos tres directorios no encuentra ningún literal de hueco fuera de `TechnicalDetail` (solo rayas de **prosa**, que el gate no marca por diseño). Las superficies siguen listadas en `DASH_SURFACES`. **No se cambia semántica de prosa.**

Además se cierran dos residuos triviales fuera de ese trío, en la ola 4:

- `research-trial-result-block.tsx` (`formatMetric` y celda Win Rate) → `ABSENT_DATA_TECHNICAL_DASH` (O4-03).
- `research-lab-evidence.ts` (tooltip «Ledger lab») → «Registro de laboratorio» (O4-04).

---

## 9. Registro ola → hallazgos → estado (entregable 4 · falsable)

| Ola | Título | Alcance pantalla | Estado | Fuente | Evidencia |
| --- | --- | --- | --- | --- | --- |
| **1** | Confirmar · Hoy | `/confirm`, `/mesa` | **DONE** (sellada) | Ol A 1 §3-4 | `confirm-first-level.test.tsx`, `mesa-hoy-first-level.test.tsx` |
| **2** | Cartera · Historial | `/mesa?view=posiciones`, `/history` | **DONE** | **W2** (v2.88.91) | O2-01…O2-03; `history-first-level.test.tsx`; censo §7 |
| **3** | Mercado | `/trading` | **DONE** (1 P2 declarado) | **W3** (v2.88.91) | O3-02/O3-03 cerrados; O3-01 abierto; censo §7 |
| **4** | Asesor | `/research` | **DONE** (2 P2 + 2 triviales) | **W4** (v2.88.91) | O4-03/O4-04 cerrados; O4-01/O4-02 abiertos; censo §7 |
| **5** | Chrome · palette | barra + rail + palette | **DONE** (1 P2 declarado) | **W3** (v2.88.91) | O5-02/O5-03 cerrados; O5-01 abierto parcial |
| **6** | Consola avanzada | `/operational-console` | **ABIERTA (P2)** | **W2** parcial + re-verif. 2026-10-14 | O6-01…O6-03 abiertos; O6-05 cerrado; **O6-06 (P1) cerrado** |

**Agregado:** olas 2-5 **DONE** (los P2 son residuos declarados, no fugas de primer nivel); **ola 6 ABIERTA** (nivel 3 explícito pendiente). Con esto «olas 2..6 abiertas» queda **falsado para 2..5** y **acotado a la ola 6**.

---

## 10. Falsabilidad de esta auditoría

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | Cartera/Historial no exponen `Libro`/`Ledger`/`fills` como copy en primer nivel. | Que `\bLibro\b`/`\bLedger\b`/`\bfills\b` aparezcan fuera de `TechnicalDetail` en `history-page`/`mesa-libro-panel`. |
| 2 | Mercado tiene un `h1` de puerta y una sola toolbar de nivel 2. | Que el `h1` baje de `text-base`, o que la toolbar avanzada vuelva al primer nivel. |
| 3 | Asesor pliega la jerga estadística bajo un `TechnicalDetail` único. | Que `campaignId`/`Sharpe presente`/`WFE`/`PBO` aparezcan fuera del disclosure. |
| 4 | El comodín `—` no existe en primer nivel en las superficies del censo. | Que `findFirstLevelDashes` devuelva algo distinto de `[]`. |
| 5 | El censo cubre las superficies de las olas 2..6. | Que una superficie declarada en §7 desaparezca del test o que un fichero nuevo del alcance quede fuera. |
| 6 | Esta auditoría no cambia motor ni contrato. | Que el diff toque `packages/py/**`, worker, umbrales, Alembic o `contract:gen`. |
| 7 | La consola no colapsa un hueco a `0`/verde en primer nivel (`O6-06`). | Que `findFirstLevelFalseZeros` devuelva algo distinto de `[]` en `FALSE_ZERO_SURFACES`, o que un panel de lifecycle pinte recuentos/SLA sin dato (test de render). |

---

## 11. Ficheros creados / modificados

- **Creado:** `docs/engineering/auditoria-ui-olas-2-6-2026-10-13.md` (este documento).
- **Modificado:** `apps/web/src/features/barrido-global-first-level.test.tsx` (censo §7).
- **Modificado:** `apps/web/src/features/research/research-trial-result-block.tsx` (O4-03).
- **Modificado:** `apps/web/src/features/research/research-lab-evidence.ts` (O4-04).
- **Modificado:** `apps/web/src/features/research/research-first-level.test.tsx` (guardas O4-03/O4-04).

**Re-verificación de profundidad (2026-10-14) — cierre de `O6-06`:**

- **Modificado:** `apps/web/src/components/first-level-gate.ts` (`findFirstLevelFalseZeros`).
- **Modificado:** `apps/web/src/features/barrido-global-first-level.test.tsx` (`FALSE_ZERO_SURFACES` + control de falsabilidad).
- **Modificado:** `apps/web/src/features/operational-console/operational-console-sections.tsx` (rejilla por presencia de dato + `absentDataLabel()`; `OpsReconSection` sin `"unknown"`; dry-run con `formatOrAbsent`).
- **Modificado:** `apps/web/src/features/operational-console/operational-console-page.tsx` (`pendingConfirm` nullable).
- **Modificado:** `apps/web/src/features/operational-console/ops-incidents-and-links.tsx` (`OpsQuickLinksSection` declara el hueco de la cola).
- **Modificado:** `apps/web/src/features/operational-console/lifecycle-panel-query.test.tsx` (test de render por panel).

**Decisión declarada (no se toca):** `research-trial-result-block.tsx:213` (`commissionBps ?? 0` · `slippageBps ?? 0` · `spreadBps ?? 0`) usa el literal `0` **dentro** del `TechnicalDetail` (nivel 3) y representa el **coste por defecto del motor**, no un hueco de medida; se deja como está y queda fuera del gate `FALSE_ZERO_SURFACES`.

---

## 12. Límites declarados

- **Solo lectura del producto:** no se rediseña ninguna pantalla; los únicos cambios de código son el censo y dos residuos mecánicos que preservan semántica.
- **`axe`/Playwright:** no se re-certifica `axe` en vivo ni se ejecuta E2E integrado; se mantiene la deuda declarada (§4 de la [auditoría 6.x](./auditoria-ui-6-x-global-2026-10-08.md) §6).
- **`heading-order` en 11 rutas L1:** deuda preexistente, fuera del alcance de este slice.
- **`Δ motor = 0`:** el diff no toca `packages/py/**`, worker, umbrales, Alembic ni `contract:gen`.
