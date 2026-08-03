# Decisión de cierre post-auditorías (2026-08-03)

> **AsOf:** 2026-08-03 · Decisión de producto tomada por defecto tras Q0–Q3 + higiene ISSUES.  
> **Contexto:** usuario sin preferencia clara entre C4 / Belief / flags ops → se elige **no abrir** los tres.

## Veredicto

| Opción | Decisión | Por qué |
|--------|----------|---------|
| **Gate C4 / Bollinger** | **No abrir** | Δ RSI IBEX 13 same / 22 changed (`2026-08-03-stability-delta-ibex.md`). No hay hipótesis escrita que justifique nueva familia. |
| **Belief → Coach (CORE-A)** | **Congelado** | v0 Coach LLM ya es honesto (no corona TOP). Belief Fase 2 es diseño + UI + outcomes; no es un flip. Reabrir solo con brief de producto. |
| **`CORE_R_CRON_ENABLED`** | **Sigue `false`** | Cola ya funciona con app abierta + BD multi-dispositivo. Cron servidor = ops cuando haga falta tick 24/7; coste de ruido/false enqueues no justificado aún. |
| **`COST_MODEL_V2_ENABLED`** | **Sigue `false`** | Cambia economía de backtests / rankings. Activar solo en Lab A/B controlado, no como default silencioso. |

### Futuro — Belief (apuntalado, no ahora)

Brief de producto listo para cuando toque reabrir (2026-08-03, **sin implementar**):

- [belief-coach-brief-draft-2026-08-03.md](./belief-coach-brief-draft-2026-08-03.md) — contrato anti-soberbia B1–B8 + criterios de reapertura  
- Decisión 2026-08-03: **seguir probando el Lab entregado**; no implementar Belief hasta ratificar el brief y uso real del embudo.

## Qué sí hacer ahora

1. **Usar** lo entregado: Play ciclo · Lista AUTO · Finalistas · Monitor CORE-R · Lab Health · mass compare · warm-up gate.  
2. **Vigilar** CORE-R en uso real (`pnpm test:operativa` tras cambios).  
3. **Re-auditar** IBEX TOP si cambia el universo (`pnpm audit:ibex35:missing`).  
4. **Revisar esta ficha** solo si aparece: necesidad real de cron 24/7, experimento de costes v2, o brief Belief.  
5. **Docstrings:** lotes 1–4 cerrados — solo forward-only al tocar código ([estándar](./code-documentation-standard-2026-08-03.md)).

## Qué no hacer

- No nueva familia (ADX/ATR/Bollinger/C4) “porque faltan”.  
- No auto-paper D · no rewrite K histórico · no Fase H (Monte Carlo / OTel / DuckDB / Strategy Studio).  
- No activar flags ops en `.env` de demo sin anotar el motivo aquí.

## Enlaces

- Roadmap: [improvement-roadmap-post-audits-2026-08-02.md](./improvement-roadmap-post-audits-2026-08-02.md) §8  
- Estabilidad: [research/observations/2026-08-03-stability-delta-ibex.md](../../research/observations/2026-08-03-stability-delta-ibex.md)  
- Flags: [github-credentials-and-ops.md](./github-credentials-and-ops.md) §9  
- Deuda lab: [research/observations/ISSUES.md](../../research/observations/ISSUES.md)
