# Lab issues (deuda técnica de explotación)

Registro **ligero** de issues del laboratorio. No son tickets de producto ni ADR.
No abren Fase 2 ni entidades nuevas.

## Open

### CORE-R continuous-strategy-reevaluation · **CRÍTICO**

| Campo | Valor |
|-------|--------|
| Estado | Open · **v0–v1.8** (cola + OOS + PnL + narración + cron + chip + toast + **Hecho todos**) · cron multi-dispositivo pendiente |
| Severidad | **Crítica (producto a medio plazo)** |
| Origen | Decisión usuario 2026-07-29 (tras pulir Lista AUTO) |
| Código | `core-r-judgment.ts` · `core-r-scheduler.ts` · `core-r-scheduler-host.tsx` · `core_r_review_evidence.py` · Monitor · tablero Lista AUTO |
| Doc | `docs/engineering/list-auto-ops-2026-07-29.md` § CORE-R |

**Idea:** de forma **periódica** (manual y automática), volver a evaluar si la estrategia / Finalistas **en curso** siguen siendo los adecuados o conviene **mejorar / optimizar / cambiar**.

**Hecho (v0):** juicio heurístico post-settle (`keep` / `fresh_ok` / `review_lab` / `consider_replace` / `profile_mismatch` / `skipped_weak`) · columna Reeval + acciones Lab/Finalistas/F3/Checklist · «Reevaluar resto» (forceRescan) · informe `bolsa-core-r-report-v1` · badge Monitor. **No** pisa `active`. **No** auto-paper D.

**Hecho (v1 · 2026-07-30):** Monitor → **Encolar revisiones** desde informe · cola persistida `bolsa-core-r-review-queue-v1` · deep-link + Hecho. Humano; sin cron servidor.

**Hecho (v1.1 OOS):** `coreROosDegradation` (PBO / credibilidad / retorno OOS / edge band) alimenta juicio desde stash Lab · no pisa `active`.

**Hecho (v1.2 · 2026-07-31):** PnL live DEMO/paper en Monitor (`getAccountSummary`) · match `simulated` preferido · degradación −5% `review_lab` / −10% `consider_replace` → cola · **scheduler lite** (`bolsa-core-r-scheduler-v1`) solo mientras el panel está abierto.

**Hecho (v1.3 · 2026-07-31):** **Narrar cola** — Evidence heurística + Proxy First (`POST /api/ai/core-r/review-evidence`). LLM solo narra; sin FA/Coach/overwrite TOP.

**Hecho (v1.4 · 2026-07-31):** **Cron shell** — `CoreRSchedulerHost` en PlatformShell; ticks con app abierta (`scope=shell` + `listId`). Cola sigue en localStorage (no multi-dispositivo).

**Hecho (v1.5 · 2026-07-31):** **Chip barra** — si hay cola abierta, «CORE-R N» en hilos de la barra Trading → Ayuda · Monitor (`openHelpBacktesting`). Deep-link hub: `/backtests?tab=run&focus=monitor`.

**Hecho (v1.6 · 2026-07-31):** **Toast al encolar** — `CoreRSchedulerHost` escucha tick; si `added > 0` → toast («revisa Monitor / chip»). Sin ruido en ticks vacíos.

**Hecho (v1.7 · 2026-07-31):** Toast con acción **Abrir Monitor** (`openHelpBacktesting`).

**Hecho (v1.8 · 2026-08-01):** **Hecho todos** en Monitor (lista actual) · `dismissOpen` · regresión chip (selector zustand estable).

**Pendiente:** cron multi-dispositivo (requiere report/cola en servidor).

**Ops:** `pnpm test:operativa` · `pnpm test:operativa:smoke` (API opcional).

---

### CORE-P profile-coach-lab-binding

| Campo | Valor |
|-------|--------|
| Estado | Closed · **v1 + deep-dive + E2E live smoke** · BETA1 vigilancia |
| Severidad | Alta (coherencia inversor ↔ estrategias) |
| Origen | Decisión producto 2026-07-29 (Asistente 1-Play) |
| Doc | `docs/engineering/profile-coach-lab-binding.md` · funnel design §3 |
| Código | `coach-profile-policy.ts` · explore stamp · Lab DD · rail · invalidate ciclo |

**Hecho (v0):** `allowLabIfWeak` desde `riskTolerance`; gate Universo→Lab; `skip_lab` → Lista AUTO next.

**Hecho (v1):** stamp `profileId`/`policyVersion` en Finalistas; techo DD Lab (`maxDrawdownSoftPct`); fingerprint frescura con perfil; rail «Perfil: …»; abort ciclo al cambiar cuenta/perfil; tests multi-perfil.

**Hecho (deep-dive):** `preferredLabFamiliesForHorizon` + hint/orden · `resolveDefaultLabFamily` · soft-bias espacio por riesgo · aviso `activeTopProfileMismatch`.

**Hecho (E2E live · 2026-08-01):** `verify_core_p_api_smoke.py` · `pnpm test:coach:smoke` (fase 2 de `test:coach`, SKIP si API down). ASGI: `apps/api-python/tests/integration/test_core_p_multi_profile.py` (con DB). Offline: `coach-profile-battery-scenario.test.ts`.

**Pendiente (BETA1):** vigilar simulaciones multi-perfil en uso real — issues cortas si falla; no reabrir congelados.

---

### CORE-A coach-soft

| Campo | Valor |
|-------|--------|
| Estado | Open · **v0 en código** · ciclo Belief pendiente |
| Severidad | Media (calidad / honestidad del Coach) |
| Origen | Funnel design §6 · tras Play + CORE-P |
| Código | `coach.llmNarrate` · `coach-llm-invariant.test.ts` · `readPriorCoachAuditHint` |

**Hecho (v0):** toggle Narración LLM en rail; OFF = solo ★ local + auditor heurístico; tests «LLM no corona TOP»; hint UI de pasada previa (`dualAudit`) sin modular score.

**Pendiente:** aprendizaje outcomes / Belief → Coach (requiere decisión; Belief UI congelada en handoff).

---

### CORE-B lab-adoption-memory

| Campo | Valor |
|-------|--------|
| Estado | Open · **v0.2 en código** · iteraciones pendientes |
| Severidad | Media (aprendizaje Lab entre pasadas) |
| Origen | Funnel design §6 · tras CORE A |
| Código | `lab-adoption-memory.ts` · `backtest-optimize-heatmap.ts` · optimize panel · explore stamp |

**Hecho (v0):** memoria localStorage del último Mejor; espacio guiado SMA/RSI; hint UI; stamp `labAdoption` en Finalistas post-Lab.

**Hecho (v0.1 · 2026-08-01):** al adoptar/guardar Mejor se persiste snapshot de meseta heatmap (`plateau`); espacio guiado **más ancho** si meseta, **más estrecho** si pico; hint «· meseta / · pico».

**Hecho (v0.2 · 2026-08-01):** sin semilla Coach, Lab elige familia por `resolveDefaultLabFamily` (adopción → horizonte perfil → SMA); elección manual no se pisa. Hint/orden de familias ya en CORE-P.

**Pendiente:** no reabre Lab UI P3–P9 / Discovery.

---

### finalists-top-without-runid (AENA)

| Campo | Valor |
|-------|--------|
| Estado | **Closed** (dato OK en live 2026-07-29; prevención en código) |
| Severidad | Alta (Camino A Checklist roto para ese valor) |
| Origen | `pnpm audit:ibex35` / `audit_ibex35_operativa.py` 2026-07-29 |
| Hallazgo | AENA TOP `active` + `lab_validated` **sin `runId`** en slots |

**Problema:** Finalistas Checklist no puede abrir el run; el usuario queda en mensaje «sin run guardado».

**Hecho:** API/app rechazan upsert `lab_validated`/`active` sin `runId` · promote TS exige runId · `pnpm backfill:top-runids -- --symbol AENA --dry-run` → `ya OK` · `TOP_sin_runId (0)`.

**Si reaparece:** `pnpm backfill:top-runids -- --symbol SYM --apply` o re-Lab.

### list-auto-freshness-restart

| Campo | Valor |
|-------|--------|
| Estado | **Fixed** 2026-07-30 (v1.2) · **histéresis v1.3** 2026-08-01 |
| Severidad | Alta (recomputaba IBEX tras reinicio / 1 barra) |
| Código | `backtest-finalists-freshness.ts` · run-context · gate perfil en `backtests-page` |

**Problema:** Play tras reinicio re-analizaba todos los valores aunque el análisis fuese de minutos atrás. Además 1 barra nueva invalidaba toda la huella.

**Hecho v1.2:** omitir solo con Finalistas reales + huella · esperar perfil · persistir run-context · no forzar Universo si falla TOP.

**Hecho v1.3:** histéresis `lastBarDate` (`1d` ≤5 días calendario → `bar_hysteresis`; stamp no desliza; «Reevaluar resto» fuerza).

### ibex35-partial-tops-coverage

| Campo | Valor |
|-------|--------|
| Estado | Open · ops (Lista AUTO) |
| Severidad | Media (cobertura operativa) |
| Origen | misma auditoría 2026-07-29 · recheck live |
| Hallazgo | **19/35** sin TOP (`con_TOP=16/35`); `TOP_sin_runId=0` |

**Problema:** Lista AUTO / Play ciclo no se ha corrido (o no guardó) sobre todo el índice. Monitor y embudo incompletos.

**Qué hacer:**  
1. `pnpm audit:ibex35:missing` → símbolos sin TOP / sin runId  
2. Universo → Lista **IBEX 35** → **Play ciclo** (frescura v1.3 omite valores **con** Finalistas; histéresis lastBar)  
   · **No** crear/usar lista «IBEX sin TOP» de producto ([pausa](../../docs/engineering/product-pause-audit-2026-07-30.md))  
3. No confundir con Fase C «Probar lista»  

sin_TOP (live): BKT, CABK, IAG, IBE, IDR, ITX, LOG, MAP, MEL, NTGY, PHM, RED, REP, ROVI, SAB, SAN, SCYR, UNI, VIS

---

### macd-signal-ema-warmup

| Campo | Valor |
|-------|--------|
| Estado | Open |
| Severidad | Baja (instrumentación / fidelidad del indicador) |
| Origen | Auditoría post-C3 / C3.5 |
| Código | `bolsa_analytics.optimize.macd_grid._macd_signal_line` |

**Problema:** la EMA de señal se calienta sembrando `None → 0.0` en la línea MACD. El backtest H0 funciona, pero el arranque no es el warm-up clásico del indicador.

**Qué no hacer ahora:** no tocar el motor ni re-ejecutar C3.

**Criterio de cierre:** antes de tratar `macd_grid_h0` como referencia estable, implementar seed clásico (retrasar hasta datos válidos / EMA sobre tramo no nulo) y documentar paridad vs. preset human `macd_signal_cross`.

---

## Closed

### coach2-soft-ack-race (2026-07-30)

| Campo | Valor |
|-------|--------|
| Estado | Closed |
| Severidad | Alta (ciclo ✓ Finalistas sin TOP en BD) |
| Código | `backtest-explore-panel.tsx` · `assistant-funnel-map.ts` · rail 5 etapas · prefs ACK |

**Problema:** tras Lab→Coach², ACK se reseteaba en cada recompute de `localDeep`; soft-ACK fallía; settle marcaba ciclo hecho (`skip_finalists`) con checkbox vacío y foco en Coach.

**Fix:** latch ACK solo al cambiar lote/pasada; prefs `autoAckOnCycle` / `pauseIfAckNeeded`; progreso `finalistsSaved`/`finalistsSkipped`; rail mapa 5 etapas (Probar→…→Finalistas).

---

### grid-is-metrics-homogeneity (2026-07-24)

| Campo | Valor |
|-------|--------|
| Estado | Closed (forward-only) |
| Origen | Auditoría A1 post-C3.5 |

**Problema:** grids escribían `PnL / DD / trades / score` sin `sharpeRatio` (y resto IS), provocando ~92% Sharpe NULL en el ledger.

**Fix:** `compute_is_metrics` compartido + `finalize_grid_is_metrics`; SMA/RSI/MACD grids y hook optimize persisten el mismo payload IS que human.

**Nota:** trials grid ya persistidos (C1–C3) **no** se reescriben ni consumen K de nuevo. Homogeneidad aplica a grids futuros. Cross-family C3.5 sigue anclado en human por diseño.
