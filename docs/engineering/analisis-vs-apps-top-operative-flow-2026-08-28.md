# Bolsa V1 vs apps TOP — Operative Flow (2026-08-28)

> **AsOf:** 2026-08-28 · **Estado:** **MARCO** — no es implementación de código.
> **Padre:** [`traspaso-relevo-v1-24-honesty-2026-08-28.md`](./traspaso-relevo-v1-24-honesty-2026-08-28.md) · [ADR-040](../adr/040-user-information-architecture.md) · [diseño Mercado 2.0](./diseno-mercado-2-0-cockpit-2026-08-27.md) · [ADR-041](../adr/041-operational-coherence.md).
> **Contrato Confirm V1.25:** [`contrato-confirm-v125-ticket-2026-08-28.md`](./contrato-confirm-v125-ticket-2026-08-28.md).
> **Estudio diseño (auditorías, abierto):** [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) · arranque [`arranque-auditor-estudio-operativa-auto-grafico-2026-08-28.md`](./arranque-auditor-estudio-operativa-auto-grafico-2026-08-28.md).
> **Tag vivo:** `v1.25-beta` → `d3c2fd6b`. **BETA / no producción.**

---

## 0. Veredicto

No hay que rediseñar la arquitectura de usuario. Las cinco puertas (Hoy · Mercado · Cartera · Asesor · Laboratorio) y el cockpit `LISTAS | GRÁFICO | OPERATIVA` ya son la mesa correcta.

La oportunidad no es «parecer TradingView» ni «tener el ticket de IBKR». Es ser **la única app que explica por qué, dimensiona con riesgo real, y nunca convierte ranking en BUY**.

**Operative Flow** no es una pantalla nueva. Es el idioma operativo sobre el cockpit que ya existe:

```
Calidad → Encaja → Preparada → Trigger → Riesgo → Confirm → Protegida → T1/T2 → Salir
```

**Freeze intacto:** Confirm = firma · `PAPER_D_EXECUTE` off · AUTO off · Ranking ≠ BUY · nav L1 congelada · shell Mercado intacto · trail ≠ autoridad · LLM no ejecuta · BETA.

V1.25 **sí toca UI**, pero no es un rediseño de producto: es el **ticket de Confirm** (única autoridad de sizing). Drag de gráfico, móvil, palette, colapsar Hoy → **fuera** de V1.25.

---

## 1. Qué hay realmente en código (V1.24) — no el mockup

| Idea de auditoría                        | Estado V1.24                                                               | Archivo / evidencia                                                            |
| ---------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Mercado 3 columnas                       | Existe, redimensionable; Operativa `hidden md:flex`                        | `apps/web/src/components/layout/trading-layout.tsx`                            |
| Plan único en superficies                | Contrato + tests; proyección, no motor durable de posición                 | `operational-plan-view.tsx` · `same-operational-plan-across-surfaces.test.ts`  |
| Niveles en gráfico                       | Pintados desde el mismo plan; **no arrastrables** (`pointer-events-none`)  | `operational-plan-chart-levels.ts` · `chart-operational-plan-levels-layer.tsx` |
| Trailing ≠ stop vigente                  | Rojo sólido vs ámbar punteado advisory                                     | mismos niveles + `isTrailingStopApplied`                                       |
| Confirm simple + avanzado                | **No.** Panel ~1120 líneas; assessments siempre visibles; `riskPct={null}` | `supervised-f3-panel.tsx`                                                      |
| What-if cartera                          | Existe en **Hoy/Mesa**, **no** en Confirm                                  | `mesa-what-if-panel.tsx` · `buildPortfolioScenario`                            |
| Sizing único                             | TradePlan dimensiona si TRIGGERED; qty editable; sizer `% caja` paralelo   | `trade_plan.py` · `suggestQuantityFromCash`                                    |
| ¿Por qué?                                | Acordeón fino: dictamen / gate / plan / fuente                             | `operativa-cockpit-card.tsx`                                                   |
| Hoy como drawer en Mercado               | **No.** Hoy = puerta L1 `/mesa`                                            | ADR-040 · `daily-nav.ts`                                                       |
| Móvil nativo / push / Cmd+K / tema claro | No existen                                                                 | deuda V1.28 + huecos reales                                                    |

**Consecuencia:** el mockup «Mercado hace el 90%» ya es el diseño aprobado ([Mercado 2.0](./diseno-mercado-2-0-cockpit-2026-08-27.md)). Lo que falta no es otro shell: es que Confirm, sizing y posición cierren el ciclo con la misma honestidad que V1.24 dio a las palabras.

---

## 2. Matriz competitiva — qué ganan las TOP

Ninguna app de referencia gana en todo. Bolsa V1 no elige a cuál parecerse: elige **eje de victoria** y roba selectivamente.

| App                   | Gana en                                            | Pierde en                                              | Qué robamos                                                            | Qué **no** copiamos                                           |
| --------------------- | -------------------------------------------------- | ------------------------------------------------------ | ---------------------------------------------------------------------- | ------------------------------------------------------------- |
| **TradingView**       | Gráfico, overlays, belleza, comunidad              | Ejecución secundaria                                   | Gráfico como mesa; niveles visibles; (más tarde) editar desde la línea | Indicadores infinitos; ranking → BUY; comunidad como producto |
| **IBKR / TWS**        | Ejecución, brackets, routing, riesgo institucional | Complejidad cognitiva; UI «ingenieros para ingenieros» | Plan vinculado entrada+stop+T1; no mentir en qty/riesgo                | Order Type / TIF / OCA / venue / routing en ticket default    |
| **thinkorswim**       | What-if / Analyze; charting; curva suave           | Mercados globales limitados                            | Analyze _antes_ de firmar; escenarios comprensibles                    | Analyze de opciones como producto                             |
| **eToro / Robinhood** | Simplicidad, mobile-first, onboarding              | Profundidad analítica; fricción de riesgo              | «Qué hago ahora» en una frase                                          | BUY de un toque; gamificación; cero fricción                  |
| **Power E\*TRADE**    | Workspaces, layouts, alertas                       | No es nuestro eje                                      | Layouts nombrados (V1.28)                                              | Personalización infinita antes de sizing                      |
| **Bloomberg**         | Autoridad, teclado, datos                          | Precio, curva de aprendizaje, estética utilitaria      | Command palette / hotkeys (V1.28)                                      | Densidad institucional como default                           |

### España 2026

El mercado local polariza _potencia_ (IBKR) vs _simplicidad_ (eToro). Bolsa V1 ocupa el hueco vacío: **potencia de tesis + simplicidad de «qué hago ahora»**.

---

## 3. Dónde ya ganamos (no empezar de cero)

1. **IA copiloto, no autopiloto** — Confirm = única firma; LLM no ejecuta; kill switch de apertura. Ninguna TOP lo comunica tan explícitamente («Nunca se envían solas»).
2. **Una proyección de plan** — Mercado / Hoy / Journal / gráfico leen `OperationalPlanView`. Contrato testeado.
3. **Honestidad semántica V1.24** — BLOCKED/EXPIRED ≠ Preparada; Calidad ≠ BUY; Barrido ≠ Datos; Estudio `unavailable` ≠ empty 0; `formatPrice` sin € inventado.
4. **Fricción deliberada** — el drawer de Confirm es ventaja de producto, no defecto a esconder al estilo Robinhood.
5. **Estadística institucional** (DSR / CPCV / walk-forward) — ventaja de fondo; falta _exponerla_ en «¿Por qué?», no reconstruirla.
6. **Gráfico ya profundo** — plantillas, indicadores, crosshair. No es el hueco.

**Frase de diseño (criterio de decisión UI):**

> ¿Esto ayuda a entender, con la mínima fricción, **por qué** el sistema sugiere esto y **qué pasa si digo que no**?

Si la respuesta es «se parece más a Bloomberg», la decisión es incorrecta.

---

## 4. Dónde estamos cortos — priorizado

### P0 — contradicción de sizing (= V1.25)

Hoy pueden coexistir: TradePlan con `riskPct` **y** ticket con cantidad/precio editados **sin** reescribir el plan. En `supervised-f3-panel.tsx`, `F3TradePlanRiskFirstBlock` se llama con `riskPct={null}` y `target1={null}`. `suggestQuantityFromCash` prefills sin plan TRIGGERED. What-if de cartera no está en la firma.

Esto es el sitio donde IBKR/TOS no se dejan mentir, y donde nosotros todavía sí.

**Ticket default V1.25** (detalle normativo: [contrato Confirm](./contrato-confirm-v125-ticket-2026-08-28.md)):

- Entrada · Stop · Cantidad · Riesgo € · Riesgo % · R
- Exposición · cash · fit
- Antes → Después (`buildPortfolioScenario` — misma función que Mesa)
- Override obligatorio si se toca cantidad/entrada/stop

Avanzado colapsado: assessments, trailing, conflictos.

### P1 — continuidad de posición (V1.26)

`sameOperationalPlanAcrossSurfaces` garantiza _proyección_, no _ciclo de vida_. Una posición debe responder: por qué entré, con qué plan, stop inicial vs vigente, T1 tocado → orden → fill → gestionado, quién autorizó.

### P1 — gráfico operativo (después de sizing único)

Drag de stop/T1 con what-if en vivo. Hover que explica ATR/soporte/R. Acentuar stop vigente vs trail propuesto (ya empezado). **No hay drag hasta V1.25 cerrado** — si no, el gráfico inventa un segundo stop.

### P2 — móvil mínimo de Hoy

Sin Capacitor; Operativa oculta bajo `md`. **No** portar Mercado. Vista estrecha: atención + posiciones + Confirmar (inbox ADR-040). Slice V1.26/V1.27, no V1.25.

### P2 — alertas fuera de pestaña

Toasts in-app existen; no Web Notifications ni push. Alertas inteligentes (trigger válido / plan invalidado) > alertas de precio.

### P3 — UX 10/10 (V1.28)

Command palette · hotkeys · layouts SIMPLE/TRADER/ANALISTA · flash tick · densidad · tema claro (hoy dark-only) · KPI Protección Cartera.

---

## 5. Operative Flow — contrato UX de dos capas

### 5.1 Flujo (backend técnico → lenguaje humano)

| Paso técnico                   | Lenguaje UI (Nivel 1)            |
| ------------------------------ | -------------------------------- |
| Estudio / watchlist            | Descubrir                        |
| Calidad N/100                  | Calificar                        |
| Encaja / Vigilable / Bloqueada | Encaje                           |
| Preparada (allowlist fase)     | Preparar                         |
| Trigger cruzado                | Esperar → Disparada              |
| TradePlan + risk signature     | Plan + riesgo                    |
| Confirm firma                  | Confirmar                        |
| PositionState + stop vigente   | Protegida / Mantener             |
| T1/T2 / trail / ExitPermission | Reducir / Proteger / Salir       |
| Journal                        | Aprender                         |
| 0 triggers + Estudio ok        | **No operar** (éxito de mandato) |

### 5.2 Dos capas

| Capa                      | Qué ve el usuario                                                                | Qué no ve por defecto                                  |
| ------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------ |
| **Nivel 1 — humano**      | Vigilar · Preparar · Comprar · Mantener · Proteger · Reducir · Salir · No operar | DecisionPackage, ExitPlan, ExitPermission, OrderIntent |
| **Nivel 2 — profesional** | Tras «Más información» / «¿Por qué?» / «Ajustes avanzados»                       | —                                                      |

**Regla:** nunca mostrar cinco objetos internos cuando hay una sola acción humana.

### 5.3 Qué congelamos (auditorías discrepan en Hoy)

| Propuesta                                                            | Decisión                                                       |
| -------------------------------------------------------------------- | -------------------------------------------------------------- |
| Nav = Mercado / Cartera / Journal / Lab / Settings (sin Hoy L1)      | **Rechazada.** Rompe ADR-040 y freeze L1.                      |
| Hoy como drawer _en lugar de_ puerta                                 | **Rechazada.** Hoy responde «¿qué debo hacer hoy?».            |
| Strip compacto «Hoy» _dentro_ de Mercado (enlace, sin borrar puerta) | **Aparcada** → V1.27.                                          |
| Mercado hace el 80–90% de la operativa diaria                        | **Sí, como peso operacional** (ADR-040 §8), no como única app. |

---

## 6. Roadmap (sin mezclar epics)

| Epic      | Objetivo                            | Dentro                                                                                                         | Fuera                                                                                                                                                 |
| --------- | ----------------------------------- | -------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **V1.25** | Operational safety                  | Sizing único · €/%/R en Confirm · what-if en ticket · override · assessments colapsados · tests de contrato    | Nav · paneles · drag gráfico · móvil · AUTO · thaw                                                                                                    |
| **V1.26** | Position management                 | Snapshot decisión+plan al fill · stop revisiones · T1 tocado→fill→gestionado · ExitPermission único            | Rediseño Mercado · palette                                                                                                                            |
| **V1.27** | Mercado más operativo (mismo shell) | Drag niveles → recálculo V1.25 · blotter instrumento · strip Hoy enlace · móvil mínimo Hoy · Web Notifications | Nuevas puertas L1 · **implementar solo tras** [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) §8 |
| **V1.28** | UX 10/10                            | Palette · hotkeys · layouts · densidad · tema · KPI Protección                                                 | Motores nuevos                                                                                                                                        |
| **V1.29** | Copiloto explicativo                | «¿Por qué?» como producto (tesis, mandato, umbral); nunca «Compra X»                                           | Autopiloto                                                                                                                                            |

---

## 7. Anexo — puntero al contrato Confirm V1.25

Normativa completa del ticket (campos default vs avanzado, recálculo, what-if, override, tests):

→ [`contrato-confirm-v125-ticket-2026-08-28.md`](./contrato-confirm-v125-ticket-2026-08-28.md)

Ese documento es el **input directo** del epic de sizing. No implementar en este marco.

---

## 9. Estudio abierto — AUTO + gráfico (auditorías)

Antes de V1.27 (drag) y de ampliar AUTO en producto, el owner abrió una **ronda de diseño** para las auditorías externas:

→ [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md)

**Arranque (copiar en chat auditor):** [`arranque-auditor-estudio-operativa-auto-grafico-2026-08-28.md`](./arranque-auditor-estudio-operativa-auto-grafico-2026-08-28.md)

**Regla:** sin filas rellenas en §8 del estudio → no PR de drag ni AUTO ampliado. V1.26b (toast/fase) puede avanzar en paralelo.

---

## 8. Criterio de hecho de este marco

1. Cursor / auditor no proponen otra puerta L1 ni colapsar Hoy.
2. V1.25 se lee como operational safety + ticket Confirm, no como «UI 10/10».
3. Drag de gráfico / móvil / palette quedan explícitamente en V1.26–V1.28.
4. El eje de victoria queda escrito: contexto · continuidad · simplicidad de acción — no copiar superficie de TOP.
