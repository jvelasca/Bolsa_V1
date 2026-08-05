# Lista AUTO — operativa (2026-07-29)

> Embudo por watchlist: tablero, frescura **v1.3** (histéresis lastBar), keep-alive, Pausa/Stop y anti-hang.  
> Complementa [`research-lifecycle.md`](./research-lifecycle.md) § Lista AUTO ·  
> pausa [`product-pause-audit-2026-07-30.md`](./product-pause-audit-2026-07-30.md) ·  
> cierre [`session-handoff-2026-07-30.md`](./session-handoff-2026-07-30.md) ·  
> [`assistant-play-funnel-design-2026-07-29.md`](./assistant-play-funnel-design-2026-07-29.md).

## 1. Qué es / qué no es

| | Lista AUTO | Fase C «Probar lista» |
|--|------------|------------------------|
| Entrada | Universo **Lista** + Play (ciclo ON) | Botón secundario en `<details>` |
| Unidad | Embudo completo × cada valor | 1 estrategia × N valores → ranking |
| Estrategia | **No se elige** (genéricas ∪ Finalistas del ticker) | Obligatoria (1 preset o Mis estrategias) |
| Cap | Tanda 40 (confirma si N>40; pref «No preguntar tandas»; tope duro 500) · filtro opcional «solo sin Finalistas» | 40 |
| Browse | Universo Lista muestra resumen TOP/★/AUTO; clic → Valor | Ranking clic → Valor + run |

## 2. Flujo

```text
Play (lista + ciclo ON)
  → tablero con todos los valores
  → por ticker: ¿fresco? → Omitido | si no → Universo→Coach→Lab→Coach²→Finalistas
  → settle → siguiente | pausa | fin
```

### Controles (rail Asistente + tablero)

| Control | Comportamiento |
|---------|----------------|
| **Pausa** | Termina el valor en curso; **no** arranca el siguiente. Persistente (ver §4). |
| **Reanudar** | Continúa en el índice guardado. |
| **Stop** | Corta ya. El **siguiente Play** de la misma lista **continúa** en el valor interrumpido (no vuelve al #1). ↻ Asistente = empezar de cero. |
| **Omitido** | Solo si hay **Finalistas reales** (slots) y la huella coincide (exacta o histéresis lastBar). Sin TOP → analizar. |
| **Forzar reanálisis** | Ignora frescura en el resto de la campaña. |
| **↻** | Aborta campaña + limpia pausa persistida. |
| **Eliminar Finalistas** | Panel TOP: borra InstrumentStrategyTop + huella local (Biblioteca ≠ Finalistas). |

### Segundo plano (usar la app mientras corre)

- Mientras la campaña está activa, `BacktestsPage` queda en **keep-alive** (`PlatformShell`) al ir a Trading u otros hubs.
- Barra de estado Trading: chip `Lista AUTO n/N · SYM · fase…` (clic → tablero).
- Badge en menú Backtesting de la top bar.
- Store: `list-auto-activity-store.ts`.

### Anti-hang (avance garantizado)

Si un valor se queda «trabajando» sin cerrar el ciclo, la campaña **sigue** al siguiente:

| Caso | Comportamiento |
|------|----------------|
| Universo 0 OK / error batería | `skip_lab` + siguiente |
| TOP sin jobs Lab encolables | `skip_lab` + siguiente |
| Zona Lab fallida / sin job | zona terminal → cierra board |
| Lab > 8 min sin terminar | watchdog → `skip_lab` |
| Doble settle mismo índice | lock (no salta tickers) |

## 3. Frescura (no repetir análisis)

**Objetivo:** tras reinicio app/servidor, si hay Finalistas y la entrada no cambió, **omitir** el embudo.

**Huella** (`buildFinalistsInputFingerprint`):

- `instrumentId`, TF, periodo, fechas custom, capital, comisión, slippage
- **`meta.lastBarDate`** del instrumento — **histéresis v1.3:** en `1d` hasta **5 días** de calendario desde el stamp no invalidan (1 barra ≠ re-embudo). Stamp **no** se desliza. «Reevaluar resto» fuerza.
- lote de genéricas (± Mis estrategias si pref ON)
- perfil (`coach-profile-v1|pid:…`) + flag includeFinalists
- motor `finalists-fresh-v1`

**Contexto estable (anti-carrera):** no se decide skip hasta `instruments` + **perfil cuenta** listos (± strategies si Mine ON). Si no, `pid:none` ≠ stamp y se reanaliza todo.

**Periodo/costes** persisten en `bolsa-backtest-run-context-v1` (misma huella tras F5).

**Dónde se guarda**

1. Memoria de sesión (Map) tras cada settle
2. `coachFacts.freshness` en el TOP (si hay slots)
3. **`localStorage`** `bolsa-finalists-freshness-v1` — tras settle
4. Snapshot de pausa/continue (opcional)

**Skip (v1.3):** prefs ON + !force + **`hasSlots`** + (sesión **o** huella local **o** stamp DB **o** adoptar TOP `active` sin stamp).  
Huella: match **exacto** o **`bar_hysteresis`** (solo `lastBarDate` dentro de slack; resto igual).  
Sin slots → **siempre analizar** (`no_finalists_slots`). Tras Eliminar Finalistas se limpia huella local.

**Error leyendo TOP:** no fuerza Universo ni Omitido → `skip_lab`.

**Prefs:** «Omitir si Finalistas frescos» (default ON). **Reevaluar resto** = `forceRescan`.

**Primera pasada** analiza; **2º Play / post-reinicio** omite si hay Finalistas y contexto igual (o solo barra dentro de slack).

## 4. Persistencia de pausa

| | |
|--|--|
| Clave | `localStorage` · `bolsa-list-auto-paused-v1` |
| Módulo | `backtest-list-auto-persist.ts` |
| Cuándo se guarda | Campaña `paused` y **ninguna** fila `running` (entre tickers) |
| Qué incluye | `listId`, cola `instrumentIds`, `index` (siguiente), tablero, `forceRescan`, memoria frescura |
| Al reiniciar | Restaura modo Lista, lista, tablero, rail con **Reanudar**; **no** auto-arranca |
| Cuándo se borra | Reanudar · Stop · fin de campaña · ↻ · nuevo Play de lista |

Si el usuario recarga **mientras** un ticker está `running` tras pulsar Pausa, esa fila aún no está persistida como pausa estable: al volver no hay snapshot (o el anterior). Tras terminar el valor y quedar en pausa entre tickers, sí persiste.

## 5. Tablero

Columnas: # · Valor · Estado · Δ · **Reeval (CORE-R)** · Últ. búsqueda · Acción · Detalle.

Estados: En cola · En curso · Finalistas · Sin cambio · **Omitido** · Skip Lab · Stop.

Pestaña de resultados **Lista AUTO** + vista compacta en el wizard.

## 5.1 CORE-R v0 (reevaluación manual)

Tras cada settle, `judgeCoreR` escribe un juicio en la fila (no pisa Finalistas):

| Verdict | Cuándo (heurística) |
|---------|---------------------|
| Fresco OK | Omitido (`skip_fresh`) |
| Mantener | TOP estable / actualizado lab_validated sin alarmas |
| Revisar Lab | sin lab_validated · skip_finalists · dual-audit débil |
| Valorar cambio | no bate B&H / reciente malo / discrepancia |
| Perfil ≠ TOP | stamp `profileId` ≠ perfil activo |
| Débil · skip | `skip_lab` |

Acciones = deep-links (Lab / Finalistas / Checklist / F3). Botón **Reevaluar resto** = forceRescan. Informe en `localStorage` `bolsa-core-r-report-v1` (Monitor lo lee).

**Cola Monitor (v1):** botón **Encolar revisiones** → `core-r-review-queue-store` (`bolsa-core-r-review-queue-v1`) con filas `coreRNeedsAction`. Deep-link primario + **Hecho**.

**OOS (v1.1):** `coreROosDegradation` (PBO / credibilidad / retorno / edge) desde stash Lab al juicio post-settle.

**PnL + scheduler lite (v1.2):** Monitor muestra retorno DEMO/paper; −5% → Revisar Lab · −10% → Valorar cambio; extras a la cola. Auto-sync opcional.

**Narrar cola (v1.3):** `POST /api/ai/core-r/review-evidence` · heurística siempre · LLM via Proxy First. Monitor → **Narrar cola**.

**Cron shell (v1.4):** `CoreRSchedulerHost` en PlatformShell · `scope=shell` + `listId` · ticks con app abierta.

**Chip barra (v1.5):** «CORE-R N» en hilos de la barra Trading si hay cola abierta → Ayuda · Monitor (`openHelpBacktesting`). Hub: `/backtests?tab=run&focus=monitor`.

**Toast encolar (v1.6–v1.7):** tras tick con `added > 0`, toast + acción **Abrir Monitor**.

**Hecho todos (v1.8):** `dismissOpen(listId)` en Monitor — cierra abiertas de la lista actual (no borra; `clearDone` limpia done).

**Multi-dispositivo (v1.9–v1.12):** cola/informe/scheduler en BD (`core_r_account_state`) = SoT; localStorage = cache. Hydrate/push vía `core-r-sync.ts`. Cron servidor opcional (`CORE_R_CRON_ENABLED`).

**Estudio personal + cadencia (v1.13, as-is):** al activar Auto-sync, `listId` prefiere la lista API «Estudio personal» (si existe); cadencia editable (15…1440 min).

> **To-be (ADR-024 · 2026-08-06):** una sola lista producto **Estudio** (API) + interruptor **Supervisión ON**; deprecar «Estudio personal». Ver [estudio-supervision-model-2026-08-06.md](./estudio-supervision-model-2026-08-06.md).

**Adoptar mandato SEMI (v1.13):** en cola, juicio «Valorar cambio» + TOP#1 → CTA **Adoptar** (modo SEMI) · tenure ADR-020 (`actor=core_r`, `propose_accepted`). AUTO execute no auto-adopta.

**No:** auto-paper D · overwrite `active` · auto-adopción de mandato.

**Ops:** `pnpm test:operativa` (web+py+smoke opcional).

## 5.2 LAB reanálisis vs TRADING cambio de mandato

| | Reanálisis (LAB) | Cambio operativo (TRADING) |
|--|------------------|----------------------------|
| Pregunta | ¿Sigue siendo buena la Finalista / hay mejor candidata? | ¿Cerrar el mandato actual y abrir otro? |
| Herramientas | Lista AUTO · Reevaluar resto · cron CORE-R · Play | Mandato ADR-020 · aceptar propuesta en Monitor · cambio manual |
| Quién decide | Embudo / frescura (automático o forzado) | Humano (SEMI Confirm) — **AUTO execute no auto-adopta** |

| Modo TRADING | Reanálisis | Cambio de estrategia |
|--------------|------------|----------------------|
| Manual | A voluntad (Play lista / Monitor) | Usuario cambia mandato |
| SEMI | CORE-R + cola; chip en barra | Usuario confirma propuesta |
| AUTO (execute) | Igual (juicio/cola) | **No** auto-adopta; solo opera el mandato vigente |

CORE-R **propone** (Mantener / Revisar Lab / Valorar cambio). No pisa TOP ni cambia mandato solo ([§5.1](#51-core-r-v0-reevaluación-manual)).

## 6. Código clave

| Pieza | Archivo |
|-------|---------|
| Campaña / Pausa / Stop | `backtest-list-auto.ts` |
| Tablero estado | `backtest-list-auto-board.ts` · `*-panel.tsx` |
| Persistencia pausa | `backtest-list-auto-persist.ts` |
| Frescura (skip) | `backtest-finalists-freshness.ts` |
| Run-context (periodo/costes) | `backtest-run-context.ts` |
| Actividad global / barra Trading | `stores/list-auto-activity-store.ts` · `trading-status-bar.tsx` |
| Keep-alive shell | `platform-shell.tsx` (monta `BacktestsPage` si campaña activa) |
| CORE-R juicio | `core-r-judgment.ts` |
| CORE-R scheduler lite | `core-r-scheduler.ts` · `core-r-scheduler-tick.ts` · `core-r-scheduler-host.tsx` |
| CORE-R chip barra | `core-r-status.ts` · `trading-app-threads.tsx` |
| CORE-R cola Monitor | `stores/core-r-review-queue-store.ts` · `strategy-monitor-panel.tsx` |
| CORE-R Adoptar SEMI | `core-r-adopt-mandate.ts` |
| Estudio personal (nombre) | `@bolsa/shared` `ESTUDIO_PERSONAL_LIST_NAME` · `resolveEstudioPersonalListId` |
| Orquestación | `backtests-page.tsx` |
| Prefs | `backtest-assistant-prefs.ts` · «Omitir si Finalistas frescos» · «No preguntar tandas» |
| Stamp al guardar TOP | `backtest-explore-panel.tsx` |
| Ayuda usuario | `backtesting-tracker.ts` · `HELP_CONTENT_AS_OF` |

## 7. Tests

```bash
pnpm --filter @bolsa/web exec vitest run \
  src/features/backtests/backtest-list-auto.test.ts \
  src/features/backtests/backtest-list-auto-board.test.ts \
  src/features/backtests/backtest-list-auto-persist.test.ts \
  src/features/backtests/backtest-finalists-freshness.test.ts \
  src/features/backtests/backtest-finalists-freshness-restart.test.ts \
  src/features/backtests/backtest-run-context.test.ts \
  src/features/backtests/core-r-judgment.test.ts
```

Incluidos en `pnpm test:coach` (battery).

Smoke live (API en marcha; SKIP si caída):

```bash
python scripts/research/verify_finalists_freshness_smoke.py
python scripts/research/verify_finalists_freshness_smoke.py --list-id ibex35
```

## 8. Deuda operativa IBEX

| Comando | Uso |
|---------|-----|
| `pnpm audit:ibex35` | Auditoría live + MD en `research/observations/` |
| `pnpm audit:ibex35:missing` | Lista símbolos sin TOP / sin runId |
| `pnpm backfill:top-runids -- --symbol AENA --dry-run` | Remedia Checklist sin re-Lab (si hay runs) |
| Lista AUTO Play | Cubre gaps `sin_TOP` (no Fase C) |

`lab_validated`/`active` **sin runId** ya lo rechaza la API (2026-07-29).

## 9. Relación con pendientes

| Track | Estado |
|-------|--------|
| Lista AUTO UX + frescura + pausa persistente | **Hecho** (esta nota) |
| CORE-R reevaluación continua + IA | v0–v1.13 **hecho** (cola · OOS · PnL · narración · cron shell · chip · toast→Monitor · Hecho todos · BD SoT · Estudio personal · Adoptar SEMI) |
| CORE-P deep-dive perfil | **Hecho** (familias + mismatch + soft-bias + E2E `test:coach:smoke`) |
| Mapa IA Config/Ayuda | **Hecho** (Ayuda → Plataforma IA) |
| Auto-paper D | Congelado |
| Cobertura IBEX gaps | Ops: `pnpm audit:ibex35:missing` + Play sobre **IBEX 35** (frescura v1.3). **No** crear lista «IBEX sin TOP» de producto — confunde ([pausa](./product-pause-audit-2026-07-30.md)) |
| Frescura post-reinicio v1.2 | **Hecho** 2026-07-30 · omitir solo con Finalistas reales |
| Histéresis lastBar v1.3 | **Hecho** 2026-08-01 · `1d` slack 5d calendario · stamp no desliza |
| Keep-alive + barra Trading | **Hecho** 2026-07-30 |

## 10. Guía rápida usuario (Ayuda)

1. Backtesting → Universo **Lista** → elige **IBEX 35** (catálogo). Si ves «IBEX… SIN TOP», bórrala: era ops, no producto.
2. Pref Asistente: **Play ciclo completo** ON · **Omitir si Finalistas frescos** ON.
3. **Play** (no «Probar lista»).
4. Puedes ir a **Trading**: mira el chip de progreso en la barra inferior.
5. Tras reiniciar app/API: otro Play → **Omitido** si ese valor **tiene Finalistas** y el contexto es igual (o solo avanzó la barra dentro de ~5 días en diario). «Reevaluar resto» fuerza.
6. Para forzar: tablero → **Reevaluar resto** (o ↻ y Play con force). Para vaciar un valor: panel → **Eliminar Finalistas**.

Detalle de cierre de sesión: [`session-handoff-2026-07-30.md`](./session-handoff-2026-07-30.md).
