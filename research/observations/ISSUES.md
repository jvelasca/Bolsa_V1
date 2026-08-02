# Lab issues (deuda técnica de explotación)

Registro **ligero** de issues del laboratorio. No son tickets de producto ni ADR.
No abren Fase 2 ni entidades nuevas.

**Higiene 2026-08-03:** Open = vigilancia / bloqueados; Closed = entregado o ops resuelto.

## Open

### CORE-R continuous-strategy-reevaluation · **vigilancia**

| Campo | Valor |
|-------|--------|
| Estado | Open · **v0–v1.12** entregado · vigilar uso real |
| Severidad | **Crítica (producto a medio plazo)** |
| Origen | Decisión usuario 2026-07-29 (tras pulir Lista AUTO) |
| Código | `core-r-judgment.ts` · `core-r-scheduler.ts` · `core-r-scheduler-host.tsx` · `core_r_review_evidence.py` · Monitor · tablero Lista AUTO |
| Doc | `docs/engineering/list-auto-ops-2026-07-29.md` § CORE-R |

**Idea:** de forma **periódica** (manual y automática), volver a evaluar si la estrategia / Finalistas **en curso** siguen siendo los adecuados o conviene **mejorar / optimizar / cambiar**.

**Entregado (v0–v1.12):** juicio heurístico · cola Monitor · OOS/PnL · narración · cron shell · chip/toast · Hecho todos · BD multi-dispositivo · cron servidor (`CORE_R_CRON_ENABLED`, off) · PnL en cron · toast remoto. **No** pisa `active`. **No** auto-paper D.

**Pendiente:** ninguno crítico en cola/cron — vigilar uso real; issues cortas si falla.

**Ops:** `pnpm test:operativa` · `pnpm test:operativa:smoke` (API opcional).

---

### CORE-A coach-soft · **bloqueado**

| Campo | Valor |
|-------|--------|
| Estado | Open · **v0 en código** · ciclo Belief pendiente |
| Severidad | Media (calidad / honestidad del Coach) |
| Origen | Funnel design §6 · tras Play + CORE-P |
| Código | `coach.llmNarrate` · `coach-llm-invariant.test.ts` · `readPriorCoachAuditHint` |

**Hecho (v0):** toggle Narración LLM en rail; OFF = solo ★ local + auditor heurístico; tests «LLM no corona TOP»; hint UI de pasada previa (`dualAudit`) sin modular score.

**Pendiente:** aprendizaje outcomes / Belief → Coach (requiere decisión; Belief UI congelada en handoff).

---

### CORE-B lab-adoption-memory · **parked**

| Campo | Valor |
|-------|--------|
| Estado | Open · **v0.2 en código** · sin más UI Lab |
| Severidad | Media (aprendizaje Lab entre pasadas) |
| Origen | Funnel design §6 · tras CORE A |
| Código | `lab-adoption-memory.ts` · `backtest-optimize-heatmap.ts` · optimize panel · explore stamp |

**Hecho (v0–v0.2):** memoria último Mejor · meseta heatmap → espacio · `resolveDefaultLabFamily` sin semilla Coach · stamp `labAdoption`.

**Pendiente:** no reabre Lab UI P3–P9 / Discovery.

---

## Closed

### CORE-P profile-coach-lab-binding · 2026-08-01

| Campo | Valor |
|-------|--------|
| Estado | Closed · **v1 + deep-dive + E2E live smoke** · BETA1 vigilancia |
| Severidad | Alta (coherencia inversor ↔ estrategias) |
| Origen | Decisión producto 2026-07-29 (Asistente 1-Play) |
| Doc | `docs/engineering/profile-coach-lab-binding.md` · funnel design §3 |
| Código | `coach-profile-policy.ts` · explore stamp · Lab DD · rail · invalidate ciclo |

**Hecho:** gate Lab · stamp perfil · techo DD · familias/horizonte · mismatch · soft-bias · `pnpm test:coach:smoke` / ASGI multi-perfil.

**Vigilancia BETA1:** simulaciones multi-perfil en uso real — issues cortas si falla; no reabrir congelados.

---

### list-auto-freshness-restart · 2026-08-01

| Campo | Valor |
|-------|--------|
| Estado | Closed · Fixed v1.2 (2026-07-30) · histéresis **v1.3** 2026-08-01 |
| Severidad | Alta (recomputaba IBEX tras reinicio / 1 barra) |
| Código | `backtest-finalists-freshness.ts` · run-context · gate perfil en `backtests-page` |

**Problema:** Play tras reinicio re-analizaba todos los valores; 1 barra nueva invalidaba la huella.

**Fix:** omitir con Finalistas + huella · histéresis `lastBarDate` (`1d` ≤5 días → `bar_hysteresis`); «Reevaluar resto» fuerza.

---

### finalists-top-without-runid (AENA) · 2026-07-29

| Campo | Valor |
|-------|--------|
| Estado | Closed (dato OK + prevención en código) |
| Severidad | Alta (Camino A Checklist roto para ese valor) |
| Origen | `pnpm audit:ibex35` / `audit_ibex35_operativa.py` 2026-07-29 |

**Problema:** TOP `lab_validated`/`active` sin `runId` → Checklist «sin run guardado».

**Fix:** API/app rechazan upsert sin `runId` · promote exige runId · `pnpm backfill:top-runids`. Si reaparece: backfill `--apply` o re-Lab.

---

### ibex35-partial-tops-coverage · 2026-08-03

| Campo | Valor |
|-------|--------|
| Estado | Closed (ops) |
| Severidad | Media (cobertura operativa) |
| Origen | auditoría 2026-07-29 · recheck live |
| Hallazgo cierre | `pnpm audit:ibex35:missing` → **con_TOP=35/35**, `TOP_sin_runId=0` |

**Cierre:** cobertura completa IBEX 35 en Finalistas. Vigilancia: re-auditar tras cambios de universo; Play ciclo / «Reevaluar resto» si aparecen huecos.

---

### macd-signal-ema-warmup · 2026-08-03

| Campo | Valor |
|-------|--------|
| Estado | Closed (forward-only) |
| Severidad | Baja (instrumentación / fidelidad del indicador) |
| Origen | Auditoría post-C3 / C3.5 |
| Código | `compute_macd_signal_line` · `macd_grid` · `rules_engine` (preset `macd_signal_cross`) |

**Problema:** la EMA de señal se calentaba con `None → 0.0` en la línea MACD.

**Fix:** seed clásico — EMA solo sobre el tramo MACD no nulo; barras previas `None`. Grid y human comparten helper. Trials C1–C3 **no** se re-ejecutan ni reescriben K.

---

### warmup-audit (Q0.3 → Q1.6) · 2026-08-03

| Campo | Valor |
|-------|--------|
| Estado | Closed |
| Severidad | Media (reproducibilidad OOS) |
| Código | `bolsa_analytics.warmup_matrix` · grids SMA/RSI/MACD · `campaign_close_gate.py` · `verify_oos_warmup.py` |
| Relacionado | `#macd-signal-ema-warmup` |

**Hecho:** matriz + `assert_grid_warmup` en `run_*_grid` · `check_manifest_warmup` en gate Q1.6 · campaign RSI salta con `WarmupInsufficientError`. No reescribe K histórico.

---

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
