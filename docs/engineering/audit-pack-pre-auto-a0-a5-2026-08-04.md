# Paquete de auditoría — prep pre-AUTO A0–A5 (2026-08-04)

> **Propósito:** documento **único** para auditar el cierre de prep Camino D / Libro AUTO **sin** thaw execute.  
> **AsOf:** 2026-08-04 · branch `stage/estudio-membership-operativa-2026-08-04` · PR [#29](https://github.com/jvelasca/Bolsa_V1/pull/29) · repo `jvelasca/Bolsa_V1`  
> **Padres:** [pack Canales](./audit-pack-estudio-asesor-canales-2026-08-04.md) · [triage institucional](./audit-ext-institutional-pre-auto-triage-2026-08-04.md) · [checklist thaw](./camino-d-auto-thaw-checklist-2026-08-04.md) · [freeze](./post-audit-decision-freeze-2026-08-03.md)  
> **Detalle código:** [camino-d-a2-a5-prep](./camino-d-a2-a5-prep-2026-08-04.md) · [OR-lite/Repro/Obs](./or-lite-repro-obs-2026-08-04.md) · [OR-RE](./risk-engine-or-re-2026-08-04.md) · [ADR-023](../adr/023-camino-d-thaw.md) (**Proposed**)

---

## 0. Resumen ejecutivo

| Bloque | Pregunta | Estado |
|--------|----------|--------|
| **A0** | ¿Telemetría dictamen (precisión/recall proxy)? | **Hecho** · `GET …/telemetry` + strip Asesor |
| **OR-lite / OR-RE / Repro+ / Obs** | ¿Decimal, APP_PASSWORD, Risk Engine, fingerprints, ErrorBoundary, gitleaks, heartbeat? | **Hecho** |
| **A1** | ¿Libro AUTO visible disabled + riesgos? | **Hecho** · pill «Auto · prep» |
| **A2** | ¿Execute path detrás flag + Risk Engine + idempotencia + DecisionSession? | **Hecho (flag off)** |
| **A3** | ¿Kill switch UI/API + doble confirm armado? | **Hecho** · no habilita pill |
| **A4** | ¿ADR thaw + freeze nota? | **Proposed** · evidencia P1–P5 ☐ |
| **A5** | ¿Opt-in 1 cuenta? | **Hecho (gate)** · `PAPER_D_ACCOUNT_ID` |
| **`PAPER_D_EXECUTE`** | ¿Se puede flippear en demo? | **No** — default off · P1–P10 |

**Veredicto:** prep **PASS** para auditoría de *código detrás de flags*. **FAIL / no procede** thaw AUTO execute hasta evidencia P1–P5 + ADR-023 Accepted.

**Operativa diaria recomendada:** SEMI + Confirm. AUTO execute **no** está liberado.

---

## 1. Cómo auditar (25–35 min)

1. Leer §0 y [checklist thaw](./camino-d-auto-thaw-checklist-2026-08-04.md) fases A0–A5.  
2. ADR-023: estado **Proposed**, tabla evidencia vacía.  
3. Tests:  
   - `python -m pytest packages/py/application/tests/test_auto_execute_idempotency.py packages/py/application/tests/test_risk_engine.py packages/py/application/tests/test_paper_d_propose.py packages/py/application/tests/test_campaign_manifest.py -q`  
   - `pnpm --filter @bolsa/web test -- src/features/trading/demo-book-*.test.ts`  
4. Smoke UI: Operativa → Configuración → Kill switch + Armar AUTO (frase `ACTIVAR AUTO`) → pill Auto sigue disabled; `PAPER_D_EXECUTE` badge off.  
5. Health: `GET /api/health` → `components.risk`, `auth`, `worker_arq`.  
6. Freeze: `.env` sin `PAPER_D_EXECUTE=1`.

---

## 2. Mapa de código

| Capacidad | Path |
|-----------|------|
| Telemetría A0 | `daily_opinion_telemetry.py` · route opinions `…/telemetry` · Asesor UI strip |
| Risk Engine | `risk_engine.py` · `execution_router.py` (`check_opening`) |
| Kill runtime | `risk_runtime.py` · `routes/risk.py` · panel Operativa |
| Idempotencia | `auto_execute_idempotency.py` · claim en Router |
| Paper D gate | `paper_d_propose.paper_d_execute_allowed` · `PAPER_D_ACCOUNT_ID` |
| Manifest Repro+ | `campaign_manifest.py` |
| Libro AUTO UI | `demo-book-mode-panel.tsx` · `demo-book-auto-copy.ts` · `demo-book-auto-arm.ts` |
| ErrorBoundary | `app-error-boundary.tsx` |
| Gitleaks | `.github/workflows/gitleaks.yml` |
| Heartbeat Arq | `worker_heartbeat.py` · health `worker_arq` |

---

## 3. Invariantes

| # | Invariante | Evidencia |
|---|------------|-----------|
| 1 | Execute Paper D sin env → `blocked_env` | `test_paper_d_propose` |
| 2 | Kill switch → DENY aperturas auto | Risk Engine + runtime OR |
| 3 | `demoBookAllowsExecute('auto') === false` | prefs tests |
| 4 | Storage `mode:auto` → coerce SEMI | normalize prefs |
| 5 | Armado local ≠ execute | arm prefs; pill off |
| 6 | SEMI Confirm no pasa por Risk Engine | humano autorizado (Camino C) |
| 7 | Radar `paper_auto` ≠ Libro AUTO | paper-paths-copy T8 |

---

## 4. Fuera de alcance (no fallar por esto)

- Evidencia P1–P5 medible en producción (días/ops/%)  
- ADR-023 Accepted  
- Flip `PAPER_D_EXECUTE`  
- Broker live · Belief · `CORE_R_CRON` · Strategy Studio  

---

## 5. Preguntas para auditoría externa

1. ¿El kill switch runtime (memoria+Redis) es suficiente vs solo env para P7?  
2. ¿Idempotencia 48h Redis+memoria cubre el riesgo de doble fill DEMO?  
3. ¿Exigís DecisionSession también en SEMI Confirm fills (hoy Gate/confirm)?  
4. ¿Umbrales P1–P5 del triage siguen razonables tras telemetría A0?

---

## 6. Resultado auditoría interna (2026-08-04)

| Check | Resultado |
|-------|-----------|
| pytest idempotency + risk + paper_d + manifest | **OK** (suite prep) |
| Vitest demo-book prefs/copy/arm | **OK** |
| `PAPER_D_EXECUTE` default off documentado | **OK** |
| ADR-023 Proposed sin evidencia | **OK** (esperado) |
| Thaw execute | **No** |

**Veredicto interno:** prep A0–A5 **lista para auditoría externa de código**. Operador puede usar **SEMI**; no liberar AUTO execute.

---

## 7. Enlaces GitHub

- PR: https://github.com/jvelasca/Bolsa_V1/pull/29  
- Pack Canales: [audit-pack-estudio-asesor-canales](./audit-pack-estudio-asesor-canales-2026-08-04.md)  
- Pack Lab: [audit-pack-post-audits](./audit-pack-post-audits-2026-08-03.md)  
- HELP: [docs/HELP.md](../HELP.md) · Ayuda in-app Trading/Operativa  
