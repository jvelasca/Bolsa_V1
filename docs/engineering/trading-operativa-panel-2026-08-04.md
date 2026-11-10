# Panel Operativa Trading — layout, IO y Estudio (2026-08-04)

> **Padre:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md) → Product / Ops  
> **Ayuda:** [HELP.md](../HELP.md) · menú in-app «Trading y gráficos»  
> **ADR Estudio:** [024-estudio-supervision-universe.md](../adr/024-estudio-supervision-universe.md)  
> **Freeze:** Belief→Coach Fase 2/5c · `CORE_R_CRON` · `COST_MODEL_V2` · Camino D AUTO **execute** · Strategy Studio / F5  
> **Update 2026-08-04b:** Estudio = membresía explícita (no ≡ pestañas); selección masiva; gate SEMI/AUTO.  
> **Update 2026-08-04c:** AUTO prep A1–A5 (pill disabled · kill switch · armado local) — [pack](./audit-pack-pre-auto-a0-a5-2026-08-04.md) · [ADR-023](../adr/023-camino-d-thaw.md) Proposed.  
> **Update 2026-08-06:** ADR-024 · sin auto-add gráfico · Supervisión en banner · modos Manual/SEMI/AUTO → barra de estado / Cuentas · UI procesos [estudio-process-status-ui-2026-08-06.md](./estudio-process-status-ui-2026-08-06.md).  
> **Update 2026-11-10:** DECISIÓN maximizable (área completa) + responsive por container queries (`operativa-panel`) + vista completa en ventanas <768 px — ver § Maximizar y responsive.

## Qué

Rediseño del rail Coach → panel **Operativa** en la mesa TRADING:

1. **Columna a altura completa** (hasta la barra de estado). Operaciones solo bajo watchlist + gráfico.
2. Secciones colapsables: **Recomendación** · **Info** (estrategia activa / mandato + resultados).  
   ~~Cuenta / modos~~ → ya no viven aquí (ver § Modo de cuenta).
3. **Índice Operativo (IO) v1** en Recomendación (gauges TA / FA / IO + ranking «El n de N en Estudio» · copy básico/avanzado).
4. Altura de sección: hasta **900px** (`MAX_OPERATIVA_SECTION_HEIGHT_PX`); asa inferior más usable.
5. Lista **Estudio** = universo supervisable API (`estudio`). Supervisión ON/cadencias = **banner** de la lista (no este panel).

## Layout

```text
┌ Watchlist │ Gráfico ─┐┌ Operativa (full height) ┐
├ Operaciones ─────────┤│ Recomendación / Info    │
└──────────────────────┘└─────────────────────────┘
TradingStatusBar: Activa · OPERATIVA: Semi · métricas · Colas/Alarmas
```

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
- **Container queries, no viewport**: `.operativa-panel-scroll` (`container-name: operativa-panel`) mide el ancho real del panel. `@container operativa-panel (min-width: 44rem)` → 2 columnas (acción | ¿Por qué?); `(min-width: 68rem)` → 3 columnas (acción | ¿Por qué? | info/mandato). Nada se oculta: solo se reparte.
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
- Banner «Fuera de Estudio» + Añadir cuando SEMI/AUTO lo exigen.
- CTAs **Proponer F3 → Confirm** y **Cola Confirm (n)** en Recomendación (Camino C).
- Chart IA propose reutiliza los mismos gates SEMI/Estudio/sizing (`propose-instrument-supervised.ts`).
- Info → **Learning / Outcomes** in-panel (DecisionSession summary + cerrar outcome).
- Camino D AUTO execute **sigue freeze**.
