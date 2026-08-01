# Análisis Fundamental (FA) — readiness (actualizado 2026-07-31)

> **Estado:** track FA **cerrado en código**; fase **prueba APP + optimización**.  
> Diseño canónico → [`fundamental-intelligence-engine-2026-07-30.md`](./fundamental-intelligence-engine-2026-07-30.md).  
> Plan de prueba → [`fa-status-and-test-plan-2026-07-31.md`](./fa-status-and-test-plan-2026-07-31.md).  
> Ayuda UI → **Análisis del valor** (`HELP_CONTENT_AS_OF=2026-07-31`).

---

## 1. ¿Listos?

**Sí — implementación completa del pack FIE acordado.** Próximo trabajo: validar en datos reales, medir null-rates y pulir UX/latencia.

| Track | Estado |
|-------|--------|
| FIE diseño (auditorías) | Hecho |
| F0–F1 / F1b | Hecho |
| F2.0–F2.8 (gate…Beneish) | Hecho |
| F2b / + / ++ filings | Hecho |
| F3 Composite | Hecho |
| F4 Screener FA | Hecho |
| Paper D + cron FA→D | Hecho (execute/cron off-by-default) |
| Verificación | `pnpm test:fa` |
| Ayuda documentada | Inventario + checklist en UI |

---

## 2. Decisiones bloqueadas

| # | Decisión |
|---|---------|
| 1 | FA = capa scoring/filtro; no embudo Coach paralelo |
| 2 | Python calcula; LLM solo explica |
| 3 | Filings fuera de Score_FUND/gate numérico |
| 4 | Piotroski/Beneish null-if-incomplete |
| 5 | Card: `scoreDisplay100`; sin `bias` |
| 6 | Paper D ≠ radar B ≠ Supervisado C |

---

## 3. Regla de oro

**Python calcula; LLM interpreta.** Ningún LLM escribe ratios ni BD operacional.

---

## 4. Enlaces

- Estado + checklist: `fa-status-and-test-plan-2026-07-31.md`
- FIE: `fundamental-intelligence-engine-2026-07-30.md`
- Código entrada: `packages/py/market/.../instrument_fundamentals.py`
- Ayuda: `apps/web/src/features/settings/value-analysis-tracker.ts`
- Battery: `scripts/research/verify_fa_battery.mjs`
