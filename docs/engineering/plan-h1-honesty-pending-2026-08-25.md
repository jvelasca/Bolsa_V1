# Plan — H1 Honesty pending (orden a precio ≠ stop)

> **Padre:** [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md) · ADR-033 §3 · gap [`adr-032-ops-authority-gap-2026-08-25.md`](./adr-032-ops-authority-gap-2026-08-25.md) §2.2 · relevo [`traspaso-relevo-audit-ext-v19-ops-discontinuity-2026-08-25.md`](./traspaso-relevo-audit-ext-v19-ops-discontinuity-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CERRADO.** D1–D8 OK · UI + HELP · wire intacto.
> **Método:** honesty de etiqueta. Cero Alembic. Cero `stopPrice`. Cero H2. Cero Consola. Cero `contract:gen`.

---

## 0. Objetivo

La UI no puede decir «Stop/Limitada» ni «precio límite / stop» mientras el modelo solo persiste `limitPrice`. Pending = **orden a precio**. Stop de posición vive (cuando exista) en PositionState — no en este diálogo.

### Qué entra vs qué queda fuera

| Incluye (H1)                                           | Excluye                                        |
| ------------------------------------------------------ | ---------------------------------------------- |
| Renombrar tab / campo / botones / listas / Operaciones | `stopPrice`, trigger, OCO, grupo, `positionId` |
| Hint UI: no es stop de posición                        | Cambiar `orderType` wire `stop_limit`          |
| HELP Trading + HELP.md + HELP_CONTENT note             | H2 invariantes · P1 Alembic · P4 consola       |
| Stamp CURRENT_SYSTEM + roadmap + relevo                | Broker · thin · ActionabilityScore             |

---

## 1. Decisiones (D1–D8)

| Id  | Decisión                                                                                |
| --- | --------------------------------------------------------------------------------------- |
| D1  | Tab: **«Orden pendiente a precio»** (no Stop/Limitada).                                 |
| D2  | Campo: **«Precio límite»** (no «precio límite / stop»).                                 |
| D3  | Copy listas/Operaciones: compra/venta **a precio** / orden pendiente a precio.          |
| D4  | Hint bajo el campo: no es stop de posición; se ejecuta si el mercado alcanza el precio. |
| D5  | Wire `orderType: "stop_limit"` **intacto** (API/DTO). Solo labels usuario.              |
| D6  | `check_opening` / Confirm SEMI / Fill / factories F1–F4 / H2 **intactos**.              |
| D7  | HELP: pending ≠ stop de posición · PositionState (cuando exista) es el hogar del stop.  |
| D8  | Stamp CURRENT_SYSTEM · roadmap H1 CERRADO · relevo H1 · CHANGELOG Unreleased.           |

Si H1 añade `stopPrice` o Alembic: **parar y replanificar**.

---

## 2. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · Thin 5.x/8.x congelados · `PAPER_D_EXECUTE` off · H2+ parked · no OrderIntent-dios.
