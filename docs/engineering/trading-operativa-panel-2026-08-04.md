# Panel Operativa Trading — layout, IO y Estudio (2026-08-04)

> **Padre:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) → Product / Ops  
> **Ayuda:** [HELP.md](../HELP.md) · menú in-app «Trading y gráficos»  
> **ADR Estudio:** [024-estudio-supervision-universe.md](../adr/024-estudio-supervision-universe.md)  
> **Freeze:** Belief→Coach Fase 2/5c · `CORE_R_CRON` · `COST_MODEL_V2` · Camino D AUTO **execute** · Strategy Studio / F5  
> **Update 2026-08-04b:** Estudio = membresía explícita (no ≡ pestañas); selección masiva; gate SEMI/AUTO.  
> **Update 2026-08-04c:** AUTO prep A1–A5 (pill disabled · kill switch · armado local) — [pack](./audit-pack-pre-auto-a0-a5-2026-08-04.md) · [ADR-023](../adr/023-camino-d-thaw.md) Proposed.  
> **Update 2026-08-06:** ADR-024 · sin auto-add gráfico · Supervisión en banner · modos Manual/SEMI/AUTO → barra de estado / Cuentas · UI procesos [estudio-process-status-ui-2026-08-06.md](./estudio-process-status-ui-2026-08-06.md).  
> **Update 2026-11-10:** DECISIÓN maximizable (área completa) + responsive por container queries (`operativa-panel`) + vista completa en ventanas <768 px — ver § Maximizar y responsive.
> **Update 2026-11-10b (V2.48):** reorganización en **2 bloques fijos** (Análisis diario · Decisión) + **5 plegables** (Seguimiento Lab · Mandato · Evidencia · Aprendizaje · AUTO) y una sola puerta de acción — ver § Bloques de DECISIÓN.

## Qué

Rediseño del rail Coach → panel **Operativa** en la mesa TRADING:

1. **Columna a altura completa** (hasta la barra de estado). Operaciones solo bajo watchlist + gráfico.
2. **Dos bloques fijos** — Análisis diario (parte del valor) y Decisión (contexto → estado → acción) — y **cinco plegables** — Seguimiento Lab, Mandato, Evidencia, Aprendizaje y AUTO.  
   ~~Cuenta / modos~~ → ya no viven aquí (ver § Modo de cuenta).
3. **Índice Operativo (IO) v1** en Evidencia (gauges TA / FA / IO + ranking «El n de N en Estudio» · copy básico/avanzado).
4. Altura de sección: hasta **900px** (`MAX_OPERATIVA_SECTION_HEIGHT_PX`); asa inferior más usable.
5. Lista **Estudio** = universo supervisable API (`estudio`). Supervisión ON/cadencias = **banner** de la lista (no este panel).

## Layout

```text
┌ Watchlist │ Gráfico ─┐┌ Operativa (full height) ┐
├ Operaciones ─────────┤│ Análisis diario·Decisión│
└──────────────────────┘│ + 5 plegables           │
                        └─────────────────────────┘
TradingStatusBar: Activa · OPERATIVA: Semi · métricas · Colas/Alarmas
```

## Bloques de DECISIÓN (V2.48)

Orden de lectura, idéntico en dock y maximizado; la anchura solo cambia el número de columnas.

| # | Bloque | Naturaleza | Contenido |
|---|--------|-----------|-----------|
| 1 | **Análisis diario** | fijo | Tendencia · seguimiento · entrada/salida (parte del valor) |
| 2 | **Decisión** | fijo | Contexto → estado → **acción** (CTA única) · «¿Por qué?» del dictamen |
| 3 | **Seguimiento Lab** | plegable | TOP #1 (rank · fuente · retorno · estabilidad) · «Abrir estudio» · «Verificar DÍA-D» |
| 4 | **Mandato** | plegable | Definición · adopción (solo si existe) · timeline de tenures |
| 5 | **Evidencia** | plegable | Pulso IO/TA/FA · dictamen · chips del paquete (avanzado) |
| 6 | **Aprendizaje** | plegable | Historial Confirm del valor (no es el dictamen del día) |
| 7 | **AUTO** | plegable | Gestión automática: autonomía · armado · qué hará AUTO |

Reglas de copy que sostiene la reorganización:

- **Una puerta por acción.** `Proponer F3`, `Cola Confirm` y `Añadir a Estudio` viven solo en la CTA de Decisión; en el resto de bloques se explica el estado, no se repite el botón.
- **Un dato, un sitio.** La estabilidad del Lab se lee en su bloque; el mandato se define una vez; el resumen de cabecera es el único sitio donde el número se repite como vistazo.
- **Ids de sección por asunto** (`lab` · `mandato` · `evidencia` · `resultados` · `auto`), no por cajón. Un guardado anterior (`recommendation`/`info`/`config`) cae a los valores por defecto sin romper el rehydrate.


- Store: `bolsa-trading-layout-v1` (`operativaOpen`, `operativaWidthPct`, `operativaSections`, …).
- Código: `trading-layout.tsx`, `trading-layout-store.ts`.

## Maximizar y responsive

DECISIÓN es maximizable como Listas u Operaciones (icono en la cabecera del dock y
entrada **Operativa maximizada** en el menú de vista de la barra superior).

```text
dock normal (md+)            maximizado                    ventana <768 px
┌──────────────┬─────────┐   ┌──────────────────────────┐   ┌──────────────────┐
│ Listas/Gráfico│ DECISIÓN│   │ DECISIÓN (área completa) │   │ DECISIÓN         │
│ Operaciones   │ 20–42 % │   │ 2–3 columnas si hay ancho│   │ (vista completa) │
└──────────────┴─────────┘   └──────────────────────────┘   └──────────────────┘
```

| Estado | Store | Comportamiento |
|--------|-------|----------------|
| Dock normal | `operativaMaximized: false` | Ancho arrastrable 20–42 % (260–420 px), una columna; secciones con alto fijo y asa |
| Maximizado | `operativaMaximized: true` | Área completa bajo la barra superior; `data-maximized="true"`; el panel entero desplaza y las secciones crecen con su contenido |
| Ventana estrecha | `operativaMaximized: true` | DECISIÓN sustituye a Listas/Gráfico a área completa (la X vuelve); sin botón Maximizar |

Reglas de implementación:

- **Exclusión mutua** con `listsMaximized` / `chartsMaximized` / `operationsMaximized`; cerrar la zona o `restoreLayout` / `applyNamedLayout` limpia el flag, y el `merge` del persist degrada un guardado inconsistente (`maximizado` + `cerrada`) a dock normal.
- **Móvil**: el dock es `hidden md:flex`, así que la única puerta al panel es **Operativa maximizada** (menú de vista). Sin maximizar, la ventana estrecha conserva Listas/Gráfico; maximizada ocupa el área y la X vuelve.
- **Container queries, no viewport**: `.operativa-panel-scroll` (`container-name: operativa-panel`) mide el ancho real del panel. `@container operativa-panel (min-width: 52rem)` → 2 columnas (decisión | seguimiento+mandato; evidencia/aprendizaje/AUTO a todo el ancho); `(min-width: 78rem)` → 3 columnas (decisión | seguimiento+mandato | evidencia/aprendizaje/AUTO). Nada se oculta: solo se reparte. Los umbrales subieron de 44/68 rem al añadir las tarjetas: a 44 rem la segunda columna quedaba en ~330 px y el detalle no respiraba.
- `TradingOperativaPanel` recibe `maximized`; `TradingOperativaSection` lee `operativaMaximized` del store para usar `height: auto` y ocultar el asa.


## Modo de cuenta (Manual / SEMI / AUTO)

Afecta a **toda la cuenta**, no al valor del gráfico:

| Dónde | Qué |
|-------|-----|
| Barra de estado | Badge `OPERATIVA: Manual|Semi|Auto` |
| Clic badge / nombre cuenta | `/accounts?selected=…&tab=config&focus=operativa` |
| Cuentas → Config | Bloque **Operativa** + `DemoBookModePanel` |

Prefs: `demo-book-prefs.ts` / `use-demo-book-prefs.ts`.

## Estudio — membresía (ADR-024)

| Acción | Efecto |
|--------|--------|
| Abrir / enfocar gráfico | **No** cambia membresía |
| Cerrar pestaña | **No** saca de Estudio |
| «Pasar a Estudio» / check | Añade membresía API |
| «Eliminar de la lista» | Unsubscribe (colas/campaña); no cierra mandato solo |
| Ranking IO | Universo = miembros Estudio |
| Nombre UI | **Estudio** (API id `estudio`) |

### Selección masiva (Valores · Estudio)

- Check cabecera; **Ctrl/Cmd** toggle · **Mayús** rango.
- Barra inferior: **Pasar a Estudio** · **Eliminar de la lista** · **Abrir gráficos** · **Actualizar** · **Redescubrir** · Limpiar.
- **Actualizar** = velas + vigilia + frescura (puede `skip_fresh`).
- **Redescubrir** = embudo completo (confirm costoso).

### Gate SEMI / AUTO

- `demoBookRequiresEstudioMembership(mode)` → true en SEMI y AUTO.
- Propose F3 falla si el instrumento no está en Estudio.
- **MANUAL** no exige Estudio.
- **AUTO UI:** pill disabled; kill switch + armado local en `DemoBookModePanel` (Cuentas).
- Execute AUTO: `PAPER_D_EXECUTE` off — [pack A0–A5](./audit-pack-pre-auto-a0-a5-2026-08-04.md).

## Índice Operativo (IO) v1

| Pieza | Regla |
|-------|--------|
| Base | Composite display 0–100 |
| Distress FA | Suelo IO ≤ 40 |
| Ranking | IO desc entre IDs en Estudio |
| Copy | `El {rank} de {total} en Estudio` |

Helpers: `operativa-index.ts` · UI: `operativa-pulse.tsx` · datos: `useInstrumentsHubScores(studyIds)`.

## Archivos clave

| Área | Path |
|------|------|
| Layout | `apps/web/src/components/layout/trading-layout.tsx` |
| Panel | `trading-operativa-panel.tsx`, `trading-operativa-section.tsx` |
| Bloque AUTO | `operativa-auto-panel.tsx`, `auto-desk-panel.tsx` |
| IO | `operativa-index.ts`, `operativa-pulse.tsx` |
| Prefs / gate | `demo-book-prefs.ts`, `use-demo-book-prefs.ts` |
| Modo UI | `demo-book-mode-panel.tsx` (Cuentas) · `trading-status-bar.tsx` |
| Supervisión | `estudio-supervision-panel.tsx`, `estudio-supervision.ts` |
| Procesos UI | `estudio-process-status.ts`, `list-name-process-subtitle.tsx` |
| Selección / Actualizar | `list-values-panel.tsx`, `list-item-accordion.tsx` |
| Label | `packages/shared/src/default-lists.ts` |

## Fuera de alcance

AUTO execute · Belief→Coach 5c · cambiar fórmula IO más allá de Composite+distress.

## Update 2026-08-04c — mesa SEMI vital

- Dictamen del valor activo con `positionOpen` real (portfolio).
- Banner «Fuera de Estudio» que explica el gate SEMI/AUTO; el alta se firma en la CTA de Decisión (no se duplica en el banner).
- CTA única **Proponer F3 / Cola Confirm / Añadir a Estudio** en la tarjeta de Decisión; `propose-instrument-supervised.ts` aplica los gates SEMI/Estudio/sizing.
- **Aprendizaje** → Learning / Outcomes en su propio bloque (DecisionSession summary + cerrar outcome).
- **AUTO** vive en su bloque propio (`operativa-auto-panel.tsx`), no dentro de la tarjeta de decisión.
- Camino D AUTO execute **sigue freeze**.

> **Nota V2.48:** los antiguos atajos «Proponer F3 → Confirm (avanzado)» y «Cola Confirm (n)» de la sección de recomendación se retiraron para que exista una sola puerta de acción (la CTA de Decisión).
