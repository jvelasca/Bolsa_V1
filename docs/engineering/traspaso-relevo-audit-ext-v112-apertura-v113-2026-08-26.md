# RELEVO — Auditoría v1.12 CERRADA · apertura V1.13 Durable Execution · 2026-08-26

> **Padre:** [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md).
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.12-beta` → `369b5d1`**. Spine **433**.
> **Estado:** **D0 CERRADO (docs).** **DEX-1 CERRADO** — ver [`traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md`](./traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md). Histórico de apertura V1.13.
> **Arranque chat nuevo (histórico):** este fichero + plan DEX-1 + ADR-035 + roadmap v1.13. **Next = DEX-2.**

---

## 0. Por qué cambiar de chat

La auditoría externa de v1.12 **ratifica** OR-1/3/4/5/6 y marca **OR-2 PARTIAL**: concepto `DurableSubmitIntent` correcto, store InMemory **no sobrevive al PID**. El siguiente trabajo es **otra fase**: Durable Execution v1.13, empezando por **DEX-1** (código Alembic + PG store). No mezclar DEX-2 kill-process ni Incident en el mismo chat.

## 1. Qué quedó hecho (este stamp)

| Pieza                           | Estado                                            |
| ------------------------------- | ------------------------------------------------- |
| Triage ext durable post-v1.12   | RATIFICADO — congelar · cerrar OR-2 físico        |
| OR-2 docs → PARTIAL             | Hecho — tag v1.12-beta intacto                    |
| Roadmap v1.13                   | ABIERTO — D0 hecho · DEX-1+ no abiertos en código |
| Nota ADR-035 post-audit         | Hecho                                             |
| Plan DEX-1                      | ABIERTO — D1–D8 + DoD                             |
| Código DEX-1 (tabla PG / store) | **No**                                            |
| Pack auditor v113               | **No** (al tag)                                   |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. Thaw estricto **deuda**. AUTO **off**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OR-1/3/4/5/6 **no se reabren** a ciegas.
- Auto-exit **no** es CTA cotidiano. **No** más brokers.
- JSONB PositionState SoT · `position_revisions` parked.

## 3. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** implementar **DEX-1** citando plan + ADR-035. Alembic `013_submit_intents` · `PostgresSubmitIntentStore` · fases `send_attempted` · DI Confirm. Cero DEX-2 kill · cero Incident · cero Confirm split.
2. **Opción B:** operar SEMI con v1.12 (TRIGGERED → Confirm → `Ejecutar en PAPER`). No reabrir thin. No XTB capital.
3. **Opción C:** owner — tag ya existente `v1.12-beta`. No bloquea DEX-1.
4. **No** DEX-3 Incident, **no** DEX-4 Confirm split, **no** DEX-5 property suite, **no** pack auditor v113 en el mismo chat que DEX-1.

## 4. Docs clave

- [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md)
- [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md)
- [`plan-dex1-pg-submit-intents-2026-08-26.md`](./plan-dex1-pg-submit-intents-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
- Pack v1.12: [`audit-pack-estado-global-2026-08-26-v112.md`](./audit-pack-estado-global-2026-08-26-v112.md)
