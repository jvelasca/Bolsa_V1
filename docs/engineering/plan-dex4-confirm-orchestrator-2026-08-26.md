# Plan — DEX-4 Confirm = orquestador

> **Padre:** [`roadmap-v113-durable-execution-2026-08-26.md`](./roadmap-v113-durable-execution-2026-08-26.md) · ADR-035 · plan DEX-3.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (código + tests + docs).
> **Partida:** tag **`v1.12-beta` → `369b5d1`**. DEX-3 CERRADO. Spine **463 → 465**.
> **Relevo:** [`traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md`](./traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md).

---

## Objetivo

El auditor marcó Confirm como God Use Case (~1531 líneas). DEX-4 **no** cambia producto ni política: extrae coordinators y deja `ConfirmRecommendationIntent` como **orquestador** (única firma transaccional SEMI).

```text
ConfirmRecommendationIntent.execute
  → Identity
  → RiskGate / OpeningGate / ExitGate   (mutuamente excluyentes por action)
  → SubmitIntent + Execution            (solo si gates ALLOW)
  → PositionSync                        (solo fill / protect)
```

Sin redesign UI · sin property suite (DEX-5) · sin pack v113 · sin thaw · sin UI Mesa incidente.

---

## Decisiones

| ID  | Decisión                                                                                                                                                       |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Paquete `bolsa_application/confirm/` con 7 coordinators: `Identity` · `RiskGate` · `OpeningGate` · `ExitGate` · `Execution` · `SubmitIntent` · `PositionSync`. |
| D2  | `ConfirmRecommendationIntent` sigue siendo la API pública (DI, `execute`, helpers re-exportados). Comportamiento equivalente para gates OR-1…OR-4 / DEX-1…3.   |
| D3  | **Identity** = Recommendation/intent · DecisionPackage · side · TTL/orphan/precio · `decision_id` · conflict package.                                          |
| D4  | **OpeningGate** = cesta `check_opening` / `allow_opening_fill` → `risk_veto` (Escalón 3 + DS-03/05 + recon/incident).                                          |
| D5  | **RiskGate** = `risk_signature` (P2 sizing vs TradePlan). ≠ OpeningGate.                                                                                       |
| D6  | **ExitGate** = ExitPermission + protect path (cero ledger en protect).                                                                                         |
| D7  | **SubmitIntent** = record / recover / persist-after-adapter (OR-2 + DEX-1).                                                                                    |
| D8  | **Execution** = idempotent replay · `adapter.submit` · paper/live receipt mapping.                                                                             |
| D9  | **PositionSync** = persist fill / exit / protect post-éxito.                                                                                                   |
| D10 | **No** Alembic · **No** `contract:gen` · **No** DEX-5 · **No** pack v113 · **No** UI Mesa · **No** thaw · **No** AUTO.                                         |

---

## Ficheros

- `packages/py/application/src/bolsa_application/confirm/` — coordinators (~922 líneas orquestador; pre ~1531)
- `confirm_recommendation.py` — orquestador fino + re-exports
- Tests: `test_dex4_confirm_orchestrator.py` (+ regresión spine)
- Docs: plan · CURRENT_SYSTEM · ADR-035 · roadmap · CHANGELOG · relevo DEX-4→DEX-5
- Spine battery: ancla DEX-4

---

## DoD

- [x] 7 coordinators extraídos; Confirm orquesta (sin God Method monolítico).
- [x] Misma semántica: risk_veto · risk_signature · exit_permission · OR-1 replay · OR-2 UNKNOWN · DEX-1/2/3 intactos.
- [x] Spine ancla DEX-4 (**465**). Sin DEX-5 · sin pack v113 · sin thaw · sin AUTO · sin broker producción.
- [x] Docs stamp + relevo al chat DEX-5.

## Freeze (intactos)

ADR-034 · OR-1/3/4/5/6 · DEX-1/2/3 · Confirm = única firma · `PAPER_D_EXECUTE` off · thin 5.x/8.x · Lab ≠ mesa · JSONB PositionState SoT · Incident UI Mesa parked.

## E1

Tras DEX-4: **DEX-5** invariantes operacionales **o** operar SEMI. **No** pack v113 en el mismo chat.
