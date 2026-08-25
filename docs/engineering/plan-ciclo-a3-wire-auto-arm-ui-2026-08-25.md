# Plan — Ciclo A3-wire: armado AUTO UI obligatorio (honesty BETA-D)

> **Padre:** [ADR-023](../adr/023-camino-d-thaw.md) Accepted **BETA-D** · [camino-d-a2-a5-prep](./camino-d-a2-a5-prep-2026-08-04.md) A3 · relevo post-E1 [`traspaso-relevo-cierre-post-e1-2026-08-25.md`](./traspaso-relevo-cierre-post-e1-2026-08-25.md).  
> **AsOf:** 2026-08-25 · HEAD **`2a9e575`** (= origin/main).  
> **Estado:** **PROPUESTO** — D1–D8 pendientes de aprobación del propietario.  
> **Método:** honesty UI thin (mismo espíritu I3/RX1); **no** broker · **no** Accept estricto · Ranking ≠ BUY · I1/I3/RX1 intactos.  
> **Nombre:** **A3-wire** = cablear el armado local A3 al panel Operativa tras thaw UI on.

---

## 0. Objetivo

Tras BETA-D, la pill **Auto** en `DemoBookModePanel` es seleccionable (`DEMO_BOOK_AUTO_UI_ENABLED=true`) pero **salta** la doble confirmación:

- Existe helper A3: `demo-book-auto-arm.ts` (`tryArmAuto` · frase exacta `ACTIVAR AUTO` · localStorage).
- Tests unitarios del helper: verdes.
- **Gap:** el panel hace `update({ mode: "auto" })` **sin** exigir `loadAutoArm().armed`.

ADR-023 §Decisión.4: _«Doble confirmación UI (armado local) obligatoria antes de modo AUTO efectivo»_. Hoy el claim P8/A3 del producto BETA está **deshonesto** en UI.

**A3-wire = fail-closed UI:** no persistir `mode:auto` hasta armado OK; desarmar al salir de Auto; sin tocar execute server / `PAPER_D_EXECUTE`.

---

## 1. Hallazgo operativo (contexto, no alcance)

Operativa DEMO 2026-08-25 (post opt-in):

| Hecho         | Detalle                                                                                     |
| ------------- | ------------------------------------------------------------------------------------------- |
| Env           | `paperDExecuteEnv=true` · kill off                                                          |
| SEMI          | 1× Confirm seed (`DSS-211d7e0be9b3`) · `action=wait` → **sin fill** · P2 `confirm_seed` 0→1 |
| AUTO UI       | Vite up; arm phrase **no cableada**; Playwright/Chrome ausente                              |
| Seed policies | 0 `paper_auto` en seed (Camino D execute sin policy)                                        |

**Fuera de este ciclo (park):** bootstrap policy `paper_auto` seed · expectancy/trail/bracket **plena** · Wyckoff Alembic · Accept estricto · inventar `recommend_long`.

---

## 2. Decisiones (aprobar D1–D8)

| Id     | Pregunta                              | Propuesta                                                                                                                                                                                           |
| ------ | ------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | ¿Obligar armado antes de `mode:auto`? | **Sí.** Click Auto sin armed → UI de armado (input frase); solo `tryArmAuto` OK → `patchDemoBookPrefs({ mode: "auto" })`.                                                                           |
| **D2** | ¿Dónde vive el armado?                | **En** `DemoBookModePanel` (+ status bar si también setea auto). Reutilizar `demo-book-auto-arm.ts`; **no** nuevo storage.                                                                          |
| **D3** | ¿Al salir de Auto?                    | **Disarm** (`disarmAutoArm`) al pasar a manual/semi **o** al desmarcar Auto. Armado no sobrevive «de por vida» tras salir.                                                                          |
| **D4** | ¿Server / execute?                    | **No.** Sin Alembic · sin `contract:gen` · sin cambiar gates I1/I3/RX1 · sin flip default `PAPER_D_EXECUTE`. Arm ≠ execute.                                                                         |
| **D5** | ¿Status bar pill Auto?                | **Misma regla:** no setear `auto` sin armed; si el bar solo refleja prefs, exigir arm en el único write-path (`patchDemoBookPrefs` guard opcional). Preferir guard en `patchDemoBookPrefs` / panel. |
| **D6** | ¿Copy / footer?                       | Actualizar footer/tooltip si aún dicen prep-only; mencionar frase `ACTIVAR AUTO` + env opt-in.                                                                                                      |
| **D7** | ¿Tests?                               | Vitest: panel/prefs — Auto click sin arm no persiste auto; phrase exacta arma + setea auto; phrase mala no; salir de auto desarma. Helper tests intactos.                                           |
| **D8** | ¿Docs / stamp?                        | Plan + relevo + stamp `CURRENT_SYSTEM` / checklist A3 «wired» · engineering-index. Push solo si el propietario lo pide.                                                                             |

---

## 3. Fuera de alcance

- Broker live · Accept estricto · inventar buys/confirms SQL.
- Crear `execution-policies` `paper_auto` en seed.
- Wire Exit Radar / Trail → auto-exit.
- Playwright E2E (opcional smoke manual owner).
- Redis/worker_arq degraded (ops, no este ciclo).

---

## 4. Arranque (tras D1–D8 OK)

```text
Implementar Ciclo A3-wire según plan-ciclo-a3-wire-auto-arm-ui-2026-08-25.md.
D1=arm obligatorio · D2=panel+helper · D3=disarm al salir · D4=no server execute.
No broker · no Accept estricto · I1/I3/RX1 intactos · PAPER_D_EXECUTE default repo off.
```

---

## 5. Definition of done

- [ ] No se puede quedar `prefs.mode === "auto"` sin `loadAutoArm().armed === true` en el camino UI.
- [ ] Frase exacta `ACTIVAR AUTO` arma; otra frase no.
- [ ] Salir a manual/semi desarma.
- [ ] Vitest del panel/prefs verdes · `pnpm test:decision-spine` intacto (159).
- [ ] Stamp docs + relevo.

---

## 6. Freeze residual

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · broker **no** · estricto deuda abierta · W2–W4 · arm UI ≠ permiso server · I1/I3/RX1 intactos.
