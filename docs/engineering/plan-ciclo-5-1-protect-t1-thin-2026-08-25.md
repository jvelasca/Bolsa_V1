# Plan — Ciclo 5.1 Protect / T1 thin (Golden E advisory)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §5 Golden **E** · §6 (trailing / T1 / Exit Radar parked; **esta** rebanada abre solo Protect/T1 **advisory thin**) · relevo [`traspaso-relevo-ciclo-5-thesis-health-thin-2026-08-25.md`](./traspaso-relevo-ciclo-5-thesis-health-thin-2026-08-25.md) §4 E1 · síntesis subagente AS-IS Golden E 2026-08-25.
> **AsOf:** 2026-08-25 · HEAD local post-implementación Ciclo 5.1; previo **`8fa8b7e`** = `origin/main`.
> **Estado:** **CÓDIGO LISTO — pendiente commit** (D1–D8 OK · batería **125**).
> **Método:** rebanada fina crecimiento; Ranking ≠ BUY; sin Alembic; sin `contract:gen`; sin LLM; **sin** mutar structuralStop; **sin** ExecuteTrade converge.
> **Secuencia dueño:** 5.0 F ✅ · **5.1 E (este)** · 5.2+ Exit/trail · MFE · luego integridad.

---

## 0. Objetivo

ADR-031 Golden **E**: _posición ganadora T1 → protección / trail_. En código no hay T1/protect/trail en TradePlan; solo `structuralStop` (compute-once) y `minTakeProfitRMultiple` en policy (declarado, **no** leído por PolicyGate). PositionPolicy exits = otro motor — **no** mezclar.

**Ciclo 5.1 = advisory read-only** (espejo 5.0): calcular T1 sintético + hint de protección cuando el precio ha recorrido ≥ N×R a favor; eco en `runtime` / Board / Hoy. **No** muta `structuralStop`, **no** ejecuta, **no** trail.

### Qué entra vs qué queda fuera

| Incluye (thin 5.1)                                                                                    | Excluye (→ 5.2+ / integridad)                          |
| ----------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Mapper `mapProtectPlan` / `map_protect_plan`: R = \|entry−stop\|; T1 = entry ± k×R; protect si MFE≥1R | Mover / reescribir `structuralStop` en sesión o broker |
| Campo advisory `protectPlan` en runtime (JSONB; no ladder TradePlan)                                  | Trailing continuo · time-stop · bracket · partial fill |
| Surface Hoy/Board: chip «Proteger» / línea T1 cuando `status=protect_hint`                            | Wire `EvaluatePositionExits` · Confirm auto-exit       |
| Umbral k desde `minTakeProfitRMultiple` de plantilla **o** default 1.0 (solo cálculo; no gate fill)   | Nueva regla PolicyGate en `check_opening`              |
| Tests Golden-E-shaped (mapper) + Hoy surface                                                          | MFE/MAE expectancy plena · Alembic · `contract:gen`    |
| Docs stamp + relevo 5.1; ADR-031 nota «5.1 advisory; trail/PM siguen parked»                          | ExecuteTrade converge · Shadow AUTO · Wyckoff          |

**Frontera:** Protect 5.1 ≠ permiso. Advisory ≠ BUY. No confundir con thesis `review` (5.0) ni cola Hoy `REVIEW` (EXPIRED).

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                                   | Propuesta por defecto                                                                                                                                                 |
| --- | ------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | ¿Alcance de **esta** rebanada?             | **Solo Golden E advisory thin:** mapper T1+protect hint + surface. **No** trail continuo ni exit parcial.                                                             |
| D2  | ¿Definición de 1R / T1?                    | `R = \|entry − structuralStop\|`. `target1 = entry + sign(dir)×k×R` con **k = 1.0** default (opcional leer `minTakeProfitRMultiple` si hay policy a mano en propose). |
| D3  | ¿Cuándo `protect_hint`?                    | Long: `lastClose >= entry + 1×R` (MFE≥1R). Short: simétrico. Sin entry/stop/close → no inventar.                                                                      |
| D4  | ¿Mutar `structuralStop` a breakeven?       | **No.** Solo hint `suggestedProtectStop = entry` (o entry±tick) en el advisory. Stop canónico intacto.                                                                |
| D5  | ¿Campo en TradePlan tipado?                | **No.** JSONB `runtime.protectPlan` (como `thesisHealth`). Sin `contract:gen`.                                                                                        |
| D6  | ¿`check_opening` / Confirm / ExecuteTrade? | **Intactos.**                                                                                                                                                         |
| D7  | ¿Alembic / qty abierta?                    | **No** Alembic. Qty abierta opcional (5.0b-style); surface también sobre plan vivo sin qty.                                                                           |
| D8  | ¿Cierre / siguiente?                       | Stamp + relevo 5.1. E1 = **5.2 Exit Radar thin** o refinamiento trail — **no** integridad ExecuteTrade aún.                                                           |

Si D1 incluye trail/auto-exit, D4 = mutar stop en runtime, o D6 toca fill: **parar y replanificar**.

---

## 2. Alcance (sí / no)

### Sí

| Pieza     | Regla                                                                                                   |
| --------- | ------------------------------------------------------------------------------------------------------- |
| Mapper    | TS + Python espejo: `{ status: none\|protect_hint, target1, suggestedProtectStop?, rMultiple?, why[] }` |
| Propose   | Escribe `runtime.protectPlan` junto a `thesisHealth` si hay entry+stop+lastClose                        |
| Board/Hoy | Echo + dialog «Proteger» / T1 cuando `protect_hint`                                                     |
| Tests     | Golden E mapper + Board echo + Hoy UI                                                                   |
| Docs      | CURRENT_SYSTEM · ADR-031 · index · relevo                                                               |

### No

- Trail / time-stop / bracket / partial T1 fill
- Mutar `structuralStop` · Position Manager execute
- PolicyGate nuevo · `check_opening` · ExecuteTrade
- MFE expectancy · Shadow AUTO · Wyckoff · Alembic · `contract:gen`

---

## 3. Diseño (borrador)

```text
# inputs
entry, structuralStop, direction, lastClose
k = 1.0  # or minTakeProfitRMultiple if cheap

R = abs(entry - structuralStop)
target1 = entry + sign * k * R
mfeR = (lastClose - entry) / R * sign   # long sign=+1

# output (advisory; no TradePlan.status)
protectPlan = {
  status: "protect_hint" if mfeR >= 1 else "none",
  target1,
  suggestedProtectStop: entry,   # tip only; structuralStop unchanged
  rMultiple: mfeR,
  why: ["mfe_ge_1r"] | []
}

# surface Hoy: «Proteger» if protect_hint
# no ExecuteTrade · no check_opening
```

---

## 4. Arranque (tras OK D1–D8)

```text
Implementar Ciclo 5.1 Protect/T1 thin según este plan.
D1=Golden E advisory · D2=R+T1 k=1 · D3=MFE≥1R → protect_hint · D4=sin mutar structuralStop · D5=JSONB protectPlan · D6=check_opening intacto · D7=sin Alembic · D8=stamp; E1=5.2.
No trail · no auto-exit · no MFE plena · no ExecuteTrade · no LLM.
```

---

## 5. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · advisory ≠ permiso · 5.0 Thesis Health intacto · integridad ExecuteTrade **parked**.
