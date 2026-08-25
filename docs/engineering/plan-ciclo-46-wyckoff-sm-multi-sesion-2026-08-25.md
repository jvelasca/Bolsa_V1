# Plan — Ciclo 4.6 SM Wyckoff multi-sesión (thin, scan lookback)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §1 SETUP · §6 (`SM Wyckoff multi-sesión / fase persistida = 4.6+`, prohibido sin plan + decisión) · relevo [`traspaso-relevo-ciclo-45-wyckoff-lps-sm-2026-08-25.md`](./traspaso-relevo-ciclo-45-wyckoff-lps-sm-2026-08-25.md) · ancla en [`plan-ciclo-45-wyckoff-lps-sm-2026-08-25.md`](./plan-ciclo-45-wyckoff-lps-sm-2026-08-25.md) (D3 difería multi-sesión → 4.6+; D4 sin `wyckoffPhase`).
> **AsOf:** 2026-08-25 · HEAD **`dd5b8e8`** = `origin/main`; feat **`fb6e801`**.
> **Estado:** **CERRADO en origin** (`fb6e801` vía `dd5b8e8`). D1–D8 OK · batería **94**.
> **Método:** rebanada fina; SETUP sigue ≠ motor paralelo; Ranking ≠ BUY; sin `contract:gen`; sin LLM.

---

## 0. Objetivo

Hacer que la SM Wyckoff **sobreviva varias sesiones de barras** después del spring, para que SOS/LPS 4.5 dejen de ser casi inalcanzables en D1.

Hoy (4.5): helpers recorren una ventana fija `WYCKOFF_PRIOR=10` + `WYCKOFF_SPRING=5` + last (`_wyckoff_windows`). Si el spring sale de esas 5 barras, `_detect_wyckoff_spring` → false y reclaim/SOS/LPS se apagan. Propose ya carga **`bar_limit=120`**. El gap no es falta de OHLCV: es el recorte de 16 barras.

**Multi-sesión en esta rebanada** = localizar el spring vivo **más reciente** dentro de un lookback de las mismas `bars` (función pura, recalculada cada classify). **No** es cache en BD ni binding a tesis entre proposes.

### Qué entra vs qué queda fuera

| Incluye (thin 4.6)                                                                                       | Excluye (→ 4.7+ / Ciclo 5)                                                  |
| -------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Locator `_locate_wyckoff_spring` sobre lookback `WYCKOFF_LOOKBACK` (default 40 cerradas + last)          | Fase persistida en cognitive store / BD / Alembic                           |
| Reclaim / SOS / LPS evaluados contra **ese** spring (hielo + barras posteriores), no solo las últimas 16 | Binding tesis↔fase entre proposes; TTL de cache; `wyckoffPhase` JSON        |
| Invalidación: close (o extreme) atraviesa el hielo → estructura muerta                                   | Acumulación/distribución completa, ranges de semanas, volumen/effort-result |
| `EntrySetup=wyckoff` si spring localizado + reclaim + hielo intacto (LPS sigue etiqueta)                 | LPS como gate de setup o de `entry_ready`                                   |
| Tests spine (spring envejecido + LPS last; hielo roto → none; regresión 4.4/4.5 ventana corta)           | Campo `wyckoffPhase` / Board HTTP / `contract:gen` / UI panel Wyckoff       |
| Sigue refinando evidencia SETUP (ADR-031); **no** sustituye Ranking ni `check_opening`                   | Position Manager, thesis health, MFE/MAE, trailing, T1 (Ciclo 5)            |

**No** es Lab paralelo · **no** cambia ladder `ARMED` 4.3 · **no** toca stop/size 4.0 ni régimen 4.1 · prioridad `breakout > pullback > wyckoff` intacta salvo D1.

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                              | Propuesta por defecto                                                                                                                                                                                                                                                                                                                                    |
| --- | ------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | ¿Alcance de **esta** rebanada?        | Locator + SM contra spring vivo en lookback de `bars` (`trade_plan.py` + tests spine). `WYCKOFF_LOOKBACK=40` (cabe en propose 120). **Sin** store/Alembic · **sin** `wyckoffPhase` · **sin** tocar ladder ARMED 4.3 · **sin** stop/size 4.0 · **sin** régimen 4.1 · **sin** cambiar prioridad breakout>pullback>wyckoff · **sin** debilitar reclaim 4.4. |
| D2  | ¿LPS / SM como **gate** o etiqueta?   | Igual 4.5: LPS/SOS **etiqueta**. `EntrySetup=wyckoff` = spring **localizado** + reclaim formal 4.4 + hielo intacto. LPS **no** fuerza ni bloquea setup. Si propietario exige «wyckoff solo con LPS» → **parar y replanificar**.                                                                                                                          |
| D3  | ¿Scan lookback vs persistir fase?     | **Scan.** Cada classify relocaliza desde `bars`. Sin estado entre proposes. Persistencia (cache fase, thesis binding, TTL store) → **4.7+**. Pedir persistencia ahora → **parar y replanificar** (store + posible contrato).                                                                                                                             |
| D4  | ¿Campo JSON / `wyckoffPhase`?         | **Sin campo JSON nuevo.** `_wyckoff_phase_evidence` sigue interno (ahora sobre el spring localizado). Si se pide `wyckoffPhase` en TradePlan / `@bolsa/shared` o `contract:gen` → **parar y replanificar**.                                                                                                                                              |
| D5  | ¿Interacción con `entry_ready`?       | Igual 4.2–4.5: `entry_ready_from_ta` **y** `setup != "none"`. LPS/SOS **no** entran en ready.                                                                                                                                                                                                                                                            |
| D6  | ¿Interacción con `ARMED` (4.3)?       | **Intacta.** `ARMED` = stop + setup≠none + !ready. SM multi-sesión no añade estados ni actionability distinta.                                                                                                                                                                                                                                           |
| D7  | ¿Códigos `why` / Why surface?         | **Sin** Why codes nuevos. `whyNot` sigue el patrón existente (`entry` bajo ARMED/WATCH). Chip Hoy sin copy Wyckoff nueva.                                                                                                                                                                                                                                |
| D8  | ¿Confirm sin barras / `contract:gen`? | Sin barras → `classify_entry_setup` = `none` (conservador 4.0–4.5). **No** se inventa fase por plan previo. **`contract:gen` = No.**                                                                                                                                                                                                                     |

Si D2 = LPS gate, D3 = persistencia store, D4 = `wyckoffPhase` / `contract:gen`, o D5 = ready exige LPS: **parar y replanificar**.

---

## 2. Alcance 4.6 (sí / no)

### Sí

| Pieza                | Regla                                                                                                                                                                                                                                                                                                       |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Locator              | `_locate_wyckoff_spring`: recorre ventanas `prior+spring` **desde la más reciente** dentro de `WYCKOFF_LOOKBACK`. Primera (más reciente) que cumple spring 4.4. Si su hielo ya está roto por barras posteriores → **ninguna** (no resucitar springs más viejos). Sin candidato → evidencia `none`.          |
| Hielo / invalidación | Long: algún `low` posterior al spring ≤ spring low → muerto. Short: espejo con spring high. Sin TTL por nº de barras (salvo OK D1).                                                                                                                                                                         |
| Reclaim / SOS / LPS  | Mismos predicados 4.4/4.5 (`k×ATR=0.25` o fuera rango spring; SOS close fuera max prior+spring; LPS pullback sobre hielo) aplicados al **spring localizado**, no a `_wyckoff_windows` fijo de 16.                                                                                                           |
| SM evidencia         | `_wyckoff_phase_evidence` igual 4.5 (`none` / `spring` / `reclaim` / `sos` / `lps`) pero sobre el locator. Interno; no JSON.                                                                                                                                                                                |
| EntrySetup           | `wyckoff` ⇔ spring localizado + reclaim + hielo intacto. Prioridad `breakout > pullback > wyckoff > none` **intacta**. Semántica más ancha que 4.5: un spring de hace 20 barras con hielo vivo **sí** puede ser `wyckoff`.                                                                                  |
| Constantes           | Conservar `WYCKOFF_SPRING` / `PRIOR` / `RECLAIM_ATR_K` / `LPS_ATR_EPS`. Añadir `WYCKOFF_LOOKBACK=40` (cerradas a escanear; last aparte). No subir `bar_limit` de propose.                                                                                                                                   |
| ARMED / ready        | Sin cambio 4.3 / 4.2 (D5–D6).                                                                                                                                                                                                                                                                               |
| Confirm              | Sin barras → `none`; no inventa wyckoff ni ARMED ni fase.                                                                                                                                                                                                                                                   |
| Tests                | ≥4–5 casos: (1) fixture 4.4/4.5 corta → sigue `wyckoff` (regresión); (2) spring envejecido (fuera de 16) + reclaim + hielo vivo → `wyckoff`; (3) mismo + LPS last → helper LPS true, setup sigue `wyckoff`; (4) hielo roto → `none` / LPS false; (5) breakout sigue ganando; (+ confirm sin barras → none). |
| Docs cierre          | Tras implement: nota ADR-031 §6 Ciclo 4.6; stamp SoT + relevo (fuera de este BORRADOR).                                                                                                                                                                                                                     |

### No

- Persistencia de fase / cognitive store / Alembic / binding a tesis entre proposes
- LPS como gate obligatorio de `EntrySetup` o de `entry_ready` (default D2/D5)
- Campo `wyckoffPhase` / Board HTTP / `contract:gen` / UI panel Wyckoff
- Cambiar ladder ARMED, stop/size 4.0, `NO_NEW_LONGS` 4.1, prioridad breakout>pullback, reclaim 4.4 (`k`)
- Subir `bar_limit` propose / pedir más OHLCV
- `check_opening`, broker, F9-B, purge MONITOR, `PAPER_D_EXECUTE`, qty Confirm
- Position Manager / thesis health / MFE / trailing / T1 (Ciclo 5)
- Familias Lab (`donchian_*` / strategy types) como motor
- Pisar `suggestedQuantity` del ticket F3
- Volumen / effort-result / ranges multi-semana / resucitar springs más viejos tras hielo roto

---

## 3. Diseño mapper / clasificador (borrador)

```text
# locate (nuevo 4.6)
_locate_wyckoff_spring(direction, bars, lookback=40):
  scan ventanas prior+spring de más reciente a más antigua dentro del lookback
  primer spring 4.4 cuyo hielo NO está roto por barras posteriores
  → {prior, spring, ice} | None

# reclaim / sos / lps 4.4–4.5 sobre el locate (no sobre last-16 fijo)
_is_wyckoff_reclaim  ← locate + close ≥ ice + k×ATR  ó  close fuera rango spring
_detect_wyckoff_sos  ← locate + last close fuera max(prior+spring)
_detect_wyckoff_lps  ← reclaim + pullback last sobre hielo (espejo short)

# classify_entry_setup (prioridad intacta — 4.2/4.4)
direction none | bars None → none
breakout? → breakout
pullback? → pullback
locate + reclaim + hielo intacto → wyckoff
else → none
# SOS / LPS: evidencia; no fuerzan EntrySetup (D2)

# evidencia SM (interno; no JSON)
_wyckoff_phase_evidence:
  !locate → none
  locate && !reclaim → spring
  reclaim && !sos && !lps → reclaim
  reclaim && sos && !lps → sos
  reclaim && lps → lps

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
`packages/py/analytics/src/bolsa_analytics/cognitive/trade_plan.py` — `_wyckoff_windows` (puede quedar como helper de una ventana, o absorberse en el locator), `_detect_wyckoff_spring`, `_is_wyckoff_reclaim`, `_detect_wyckoff_sos`, `_detect_wyckoff_lps`, `_wyckoff_phase_evidence`, `classify_entry_setup`.
Tests: `packages/py/application/tests/test_trade_plan.py` (y analytics si aplica); reutilizar fixtures `_wyckoff_*` 4.4/4.5 + series envejecida.

**Invariant:** Ranking ≠ BUY. SETUP ≠ motor paralelo Lab. `ARMED` ≠ fill. `TRIGGERED` + `check_opening` ALLOW + firma humana = BUY operativo. LPS/SM ≠ nuevo status ladder. Scan ≠ store.

---

## 4. Batería pactada

- ruff touched Python (`trade_plan.py` + tests tocados)
- `pnpm test:decision-spine` (hoy **92**; +casos lookback/hielo ≥4–5 → esperado **96–97**)
- vitest `@bolsa/shared` **no** esperado (sin campo/tipo nuevo si D4 default)

---

## 5. Criterio de cierre 4.6

1. Regresión 4.4/4.5: spring+reclaim en ventana corta sin LPS → sigue `entrySetup=wyckoff`.
2. Spring fuera de las últimas 16 + reclaim + hielo vivo → `entrySetup=wyckoff` (el punto de 4.6).
3. Hielo roto tras el spring → no `wyckoff`; LPS false.
4. Breakout artificial sigue ganando a wyckoff cuando ambos matchean.
5. Confirm/rebuild sin barras → `none` / no ARMED inventado / no fase inventada.
6. Diff `check_opening` vacío; stop/size/régimen/ARMED ladder/prioridad EntrySetup/reclaim `k` intactos.
7. Sin `wyckoffPhase` en JSON TradePlan; sin `contract:gen`; sin store/Alembic.
8. Relevo + stamp SoT. Commit/push solo con OK propietario.

---

## 6. Texto de arranque (tras OK D1–D8)

```text
Implementar Ciclo 4.6 SM Wyckoff multi-sesión según plan-ciclo-46-wyckoff-sm-multi-sesion-2026-08-25.md.
D1=locator lookback=40 thin · D2=LPS etiqueta; wyckoff=spring localizado+reclaim+hielo · D3=scan no persist · D4=sin wyckoffPhase/JSON · D5=ready=ta+setup · D6=ARMED 4.3 intacta · D7=sin why codes nuevos · D8=confirm sin barras=none; sin contract:gen.
No check_opening · no store/Alembic · no Position Manager · no thesis health · no F9-B/purge/broker · no Ciclo 5.
```
