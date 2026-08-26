# Checklist — SEMI E2E: TRIGGERED → Confirm → protect

> **AsOf:** 2026-08-26  
> **Padre:** ADR-034 · relevo OI-4 ([`traspaso-relevo-oi4-order-lifecycle-2026-08-26.md`](./traspaso-relevo-oi4-order-lifecycle-2026-08-26.md)) · OI-5 cerrado ([`traspaso-relevo-oi5-position-revisions-2026-08-26.md`](./traspaso-relevo-oi5-position-revisions-2026-08-26.md)).  
> **Alcance:** operar el camino paper SEMI ya cableado. **No** OI-6 · **No** broker.

---

## Camino (código)

```text
TradePlan STATUS=TRIGGERED
    → propose / cola F3 (supervised-f3-panel)
    → Confirm execute (recommend_long|short)
         · risk_signature (OI-2): exige TRIGGERED + qty/riesgo del plan
         · PaperOrder CREATED → FILLED (OI-4)
         · execute_trade → ledger fill
         · PersistPositionFromFill → PositionState OPEN + stops (OI-1)
         · ExecutionRecord outcome=executed (OI-3)
    → PositionState OPEN (currentStop = structuralStop del plan)
    → Consola: Proteger (operativaIntent=protect, action=wait)
    → Confirm protect
         · ExitPermission / semi_protect_permission
         · PersistPositionFromProtect → apply_position_current_stop
         · PositionRevision append (OI-5, origin=protect) si stop/status cambian
         · cero ledger · sin PaperOrder
         · si stop ≥ entry (long) → status PROTECTED (BE)
```

**Archivos clave:** `confirm_recommendation.py` · `risk_signature` · `persist_position_from_fill` · `persist_position_from_protect` · `paper_order` · `execution_record` · UI `supervised-f3-panel.tsx` / F3 protect block.

---

## Qué ya cubre el spine (pytest)

Archivo: `packages/py/application/tests/test_semi_triggered_confirm_protect.py` (+ OI-1…OI-5).

| Escenario                                                                  | Cubierto                              |
| -------------------------------------------------------------------------- | ------------------------------------- |
| TRIGGERED + Confirm execute → OPEN + stops                                 | Sí (cadena)                           |
| Luego protect → `currentStop` actualizado, cero ledger                     | Sí                                    |
| Protect a BE → `PROTECTED`                                                 | Sí                                    |
| Sin plan / WATCH → `risk_signature`, no abre                               | Sí                                    |
| Honesty: `paperOrder` FILLED · `executionRecord` executed · gate sin orden | Sí (cadena + OI-3/OI-4)               |
| Protect empeora stop sin override (H2 factory)                             | Unit protect / position_state (no UI) |
| PositionRevision en protect/reduce                                         | Sí (OI-5 factory + persist)           |

Batería: `pnpm test:decision-spine` (**306** post-OI-5).

---

## Qué probar a mano en mesa (paper)

1. Cuenta **SEMI**, valor en Estudio, Proponer F3 con plan **TRIGGERED**.
2. Confirmar + ejecutar → Operaciones / posición: status **OPEN**, stop/T1/T2 del plan.
3. En Consola, **Proteger** con stop mejorado → Confirmar protección → `currentStop` cambia; **sin** nueva fila ledger; snapshot con `revisions[]` (OI-5).
4. Opcional: stop a break-even → status **PROTECTED**.
5. Intentar firmar apertura **sin** TRIGGERED (WATCH / sin plan) → rechazo `risk_signature`, no fill.

---

## Qué NO hacer

- Broker / PaperBroker / reconciliación plena (**OI-6**).
- Alembic · `contract:gen` · thaw `PAPER_D_EXECUTE`.
- Lab executeTrades como sustituto de Confirm en mesa.

---

## Gaps operativos → parked

| Gap                               | Notas                                                                            |
| --------------------------------- | -------------------------------------------------------------------------------- |
| **Historial de stop / revisions** | **Cerrado OI-5** — `PositionState.revisions[]` append-only.                      |
| **Protect + persist None**        | **Cerrado PH-1** — `skipped` / `stop_not_applied`; no journal `protect_applied`. |
| **UI e2e browser**                | No hay Playwright de esta cadena; spine + checklist manual.                      |

---

## Freeze

ADR-033/034 · Confirm = firma de mesa · no broker · no OI-6.
