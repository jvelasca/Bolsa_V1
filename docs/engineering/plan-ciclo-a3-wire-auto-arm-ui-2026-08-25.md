# Plan — Ciclo A3-wire: armado AUTO UI obligatorio (honesty BETA-D)

> **Padre:** [ADR-023](../adr/023-camino-d-thaw.md) Accepted **BETA-D** · [camino-d-a2-a5-prep](./camino-d-a2-a5-prep-2026-08-04.md) A3 · relevo post-E1 [`traspaso-relevo-cierre-post-e1-2026-08-25.md`](./traspaso-relevo-cierre-post-e1-2026-08-25.md).  
> **AsOf:** 2026-08-25 · feat **`d704263`**.  
> **Estado:** **CERRADO** — D1–D8 OK (aprobados propietario).  
> **Método:** honesty UI thin; **no** broker · **no** Accept estricto · Ranking ≠ BUY · I1/I3/RX1 intactos.  
> **Nombre:** **A3-wire** = cablear el armado local A3 al panel Operativa tras thaw UI on.

---

## 0. Objetivo

Tras BETA-D, la pill **Auto** era seleccionable pero **saltaba** la doble confirmación ADR-023. Helper A3 existía (`tryArmAuto` · `ACTIVAR AUTO`); el panel hacía `mode:auto` directo.

**A3-wire = fail-closed UI:** no persistir `mode:auto` hasta armado OK; desarmar al salir de Auto; sin tocar execute server / `PAPER_D_EXECUTE`.

---

## 1. Decisiones (D1–D8 OK)

| Id  | Decisión                                                                     |
| --- | ---------------------------------------------------------------------------- |
| D1  | Arm obligatorio antes de `mode:auto`.                                        |
| D2  | Armado en `DemoBookModePanel` + helper `demo-book-auto-arm.ts`.              |
| D3  | Disarm al pasar a manual/semi (`patchDemoBookPrefs`).                        |
| D4  | No server / Alembic / `contract:gen` / flip default env. Arm ≠ execute.      |
| D5  | Guard en `normalizeDemoBookPrefs` + `patchDemoBookPrefs` (write-path único). |
| D6  | Tooltip/footer mencionan `ACTIVAR AUTO` + `PAPER_D_EXECUTE`.                 |
| D7  | Vitest prefs + panel (15 tests A3-related).                                  |
| D8  | Plan + relevo + stamp SoT / index.                                           |

---

## 2. Commits

| SHA       | Mensaje                                                       |
| --------- | ------------------------------------------------------------- |
| `10e60dc` | docs: propose Ciclo A3-wire                                   |
| `d704263` | feat(ui): A3-wire mandatory AUTO arm phrase (BETA-D honesty). |
| _(stamp)_ | docs: stamp living SoT after Ciclo A3-wire.                   |

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · broker **no** · estricto deuda · arm UI ≠ permiso server · I1/I3/RX1 intactos.
