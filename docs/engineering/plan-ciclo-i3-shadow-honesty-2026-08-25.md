# Plan — Ciclo I3 Shadow honesty (integridad, **sin thaw**)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §6 · [ADR-023](../adr/023-camino-d-thaw.md) (**Proposed**, P1–P10 vacíos) · relevo [`traspaso-relevo-ciclo-i3-shadow-honesty-2026-08-25.md`](./traspaso-relevo-ciclo-i3-shadow-honesty-2026-08-25.md) · cierre I2 [`traspaso-relevo-ciclo-i2-actionability-io-2026-08-25.md`](./traspaso-relevo-ciclo-i2-actionability-io-2026-08-25.md).
> **AsOf:** 2026-08-25 · origin **`05e354c`**; feat I3 **`26901aa`** (local, no push).
> **Estado:** **CERRADO en `26901aa`.** D1–D8 OK. **No thaw.**
> **Método:** integridad thin; Ranking ≠ BUY; Shadow **off**; sin broker; I1/I2 intactos.
> **Nombre:** I3 = cerrar bypass AUTO **sin** thaw Camino D.

---

## 0. Objetivo

**I3 = fail-closed HTTP `paper_auto`** (`/route` + scan-execute) con el mismo env que Paper D. No encender AUTO. No fusionar Router con Confirm.

---

## 1. Decisiones (D1–D8 OK)

| Id  | Decisión                                                                                                                    |
| --- | --------------------------------------------------------------------------------------------------------------------------- |
| D1  | **No thaw.** Flag default off. ADR-023 sigue Proposed.                                                                      |
| D2  | HTTP `paper_auto` (`/route` + scan-execute): `require_http_paper_auto_env`. `inform_only` / `alert` / `live_auto` intactos. |
| D3  | **No** fusionar `ExecutionRouter` con `allow_opening_fill`. Gate **fuera** del Router (spine no toca el env).               |
| D4  | Tracker alarms y exits `full_auto` **fuera**.                                                                               |
| D5  | Sin Alembic / `contract:gen` / broker. Veto HTTP = 403 `paper_auto_env_blocked`.                                            |
| D6  | `PAPER_D_EXECUTE` **off**.                                                                                                  |
| D7  | Pytest helper (no spine battery).                                                                                           |
| D8  | Stamp + relevo. E1 = park thaw real (checklist) · expectancy · trail · bracket. Push explícito.                             |

---

## 2. Arranque (hecho)

```text
Implementar Ciclo I3 Shadow honesty según este plan.
D1=no thaw · D2=gate env HTTP paper_auto · D3=no fusionar Router · D6=flag off.
No PAPER_D_EXECUTE on · no broker · no reabrir I1/I2 · no LLM.
```

---

## 3. Commits

| SHA       | Mensaje                                                 |
| --------- | ------------------------------------------------------- |
| `26901aa` | feat(spine): ADR-031 Ciclo I3 Shadow honesty (no thaw). |

## 4. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · advisory 5.x ≠ permiso · `PAPER_D_EXECUTE` off · I1 `check_opening` intacto · I2 IO ≠ permiso.
