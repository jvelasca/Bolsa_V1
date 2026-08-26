# Roadmap — v1.11 Operational Integrity

> **Padre:** ADR-034 · auditorías post-v1.10 · [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md).
> **AsOf:** 2026-08-26.
> **Partida:** `v1.10-beta` → `047ddb6`.

---

## Secuencia

| Slice          | Nombre                  | Qué                                                                     | Estado      |
| -------------- | ----------------------- | ----------------------------------------------------------------------- | ----------- |
| **OI-1**       | Continuidad post-fill   | Manual/pending/Confirm/Lab/protect alinean ledger ↔ PositionState       | **CERRADO** |
| **OI-2**       | Risk signature honesty  | `no_plan` fail-closed en contexto recomendado SEMI                      | **CERRADO** |
| **OI-3**       | ExecutionRecord         | UNKNOWN ≠ ERROR; nunca confundir excepción con no-ejecutado             | **CERRADO** |
| **OI-4**       | Order lifecycle paper   | CREATED→FILLED antes de broker                                          | **CERRADO** |
| **OI-5**       | Position revisions      | Historia auditada de stop/transiciones                                  | **CERRADO** |
| **OI-6**       | Reconciliation          | Ledger ↔ Orders ↔ Fills ↔ Position ↔ Cash                               | **CERRADO** |
| **PB-1**       | PaperBroker             | Venue PAPER antes de BrokerAdapter                                      | **CERRADO** |
| **BA-1**       | BrokerAdapter           | Puerto Paper \| Live; mock `not_wired`                                  | **CERRADO** |
| **PH-1**       | Confirm protect honesty | persist None ≠ `protect_applied`                                        | **CERRADO** |
| **XL-1**       | Broker live XTB         | Adapter + bridge; submitted ≠ fill; fail-closed                         | **CERRADO** |
| **LR-1**       | Live reconciliation     | Live↔ledger detect/report; no heal                                      | **CERRADO** |
| **XL-2**       | XTB fill → ledger       | `filled` → `execute_trade`; submitted ≠ fill                            | **CERRADO** |
| **VS-1**       | Venue selector          | Paper \| Live DI + mesa; default paper                                  | **CERRADO** |
| **RV-1**       | Redis venue             | Key `bolsa:risk:broker_venue`; coalesce memory ?? redis ?? env ?? paper | **CERRADO** |
| **JP-1**       | JSONB → columnas        | Alembic `012` dual-write; JSONB SoT                                     | **CERRADO** |
| **Thaw stamp** | `PAPER_D_EXECUTE`       | DEMO opt-in autorizado; default repo OFF (docs/ops)                     | **CERRADO** |
| **PA-1**       | Per-account venue       | `settings_json.brokerVenue`; lazy Confirm/Fill; global override mesa    | **CERRADO** |
| **OE-1**       | Ops Autoeval            | Scorecard SEMI+AUTO read-only (`/risk/ops-self-eval` + mesa chip)       | **CERRADO** |

Después: pack + tag **`v1.11-beta`** (hecho) · **v1.12 Operational Reliability** ([`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md) · OR-1) · thaw **estricto** Accept (deuda; DoD + palabra) · remasure W+2 docs **cerrado** ([`traspaso-relevo-thaw-estricto-remeasure-2026-08-26.md`](./traspaso-relevo-thaw-estricto-remeasure-2026-08-26.md)) · UI preferencia cuenta (OR-6).

---

## OI-1 (cerrado)

Ver [`plan-oi1-continuity-2026-08-26.md`](./plan-oi1-continuity-2026-08-26.md) · relevo [`traspaso-relevo-oi1-continuity-2026-08-26.md`](./traspaso-relevo-oi1-continuity-2026-08-26.md).

Spine `pnpm test:decision-spine` — **367** (post-OE-1 / v1.11 pre-tag).

## OI-2 (cerrado)

Ver [`plan-oi2-risk-signature-honesty-2026-08-26.md`](./plan-oi2-risk-signature-honesty-2026-08-26.md) · relevo [`traspaso-relevo-oi2-risk-signature-2026-08-26.md`](./traspaso-relevo-oi2-risk-signature-2026-08-26.md).

## OI-3 (cerrado)

Ver [`plan-oi3-execution-record-2026-08-26.md`](./plan-oi3-execution-record-2026-08-26.md) · relevo [`traspaso-relevo-oi3-execution-record-2026-08-26.md`](./traspaso-relevo-oi3-execution-record-2026-08-26.md).

## OI-4 (cerrado)

Ver [`plan-oi4-order-lifecycle-2026-08-26.md`](./plan-oi4-order-lifecycle-2026-08-26.md) · relevo [`traspaso-relevo-oi4-order-lifecycle-2026-08-26.md`](./traspaso-relevo-oi4-order-lifecycle-2026-08-26.md).

## OI-5 (cerrado)

Ver [`plan-oi5-position-revisions-2026-08-26.md`](./plan-oi5-position-revisions-2026-08-26.md) · relevo [`traspaso-relevo-oi5-position-revisions-2026-08-26.md`](./traspaso-relevo-oi5-position-revisions-2026-08-26.md).

## OI-6 (cerrado)

Ver [`plan-oi6-reconciliation-2026-08-26.md`](./plan-oi6-reconciliation-2026-08-26.md) · relevo [`traspaso-relevo-oi6-reconciliation-2026-08-26.md`](./traspaso-relevo-oi6-reconciliation-2026-08-26.md).

## PB-1 PaperBroker (cerrado)

Ver [`plan-paperbroker-2026-08-26.md`](./plan-paperbroker-2026-08-26.md) · relevo [`traspaso-relevo-paperbroker-2026-08-26.md`](./traspaso-relevo-paperbroker-2026-08-26.md).

## BA-1 BrokerAdapter (cerrado)

Ver [`plan-brokeradapter-2026-08-26.md`](./plan-brokeradapter-2026-08-26.md) · relevo [`traspaso-relevo-brokeradapter-2026-08-26.md`](./traspaso-relevo-brokeradapter-2026-08-26.md).

## PH-1 Confirm protect honesty (cerrado)

Ver [`plan-confirm-protect-honesty-2026-08-26.md`](./plan-confirm-protect-honesty-2026-08-26.md) · relevo [`traspaso-relevo-confirm-protect-honesty-2026-08-26.md`](./traspaso-relevo-confirm-protect-honesty-2026-08-26.md).

## XL-1 Broker live XTB (cerrado)

Ver [`plan-broker-live-xtb-2026-08-26.md`](./plan-broker-live-xtb-2026-08-26.md) · relevo [`traspaso-relevo-broker-live-xtb-2026-08-26.md`](./traspaso-relevo-broker-live-xtb-2026-08-26.md).

## LR-1 Live reconciliation (cerrado)

Ver [`plan-lr1-live-reconciliation-2026-08-26.md`](./plan-lr1-live-reconciliation-2026-08-26.md) · relevo [`traspaso-relevo-lr1-live-reconciliation-2026-08-26.md`](./traspaso-relevo-lr1-live-reconciliation-2026-08-26.md).

## XL-2 XTB fill → ledger (cerrado)

Ver [`plan-xl2-xtb-fill-ledger-2026-08-26.md`](./plan-xl2-xtb-fill-ledger-2026-08-26.md) · relevo [`traspaso-relevo-xl2-xtb-fill-ledger-2026-08-26.md`](./traspaso-relevo-xl2-xtb-fill-ledger-2026-08-26.md).

## VS-1 Venue selector (cerrado)

Ver [`plan-vs1-venue-selector-2026-08-26.md`](./plan-vs1-venue-selector-2026-08-26.md) · relevo [`traspaso-relevo-vs1-venue-selector-2026-08-26.md`](./traspaso-relevo-vs1-venue-selector-2026-08-26.md).

## RV-1 Redis venue (cerrado)

Ver [`plan-rv1-redis-venue-2026-08-26.md`](./plan-rv1-redis-venue-2026-08-26.md) · relevo [`traspaso-relevo-rv1-redis-venue-2026-08-26.md`](./traspaso-relevo-rv1-redis-venue-2026-08-26.md).

## JP-1 Position JSONB columns (cerrado)

Ver [`plan-jp1-position-jsonb-columns-2026-08-26.md`](./plan-jp1-position-jsonb-columns-2026-08-26.md) · relevo [`traspaso-relevo-jp1-position-jsonb-columns-2026-08-26.md`](./traspaso-relevo-jp1-position-jsonb-columns-2026-08-26.md).

## Thaw stamp `PAPER_D_EXECUTE` (cerrado — docs/ops)

Ver [`plan-thaw-paper-d-execute-stamp-2026-08-26.md`](./plan-thaw-paper-d-execute-stamp-2026-08-26.md) · relevo [`traspaso-relevo-thaw-paper-d-execute-2026-08-26.md`](./traspaso-relevo-thaw-paper-d-execute-2026-08-26.md). DEMO opt-in autorizado; default OFF; ≠ venue Live; ≠ estricto P1–P5.

## PA-1 Per-account venue (cerrado)

Ver [`plan-pa1-per-account-venue-2026-08-26.md`](./plan-pa1-per-account-venue-2026-08-26.md) · relevo [`traspaso-relevo-pa1-per-account-venue-2026-08-26.md`](./traspaso-relevo-pa1-per-account-venue-2026-08-26.md). Preferencia `settings_json.brokerVenue`; coalesce memory ?? redis ?? account ?? env ?? paper; lazy Confirm/Fill; mesa global intacta. **No** thaw.

## OE-1 Ops Autoeval (cerrado)

Ver [`plan-oe1-ops-autoeval-2026-08-26.md`](./plan-oe1-ops-autoeval-2026-08-26.md) · relevo [`traspaso-relevo-oe1-ops-autoeval-2026-08-26.md`](./traspaso-relevo-oe1-ops-autoeval-2026-08-26.md) · checklist [`ops-autoeval-checklist-2026-08-26.md`](./ops-autoeval-checklist-2026-08-26.md). `GET /api/risk/ops-self-eval` + script + chip mesa. Measure ≠ Accept · recon OI-6 `not_wired`.
