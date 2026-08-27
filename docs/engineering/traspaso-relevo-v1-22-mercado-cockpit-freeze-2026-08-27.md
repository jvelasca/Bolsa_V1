# RELEVO — V1.22 freeze conceptual (Mercado cockpit)

> **AsOf:** 2026-08-27 · **Estado:** **FREEZE + H1/H2 + cockpit + Hoy slim + Asesor explica**.
> **Padre:** [`traspaso-relevo-tag-v1-21-beta-2026-08-27.md`](./traspaso-relevo-tag-v1-21-beta-2026-08-27.md) · [ADR-041](../adr/041-operational-coherence.md) · [ADR-040](../adr/040-user-information-architecture.md) · propuesta absorbida [`traspaso-relevo-hoy-cobertura-estudio-propuesta-2026-08-27.md`](./traspaso-relevo-hoy-cobertura-estudio-propuesta-2026-08-27.md).
> **Diseño:** [`diseno-mercado-2-0-cockpit-2026-08-27.md`](./diseno-mercado-2-0-cockpit-2026-08-27.md) (slice 1 en Operativa).
> **Partida:** tag `v1.21-beta` → `dad8f51c`.

---

## 0. Qué cierra este freeze

V1.21 resolvió _cómo sobrevive una decisión desde Estudio hasta una posición_.
V1.22 congela _cómo el usuario lo entiende_, sin tocar todavía el cockpit.

| Pieza                                    | Estado                                                       |
| ---------------------------------------- | ------------------------------------------------------------ |
| Contrato UX (5 puertas, pesos distintos) | CONGELADO (ADR-040 §8 · ADR-041 §1.1 enmienda)               |
| H1 Daily Ops universo = Estudio ∩ filtro | CÓDIGO                                                       |
| H2 T1/T2 tocado ≠ gestionado             | CÓDIGO (proyección; no entidad nueva)                        |
| Diseño Mercado 2.0                       | SLICE 1 — Operativa cockpit                                  |
| UI Hoy / Mercado / Asesor / Cartera      | Hoy KPI Cobertura · Asesor sin Proponer F3 · Cartera intacta |

## 1. Ley UX (cinco puertas, peso desigual)

Nav L1 intacta: **Hoy · Mercado · Cartera · Asesor · Laboratorio**.

| Zona            | Pregunta                                         | No es                     |
| --------------- | ------------------------------------------------ | ------------------------- |
| **Mercado**     | ¿Qué está pasando en este valor y cómo lo opero? | Un dump de Hoy            |
| **Cartera**     | ¿Qué tengo y cómo salgo?                         | Otro terminal de análisis |
| **Hoy**         | ¿Qué requiere mi atención ahora?                 | Un segundo Mercado        |
| **Asesor**      | ¿Por qué / qué significa?                        | Una Mesa operativa        |
| **Laboratorio** | ¿Qué estrategias funcionan?                      | Trading                   |

Estudio **no** es puerta L1: es la lista canónica dentro de Mercado.

Tríada **Descubrir → Supervisar → Operar** se mantiene. **Operar vive en Mercado.** Hoy es el inbox del mismo flujo.

## 2. Principios (contrato V1.22)

1. Mercado es el workspace operativo principal.
2. Estudio es el único universo supervisado por Daily Ops. `DAILY_OPS_UNIVERSE = Estudio`; un filtro nunca amplía.
3. Un instrumento seleccionado es el centro de contexto.
4. Una operación tiene una única continuidad visual.
5. `OperationalPlanView` es la proyección visual común (aún no recableada a Mercado Operativa).
6. `currentStop` es el único stop vigente post-fill.
7. T1/T2 distinguen **alcanzado** (precio) de **gestionado** (sello / reduce).
8. Trailing sigue siendo propuesta hasta autoridad operacional real.
9. Hoy no analiza de nuevo el mercado: resume lo que requiere atención + KPI de cobertura.
10. Asesor explica; no ejecuta.
11. Cartera gestiona posiciones existentes.
12. Laboratorio investiga estrategias.
13. ⚙ solo configuración.
14. AdminRail solo administración.
15. El backend puede ser sofisticado; la UI debe parecer sencilla.

Lenguaje de producto (no BUY gigante):

`VIGILAR → PREPARADA → DISPARADA → PROPUESTA → CONFIRMADA → POSICIÓN`

## 3. Hoy — jobs (propuesta Cobertura absorbida)

Tres jobs, nunca colapsados en una tabla:

1. **Actuar** — posiciones, stops, Confirm, atención.
2. **Priorizar** — TOP oportunidades (ranking ≠ BUY).
3. **Cobertura** — ¿cuántos de Estudio tienen estudio fresco? KPI `frescos / N`; no listar ~180 en Resumen.

| Contador       | Significado                  |
| -------------- | ---------------------------- |
| Estudio        | Membresía lista supervisable |
| Decision Study | Artefacto propose / análisis |
| WATCH board    | TradePlan en cola SEMI       |

Journal = solo artefactos propose. Batch propose = epic **posterior** (flag off, cap, cero execute). Nombre de vista futura = **Cobertura**. Sin `?view=cobertura` ni nueva puerta L1 en este freeze.

## 4. H1 / H2 (servidor + proyección)

- **H1:** `GetDailyOpsReport` resuelve membresía `estudio` y aplica `Estudio ∩ instrument_ids`. Scan Daily Ops ignora `opportunityUniverseListId` / env distinto de `estudio`.
- **H2:** `target1Touched` / `target1Managed` (sello `target1AchievedAt`). T2: touched por precio; `target2Managed = false` (no inventar sello). `target1Reached` queda como derivado (compat). Copy de la tarjeta existente: pendiente / alcanzado / gestionado. Trailing copy = propuesta.

## 5. Freeze heredado

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY · trail thin ≠ autoridad · LLM no ejecuta · LAB ≠ TRADING · OpportunityScore aparcado · DEX-1…5 · BETA.

## 6. Next (después de este freeze)

1. ~~Diseño Mercado 2.0~~ · ~~cockpit Operativa slice 1~~ · ~~Hoy slim (KPI Cobertura)~~ · ~~Asesor explica~~.
2. Vista `?view=cobertura` (grid) + batch propose = epic posterior.
3. Opcional: demorar Pulso/Lab bajo cockpit Mercado; niveles en gráfico.

No mezclar con OpportunityScore / VaR / thaw / AUTO.
