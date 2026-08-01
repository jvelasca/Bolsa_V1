# Handoff embudo AT → paper / monitor (2026-07-29)

> **Actualización 2026-07-30:** retomar en  
> [`session-handoff-2026-07-30.md`](./session-handoff-2026-07-30.md)  
> (frescura v1.1, keep-alive, anti-hang, pendientes mañana).

Documento histórico de cierre 29-jul. Complementa
[`research-lifecycle.md`](./research-lifecycle.md) § Embudo D · Lista AUTO · Narrativa unificada
y Ayuda → Backtesting (`backtesting-tracker.ts`, `paper-paths-copy.ts`).

**Estado de producto:** el embudo de exploración (Play ciclo + Lista AUTO) y las puertas
Finalistas → paper (A) / Supervisado (C) + Monitor MVP (solo lectura) están **listos**.
Auto-paper **D** (ejecución sin clic) sigue **congelado**.

**Documentación:** `HELP_CONTENT_AS_OF` = **2026-07-30** · ops Lista AUTO en
[`list-auto-ops-2026-07-29.md`](./list-auto-ops-2026-07-29.md).

Gate de regresión: `pnpm test:coach` (incluye full-cycle, list-auto, monitor, F3 origin, paper-paths, IBEX35 operativa offline).

Auditoría live IBEX: `pnpm audit:ibex35` → `research/observations/*-ibex35-operativa-audit.md`.

---

## 1. Qué se entregó (mapa mental)

```
Universo (1 valor o Lista)
    │ Play + fullCycleOnPlay (default ON)
    ▼
Coach → Lab TOP-3 → Coach² → Finalistas (lab_validated solo con mejora Lab)
    │
    ├─ Checklist  → Detalle + checklist → Desplegar en paper     [= Camino A]
    ├─ Proponer   → FA+perfil → cola F3 → Confirm humano        [= Camino C]
    └─ Monitor    → Ayuda Backtesting (estado; no ejecuta)      [= pre-D MVP]
```

| Pieza | Rol | Código principal |
|-------|-----|------------------|
| Ciclo 1 valor | Play encadena Universo→…→Finalistas | `backtest-assistant-full-cycle.ts`, prefs `fullCycleOnPlay`, `backtests-page.tsx` |
| Lista AUTO | Mismo ciclo × N tickers (cap 40) | `backtest-list-auto.ts`, Play en modo Lista |
| ≠ Fase C | «Probar lista» = 1 estrategia × N → ranking | `backtest-batch-run.ts` |
| Finalistas → A | CTA Checklist si `runId` | `instrument-strategy-top-panel.tsx`, `openFinalistChecklist` |
| Finalistas → C | CTA Proponer si `lab_validated` | `finalist-propose-supervised.ts`, cola F3 |
| F3 origen | Badge Finalistas/Scan/Gráfico/Manual + scroll Confirm | `supervised-f3-queue-store.ts`, `supervised-f3-panel.tsx` |
| Monitor MVP | Lista watchlist → TOP + paper + último Proponer | `strategy-monitor.ts`, `strategy-monitor-panel.tsx` |

---

## 2. Política (no negociar sin decisión explícita)

1. **Sin mejora Lab** → no pisar Finalistas `active` previos.
2. **Finalistas `active` + `lab_validated`** solo tras Lab con ≥1 Mejor y Coach² guardable.
3. **No unificar** Lab checklist (A) con Radar `paper_auto` (B) en un solo «auto».
4. **Proponer (C)** exige cuenta activa (perfil); humano confirma en Supervisado F3.
5. **Monitor** es solo lectura: no deploy, no execute, no scheduler.
6. **D congelado** hasta ranking TA+FA+perfil + ejecución sin clic (el MVP monitor no descongela D).

---

## 3. Cómo probar mañana (smoke manual)

1. **1 valor:** Universo Valor → Play (ciclo ON) → esperar Lab → Coach² → Finalistas.
2. **Sin mejora Lab:** mensaje de política; TOP active previo intacto.
3. **Checklist:** Finalistas con run → Checklist → Detalle con «Análisis · paper» abierto → Desplegar solo si gates OK. URL debe llevar `openAnalysis=1`.
4. **Proponer:** cuenta activa → Proponer → Ayuda IA hace scroll a Supervisado F3 con origen **Finalistas** → Confirmar Intent (humano).
5. **Lista AUTO:** modo Lista + Play → tablero + **Pausa/Stop en rail** (pausa **persiste** reinicio) + frescura/Omitido · doc [`list-auto-ops-2026-07-29.md`](./list-auto-ops-2026-07-29.md).
6. **Monitor:** hub Probar (desplegable abajo) y Ayuda → Backtesting → elegir lista → filas con TOP; Checklist abre con `openAnalysis=1`.
7. **Regresión:** `pnpm test:coach`.
8. **Futuro crítico (no ahora):** CORE-R reevaluación continua — `ISSUES.md`.

**Smoke automatizado 2026-07-29 AM:** `pnpm test:coach` → 87 OK. UX: Monitor en hub + `openAnalysis` query + vacíos.

### Pendiente inmediato (orden sugerido)

1. **Mapa IA** en Config / Ayuda  
2. **CORE-P** deep-dive (stamp perfil, techos DD Lab, UI rail)  
3. **CORE-R** (tras operativa estable; ya tiene precursor frescura + tablero)  

---

## 4. Archivos clave (índice)

### Motor / prefs
- `apps/web/src/features/backtests/backtest-assistant-full-cycle.ts` (+ `.test.ts`)
- `apps/web/src/features/backtests/backtest-assistant-prefs.ts` — `fullCycleOnPlay`
- `apps/web/src/features/backtests/backtest-list-auto.ts` (+ `.test.ts`) — `LIST_AUTO_MAX_INSTRUMENTS = 40`

### Orquestación UI
- `apps/web/src/features/backtests/backtests-page.tsx` — `fullCycleActive`, `listAuto*`, `settleFullCycle`, `openFinalistChecklist`, `proposeFinalistSupervisedSlot`
- `apps/web/src/features/backtests/backtest-assistant-rail.tsx` — pref Play ciclo
- `apps/web/src/features/backtests/backtest-lab-board.tsx` — `autoHandoff`
- `apps/web/src/features/backtests/backtest-explore-panel.tsx` — `autoSaveFinalists`
- `apps/web/src/features/backtests/instrument-strategy-top-panel.tsx` — Checklist / Proponer / Usar

### Camino C + F3
- `apps/web/src/features/backtests/finalist-propose-supervised.ts`
- `apps/web/src/stores/supervised-f3-queue-store.ts` — `origin`, `openHelpAiPlatform({ panel })`
- `apps/web/src/features/settings/supervised-f3-panel.tsx` — badge + callout Confirm
- `apps/web/src/features/help/app-help-menu.tsx` — `panel: 'supervised-f3'`
- `apps/web/src/features/settings/ai-platform-section.tsx` — scroll al panel

### Monitor
- `apps/web/src/features/backtests/strategy-monitor.ts` (+ `.test.ts`)
- `apps/web/src/features/backtests/strategy-monitor-panel.tsx`
- Montaje: `apps/web/src/features/settings/backtesting-help-section.tsx`

### Copy / Ayuda / docs
- `apps/web/src/features/settings/paper-paths-copy.ts` — A / B / C / Monitor
- `apps/web/src/features/settings/backtesting-tracker.ts`
- `apps/web/src/features/help/help-content-as-of.ts`
- `docs/engineering/research-lifecycle.md`
- `scripts/research/verify_coach_battery.mjs`

---

## 5. Mañana — opciones de continuación (por prioridad)

| Opción | Notas |
|--------|--------|
| **Smoke UI** | Validar flujo real (recomendado antes de más código) |
| **Pulir UX** | Monitor en hub Probar; openAnalysis por query param; vacíos más claros |
| **Descongelar D** | Solo con decisión explícita: ranking TA+FA+perfil + execute loop |
| **Otro dominio** | Fuera del embudo (FA UI, perfiles, trading, charts…) |

**No retomar sin decisión:** Lab UI P3–P9, Discovery/Planner, Belief/Knowledge deep UI, unificar A+B.

---

## 6. Decisiones ya tomadas (recordatorio)

- 2026-07-28: Radar etiquetado; auto D congelado (`PAPER_PATH_PRODUCT_DECISION`).
- 2026-07-28/29: Lista AUTO = bucle del ciclo completo; ≠ Fase C «Probar lista».
- 2026-07-29: Finalistas expone **dos puertas** A y C; Monitor es tercera superficie de **estado**, no on-ramp de ejecución.
