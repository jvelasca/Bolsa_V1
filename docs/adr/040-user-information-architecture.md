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

| ID    | Pregunta del usuario                    | Respuesta de producto                                                                      |
| ----- | --------------------------------------- | ------------------------------------------------------------------------------------------ |
| UX-01 | ¿Qué tengo que hacer hoy?               | **Hoy** (inbox: atención + KPI cobertura; no reanaliza el mercado)                         |
| UX-02 | ¿Qué acciones son mejores para comprar? | **Hoy → Oportunidades** (ranking ≠ BUY; universo = Estudio)                                |
| UX-03 | ¿Quiero estudiar / operar un valor?     | **Mercado** (contexto estable: lista → gráfico → plan → acción). Asesor explica el porqué. |
| UX-04 | ¿Quiero modificar una orden?            | **Cartera → Órdenes** (o contexto de oportunidad)                                          |
| UX-05 | ¿Algo ha fallado en la operativa?       | **Hoy → estado operativo → Detalles**                                                      |

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

## 8. Enmienda V1.22 — Mercado opera; Hoy resume

**Fecha:** 2026-08-27

- Las cinco puertas L1 **siguen**; el **peso operacional no es igual**.
- **Mercado** = workspace operativo (cockpit del instrumento seleccionado).
- **Hoy** = command center del día: Actuar / Priorizar / Cobertura (KPI). No dump de membresía Estudio (~180).
- **Asesor** explica; no es una Mesa. **Cartera** gestiona lo ya comprado. **Laboratorio** prueba estrategias.
- Ver [ADR-041](./041-operational-coherence.md) §1.1 enmienda · [relevo V1.22](../engineering/traspaso-relevo-v1-22-mercado-cockpit-freeze-2026-08-27.md).

## 9. Enmienda V1.23 — UX Consolidation

**Fecha:** 2026-08-27

- **Hoy = inbox de 4 niveles:** Requiere acción · Oportunidades · Vigilar · Sin acción. Sin pestañas L2 en el chrome.
- **Confirmar** no es vista de Hoy: firma = drawer + `/confirm`.
- Detalles (Decisiones / Journal / Libro / Consola) detrás de **«Ver detalles»**; deep-links `?view=` intactos.
- **Mercado** = cockpit operativo completo: Listas (Estudio primero) | Gráfico (overlays del plan) | Operativa contextual | Operaciones filtradas al valor.
- Panel derecho por fase (`InstrumentOperationalContext`): en estudio **no** se muestran Entrada/Stop/T1/T2.
- Ranking visual: **Prioridad N/100** + **NO ES UNA ORDEN** (nunca BUY).
- Asesor: Análisis / Tesis / Journal / Investigación — sin CTA operativo primario.
- Honestidad Estudio: `estudioStatus` = `ok` | `empty` | `unavailable` (fallo ≠ 0 candidatos).
- Sin motores nuevos · Ranking ≠ BUY · Confirm = firma · trail ≠ autoridad.
- Ver [diseño Mercado 2.0](../engineering/diseno-mercado-2-0-cockpit-2026-08-27.md) · [relevo V1.23](../engineering/traspaso-relevo-v1-23-ux-consolidation-2026-08-27.md).

## 10. Enmienda V1.24+ — Operative Flow (filosofía, no pantalla)

**Fecha:** 2026-08-28

**Contexto:** Auditorías post-V1.24 contrastan Bolsa V1 con TradingView / IBKR / thinkorswim / eToro. Coinciden en el destino (mesa asistida por IA, no terminal genérico) y divergen en si «Hoy» debe dejar de ser puerta L1.

**Decisión:**

1. **Operative Flow** es la filosofía de interfaz sobre el cockpit ya existente — **no** una sexta puerta ni un panel nuevo:

   ```
   Calidad → Encaja → Preparada → Trigger → Riesgo → Confirm → Protegida → T1/T2 → Salir
   ```

   («No operar» es resultado de primera clase cuando Estudio está ok y no hay triggers válidos.)

2. **Cinco puertas L1 intactas.** Rechazado colapsar Hoy dentro de Mercado como única app. Hoy sigue respondiendo UX-01 («¿qué debo hacer hoy?»). Un strip compacto «Hoy» _dentro_ de Mercado (enlace, sin borrar la puerta) queda **aparcado** a V1.27.

3. **Shell Mercado congelado:** `LISTAS | GRÁFICO | OPERATIVA` ([diseño Mercado 2.0](../engineering/diseno-mercado-2-0-cockpit-2026-08-27.md)). El peso operacional sigue siendo Mercado opera / Hoy resume (§8). No nuevas barras ni paneles L1.

4. **Dos capas de UI:** Nivel 1 humano (Vigilar / Preparar / Mantener / Proteger / Reducir / Salir / No operar); Nivel 2 profesional (TradePlan, R, ExitPermission, …) detrás de «Más información» / «¿Por qué?» / «Ajustes avanzados». Nunca exponer cinco objetos internos cuando hay una sola acción.

5. **V1.25 = operational safety en Confirm**, no «UI 10/10»:
   - Sizing único TradePlan → ticket
   - Riesgo € / % / R visibles en default
   - What-if Antes→Después en el ticket (`buildPortfolioScenario`)
   - Override si se edita qty/entrada/stop
   - Assessments colapsados
   - Contrato normativo: [`contrato-confirm-v125-ticket-2026-08-28.md`](../engineering/contrato-confirm-v125-ticket-2026-08-28.md)

6. **No adelantar** en V1.25: drag de niveles en gráfico, móvil nativo, Web Notifications, command palette / hotkeys / layouts, colapsar puertas, AUTO / thaw.

7. **Eje de victoria vs apps TOP:** contexto (por qué + riesgo) · continuidad (tesis → posición → salida) · simplicidad de «qué hago ahora» — no copiar la superficie de TradingView ni la densidad de TWS.

**Marco completo:** [`analisis-vs-apps-top-operative-flow-2026-08-28.md`](../engineering/analisis-vs-apps-top-operative-flow-2026-08-28.md).
