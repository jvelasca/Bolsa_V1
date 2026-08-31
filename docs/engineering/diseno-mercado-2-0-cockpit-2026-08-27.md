# Diseño — Mercado 2.0 (cockpit)

> **AsOf:** 2026-08-31 · **Estado:** **SLICE 2 en código (V1.23)** — overlays del plan en gráfico · `InstrumentOperationalContext` · Listas Estudio-first · Operaciones filtradas · Pulso/Lab bajo «¿Por qué?».  
> **Contrato V1.42 (sin código):** panel derecho = **DECISIÓN** — [ADR-042](../adr/042-operating-excellence.md) · [spec](./spec-v142-operating-excellence-2026-08-31.md) §B. El chrome actual puede seguir diciendo «Operativa» hasta F5.
> **Padre:** [`traspaso-relevo-v1-23-ux-consolidation-2026-08-27.md`](./traspaso-relevo-v1-23-ux-consolidation-2026-08-27.md) · [ADR-040](../adr/040-user-information-architecture.md) §9 · [ADR-041](../adr/041-operational-coherence.md).
> **Estudio pendiente (drag / AUTO UX):** [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) — niveles en gráfico **read-only** hasta acuerdo §8.
> **Regla:** No nuevas puertas L1. Shell dock intacto; cambia el contenido contextual.

---

## 0. Principio

No diseñar pantallas. Diseñar **CONTEXTO → ESTADO → ACCIÓN**.

El centro semántico no es «estoy en Mercado». Es «estoy analizando NVIDIA».

Layout **actual** de `/trading` se conserva (no más paneles):

```
┌─────────────────────────────────────────────────────────────┐
│ NAV · cuenta · mercado · datos · ayuda · configuración      │
├──────────────┬──────────────────────────────┬───────────────┤
│ LISTAS       │           GRÁFICO            │   DECISIÓN    │
│ ¿Qué miro?   │     ¿Qué está pasando?       │  ¿Qué hago?   │
├──────────────┴──────────────────────────────┴───────────────┤
│                    OPERACIONES / RESUMEN                     │
└─────────────────────────────────────────────────────────────┘
```

La mejora es **qué información** aparece en cada zona según el instrumento seleccionado, no nuevas puertas.

## 1. Izquierda — ¿Qué quiero mirar?

Listas (orden de producto):

- **Estudio** — universo supervisado (Daily Ops). Destacar membresía, no es «una lista más».
- **Cartera** — posiciones abiertas.
- **Watchlist** / catálogos (S&P, IBEX, …) — descubrir.

Seleccionar un valor fija el contexto de gráfico + Operativa + operaciones. Abrir gráfico **no** añade a Estudio (ADR-024).

Fuera de Estudio con score interesante → **Descubierto**: Ver / Añadir a Estudio. Nunca BUY.

## 2. Centro — ¿Qué está pasando?

Gráfico del instrumento. Niveles del plan cuando existan: entrada, stop vigente, T1, T2, trailing **sugerido** (advisory, no autoridad).

Fuente de niveles = `OperationalPlanView` (misma proyección que Hoy / Journal). No un segundo stop.

## 3. Derecha — ¿Qué hago? (DECISIÓN)

Nombre de producto **DECISIÓN** ([ADR-042](../adr/042-operating-excellence.md)): ¿cuál es la decisión operativa sobre este activo? No Operativa, ni Asesor, ni Trading. El código V1.23 puede seguir usando el identificador `Operativa` hasta F5.

Sustituir Pulso/dictamen/Lab como idioma principal por **una tarjeta contextual** (`OperationalPlanView` / truths V1.37–V1.38) + bloque «¿Por qué?» colapsado. **Una CTA primaria.**

No botón BUY gigante. Stance interno puede ser BUY; el lenguaje de producto es:

```
VIGILAR → PREPARADA → DISPARADA → PROPUESTA → CONFIRMADA → POSICIÓN
```

### 3.1 Estados y CTAs

| Estado         | Cuándo                                       | Panel (mínimo)                                                                                | CTA primario        | CTA secundario        |
| -------------- | -------------------------------------------- | --------------------------------------------------------------------------------------------- | ------------------- | --------------------- |
| **VIGILAR**    | En Estudio, sin oportunidad / disparador     | Opinión VIGILAR · condición no cumple · entrada/stop/T1 vacíos                                | Seguir              | Ver análisis          |
| **PREPARADA**  | Oportunidad / plan ARMED, trigger no cruzado | Entrada propuesta · stop · riesgo % · T1 · T2 · R/R                                           | Preparar operación  | ¿Por qué?             |
| **DISPARADA**  | Trigger cruzado, aún no propuesta de firma   | Mismos niveles · copy «disparo confirmado»                                                    | Revisar y confirmar | ¿Por qué?             |
| **PROPUESTA**  | Hay intent SEMI pendiente                    | Plan congelado · gate/mandato/fit                                                             | Revisar y confirmar | Descartar (si aplica) |
| **CONFIRMADA** | Firma hecha, fill pendiente                  | Plan · estado de orden                                                                        | Ver operaciones     | —                     |
| **POSICIÓN**   | Fill · PositionState OPEN/PARTIAL/PROTECTED  | Entrada · actual · P&L · R · stop vigente · T1/T2 (tocado vs gestionado) · trailing propuesta | Mantener            | Reducir / Salir       |

Confirm **sigue siendo la firma**. Preparar / Revisar navegan o abren el drawer de Confirm; no ejecutan.

**V1.42 (contrato):** una sola CTA primaria. En **POSICIÓN**, Reducir/Salir son secundarias **solo si** la primaria no es ya Reducir o Salir (spec §A.7–A.8: `full_exit` urgente → Salir). Copy de T1 = «Mantener», no `T1_REACHED`.

Ranking ≠ BUY. Opportunity ≠ Permission.

### 3.2 T1 / T2 (H2)

Copy en la tarjeta (ya en proyección):

- `○ pendiente` — precio no cruzó
- `● alcanzado` — precio cruzó; **no** implica reduce
- `✓ gestionado` — `target1AchievedAt` (T2: no hay sello; no fingir gestionado)

### 3.3 Trailing

Advisory. Pico / stop **sugerido** / distancia / estado **PROPUESTA**. Nunca sustituir `currentStop`.

### 3.4 ¿Por qué? (colapsado)

Al abrir, lenguaje de usuario (no Decision Spine):

- Régimen / estrategia / momentum / volumen / portfolio fit / riesgo / mandato
- Advertencias (earnings, datos stale)
- Trazabilidad: Universo Estudio · Análisis as-of · Fuente on-demand \| eod_batch · Dictamen · Gate · Mandato · Fit

IA puede resumir **debajo** del dictamen determinista. IA no es autoridad.

## 4. Abajo — Operaciones

Resumen de órdenes/fills del valor (o de la cuenta si no hay valor). No duplicar Hoy.

## 5. Proyecciones hermanas (no recablear ahora)

**Hoy** — inbox. Tres jobs: Actuar / Priorizar / Cobertura KPI (`frescos / N` en Resumen). No listar ~180. Journal = propose. Vista `?view=cobertura` = epic posterior.

**Cartera** — qué tengo y cómo salgo. Misma `OperationalPlanView` en modo POSICIÓN.

**Asesor** — qué significa. No Mesa. Diario R1 usa Estudio ∩ filtro (H1).

**Laboratorio** — ¿funciona la estrategia?

## 6. Lo que no entra en la primera implementación de UI

- Nuevas puertas L1 ni barras Hoy en Trading
- Entidad OperationalPlan
- OpportunityScore / VaR / AUTO / thaw
- Batch propose
- Promover trail a `currentStop`
- Grid 180 en Resumen/Journal
- **Drag de niveles / edición gráfica** — ver [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) (ronda auditorías abierta)

## 7. Criterio de hecho (cuando se implemente)

1. Seleccionar NVIDIA en Estudio deja gráfico + **DECISIÓN** + plan alineados sin cambiar de página.
2. El mismo plan se ve igual (números) en Mercado, Hoy, Journal, posición.
3. T1 tocado no se lee como «ya reducido».
4. Confirm es el único camino a ejecutar.
5. Fuera de Estudio no hay BUY diario.
