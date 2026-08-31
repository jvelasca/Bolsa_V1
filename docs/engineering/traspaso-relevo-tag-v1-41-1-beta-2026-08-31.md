# RELEVO — tag v1.41.1-beta → auditoría externa (2026-08-31)

> **Padre:** [`traspaso-relevo-tag-v1-41-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-41-beta-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **PUBLICACIÓN** — tip certificado `v1.41.1-beta` (mismo producto V1.37→V1.41 + CI tip GREEN).  
> **Arranque auditor:** [`arranque-auditor-v1-41-1-beta-2026-08-31.md`](./arranque-auditor-v1-41-1-beta-2026-08-31.md).  
> **Fuera:** P2 Lab · móvil · push · thaw estricto · OCO · trail autoridad · segundo Mercado · drag entry/exit.

---

## 0. Confirmación

- Producto **igual** que `v1.41-beta` (`4247f0f0`): proyección Operational Truth → Daily Desk.
- Tip CI: `v1.41-beta` Release-tag **RED** (Ruff I001 `position_decision.py`) → supersede con `v1.41.1-beta` (**sin** retag destructivo).
- Freeze intacto · backend operativo sin cambio de comportamiento (solo formato imports).

## 1. Release

| Pieza      | Valor                                                                                            |
| ---------- | ------------------------------------------------------------------------------------------------ |
| Tag tip    | `v1.41.1-beta` → _(SHA al publicar)_                                                             |
| Previo tip | `v1.41-beta` → `4247f0f0` (CI tag RED)                                                           |
| Fix CI     | ruff I001 `packages/py/analytics/.../position_decision.py`                                       |
| Relevo UX  | [`traspaso-relevo-tag-v1-41-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-41-beta-2026-08-31.md) |

## 2. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · AUTO execute off · Ranking ≠ BUY · `protect_hint` thin ≠ autoridad · sin drag entry/exit.
