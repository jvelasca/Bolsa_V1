# RELEVO — DEX-2 Crash/restart cross-PID · apertura DEX-3 · 2026-08-26

> **Padre:** [`plan-dex2-crash-restart-cross-pid-2026-08-26.md`](./plan-dex2-crash-restart-cross-pid-2026-08-26.md) · ADR-035 · roadmap v1.13.
> **AsOf:** 2026-08-26.
> **Partida:** tag **`v1.12-beta` → `369b5d1`**. Spine **433 → 440**.
> **Estado:** **DEX-2 CERRADO** (tests + docs). Next = **DEX-3**.
> **Arranque chat nuevo:** este fichero + plan DEX-2 + ADR-035 + roadmap v1.13 + `CURRENT_SYSTEM.md`.

---

## 0. Por qué cambiar de chat

DEX-2 certifica recuperación **cross-PID**: store/sesión A persiste → kill → store/cliente **fresco** (B) lee el mismo backing → `UNKNOWN` · 0 re-POST. El siguiente hueco del auditor es **Incident / resolución recon** (DEX-3). No mezclar Confirm split (DEX-4) ni property suite (DEX-5) en el mismo chat.

## 1. Qué quedó hecho

| Pieza                                              | Estado                  |
| -------------------------------------------------- | ----------------------- |
| DEX-1 PG `submit_intents` + store + fases          | **Hecho** (chat previo) |
| Store A → kill → Store B get (PG mapping)          | **Hecho**               |
| Confirm store B post-recorded → UNKNOWN · 0 submit | **Hecho**               |
| Confirm store B post-venue_bound → mapeo · 0 POST  | **Hecho**               |
| Live submit A → Confirm B · 1 venue POST total     | **Hecho**               |
| Spine ancla `test_dex2_crash_restart_cross_pid.py` | **Hecho** · **440**     |
| DEX-3 Incident · DEX-4 split · pack v113           | **No**                  |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off**. LIVE **experimental**. Thaw estricto **deuda**. AUTO **off**.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Confirm = firma · I1/I3/RX1 intactos.
- Thin 5.x/8.x **congelados**. OR-1/3/4/5/6 **no se reabren** a ciegas.
- Auto-exit **no** es CTA cotidiano. **No** más brokers.
- JSONB PositionState SoT · `position_revisions` parked. Redis multi-worker **parked**.

## 3. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** implementar **DEX-3** — `OperationalIncident` + resolve/clear (mínimo backend; drift → INC → review → resolve → clear). Sin auto-heal. Citar plan DEX-2 + ADR-035. Cero Confirm split · cero pack v113.
2. **Opción B:** operar SEMI con v1.12 + DEX-1/2 PG (TRIGGERED → Confirm → `Ejecutar en PAPER`). No reabrir thin. No XTB capital.
3. **No** DEX-4 Confirm split, **no** DEX-5 property suite, **no** pack auditor v113 en el mismo chat que DEX-3.

## 4. Docs clave

- [`plan-dex2-crash-restart-cross-pid-2026-08-26.md`](./plan-dex2-crash-restart-cross-pid-2026-08-26.md)
- [`plan-dex1-pg-submit-intents-2026-08-26.md`](./plan-dex1-pg-submit-intents-2026-08-26.md)
- [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md)
- [`audit-ext-v112-durable-execution-triage-2026-08-26.md`](./audit-ext-v112-durable-execution-triage-2026-08-26.md)
- ADR-035 · ADR-034 · `CURRENT_SYSTEM.md`
- Relevo previo: [`traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md`](./traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md)
