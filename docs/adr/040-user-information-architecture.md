# ADR-040: Arquitectura de información de usuario (V1.20)

**Estado:** Accepted  
**Fecha:** 2026-08-27  
**Contexto:** V1.19 separó Opportunity Discovery del Decision Board y absorbió Libro/Spine en Mesa vía `?focus=`. La UX sigue exponiendo la arquitectura interna (Decision Spine, Consola ops, Decision Journal, Libro, tira Hoy dentro de Trading).

**Depende de:** [ADR-037](./037-mesa-hoy-operational-ux.md) · [ADR-031](./031-operational-model-tesis-plan-permiso.md) · [ADR-019](./019-dual-universes-lab-vs-trading.md)

---

## 1. Decisión

La arquitectura **interna** (OpportunityEngine, DecisionPackage, DecisionSpine, TradePlan, OperationalConsole, DecisionJournal, …) **no** es la arquitectura **de usuario**.

El usuario piensa en cinco conceptos de primer nivel:

| Puerta          | Pregunta                    | Destino principal                                      |
| --------------- | --------------------------- | ------------------------------------------------------ |
| **Hoy**         | ¿Qué debo hacer hoy?        | `/mesa` (label producto «Hoy»)                         |
| **Mercado**     | ¿Qué está pasando / operar? | Terminal `/trading` (+ Señales, Instrumentos, Alertas) |
| **Cartera**     | ¿Qué tengo?                 | Posiciones / Órdenes / Historial / Riesgo              |
| **Asesor**      | ¿Qué pienso / estudio?      | `/research`                                            |
| **Laboratorio** | ¿Qué pruebo?                | `/backtests`                                           |

Nombres internos **no** aparecen en la navegación diaria: Decision Spine, Decision Board, Consola ops, Decision Journal, Libro, Mesa · Hoy (como label), Trading como sexta puerta, Señales/Confirmar como L1 textual.

## 2. Mapa módulo → puerta

| Módulo interno                                                                                      | Puerta de usuario                                                                    |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| MesaHoyPage / mesa-hoy-model                                                                        | Hoy (vistas Resumen / Posiciones / Oportunidades / Decisiones / Journal / Confirmar) |
| DecisionSpineDetailPanel / decision-board                                                           | Hoy → Decisiones                                                                     |
| DecisionJournalPage                                                                                 | Hoy → Journal                                                                        |
| OperationalConsolePage                                                                              | AdminRail → Consola avanzada; Hoy → estado operativo → Detalles                      |
| MesaLibroPanel / OperationsPanel                                                                    | Cartera → Posiciones / Órdenes                                                       |
| HistoryPage                                                                                         | Cartera → Historial                                                                  |
| TradingLayout / ChartWorkspace                                                                      | Mercado (terminal)                                                                   |
| ScreenersPage                                                                                       | Mercado → Señales                                                                    |
| InstrumentsPage                                                                                     | Mercado → Instrumentos                                                               |
| AlertsPage                                                                                          | 🔔 / Mercado → Alertas                                                               |
| ConfirmPage                                                                                         | Hoy → Confirmar (+ ruta `/confirm` intacta)                                          |
| ResearchPage                                                                                        | Asesor                                                                               |
| BacktestsPage                                                                                       | Laboratorio                                                                          |
| Overview / Accounts / Fiscal / Consola avanzada                                                     | **AdminRail** (barra admin colapsable; ≠ L1 diario; ≠ ⚙)                             |
| Preferencias / Interfaz / Datos / Notificaciones / Trading / Riesgo / IA / Integraciones / Avanzado | ⚙ Configuración (`PlatformConfigDialog`)                                             |

## 3. Contrato UX (DoD)

| ID    | Pregunta del usuario                    | Respuesta de producto                             |
| ----- | --------------------------------------- | ------------------------------------------------- |
| UX-01 | ¿Qué tengo que hacer hoy?               | **Hoy**                                           |
| UX-02 | ¿Qué acciones son mejores para comprar? | **Hoy → Oportunidades**                           |
| UX-03 | ¿Quiero estudiar una acción?            | **Mercado** o **Asesor**                          |
| UX-04 | ¿Quiero modificar una orden?            | **Cartera → Órdenes** (o contexto de oportunidad) |
| UX-05 | ¿Algo ha fallado en la operativa?       | **Hoy → estado operativo → Detalles**             |

Si hace falta explicar Decision Spine / Consola ops / Journal / Libro para responder, la IA UX no está cerrada.

## 4. Trading = terminal

- `HoyCommandStrip` y `MesaOperationalBar` **no** se montan en el workspace de Trading.
- Una sola línea mínima de salud operativa (sin candidatos, sin cola F3, sin «Hoy»).
- `TradingStatusBar` inferior (cuenta / P&L / alarmas) se conserva.
- Candidatos y atención viven solo en **Hoy**.

## 5. Freeze V1.20

- Sin OpportunityScore, sin nueva cola, sin nuevo motor, sin nuevo panel operativo.
- Confirm = única firma. `PAPER_D_EXECUTE` default off. LAB ≠ TRADING.
- Ranking ≠ BUY. Opportunity ≠ Permission. Códigos y docs técnicas conservan nombres internos.

## 6. Consecuencias

- Nav L1: Hoy · Mercado · Cartera · Asesor · Laboratorio (+ 🔔 ? ⚙).
- Label producto de `/mesa` = **Hoy**; «Mesa» queda interno.
- Rutas HTTP históricas se mantienen con redirect (`/decision-board`, `/operations`, …).
- Enmienda ADR-037 §5: strip Hoy sale de Trading; nav diaria deja de ser Mesa→Trading→Señales→Confirmar→Libro.

## 7. Enmienda V1.21 — AdminRail vs Configuración

**Fecha:** 2026-08-27

- Overview · Cuentas · Fiscal · Consola avanzada **salen** del menú ⚙.
- Pasan a **AdminRail** (columna izquierda colapsable bajo el logo Bolsa). No es navegación de producto diaria.
- ⚙ abre solo preferencias / configuración de plataforma.
- Cuenta activa visible en el header como **contexto** (selector compacto), no como página de administración.
- Ver [ADR-041](./041-operational-coherence.md).
