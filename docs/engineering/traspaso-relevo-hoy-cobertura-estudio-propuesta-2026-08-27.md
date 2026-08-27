# RELEVO — propuesta Hoy Command Center & Cobertura Estudio (post v1.21)

> **AsOf:** 2026-08-27 · **Estado:** **CONSENSUADA / ABSORBIDA en V1.22** — KPI Cobertura en Resumen Hoy (sin `?view=cobertura`).
> **Padre:** [`traspaso-relevo-tag-v1-21-beta-2026-08-27.md`](./traspaso-relevo-tag-v1-21-beta-2026-08-27.md) · freeze [`traspaso-relevo-v1-22-mercado-cockpit-freeze-2026-08-27.md`](./traspaso-relevo-v1-22-mercado-cockpit-freeze-2026-08-27.md) · [ADR-041](../adr/041-operational-coherence.md) · [ADR-040](../adr/040-user-information-architecture.md) · [ADR-024](../adr/024-estudio-supervision-universe.md).
> **Para:** owner + auditoras (histórico de consenso). Vista `?view=cobertura` = epic **posterior**.
> **Patch UX ya en main (no es este epic):** AdminRail icon-first; copy sesión `Estudio N en supervisión` ≠ `WATCH en board`; Journal default lista Estudio + copy “propose ≠ membresía”.

---

## 0. Problema que vimos

Tras V1.21 el usuario espera ver **Estudio (~180)** como universo supervisado en Hoy/Journal, pero la UI mezclaba tres números distintos:

| Contador           | Significado real               | Ejemplo                   |
| ------------------ | ------------------------------ | ------------------------- |
| **Estudio**        | Membresía lista supervisable   | ~180                      |
| **Decision Study** | Artefacto _propose_ / análisis | ~3 si solo hay 3 proposes |
| **WATCH board**    | TradePlan en cola SEMI         | ~3                        |

Copy antiguo «N en vigilancia» = WATCH board → se leía como «tamaño Estudio». Journal listaba studies, no membresía. Embudo ya decía `180 → 3 evaluados` pero el lenguaje no era profesional ni operativo.

**Decisión pedida:** no parchear Hoy metiendo 180 filas en Resumen/Journal. Diseñar como apps pro (Bloomberg / TOS / IBKR / TV Pro): _command center_ + _coverage_ separado.

---

## 1. Tesis de producto

**Hoy = Command Center del día** (decidir / actuar), no dump del universo ni Journal embebido.

Tres jobs distintos (nunca colapsar en una tabla):

1. **Actuar** — posiciones, stops, Confirm, atención.
2. **Priorizar** — TOP oportunidades (ranking ≠ BUY).
3. **Supervisar cobertura** — ¿cuántos de Estudio tienen estudio fresco?

---

## 2. Estructura propuesta (vistas)

| Vista                                 | Job             | Contenido                                                                                       | No contenido           |
| ------------------------------------- | --------------- | ----------------------------------------------------------------------------------------------- | ---------------------- |
| **Hoy · Resumen**                     | Glance + actuar | Estado sesión · riesgo · incidente · KPI Estudio N · embudo · Attention · posiciones · TOP link | Lista 180              |
| **Hoy · Oportunidades**               | Priorizar       | Ranking / buckets / funnel honesto                                                              | Membresía completa     |
| **Hoy · Cobertura Estudio** _(nueva)_ | Supervisar      | Matriz/grid: fresco · stale · sin propose · fuera                                               | Cola Confirm / BUY     |
| **Hoy · Journal**                     | Auditar tesis   | Solo Decision Studies                                                                           | “Todos los de Estudio” |
| **Mercado**                           | Terminal        | Chart + ticket                                                                                  | Cola Hoy               |

### Resumen (layout mental)

```
A. Estado     → Estudio N · embudo · régimen · incidente
B. Atención   → work queue (posiciones / Confirm / protect)
C. Cobertura  → KPI 3/180 fresco + CTA “Ver cobertura” / “Batch propose” (opt-in)
```

---

## 3. Reglas — consenso V1.22 (sí)

1. **Estudio ≠ Journal ≠ WATCH board** — tres contadores, siempre etiquetados. **Sí.**
2. **Hoy Resumen no pagina 180** — solo KPI + drill-down a Cobertura. **Sí.**
3. **Journal no es watchlist** — si se quiere “todos Estudio”, es **Cobertura**. **Sí.**
4. **Batch propose** = job back-office opt-in (scheduler / job), no auto en home; Confirm sigue siendo firma; Ranking ≠ BUY. **Sí — epic posterior**, no este freeze.
5. **Sin nuevas puertas L1** — Cobertura = `?view=` bajo Hoy (ADR-040 intacto). **Sí.** Sin `?view=cobertura` todavía.
6. **Sin OpportunityScore / VaR / thaw / AUTO** en este epic. **Sí.**

---

## 4. Epic candidato (nombre tentativo)

Absorbido por **V1.22 freeze conceptual** ([`traspaso-relevo-v1-22-mercado-cockpit-freeze-2026-08-27.md`](./traspaso-relevo-v1-22-mercado-cockpit-freeze-2026-08-27.md)). Vista `Hoy?view=cobertura` = **epic posterior** (después del cockpit Mercado).

Alcance mínimo (cuando se implemente la vista):

- Vista `Hoy?view=cobertura` (o label producto acordado).
- Modelo read-only: por `instrumentId` de Estudio → estado `fresh | stale | missing | outside` + asOf study.
- KPI en Resumen: `frescos / N` + link.
- CTA opcional a job batch propose (flag off por defecto; cap; cero execute).
- Tests: tres contadores no se confunden; Resumen no lista 180.

Fuera: motor OpportunityScore, correlación, thaw, AUTO, barras en Trading.

---

## 5. Preguntas para auditoras — resueltas

1. ¿Tríada **Actuar / Priorizar / Cobertura**? **Sí** (jobs de Hoy, no tres apps).
2. ¿Journal solo propose? **Sí.**
3. ¿Batch propose en el mismo epic? **No** — posterior.
4. ¿Nombre? **Cobertura** (no Universo / Supervisión).
5. ¿Veto grid 180? **Veto en Resumen y Journal.** En Cobertura futura, como mucho matriz virtualizada de estados.

---

## 6. Freeze heredado

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY · trail thin ≠ autoridad · DEX-1…5 · BETA.

---

## 7. Arranque chat auditor (copiar)

Lee: este relevo + pack v121 + ADR-041 + ADR-040 + ADR-024.  
Valida semántica de contadores y la propuesta V1.22 Cobertura. **No implementar.** Devolver: sí/no a reglas §3 + respuestas §5 + riesgos.
