# Spec — AUTO UI REFACTOR 2.0 (espacio AUTO con sub-navegación propia)

> **AsOf:** 2026-10-05 · **Estado:** **DISEÑO CONGELADO + implementación de arranque** (Fase 0/1).
> **Padre:** [ADR-044](../adr/044-auto-workspace-information-architecture.md) · [ADR-040](../adr/040-user-information-architecture.md) · [AUTO UI SEMANTIC MODEL 1.0](./spec-auto-ui-semantic-model-1-2026-10-05.md) · evidencia [`v2.88.54`](./evidence/v2.88.54/README.md).
> **Naturaleza:** UI / read-model. **`Δ AUTO decision/execution motor = 0`**, sin cambio de contrato HTTP, sin migración Alembic.

Este documento congela **la IA de producto del espacio AUTO** y su mapa a las superficies ya existentes, para dejar de corregir componentes sueltos. **No** sustituye pantallas, **no** toca el motor y **no** re-mide nada.

---

## 0. Propósito y alcance

- **Congela:** las cinco secciones de AUTO, su sub-navegación, el entry point, el mapa sección→superficie existente y el orden narrativo de la operación.
- **NO congela (fuera de este slice):** la implementación definitiva de cada panel; el contrato de explicación por `cycleId`; `PortfolioDecision` durable; PIT histórico institucional; Execution Analysis.

**Regla de compatibilidad:** mientras el espacio y las pantallas discrepen, **manda ADR-044**. El resto se migra de forma **aditiva**.

---

## 1. Principios duros (heredados, no negociables)

| # | Principio | Por qué |
| --- | --- | --- |
| **1** | **No re-derivar.** La UI copia hechos ya producidos; no recalcula PnL, riesgo, fills ni MAE/MFE. | Un segundo cálculo es una segunda verdad. |
| **2** | **`UNKNOWN ≠ 0`.** Un hueco se rotula `NO MEDIDO`/`PARCIAL`; nunca se rellena con `0`. | Raíz del bug del PnL de `v2.88.50`. |
| **3** | **Una operación = una historia.** Un `cycleId`, una secuencia ordenada de etapas. | Se depura *un* ciclo, no un muro de ciclos. |
| **4** | **Hecho ≠ contexto.** Lo que la operación hizo y lo que la originó son bloques distintos. | «¿Por qué existe?» no se responde con un `NO MEDIDO`. |
| **5** | **Read-only y puro.** El view-model no ejecuta, no escribe y es determinista. | Auditable y reproducible. |
| **6** | **Resumen operativo arriba, causalidad técnica bajo demanda.** | La superficie principal dice *qué pasó*; el detalle dice *por qué*. |

---

## 2. Secciones y mapa a superficies existentes

| Sección | Ruta | Superficie(s) existente(s) reutilizada(s) |
| --- | --- | --- |
| **Operar** | `/auto/operar` | Lista de operaciones (ciclos) + [`AutoOperationStoryPanel`](../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx); Oportunidades → `Mesa` `?view=oportunidades` / `Screeners` (enlace). |
| **Operación seleccionada** | `/auto/operar/operacion/:cycleId` | Historia única ordenada (misma fuente que el story panel). |
| **Cartera** | `/auto/cartera` | `MesaLibroPanel`/`OperationsPanel` + enlaces a `/history` y `/accounts`. |
| **Riesgo** | `/auto/riesgo` | Bloques de riesgo de [`operational-console-sections.tsx`](../../apps/web/src/features/operational-console/operational-console-sections.tsx) + enlace a `${CARTERA_RIESGO_PATH}`. |
| **Análisis** | `/auto/analisis` | `DÍA-D` ([`DiaDAutoPanel`](../../apps/web/src/features/auto-monitor/dia-d-auto-panel.tsx)) · Evidencia ([`OpsAutoEvidenceSection`](../../apps/web/src/features/operational-console/auto-evidence-section.tsx)) · Estrategias (`/backtests?tab=strategies`) · Investigación (`/research`). |
| **Sistema** | `/auto/sistema` | Salud AUTO ([`AutoMonitorPage`](../../apps/web/src/features/auto-monitor/auto-monitor-page.tsx) `mode=current`) · Broker/ejecución · Reconciliación (`OpsReconSection`/`OpsLifecycleReconSection`) · Auditoría (`/decision-journal`, `/history`). |

**Criterio de admisión de una sección:** (a) responde a una intención de trabajo del usuario; (b) su contenido sale de una costura durable **existente**; (c) si no hay traza, declara `NO MEDIDO` en lugar de inventar; (d) no expone conceptos internos como destino de navegación.

---

## 3. Contrato de sub-navegación

- Fuente única: [`auto-nav.ts`](../../apps/web/src/features/auto/auto-nav.ts). Labels/rutas unit-testables, sin React.
- Persistente: cambiar de sección no desmonta el shell ni pierde la selección (URL).
- **Accesibilidad:** exactamente un `<h1>` por ruta, un solo `<main>` visible (aportado por el `PlatformShell`; el layout de AUTO no anida `<main>`), jerarquía `h1 → h2 → h3`.
- **Entry point:** `AdminRail` (barra admin, no L1) → `AUTO`; comandos en la command palette. **No** se crea sexta puerta L1 (ADR-040 intacto).

---

## 4. Orden narrativo de una operación (OPERAR)

```
QUÉ PASÓ
   └── Operación: instrumento · estrategia · dirección · entrada
POR QUÉ
   └── Contexto que la originó (universo PIT · régimen · ranking · motivo)
QUÉ RIESGO TENÍA
   └── RIESGO · RESERVA (trazas durables o NO MEDIDO)
QUÉ HIZO EL BROKER
   └── ORDEN · FILL · PROTECCIÓN
QUÉ RESULTADO
   └── LIQUIDACIÓN · RESULTADO (PnL con su medición)
¿QUÉ ENSEÑA DÍA-D?
   └── EXPLANATION (identidad: cycleId + ejes) → heatmap
```

Reglas no negociables sobre la historia (ya implementadas en `v2.88.52`/`v2.88.53`, **no** se regresan):

- `SELECTION` (TOP-N) ≠ `DECISION` (cartera, `NOT_MEASURED`).
- `EXIT` plegado en `SETTLEMENT` (`foldedInto`); una sola fila `REACHED` por hecho.
- `OPPORTUNITY` es **contexto**, no etapa operativa.
- Toda cifra viaja con su **medición** (`MeasurementValue`).

---

## 5. Falsabilidad

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | ADR-040 intacto: AUTO no es puerta L1. | Que AUTO aparezca como L1 en la barra superior o desplace a `Hoy · Mercado · Cartera · Asesor · Laboratorio`. |
| 2 | Un solo `<main>` y un solo `<h1>` por ruta AUTO. | Que `document.querySelectorAll('main').length > 1` o que una sección no tenga `h1`. |
| 3 | Secciones componen superficies existentes. | Que una sección reimplemente el motor o re-derive cifras en vez de enlazar/citar. |
| 4 | `Δ motor = 0`. | Que el diff toque motor/umbrales o que `contract:check` no coincida. |
| 5 | La selección sobrevive en la URL. | Que un selector ignore la query o no la actualice. |

---

## 6. Límites declarados (NO se cierran aquí)

- **`PortfolioDecision` durable (`UI52-02`)** — spine/backend; se declara abierta.
- **Contrato de explicación por `cycleId`** — requiere mover `openapi.json`/`schema.d.ts`; fuera de este slice (la identidad ya se formalizó en `v2.88.53`, la resolución sigue por instrumento).
- **PIT histórico institucional** y **Execution Analysis** (`23 orden_creada_sin_fill`) — P3 abiertas.
- **`CONFIRMED` NO se emite.**
- **No** se re-mide DÍA-D: las cifras OOS se heredan y citan de `v2.88.50`/`v2.88.51`.

---

## 7. Plan por fases (estado)

| Fase | Contenido | Estado |
| --- | --- | --- |
| **0** | ADR-044 + este spec (congelar diseño) | **HECHO** |
| **1** | Shell `/auto` + sub-nav + entry point + gates | **HECHO** |
| **2** | OPERAR canónico (`/auto/operar/operacion/:cycleId`) | **HECHO** |
| **3** | Secciones Cartera · Riesgo · Análisis · Sistema | **HECHO** |
| **4** | `heading-order` (h1/h2/h3) + deuda declarada | **HECHO** |
