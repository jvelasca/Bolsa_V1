# Roadmap — LIVE Execution Core (post V2.11)

> **AsOf:** 2026-09-07 · **Padre:** [engineering-index](./engineering-index-2026-08-03.md) · [audit V2.11](./audit-pack-v2-11-live-virtual-confirm-2026-09-07.md) · [audit LIVE venue](./audit-pack-live-venue-thaw-design-2026-09-06.md) · XL-2 [plan cerrado](./plan-xl2-xtb-fill-ledger-2026-08-26.md).  
> **Estado:** **ABIERTO** (dominio XL-3 + sandbox VIRTUAL + OR-6 fail-closed en código; poll/ledger partial PARKED).  
> **≠** thaw · **≠** Accept estricto · **≠** `PAPER_D_EXECUTE` · **≠** default `brokerVenue=live`.

---

## 0. Tres certificaciones (no mezclar)

| Carril         | Evidencia                                           | Estado hoy     |
| -------------- | --------------------------------------------------- | -------------- |
| **Producto**   | V2.10.1 / V2.11 CI·E2E·UI honesty                   | 🟢 tip V2.11   |
| **Estrategia** | P1–P5 / W2–W4                                       | 🔴 W+5 **0/5** |
| **Broker**     | XL-1/XL-2 slice + XL-3 FSM + LR-1 en OE-1 + sandbox | 🟡 en progreso |

**LIVE THAW** = Producto ∧ Estrategia ∧ Broker verdes + **owner word** (L10). Tip GREEN ≠ Accept estricto ≠ thaw capital.

---

## 1. XL-2 cerrado vs XL-3

| Pieza    | Alcance                                                                       | Estado                                                         |
| -------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------- |
| **XL-2** | Bridge `filled` síncrono → `execute_trade` → ledger                           | **CERRADO** (2026-08-26)                                       |
| **XL-3** | Máquina LIVE: AUTHORIZED→…→UNKNOWN/PARTIAL/FILLED · no re-POST · query_broker | **Dominio + tests** · poll real PARKED · partial→ledger PARKED |

---

## 2. Versiones siguientes (nombres)

| Versión     | Foco                                                                    | UI                      |
| ----------- | ----------------------------------------------------------------------- | ----------------------- |
| **V2.12**   | LIVE Execution Core (XL-3 wire + UNKNOWN recovery + idempotencia)       | Solo estados necesarios |
| **V2.13**   | Reconciliation & Safety (account/position/order · kill LIVE · incident) | Mínima                  |
| **V2.14**   | Shadow LIVE (consultar, no enviar)                                      | Comparación             |
| **V2.15**   | LIVE Certification (evidencia)                                          | —                       |
| **después** | Micro-LIVE / thaw process                                               | Owner approval          |

---

## 3. Ya en código (esta tanda)

- OR-6 fail-closed: live recon ausente → `live_unavailable`; adapter `None` → `live_adapter_not_wired`.
- OE-1 → LR-1 + `liveAdapterWired` (bridge URL).
- `LIVE_EXECUTION_UNLOCKED` default **off** → `live_virtual_sandbox` (cero POST bridge).
- `XtbBrokerAdapter` reconsulta kill switch antes de submit.
- Dominio `LiveOrder` (PY+TS) + `LiveOrderQueryPort` mock.

---

## 4. Qué NO afirmar

- Que XL-3 esté cableado a Confirm/ledger.
- Que VIRTUAL sandbox = Accept LIVE.
- Que P1–P5 PASS o thaw autorizado.
- Auto-heal de drift.
