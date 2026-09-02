# Relevo — V1.73 Multi-instrument integrity

> **AsOf:** 2026-09-02 · **Estado:** CERRADA (código + E2E mock locales) · **Auditor:** [`arranque-auditor-v1-73-multi-instrument-integrity-2026-09-02.md`](./arranque-auditor-v1-73-multi-instrument-integrity-2026-09-02.md) · **Partida:** V1.72 local / V1.71 `b70849bd`

## Hecho

- Fixture multi: `ensureMultiInstrumentMercadoFixture` (≥3 buys PAPER + Entry-only 4º si catálogo) · mocks AAPL/MSFT/GOOGL + NVDA
- GP-V173-01 A→B→C→A identidad chart+cockpit+positionId
- GP-V173-02 refresh con re-seed workspace del foco
- GP-V173-03 Position ↔ Entry vía dual chart + study ARMED mock; Cartera restaura Position
- Mock `/api/instruments/quotes` → **array** (antes objeto → crash ListValuesPanel)
- Specs: `gp-v173-multi-instrument-mock.spec.ts` · `gp-v173-multi-instrument-integrated.spec.ts`

## Reservas

- Playwright integrado **opt-in** (API+PG+`E2E_ALLOW_DEV_DB=1`); Entry integrado acepta `entry-decision-surface` **o** `operativa-cockpit-no-levels` (sin study ARMED en API)
- Certificación de cierre = **mock 3/3**; integrado serial/workers=1 pendiente de verde estable en entorno local (cuenta Activa ↔ Cartera count)
- **No** stamp CI GREEN
- V1.72+V1.73 aún **sin commit** en tip GitHub si el owner no lo pidió

## Next candidato

**Paper Autonomous Day (V1.74)** · stale→no-execute / chaos (**V1.75**) · bump package · **NO LIVE**.
