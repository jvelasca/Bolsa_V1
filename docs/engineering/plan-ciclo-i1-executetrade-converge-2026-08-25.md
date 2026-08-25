# Plan — Ciclo I1 ExecuteTrade converge (integridad)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) · relevo [`traspaso-relevo-ciclo-i1-executetrade-converge-2026-08-25.md`](./traspaso-relevo-ciclo-i1-executetrade-converge-2026-08-25.md) · honesty Ciclo 7 (mapa 3+1) · cierre crecimiento 5.0–5.3.
> **AsOf:** 2026-08-25 · HEAD tip **`05e354c`** = `origin/main` (post 5.3).
> **Estado:** **BORRADOR — pendiente D1–D8 propietario.**
> **Método:** integridad thin; Ranking ≠ BUY; sin Shadow AUTO; sin broker; sin reabrir 5.x.
> **Secuencia dueño:** crecimiento 5.x ✅ · **I1 (este)** · I2 Actionability · I3 Shadow (explícito).

---

## 0. Objetivo

Hoy hay **3** call-sites spine a `ExecuteTrade` (Confirm · ExecutionRouter · FillPendingOrder) + **1** HTTP crudo `POST /portfolio/trade` que **no** pasa `check_opening` (`CURRENT_SYSTEM` limitaciones).

**I1 = cerrar el bypass / unificar permiso pre-fill** sin reescribir el ledger ni encender AUTO.

### Qué entra vs qué queda fuera (propuesta)

| Incluye (thin I1)                                                    | Excluye                                      |
| -------------------------------------------------------------------- | -------------------------------------------- |
| Inventario AS-IS de los 4 puertos + tests de regresión               | Shadow AUTO / `PAPER_D_EXECUTE`              |
| Fail-closed o re-route del HTTP crudo vía mismo gate que aperturas   | Broker live · money path real                |
| Docs + batería spine actualizada                                     | Actionability/IO server (I2)                 |
| Prefer helper compartido pre-fill si reduce duplicación sin big-bang | Expectancy · trail continuo · Wyckoff reopen |

**Parar y replanificar si:** D1 incluye auto-execute, Shadow thaw, o quitar `check_opening` de Confirm/Fill.

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                                 | Propuesta por defecto                                                                 |
| --- | ---------------------------------------- | ------------------------------------------------------------------------------------- |
| D1  | ¿Alcance I1?                             | **Cerrar bypass** del `POST /portfolio/trade` (gate o deprecar). Spine 3 intactos.    |
| D2  | ¿HTTP crudo: gate-in o remove/deprecate? | **Gate-in** (mismo `check_opening` en aperturas) o 410/redirect a Confirm — elegir 1. |
| D3  | ¿Helper compartido pre-fill?             | Sí si thin (extrae duplicación Confirm/Fill); **no** fusionar Router en el mismo PR.  |
| D4  | ¿Cierres / exits por este puerto?        | Fuera de I1 o misma política que hoy (no inventar auto-exit).                         |
| D5  | ¿Alembic / `contract:gen`?               | **No** salvo schema obligatorio (preferir no).                                        |
| D6  | ¿Shadow / PAPER_D_EXECUTE?               | **Off.**                                                                              |
| D7  | ¿Tests?                                  | Spine battery + tests del puerto HTTP (fail-closed / gate).                           |
| D8  | ¿Cierre / siguiente?                     | Stamp + relevo. E1 = **I2 Actionability** o park.                                     |

---

## 2. Arranque (tras OK D1–D8)

```text
Implementar Ciclo I1 ExecuteTrade converge según este plan.
Primero: AS-IS de Confirm / ExecutionRouter / FillPendingOrder / POST /portfolio/trade.
D1=cerrar bypass · D6=Shadow off · D8=stamp; E1=I2.
No Shadow · no broker · no reabrir 5.x · no LLM.
```

---

## 3. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · advisory 5.x ≠ permiso · `PAPER_D_EXECUTE` off.
