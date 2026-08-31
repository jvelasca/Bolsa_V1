# RELEVO — tag v1.45-beta → auditoría / CI (2026-08-31)

> **Padre:** [`traspaso-relevo-v1-45-paper-auto-position-2026-08-31.md`](./traspaso-relevo-v1-45-paper-auto-position-2026-08-31.md) · [`traspaso-relevo-tag-v1-44-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-44-beta-2026-08-31.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **TIP PUBLICADO** — tag `v1.45-beta` → `1627e9c9` · Release-tag CI **pending** tras push.  
> **Arranque auditor:** [`arranque-auditor-v1-45-beta-2026-08-31.md`](./arranque-auditor-v1-45-beta-2026-08-31.md).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · Lab retrofit · OCO · auto-promote · browser E2E · package bump.

---

## 0. Confirmación

Sobre tip `v1.44-beta` → `db346a11`:

| Pieza                       | Entrega                                              |
| --------------------------- | ---------------------------------------------------- |
| `ExecutePositionPolicyAuto` | Policy → JIT → protect \| Router reduce/exit         |
| Router qty                  | `resolve_exit_sell_quantity` (reduce/exit clamp)     |
| HTTP                        | `POST /position-automation/execute-auto` (+ dryRun)  |
| GP-AUTO-01 E2E              | pytest PAPER · env-off / stale / closed / protective |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no Lab SoT · package `1.35.0-beta`.

## 1. Release

| Pieza      | Valor                                                                                 |
| ---------- | ------------------------------------------------------------------------------------- |
| Tag tip    | `v1.45-beta` → `1627e9c9`                                                             |
| Código     | `1627e9c9` `feat(v1.45): PAPER AUTO position — Policy + JIT → protect\|Router reduce` |
| Previo tip | `v1.44-beta` → `db346a11` (CI GREEN)                                                  |
| CI tag     | **pending**                                                                           |

## 2. Next

1. Release-tag CI GREEN → certify.
2. V1.46 Autonomous Paper Desk — solo tras tip certificado. NO LIVE.
