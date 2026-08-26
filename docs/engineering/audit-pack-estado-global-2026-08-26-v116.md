# Audit pack — estado global v1.16 (Mesa desk)

> **AsOf:** 2026-08-26 · **Tag:** **`v1.16-beta` → `42469e7`**. Partida **`v1.15-beta` → `fc2ed753`**.
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · roadmap [`roadmap-v116-mesa-desk-2026-08-26.md`](./roadmap-v116-mesa-desk-2026-08-26.md) · plan [`plan-mesa-desk-v116-v119-2026-08-26.md`](./plan-mesa-desk-v116-v119-2026-08-26.md) · ADR-037 · pack previo [`audit-pack-estado-global-2026-08-26-v113.md`](./audit-pack-estado-global-2026-08-26-v113.md).
> **Para:** auditoría externa / GitHub Actions Release tag CI · cierre de fase V1.16 Mesa desk.

---

## 0. Veredicto interno

Mesa desk V1.16–V1.19 **CERRADA en código (MD-0 + MD-1…MD-5)** sin commit ni tag: desk operativo de 20 segundos en `/mesa`, proyecciones UI sobre dominio intacto, hardening backend auditoría V1.15, **sin** tocar Confirm/DEX/SubmitIntent ni HTTP nuevo Mesa. DEX-1…DEX-5 **intactos**. Producto sigue **BETA / no producción**. Confirm = **única** firma. Accept estricto **NO**. `PAPER_D_EXECUTE` repo **OFF**. LIVE **experimental**. AUTO **off**.

| Slice | Nombre                             | Estado    |
| ----- | ---------------------------------- | --------- |
| MD-0  | Apertura + baseline                | CERRADO   |
| MD-1  | V1.16 Mesa desk (matriz + smoke)   | CERRADO\* |
| MD-2  | V1.17 Posición + ticket Confirm    | CERRADO   |
| MD-3  | V1.18 Evolución + alertas          | CERRADO   |
| MD-4  | V1.19 What-if + ranking operable   | CERRADO   |
| MD-5  | Backend paralelo (auditoría V1.15) | CERRADO\* |

\* **Limitaciones P1 declaradas:** F1-H chip DS-05 honesto (MD-1) · `sanity_warnings` E2E runtime (MD-5). Ver §4.

**Mensaje clave:** v1.15 **validó** home `/mesa`; v1.16 **endurece** semántica operativa (10 estados), ruta posición, alertas Journal, ranking operable + what-if read-only, y pytest backend (pickle/env/PAPER_D/sanity API). Tag `v1.15-beta` intacto hasta elevación owner. **No** Accept estricto. **No** default-on execute. **No** AUTO on. **No** broker producción. **No** `GET /api/mesa/today`.

---

## 1. Scorecard MD-1…MD-5

| Slice    | Cierra                                                                                      | Evidencia principal                                                                         | Spine   |
| -------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------- |
| **MD-1** | Matriz semántica 10 estados · cabecera operativa · FeatureErrorBoundary · smoke browser 5/5 | `mesa-next-action` · `mesa-protection` · `mesa-hoy` · relevo v116                           | —       |
| **MD-2** | `showRoute` Mesa · invalidación qty/precio F3 · ticket riesgo primero                       | `mesa-position-row` · `f3-risk-input-baseline` · `supervised-f3-panel`                      | —       |
| **MD-3** | Deltas Journal relevantes · alertas decisión · orden ADR-037                                | `decision-journal-relevant-delta` · `mesa-decision-alerts-panel` · `mesa-hoy-page`          | —       |
| **MD-4** | Ranking operable · what-if read-only · tests `projectMesaWhatIf`                            | `mesa-operable-ranking.test.ts` · `mesa-what-if-panel`                                      | —       |
| **MD-5** | Pickle SHA256 · prod allowlist · `PAPER_D_EXECUTE` Router · sanity→DS-05 API · EdgeReport   | pytest 72 · `test_lightgbm_checksum` · `test_sanity_opening_veto` · `test_execution_router` | **485** |

Matriz MD-1 (mapper + UI):

```text
WATCH / sin plan     → sin SL/TP operativo; copy plan
ARMED                → plan visible; sin CTA Confirm
TRIGGERED            → Revisar propuesta
BLOCKED / incidente  → entradas bloqueadas
EXPIRED              → no operable
OPEN + hold          → Mantener
protect_hint         → Proteger; no Confirmada
persist skipped      → Discrepancia en Atención
NO TRADE / 0 listos  → sesión sin operaciones
query incidentes err → fail-closed (≠ banner 0)
```

---

## 2. Batería (local, pre-tag / 2026-08-26)

| Gate                       | Resultado                                                       |
| -------------------------- | --------------------------------------------------------------- |
| `pnpm test:decision-spine` | **485** passed                                                  |
| Mesa shared + web          | shared 34+ (mesa) · web 11 (mesa-hoy) · ver relevos MD-1/3      |
| Backend F5 pytest          | **72** passed (suite MD-5)                                      |
| Release tag CI             | `release-tag-ci.yml` — al pushear tag `v1.16-beta` (post-owner) |

```bash
pnpm test:decision-spine
# expect: 485 passed

python -m pytest \
  packages/py/analytics/tests/test_lightgbm_checksum.py \
  packages/py/infrastructure/tests/test_config_production.py \
  packages/py/market/tests/test_sanity_opening_veto.py \
  packages/py/application/tests/test_execution_router.py \
  packages/py/application/tests/test_risk_engine.py \
  packages/py/application/tests/test_paper_d_propose.py \
  packages/py/application/tests/test_paper_auto_http_gate.py \
  packages/py/analytics/tests/test_lab_edge_report.py \
  apps/api-python/tests/test_auth.py -q
# expect: 72 passed
```

Spine progression V1.16: **483** (v1.13) → **485** (Mesa desk + backend tests).

---

## 3. Qué entra en el tag (cuando el owner lo pida)

- **MD-1:** Cabecera operativa · `mapMesaNextAction` · PLAN/PROPUESTA/EJECUTADO · FeatureErrorBoundary · matriz tests 10 estados · smoke browser documentado.
- **MD-2:** `PositionRoutePanel` cableado en `/mesa` · `f3-risk-input-baseline` + aviso inputs stale · subcomponentes F3 auditables.
- **MD-3:** `buildMesaDecisionAlerts` · deltas relevantes Journal · copy «¿Por qué cambió?» · orden visual ADR-037.
- **MD-4:** `sortMesaCandidatesOperable` · `projectMesaWhatIf` read-only · copy `No operable: …`.
- **MD-5:** Pickle checksum · `is_production_environment()` · `PAPER_D_EXECUTE` en `Router.execute` · `PAPER_D_ACCOUNT_ID` fail-closed · EdgeReport denominador · sanity→DS-05 helper API · `require_role` en CURRENT_SYSTEM.
- ADR-037 extensiones V1.16–V1.19 · roadmap v116 · pack v116 · relevos MD-1…MD-5. DEX-1…DEX-5 / OR-1/3/4/5/6 **intactos**.

---

## 4. Qué no entra / parked (candidatas post-v1.16)

| Excluido / parked                         | Severidad | Notas                                                                       |
| ----------------------------------------- | --------- | --------------------------------------------------------------------------- |
| **F1-H chip DS-05 honesto**               | **P1**    | Header + ops-self-eval — sin verde por omisión; API sanity lista            |
| **`sanity_warnings` E2E runtime**         | **P1**    | `check_opening(..., sanity_warnings=...)` API OK; Confirm/Router sin wiring |
| **What-if gates reales**                  | **P2**    | Proyección aritmética read-only; Confirm = única firma                      |
| **`showRoute` en Libro** (`/operaciones`) | **P1**    | Solo `/mesa` vía `MesaPositionsSummary`; unificar componente post-tag       |
| `GET /api/mesa/today`                     | —         | Fuera v1.16-beta (plan §6)                                                  |
| Backtest = TradingPolicy                  | P3        | Fundación only; pack propio                                                 |
| Accept estricto P1–P5                     | Deuda     | DoD runbook §4 + palabra **thaw**                                           |
| `PAPER_D_EXECUTE` default on              | —         | Opt-in local; repo **off**                                                  |
| AUTO on / AUTO como modalidad             | —         | Confirm = firma                                                             |
| Redis multi-worker SubmitIntent           | Parked    |                                                                             |
| LIVE trading accepted / XTB capital       | —         | LIVE experimental only                                                      |
| Reabrir DEX-1…5 u OR a ciegas             | —         | No                                                                          |

---

## 5. Cadena de autoridad

```text
CURRENT_SYSTEM → ADR-037 (Mesa desk) → código → tests → HELP

Confirm SEMI = firma
Proyección UI (mapMesaNextAction, ranking, what-if) ≠ permiso operativo
DEX-1…DEX-5 intactos · Incident lifecycle sin auto-heal
What-if = informativo; no re-evalúa TradePlan / check_opening / firma riesgo
Venue: memory ?? redis ?? account ?? env ?? paper
```

---

## 6. Freeze (v1.16)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · ExitPlan ≠ auto-exit · Confirm = firma · thin 5.x/8.x congelados · I1–I3 + RX1 · OI-1…OE-1 **no se reabren** · OR-1/3/4/5/6 **no se reabren** · DEX-1…DEX-5 **no se reabren** a ciegas · `PAPER_D_EXECUTE` **off** · mesa default **paper** · LIVE experimental · Accept estricto **parked** · AUTO **off** · sin HTTP nuevo Mesa · **BETA / no producción**.

---

## 7. Docs clave (lectura auditor)

| Tipo       | Documento                                                                                              |
| ---------- | ------------------------------------------------------------------------------------------------------ |
| SoT vivo   | [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)                                                            |
| Contrato   | [`037-mesa-hoy-operational-ux.md`](../adr/037-mesa-hoy-operational-ux.md)                              |
| Integridad | [`035-operational-reliability.md`](../adr/035-operational-reliability.md) (DEX intacto)                |
| Roadmap    | [`roadmap-v116-mesa-desk-2026-08-26.md`](./roadmap-v116-mesa-desk-2026-08-26.md)                       |
| Plan       | [`plan-mesa-desk-v116-v119-2026-08-26.md`](./plan-mesa-desk-v116-v119-2026-08-26.md)                   |
| Relevo tag | [`traspaso-relevo-tag-v1-16-beta-2026-08-26.md`](./traspaso-relevo-tag-v1-16-beta-2026-08-26.md)       |
| MD-1       | [`traspaso-relevo-mesa-desk-v116-2026-08-26.md`](./traspaso-relevo-mesa-desk-v116-2026-08-26.md)       |
| MD-2       | [`traspaso-relevo-mesa-desk-v117-2026-08-26.md`](./traspaso-relevo-mesa-desk-v117-2026-08-26.md)       |
| MD-3       | [`traspaso-relevo-mesa-desk-v118-2026-08-26.md`](./traspaso-relevo-mesa-desk-v118-2026-08-26.md)       |
| MD-4       | [`traspaso-relevo-mesa-desk-v119-2026-08-26.md`](./traspaso-relevo-mesa-desk-v119-2026-08-26.md)       |
| MD-5       | [`traspaso-relevo-mesa-desk-backend-2026-08-26.md`](./traspaso-relevo-mesa-desk-backend-2026-08-26.md) |
| Pack prev. | [`audit-pack-estado-global-2026-08-26-v113.md`](./audit-pack-estado-global-2026-08-26-v113.md)         |
| Thaw deuda | [`deuda-thaw-estricto-runbook-2026-08-25.md`](./deuda-thaw-estricto-runbook-2026-08-25.md)             |

---

## 8. Checklist auditor (E1)

1. Checkout commit owner (post-tag: **`v1.16-beta` → SHA TBD**).
2. Verificar GitHub Actions **`release-tag-ci.yml`** GREEN en el push del tag.
3. Ejecutar `pnpm test:decision-spine` → esperar **485** passed.
4. Ejecutar suite pytest MD-5 (§2) → esperar **72** passed.
5. Contrastar ADR-037 + relevos MD-1…MD-5 con código: matriz semántica, alertas, ranking, what-if read-only, backend hardening.
6. Confirmar freeze §6: sin Accept estricto, sin default-on, sin AUTO on, mesa paper, Confirm = firma, LIVE experimental, sin HTTP nuevo Mesa.
7. Verificar limitaciones §4 declaradas (no ocultas): chip DS-05 P1 · sanity E2E P1 · what-if sin gates · Libro sin `showRoute`.
8. Opcional SEMI UI: TRIGGERED → Confirm → CTA `Ejecutar en PAPER` · DEX-2/3/5 en spine.
9. Emitir triage/findings si aplica (candidatas §4).

**Preguntas que este pack no resuelve:** Accept estricto · default-on · AUTO on · gates reales what-if · sanity E2E · chip DS-05 honesto · Libro showRoute · `GET /api/mesa/today` · backtest TradingPolicy · thaw.
