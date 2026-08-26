# RELEVO — OI-5 Position revisions · 2026-08-26

> **Padre:** [`plan-oi5-position-revisions-2026-08-26.md`](./plan-oi5-position-revisions-2026-08-26.md) · ADR-034 §6.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO (código + tests).**

---

## Qué quedó hecho

| Pieza                                                    | Estado    |
| -------------------------------------------------------- | --------- |
| `PositionRevision` Python + TS (append-only)             | **Hecho** |
| `PositionState.revisions[]` en snapshot JSON             | **Hecho** |
| `applyCurrentStop` / `applyReduce` append si cambio real | **Hecho** |
| Persist protect → `origin=protect`; exit → `reduce`      | **Hecho** |
| Mark sin revisión; from_fill `revisions=[]`              | **Hecho** |
| HELP Hoy + docs ADR-034 / CURRENT_SYSTEM                 | **Hecho** |
| Tests factory + protect + spine **306** · shared **179** | **Hecho** |

## Siguiente chat

1. **PaperBroker** (capa paper antes de BrokerAdapter), **o**
2. Edge parked: Confirm `protect_applied` si H2/`persist` → `None` (honesty UI).

OI-6 cerrado: [`traspaso-relevo-oi6-reconciliation-2026-08-26.md`](./traspaso-relevo-oi6-reconciliation-2026-08-26.md) · spine **317**.

**No** broker live en el mismo chat que PaperBroker.

## Sesión 2026-08-26

- **OI-1** continuidad post-fill.
- **OI-2** risk signature honesty.
- **OI-3** ExecutionRecord: excepción de envío ≠ no-ejecutado.
- **OI-4** PaperOrder: CREATED→FILLED paper antes de broker.
- **OI-5** PositionRevision: historia auditada stop/status.

## Docs

- Plan OI-5 · roadmap v1.11 · CURRENT_SYSTEM stamp OI-1…OI-5
- Relevo OI-4: [`traspaso-relevo-oi4-order-lifecycle-2026-08-26.md`](./traspaso-relevo-oi4-order-lifecycle-2026-08-26.md)
