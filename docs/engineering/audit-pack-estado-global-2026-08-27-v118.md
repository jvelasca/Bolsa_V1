# Audit pack — estado global v1.18 (Lineage + Mesa honesty + Stress MVP + OpportunityEvidence)

> **AsOf:** 2026-08-27 · **Tag (stamp):** **`v1.18-beta` → `4d1b2e6`**. Partida **`v1.17.1-beta` → `e0ae633`** (tag git `9c98fb8`).
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · ADR-038 · ADR-039 · pack previo [`audit-pack-estado-global-2026-08-27-v1171.md`](./audit-pack-estado-global-2026-08-27-v1171.md).
> **Para:** auditoría cruzada post-v1.18 · Release tag CI.

---

## 0. Veredicto interno

Ciclo **V1.18** **CERRADO** (L1+L2a + MR-1 + Stress MVP + OpportunityEvidence contrato). Eleva honestidad de memoria operativa y riesgo de cartera **sin** thaw/AUTO/LIVE prod. DEX-1…DEX-5 **intactos**. Confirm = **única** firma. `PAPER_D_EXECUTE` **OFF**. AUTO **off**. LIVE **experimental**. Producto **BETA**.

| Epic       | Nombre                                                      | Estado  |
| ---------- | ----------------------------------------------------------- | ------- |
| L1         | Position lineage por `decisionId` (fail-closed)             | CERRADO |
| L2a        | `originDecisionPackage` write-once al fill + `originThesis` | CERRADO |
| MR-1       | Mesa honesty residual (what-if / Datos / CTA)               | CERRADO |
| STRESS-MVP | `portfolioStressRiskR` = `concurrent_stops_v0`              | CERRADO |
| OPP-V1     | `OpportunityEvidenceV1` + best-next-R (shared, read-only)   | CERRADO |

**Mensaje clave:** v1.17.1 dejó de inventar R; v1.18 **deja de colgar la tesis equivocada** a la posición, congela Package al fill, endurece copy Mesa, y sustituye el stub de Stress por una cota honesta — Opportunity queda contrato provisional, no BUY.

---

## 1. Scorecard

| Epic       | Cierra                                                  | Evidencia                                                                      |
| ---------- | ------------------------------------------------------- | ------------------------------------------------------------------------------ |
| **L1**     | Soft-join instrumento ≠ origen; orphan fail-closed      | `position-lineage` · `pickPositionStudies` · aggregate                         |
| **L2a**    | Snapshot Package al fill; protect/exit preservan        | `origin_decision_package` · `persist_position_from_fill` · `originThesis` HTTP |
| **MR-1**   | What-if ≠ gates; Datos parcial; un CTA; sin «operables» | `mesa-what-if` · `data-freshness` · `mesa-candidates`                          |
| **STRESS** | Cota concurrente cobertura completa o null              | `portfolio-risk-metrics` · chip/what-if Stress                                 |
| **OPP**    | Quality pura + best-next-R; provisional; ≠ Permission   | `opportunity-evidence.ts`                                                      |

---

## 2. Batería (local, 2026-08-27)

| Gate                                | Resultado            |
| ----------------------------------- | -------------------- |
| `pnpm --filter @bolsa/shared` build | OK                   |
| Shared DoD (9 files)                | **78** passed        |
| Web `mesa-hoy` + `mesa-position`    | **19** passed        |
| Pytest L2a dirigido                 | **19** passed        |
| `pnpm test:decision-spine`          | **497** passed       |
| Release tag CI                      | _pendiente push tag_ |

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/shared exec vitest run portfolio-risk-metrics portfolio-scenario investment-position-aggregate operational-priority mesa-next-action mesa-hoy-model opportunity-evidence position-lineage data-freshness
pnpm --filter @bolsa/web test -- mesa-hoy mesa-position
python -m pytest packages/py/application/tests/test_origin_decision_package.py packages/py/application/tests/test_persist_position_from_fill.py packages/py/application/tests/test_persist_position_from_protect.py -q
pnpm test:decision-spine
# expect: 497 passed
```

Spine: **495** (v1.17.1) → **497** (v1.18).

---

## 3. Freeze (intacto)

Confirm = firma · DEX-1…5 · `PAPER_D_EXECUTE` off · AUTO off · BETA · Scenario ≠ permiso · Ranking ≠ BUY · Opportunity ≠ Permission · Stress ≠ permiso · LLM no ejecuta.

---

## 4. Deuda restante (explícita)

| ID          | Limitación                                     | Severidad   |
| ----------- | ---------------------------------------------- | ----------- |
| STRESS-FULL | Correlación / VaR (post `concurrent_stops_v0`) | Producto    |
| OPP-UI      | Wire OpportunityEvidence → Priority UI         | Producto    |
| V118-B      | B-read Mesa / backfill legacy sin snapshot     | ADR-038     |
| LAB-B       | Backtest ≠ TradingPolicy                       | Lab         |
| THAW        | Accept estricto 60d/50/70/55                   | Deuda larga |
| AUTO-ON     | AUTO on / LIVE producción                      | Freeze      |

---

## 5. Qué **no** entra

Thaw · AUTO ON · LIVE prod · MonteCarlo/ρ · Opportunity score definitivo · Actionability v1 · `contract:gen` · pesos 35/35/30 · Primary Action mega-rediseño · Confirm/DEX.
