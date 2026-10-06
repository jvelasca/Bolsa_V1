# Auditoría UI AUTO para usuario básico — `v2.88.57-beta` (2026-10-05)

> **AsOf:** 2026-10-05 · **Estado:** **AUDITORÍA EN SOLO LECTURA** (no es código, no es un sello).
> **Alcance:** el espacio AUTO completo (`/auto/*`) leído contra el objetivo *«simplificar y dar claridad máxima a toda la operativa, para un usuario básico»*, y con la realidad **dinero virtual DEMO** como principio visual de primer nivel.
> **Base:** `v2.88.57-beta` (package `2.11.57-beta`, Alembic head `048_journal_entry_dedupe_key`).
> **Padres:** [ADR-044](../adr/044-auto-workspace-information-architecture.md) · [spec AUTO UI 2.0](./spec-auto-ui-refactor-2-0-2026-10-05.md) · [spec AUTO UI 2.1](./spec-auto-ui-refactor-2-1-2026-10-05.md) · [spec AUTO UI 2.1.1](./spec-auto-ui-refactor-2-1-1-2026-10-05.md) · [AUTO UI SEMANTIC MODEL 1.0](./spec-auto-ui-semantic-model-1-2026-10-05.md) · [auditoría UI `v2.88.54`](./auditoria-ui-v2.88.54-2026-10-05.md) · [invariante paper virtual](./invariante-paper-virtual-2026-09-25.md).
> **Naturaleza:** UI / producto. **`Δ AUTO decision/execution motor = 0`**, contrato HTTP sin cambio, sin migración Alembic. **No** se re-mide DÍA-D.
> **Compañera:** [spec del cockpit para usuario básico](./spec-auto-cockpit-usuario-basico-2026-10-05.md) (propuesta derivada de estos hallazgos).

---

## 0. Objeto y qué certifica este documento

Este informe **no cambia la aplicación**: audita la **superficie** de AUTO con una lente de producto (usuario sin conocimientos de trading) y declara hallazgos **falsables** con evidencia `fichero:línea`. La pregunta que añade a la auditoría técnica previa (`v2.88.54`) es:

> ¿Puede una persona que no sabe de trading **entender** AUTO —qué puede hacer, qué está haciendo el sistema, con cuánto dinero, qué riesgo tiene y qué ha pasado— sin conocer la arquitectura interna?

La conclusión de partida (coincidente con el dictamen externo): AUTO está **técnicamente muy bien construido** (integridad de deep-link corregida, semántica congelada, read-only honesto) pero **todavía no está diseñado como cockpit de producto** para un no experto. El riesgo ya no es "arquitectura incorrecta": es **densidad y jerga**.

---

## 1. Rúbrica congelada (criterio único)

| Lente | Pregunta operativa |
| --- | --- |
| **5 preguntas del usuario básico** | 1 ¿Qué puedo hacer? · 2 ¿Qué está haciendo AUTO? · 3 ¿Con cuánto dinero? · 4 ¿Qué riesgo tengo? · 5 ¿Qué ha pasado? |
| **Realidad** | ¿Se ve en <1 s que es **DEMO virtual** y **no XTB real**? |
| **Anti-jerga** | ¿Aparece `cycleId`, `TOP-N`, `Fill`, `NO MEDIDO`, `venue`, `PAPER_D_EXECUTE` sin traducir? |
| **Integridad (no regresar)** | No re-derivar · `UNKNOWN ≠ 0` · hecho ≠ contexto · una operación = una historia · resumen arriba / detalle bajo demanda |
| **UI** | Jerarquía `h1/h2/h3`, densidad, estados loading/error/empty, responsive, duplicación de superficies, accesibilidad |

**Rutas auditadas:** `/auto` → `/auto/operar` → `/auto/operar/operacion/:cycleId` → `/auto/cartera` → `/auto/riesgo` → `/auto/analisis` → `/auto/sistema`, más el monitor experto `/auto-monitor` y las superficies de realidad monetaria (Mercado/Libro, Cuentas).

---

## 2. Confirmación: AUTO es 100 % virtual (DEMO/PAPER), no XTB real

Se confirma con código y gates, no solo con documentación:

| Evidencia | Qué declara | Fichero |
| --- | --- | --- |
| Invariante de procedencia | `EXECUTION_REALITY_VIRTUAL_PAPER = "virtual_paper_only"`, `REAL_MONEY_AT_RISK = False`, `LIVE_EXECUTION_AUTHORIZED/UNLOCKED = false`, **fail-closed** (`exit 2` si la venue no es `paper`) | [invariante-paper-virtual-2026-09-25.md](./invariante-paper-virtual-2026-09-25.md) §2–§4 |
| Freeze del espacio AUTO | `PAPER_D_EXECUTE` off · AUTO off · `CONFIRMED` no se emite | [044](../adr/044-auto-workspace-information-architecture.md) §5 |
| Postura de producto | `executionVenueLabel = "EJECUCIÓN: PAPER"`, `"arm ≠ LIVE"`, `AUTO armado · ejecución off` | [paper-auto-posture.ts](../../packages/shared/src/cognitive/paper-auto-posture.ts) L70, L134-L141 |
| Cuenta activa | `simulated → "Demo"`, `paper → "Paper (futuro · broker)"`, `live → "Live (reservado)"` | [use-active-account.ts](../../apps/web/src/features/accounts/use-active-account.ts) L135-L136 |
| Venue | `"Paper"`/`"Live"` con "Efectivo ahora" | [account-venue-preference.tsx](../../apps/web/src/features/accounts/account-venue-preference.tsx) L64, L69 |

**Conclusión:** la operativa AUTO es **totalmente virtual**, con capital y PnL simulados en el ledger interno; el camino LIVE/XTB existe pero está separado y bloqueado. El hueco **no es de motor**: es que esta verdad **hoy no vive en la puerta de entrada de AUTO** (ver F-R1).

---

## 3. Recorrido por superficies

### 3.1 OPERAR — `/auto/operar`

Fichero: [auto-operar-page.tsx](../../apps/web/src/features/auto/auto-operar-page.tsx).

- La sección **promete oportunidades** («Oportunidades e operaciones», hint «Oportunidades, operaciones y la operación seleccionada» en [auto-nav.ts](../../apps/web/src/features/auto/auto-nav.ts) L61) pero **solo pinta una lista de operaciones** (`<ul>` de enlaces, L39-L52). No hay bloque de oportunidades.
- El texto visible del enlace es `{cycle.instrumentId ?? cycle.cycleId}` (L48): con `AAPL`, `AAPL`, `AAPL` produce tres botones **visualmente idénticos** aunque sus `cycleId` difieran. El `href` es correcto; la **identidad humana** no.
- Si la query **falla**, la página no tiene estado de error propio: `view` es `null` y muestra «Sin operaciones en la ventana.» (L36-L38), **confundiendo error con vacío**. El hook sí expone `isError` ([use-auto-operational-monitor.ts](../../apps/web/src/features/auto-monitor/use-auto-operational-monitor.ts) L7-L44) pero la página no lo usa.

### 3.2 OPERACIÓN — `/auto/operar/operacion/:cycleId`

Ficheros: [auto-operacion-page.tsx](../../apps/web/src/features/auto/auto-operacion-page.tsx) + [auto-operation-story-panel.tsx](../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx).

- La **integridad de deep-link** está correcta (helper `resolveAutoOperationSelection`, L78-L96): un `cycleId` explícito inexistente **no** cae a `cycles[0]` y se declara «Operación no encontrada» (L266-L275). Esto es un punto fuerte.
- La historia pinta **12 filas de hechos** en `text-[11px]` (L279-L338) con etiquetas internas: «Selección · TOP-N», «Reserva», «Fill», «Protección», «Liquidación» ([auto-operation-story.ts](../../packages/shared/src/cognitive/auto-operation-story.ts) L201, L227, L239, L264, L272). Para un no experto, «Fill», «TOP-N» y «Reserva» son opacos; `NO MEDIDO` aparece repetidamente por diseño.
- La **explicación DÍA-D se resuelve por `symbol`** (L141 `instrumentId`, L159 `find(item => item.symbol === symbol)`), no por `cycleId`. Dos ciclos de `AAPL` comparten la misma explicación aunque la identidad declarada (`cycleId`/`estrategia`/`entryDay`) sea distinta. Deuda de §21 del dictamen externo — **confirmada**.

### 3.3 CARTERA — `/auto/cartera`

Fichero: [auto-cartera-page.tsx](../../apps/web/src/features/auto/auto-cartera-page.tsx).

- Compone `OperationsPanel` + enlaces (L28, L39-L59). Correcto por ADR-044 (componer, no duplicar).
- La descripción de sección es **lenguaje de ingeniería**: «Reducir / salir encolan Confirm; Confirm es la única firma.» (L22). Un usuario básico no sabe qué es encolar ni qué es Confirm.

### 3.4 RIESGO — `/auto/riesgo`

Fichero: [auto-riesgo-page.tsx](../../apps/web/src/features/auto/auto-riesgo-page.tsx).

- Tres bloques read-only con títulos internos: «Integridad financiera» (L40-L41), «Reconciliación de ciclo de vida» (L55-L57), «Reconciliación de cartera» (L70-L72).
- No hay un **titular de riesgo legible** («estás arriesgando X € de 20.000 €»); el detalle por posición vive en un enlace a Cartera (L76-L83).

### 3.5 ANÁLISIS — `/auto/analisis`

Fichero: [auto-analisis-page.tsx](../../apps/web/src/features/auto/auto-analisis-page.tsx).

- Tabs **bien implementados** (WAI-ARIA): `role="tablist"|"tab"|"tabpanel"`, `aria-controls`/`aria-labelledby`, `tabIndex`, y teclado `ArrowLeft/Right/Home/End` (L54-L108). Estado en URL `?tab=` (L31-L38). **Es el patrón de referencia del propio producto.**
- DÍA-D y Evidencia son paneles densos; Estrategias/Investigación enlazan fuera (correcto, no duplica).

### 3.6 SISTEMA — `/auto/sistema`

Fichero: [auto-sistema-page.tsx](../../apps/web/src/features/auto/auto-sistema-page.tsx).

- «Salud AUTO» monta el `AutoMonitorHeader` + timeline + reservas + concurrencia (L50-L62). El header expone campos expertos: `Venue`, `Granularidad`, `Heartbeat`, `Ventana gracia`, `Ejecución` declarado vs habilitado ([auto-monitor-header.tsx](../../apps/web/src/features/auto-monitor/auto-monitor-header.tsx) L52-L140).
- «Broker / ejecución» es **prosa + enlace** (L74-L86); no dice de forma plana «XTB: no opera / dinero real: no».
- «Reconciliación» **repite** `OpsReconSection`/`OpsLifecycleReconSection` que ya aparecen en Riesgo (L94-L99 vs [auto-riesgo-page.tsx](../../apps/web/src/features/auto/auto-riesgo-page.tsx) L47-L63): la misma superficie dos veces dentro de AUTO.

### 3.7 Monitor experto — `/auto-monitor`

Fichero: [auto-monitor-page.tsx](../../apps/web/src/features/auto-monitor/auto-monitor-page.tsx).

- Cabecera de la cadena completa en jerga: `SIGNAL → TOP-N → RIESGO → RESERVA → ORDEN → FILL → PROTECCIÓN → LIQUIDACIÓN → CICLO CERRADO` (L75-L79). Es honesto y correcto para experto; **no** es el lenguaje del cockpit.

### 3.8 Realidad monetaria (transversal)

- El único rastro de realidad en AUTO es el campo `Venue` del header del monitor (dentro de Sistema) y un texto en DÍA-D («No sustituye la ventana PAPER», [dia-d-auto-panel.tsx](../../apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx) L153).
- La postura completa (`AUTO armado · ejecución off`, `arm ≠ LIVE`, `PAPER_D_EXECUTE`) vive en **Mercado/Libro** ([demo-book-auto-copy.ts](../../apps/web/src/features/trading/demo-book-auto-copy.ts) L17-L31; [trading-status-bar.tsx](../../apps/web/src/features/trading/trading-status-bar.tsx) L171), no en AUTO.

---

## 4. Hallazgos consolidados (fallables)

Severidad: **P0** bloqueo · **P1** próximo trabajo · **P2** deuda arquitectónica/UX · **P3** menor.

| # | Sev | Hallazgo | Evidencia | Cómo se rompe (falsación) |
| --- | --- | --- | --- | --- |
| **F-R1** | **P1** | AUTO no declara en primer nivel que la operativa es **DEMO / dinero virtual**; la verdad vive solo en Sistema → Venue y en Mercado/Libro. Un usuario básico no puede responder «¿dinero real o virtual?» desde Operar. | `rg "dinero\|virtual\|DEMO"` en `features/auto{,‑monitor}` → **0** coincidencias de realidad monetaria; único rastro [dia-d-auto-panel.tsx](../../apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx) L153 y campo `Venue` [auto-monitor-header.tsx](../../apps/web/src/features/auto-monitor/auto-monitor-header.tsx) L56 | Que exista en `/auto/operar` un indicador de realidad visible y verificable. Hoy no existe. |
| **F-O1** | **P1** | La lista de OPERAR es indistinguible con el mismo símbolo: solo pinta `instrumentId` (o `cycleId`). | [auto-operar-page.tsx](../../apps/web/src/features/auto/auto-operar-page.tsx) L48; el test solo comprueba el instrumento ([auto-pages.test.tsx](../../apps/web/src/features/auto/auto-pages.test.tsx) L61) | Que dos ciclos del mismo símbolo se diferencien por texto visible (día/dirección/estado). |
| **F-S1** | **P1 → CERRADA (`v2.88.60`, funcional `71ab00df`)** | La explicación DÍA-D se resuelve por `symbol`, no por `cycleId`: dos operaciones del mismo instrumento comparten explicación. **Cierre:** el artefacto `dia-d-feedback-v2` expone el índice `cycles[]` y el panel resuelve por `cycleId` con fallback declarado PARCIAL ([evidencia `v2.88.60`](./evidence/v2.88.60/README.md)). | [auto-operation-story-panel.tsx](../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx) L141, L159; identidad declarada pero no usada para resolver ([auto-operation-story.ts](../../packages/shared/src/cognitive/auto-operation-story.ts) L120-L128) | Que el artefacto DÍA-D exponga clave por `cycleId` y el panel resuelva por ella. |
| **F-J1** | **P1** | Jerga de motor en la superficie de producto: «Read-only», «NO MEDIDO», «Selección · TOP-N», «Fill», «Reserva», «Detalle técnico (ventana actual)». | [auto-operar-page.tsx](../../apps/web/src/features/auto/auto-operar-page.tsx) L26; [auto-operation-story-panel.tsx](../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx) L205; [auto-operation-story.ts](../../packages/shared/src/cognitive/auto-operation-story.ts) L201-L272 | Que un no experto identifique cada fila de la historia sin glosario. Hoy requiere traducción. |
| **F-O3** | **P2** | En OPERAR, un **error de carga se muestra como vacío** («Sin operaciones»). | [auto-operar-page.tsx](../../apps/web/src/features/auto/auto-operar-page.tsx) L36-L38 (no consulta `isError`) | Que un fallo de red muestre un estado de error distinto del vacío. |
| **F-DUP1** | **P2** | Reconciliación **duplicada** dentro de AUTO (Riesgo y Sistema montan los mismos bloques). | [auto-riesgo-page.tsx](../../apps/web/src/features/auto/auto-riesgo-page.tsx) L47-L63; [auto-sistema-page.tsx](../../apps/web/src/features/auto/auto-sistema-page.tsx) L94-L99 | Que los mismos datos se pinten dos veces dentro del espacio. |
| **F-J2** | **P2** | Descripciones de sección con matices de ingeniería / proceso interno. | [auto-cartera-page.tsx](../../apps/web/src/features/auto/auto-cartera-page.tsx) L22; [auto-riesgo-page.tsx](../../apps/web/src/features/auto/auto-riesgo-page.tsx) L36 | Que la copy de cabecera hable de la intención del usuario, no del mecanismo. |
| **F-A1** | **P2** | El conmutador de vista de DÍA-D usa `role="tablist"`/`role="tab"` **sin** `role="tabpanel"`/`aria-controls` ni navegación por teclado, a diferencia de Análisis. | [dia-d-auto-panel.tsx](../../apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx) L342-L385 (contrasta con [auto-analisis-page.tsx](../../apps/web/src/features/auto/auto-analisis-page.tsx) L54-L108) | Que el tablist DÍA-D omita el enlace tab↔panel o el teclado. |
| **F-A2** | **P2** | AUTO 2.0/2.1 **no** tiene barrido `axe` automatizado propio; el último barrido real es de `v2.88.54` (anterior al espacio AUTO) y `v2.88.57` declara no haberlo repetido. | Sin spec `axe` en `apps/web/e2e` (`Glob *axe*` → 0; `rg axe` en `e2e` → 0); hueco declarado en [evidence/v2.88.57](./evidence/v2.88.57/README.md) §4 | Que exista un spec `axe` que cubra `/auto/*`. Hoy no existe. |
| **F-S2** | **P3** | Densidad tipográfica alta (`text-[11px]`) en la historia de operación, poco «cockpit». | [auto-operation-story-panel.tsx](../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx) L279-L338 | Que una operación se lea a dos niveles (resumen + detalle) sin tabla densa. |
| **F-S3** | **P3** | Un `cycleId` no encontrado se muestra crudo en el `h1` («Operación · does-not-exist»). | [auto-operacion-page.tsx](../../apps/web/src/features/auto/auto-operacion-page.tsx) L24; [auto-pages.test.tsx](../../apps/web/src/features/auto/auto-pages.test.tsx) L74-L89 | Que el estado de ausencia use lenguaje de usuario, no el id técnico. |

> **Nota de método (sondas estáticas).** Los recuentos «0 coincidencias» provienen de `rg` sobre `apps/web/src/features/auto` y `apps/web/src/features/auto-monitor` para términos de realidad monetaria (`dinero|virtual|DEMO|Demo|XTB|LIVE|PAPER`) y de la lectura directa de las 6 páginas + el story panel. Reproducible sin app levantada.

---

## 5. Deudas estructurales (confirmadas con traza)

### 5.1 Contrato DÍA-D `cycleId`-resolutivo (P1 funcional/semántico)

- **Hoy:** la explicación se busca por `symbol` (F-S1). La identidad (`cycleId`, `instrument`, `strategyVersion`, `direction`, `entryDay`, `timeframe`, `regime`) ya se **declara** en `AutoOperationStoryExplanationIdentity` ([auto-operation-story.ts](../../packages/shared/src/cognitive/auto-operation-story.ts) L120-L128) y se pinta en la historia (L360-L368), pero **no** se usa como clave de resolución.
- **Objetivo:** indexar el artefacto por `cycleId` + ejes, sin perder la resolución por instrumento como fallback.
- **Coste:** tocar el artefacto/proyección (`auto_dia_d_feedback.py`) y el contrato HTTP (`openapi.json`/`schema.d.ts`) → **deja de ser UI-only**. Es la deuda §21 del dictamen externo.
- **CERRADA en `v2.88.60-beta` (fase F5, funcional `71ab00df`).** El artefacto `dia-d-feedback-v2` expone `cycles[]` (`cycleId` → identidad del ciclo) y el panel resuelve por `cycleId` con fallback por instrumento declarado **PARCIAL**; el veredicto OOS sigue agregado por instrumento. Evidencia: [`evidence/v2.88.60`](./evidence/v2.88.60/README.md).

### 5.2 `PortfolioDecision` durable (`UI52-02`, P1/P2)

- **Existe en memoria:** `PortfolioDecision` (dataclass) y `decide_portfolio` en [portfolio_decision_engine.py](../../packages/py/application/src/bolsa_application/portfolio_decision_engine.py) L228, L417.
- **Ya se journaliza:** `_journal_entry` publica `event="auto_entry_decision"`, `decision_id`, `reasonCodes`, `tradePlan`, `cycleId` ([auto_v2_entry.py](../../packages/py/application/src/bolsa_application/auto_v2_entry.py) L2235-L2316).
- **Pero NO se expone como paso propio:** `OPERATIONAL_STEPS` **no** contiene `DECISION` ([auto_operational_monitor.py](../../packages/py/application/src/bolsa_application/auto_operational_monitor.py) L66-L76), y la historia mapea `DECISION → sourceStepId: null` ⇒ `NOT_MEASURED` ([auto-operation-story.ts](../../packages/shared/src/cognitive/auto-operation-story.ts) L207-L213). Es decir: **la decisión de cartera está journalizada pero no se presentan como hecho alcanzado**; se declara NO MEDIDO a propósito (correcto hasta que exista la traza del monitor).
- **Falta:** un paso durable `DECISION` en el read-model y su proyección en la historia. No es "inventar": es **exponer** lo que ya se journaliza.

### 5.3 `analytics → ai` (P2 arquitectónico)

- **Acoplamiento real y acotado:** solo `research/llm_draft.py` L7 y `research/llm_indicator_draft.py` L7 importan `get_default_proxy` de `bolsa_ai` (proxy LLM de borradores, **no** el motor cuantitativo). Declarado como dependencia dura en [analytics/pyproject.toml](../../packages/py/analytics/pyproject.toml) L7-L13.
- **El import-linter no lo prohíbe:** `.importlinter` protege `domain` (no infra/analytics/ai) y la independencia `analytics ↔ market`, pero **no** la dirección `analytics → ai` ([.importlinter](../../packages/py/.importlinter) L12-L51).
- **Lectura:** no rompe hoy la pureza determinista del motor, pero permite que un cambio de `bolsa_ai` arrastre a `analytics`. Extracción propuesta: un **puerto** de borrador/asesor en `analytics` + adaptador en la capa de wiring, dejando `bolsa_ai` fuera del camino determinista.

### 5.4 Deuda P2 (tooling / complejidad)

| Ítem | Evidencia |
| --- | --- |
| `PlatformShell` como contenedor de orquestación (≈14 hosts globales + keep-alive de Backtests + rama AUTO `fillHub`) | [platform-shell.tsx](../../apps/web/src/components/layout/platform-shell.tsx) L104-L160 (168 líneas) |
| Documentación que compite con el código (~1.568 piezas; `CHANGELOG.md` ~916 KB) | `docs/**` (recuento del dictamen externo) |
| Tooling Prisma legacy conviviendo con Alembic como autoridad | `packages/database` + `prisma-not-authoritative.mjs` |
| Cinco conceptos de versión visibles (producto/package/web/api/schema) | [CURRENT_SYSTEM.md](../CURRENT_SYSTEM.md) + [versioning.md](./versioning.md) |
| Barrido `axe` real no repetido desde `v2.88.54` | [evidence/v2.88.57](./evidence/v2.88.57/README.md) §4 |

---

## 6. Inventario de pruebas y huecos

| Nivel | Qué cubre hoy | Fichero |
| --- | --- | --- |
| Unit | Resolución de selección + estado «no encontrada» | [auto-operation-story-panel.test.tsx](../../apps/web/src/features/auto-monitor/auto-operation-story-panel.test.tsx) |
| Unit | `h1` por sección y enlace canónico desde OPERAR | [auto-pages.test.tsx](../../apps/web/src/features/auto/auto-pages.test.tsx) |
| E2E mock | Deep-link inválido por ruta y por `?cycle=`; regresión de ruta válida | `apps/web/e2e/gp-e2e-v28857-auto-operacion-invalida-mock.spec.ts` |
| **Hueco** | **Barrido `axe` en navegador real sobre `/auto/*`** (F-A2) | — |
| **Cerrado** | Contrato `cycleId` de la explicación (F-S1) — **`v2.88.60`** | `auto-operation-story-panel.test.tsx` (`resolveExplanationForCycle`) |
| **Hueco** | Estado de error propio en OPERAR (F-O3) | — |

**Hueco declarado (no silenciado):** el barrido en vivo requiere app + API + auth + `axe-core` inyectado; en esta auditoría **no se ejecutó** (no existe spec `axe` en `apps/web/e2e`). Se hereda el método de [auditoría `v2.88.54`](./auditoria-ui-v2.88.54-2026-10-05.md) §0 para repetirlo en un sello de UI.

---

## 7. Cómo se reproduce

```bash
# Localizar el hueco de realidad monetaria en AUTO (debe salir acotado).
rg -n "dinero|virtual|DEMO|Demo|XTB|PAPER" apps/web/src/features/auto apps/web/src/features/auto-monitor

# La lista de OPERAR pinta solo el instrumento.
rg -n "instrumentId \?\? cycle.cycleId" apps/web/src/features/auto

# La explicación resuelve por símbolo.
rg -n "item.symbol === symbol|instrumentId" apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx

# El acoplamiento analytics -> ai.
rg -n "from bolsa_ai" packages/py/analytics/src

# DECISION no está en el spine del monitor.
rg -n "OPERATIONAL_STEPS" -A 12 packages/py/application/src/bolsa_application/auto_operational_monitor.py
```

---

## 8. Qué NO se toca / límites

- **`Δ AUTO decision/execution motor = 0`**, contrato HTTP sin cambio, sin migración, no se re-mide DÍA-D.
- Este informe **no implementa** ninguna corrección; la propuesta vive en la [spec del cockpit](./spec-auto-cockpit-usuario-basico-2026-10-05.md).
- **No** cierra `PortfolioDecision`, el contrato `cycleId`, PIT institucional ni Execution Analysis: los **localiza** y los deja declarados.
- Se respetan los 6 principios duros de AUTO UI 2.0 (no re-derivar · `UNKNOWN ≠ 0` · una operación = una historia · hecho ≠ contexto · read-only/puro · resumen arriba / detalle a demanda).
