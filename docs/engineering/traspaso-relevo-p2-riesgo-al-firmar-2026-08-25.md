# RELEVO — P2 Riesgo al firmar CERRADO · apertura P3 · 2026-08-25

> **Padre:** [`plan-p2-riesgo-al-firmar-2026-08-25.md`](./plan-p2-riesgo-al-firmar-2026-08-25.md) · roadmap [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO (ticket F3 + gate Confirm `risk_signature` + HELP).** Cambiar de chat recomendado para P3.
> **Arranque chat nuevo:** este fichero + plan P2 + ADR-033 §4 + `CURRENT_SYSTEM.md` + roadmap v1.10.

---

## 0. Qué quedó hecho

| Pieza                                                             | Estado         |
| ----------------------------------------------------------------- | -------------- |
| `evaluateRiskSignature` / `evaluate_risk_signature` (TS+Py)       | **Hecho**      |
| Ticket F3: qty/stop/pérdida €/R del plan; % caja solo sin plan    | **Hecho**      |
| Override con motivo; execute apertura bloqueado sin él            | **Hecho**      |
| Confirm execute: `risk_signature` ≠ `risk_veto` (`check_opening`) | **Hecho**      |
| HELP Trading + HELP.md + note HELP_CONTENT_AS_OF                  | **Hecho**      |
| Consola / `stopPrice` / OCO / P3 cadena / persist reduce-BE       | **No** (fuera) |

Spine `pnpm test:decision-spine` **245** (P2 firma +12).

## 1. Freeze / flags

- `PAPER_D_EXECUTE` **off**. Broker **no**. Thaw estricto **FAIL**.
- Thin 5.x/8.x **congelados**. Dedup Hoy por símbolo **intacta**.
- `check_opening` **intacto**. H1 pending honesty **intacta**. H2 factories **sin campos extra**. P1 persist **intacto**.
- Pending ≠ stop de posición. OrderIntent = fill. **No** OrderIntent-dios.
- Lote «seleccionadas»: gate backend aplica; sin UI de override en lote.
- Diálogo de orden **sigue** sin snapshot (P1).

## 2. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** plan D1–D8 **P3 Una cadena de salida** (ADR-033 §4). ExitPlan → ExitPermission → SEMI. Lab intacto. **No** auto-exit CTA. **No** consola.
2. **Opción B:** operar SEMI. No reabrir thin.
3. **No** Consola de Mesa en el mismo chat. **No** `stopPrice` / OCO. **No** P4.

## 3. Docs clave

- [`plan-p2-riesgo-al-firmar-2026-08-25.md`](./plan-p2-riesgo-al-firmar-2026-08-25.md)
- ADR-033 §4 · gap autoridad · `CURRENT_SYSTEM.md` · roadmap v1.10
