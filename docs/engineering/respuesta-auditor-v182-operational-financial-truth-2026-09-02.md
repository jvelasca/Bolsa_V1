# Respuesta auditor — V1.82 (Operational / Financial Truth) (2026-09-02)

> **Padre:** [`arranque-auditor-v1-82-beta-2026-09-02.md`](./arranque-auditor-v1-82-beta-2026-09-02.md) · [`traspaso-relevo-tag-v1-82-beta-2026-09-02.md`](./traspaso-relevo-tag-v1-82-beta-2026-09-02.md).  
> **Tip auditado:** `v1.82-beta` → [`d0ccf235`](https://github.com/jvelasca/Bolsa_V1/commit/d0ccf235) · CI GREEN [run 33651647262](https://github.com/jvelasca/Bolsa_V1/actions/runs/33651647262).  
> **Siguiente slice:** [`spec-v183-lifecycle-snapshot-truth-2026-09-02.md`](./spec-v183-lifecycle-snapshot-truth-2026-09-02.md).

## Veredicto

**V1.82 = 9,75 / 10** · **P0 = 0** · **P1 = 3** · **P2 ≈ 5**.

La arquitectura no se rediseña. El riesgo residual está en la **fidelidad del modelo de lifecycle** respecto a la historia operativa acumulada, no en tesis ≠ plan ≠ permiso ≠ orden ≠ fill.

CI GREEN real (security · shared · spine · frontend · python · playwright-mock · certify). Integrated E2E sigue **opt-in / skipped**. Certificación = mock stack, no FastAPI+PG+browser.

## Qué V1.82 (y el arco) ya resolvió

- V1.79: journey stateful AAPL (candidato→CLOSED) con aserciones Identity / Financial / Operational / Certification.
- V1.80: stamp CI GREEN remoto (`playwright-mock` curado).
- V1.81: T2_READY / T2_EXECUTED · MONITOR/Mantener intencional · 0 COMPRAR.
- V1.82: split fixtures (`runtime` / `routes` / `installers` + barrel) sin romper semántica.

## P1 (hacer en V1.83)

1. **Lineage monotónica** — `applyGoldenPositionStage` reconstruía `EXIT_REQUIRED` / `CLOSED` borrando T1/T2, `stopHistory`, `revisions` y `events`. CLOSED debe conservar historia y añadir `POSITION_CLOSED`.
2. **Invariantes financieras** — `assertFinancialTruth` valida HUD, no `marketValue = lastPrice × qty`, PnL, R = PnL / initialRisk, `0 ≤ remaining ≤ birthQty`.
3. **Un LifecycleSnapshot** — `/portfolio` y `/summary` (y desk/journal/POV) no pueden inventar `totalEquity` distinto.

Limitación nombrada (no P1 de producto): el test sigue siendo **Stateful Projection** (`setStage` → fabricar DTO), no ejecución por eventos. Event-driven = P2.

## P2 (aparcar)

- Semántica `/portfolio.positions`: open-only vs open+closed (hoy incluye CLOSED qty 0; documentar, no cambiar).
- E2E event-driven (`POST` T1_EXECUTED → persist → GET).
- Un Golden Journey integrado FastAPI+PG+Playwright (opt-in hoy).
- Revisar UX T2_READY → Mantener (intencional, no bug).
- Inconsistencias menores de mock no-lifecycle.

## Next

Fase **Operational / Financial Truth Certification** (mock): Snapshot → transiciones proyectadas con historia → invariantes → (más tarde) un integrated golden journey. **No LIVE.**
