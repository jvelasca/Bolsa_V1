# RELEVO — Ciclo A3-wire armado AUTO UI (2026-08-25)

> **Padre:** [`plan-ciclo-a3-wire-auto-arm-ui-2026-08-25.md`](./plan-ciclo-a3-wire-auto-arm-ui-2026-08-25.md) · [ADR-023](../adr/023-camino-d-thaw.md).  
> **AsOf:** 2026-08-25.  
> **Estado:** **CERRADO** — honesty UI BETA-D.  
> **Arranque chat nuevo:** este fichero + `CURRENT_SYSTEM.md` + ADR-023 + runbook deuda estricto.

---

## 0. Qué se hizo

| Pieza       | Resultado                                               |
| ----------- | ------------------------------------------------------- |
| Gap         | Pill Auto saltaba `ACTIVAR AUTO`                        |
| Guard prefs | `mode:auto` requiere `loadAutoArm().armed`              |
| Panel       | Form armado + frase exacta; cancel; badge «AUTO armado» |
| Disarm      | Salir a Manual/Semi limpia arm                          |
| Tests       | prefs + panel + copy · 15 verdes                        |
| Server      | Intactos I1/I3/RX1 · `PAPER_D_EXECUTE` opt-in           |

## 1. Freeze / no hacer

- Broker live · Accept estricto · inventar fills · reabrir Wyckoff/5.x plena por defecto.
- Arm UI ≠ execute: sigue haciendo falta `PAPER_D_EXECUTE=1` + kill off.

## 2. E1 — fork

1. Owner: Cuentas → Operativa → Auto → escribir `ACTIVAR AUTO` → Confirmar armado.
2. Seguir deuda P2 (SEMI Confirm fills seed) + P1 días.
3. Park: policy `paper_auto` seed · growth plena 8.x · Playwright E2E armado.

## 3. Docs

- Plan A3-wire · ADR-023 · `deuda-thaw-estricto-runbook-2026-08-25.md` · `CURRENT_SYSTEM.md`
