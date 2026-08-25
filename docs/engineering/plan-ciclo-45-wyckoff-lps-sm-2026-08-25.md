# Plan — Ciclo 4.5 LPS / state machine Wyckoff (thin)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §1 SETUP · §6 (`LPS / state machine Wyckoff multi-sesión = 4.5+`, prohibido sin plan + decisión) · relevo [`traspaso-relevo-ciclo-44-wyckoff-formal-2026-08-25.md`](./traspaso-relevo-ciclo-44-wyckoff-formal-2026-08-25.md) · ancla en [`plan-ciclo-44-wyckoff-formal-2026-08-25.md`](./plan-ciclo-44-wyckoff-formal-2026-08-25.md) (D2 difería LPS → 4.5+; D3 sin `wyckoffPhase`).
> **AsOf:** 2026-08-25 · HEAD local feat **`baaa9b4`** (docs stamp pendiente push). Feat 4.4 **`7003ddf`** en origin.
> **Estado:** **CERRADO** (D1–D8 OK · batería **92** · feat `baaa9b4`). Push solo con OK propietario.
> **Método:** rebanada fina; SETUP sigue ≠ motor paralelo; Ranking ≠ BUY; sin `contract:gen`; sin LLM.

---

## 0. Objetivo

Añadir **LPS** (Last Point of Support / Supply) y una **SM Wyckoff delgada de ventana única** sobre el clasificador ya cerrado en 4.4 (`_detect_wyckoff_spring` · `_is_wyckoff_reclaim` · `_detect_wyckoff_sos`), sin abrir persistencia multi-sesión, Position Manager ni contrato nuevo.

Hoy (4.4): `EntrySetup=wyckoff` ⇔ spring + reclaim estricto (`WYCKOFF_RECLAIM_ATR_K=0.25` **o** close fuera del rango spring). SOS = etiqueta interna no cableada al enum. LPS ausente. Sin `wyckoffPhase`. Ventana fija `WYCKOFF_PRIOR=10` + `WYCKOFF_SPRING=5` + last bar en `trade_plan.py`.

### Qué entra en **esta** rebanada vs qué queda fuera

| Incluye (thin 4.5)                                                                                          | Excluye (→ 4.6+ / Ciclo 5)                                                                 |
| ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Helper `_detect_wyckoff_lps` (long/short espejo) sobre la **misma** ventana prior+spring+last               | SM **multi-sesión** persistida (fase en BD / tesis / plan entre proposes)                  |
| SM de evidencia **single-window**: orden interno `spring → reclaim → sos? → lps?` recalculado cada classify | Acumulación/distribución completa, ranges de semanas, volumen/effort-result formal         |
| Tests spine + (si D7) why codes opcionales                                                                  | Campo `wyckoffPhase` / Board HTTP / `contract:gen` / UI panel Wyckoff                      |
| Sigue refinando evidencia SETUP (ADR-031); **no** sustituye Ranking ni `check_opening`                      | Cambiar gate 4.4 (LPS obligatorio para `wyckoff`) salvo OK explícito + replan tests Golden |
|                                                                                                             | Position Manager, thesis health, MFE/MAE, trailing, T1 (Ciclo 5)                           |

**No** es Lab paralelo · **no** cambia ladder `ARMED` 4.3 salvo D6 explícito · **no** toca stop/size 4.0 ni régimen 4.1 · prioridad `breakout > pullback > wyckoff` intacta salvo D1.

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                                | Propuesta por defecto                                                                                                                                                                                                                                                                                  |
| --- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| D1  | ¿Alcance de **esta** rebanada?          | LPS + SM thin **single-window** en `trade_plan.py` (+ tests spine). **Sin** persistencia multi-sesión · **sin** Position Manager · **sin** tocar ladder ARMED 4.3 · **sin** stop/size 4.0 · **sin** régimen 4.1 · **sin** cambiar prioridad breakout>pullback>wyckoff · **sin** debilitar reclaim 4.4. |
| D2  | ¿LPS como **gate** o solo **etiqueta**? | **Etiqueta / evidencia interna** (mismo rol que SOS en 4.4). `EntrySetup=wyckoff` sigue = spring + reclaim formal. LPS **no** fuerza ni bloquea setup. Si propietario exige «wyckoff solo con LPS» o «ready solo con LPS» → **parar y replanificar** (rompe Golden 4.4 + batería).                     |
| D3  | ¿SM multi-sesión vs single-window?      | **Single-window:** helpers recalculan fase/evidencia desde `bars` en cada `classify_entry_setup` / propose. **Sin** estado persistido entre sesiones. Multi-sesión (cache fase, thesis binding, TTL) → **4.6+**. Pedir multi-sesión ahora → **parar y replanificar** (storage + posible contrato).     |
| D4  | ¿Campo JSON nuevo vs helpers internos?  | **Sin campo JSON nuevo.** Sin `wyckoffPhase` en TradePlan / `@bolsa/shared`. Solo helpers (`_detect_wyckoff_lps`, opcional `_wyckoff_phase_evidence` Literal interno). Si se pide `wyckoffPhase` en contrato o `contract:gen` → **parar y replanificar**.                                              |
| D5  | ¿Interacción con `entry_ready`?         | Igual 4.2–4.4: `entry_ready_from_ta` **y** `setup != "none"`. LPS/SOS **no** entran en ready.                                                                                                                                                                                                          |
| D6  | ¿Interacción con `ARMED` (4.3)?         | **Intacta.** `ARMED` = stop + setup≠none + !ready. LPS/SM solo añaden evidencia interna; no estados nuevos ni actionability distinta.                                                                                                                                                                  |
| D7  | ¿Códigos `why` / Why surface?           | **Sin** Why codes nuevos (`lps`/`sos`/`spring`) por defecto. `whyNot` sigue el patrón existente (`entry` bajo ARMED/WATCH). Chip Hoy sin copy Wyckoff nueva. OK propietario puede activar códigos thin solo en evidencia/notas internas sin UI.                                                        |
| D8  | ¿Confirm sin barras / `contract:gen`?   | Sin barras → `classify_entry_setup` = `none` (conservador 4.0–4.4). **`contract:gen` = No.** Solo dict TradePlan propose/confirm/Hoy.                                                                                                                                                                  |

Si D2 = LPS gate obligatorio, D3 = multi-sesión, D4 = `wyckoffPhase` / `contract:gen`, o D5 = ready exige LPS: **parar y replanificar**.

---

## 2. Alcance 4.5 (sí / no)

### Sí

| Pieza            | Regla                                                                                                                                                                                                                                                                                                       |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LPS (helper)     | `_detect_wyckoff_lps`: requiere spring + reclaim formal previos en la ventana. Long: tras reclaim, existe pullback reciente cuyo low queda **por encima** del spring low (hielo) y last close ≥ ese low LPS (o ≥ low + ε×ATR si se fija constante); short espejo bajo spring high. Sin reclaim → LPS false. |
| SM single-window | Evidencia ordenada interna (no JSON): `spring` → `reclaim` → `sos?` → `lps?`. Función opcional `_wyckoff_phase_evidence(...)` → Literal/`tuple` interno para tests; **no** expuesta en TradePlan.                                                                                                           |
| SOS              | Conservar `_detect_wyckoff_sos` 4.4 (etiqueta). SM puede consultarla; sigue sin forzar `EntrySetup`.                                                                                                                                                                                                        |
| EntrySetup       | Sin cambio de semántica 4.4: solo spring+reclaim → `wyckoff`. Prioridad `breakout > pullback > wyckoff > none`.                                                                                                                                                                                             |
| ARMED / ready    | Sin cambio 4.3 / 4.2 (D5–D6).                                                                                                                                                                                                                                                                               |
| Confirm          | Sin barras → `none`; no inventa wyckoff ni ARMED ni LPS.                                                                                                                                                                                                                                                    |
| Constantes       | Conservar `WYCKOFF_SPRING`/`PRIOR`/`RECLAIM_ATR_K`. Añadir solo si hace falta `WYCKOFF_LPS_*` thin (p.ej. lookback pullback ≤ spring window o `LPS_ATR_EPS`); ajustar con OK D1.                                                                                                                            |
| Tests            | ≥3–4 casos: (1) spring+reclaim sin LPS → sigue `wyckoff` (regresión 4.4); (2) spring+reclaim+LPS → `wyckoff` + helper LPS true; (3) LPS sin reclaim → false / setup no forzado; (4) breakout sigue ganando; (+ confirm sin barras → none).                                                                  |
| Docs cierre      | Tras implement: nota ADR-031 §6 Ciclo 4.5; stamp SoT + relevo (fuera de este BORRADOR).                                                                                                                                                                                                                     |

### No

- SM multi-sesión / fase persistida / binding a tesis entre proposes
- LPS como gate obligatorio de `EntrySetup` o de `entry_ready` (default D2/D5)
- Campo `wyckoffPhase` / Board HTTP / `contract:gen` / UI panel Wyckoff
- Cambiar ladder ARMED, stop/size 4.0, `NO_NEW_LONGS` 4.1, prioridad breakout>pullback, reclaim 4.4
- `check_opening`, broker, F9-B, purge MONITOR, `PAPER_D_EXECUTE`, qty Confirm
- Position Manager / thesis health / MFE / trailing / T1 (Ciclo 5)
- Familias Lab (`donchian_*` / strategy types) como motor — solo heurística de barras en analytics
- Pisar `suggestedQuantity` del ticket F3
- Volumen / effort-result / ranges multi-semana

---

## 3. Diseño mapper / clasificador (borrador)

```text
# classify_entry_setup (prioridad intacta — 4.2/4.4)
direction none | bars None → none
breakout? → breakout
pullback? → pullback
spring + reclaim_formal(ATR/spring-range)? → wyckoff   # 4.4 intacto
else → none
# SOS / LPS: helpers/evidencia; no fuerzan EntrySetup (D2 default)

# evidencia SM single-window (interno; no JSON)
_wyckoff_phase_evidence:
  !spring → none
  spring && !reclaim → spring
  reclaim && !sos && !lps → reclaim
  reclaim && sos && !lps → sos        # etiqueta
  reclaim && lps → lps                # etiqueta (sos opcional previo)

# LPS thin (long; short espejo)
_detect_wyckoff_lps:
  require _is_wyckoff_reclaim
  ice = spring_low
  pullback_low = min(low) de barras post-spring en ventana (o last N cerradas)
  pullback_low > ice
  last close >= pullback_low   # (o + eps×ATR si D1 fija constante)
  → True

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

**Ancla código (no tocar fuera de helpers/tests pactados):**
`packages/py/analytics/src/bolsa_analytics/cognitive/trade_plan.py` — `_wyckoff_windows`, `_detect_wyckoff_spring`, `_is_wyckoff_reclaim`, `_detect_wyckoff_sos`, `classify_entry_setup`.
Tests: `packages/py/analytics/tests/test_trade_plan.py` (fixtures `_wyckoff_*` 4.4).

**Invariant:** Ranking ≠ BUY. SETUP ≠ motor paralelo Lab. `ARMED` ≠ fill. `TRIGGERED` + `check_opening` ALLOW + firma humana = BUY operativo. LPS/SM ≠ nuevo status ladder.

---

## 4. Batería pactada

- ruff touched Python (`trade_plan.py` + tests analytics tocados)
- `pnpm test:decision-spine` (hoy **88**; +casos LPS/SM ≥3–4 → esperado **91–92**)
- vitest `@bolsa/shared` **no** esperado (sin campo/tipo nuevo si D4 default)

---

## 5. Criterio de cierre 4.5

1. Regresión 4.4: spring + reclaim formal sin LPS → sigue `entrySetup=wyckoff` (LPS no gate).
2. Caso LPS true solo con reclaim previo; sin reclaim → LPS false.
3. Breakout artificial sigue ganando a wyckoff cuando ambos matchean.
4. Confirm/rebuild sin barras → `none` / no ARMED inventado / no LPS inventado en contrato.
5. Diff `check_opening` vacío; stop/size/régimen/ARMED ladder/prioridad EntrySetup/reclaim 4.4 intactos.
6. Sin `wyckoffPhase` en JSON TradePlan; sin `contract:gen`.
7. Relevo + stamp SoT. Commit/push solo con OK propietario.

---

## 6. Texto de arranque (tras OK D1–D8)

```text
Implementar Ciclo 4.5 LPS / SM Wyckoff según plan-ciclo-45-wyckoff-lps-sm-2026-08-25.md.
D1=LPS+SM single-window thin · D2=LPS etiqueta (no gate) · D3=sin multi-sesión · D4=sin wyckoffPhase/JSON · D5=ready=ta+setup · D6=ARMED 4.3 intacta · D7=sin why codes nuevos · D8=confirm sin barras=none; sin contract:gen.
No check_opening · no Position Manager · no thesis health · no F9-B/purge/broker · no Ciclo 5.
```
