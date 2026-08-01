# Lista AUTO — operativa (2026-07-29)

> Embudo por watchlist: tablero, frescura **v1.2**, keep-alive, Pausa/Stop y anti-hang.  
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
| Cap | 40 | 40 |

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
| **Omitido** | Correcto: ese valor ya tiene Finalistas frescos → no se re-analiza. |
| **Forzar reanálisis** | Ignora frescura en el resto de la campaña. |
| **↻** | Aborta campaña + limpia pausa persistida. |

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

**Objetivo:** tras reinicio app/servidor, si la entrada no cambió, **omitir** el embudo (no recalcular IBEX entero).

**Huella** (`buildFinalistsInputFingerprint`):

- `instrumentId`, TF, periodo, fechas custom, capital, comisión, slippage
- **`meta.lastBarDate`** del instrumento (invalida cuando hay barra nueva)
- lote de genéricas (± Mis estrategias si pref ON)
- perfil (`coach-profile-v1|pid:…`) + flag includeFinalists
- motor `finalists-fresh-v1`

**Contexto estable (anti-carrera):** no se decide skip hasta `instruments` + **perfil cuenta** listos (± strategies si Mine ON). Si no, `pid:none` ≠ stamp y se reanaliza todo.

**Periodo/costes** persisten en `bolsa-backtest-run-context-v1` (misma huella tras F5).

**Dónde se guarda**

1. Memoria de sesión (Map) tras cada settle
2. `coachFacts.freshness` en el TOP (si hay slots)
3. **`localStorage`** `bolsa-finalists-freshness-v1` — **siempre** tras settle (también `skip_lab`)
4. Snapshot de pausa/continue (opcional)

**Skip:** prefs ON + !force + (sesión **o** huella local **o** stamp DB **o** adoptar TOP `active` sin stamp). Local/DB **no** exigen `active`.

**Error leyendo TOP:** no fuerza Universo; huella local → omitir; si no → `skip_lab`.

**Prefs:** «Omitir si Finalistas frescos» (default ON). **Reevaluar resto** = `forceRescan`.

**Primera pasada** analiza; **2º Play / post-reinicio** omite si `lastBarDate` y contexto igual.

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

**Cola Monitor (v1):** botón **Encolar revisiones** → `core-r-review-queue-store` (`bolsa-core-r-review-queue-v1`) con filas `coreRNeedsAction`. Deep-link primario + **Hecho**. No cron.

**OOS (v1.1):** `coreROosDegradation` (PBO / credibilidad / retorno / edge) desde stash Lab al juicio post-settle.

**No:** scheduler auto · auto-paper D · overwrite `active`.

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
| CORE-R cola Monitor | `stores/core-r-review-queue-store.ts` · `strategy-monitor-panel.tsx` |
| Orquestación | `backtests-page.tsx` |
| Prefs | `backtest-assistant-prefs.ts` · rail «Omitir si Finalistas frescos» |
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
| CORE-R reevaluación continua + IA | v0+v1 cola Monitor **hecho** · scheduler/OOS/LLM pendiente |
| CORE-P deep-dive perfil | **Hecho** (familias Lab + aviso mismatch) · E2E pendiente |
| Mapa IA Config/Ayuda | **Hecho** (Ayuda → Plataforma IA) |
| Auto-paper D | Congelado |
| Cobertura IBEX sin TOP | Ops: lista `IBEX sin TOP` (`4225247e9c004bd396c17a521`) → Play ciclo |
| Frescura post-reinicio v1.1 | **Hecho** 2026-07-30 |
| Keep-alive + barra Trading | **Hecho** 2026-07-30 |

## 10. Guía rápida usuario (Ayuda)

1. Backtesting → Universo **Lista** → elige IBEX (o IBEX sin TOP).
2. Pref Asistente: **Play ciclo completo** ON · **Omitir si Finalistas frescos** ON.
3. **Play** (no «Probar lista»).
4. Puedes ir a **Trading**: mira el chip de progreso en la barra inferior.
5. Tras reiniciar app/API: otro Play → casi todos **Omitido** si no hay barra nueva.
6. Para forzar: tablero → **Reevaluar resto** (o ↻ y Play con force).

Detalle de cierre de sesión: [`session-handoff-2026-07-30.md`](./session-handoff-2026-07-30.md).
