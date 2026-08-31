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
- Use-case Daily Ops: `DAILY_OPS_UNIVERSE = Estudio`. `instrument_ids` / settings / env son **filtro** (`Estudio ∩ ids`); nunca amplían el universo (V1.22 H1).
- Tríada de producto: **Descubrir** (Mercado) → **Supervisar** (Estudio) → **Operar**.
- **Enmienda V1.22:** Operar **vive en Mercado** (cockpit del instrumento). **Hoy es el inbox** del mismo flujo (atención + KPI de cobertura), no un segundo terminal. Estudio no es puerta L1.

### 1.2 Una OPERACIÓN visual

- Proyección `OperationalPlanView` (no entidad nueva) alimentada por TradePlan/study o PositionState.
- Mismo bloque en Hoy, ficha Journal, drawer de oportunidad y ruta de posición. Destino de producto: Mercado · panel **DECISIÓN** ([ADR-042](./042-operating-excellence.md); **F5 CÓDIGO**).
- `TradePlan.entry` sigue siendo un precio único (no inventar rangos).

### 1.3 Stop vigente único

- Autoridad post-fill: `PositionState.currentStop`.
- Plan inicial / propuesta / pending limit = trazas, no rivales.
- T1 idempotente vía `target1AchievedAt` (ExitPlan no re-emite `TARGET_1`).
- **V1.22 H2:** la proyección distingue T1/T2 **tocado** (precio) de **gestionado** (`target1AchievedAt` / reduce). Tocar el nivel ≠ reducción ejecutada. T2 no inventa sello.
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

### 1.6 Enmienda V1.42 — panel DECISIÓN (**CÓDIGO** F5)

**Fecha:** 2026-08-31 · **Norma:** [ADR-042](./042-operating-excellence.md) · [spec V1.42](../engineering/spec-v142-operating-excellence-2026-08-31.md) §B · [relevo F5](../engineering/traspaso-relevo-v1-42-f5-mercado-decision-2026-08-31.md).

- El panel derecho de Mercado se llama **DECISIÓN**: ¿cuál es la decisión operativa sobre este activo?
- No se llama Operativa, Asesor ni Trading. No absorbe Hoy, Journal ni Decision Spine.
- Hoy permanece command center (cuatro cubos: requiere acción / oportunidades / vigilar / sin acción). Mercado permanece terminal.
- Una CTA primaria por activo. `full_exit` urgente no queda oculta por discrepancia de protección.
- Proyecciones de lectura `ExecutionState` / `PositionOperatingTruth` / `TradeStory`: no motores, no tablas. `OperationalTruth` se compone, no se sustituye.
- Geometría `LISTAS | GRÁFICO | DECISIÓN` congelada. F6 Hoy cubos **CÓDIGO**; F7–F8 **CÓDIGO**.

---

## 2. Freeze (heredado)

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY · LLM no ejecuta · LAB ≠ TRADING · OpportunityScore aparcado.

---

## 3. Consecuencias

- Tests: `DAILY-OPS-UNIVERSE-001/002`, OP-03…08 · H1 intersección Estudio · H2 touched vs managed.
- Enmienda ADR-040 §2 / §7 / **§8 (V1.22)**.
- Docs: `CURRENT_SYSTEM.md`, `domain-language.md`, relevo V1.21, relevo [V1.22 freeze](../engineering/traspaso-relevo-v1-22-mercado-cockpit-freeze-2026-08-27.md).
- Enmienda §1.6 (V1.42 contrato): panel **DECISIÓN** · [ADR-042](./042-operating-excellence.md).
