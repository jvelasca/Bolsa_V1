# RELEVO — DEX-3 OperationalIncident · apertura DEX-4 · 2026-08-26

> **Padre:** [`plan-dex3-operational-incident-2026-08-26.md`](./plan-dex3-operational-incident-2026-08-26.md) · ADR-035 · roadmap v1.13.
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.12-beta` → `369b5d1`**. Spine **440 → 463**.
> **Estado:** **DEX-3 CERRADO** (código + tests + docs). Next = **DEX-4**.
> **Arranque chat nuevo:** este fichero + plan DEX-3 + ADR-035 + roadmap v1.13 + `CURRENT_SYSTEM.md`.

---

## 0. Por qué cambiar de chat

DEX-3 cierra el hueco humano de recon: drift → `OperationalIncident` OPEN → review → resolve (nota, sin auto-heal) → clear solo si recon `clean`. El siguiente hueco del auditor es **Confirm = orquestador** (DEX-4). No mezclar property suite (DEX-5) ni pack v113 en el mismo chat.

## 1. Qué quedó hecho

| Pieza                                            | Estado              |
| ------------------------------------------------ | ------------------- |
| Kernel `OperationalIncident` + espejo TS         | **Hecho**           |
| Store InMemory + PG + Alembic `014`              | **Hecho**           |
| Drift → INC único por kind · resolve/clear       | **Hecho**           |
| Opening veto `incident:unresolved` · exits ALLOW | **Hecho**           |
| Confirm / Fill / HTTP / Router DI                | **Hecho**           |
| Spine ancla `test_dex3_operational_incident.py`  | **Hecho** · **463** |
| DEX-4 Confirm split · DEX-5 · pack v113          | **No**              |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. Thaw estricto **deuda**. AUTO **off**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OR-1/3/4/5/6 **no se reabren** a ciegas.
- Auto-exit **no** es CTA cotidiano. **No** más brokers.
- JSONB PositionState SoT · `position_revisions` parked. Redis multi-worker **parked**.
- Mesa UI banner / HTTP resolución = candidata posterior (no en DEX-4).

## 3. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** implementar **DEX-4** — Confirm = orquestador (extraer coordinators Identity / RiskGate / OpeningGate / ExitGate / Execution / SubmitIntent / PositionSync). Citar plan DEX-3 + ADR-035. Cero property suite · cero pack v113 · cero UI Mesa incidente.
2. **Opción B:** operar SEMI con v1.12 + DEX-1/2/3 (TRIGGERED → Confirm → `Ejecutar en PAPER`). No reabrir thin. No XTB capital.
3. **No** DEX-5 property suite, **no** pack auditor v113 en el mismo chat que DEX-4.

## 4. Docs clave

- [`plan-dex3-operational-incident-2026-08-26.md`](./plan-dex3-operational-incident-2026-08-26.md)
- [`plan-dex2-crash-restart-cross-pid-2026-08-26.md`](./plan-dex2-crash-restart-cross-pid-2026-08-26.md)
- [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md)
- [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
- Relevo previo: [`traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md`](./traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md)
