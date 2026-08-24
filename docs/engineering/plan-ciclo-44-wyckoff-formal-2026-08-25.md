# Plan — Ciclo 4.4 Wyckoff formal (más allá del stub reclaim 4.2)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §1 SETUP · §6 (`Wyckoff fases formales = 4.4+`) · relevo [`traspaso-relevo-ciclo-43-armed-2026-08-25.md`](./traspaso-relevo-ciclo-43-armed-2026-08-25.md) · ancla en [`plan-ciclo-43-armed-entrysetup-2026-08-25.md`](./plan-ciclo-43-armed-entrysetup-2026-08-25.md) (D3 difería Wyckoff formal → 4.4+).
> **AsOf:** 2026-08-25 · HEAD **`2135fc5`** = `origin/main`; feat **`7003ddf`**.
> **Estado:** **CERRADO en origin** (`7003ddf` vía `2135fc5`). D1–D7 OK · batería **88**.
> **Método:** rebanada fina; SETUP sigue ≠ motor paralelo; Ranking ≠ BUY; sin `contract:gen`; sin LLM.

---

## 0. Objetivo

Sustituir el **stub reclaim** de Ciclo 4.2 (`_is_wyckoff_reclaim`: spring 5 + prior 10 → close > spring low) por una clasificación **Wyckoff formal delgada**: etiquetas de fase + reglas de reclaim más estrictas (+ códigos `why` opcionales), sin abrir Position Manager / thesis health / trailing (**Ciclo 5**).

Hoy `EntrySetup=wyckoff` es un booleano heurístico. 4.4 hace explícito **qué fase** se detecta y **cuándo** basta para `entry_setup="wyckoff"` (y, si D4 lo pide, para `entry_ready` bajo setup wyckoff).

**No** es Lab paralelo · **no** cambia ladder `ARMED` 4.3 salvo D5 explícito · **no** toca stop/size 4.0 ni régimen 4.1 · prioridad `breakout > pullback > wyckoff` intacta salvo D2.

### Qué significa «formal» en **esta** rebanada

| Incluye (thin)                                                                                                   | Excluye (→ 4.5+ / Ciclo 5)                                                               |
| ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Etiquetas de fase: al menos **spring** (+ reclaim); **SOS** / **LPS** como detección opcional con defaults abajo | State machine multi-sesión, acumulación/distribución completa, ranges Wyckoff de semanas |
| Reclaim más estricto que 4.2 (p.ej. close > spring low **y** > umbral ATR / prior range)                         | Motor de posición, trailing, thesis health, MFE/MAE                                      |
| Códigos `why` opcionales (evidencia; no nuevo motor)                                                             | Campo Board HTTP / `contract:gen` / UI panel Wyckoff                                     |
| Sigue refinando `EntrySetup` / `entry_ready` (ADR-031 SETUP)                                                     | Sustituir Ranking o `check_opening`                                                      |

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                                | Propuesta por defecto                                                                                                                                                                                                                                                         |
| --- | --------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | ¿Alcance de **esta** rebanada?          | Formalizar clasificador wyckoff en `trade_plan.py` (+ tests spine). **Sin** Position Manager · **sin** tocar ladder ARMED 4.3 · **sin** stop/size 4.0 · **sin** régimen 4.1 · **sin** cambiar prioridad breakout>pullback>wyckoff.                                            |
| D2  | ¿Qué fases entran (SOS / LPS / spring)? | **Spring + reclaim estricto** → único camino a `EntrySetup=wyckoff`. **SOS** = etiqueta interna / evidencia (close por encima del máximo del spring o del prior range tras reclaim). **LPS** = **diferido** (4.5+) salvo OK propietario; no bloquea ni fuerza setup en 4.4.   |
| D3  | ¿Fases → `EntrySetup` vs campo nuevo?   | **Sin campo JSON nuevo.** Seguir `entrySetup: "wyckoff" \| …`. Fases solo en helpers internos + (si D6) códigos `whyNot` / notas de evidencia. Si se pide `wyckoffPhase` en TradePlan → **parar y replanificar** (posible TS shared + Hoy).                                   |
| D4  | ¿`entry_ready` bajo wyckoff?            | Igual que 4.2/4.3: `entry_ready_from_ta` **y** `setup != "none"`. Reclaim formal **no** exige SOS para ready (SOS solo etiqueta). Si propietario quiere «wyckoff ready solo con spring+SOS» → replanificar tests Golden.                                                      |
| D5  | ¿Interacción con `ARMED` (4.3)?         | **Intacta.** `ARMED` = stop + setup≠none + !ready. Wyckoff formal solo cambia _cuándo_ `setup` pasa a `wyckoff` (vs `none`). Sin estados nuevos ni actionability distinta.                                                                                                    |
| D6  | ¿Códigos `why` / Why surface?           | **Opcional thin:** si spring detectado pero reclaim falla → seguir `setup=none` + `whyNot` puede incluir `entry` (ya existe). **No** inventar códigos nuevos (`spring`/`sos`) en 4.4 salvo OK explícito; default = **sin** Why codes nuevos. Chip Hoy sin copy Wyckoff nueva. |
| D7  | ¿Confirm sin barras / `contract:gen`?   | Sin barras → `classify_entry_setup` = `none` (conservador 4.0–4.3). **`contract:gen` = No.** Solo dict TradePlan propose/confirm/Hoy.                                                                                                                                         |

Si D3 = campo `wyckoffPhase` ahora, o D2 = LPS obligatorio, o D4 = ready exige SOS: **parar y replanificar** (contrato + tests + posible UI).

---

## 2. Alcance 4.4 (sí / no)

### Sí

| Pieza           | Regla                                                                                                                                                                                                     |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Reclaim formal  | Sustituir/estrechar `_is_wyckoff_reclaim`: spring low (long) < min prior **y** last close > spring low **y** close ≥ spring low + `k × ATR` (default `k=0.25`) **o** close > max(high) del spring.        |
| Fases (helpers) | `_detect_wyckoff_spring` / `_detect_wyckoff_sos` (bool o Literal interno). `classify_entry_setup` devuelve `wyckoff` **solo** si spring+reclaim formal OK. SOS no cambia el enum.                         |
| Prioridad       | Sigue `breakout > pullback > wyckoff > none`.                                                                                                                                                             |
| ARMED / ready   | Sin cambio de semántica 4.3 / 4.2 (D4–D5).                                                                                                                                                                |
| Confirm         | Sin barras → `none`; no inventa wyckoff ni ARMED.                                                                                                                                                         |
| Tests           | ≥3–4 casos: (1) stub viejo que ya no pasa umbral → `none`; (2) spring+reclaim estricto → `wyckoff` (+ ARMED o TRIGGERED según bias); (3) breakout sigue ganando prioridad; (4) confirm sin barras → none. |
| Docs cierre     | Tras implement: nota ADR-031 §6 Ciclo 4.4; stamp SoT + relevo (fuera de este BORRADOR).                                                                                                                   |

### No

- Position Manager / thesis health / MFE / trailing / T1 (Ciclo 5)
- LPS como gate de setup (default D2)
- Campo `wyckoffPhase` / Board HTTP / `contract:gen`
- Cambiar ladder ARMED, stop/size 4.0, `NO_NEW_LONGS` 4.1, prioridad breakout>pullback
- `check_opening`, broker, F9-B, purge MONITOR, `PAPER_D_EXECUTE`, qty Confirm
- Familias Lab (`donchian_*` / strategy types) como motor — solo heurística de barras en analytics
- UI panel / copy Why dedicada Wyckoff
- Pisar `suggestedQuantity` del ticket F3

---

## 3. Diseño mapper / clasificador (borrador)

```text
# classify_entry_setup (prioridad intacta)
direction none | bars None → none
breakout? → breakout
pullback? → pullback
spring + reclaim_formal(ATR/spring-range)? → wyckoff   # 4.4
else → none
# SOS: helper/evidencia; no fuerza EntrySetup
# LPS: fuera de 4.4 (default)

# build_trade_plan ladder (4.3 intacta)
expired? → EXPIRED
regime blocks long? → BLOCKED (+ regime)          # 4.1
!fit / !freshness / !mandate → BLOCKED
wait/reduce/none → WATCH entry
!stop → WATCH no_stop
setup ≠ none AND !entry_ready → ARMED (+ entry)   # 4.3
!entry_ready (setup == none) → WATCH entry
else → TRIGGERED + size
```

**Constantes (propuesta):** conservar `WYCKOFF_SPRING=5`, `WYCKOFF_PRIOR=10`; añadir `WYCKOFF_RECLAIM_ATR_K=0.25` (o reclaim por max spring high). Ajustar solo con OK D1.

**Invariant:** Ranking ≠ BUY. SETUP ≠ motor paralelo Lab. `ARMED` ≠ fill. `TRIGGERED` + `check_opening` ALLOW + firma humana = BUY operativo.

---

## 4. Batería pactada

- ruff touched Python (`trade_plan.py` + tests application/analytics tocados)
- `pnpm test:decision-spine` (hoy **84**; +casos wyckoff formal ≥3–4 → esperado **87–88**)
- vitest `@bolsa/shared` **no** esperado (sin campo/tipo nuevo si D3 default)

---

## 5. Criterio de cierre 4.4

1. Caso que cumplía stub 4.2 pero falla reclaim estricto → `entrySetup=none` (no wyckoff falso).
2. Spring + reclaim formal + bias → `TRIGGERED` + `entrySetup=wyckoff` (o `ARMED` si !ready).
3. Breakout artificial sigue ganando a wyckoff cuando ambos matchean.
4. Confirm/rebuild sin barras → `none` / no ARMED inventado.
5. Diff `check_opening` vacío; stop/size/régimen/ARMED ladder/prioridad EntrySetup intactos.
6. Relevo + stamp SoT. Commit/push solo con OK propietario.

---

## 6. Texto de arranque (tras OK D1–D7)

```text
Implementar Ciclo 4.4 Wyckoff formal según plan-ciclo-44-wyckoff-formal-2026-08-25.md.
D1=clasificador formal thin · D2=spring+reclaim estricto; SOS etiqueta; LPS diferido · D3=sin campo wyckoffPhase · D4=ready=ta+setup · D5=ARMED 4.3 intacta · D6=sin why codes nuevos · D7=confirm sin barras=none; sin contract:gen.
No check_opening · no Position Manager · no thesis health · no F9-B/purge/broker.
```
