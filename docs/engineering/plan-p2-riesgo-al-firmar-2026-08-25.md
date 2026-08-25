# Plan — P2 Riesgo al firmar (ticket vs TradePlan)

> **Padre:** [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md) · ADR-033 §6 · gap [`adr-032-ops-authority-gap-2026-08-25.md`](./adr-032-ops-authority-gap-2026-08-25.md) §2 / mapa P2 · relevo [`traspaso-relevo-p1-position-durable-2026-08-25.md`](./traspaso-relevo-p1-position-durable-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO.** D1–D8 OK · ticket vs TradePlan · gate `risk_signature` · HELP · spine **245**.
> **Método:** al firmar, el tamaño es el del TradePlan (riesgo € / distancia al stop), no % caja. Gate UI **y** Confirm. Cero Consola. Cero `stopPrice` / OCO. Cero P3/P4. Cero `regen_full`. Cero campos extra F1–F4.

---

## 0. Objetivo

El ticket F3 (Confirmar página + drawer) muestra y **bloquea** el riesgo del plan: qty sugerida/máx, pérdida € y R, stop técnico, costes, efectivo posterior. Superar el plan exige motivo no vacío y revalidación. `check_opening` sigue siendo el veto de **apertura**; no se fusiona con sizing.

### Qué entra vs qué queda fuera

| Incluye (P2)                                                                    | Excluye                                           |
| ------------------------------------------------------------------------------- | ------------------------------------------------- |
| SoT al firmar = TradePlan TRIGGERED (`quantity`, stop, `riskAmount`)            | Pisar qty a ciegas; % caja como autoridad         |
| UI ticket: qty sugerida/máx, pérdida €/R, stop, costes (U6), efectivo           | Consola de Mesa · P4                              |
| Override `{ reason }` no vacío + revalidación; gate Confirm execute (aperturas) | `stopPrice` · OCO · OrderIntent-dios              |
| Sin plan TRIGGERED: honest (no inventar stop/R/máx); % caja puede prellenar     | P3 cadena ExitPlan · persist reduce/BE            |
| Tests familia B (qty ≤ plan · override · sin plan) + HELP                       | Thin 5.x/8.x · broker · `PAPER_D_EXECUTE`         |
| Delta mínimo `ConfirmIntentRequest.riskOverrideReason` (openapi + schema.d.ts)  | Pending / diálogo de orden · lote con override UI |

---

## 1. Decisiones (D1–D8)

| Id     | Decisión                                                                                                                                                                                                                                                                             |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **D1** | Con TradePlan **TRIGGERED** y `quantity` > 0: qty sugerida = qty máx = `TradePlan.quantity`. Default del ticket = esa qty (deja de ser % caja). % caja solo si no hay plan TRIGGERED.                                                                                                |
| **D2** | Superficie = ticket F3 (`SupervisedF3Panel` / Confirm). Mostrar: qty sugerida/máx, stop técnico, pérdida € al stop (`qty × \|precio − stop\|`), R firmado (`pérdida / riskAmount` si hay), costes+efectivo U6. **No** Consola.                                                       |
| **D3** | Gate UI+backend en **execute** de **aperturas** (`recommend_long`/`recommend_short`): qty > plan **o** pérdida € > `riskAmount` → override obligatorio. Bajar qty OK. Cierres/reduce **no** usan este gate. `check_opening` **intacto** (sigue siendo `risk_veto`).                  |
| **D4** | Revalidación: al cambiar qty/precio se recálcula la pérdida. Motivo = string no vacío (mismo criterio H2). Confirm `execute=False` **no** aplica el gate. Motivo de rechazo: `risk_signature` (≠ `risk_veto`).                                                                       |
| **D5** | Sin TradePlan TRIGGERED (WATCH/ARMED/ausente/qty 0): modo `no_plan` — no inventar stop/R/máx. Sizing % caja puede prellenar. Backend no aplica cap. Pending / `order-dialog` **fuera** (P1: sin snapshot). Lote «seleccionadas»: el gate backend aplica; sin UI de override en lote. |
| **D6** | Override de **firma** ≠ `birth_override_reason` P1. Campo opcional `riskOverrideReason` en `ConfirmIntentRequest`. **No** persiste en `position_states`. **No** campos nuevos F1–F4. **No** OrderIntent-dios.                                                                        |
| **D7** | HELP: al firmar, el tamaño es el riesgo del plan, no % caja. Override con motivo. Ciclo 4.0 «no pisar suggestedQuantity» queda **supersedido** cuando hay plan TRIGGERED.                                                                                                            |
| **D8** | Tests B · HELP · stamp CURRENT_SYSTEM / CHANGELOG / ADR-033 / roadmap P2 · relevo. **E1:** P3 cadena **o** operar SEMI. **No** P3/P4 en este chat.                                                                                                                                   |

Si P2 añade Consola, `stopPrice`, fusiona sizing con `check_opening`, o usa % caja como SoT con plan TRIGGERED: **parar y replanificar**.

---

## 2. Ficheros

- `packages/shared/src/cognitive/risk-signature.ts` · `risk-signature.test.ts`
- `packages/py/analytics/.../risk_signature.py` · `tests/test_risk_signature.py`
- `confirm_recommendation.py` (gate execute aperturas) · `ai_governance.py` DTO · ruta confirm
- `supervised-f3-panel.tsx` · bloque firma · `api.ts` · openapi.json + schema.d.ts (delta)
- Tests application Confirm · HELP · stamp

## 3. Freeze (intactos)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · ExitPlan ≠ auto-exit · SETUP Wyckoff cerrada · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 · `PAPER_D_EXECUTE` **off** · `check_opening` · H1 pending honesty · H2 factories **sin campos extra** · P1 persist · Dedup Hoy por símbolo · broker **no** · **no** OrderIntent-dios · **no** Consola.
