# Paquete de auditoría — post-auditorías Q0–Q3 + freeze (2026-08-03)

> **Propósito:** documento **único** para pasar auditorías del cierre post-etapa (tras [stage-audit LAB/DÍA D/Mandato](./stage-audit-lab-dia-d-mandate-2026-08-02.md)).  
> **AsOf:** 2026-08-03 · `HELP_CONTENT_AS_OF` · `main` · repo **público** (`jvelasca/Bolsa_V1`) para auditorías externas.  
> **Premisas:** [PROJECT_PREMISES.md](../PROJECT_PREMISES.md) (documentar todo + docstrings).  
> **Índice docs ingeniería:** [engineering-index-2026-08-03.md](./engineering-index-2026-08-03.md).  
> **Repo:** `https://github.com/jvelasca/Bolsa_V1`

---

## 0. Resumen ejecutivo

| Pieza | Pregunta | Estado |
|-------|----------|--------|
| **Etapa LAB/DÍA D/Mandato** | ¿Universos + Verify + Mandato cerrados? | Sí — [stage-audit](./stage-audit-lab-dia-d-mandate-2026-08-02.md) |
| **Roadmap Q0–Q3** | ¿Lab Health, manifests, warm-up, estabilidad, FIE hygiene, CORE-R BD, costes v2 gated? | Sí — [roadmap §8](./improvement-roadmap-post-audits-2026-08-02.md) |
| **Q1.6 warm-up** | ¿Grids/campañas fallan si faltan barras? | Sí — `assert_grid_warmup` + gate |
| **Estabilidad IBEX** | ¿Ranking RSI estable entre ventanas? | **No** (13 same / 22 changed) → Gate C4 **cerrado** |
| **IBEX Finalistas** | ¿Cobertura TOP? | **35/35**, `TOP_sin_runId=0` |
| **Freeze producto** | ¿C4 / Belief / flags ops? | **No abrir** — [decision freeze](./post-audit-decision-freeze-2026-08-03.md) |
| **DEMO SEMI** | ¿Libro operativo Confirm F3? | Sí — MANUAL/SEMI · geo · cola BD · tenure 5a/5b · H≠M · [handoff](./session-handoff-2026-08-03-semi.md) · `pnpm test:semi` |
| **Auditoría 1 (ingesta+FIE)** | ¿Gaps A/B del informe externo? | Ver [audit1-response](./audit1-response-ingest-fie-2026-08-03.md) — CB Yahoo + cuarentena + health Redis + test FIE parcial |
| **Auditoría 2 (Lab UI)** | ¿Workers / Zod / abort / DD? | Ver [audit2-response](./audit2-response-backtests-lab-2026-08-03.md) — abort LLM + schema + underwater DD + elapsedMs |
| **Round 2 externas (A0·N4·Deep)** | ¿Complejidad docs / radiografía freeze / deep code? | Ver [audit-ext-round2-triage](./audit-ext-round2-triage-2026-08-03.md) — Index + bounded contexts; Deep = errata de stack |

**Cómo auditar en 30–45 min**

1. Leer este doc §0–§2 y el freeze.  
2. Etapa base: [stage-audit](./stage-audit-lab-dia-d-mandate-2026-08-02.md) §0–§3.  
3. Tests offline: `pnpm test:operativa` · `pnpm test:coach` · `pnpm test:semi` (sin API).  
4. Stack: Docker + `pnpm dev` → `pnpm test:operativa:smoke` · `pnpm test:coach:smoke` · `pnpm test:semi:smoke`.  
5. Ops: `pnpm audit:ibex35:missing` → esperar `con_TOP=35/35`.  
6. Estabilidad: observation [2026-08-03-stability-delta-ibex.md](../../research/observations/2026-08-03-stability-delta-ibex.md).  
7. Si el informe cita tRPC / Next / `packages/engine`: leer [round2 triage](./audit-ext-round2-triage-2026-08-03.md) §3 primero.

---

## 1. Errata respecto a stage-audit 2026-08-02

El stage-audit §6 decía «CORE-R cola multi-dispositivo (sigue localStorage)».

**Corrección 2026-08-03:** CORE-R v1.9–v1.12 — BD `core_r_account_state` + sync; LS = cache; cron servidor **off** (`CORE_R_CRON_ENABLED`). Toast remoto multi-dispositivo. Auto-paper D sigue congelado.

---

## 2. Entregables post-auditorías (checklist)

### Q0 — Observabilidad Lab

| Ítem | Evidencia |
|------|-----------|
| Lab Health | `GET /api/research/lab-health` · Observatory · `lab_health_report.py` |
| Campaign manifest v0 | `campaign_manifest.py` · `research/campaigns/*.json` |
| Warm-up matrix + assert | `warmup_matrix.py` · grids SMA/RSI/MACD · `campaign_close_gate.py` |
| Caveat Sharpe | Lab Health + notebook C3.5 |

### Q1 — Temporalidad / campañas

| Ítem | Evidencia |
|------|-----------|
| Dataset metadata | `dataset_metadata` en trials human |
| Estabilidad multi-ventana | `stability_windows_smoke.py --full` · Δ IBEX MD |
| family.yaml | `research/families/{sma,rsi,macd}/` |
| Gate cierre | `campaign_close_gate.py` (manifest + warm-up + zero-trades) |

### Q2 — FIE / higiene

| Ítem | Evidencia |
|------|-----------|
| Confidence/stale, OHLCV quarantine, health components, redact, rate limit, FA ROE guardrails | roadmap §8 · `test_q2_hygiene` / FA tests |

### Q3 — Producto usable

| Ítem | Evidencia |
|------|-----------|
| Embudo labEvidence | badge Finalistas/Coach |
| Mass compare | UI + `mass_compare_list.py` |
| CORE-R BD + cron off + toast remoto | `core-r-sync.ts` · worker · HELP |
| Costes v2 gated | `COST_MODEL_V2_ENABLED=false` |

### Fidelity MACD (forward-only)

| Ítem | Evidencia |
|------|-----------|
| Signal EMA classic seed | `compute_macd_signal_line` · `test_macd_signal_warmup` · ISSUES closed |

---

## 3. Verificación ejecutada (sesión 2026-08-03)

| Check | Resultado |
|-------|-----------|
| `pnpm test:operativa` | OK (74 vitest + 33 pytest) · re-check mañana OK |
| `pnpm test:operativa:smoke` | PASS (health, FA asOf, Evidence, CORE-R, persist) · re-check mañana PASS |
| `pnpm test:coach:smoke` | PASS (CORE-P multi-perfil) · re-check mañana PASS |
| `pnpm audit:ibex35:missing` | `con_TOP=35/35` · `sin_TOP=0` · `TOP_sin_runId=0` · re-check mañana OK |
| CI PRs #2–#10 | Mergeados a `main` (incl. docstrings lotes 1–4) |

Comandos de repetición:

```bash
docker compose up -d          # si PG down
pnpm db:ensure
pnpm dev                      # Web :5173 · API :8000
pnpm test:operativa
pnpm test:operativa:smoke
pnpm test:coach:smoke
pnpm audit:ibex35:missing
```

---

## 4. Decisiones de no-hacer (freeze)

Ver [post-audit-decision-freeze-2026-08-03.md](./post-audit-decision-freeze-2026-08-03.md).

| Tema | Decisión |
|------|----------|
| C4 / Bollinger | **No** |
| Belief → Coach | **Congelado** |
| `CORE_R_CRON_ENABLED` | **false** |
| `COST_MODEL_V2_ENABLED` | **false** |
| Fase H / auto-paper D / rewrite K | **No** |

---

## 5. Deuda abierta (vigilancia, no bloquea auditoría)

Fuente: [research/observations/ISSUES.md](../../research/observations/ISSUES.md)

| Issue | Estado |
|-------|--------|
| CORE-R | Entregado v1.12 · **vigilancia** uso real |
| CORE-A | v0 · bloqueado a Belief |
| CORE-B | v0.2 · parked (no Lab UI P3–P9) |
| Docstrings código | ~80% defs públicas sin docstring al AsOf — **no bloquea** producto; política + lote 1 en [code-documentation-standard](./code-documentation-standard-2026-08-03.md); medir con `python scripts/research/docstring_coverage_report.py` |

---

## 6. Índice de docs para el auditor

1. **Este archivo** (paquete post-auditorías).  
2. [stage-audit-lab-dia-d-mandate-2026-08-02.md](./stage-audit-lab-dia-d-mandate-2026-08-02.md) (+ errata §1).  
3. [improvement-roadmap-post-audits-2026-08-02.md](./improvement-roadmap-post-audits-2026-08-02.md) §8.  
4. [post-audit-decision-freeze-2026-08-03.md](./post-audit-decision-freeze-2026-08-03.md).  
5. [stability-campaign-protocol-2026-08-02.md](./stability-campaign-protocol-2026-08-02.md) · observation Δ IBEX.  
6. [HELP.md](../HELP.md) · [docs/README.md](../README.md).  
7. [operativa-test-plan-2026-07-31.md](./operativa-test-plan-2026-07-31.md).  
8. [github-credentials-and-ops.md](./github-credentials-and-ops.md) §9 flags.  
9. Logs locales (no producto): [dev-logs.md](./dev-logs.md).

---

## 7. Smoke UI (humano, 10 min)

1. Abrir http://localhost:5173 · universo LAB.  
2. Lista **IBEX 35** → **Play ciclo** → mayoría **Omitido** (frescura v1.3).  
3. Monitor → cola CORE-R (sin overwrite TOP).  
4. Ayuda → Backtesting: sync date **2026-08-03**, CORE-R v1.12.  
5. **SEMI (opcional):** Libro DEMO SEMI → Finalistas Proponer + alarma → F3 H≠M → Confirm → tenure en Coach.  

---

*Fin del paquete. Si código y este doc divergen: prevalece código + ADR; actualizar este archivo en el mismo PR.*
