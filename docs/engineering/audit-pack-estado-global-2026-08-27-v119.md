# Audit pack — estado global v1.19 (Opportunity Discovery + Mesa Zona 1)

> **AsOf:** 2026-08-27 · **Tag (stamp):** **`v1.19-beta` → `c30594e`**. Partida **`v1.18-beta` → `4d1b2e6`**.
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · ADR-037 · ADR-039 · plan [`plan-v119-opportunity-discovery-2026-08-27.md`](./plan-v119-opportunity-discovery-2026-08-27.md) · pack previo [`audit-pack-estado-global-2026-08-27-v118.md`](./audit-pack-estado-global-2026-08-27-v118.md).
> **Para:** auditoría cruzada post-v1.19 · Release tag CI.

---

## 0. Veredicto interno

Ciclo **V1.19** **CERRADO** (Opportunity Discovery + Mesa L3 ranking ≠ Action Queue + scan diario opt-in + fusión Zona 1). Eleva la pregunta correcta de Mesa (**mejores oportunidades para ESTA cartera, de lo medido**) **sin** convertir Decision Board en screener y **sin** thaw/AUTO. DEX-1…DEX-5 **intactos**. Confirm = **única** firma. `PAPER_D_EXECUTE` **OFF**. AUTO **off**. LIVE **experimental**. Producto **BETA**.

| Epic       | Nombre                                                         | Estado  |
| ---------- | -------------------------------------------------------------- | ------- |
| OPP-DISC   | Funnel + Ranking (scan+studies); Quality 0–100 → Priority      | CERRADO |
| MESA-L3    | «Mejores oportunidades» TOP 5 · embudo · CTA Señales · umbral  | CERRADO |
| SCAN-OPTIN | `OPPORTUNITY_DAILY_SCAN_ENABLED` default OFF · propose cap 15  | CERRADO |
| ZONA1      | `/operations`+`/decision-board` → Mesa `?focus=` · Libro/Spine | CERRADO |

**Mensaje clave:** v1.18 dejó Opportunity como contrato; v1.19 **deja de usar la Action Queue como ranking del mercado**, hace visible el denominador (funnel), y unifica la zona diaria en Mesa.

---

## 1. Scorecard

| Epic         | Cierra                                             | Evidencia                                                                        |
| ------------ | -------------------------------------------------- | -------------------------------------------------------------------------------- |
| **OPP-DISC** | Ranking ≠ Action Queue; Quality pura en Priority   | `opportunity-ranking.ts` · `opportunity-evidence.ts` · `operational-priority.ts` |
| **MESA-L3**  | Funnel + TOP 5 + baja calidad honesta + CTA        | `mesa-candidates-panel.tsx` · `mesa-hoy-page.tsx`                                |
| **SCAN**     | Opt-in OFF; enqueue; propose acotado; cero execute | `opportunity_daily_discovery.py` · `opportunity_daily_scan_worker.py`            |
| **ZONA1**    | Redirects + Libro/Spine absorbidos                 | `app.tsx` · `mesa-libro-panel.tsx` · `decision-spine-detail-panel.tsx`           |

---

## 2. Batería (local, 2026-08-27)

| Gate                                          | Resultado      |
| --------------------------------------------- | -------------- |
| `pnpm --filter @bolsa/shared` build           | OK             |
| Shared DoD (opp + priority + mesa-hoy-model)  | **25** passed  |
| Web `tsc --noEmit`                            | OK             |
| Web mesa + daily-nav + decision-board + zone1 | **35** passed  |
| Pytest `test_opportunity_daily_discovery`     | **5** passed   |
| `pnpm test:decision-spine`                    | **497** passed |

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run opportunity-evidence opportunity-ranking operational-priority mesa-hoy-model
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm --filter @bolsa/web test -- mesa-hoy mesa-candidates daily-nav decision-board mesa-zone1
python -m pytest packages/py/application/tests/test_opportunity_daily_discovery.py -q
pnpm test:decision-spine
# expect: 497 passed
```

Spine: **497** (v1.18) → **497** (v1.19; sin cambio spine).

---

## 3. Freeze (intacto)

Confirm = firma · DEX-1…5 · `PAPER_D_EXECUTE` off · AUTO off · BETA · Scenario ≠ permiso · Ranking ≠ BUY · Opportunity ≠ Permission · Stress ≠ permiso · Decision Board ≠ screener · LLM no ejecuta.

---

## 4. Deuda restante (explícita)

| ID          | Limitación                                            | Severidad   |
| ----------- | ----------------------------------------------------- | ----------- |
| OPP-SCORE   | OpportunityScore multiplicativo (V1.20+)              | Producto    |
| OPP-ENGINE  | Análisis TA+FA universo amplio (no solo scan/studies) | Producto    |
| STRESS-FULL | Correlación / VaR                                     | Producto    |
| V118-B      | B-read Mesa / backfill legacy                         | ADR-038     |
| LAB-B       | Backtest ≠ TradingPolicy                              | Lab         |
| THAW        | Accept estricto 60d/50/70/55                          | Deuda larga |
| AUTO-ON     | AUTO on / LIVE producción                             | Freeze      |

---

## 5. Qué **no** entra

Thaw · AUTO ON · `contract:gen` · renombrar Python `opportunity.py` · convertir GetDecisionBoard en screener · OpportunityScore pleno.
