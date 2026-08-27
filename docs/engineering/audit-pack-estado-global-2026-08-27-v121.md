# Audit pack — estado global v1.21 (Operational Coherence & UX Hardening)

> **AsOf:** 2026-08-27 · **Tag (stamp):** **`v1.21-beta` → `dad8f51c`**. Partida **`v1.20-beta` → `4c0bfe7b`**.
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-041](../adr/041-operational-coherence.md) · [ADR-040](../adr/040-user-information-architecture.md) §7 · pack previo [`audit-pack-estado-global-2026-08-27-v120.md`](./audit-pack-estado-global-2026-08-27-v120.md).
> **Para:** auditoría cruzada post-v1.21 · Release tag CI [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33095441423).

---

## 0. Veredicto interno

Ciclo **V1.21** **CERRADO** (coherencia operativa diaria + UX hardening). **No** añade motores, OpportunityScore, correlación/VaR, thaw ni AUTO. Alinea **universo Diario = Estudio**, **una proyección de plan operativo**, **un stop vigente**, **AdminRail ≠ ⚙**, higiene de cuentas y **trailing advisory** (thin; no autoridad). DEX-1…DEX-5 **intactos**. Confirm = **única** firma. `PAPER_D_EXECUTE` **OFF**. AUTO **off**. Ranking ≠ BUY. Producto **BETA**.

| Epic        | Nombre                                                            | Estado  |
| ----------- | ----------------------------------------------------------------- | ------- |
| B1 Universo | Estudio = Daily Ops (funnel/ranking/scan default)                 | CERRADO |
| B2 Plan     | `OperationalPlanView` shared + UI (Hoy / drawer / PositionRoute)  | CERRADO |
| B3/B4 Stop  | Stop vigente = `currentStop` · T1 idempotente `target1AchievedAt` | CERRADO |
| AdminRail   | Overview/Cuentas/Fiscal/Consola fuera de ⚙ · ADR-040 §7           | CERRADO |
| B6 Cuentas  | Origen seed/user/lab · selector diario · cerrar extras OP-08      | CERRADO |
| Trail UI    | `mapTrailPlan` → trailing peak/stop/distancia (advisory)          | CERRADO |

**Mensaje clave:** v1.20 separó arquitectura de usuario; v1.21 hace coherente el **ciclo operativo** (recomendar → entrar → posición → SL/T1/T2/trail) sin promocionar thin a autoridad.

---

## 1. Scorecard

| Epic          | Cierra                                        | Evidencia                                                               |
| ------------- | --------------------------------------------- | ----------------------------------------------------------------------- |
| **Universo**  | Solo Estudio en Daily Ops; fuera = discovered | `opportunity-ranking.ts` · `mesa-candidates-panel` · UNIVERSE-001/002   |
| **Plan view** | Una proyección visual del plan                | `operational-plan-view.ts` · `operational-plan-view.tsx`                |
| **Stop/T1**   | Un stop vigente · T1 no se re-emite           | `position-state` · `exit-plan` · OP-03/04/05                            |
| **Admin**     | AdminRail ≠ preferencias                      | `admin-rail.tsx` · ADR-040 §7 · ADR-041                                 |
| **Cuentas**   | Seed nunca en bulk close · paper no bulk      | `accounts.ts` `listCloseableDevExtraAccounts` · OP-08 · `accounts-page` |
| **Trailing**  | tip/ratchet visible; no escribe `currentStop` | `mapTrailPlan` · `buildOperationalPlanFromPosition` · test ratchet      |

---

## 2. Batería (local, 2026-08-27)

| Gate                          | Resultado                                |
| ----------------------------- | ---------------------------------------- |
| `@bolsa/shared` build         | OK                                       |
| Web `tsc --noEmit`            | OK                                       |
| Suites V1.21 (shared + web)   | OK                                       |
| `pnpm test:daily-ops:offline` | **1159** (6 fases: 366+92+121+50+497+33) |
| `pnpm test:decision-spine`    | **497**                                  |

```bash
pnpm --filter @bolsa/shared build
pnpm --filter @bolsa/web exec tsc --noEmit
pnpm --filter @bolsa/shared exec vitest run src/cognitive/opportunity-ranking.test.ts src/exit-plan.test.ts src/position-state.test.ts src/accounts-origin.test.ts src/cognitive/operational-plan-view.test.ts
pnpm --filter @bolsa/web exec vitest run src/features/mesa/mesa-candidates-panel.test.ts src/features/mesa/mesa-zone1-redirects.test.ts src/components/layout/admin-rail.test.ts
python -m pytest packages/py/application/tests/test_opportunity_daily_discovery.py packages/py/analytics/tests/test_exit_plan.py packages/py/analytics/tests/test_position_state.py -q
pnpm test:daily-ops:offline
pnpm test:decision-spine
# expect: daily-ops ≥1145 (ahora 1159) · spine 497
```

Manifest: `scripts/research/daily-ops-manifest.mjs`.

---

## 3. Freeze (intacto)

Confirm = firma · DEX-1…5 · `PAPER_D_EXECUTE` off · AUTO off · BETA · Scenario ≠ permiso · Ranking ≠ BUY · Opportunity ≠ Permission · Stress ≠ permiso · Decision Board ≠ screener · LLM no ejecuta · LAB ≠ TRADING · trailing thin ≠ autoridad de stop · OpportunityScore aparcado.

---

## 4. Deuda restante (explícita)

| ID          | Limitación                                | Severidad   |
| ----------- | ----------------------------------------- | ----------- |
| OPP-SCORE   | OpportunityScore multiplicativo (backlog) | Producto    |
| OPP-ENGINE  | Análisis TA+FA universo amplio            | Producto    |
| STRESS-FULL | Correlación / VaR                         | Producto    |
| V118-B      | B-read Mesa / backfill legacy             | ADR-038     |
| LAB-B       | Backtest ≠ TradingPolicy                  | Lab         |
| THAW        | Accept estricto 60d/50/70/55              | Deuda larga |
| AUTO-ON     | AUTO on / LIVE producción                 | Freeze      |

---

## 5. Qué **no** entra

OpportunityScore · correlación/VaR · thaw · AUTO on · nuevas puertas L1 · barras Hoy en Trading · borrar `default-account-seed` · auto-exit · promocionar trail a `currentStop` · `contract:gen`.

---

## 6. Focos para auditor externo

1. ¿Estudio es el **único** universo Daily Ops (TOP/BUY diario)?
2. ¿Hay **un** stop vigente = `currentStop` (no rivales en UI)?
3. ¿AdminRail ≠ ⚙ (preferencias)?
4. ¿T1 es idempotente (`target1AchievedAt`)?
5. ¿Freeze SEMI intacto (Confirm firma · trail solo propuesta)?
