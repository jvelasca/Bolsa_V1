# RELEVO — tag v1.41.1-beta → auditoría externa (2026-08-31)

> **Padre:** [`traspaso-relevo-tag-v1-41-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-41-beta-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **SUPERSEDIDO por `v1.41.2-beta`** — tip CI `v1.41.1-beta` → `9938ff30` · Release-tag CI [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33370993883).  
> **Tip vigente:** [`traspaso-relevo-tag-v1-41-2-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-41-2-beta-2026-08-31.md).  
> **Arranque auditor (histórico):** [`arranque-auditor-v1-41-1-beta-2026-08-31.md`](./arranque-auditor-v1-41-1-beta-2026-08-31.md).  
> **Fuera:** P2 Lab · móvil · push · thaw estricto · OCO · trail autoridad · segundo Mercado · drag entry/exit.

---

## 0. Confirmación

- Producto **igual** que `v1.41-beta` (`4247f0f0`): proyección Operational Truth → Daily Desk.
- Tip CI: `v1.41-beta` Release-tag **RED** (Ruff I001 `position_decision.py`) → supersede con `v1.41.1-beta` (**sin** retag destructivo).
- Freeze intacto · backend operativo sin cambio de comportamiento (solo formato imports).

## 1. Release

| Pieza      | Valor                                                                                            |
| ---------- | ------------------------------------------------------------------------------------------------ |
| Tag tip    | `v1.41.1-beta` → `9938ff30`                                                                      |
| Previo tip | `v1.41-beta` → `4247f0f0` (CI tag RED)                                                           |
| Fix CI     | ruff I001 `packages/py/analytics/.../position_decision.py`                                       |
| CI tag     | [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33370993883)                           |
| Relevo UX  | [`traspaso-relevo-tag-v1-41-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-41-beta-2026-08-31.md) |

## 2. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO execute off · Ranking ≠ BUY · `protect_hint` thin ≠ autoridad · sin drag entry/exit.
