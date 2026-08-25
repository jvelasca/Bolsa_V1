# RELEVO — Cierre línea integridad I1–I3 (2026-08-25)

> **Padre:** [`traspaso-relevo-ciclo-i3-shadow-honesty-2026-08-25.md`](./traspaso-relevo-ciclo-i3-shadow-honesty-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **HEAD origin:** `05e354c`. Feat I3 **`26901aa`** · stamp **`95e4720`** (local, no push). `main` ahead de origin (I1+I2+I3).
> **Estado:** **LÍNEA INTEGRIDAD I1–I3 CERRADA.** No hay I4 automático.
> **Arranque chat nuevo:** este fichero + `CURRENT_SYSTEM.md` + ADR-031 §6.

---

## 0. Por qué se cierra aquí

Tras crecimiento 5.x, integridad era **cerrar huecos de execute / honestidad de señales**, no encender AUTO.

| Ciclo | Qué                                                                              | SHA (feat) |
| ----- | -------------------------------------------------------------------------------- | ---------- |
| I1    | HTTP ledger buy → `check_opening` (sell skip). Router no fusionado.              | `2bd5cd8`  |
| I2    | Fórmula IO server (chip). Rank Estudio cliente. IO ≠ permiso.                    | `e31840d`  |
| I3    | HTTP `paper_auto` (`/route`, scan-execute) → mismo env que Paper D. **No thaw.** | `26901aa`  |

No queda un bypass HTTP de **apertura paper** al nivel de I1/I3. Seguir con «I4» por inercia sería thaw o reabrir 5.x.

## 1. Qué queda (no es el siguiente por defecto)

| Tema                                        | Por qué no es I4 automático                                                          |
| ------------------------------------------- | ------------------------------------------------------------------------------------ |
| Thaw Camino D / `PAPER_D_EXECUTE=1`         | ADR-023 **Proposed**, P1–P10 vacíos. Solo con la palabra **thaw** + checklist.       |
| Exits `full_auto` → Router                  | I3 D4 **park**. Es auto-salida, no el hueco de apertura HTTP.                        |
| Fusionar `ExecutionRouter` con Confirm/Fill | I1 D3 / I3 D3 **no**. Knobs AUTO distintos.                                          |
| Expectancy / trail / bracket                | Crecimiento parked (5.x **cerrada**). Fase nueva si se pide, no «seguir integridad». |
| `TRUSTED_PROXIES` / secret scanning UI      | Ops, no código de ciclo.                                                             |
| **Push** `origin/main`                      | `main` local **ahead**; decisión explícita (**push**).                               |

## 2. E1 — fork (el dueño elige)

1. **Push** I1–I3 a origin (si se pide).
2. Ops-only: `TRUSTED_PROXIES` · secret scanning UI.
3. Residual integridad **solo si se nombra:** exits `full_auto` / `EvaluatePositionExits` (no auto-exit por «seguimos»).
4. Crecimiento **solo si se nombra:** expectancy plena · trail · bracket (plan D1–D8, no reabrir Wyckoff/5.x por defecto).
5. **Thaw AUTO** solo con «thaw» + ADR-023 / checklist. Un «seguimos» **no** basta.

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO **off** · `PAPER_D_EXECUTE` **off** · advisory 5.x ≠ permiso · I1 `check_opening` intacto · I2 IO ≠ permiso · I3 gate HTTP ≠ thaw.
