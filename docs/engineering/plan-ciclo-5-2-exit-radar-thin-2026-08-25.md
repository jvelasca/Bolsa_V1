# Plan — Ciclo 5.2 Exit Radar thin (trail / time-stop / exit hint advisory)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §5–6 (Exit Radar / trailing / time-stop parked; **esta** rebanada abre solo Exit Radar **advisory thin**) · relevo [`traspaso-relevo-ciclo-5-1-protect-t1-thin-2026-08-25.md`](./traspaso-relevo-ciclo-5-1-protect-t1-thin-2026-08-25.md) §4 E1 · síntesis subagente AS-IS 2026-08-25.
> **AsOf:** 2026-08-25 · HEAD **`50004da`** = `origin/main`; feat **`e813aa3`**.
> **Estado:** **CERRADO en origin** (`e813aa3` vía `50004da`). D1–D8 OK · batería **130**.
> **Método:** espejo 5.0/5.1; Ranking ≠ BUY; sin Alembic; sin `contract:gen`; sin LLM; **sin** auto-exit; **sin** EvaluatePositionExits; **sin** ExecuteTrade converge.
> **Secuencia:** 5.0 F ✅ · 5.1 E ✅ · **5.2 (este)** · MFE / 5.x cierre · luego integridad.

---

## 0. Objetivo

Tras Protect/T1 (5.1), falta la proyección de **salida condicional** (trail / time-stop / exit hint) sin motor de ejecución. PositionPolicy `EvaluatePositionExits` es Lab/estrategia — **no** cablear. Confirm ya cierra con firma humana si `action=exit_hint|reduce`.

**Ciclo 5.2 = advisory read-only:** mapper `exitRadar` + eco runtime/Board/Hoy («Salida»). Compone señales ya vivas (protectPlan MFE, thesisHealth hint, `expiresAt`, T1) en un hint unificado. **No** muta stop, **no** ejecuta.

### Qué entra vs qué queda fuera

| Incluye (thin 5.2)                                                                                         | Excluye                                                |
| ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Mapper `mapExitRadar` / `map_exit_radar`: status `none` \| `trail_hint` \| `time_stop_hint` \| `exit_hint` | Wire `EvaluatePositionExits` / `full_auto`             |
| `suggestedTrailStop` tip (p.ej. entry+0.5R si MFE≥1.5R) — **no** escribe `structuralStop`                  | Trail continuo broker · time-stop auto-flat · bracket  |
| Eco `runtime.exitRadar` + Hoy «Salida»                                                                     | Auto-Confirm `exit_hint` · mutate stop                 |
| Reusar inputs 5.0/5.1 + `expiresAt` del TradePlan si hay                                                   | MFE expectancy plena · Alembic · `contract:gen`        |
| Tests + stamp + relevo 5.2                                                                                 | ExecuteTrade converge · Shadow AUTO · Actionability/IO |

**Frontera:** Exit Radar 5.2 ≠ permiso. Advisory ≠ BUY. Distinto de cola Hoy `REVIEW` (EXPIRED) y de thesis `review`.

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                                   | Propuesta por defecto                                                                                                                |
| --- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| D1  | ¿Alcance?                                  | **Advisory thin:** mapper + surface. **No** auto-exit ni PositionPolicy.                                                             |
| D2  | ¿Prioridad de status?                      | Si varios aplican: `exit_hint` > `time_stop_hint` > `trail_hint` > `none`.                                                           |
| D3  | ¿Cuándo `trail_hint`?                      | MFE ≥ **1.5R** (vía mismos inputs que protectPlan) → `suggestedTrailStop = entry + sign×0.5×R`. Sin mutar stop.                      |
| D4  | ¿Cuándo `time_stop_hint`?                  | `expiresAt` presente y `now >= expiresAt` (o lastClose session past expiry string). Sin expiry → no inventar.                        |
| D5  | ¿Cuándo `exit_hint`?                       | thesisHealth.hint ∈ {exit, reduce} **o** (long: lastClose ≥ target1; short: simétrico) si hay target1 del protectPlan. Display only. |
| D6  | ¿`check_opening` / ExecuteTrade / Confirm? | **Intactos.** No auto-firmar cierres.                                                                                                |
| D7  | ¿Alembic / `contract:gen`?                 | **No.** JSONB `runtime.exitRadar`.                                                                                                   |
| D8  | ¿Cierre / siguiente?                       | Stamp + relevo. E1 = **MFE thin** o cierre línea 5.x crecimiento → integridad ExecuteTrade.                                          |

Si D1 incluye auto-exit / EvaluatePositionExits / mutar stop: **parar y replanificar**.

---

## 2. Diseño (borrador)

```text
# inputs (de plan vivo + 5.0/5.1)
entry, stop, direction, lastClose, expiresAt?
thesisHealth.hint?, protectPlan.{rMultiple,target1}?

R = |entry-stop|
mfeR = ...

# rules (priority)
exit_hint     if thesis hint in {exit,reduce} OR price beyond target1
time_stop_hint if expiresAt past
trail_hint    if mfeR >= 1.5
else none

# output
exitRadar = {
  status, suggestedTrailStop?, why: [...],
  target1?: from protect or recompute
}
# Hoy: «Salida» if status != none
```

---

## 3. Arranque (tras OK D1–D8)

```text
Implementar Ciclo 5.2 Exit Radar thin según este plan.
D1=advisory · D2=prioridad exit>time>trail · D3=trail @1.5R · D4=time_stop por expiresAt · D5=exit por thesis/T1 · D6=fill intacto · D7=JSONB · D8=stamp; E1=MFE o cierre 5.x.
No EvaluatePositionExits · no auto-exit · no mutar stop · no ExecuteTrade · no LLM.
```

---

## 4. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · 5.0/5.1 intactos · advisory ≠ permiso · integridad ExecuteTrade **parked**.
