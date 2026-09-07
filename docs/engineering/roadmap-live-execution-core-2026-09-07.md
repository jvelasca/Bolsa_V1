# Roadmap — LIVE Execution Core (post V2.11)

> **AsOf:** 2026-09-07 · **Padre:** [engineering-index](./engineering-index-2026-08-03.md) · [audit V2.11](./audit-pack-v2-11-live-virtual-confirm-2026-09-07.md) · [audit LIVE venue](./audit-pack-live-venue-thaw-design-2026-09-06.md) · XL-2 [plan cerrado](./plan-xl2-xtb-fill-ledger-2026-08-26.md).  
> **Estado:** **PARCIAL** (dominio + sandbox VIRTUAL + OR-6 fail-closed + **Confirm wire persist-only** en código; UNKNOWN recovery/poll/partial ledger PARKED).  
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

| Pieza    | Alcance                                                                       | Estado                                                                                                               |
| -------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| **XL-2** | Bridge `filled` síncrono → `execute_trade` → ledger                           | **CERRADO** (2026-08-26)                                                                                             |
| **XL-3** | Máquina LIVE: AUTHORIZED→…→UNKNOWN/PARTIAL/FILLED · no re-POST · query_broker | **Dominio + tests + Confirm wire persist-only** · poll real PARKED · partial→ledger PARKED · UNKNOWN recovery PARKED |

---

## 2. Versiones siguientes (nombres)

| Versión     | Foco                                                                                       | UI                      |
| ----------- | ------------------------------------------------------------------------------------------ | ----------------------- |
| **V2.12**   | LIVE Execution Core (XL-3 wire + UNKNOWN recovery + idempotencia)                          | Solo estados necesarios |
| **V2.13**   | Reconciliation & Safety (account/position/order · kill LIVE · incident)                    | Mínima                  |
| **V2.14**   | Financial Execution & Full Reconciliation (fill→ExecutionEvent→Position→Ledger·Full Recon) | No nueva                |
| **V2.15**   | Shadow LIVE (consultar, no enviar)                                                         | Comparación             |
| **V2.16**   | LIVE Certification (evidencia)                                                             | —                       |
| **después** | Micro-LIVE / thaw process                                                                  | Owner approval          |

> **Corrección de numeración (2026-09-07, decree V2.14):** esta tabla antes rotulaba `V2.14 = Shadow LIVE`.
> Se sella **V2.14 = Financial Execution & Full Reconciliation**, Shadow LIVE pasa a V2.15 y LIVE cert a V2.16,
> para resolver la colisión con el track operator-journey. Ver
> [`plan-v2-14-financial-execution-reconciliation`](./plan-v2-14-financial-execution-reconciliation-2026-09-07.md).

---

## 3. Ya en código (esta tanda)

- OR-6 fail-closed: live recon ausente → `live_unavailable`; adapter `None` → `live_adapter_not_wired`.
- OE-1 → LR-1 + `liveAdapterWired` (bridge URL).
- `LIVE_EXECUTION_UNLOCKED` default **off** → `live_virtual_sandbox` (cero POST bridge).
- `XtbBrokerAdapter` reconsulta kill switch antes de submit.
- Dominio `LiveOrder` (PY+TS) + `LiveOrderQueryPort` mock.
- **Confirm wiring (persist-only):** `LiveOrderCoordinator` extremo (en `ConfirmRecommendationIntent`,
  inyección `live_order_store`) persiste/expona `result["liveOrder"]` tras `submit` LIVE que devuelve
  `submitted` (→ `SUBMITTED` + venue id) o `unknown` (→ `UNKNOWN` first-class). PAPER, sandbox
  VIRTUAL `not_wired`, `rejected` y `executed`(XL-2 cerr.) NO escriben la máquina. `LiveOrderStore`
  proceso (InMemory; store inyectable) como fallback — Sled PG para V2.12. Mantiene
  `dex4_module_is_thin` (<1100 líneas) sin engordar el orquestador.

---

## 4. Qué NO afirmar

- Que XL-3 esté cableado a Confirm/ledger.
- Que VIRTUAL sandbox = Accept LIVE.
- Que P1–P5 PASS o thaw autorizado.
- Auto-heal de drift.
