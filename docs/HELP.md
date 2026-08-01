# Ayuda en la app — coordinación con trackers y docs

> **Sync:** `HELP_CONTENT_AS_OF` = **2026-08-01**  
> Ayuda «Datos de mercado» + Watchlist + «Análisis del valor» + **Backtesting** (Play ciclo, Lista AUTO **v1.3**, Finalistas A/C, Monitor + **CORE-R v1.8**, **DÍA D v0.11**, Lab **CORE-B v0.2**) + Trading (MODO DÍA D).  
> Configuración → **BD** (estado PostgreSQL, purga de huérfanos y demos cerradas).  
> **Espacios de trabajo:** chip superior → gestor (nuevo blanco / duplicar / renombrar); arranque = último activo.  
> Handoff: [engineering/session-handoff-2026-08-01.md](./engineering/session-handoff-2026-08-01.md) (cierre racha) · previo [07-31](./engineering/session-handoff-2026-07-31.md) · DÍA D: [engineering/backtesting-dia-d-premises-2026-07-31.md](./engineering/backtesting-dia-d-premises-2026-07-31.md) · Plan prueba: [engineering/operativa-test-plan-2026-07-31.md](./engineering/operativa-test-plan-2026-07-31.md) · Lista AUTO: [engineering/list-auto-ops-2026-07-29.md](./engineering/list-auto-ops-2026-07-29.md).  
> (`apps/web/src/features/help/help-content-as-of.ts`)

La UI **Ayuda (?)** muestra guías y tableros de seguimiento.  
**Configuración (⚙)** solo tiene preferencias editables (incluida pestaña **BD**).

## Nomenclatura de producto

| En la app (español) | Código / URL (interno) |
|---------------------|------------------------|
| Análisis del valor | value-analysis / FA |
| Backtesting | backtests |
| Plataforma IA | ai / supervised F3 |
| Datos de mercado | data capture |
| Espacio de trabajo | workspace |

## Mapa sección → tracker → docs

| Sección Ayuda | Tracker / UI | Docs |
|---------------|--------------|------|
| **Backtesting** | `backtesting-tracker.ts` + Monitor (`strategy-monitor-panel.tsx`) | [research-lifecycle.md](./engineering/research-lifecycle.md), [DÍA D](./engineering/backtesting-dia-d-premises-2026-07-31.md), [operativa test](./engineering/operativa-test-plan-2026-07-31.md), [handoff 2026-08-01](./engineering/session-handoff-2026-08-01.md), [list-auto-ops](./engineering/list-auto-ops-2026-07-29.md), [ADR-009](./adr/009-backtesting-research-platform-h0.md), [ADR-018](./adr/018-fase2-evidence-store-v0.md) |
| Análisis del valor | `value-analysis-tracker.ts` | FA status / FIE |
| Datos de mercado | `data-market-tracker.ts` | data capture |
| Watchlist / listas | `watchlist-lists-tracker.ts` | lists-universes |
| Plataforma IA | `ai-platform-tracker.ts` | AI_PLATFORM_SOLUTION |
| Gráficos | `chart-platform-tracker.ts` | charts |

(El resto de filas del mapa histórico se mantienen en los trackers; este archivo prioriza Backtesting operativo.)

## Backtesting DÍA D (usuario · sync 2026-08-01 · v0.11)

Guía en Ayuda → Backtesting (`BACKTESTING_DIA_D_GUIDE`). Premisas: [backtesting-dia-d-premises-2026-07-31.md](./engineering/backtesting-dia-d-premises-2026-07-31.md). Plan de prueba: [operativa-test-plan-2026-07-31.md](./engineering/operativa-test-plan-2026-07-31.md).

| Paso | Dónde | Qué hacer |
|------|--------|-----------|
| 1 | Backtesting → Probar | Bloque **Backtesting DÍA D** → fecha **pasada** |
| 2 | Mismo hub | **Play** hasta Finalistas (embudo ≤ D) |
| 3 | Resultado → Finalistas | En **#1** → **Simular D→hoy** |
| 4 | Trading | Banner MODO DÍA D + película · modos Manual / Semi / Auto |
| 5 | Semi/Manual | En cada señal → **Aceptar** (fill) / **Rechazar** (no fill; buy KO anula sell) |
| 6 | Opcional | **Pantalla completa** (efímera: no sobrevive a recarga) · **Narrar con IA** · **Guardar Evidence** |
| 7 | Archivo | Trading (preview/JSON/Importar) · también **Ayuda → Backtesting** |
| 8 | Salir | Banner → **Salir DÍA D** → restaura docks / **Operaciones** (sandbox; no toca DEMO live) |

Si Trading «desapareció» (solo película): **Salir pantalla completa** o **Salir DÍA D**, o recarga (full-bleed no se persiste).

Si no ves el CTA: la fecha DÍA D sigue en «hoy», o no hay Finalistas #1 con estrategia guardada.

En **Análisis fundamental** con D en el pasado: la API pide `asOf=D`. Si hay ``statementPack`` (tras **refresh FA** del valor), reconstruye ratios desde estados ≤ D (`pointInTime=reconstructed`). Si no hay pack, **blocked**. El Composite corta TA a barras ≤ D.

Informe lateral: retorno/DD/ops del **gate** (+ referencia Auto) y bloque **Evidence** (band + narrativa; «Narrar con IA» opcional; «Guardar Evidence» → archivo local + Fase 2 `dia_d_session`).

**Reinicia api-python** tras actualizar código para rutas Evidence / asOf / CORE-R.

## CORE-R / Monitor Finalistas (usuario · v1.8)

Guía en Ayuda → Backtesting (`BACKTESTING_CORE_R_GUIDE`). Detalle: [list-auto-ops § CORE-R](./engineering/list-auto-ops-2026-07-29.md).

| Paso | Qué |
|------|-----|
| 1 | Monitor (Probar o Ayuda) → elige lista con TOP |
| 2 | **Encolar revisiones** (informe Lista AUTO + PnL DEMO ≤ −5%/−10%) |
| 3 | Deep-links Lab / Finalistas / Checklist → **Hecho** |
| 4 | Opcional: **Narrar cola** · **Auto-sync app abierta** (cron shell) |
| 5 | Chip **CORE-R N** · toast con **Abrir Monitor** si el cron encola |
| 6 | **Hecho todos** cierra las abiertas de la lista actual |

No pisa TOP · no auto-paper D · cola en este navegador (localStorage).

## Lista AUTO frescura (v1.3)

Tras reinicio, un 2º Play sobre la misma lista debe **Omitir** si periodo/costes/perfil no cambiaron y la última barra no aporta señal nueva (`1d` ≤5 días → `bar_hysteresis`). «Reevaluar resto» fuerza. Detalle: [list-auto-ops](./engineering/list-auto-ops-2026-07-29.md).

## Batería offline (antes de smoke UI)

```bash
pnpm test:operativa          # DÍA D + CORE-R (web + py + smoke API opcional)
pnpm test:operativa:smoke    # API live (reinicia api primero)
pnpm test:coach              # embudo / Lista AUTO / CORE-P (+ smoke API opcional)
pnpm test:coach:smoke        # CORE-P multi-perfil live (API)
pnpm test:coach:api          # ASGI multi-perfil (DB) + smoke live
```

## UX diálogo

El diálogo de Ayuda usa **ancho y alto fijos** (`max-w-4xl` + altura viewport) para que cambiar de sección no redimensione la ventana; el cuerpo hace scroll interno.
