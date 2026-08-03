# Respuesta a Auditoría 2 — Lab backtests UI (2026-08-03)

> **Ámbito:** `apps/web/src/features/backtests/` + APIs Lab Python.  
> **Stack real:** UI React orquesta; **grids / PBO / WF / CPCV / backtests** corren en **Python** (`POST /backtests/*`).  
> **Premisas:** [PROJECT_PREMISES.md](../PROJECT_PREMISES.md) · Freeze: [post-audit-decision-freeze-2026-08-03.md](./post-audit-decision-freeze-2026-08-03.md).

---

## 0. Resumen

La auditoría 2 describe bien el **rigor cuantitativo** (PBO, OOS, Paper Gate, embudo) y la UX (Replay/Movie HUD).  
Sobreestima el riesgo de «cómputo pesado en el hilo principal»: matrices y PBO **no** se calculan en el browser.

| Hallazgo auditoría | Veredicto | Acción |
|--------------------|-----------|--------|
| Web Workers para PBO/matriz | **Mal planteado** (ya es backend) | Soft-caps + HTTP concurrency; no Workers |
| Costes / slippage | **Parcial mal nombrado** | `commissionBps`/`slippageBps` en motor Python; `period-returns` ≠ costes; v2 gated |
| Zod en `assistant-completion` | **Archivo incorrecto** | Validación en API + `sanitizeLlmDeepCoachPayload` |
| Abort LLM mid-cycle | **Gap real** | AbortSignal + ignore late success |
| IndexedDB vs LS | **Parcial** | Lista AUTO = snapshots pequeños; historial en BD |
| Underwater DD chart | **Missing** | Pane under equity |
| Telemetría matriz | **Missing** | `elapsedMs` en progress |
| Paper Gate / PBO / OOS / WFE | **EXISTS** | Sin cambio |
| Soft-caps mass compare | **EXISTS** | 40×8 / 120 celdas |

---

## 1. Hardening entregado (esta pasada)

| Ítem | Evidencia |
|------|-----------|
| Validación payload coach | `bolsa_ai.schemas.validate_backtest_coach_payload` · route `/ai/backtest-coach/analyze` → heuristic si falla |
| Sanitize cliente | `sanitizeLlmDeepCoachPayload` · merge solo prosa |
| Abort LLM | `AbortController` en explore panel · `api.analyzeBacktestCoach(..., { signal })` |
| Underwater DD | `toUnderwaterDrawdownData` + AreaSeries `priceScaleId=dd` en equity chart |
| Telemetría matriz | `StrategyMatrixRunProgress.elapsedMs` |

---

## 2. Qué no se abre (freeze / ROI)

- Activar `COST_MODEL_V2` por defecto.  
- Migración IndexedDB del historial (historial ya es API/BD).  
- Web Workers / microservicio Rust para grids.  
- Auto-paper / Belief Fase 2.

---

## 3. Verificar

```bash
python -m pytest packages/py/ai/tests/test_backtest_coach_schema.py -q
pnpm --filter @bolsa/web exec vitest run src/features/backtests/coach-llm-invariant.test.ts
```
