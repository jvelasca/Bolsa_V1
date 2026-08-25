# Plan — Ciclo I3 Shadow honesty (integridad, **sin thaw**)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §6 · [ADR-023](../adr/023-camino-d-thaw.md) (**Proposed**, P1–P10 vacíos) · relevo [`traspaso-relevo-ciclo-i3-shadow-honesty-2026-08-25.md`](./traspaso-relevo-ciclo-i3-shadow-honesty-2026-08-25.md) · cierre I2 [`traspaso-relevo-ciclo-i2-actionability-io-2026-08-25.md`](./traspaso-relevo-ciclo-i2-actionability-io-2026-08-25.md).
> **AsOf:** 2026-08-25 · origin **`05e354c`**; local I2 **`e31840d`** / stamp **`cfc8042`** / update-last **`a4762e8`** (6 commits ahead; **no push**).
> **Estado:** **D1–D8 BORRADOR — esperar OK.** Sin código I3. **No** flip `PAPER_D_EXECUTE`.
> **Método:** integridad thin; Ranking ≠ BUY; Shadow **off**; sin broker; I1/I2 intactos.
> **Nombre:** I3 = cerrar bypass AUTO **sin** thaw Camino D. Thaw real = ADR-023 Accepted + checklist, no este ciclo.

---

## 0. Objetivo

I1 cerró `POST /portfolio/trade`. Paper D execute **sí** mira `PAPER_D_EXECUTE`. Otros HTTP llegan al `ExecutionRouter` **sin** ese env → pueden fill `paper_auto` con el flag off.

**I3 = fail-closed de esos bypass.** No encender AUTO. No fusionar Router con Confirm.

### AS-IS (hechos)

| Puerto          | Path                                                              | `PAPER_D_EXECUTE`                                                                       |
| --------------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Paper D execute | `ProposePaperDPlan` (`execute=true`)                              | **Sí** → `blocked_env` si off (`test_execute_blocked_without_env`)                      |
| HTTP route      | `POST /execution-policies/{id}/route` → `ExecutionRouter.execute` | **No**                                                                                  |
| HTTP scan       | `POST /scans/jobs/{id}/execute` → `ExecuteScanJobHits` → Router   | **No**                                                                                  |
| Tracker alarms  | `route_tracker_alarms`                                            | N/A — solo `inform_only` / `alert` (`ALARM_SAFE_MODES`)                                 |
| Router spine    | `ExecutionRouter._execute_paper_trade`                            | Extra knobs AUTO; `check_opening` si `_enforce_cognitive_gate`. **No fusionar** (I1 D3) |
| Exits           | `PositionExitEvaluator` `full_auto` → Router                      | Fuera de I3 (no apertura)                                                               |

ADR-023 **Proposed**. Checklist P1–P5 ☐. Libro AUTO pill = prep, no flip de env. `live_auto` = dry-run (sin broker).

### Qué entra vs qué queda fuera

| Incluye (thin I3, si OK)                                    | Excluye                                              |
| ----------------------------------------------------------- | ---------------------------------------------------- |
| Gate env (o veto) en HTTP `paper_auto` route + scan-execute | Flip `PAPER_D_EXECUTE` · ADR-023 Accepted · broker   |
| Tests fail-closed flag off                                  | Fusionar ExecutionRouter · I1/I2 reopen              |
| Docs honesty cadena                                         | Expectancy · trail · bracket · EvaluatePositionExits |

**Parar y replanificar si:** D1 incluye thaw, auto-execute sin flag, o quitar `check_opening` del Router.

---

## 1. Decisiones (D1–D8 — **BORRADOR, esperar OK**)

| Id  | Propuesta (default)                                                                                                                 |
| --- | ----------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **No thaw.** Flag default off. ADR-023 sigue Proposed.                                                                              |
| D2  | HTTP `paper_auto` (`/route` + scan-execute): mismo gate env que Paper D (fail-closed si off). `inform_only` / `alert` intactos.     |
| D3  | **No** fusionar `ExecutionRouter` con `allow_opening_fill`. Spine Confirm/Fill/HTTP I1 intactos.                                    |
| D4  | Tracker alarms y exits `full_auto` **fuera** (park).                                                                                |
| D5  | Sin Alembic / `contract:gen` / broker. Veto HTTP = 403 (o status Paper D `blocked_env` si el contrato del route ya es 200+payload). |
| D6  | `PAPER_D_EXECUTE` **off**. Sin `PAPER_D_ACCOUNT_ID` de producto.                                                                    |
| D7  | Tests: `paper_auto` HTTP/use-case sin env → bloqueado; inform/alert OK. Spine battery solo si se toca Router (evitar si se puede).  |
| D8  | Stamp + relevo. E1 = park thaw real (checklist) · expectancy · trail · bracket. Push explícito. Ops-only `TRUSTED_PROXIES`.         |

**Alternativa D2 (si el gate-in en `/route` se ve gordo):** 403/410 solo `paper_auto` en esos dos HTTP; inform/alert vivos. Decir explícito.

---

## 2. Arranque (tras OK)

```text
Implementar Ciclo I3 Shadow honesty según este plan.
D1=no thaw · D2=gate env HTTP paper_auto · D3=no fusionar Router · D6=flag off.
No PAPER_D_EXECUTE on · no broker · no reabrir I1/I2 · no LLM.
```

---

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · advisory 5.x ≠ permiso · `PAPER_D_EXECUTE` off · I1 `check_opening` intacto · I2 IO ≠ permiso.
