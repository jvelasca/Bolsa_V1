# Plan — Ciclo 5.0 Thesis Health thin (Golden F advisory)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §5 Golden **F** · §6 (Position Manager / Thesis Health / Exit Radar — parked; **esta** rebanada abre solo Thesis Health **advisory thin**) · relevo [`traspaso-relevo-ciclo-7-spine-honesty-2026-08-25.md`](./traspaso-relevo-ciclo-7-spine-honesty-2026-08-25.md) §4 E1 · síntesis subagentes AS-IS PM + integridad parked 2026-08-25.
> **AsOf:** 2026-08-25 · HEAD **`a2f32bb`** feat Ciclo 5.0.
> **Estado:** **CERRADO en código** (`a2f32bb`; stamp docs siguiente). D1–D8 OK · batería **121**.
> **Método:** rebanada fina crecimiento; Ranking ≠ BUY; sin Alembic; sin `contract:gen`; sin LLM; **sin** trailing/T1/MFE; **sin** ExecuteTrade converge (integridad = fase posterior).
> **Secuencia dueño:** (1) crecer Ciclo 5.x poco a poco · (2) luego integridad (ExecuteTrade / Actionability / Shadow).

---

## 0. Objetivo

ADR-031 Golden **F**: _tesis se degrada, precio > SL → `REVIEW`_. Hoy no hay Position Manager ni Thesis Health en código; Confidence Lifecycle (RFC-008 D7) existe como librería + tabla, **sin** cable al spine/mesa. PositionPolicy `EvaluatePositionExits` es otro motor (Lab/estrategia) — **no** mezclar.

**Ciclo 5.0 = advisory read-only.** Proyectar un hint de salud de tesis (hold / tighten / reduce / exit / review) desde señales ya disponibles (confidence mapper + stop estructural + qty abierta si hay), surfacing en mesa/Hoy. **No** ejecuta, **no** trail, **no** cambia `check_opening`.

### Qué entra vs qué queda fuera

| Incluye (thin 5.0)                                                       | Excluye (→ 5.1+ / integridad)                                       |
| ------------------------------------------------------------------------ | ------------------------------------------------------------------- |
| Mapper puro `thesis_health` / `mapThesisHealth` (hint + `why[]`)         | Trailing · T1 parcial · time-stop · bracket (Golden **E**)          |
| Eco opcional en `DecisionSession.runtime` / Board / Hoy (chip advisory)  | Auto-exit · wire `EvaluatePositionExits` · Confirm `exit_hint` auto |
| Test Golden-F-shaped (mapper): degrada + precio > SL → `review`          | MFE/MAE · expectancy plena                                          |
| Docs stamp + relevo 5.0; ADR-031 nota «5.0 advisory; PM/E siguen parked» | TradePlan `status=REVIEW` como gate de fill                         |
| Reusar `hintForConfidence` / lifecycle puro si encaja                    | Alembic · `contract:gen` · Shadow AUTO · ExecuteTrade converge      |

**Frontera:** Thesis Health 5.0 ≠ permiso. Advisory ≠ BUY. Hoy `REVIEW` (de `EXPIRED`) ≠ Golden F — usar label distinto (`thesis_review` / «Revisar tesis»).

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                                   | Propuesta por defecto                                                                                                                                                                                                                    |
| --- | ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | ¿Alcance de **esta** rebanada?             | **Solo Golden F advisory thin:** mapper + surface mesa/Hoy + tests. **No** Golden E (T1/trail).                                                                                                                                          |
| D2  | ¿Fuente de “tesis degrada”?                | **Confidence hint** (`hintForConfidence` / lifecycle puro) + umbrales existentes. Sin inventar segundo scoring. Si no hay confidence cableada → calcular hint desde inputs del test/mapper; persistencia Confidence = **opcional 5.0b**. |
| D3  | ¿Condición precio vs SL?                   | **Sí thin:** si hay `structuralStop` + last close y precio **no** ha roto el stop (precio > SL en long), pero hint ∈ {reduce,exit,tighten} → `review`. Sin barras → no inventar.                                                         |
| D4  | ¿Cambiar enum `TradePlan.status`?          | **No.** No añadir `REVIEW` al ladder de entrada. Campo advisory aparte (`thesisHealth` / `thesisHealthHint`).                                                                                                                            |
| D5  | ¿Qty abierta / cartera?                    | **Sí si barato:** si hay open qty del instrumento, priorizar surface; sin portfolio call pesado en Board → advisory también sobre sesiones Board (plan vivo) sin qty.                                                                    |
| D6  | ¿`check_opening` / Confirm / ExecuteTrade? | **Intactos.** Cero cambios en fill path.                                                                                                                                                                                                 |
| D7  | ¿Alembic / `contract:gen`?                 | **No.** JSONB runtime / DTO a mano si hace falta (patrón 4.9).                                                                                                                                                                           |
| D8  | ¿Cierre / siguiente?                       | Stamp + relevo 5.0. E1 = **5.1 protect/T1 thin (Golden E)** o refinamiento persistencia Confidence — **no** integridad ExecuteTrade hasta cerrar crecimiento 5.x pactado.                                                                |

Si D1 incluye trail/T1/auto-exit, D4 = `status=REVIEW` en TradePlan, o D6 toca fill: **parar y replanificar**.

---

## 2. Alcance (sí / no)

### Sí

| Pieza   | Regla                                                                                                 |
| ------- | ----------------------------------------------------------------------------------------------------- |
| Mapper  | Puro TS y/o Python espejo: inputs → `{ hint, status: ok\|review, why[] }`                             |
| Surface | Hoy chip / dialog línea «Revisar tesis» cuando `status=review`; Board echo si session.runtime lo trae |
| Tests   | Unit Golden F-shaped + regresión Hoy (EXPIRED→REVIEW de cola **no** se pisa)                          |
| Docs    | CURRENT_SYSTEM · ADR-031 §6 nota 5.0 · engineering-index · relevo                                     |

### No

- Trailing / T1 / time-stop / bracket / Position Manager execute
- MFE/MAE · expectancy · Shadow AUTO · `PAPER_D_EXECUTE`
- Dual ExecuteTrade / Actionability IO server / gate HTTP crudo
- Wire PositionPolicy exits al spine
- Wyckoff Alembic / `wyckoffPhase`

---

## 3. Diseño (borrador)

```text
# inputs (thin)
confidence | package score → hintForConfidence
structuralStop + lastClose + side → stopIntact?
openQty? (optional)

# output (advisory; no TradePlan.status)
thesisHealth = {
  hint: hold|tighten|reduce|exit|expire,
  status: ok | review,          # review ≈ Golden F
  why: ["confidence_degraded" | "stop_intact" | ...]
}

# surface
Hoy/Board: chip if status=review (label ≠ cola REVIEW de EXPIRED)
# no ExecuteTrade · no check_opening
```

---

## 4. Roadmap crecimiento → integridad (dueño)

| Orden    | Pieza                              | Notas                                    |
| -------- | ---------------------------------- | ---------------------------------------- |
| **5.0**  | Thesis Health advisory (este plan) | Golden F thin                            |
| **5.1**  | Protect / T1 thin                  | Golden E — sin broker                    |
| **5.2+** | Exit Radar / trailing / time-stop  | Solo con plan propio                     |
| **MFE**  | MFE/MAE + expectancy               | Tras journal attribution thin (ya hecha) |
| **I1**   | ExecuteTrade converge              | **Después** del crecimiento 5.x          |
| **I2**   | Actionability / IO server          | Post I1 o en paralelo si thin            |
| **I3**   | Shadow AUTO                        | Solo decisión explícita                  |

---

## 5. Arranque (tras OK D1–D8)

```text
Implementar Ciclo 5.0 Thesis Health thin según este plan.
D1=Golden F advisory · D2=confidence hint · D3=precio vs SL · D4=sin TradePlan.REVIEW · D5=qty opcional · D6=check_opening intacto · D7=sin Alembic/contract:gen · D8=stamp; E1=5.1 Golden E.
No trail · no T1 · no MFE · no ExecuteTrade · no PositionPolicy auto · no LLM.
```

---

## 6. Freeze

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · SETUP Wyckoff cerrada · Shadow AUTO off · advisory ≠ permiso · integridad ExecuteTrade **parked** hasta fin crecimiento.
