# RELEVO — P3 Cadena de salida CERRADO · apertura P4 · 2026-08-25

> **Padre:** [`plan-p3-cadena-salida-2026-08-25.md`](./plan-p3-cadena-salida-2026-08-25.md) · roadmap [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO (Confirm `exit_permission` + persist reduce + Operaciones advisory + HELP).** Cambiar de chat recomendado para P4.
> **Arranque chat nuevo:** este fichero + plan P3 + ADR-033 §7 + `CURRENT_SYSTEM.md` + roadmap v1.10.

---

## 0. Qué quedó hecho

| Pieza                                                                         | Estado         |
| ----------------------------------------------------------------------------- | -------------- |
| Confirm execute `exit_hint`/`reduce` → ExitPlan (`manual`) + ExitPermission   | **Hecho**      |
| Motivo `exit_permission` ≠ `risk_veto` ≠ `risk_signature`                     | **Hecho**      |
| Persist `applyReduce` (PARTIAL/CLOSED); idempotencia `_lastExitTransactionId` | **Hecho**      |
| Operaciones: columna Salida advisory (sin CTA)                                | **Hecho**      |
| HELP Trading + HELP.md + note HELP_CONTENT_AS_OF                              | **Hecho**      |
| Lab `evaluate-exits` / thin Hoy «Salida» / Consola / `stopPrice` / OCO        | **No** (fuera) |
| Protect/BE persist · `POST /portfolio/trade` sell como puerto                 | **No** (fuera) |

Spine `pnpm test:decision-spine` **257** (P3 cadena +12).

## 1. Freeze / flags

- `PAPER_D_EXECUTE` **off**. Broker **no**. Thaw estricto **FAIL**.
- Thin 5.x/8.x **congelados**. Dedup Hoy por símbolo **intacta**.
- `check_opening` **intacto**. H1 pending honesty **intacta**. H2 factories **sin campos extra**. P1 nacimiento **intacto**. P2 firma **intacta**.
- Pending ≠ stop de posición. OrderIntent = fill. **No** OrderIntent-dios.
- Lab Señales ≠ mesa. Thin «Salida» ≠ ExitPlan. Auto-exit **no** es CTA.
- Diálogo de orden **sigue** sin snapshot (P1). Venta directa no actualiza Position.

## 2. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** plan D1–D8 **P4 Consola de Mesa** (ADR-033 §7). Posiciones primero. **No** god page. **No** sexta puerta. Confirmar sigue siendo la firma.
2. **Opción B:** operar SEMI (firma + cadena). No reabrir thin.
3. **No** broker / `stopPrice` / OCO en el mismo chat. **No** auto-exit CTA.

## 3. Docs clave

- [`plan-p3-cadena-salida-2026-08-25.md`](./plan-p3-cadena-salida-2026-08-25.md)
- ADR-033 §7 · gap autoridad · `CURRENT_SYSTEM.md` · roadmap v1.10
