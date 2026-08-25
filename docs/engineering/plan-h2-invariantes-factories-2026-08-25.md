# Plan — H2 Invariantes factories (antes de persistir)

> **Padre:** [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md) · ADR-033 §5 · gap [`adr-032-ops-authority-gap-2026-08-25.md`](./adr-032-ops-authority-gap-2026-08-25.md) §2.4 · relevo [`traspaso-relevo-h1-honesty-pending-2026-08-25.md`](./traspaso-relevo-h1-honesty-pending-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO.** D1–D8 OK · guards factories TS+Py · HELP kill switch · spine **226**.
> **Método:** guards en factories TS+Py. Cero Alembic. Cero wire Confirm. Cero UI mesa. Cero `contract:gen`. Cero campos nuevos en F1–F4.

---

## 0. Objetivo

Las factories no mienten **antes** de que P1 las grabe. WATCH/ARMED no nacen posición; el stop no empeora a ciegas; T2 no dispara el atajo T1; cerrar short no es `sell`; el kill switch no niega el desriesgo humano.

### Qué entra vs qué queda fuera

| Incluye (H2)                                                              | Excluye                                    |
| ------------------------------------------------------------------------- | ------------------------------------------ |
| Guards ADR-033 §5.1–§5.5 en factories TS + Py                             | Alembic · persistencia Position            |
| Override auditado = `{ reason }` no vacío (no persiste; P1 lo usará)      | Wire Confirm / Fill / `apps/`              |
| Tests familia B (nacimiento/stop) + D (T2, short=buy, kill asimétrico)    | Consola de Mesa · P2 firma · P3 cadena     |
| HELP: kill switch bloquea aperturas/AUTO; SEMI desriesgo humano permitido | `stopPrice` · OCO · `contract:gen`         |
| Stamp CURRENT_SYSTEM + roadmap H2 CERRADO + relevo H2                     | Thin 5.x/8.x · ActionabilityScore · broker |

---

## 1. Decisiones (D1–D8)

| Id     | Decisión                                                                                                                                                                                                                                                      |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | `buildPositionStateFromFill` / `build_position_state_from_fill` exige `TradePlan.status == TRIGGERED`. WATCH / ARMED / BLOCKED / EXPIRED → `null`. Override `{ reason }` no vacío permite nacer.                                                              |
| **D2** | `applyPositionCurrentStop` / `apply_position_current_stop` no empeora el stop (long: nuevo < actual; short: nuevo > actual) sin override auditado → `null`. Mejorar / igual / primer stop (actual null) OK.                                                   |
| **D3** | Si `TARGET_2` dispara, no se interpreta `TARGET_1`: se descarta T1 del set y primary = T2 → `full_exit` (qty = remaining). Solo T1 (sin T2) sigue `reduce` mitad. Precedencia lista **intacta**.                                                              |
| **D4** | ExecutionPlan: cerrar / reducir long = `sell`; short = `buy`. `stop_amend` sigue `side: none`.                                                                                                                                                                |
| **D5** | ExitPermission: `killSwitch` + `autoExecute` → DENY `kill_switch` (automatismos). `killSwitch` + humano (`autoExecute !== true`) + accionable protect/reduce/full_exit → **no** DENY por kill. Idle+kill sigue DENY. `check_opening` **intacto** (aperturas). |
| **D6** | Override = gate de reason no vacío. **No** campos nuevos en PositionState / ExitPlan / ExecutionPlan. **No** persiste (sin Alembic).                                                                                                                          |
| **D7** | Paridad TS+Py. HELP: kill switch asimétrico (usuario). H1 honesty pending **intacta**.                                                                                                                                                                        |
| **D8** | Tests invariante · stamp CURRENT_SYSTEM / CHANGELOG / roadmap H2 CERRADO · relevo H2. **E1:** P1 Position durable **o** operar SEMI. **No** P1 en este chat. **No** Consola.                                                                                  |

Si H2 añade Alembic, wire Confirm o `stopPrice`: **parar y replanificar**.

---

## 2. Ficheros

- `packages/shared/src/cognitive/position-state.ts` · `position-state.test.ts`
- `packages/shared/src/cognitive/exit-plan.ts` · `exit-plan.test.ts`
- `packages/shared/src/cognitive/execution-plan.ts` · `execution-plan.test.ts`
- `packages/shared/src/cognitive/exit-permission.ts` · `exit-permission.test.ts`
- `packages/py/analytics/.../position_state.py` · `exit_plan.py` · `execution_plan.py` · `exit_permission.py` + tests
- HELP (`hoy-en-la-mesa` / HELP.md / as-of)
- Stamp: CURRENT_SYSTEM · CHANGELOG · roadmap v1.10 · ADR-033 nota H2 · relevo H2

## 3. Freeze (intactos)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · ExitPlan ≠ auto-exit · SETUP Wyckoff cerrada · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 · `PAPER_D_EXECUTE` **off** · `check_opening` · Confirm / Fill / Hoy · H1 pending honesty · F1–F4 **sin campos extra** · broker **no** · **no** `contract:gen` · **no** OrderIntent-dios.
