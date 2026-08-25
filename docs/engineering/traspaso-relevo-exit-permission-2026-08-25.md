# RELEVO — ExitPermission · 2026-08-25

> **Padre:** [`plan-exit-permission-2026-08-25.md`](./plan-exit-permission-2026-08-25.md) · roadmap [`roadmap-v19-operational-core-2026-08-25.md`](./roadmap-v19-operational-core-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **CÓDIGO LISTO.** Spine **217**. Cadena post-entrada modelada hasta permiso. Cambiar de chat recomendado para SEMI / tag `v1.9-beta` / wire.
> **Arranque chat nuevo:** este fichero + plan ExitPermission + ADR-032 §4 + `CURRENT_SYSTEM.md` + roadmap v1.9.

---

## 0. Qué quedó hecho

| Pieza                                               | Estado       |
| --------------------------------------------------- | ------------ |
| `checkExitPermission` / `check_exit_permission`     | **Hecho**    |
| ALLOW accionable; DENY reasons canónicas            | **Hecho**    |
| RX1 honesty `paper_auto_env_blocked`                | **Hecho**    |
| Wire Confirm / EvaluatePositionExits / ExecuteTrade | **No**       |
| Fusionar con `check_opening`                        | **No**       |
| Auto-exit producto / broker                         | **No**       |
| HELP ExitPermission ≠ check_opening                 | **Hecho**    |
| F1–F4 / INFRA                                       | **Intactos** |

## 1. Freeze / flags

- `PAPER_D_EXECUTE` **off**. Broker **no**.
- ExitPermission ALLOW ≠ ExecuteTrade ≠ auto-exit.
- `check_opening` (apertura) **intacto**.

## 2. E1 — fork (chat nuevo)

1. **Opción A:** operar **SEMI** (no reabrir thin).
2. **Opción B:** owner tag **`v1.9-beta`** (Release tag CI debe GREEN).
3. **Opción C:** plan wire ExitPermission→ExecutionPlan PAPER (fase explícita; aún ≠ broker).
4. **No** broker adapter. **No** ActionabilityScore. **No** auto-exit producto.

## 3. Docs clave

- [`plan-exit-permission-2026-08-25.md`](./plan-exit-permission-2026-08-25.md)
- ADR-032 · `CURRENT_SYSTEM.md` · roadmap v1.9
