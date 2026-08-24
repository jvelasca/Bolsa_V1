# RELEVO — UX mesa U6 CERRADA → spine residual

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT** tras U6. **Siguiente = spine residual** (decisión de secuencia del propietario: U6 → spine residual → ops).
> **AsOf:** 2026-08-24. **`main` == `9e9a346`** (U6; ahead of `origin/main` hasta push). Ancla código U0–U5 **`04e441e`**. U6 **CERRADA**.
> **Protocolo:** máx. 1 writer + 1 verifier RO. Coordinador re-lee file:line. Pre-commit: batería de la fase + update-last.

---

## 1. Qué quedó hecho (U6)

| Entrega                       | Detalle                                                                                       |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| Preview ticket Confirm/drawer | Bloque compacto en `SupervisedF3Panel` (página `/confirm` + drawer U3 vía `ConfirmContent`)   |
| Comisión                      | `calculateTradeFees` (`packages/shared` account-settings) + `account.settings`                |
| Margen                        | `AccountSummaryDto.freeMargin` / `marginUsed` + margen orden est. `notional / leverage`       |
| Tip mesa                      | `confirm-ticket-preview` en `mesa-tip-catalog.ts`                                             |
| Tests                         | `f3-ticket-preview.test.ts` + tip catalog; confirm drawer tests intactos                      |
| Freeze                        | **Sin bypass execute** · botones Confirmar Intent / Confirmar+ejecutar sin cambio de contrato |

**Archivos (código):**

- `apps/web/src/features/trading/f3-ticket-preview.ts` (+ `.test.ts`)
- `apps/web/src/features/trading/f3-ticket-preview-block.tsx`
- `apps/web/src/features/settings/supervised-f3-panel.tsx` (wire)
- `apps/web/src/features/help/mesa-tip-catalog.ts` (+ test tip)

**Docs (update-last):** backlog §0 · `CURRENT_SYSTEM.md` · `PROJECT_STATE.md` · este relevo.

## 2. Freeze (sigue intacto)

OrderProposal · Journal · Attribution · orquestador · Daily Mission · Track B B1–B12 · Belief · `PAPER_D_EXECUTE` **off** · sin broker live · Lab→spine · `contract:gen` salvo fase pactada · **no bypass execute desde preview**.

## 3. Siguiente · spine residual

**Abrir spine residual** (huecos DS documentados; **no** OrderProposal). Ops propietario (secret scanning UI · `TRUSTED_PROXIES` prod) queda **después**.

## 4. Anti-sobrecarga

Máx. **2** subagentes (1 writer + 1 verifier RO). No reabrir Track B / Belief / H5. No mezclar ops en el mismo writer.

## 5. Texto de arranque (pegar en el chat nuevo)

```
CONTEXTO: main == 9e9a346 (U6; push pendiente). Código U0–U5 ancla 04e441e.
U6 ticket preview CERRADA. Prove+H5 CERRADOS. Freeze: sin OrderProposal ·
PAPER_D_EXECUTE off · Lab fuera spine · no broker live · no bypass execute preview.
SIGUIENTE: spine residual (huecos DS; no OrderProposal). Luego ops propietario.
Protocolo 1 writer + 1 verifier RO.
Read-first: backlog §0 · CURRENT_SYSTEM · PROJECT_STATE · este relevo.
```
