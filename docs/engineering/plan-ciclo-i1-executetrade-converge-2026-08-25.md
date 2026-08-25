# Plan — Ciclo I1 ExecuteTrade converge (integridad)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) · relevo [`traspaso-relevo-ciclo-i1-executetrade-converge-2026-08-25.md`](./traspaso-relevo-ciclo-i1-executetrade-converge-2026-08-25.md) · honesty Ciclo 7 (mapa 3+1) · cierre crecimiento 5.0–5.3.
> **AsOf:** 2026-08-25 · origin **`05e354c`**; feat I1 **`2bd5cd8`** · stamp **`8fce269`** (local, no push).
> **Estado:** **CERRADO en `2bd5cd8`.** D1–D8 OK · batería **144**.
> **Método:** integridad thin; Ranking ≠ BUY; sin Shadow AUTO; sin broker; sin reabrir 5.x.
> **Secuencia dueño:** crecimiento 5.x ✅ · **I1 (este)** · I2 Actionability · I3 Shadow (explícito).

---

## 0. Objetivo

Hoy hay **3** call-sites spine a `ExecuteTrade` (Confirm · ExecutionRouter · FillPendingOrder) + **1** HTTP `POST /portfolio/trade`.

**I1 = cerrar el bypass / unificar permiso pre-fill** sin reescribir el ledger ni encender AUTO.

### Qué entra vs qué queda fuera

| Incluye (thin I1)                                                    | Excluye                                      |
| -------------------------------------------------------------------- | -------------------------------------------- |
| Inventario AS-IS de los 4 puertos + tests de regresión               | Shadow AUTO / `PAPER_D_EXECUTE`              |
| Fail-closed o re-route del HTTP crudo vía mismo gate que aperturas   | Broker live · money path real                |
| Docs + batería spine actualizada                                     | Actionability/IO server (I2)                 |
| Prefer helper compartido pre-fill si reduce duplicación sin big-bang | Expectancy · trail continuo · Wyckoff reopen |

**Parar y replanificar si:** D1 incluye auto-execute, Shadow thaw, o quitar `check_opening` de Confirm/Fill.

---

## 1. Decisiones (D1–D8 OK)

| Id  | Decisión                                                                                         |
| --- | ------------------------------------------------------------------------------------------------ |
| D1  | Cerrar bypass HTTP. Spine 3 intactos.                                                            |
| D2  | **Gate-in** (no 410). `OrderDialog` / instrument-detail siguen vivos.                            |
| D3  | Helper `allow_opening_fill` (Confirm + Fill + HTTP). **No** fusionar `ExecutionRouter`.          |
| D4  | `buy` → gate; `sell` → skip (misma política Fill). No auto-exit.                                 |
| D5  | Sin Alembic / `contract:gen`. Veto HTTP = 403 `risk_veto`.                                       |
| D6  | Shadow / `PAPER_D_EXECUTE` **off**.                                                              |
| D7  | Spine battery + tests helper/HTTP use-case. Integración API siembra mandato+barra si espera 200. |
| D8  | Stamp + relevo. E1 = **I2 Actionability**.                                                       |

---

## 2. Arranque (hecho)

```text
Implementar Ciclo I1 ExecuteTrade converge según este plan.
D1=cerrar bypass · D2=gate-in · D3=helper · D6=Shadow off · D8=stamp; E1=I2.
No Shadow · no broker · no reabrir 5.x · no LLM.
```

---

## 3. Commits

| SHA       | Mensaje                                                                         |
| --------- | ------------------------------------------------------------------------------- |
| `2bd5cd8` | feat(spine): ADR-031 Ciclo I1 ExecuteTrade converge.                            |
| `8fce269` | docs: stamp living SoT after Ciclo I1 (`2bd5cd8`) and open I2 Actionability/IO. |

## 4. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · advisory 5.x ≠ permiso · `PAPER_D_EXECUTE` off.
