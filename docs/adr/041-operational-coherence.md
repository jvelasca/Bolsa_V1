# ADR-041 — Continuidad operacional y coherencia UX (V1.21)

**Estado:** Accepted  
**Fecha:** 2026-08-27  
**Contexto:** V1.20 cerró la arquitectura de usuario (ADR-040). Quedaba deuda de semántica: Mesa Opportunity usaba `ibex35`, el menú ⚙ mezclaba admin y preferencias, y la UI fragmentaba stop/T1/T2 entre paneles.

**Depende de:** [ADR-040](./040-user-information-architecture.md) · [ADR-024](./024-estudio-supervision-universe.md) · [ADR-032](./032-operational-core-tradeplan-positionstate-execution.md) · [ADR-033](./033-operational-authority-position-persistence.md)

---

## 1. Decisiones

### 1.1 Estudio = universo Daily Ops

- Opportunity ranking, scan diario y funnel de Hoy usan lista API `estudio`.
- Instrumentos fuera de Estudio pueden aparecer como **Descubierto**; nunca como BUY diario.
- Tríada de producto: **Descubrir** (Mercado) → **Supervisar** (Estudio) → **Operar** (Hoy).

### 1.2 Una OPERACIÓN visual

- Proyección `OperationalPlanView` (no entidad nueva) alimentada por TradePlan/study o PositionState.
- Mismo bloque en Hoy, ficha Journal, drawer de oportunidad y ruta de posición.
- `TradePlan.entry` sigue siendo un precio único (no inventar rangos).

### 1.3 Stop vigente único

- Autoridad post-fill: `PositionState.currentStop`.
- Plan inicial / propuesta / pending limit = trazas, no rivales.
- T1 idempotente vía `target1AchievedAt` (ExitPlan no re-emite `TARGET_1`).
- Stop solo avanza (`applyCurrentStop` / never-worsen) salvo override auditado.
- Ejecución de reduce/salida = SEMI (Confirm). El motor propone; el humano firma.

### 1.4 AdminRail ≠ Configuración ≠ Operar

| Capa        | Qué                                                |
| ----------- | -------------------------------------------------- |
| L1 producto | Hoy · Mercado · Cartera · Asesor · Laboratorio     |
| AdminRail   | Overview · Cuentas · Fiscal · Consola avanzada     |
| ⚙           | Preferencias / perfil / notificaciones / BD / sync |

Cuenta activa = contexto en header (selector compacto de demos diarias).

### 1.5 Higiene de cuentas

- Conservar modelo multi-cuenta.
- Distinguir seed (`default-account-seed`), demo de usuario y Lab paper.
- Selector diario excluye Lab paper.
- No borrar seed en migración; limpieza = cerrar + purge cerradas.
- Acción segura «Cerrar extras de desarrollo»: simulated activas ≠ seed, `positionsCount === 0`; Paper sin bulk.

---

## 2. Freeze (heredado)

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY · LLM no ejecuta · LAB ≠ TRADING · OpportunityScore aparcado.

---

## 3. Consecuencias

- Tests: `DAILY-OPS-UNIVERSE-001/002`, OP-03…08.
- Enmienda ADR-040 §2 / §7.
- Docs: `CURRENT_SYSTEM.md`, `domain-language.md`, relevo V1.21.
