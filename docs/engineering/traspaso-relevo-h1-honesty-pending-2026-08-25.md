# RELEVO — H1 Honesty pending CERRADO · apertura H2 · 2026-08-25

> **Padre:** [`plan-h1-honesty-pending-2026-08-25.md`](./plan-h1-honesty-pending-2026-08-25.md) · roadmap [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO (honesty UI + HELP).** Cambiar de chat recomendado para H2.
> **Arranque chat nuevo:** este fichero + plan H1 + ADR-033 §5 + `CURRENT_SYSTEM.md` + roadmap v1.10.

---

## 0. Qué quedó hecho

| Pieza                                                        | Estado                   |
| ------------------------------------------------------------ | ------------------------ |
| Tab / campo / botones / Operaciones / listas → «a precio»    | **Hecho**                |
| Hint UI: no es stop de posición                              | **Hecho**                |
| HELP Trading + HELP.md + note HELP_CONTENT_AS_OF             | **Hecho**                |
| Wire `orderType: "stop_limit"` / Alembic / `stopPrice` / OCO | **No** (intacto / fuera) |
| H2 invariantes / P1 Position / Consola                       | **No**                   |

## 1. Freeze / flags

- `PAPER_D_EXECUTE` **off**. Broker **no**. Thaw estricto **FAIL**.
- Thin 5.x/8.x **congelados**. Dedup Hoy por símbolo **intacta**.
- Pending ≠ stop de posición. OrderIntent = fill (ADR-029). **No** OrderIntent-dios.

## 2. E1 — fork (chat nuevo)

1. **Opción A (recomendada):** plan D1–D8 **H2 Invariantes factories** (TRIGGERED, stop no empeora, T2≠T1, short=`buy`, kill switch asimétrico).
2. **Opción B:** operar SEMI. No reabrir thin.
3. **No** P1 Alembic sin H2. **No** Consola de Mesa. **No** `stopPrice` / OCO.

## 3. Docs clave

- [`plan-h1-honesty-pending-2026-08-25.md`](./plan-h1-honesty-pending-2026-08-25.md)
- ADR-033 · gap autoridad · `CURRENT_SYSTEM.md` · roadmap v1.10
