# Audit pack — Broker LIVE venue thaw design (post V2.10.1)

> **AsOf:** 2026-09-06 · **Tip:** [`v2.10.1-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.10.1-beta) → [`a060af37`](https://github.com/jvelasca/Bolsa_V1/commit/a060af37) · package `1.39.1-beta`.  
> **Padre:** [cierre V2.10.x](./traspaso-relevo-cierre-v2-10-x-2026-09-06.md) · [ADR-034](../adr/034-operational-integrity-continuity.md) · [ADR-035](../adr/035-operational-reliability.md) · [ops readiness](./traspaso-relevo-stamp-v2-10-1-operational-readiness-2026-09-06.md) · [Nivel 4](./traspaso-relevo-stamp-nivel4-ops-partial-2026-09-06.md).  
> **Veredicto:** **DESIGN_ONLY** · **LIVE bloqueado** · **no** thaw venue · **no** tip/bump · **≠** Accept estricto / `PAPER_D_EXECUTE`.  
> **Inventario:** [gates](2fb5c4de-a1ab-4762-9431-0d1218e507e6) · [bridge](613db2f4-d049-45e0-a3f5-3fb262019f8f) · [ops blockers](ca11265d-796f-4d5b-b2a5-00fe012d08ce).

---

## 0. Honestidad

| Afirmar                                                       | No afirmar                                     |
| ------------------------------------------------------------- | ---------------------------------------------- |
| Cableado XL-1/LR-1/XL-2/VS-1/RV-1/PA-1 + OR-4/OR-6 **existe** | Que LIVE TRADING está Accepted                 |
| Mock bridge fail-closed por defecto                           | Que mock FILL = capital XTB real               |
| Scorecard de precondiciones para un thaw **futuro**           | Que este pack autoriza flip `brokerVenue=live` |
| `LIVE_EXPERIMENTAL` ≠ Accepted (note `live_not_accepted`)     | Que `LIVE_EXPERIMENTAL` = listo para capital   |

Freeze: NO LIVE · `PAPER_D_EXECUTE` off · Confirm = firma · Arm ≠ Execute · Ranking ≠ BUY · **NO MÁS PANELES** · **PRODUCT FREEZE**.

### 0.1 Premisas owner (2026-09-06 noche)

| Premisa             | Detalle                                                                                                                                                                                                                                                |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **LIVE VIRTUAL**    | Hasta que la APP esté **100% probada** (puede tardar **meses**). Sin capital real / sin thaw prod en esa fase.                                                                                                                                         |
| **Pasarela visual** | Destino conceptual = **pasarela VISUAL de órdenes** al broker. **Concepto UI (híbrido)** documentado en [design UI LIVE VIRTUAL](./design-live-virtual-order-gateway-ui-2026-09-07.md) · **UI producto no implementada** · settlement real **PARKED**. |
| Estudio ≠ thaw      | Meterse a fondo en LIVE (docs/gates) **no** autoriza flip `brokerVenue=live` ni `PAPER_D_EXECUTE`.                                                                                                                                                     |

Arranque: [LIVE VIRTUAL design](./arranque-agente-pista-a-estricto-2026-09-07.md) · [cierre sesión](./traspaso-relevo-cierre-sesion-pista-a-2026-09-06.md) · [UI pasarela](./design-live-virtual-order-gateway-ui-2026-09-07.md).

---

## 1. Inventario cerrado (código) vs parked

| Pieza                                                   | Estado                   | Nota                                                    |
| ------------------------------------------------------- | ------------------------ | ------------------------------------------------------- |
| XL-1 `XtbBrokerAdapter`                                 | CERRADO                  | `submitted` ≠ fill · sin bridge → `not_wired`           |
| LR-1 `LiveLedgerReconciliation`                         | CERRADO                  | detect/report · `unavailable` fail-closed · no heal     |
| XL-2 filled → `execute_trade`                           | CERRADO                  | solo tras bridge `filled` · boom → `unknown`            |
| VS-1 / RV-1 / PA-1 venue                                | CERRADO                  | coalesce memory ?? redis ?? account ?? env ?? **paper** |
| OR-4 opening veto live                                  | CERRADO                  | `live_drift` / `live_unavailable` solo venue live       |
| OR-6 readiness 4 estados                                | CERRADO                  | `LIVE_BLOCKED` si reasons; else `LIVE_EXPERIMENTAL`     |
| Money path XTB API real                                 | **PARKED**               | mock ≠ settlement real                                  |
| Accept LIVE / capital prod                              | **PARKED**               | owner + scorecard                                       |
| Wire OE-1 → LR-1 / adapter en OR-6                      | **CERRADO (post V2.11)** | OE-1 mide LR-1 + bridge URL → OR-6 fail-closed          |
| Typed `AccountSettings.brokerVenue` / Redis per-account | PARKED ADR-034           |                                                         |

---

## 2. Coalesce venue

**Async (Confirm/Fill/API):**  
`runtime_memory` ?? `redis` (`bolsa:risk:broker_venue`) ?? `account.settings_json.brokerVenue` ?? `Settings.BROKER_VENUE` ?? **`paper`**

Archivo: `packages/py/application/src/bolsa_application/broker_venue_runtime.py` · API `POST /api/risk/broker-venue` · PA-1 `PATCH /accounts/{id}/broker-venue`.

Override global mesa **≠** thaw `PAPER_D_EXECUTE` (ortogonal).

---

## 3. Gates (matriz)

| Gate           | Trigger                      | Efecto                                                                        |
| -------------- | ---------------------------- | ----------------------------------------------------------------------------- |
| Adapter select | venue efectivo               | paper → PaperBroker · live → Xtb (sin URL → `not_wired`)                      |
| OR-4           | apertura buy + recon wired   | portfolio drift DENY siempre · LR-1 solo si venue=live                        |
| Kill switch    | `effective`                  | DENY openings · OR-6 reason `kill_switch`                                     |
| Mock default   | sin ALLOW                    | `rejected` / `live_orders_disabled`                                           |
| ALLOW alone    | `XTB_BRIDGE_ALLOW_ORDERS=1`  | `submitted` · **no** ledger                                                   |
| ALLOW+FILL     | + `XTB_BRIDGE_FILL_ORDERS=1` | `filled` → ledger solo si `execute_trade` OK                                  |
| OR-6 live      | venue=live + reasons         | `LIVE_BLOCKED` · sin reasons → `LIVE_EXPERIMENTAL` + note `live_not_accepted` |

---

## 4. Scorecard precondiciones (DESIGN_ONLY)

| #   | Precondición              | Estado hoy                         | Bloquea claim LIVE ready?             |
| --- | ------------------------- | ---------------------------------- | ------------------------------------- |
| L1  | Mesa default paper        | PASS                               | —                                     |
| L2  | `PAPER_D_EXECUTE` off     | PASS (prep stamp)                  | Flip = fuera de este pack             |
| L3  | Kill off en steady state  | PASS (B3 restore)                  | —                                     |
| L4  | OI-6 ≠ LR-1 (dos capas)   | Diseño OK · LR-1 no medido en OE-1 | Sí si se colapsan                     |
| L5  | Mock fail-closed default  | PASS                               | Sí si se trata mock FILL como capital |
| L6  | `TRUSTED_PROXIES` prod    | BLOCKED_ON_OWNER                   | Sí para edge prod                     |
| L7  | Auth prod-like            | open-local ≠ prod                  | Sí para claim prod                    |
| L8  | Nivel 4 load/soak/chaos   | PARTIAL / DEFER                    | Sí para “operacionalmente listo”      |
| L9  | Cuenta DEMO ≠ policy LIVE | Seed paper                         | Sí                                    |
| L10 | Owner word thaw LIVE      | **NO**                             | Hard gate                             |

**Veredicto scorecard:** **no PASS** para thaw · diseño documentado.

---

## 5. Qué NO afirmar

- Flip venue = Accept / prod LIVE.
- `LIVE_EXPERIMENTAL` = listo para capital.
- `submitted` = fill = `executed`.
- XL-2 mock filled = settlement XTB real.
- OI-6 `clean` = LR-1 live-safe.
- Prep PAPER / DEMO execute / Accept estricto = autorización LIVE.
- OE-1 sin LR-1 medido (ya cableado post V2.11; unmeasured → BLOCKED).
- Que el estudio LIVE VIRTUAL = capital real / pasarela UI **Accepted** o **shipped**.
- Que el [diseño UI híbrido](./design-live-virtual-order-gateway-ui-2026-09-07.md) autorice thaw o flip venue/execute.
- Que VIRTUAL (meses) autorice thaw prod antes de APP 100% probada.
- Que `LIVE_EXECUTION_UNLOCKED` off se salte con solo `brokerVenue=live`.

---

## 6. Siguiente (docs)

1. [Diseño UI pasarela LIVE VIRTUAL (híbrido)](./design-live-virtual-order-gateway-ui-2026-09-07.md) — concepto cerrado · UI producto **no** implementada · [relevo](./traspaso-relevo-design-live-virtual-ui-2026-09-07.md).
2. [Runbook gates](./runbook-live-venue-thaw-gates-2026-09-06.md) — preflight / flip futuro / abort / restore paper (**sin** ejecutar flip hoy).
3. Cadena B: Accept estricto — [deuda](./deuda-thaw-estricto-runbook-2026-08-25.md) · **≠** este pack.
4. Post-freeze: OR-6 fail-closed + OE-1↔LR-1 + VIRTUAL sandbox + XL-3 dominio — ver [roadmap LIVE Execution](./roadmap-live-execution-core-2026-09-07.md).
