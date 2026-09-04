# Arranque auditor externo — V1.99 tip (Position Management Certification) (2026-09-04)

Copia en chat nuevo (auditor):

---

Eres auditor externo de Bolsa V1 **candidato V1.99** (partida **`v1.98-beta` → `7b5b1052`** · Release-tag CI V1.98 **GREEN** [run 33844531875](https://github.com/jvelasca/Bolsa_V1/actions/runs/33844531875)). **No** LIVE · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`**.

**Alcance V1.99 (solo certificación, cero features):**

- Goldens G1–G8 de gestión de posición (FSM + qty + lastFill + stop mono)
- Contrato: `event log` = verdad · `stage` = derivado · `lineagePath` = last-wins (**no** historia)
- `initialRisk` / `initialStop` inmutables tras trail / T1 reduce
- Trail **solo después de T1** (no `open` → TRAIL)
- G7 = ancla V1.97 crash mid T2 pair exactly-once (no reimplementado)
- Sin Alembic · sin cambios `TRANSITIONS`

**Regla:** NINGÚN estado ambiguo → COMPRAR. DryRun honesto. No unificar ledger/mesa. No LIVE.

Lee: `CURRENT_SYSTEM.md` · `spec-v199` · `test_lifecycle_position_management_v199.py` · `test_position_state.py` (`test_v199_trail_and_reduce_preserve_initial_risk`) · `test_lifecycle_t2_atomicity_v197.py` (G7) · `lifecycle-fsm.test.ts` (V1.99) · [`relevo`](./traspaso-relevo-v1-99-position-management-certification-2026-09-04.md).

**Foco:**

1. ¿G5 (T1→TRAIL×2→T2→TRAIL→EXIT) certifica stop que no retrocede, qty, lastFill y remaining?
2. ¿Tras T2→TRAIL, `lineagePath=trail` pero el log sigue conteniendo `T2_EXECUTED`?
3. ¿Trail/reduce dejan intactos `initialRisk` / `initialStop` en PositionState?
4. ¿G7 sigue siendo exactamente el crash/retry V1.97 (sin motor paralelo)?
5. ¿Freeze intacto? ¿Cero cambios de TRANSITIONS?

**No pedir:** LIVE · bump · open→TRAIL · LineagePath flags · cuarteto riesgo persistido · UI MERCADO V2.0 · unificar ledger · V2.0 por inercia antes de PASS G1–G8.

**Respuesta:** (pendiente — no inventar PASS).

---
