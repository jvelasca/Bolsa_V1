# Auditoría UI 6.x — lenguaje global + oleada 1 (Confirmar · Hoy)

> **AsOf:** 2026-10-08 · **Estado:** **AUDITORÍA EN SOLO LECTURA** (no es código, no es un sello).
> **Base:** tag anotado `v2.88.90-beta` (objeto `c220df76` → commit `c15873fd`); `Release tag CI` [`37774540104`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37774540104) **VERDE**; `Δ motor = 0`; contrato HTTP sin cambio; head Alembic `052_top3_opportunities`.
> **Padres:** [UI Contract 5.0](./spec-ui-contract-5-0-2026-10-08.md) · [Mapa de problemas UI 5.0](./auditoria-ui-5-0-mapa-problemas-2026-10-08.md) · [plan único UI 6.0](./plan-ui-6-0-2026-10-08.md) · [spec AUTO UI definitiva](./spec-auto-ui-definitiva-2026-10-07.md) · [ADR-040](../adr/040-user-information-architecture.md) · [ADR-044](../adr/044-auto-workspace-information-architecture.md) · [ADR-045](../adr/045-ui-contract-5-0.md) · [domain-language](../domain-language.md).
> **Naturaleza:** UI / producto / semántica. **No** se audita motor, backend ni contrato HTTP. **No** se toca código en este slice. **No** se crea tag.
> **Sucesor:** backlog priorizado (§5) → plan de slices e implementación en un ciclo posterior.

---

## 0. Pregunta y método

Con AUTO ya coherente por dentro y la HOME de `v2.88.90` corregida, la pregunta cambia de nivel:

> ¿Dónde se sigue comportando la aplicación como una herramienta técnica en lugar de como una aplicación para un usuario básico?

Se audita **toda** la app bajo dos reglas nuevas y se detalla la **oleada 1**, fijada por el encargo en **Confirmar** y **Hoy** (donde `información → acción → firma` se encuentran y donde queda la mayor ambigüedad de pregunta).

**Método (esta auditoría):** lectura de código en solo lectura (`file:line`), conteo de términos de la lista prohibida ([Mapa UI 5.0](./auditoria-ui-5-0-mapa-problemas-2026-10-08.md) §8) y del comodín `—`, y verificación de la cobertura de `Sin dato todavía` ([helper `absent-data.ts`](../../apps/web/src/components/absent-data.ts)). **No** se re-ejecuta `axe`: se **hereda** la certificación de `v2.88.90` (rutas tocadas 9/9; AUTO 14/14) y se marcan como deuda las rutas no cubiertas.

---

## 1. Rúbrica de auditoría

### 1.1 Las dos reglas (principio rector UI 6.x)

| ID | Regla | Cómo se falsa |
| --- | --- | --- |
| `R-G1` · **Se entiende sin el backend** | Ninguna superficie de **primer nivel** muestra arquitectura interna (identificadores, tokens de modelo, pasos de pipeline, nombres de motor). | Que el primer nivel muestre `runId`, `cycleId`, `Recommendation`, `DecisionSession`, `Gate`, `ledger`, `fill`, `Risk Gate`, `PAPER_D execute`. |
| `R-G2` · **Una pantalla = una pregunta** | El **primer bloque** responde a la pregunta principal de la pantalla; no a una segunda ni a una explicación de mecanismo. | Que el primer bloque de la pantalla sea copy explicativa (`R-G2`) o una segunda pregunta (`RT-03`). |

**Nota honesta (solape con el contrato vigente).** `R-G1` es una lectura de **RT-02** («la app explica el resultado, no cómo está construida») y `R-G2` es una lectura de **UI5-01** («una pantalla = una pregunta») + **RT-03** («dos lecturas»). Por tanto **no son reglas nuevas de implementación**, sino la **vara de medir** de la fase: se declaran aquí como principio rector y se propone su enmienda formal al contrato en el ciclo siguiente (no se aplica en este documento).

### 1.2 Tabla pantalla → pregunta principal (vara de medida)

| Pantalla | Pregunta principal (acordada) |
| --- | --- |
| Hoy | ¿Qué requiere mi atención? |
| Mercado | ¿Qué está ocurriendo? |
| Cartera | ¿Qué tengo? |
| Asesor | ¿Por qué? |
| Laboratorio | ¿Qué estamos aprendiendo? |
| AUTO | ¿Qué está haciendo AUTO? |
| Confirmar | ¿Qué voy a autorizar? |

### 1.3 Checklist uniforme por pantalla (falsable)

1. `h1` único y visible; el primer bloque responde **una** pregunta.
2. Cuenta de términos prohibidos (§8 del Mapa UI 5.0) en primer nivel.
3. Cuenta de `—` / `NO MEDIDO` / `Sin datos` frente al vocabulario Opción B (`Sin dato todavía` / `No aplica` / `No disponible`).
4. Disclosures de profundidad: debe existir **uno solo** (`RT-04`).
5. Nav vs acción vs información (`UI5-17`).
6. Semáforo final: P0 / P1 / P2 / verde.

### 1.4 Niveles de lectura (heredados, §4 del contrato)

- **Nivel 1 · usuario:** respuesta, veredicto, frase (≥ `text-sm`).
- **Nivel 2 · avanzado:** componentes, motivos, contexto (plegado).
- **Nivel 3 · auditoría:** `runId`, `cycleId`, `reasons` crudos, `venue` (`—` permitido aquí).

---

## 2. Inventario global pantalla → pregunta

| Pantalla / ruta | Pregunta principal | ¿La responde? | Segunda pregunta / fuga detectada | Sev. |
| --- | --- | --- | --- | --- |
| **Hoy** `/mesa` | ¿Qué requiere mi atención? | Parcial | Explica arquitectura interna («Ranking Estudio, Libro y Decisiones viven en Ver detalles — Hoy no es Mercado») y declara una pregunta distinta («¿qué debo hacer?») | **P1** |
| **Mercado** `/trading` | ¿Qué está ocurriendo? | Parcial | `h1` presente pero diminuto (`text-sm`); toolbar avanzada permanente (layout, toggles, reset, abrir en otra pestaña); tooltip «Mostrar DECISIÓN» | **P1/P2** |
| **Cartera** `/mesa?view=posiciones` + `/history` | ¿Qué tengo? | Parcial | `Libro` (alias deprecado) y `Ledger y fills` en primer nivel de Historial; `—` en filas de Posiciones | **P1** |
| **Asesor** `/research` | ¿Por qué? | Parcial | Jerga estadística en primer nivel (`Sharpe`, `campaignId`, `proposedBy`, `presetKey`, `K consumido`, `—`, `Sin datos.`) | **P1** |
| **Laboratorio** `/backtests` | ¿Qué estamos aprendiendo? | Sí | Renombrado a `Laboratorio`; `title` aclara «Backtesting …» | P2 |
| **AUTO** `/auto/*` | ¿Qué está haciendo AUTO? | Sí | Estabilizado en `v2.88.90`; solo verificación (no se reabre) | verde |
| **Confirmar** `/confirm` | ¿Qué voy a autorizar? | **No** | El primer bloque explica el mecanismo y aparece un bloque técnico no plegado (`Recommendation`, `DecisionSession`, `Policy Gate`) | **P0** |
| **Chrome global** (barra + rail + barra de estado + palette) | — | Parcial | Toolbar avanzada en primer nivel; la palette mezcla navegación/config/densidad/tema/layout en un mismo listado | P1 |
| **Consola avanzada** `/operational-console` | (diagnóstico, nivel 3) | n/a | Deuda declarada: `—` y `órdenes UNKNOWN` (§6) | P2 |

### 2.1 Chrome global

- **`AppTopBar`** ([`app-top-bar.tsx`](../../apps/web/src/components/layout/app-top-bar.tsx)): doble activo `Hoy`/`Cartera` **ya resuelto** (`isCarteraRoute` + `!isCarteraRoute`, líneas 324-327, 435-440). Persisten: toolbar avanzada permanente (selector de layout nombrado, tres toggles, reset, abrir en otra pestaña, líneas 519-609), badge de «pendientes de firma» sobre la navegación `Hoy` (líneas 442-455) y el `title` de `Hoy` = «¿Qué debo hacer hoy?» (línea 441).
- **`AdminRail`** ([`admin-rail.tsx`](../../apps/web/src/components/layout/admin-rail.tsx)): tres grupos correctos (`Producto` / `Administración` / `Diagnóstico`, líneas 249-262); sin el stub `Estadísticas · pronto`. Correcto (`UI5-08`).
- **`TradingStatusBar`** ([`trading-status-bar.tsx`](../../apps/web/src/features/trading/trading-status-bar.tsx)): abreviaturas y `PAPER_D_EXECUTE` **ya retirados**; usa `absentDataLabel()` (líneas 19, 122). El tooltip mantiene lenguaje de mecanismo (`ARMADO ≠ EJECUTADO`, líneas 176-177) en **nivel 2** (aceptable).
- **Command palette** ([`command-registry.ts`](../../apps/web/src/features/command-palette/command-registry.ts)): agrupa por `group`, pero en un mismo listado conviven navegación, configuración, densidad, tema y layout (líneas 55-210); todo corre por un único `run`. Es la deuda de `UI5-17` ya anotada como «verificado (no-op funcional)».

### 2.2 AUTO (solo verificación)

La HOME de `v2.88.90` cumple: un solo chip, hueco declarado una vez, `Ver todas las operaciones` fuera de Oportunidades. **No se reabre**; cualquier defecto concreto iría a backlog, no a esta oleada.

---

## 3. Oleada 1 · Confirmar (`/confirm`)

### 3.1 La pregunta

La pregunta principal es **«¿Qué voy a autorizar?»**. La pantalla actual **no** la responde en el primer bloque: responde «cómo está construido el sistema» (`R-G1`) y deja un bloque técnico sin plegar. Es el punto donde `información → acción → firma` se encuentran, así que la severidad es la más alta de la auditoría.

### 3.2 Hallazgos

| # | Hallazgo | Evidencia (`file:line`) | Regla | Sev. |
| --- | --- | --- | --- | --- |
| C-01 | Bloque **«Recommendation»** técnico en primer nivel, sin plegar: `recommendationId`, `action`, `Fusión Runtime · score`, `DecisionSession: sessionId`, `Policy Gate`, `Assessments: <tipos>`, `Prediction: … modelId`. | [`supervised-f3-panel.tsx:1398-1504`](../../apps/web/src/features/settings/supervised-f3-panel.tsx) | `R-G1`/`RT-02` (§8) | **P0** |
| C-02 | **Segunda escalera** con tokens ingleses en `data-testid` (`…-proposed/-signed/-submitted/-filled`, `data-step`) y copy con `Fill`/`settlement`/`fill`. | [`live-virtual-order-gateway.tsx:55-108`](../../apps/web/src/features/confirm/live-virtual-order-gateway.tsx) · [`live-virtual-ladder.ts:28-35`](../../apps/web/src/features/confirm/live-virtual-ladder.ts) | `UI5-09`, `UI5-20`, §8 | **P0** |
| C-03 | Metáfora/mecanismo en primer nivel: «Telegrama al broker», `DE`/`A`/`REF`, «Fuentes: TradePlan · DECISIÓN · risk / ticket Confirm», «CTA abajo». | [`live-virtual-order-gateway.tsx:145-155`](../../apps/web/src/features/confirm/live-virtual-order-gateway.tsx), `:204`, `:211-212` | `R-G1`/`RT-02` | P1 |
| C-04 | Cabecera y cola con pasos internos: «SEMI · Assessment(s) → Recommendation → Confirm. Cola: Finalistas, Radar, Scan, Gráfico.» y «Orden: óptimo → geo (…)». | [`supervised-f3-panel.tsx:929-937`](../../apps/web/src/features/settings/supervised-f3-panel.tsx), `:968-970` | `R-G1`/`RT-02` | P1 |
| C-05 | Alias deprecado `Libro` y jerga de navegación interna: «rail Coach → Libro DEMO». | [`supervised-f3-panel.tsx:1088-1091`](../../apps/web/src/features/settings/supervised-f3-panel.tsx), `:466`, `:598`, `:1325` · [`live-virtual-why.ts:103`](../../apps/web/src/features/confirm/live-virtual-why.ts) | `UI5-20` | P1 |
| C-06 | Frases de mecanismo en el bloque «Qué NO implica»: «Ranking ≠ BUY.», «Arm ≠ Execute.». | [`live-virtual-why.ts:122-126`](../../apps/web/src/features/confirm/live-virtual-why.ts) | `RT-02` | P1 |
| C-07 | El primer bloque **no responde** «¿Qué voy a autorizar?»: `h1` «Confirmar» + copy «La app propone operaciones sobre tu Universo. Tú las firmas aquí. Nunca se envían solas.» | [`confirm-content.tsx:41-50`](../../apps/web/src/features/confirm/confirm-content.tsx) | `R-G2`/`UI5-01` | P1 |
| C-08 | Disclosures con **idioms distintos** coexistentes: «Ajustes avanzados», «Para ti (por qué)», «Detalle técnico». | [`supervised-f3-panel.tsx:1244`](../../apps/web/src/features/settings/supervised-f3-panel.tsx) · [`live-virtual-order-gateway.tsx:192`](../../apps/web/src/features/confirm/live-virtual-order-gateway.tsx) | `RT-04` | P2 |
| C-09 | `account-venue-preference.tsx` conserva `Paper`/`Live` y «enviada no significa ejecutada»; deuda `submitted ≠ fill`. | [`account-venue-preference.tsx:42-69`](../../apps/web/src/features/accounts/account-venue-preference.tsx) | §8, deuda D | P2 |

### 3.3 Lectura

- **C-01** es el hallazgo dominante: no es jerga de un chip, es un bloque entero de identificadores de modelo y de sesión que el usuario ve **junto a los botones de firma**, sin pasar por «Ajustes avanzados». Debe plegarse bajo un único disclosure (`RT-04`).
- **C-02** confirma que la «escalera universal» se **pinta** en español pero se **codifica** en inglés: los tokens siguen en el DOM vía `data-testid`/`data-step` y en el diccionario de copy (`Fill SIMULADO · ≠ settlement real`). Esto es exactamente lo que `v2.88.90` declaró «fuera del DOM» y no lo está a nivel de atributo.
- **C-05** muestra que `Libro` sobrevive fuera de `daily-nav`, contradiciendo `UI5-20` (un término = un significado; `Libro` alias deprecado).

**Veredicto Confirmar: P0.** La firma no puede explicarse con lenguaje de backend.

---

## 4. Oleada 1 · Hoy (`/mesa`)

### 4.1 La pregunta

Pregunta principal acordada: **«¿Qué requiere mi atención?»**. La pantalla es un inbox de cuatro cubos + un pie. El primer bloque (inbox) responde razonablemente, pero persisten dos fugas: el **pie** explica arquitectura interna (`R-G1`) y la **pregunta declarada** («¿qué debo hacer?») no coincide con la acordada.

### 4.2 Hallazgos

| # | Hallazgo | Evidencia (`file:line`) | Regla | Sev. |
| --- | --- | --- | --- | --- |
| H-01 | Pie de la HOME explica arquitectura interna y usa el alias `Libro`: «Ranking Estudio, Libro y Decisiones viven en Ver detalles — Hoy no es Mercado.» | [`mesa-hoy-page.tsx:655-674`](../../apps/web/src/features/mesa/mesa-hoy-page.tsx) | `R-G1`/`RT-02`, `UI5-20` | P1 |
| H-02 | Menú «Avanzado»: etiqueta «Ranking Estudio» con hint «Ranking Estudio — no es una orden · **Ranking ≠ BUY**» y «**Libro** / Posiciones». | [`mesa-hoy-view.ts:59-61`](../../apps/web/src/features/mesa/mesa-hoy-view.ts), `:78` | `RT-02`, `UI5-20` | P1 |
| H-03 | `Gate {row.gate}` en la ficha de oportunidad. | [`mesa-candidates-panel.tsx:225`](../../apps/web/src/features/mesa/mesa-candidates-panel.tsx) | §8, deuda C | P2 |
| H-04 | Comodín `—` de primer nivel en Oportunidades (`opinión`, `vigencia`, `updatedLabel`, `Sector`). | [`mesa-candidates-panel.tsx:189`](../../apps/web/src/features/mesa/mesa-candidates-panel.tsx), `:265`, `:472`, `:282-285` | `UI5-14` | P1 |
| H-05 | Jerga de arquitectura interna en Oportunidades: «Añade valores a **Estudio**», «Abrir Señales · lista **{estudio}**». | [`mesa-candidates-panel.tsx:522-533`](../../apps/web/src/features/mesa/mesa-candidates-panel.tsx) | `R-G1` | P1 |
| H-06 | Cadena de estados en mayúsculas tras el banner de incidentes: «Nuevas entradas: BLOQUEADAS · Automatismos: BLOQUEADOS · Posiciones: VISIBLES · Desriesgo humano: DISPONIBLE». | [`mesa-hoy-page.tsx:632-634`](../../apps/web/src/features/mesa/mesa-hoy-page.tsx) | `RT-01`/§8 | P2 |
| H-07 | Comodín `—` en filas de **Posiciones** (vista Cartera dentro de Hoy). | [`mesa-position-row.tsx:46`](../../apps/web/src/features/mesa/mesa-position-row.tsx), `:384`, `:390`, `:396`, `:420` | `UI5-14` | P1 |
| H-08 | Pregunta declarada «¿qué debo hacer?» ≠ acordada «¿Qué requiere mi atención?». | [`mesa-hoy-page.tsx:568-576`](../../apps/web/src/features/mesa/mesa-hoy-page.tsx) · [`app-top-bar.tsx:441`](../../apps/web/src/components/layout/app-top-bar.tsx) | `R-G2` | P2 |
| H-09 | H2 «**Libro** · Posiciones» y «Misma superficie que el Libro histórico». | [`mesa-libro-panel.tsx:39`](../../apps/web/src/features/mesa/mesa-libro-panel.tsx), `:93` | `UI5-20` | P2 |
| H-10 | Componente `MesaOperationalHeaderStrip` arrastra `Risk Gate` y `PAPER_D execute (env)` y comodín `—`; **no está montado** en Hoy (un test lo prohíbe), pero queda latente si se remonta. | [`mesa-operational-header.tsx:63`](../../apps/web/src/features/mesa/mesa-operational-header.tsx), `:151`, `:175` · [`mesa-hoy-page.test.ts:325`](../../apps/web/src/features/mesa/mesa-hoy-page.test.ts) | §8 | P2 |

### 4.3 Lectura

- El inbox ([`daily-desk-inbox.tsx:169-172`](../../apps/web/src/features/mesa/daily-desk-inbox.tsx)) **sí** responde «¿qué requiere mi atención?» con copy honesto («estar arriba en la lista no es una compra»). El problema no está en el inbox, está en **su pie** (H-01) y en el **menú Avanzado** (H-02), que reintroducen el lenguaje de mecanismo que `v2.88.90` retiró del primer nivel de la HOME de AUTO.
- `Estudio` (H-05) es el caso más claro de `R-G1`: la UI nombra una lista interna con su `listId` crudo (`estudio`) en vez de explicar el resultado («tu universo de análisis»).

**Veredicto Hoy: P1.** El cockpit funciona; el pie y el menú Avanzado lo contaminan.

---

## 5. Backlog priorizado (oleadas 2..n)

| Oleada | Pantalla | Trabajo | Sev. | Regla |
| --- | --- | --- | --- | --- |
| **1 (esta)** | Confirmar · Hoy | C-01…C-09 · H-01…H-10 | P0/P1/P2 | `R-G1`, `R-G2`, `RT-02`…`RT-04`, `UI5-09/14/20` |
| 2 | Cartera (`/mesa?view=posiciones`, `/history`) | Retirar `Libro`/`Ledger`/`fills` de primer nivel; `—` → vocabulario Opción B; separar «¿qué tengo?» de «¿qué ha pasado?» ([`history-page.tsx:180`](../../apps/web/src/features/history/history-page.tsx), `:183`, `:224`; [`mesa-libro-panel.tsx:39`](../../apps/web/src/features/mesa/mesa-libro-panel.tsx)) | P1 | `UI5-13/14/20`, `R-G1` |
| 3 | Mercado (`/trading`) | `h1` visible con tamaño de puerta; toolbar avanzada a segundo nivel/palette; separar acción de información ([`app-top-bar.tsx:519-609`](../../apps/web/src/components/layout/app-top-bar.tsx)) | P1/P2 | `R-G2`, `RT-01`, `UI5-17` |
| 4 | Asesor (`/research`) | Plegar jerga estadística (`Sharpe`, `campaignId`, `proposedBy`, `presetKey`, `K consumido`, `—`, `Sin datos.`) tras «¿Por qué?» ([`research-page.tsx:296`](../../apps/web/src/features/research/research-page.tsx), `:330`, `:361`, `:409`, `:440`, `:474`) | P1 | `R-G1`, §8 |
| 5 | Chrome/palette | Un solo mecanismo de profundidad; palette separa navegación de ajustes con acción visible | P2 | `RT-04`, `UI5-17` |
| 6 | Consola avanzada | Nivel 3 explícito; sin `—` ni `órdenes UNKNOWN` cuando el dato se muestre fuera de nivel 3 | P2 | `UI5-14` |

**Dependencia:** la enmienda formal de `R-G1`/`R-G2` al contrato (§1.1) debería preceder a la implementación, igual que `RT-01…RT-04` precedieron a UI 6.0.

---

## 6. Deudas arrastradas (inventario)

| Deuda | Estado | Ubicación |
| --- | --- | --- |
| `heading-order` (best-practice) en 11 rutas L1 | Abierta desde `v2.88.54`; preexistente, fuera del alcance de los sellos UI 6.0 | Declarada en §4 de [entrega v2.88.90](./entrega-auditoria-externa-mia-v2.88.90-2026-10-08.md) (no hay artefacto de código en `apps/web`) |
| Playwright **integrado** (E2E contra stack real) | `opt-in` / `skipped`; la certificación `axe` de `v2.88.90` es **con mocks** | [entrega v2.88.90](./entrega-auditoria-externa-mia-v2.88.90-2026-10-08.md) §4 |
| `Gate N` en `mesa-candidates-panel` | Conservado como dato de decisión (no prohibido) | [`mesa-candidates-panel.tsx:225`](../../apps/web/src/features/mesa/mesa-candidates-panel.tsx) |
| `submitted ≠ fill` en `account-venue-preference.tsx` | Conservado fuera de los slices | [`account-venue-preference.tsx:42-44`](../../apps/web/src/features/accounts/account-venue-preference.tsx) |
| Cierre `COMPLETE → Posición cerrada` sin traza intermedia | Coherente con el modelo durable; pertenece al backend | `auto-operation-ladder.ts` |
| `PortfolioDecision` durable · materialización SIM · PIT histórico · Execution Analysis | Abiertos (spine/backend) | §4 de [entrega v2.88.90](./entrega-auditoria-externa-mia-v2.88.90-2026-10-08.md) |
| 23 avisos `react-hooks/exhaustive-deps` | Preexistentes; 0 errores | `eslint` |

---

## 7. Falsabilidad de esta auditoría

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | El primer nivel de Confirmar no muestra identificadores de modelo/sesión. | Que `Recommendation`, `DecisionSession`, `Policy Gate` o `recommendationId` aparezcan fuera de un disclosure. |
| 2 | Existe una única escalera de operación, sin tokens ingleses en el DOM. | Que `live-virtual-ladder-proposed/-signed/-submitted` (o `data-step`) sigan en el DOM. |
| 3 | `Libro` no se muestra como término en la UI (alias deprecado). | Que `Libro` aparezca en `/mesa`, `/history` o `/confirm`. |
| 4 | El comodín `—` no aparece en primer nivel. | Que `—` se pinte en Oportunidades o en filas de Posiciones. |
| 5 | La pregunta de Hoy es «¿Qué requiere mi atención?». | Que la UI declare «¿qué debo hacer?» sin reconciliación. |
| 6 | `Estudio` (lista interna) no se nombra con su `listId` en primer nivel. | Que la UI muestre «lista estudio». |
| 7 | Esta auditoría no cambia motor ni contrato. | Que el diff toque `packages/py/**`, worker, umbrales, Alembic o `contract:gen`. |

---

## 8. Límites declarados

- **Solo lectura:** este documento **no** implementa correcciones, **no** añade tests y **no** re-certifica `axe`; hereda la certificación de `v2.88.90`.
- **Confirmar y Hoy** son la oleada 1 detallada; el resto de pantallas se inventarían a nivel de pregunta + severidad (§2) y se priorizan en el backlog (§5).
- **No** se edita el contrato vigente ([`spec-ui-contract-5-0`](./spec-ui-contract-5-0-2026-10-08.md), [`ADR-045`](../adr/045-ui-contract-5-0.md)); la enmienda `R-G1`/`R-G2` se **propone**.
- **No** se reabre AUTO ni se re-mide el motor.
- **`Δ motor = 0`** por construcción: el árbol auditado es el del tag `v2.88.90-beta`; comprobable con `git diff --name-only v2.88.89-beta v2.88.90-beta -- packages/py` (vacío) sobre el sello base.

---

## 9. Barrido global — cierre de residuos declarados (rama, sin tag)

> **AsOf:** 2026-10-08 · **Estado:** ejecución en rama `ui6x-barrido-global-residuos`, **sin sello ni tag**.
> **Naturaleza:** UI/semántica y tests en `apps/web/**`. **`Δ motor = 0`** (el diff no toca `packages/py/**`, worker, umbrales, Alembic, `contract:gen` ni `package.json`/`meta.bump`).
> **Precedente:** correcciones que `v2.88.91-beta` dejó **abiertas** en su [entrega §4](./entrega-auditoria-externa-mia-v2.88.91-2026-10-08.md).

| # | Residuo declarado en §4 de la entrega | Cierre en este barrido |
| --- | --- | --- |
| 1 | `Gate N` residual | `gateHumanLabel` extraído a [`components/gate-label.ts`](../../apps/web/src/components/gate-label.ts) y aplicado en [`hoy-command-strip.tsx`](../../apps/web/src/features/trading/hoy-command-strip.tsx) y [`mesa-entry-queue-panel.tsx`](../../apps/web/src/features/operations/mesa-entry-queue-panel.tsx) (filtro y celda). |
| 2 | `submitted ≠ fill` | Unificado a «Enviar una orden no significa que se haya ejecutado» en `account-venue-preference.tsx`, `live-virtual-order-gateway.tsx`, `live-virtual-banner.tsx` y `mesa-operational-bar.tsx`. |
| 3 | `Libro`/`Ledger` de primer nivel | Retirados en dashboard, cuentas (panel/wizard/settings), fiscal, screeners, screeners-page, `backtesting-tracker`, ayuda (`app-help-menu.tsx`, `mesa-tip-catalog.ts`), `paper-paths-copy` y los `*-propose-supervised`/`position-exit-drawer-actions`. Identificadores de código y comentarios no se tocan. |
| 4 | Barrido del comodín `—` | `findFirstLevelDashes` añadido a [`first-level-gate.ts`](../../apps/web/src/components/first-level-gate.ts); fallbacks `"—"` sustituidos por `absentDataLabel()` en dashboard, cuentas, instrumentos, fiscal y screeners. |
| 5 | Gates de primer nivel fuera de alcance | Nuevo [`barrido-global-first-level.test.tsx`](../../apps/web/src/features/barrido-global-first-level.test.tsx): Mercado (`chart-workspace-page`, `app-top-bar`), Laboratorio (`backtests-page` + pestañas), chrome (`app-top-bar`, `command-registry`, `command-palette`) y el barrido `—` de las superficies del punto 4. |

**Verificación (local):** `typecheck` OK · `lint` **0 errores** (23 avisos `react-hooks/exhaustive-deps` preexistentes) · **277 ficheros / 1687 passed** (+1 fichero / +25 tests sobre `v2.88.91`) · `git diff --name-only -- packages/py` **vacío** ⇒ **`Δ motor = 0`**.

**Límites de este documento (§8 sigue vigente):** este §9 **sí** implementa y añade tests (a diferencia del cuerpo de solo lectura); **no** crea tag, **no** re-certifica `axe` en vivo ni activa el `playwright` integrado (`opt-in`), y **no** reabre AUTO.
