# Plan — Ciclo 4.7 Wyckoff thesis binding (thin, sesión cognitiva)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §1 SETUP · §6 (`Persistencia fase Wyckoff / binding tesis (store) — 4.7+`, prohibido sin plan + decisión) · relevo [`traspaso-relevo-ciclo-46-wyckoff-sm-lookback-2026-08-25.md`](./traspaso-relevo-ciclo-46-wyckoff-sm-lookback-2026-08-25.md) · ancla en [`plan-ciclo-46-wyckoff-sm-multi-sesion-2026-08-25.md`](./plan-ciclo-46-wyckoff-sm-multi-sesion-2026-08-25.md) (D3 difería persistencia → 4.7+; D4 sin `wyckoffPhase`).
> **AsOf:** 2026-08-25 · HEAD **`f0ba3e5`** = `origin/main`; feat **`604fd90`**.
> **Estado:** **CERRADO en origin** (`604fd90` vía `f0ba3e5`). D1–D8 OK · batería **100**.
> **Método:** rebanada fina; SETUP sigue ≠ motor paralelo; Ranking ≠ BUY; sin `contract:gen`; sin LLM.

---

## 0. Objetivo

Dar **continuidad de spring** entre proposes de la misma tesis: el scan 4.6 (`_locate_wyckoff_spring`, lookback 40) es correcto por barra, pero cada classify puede elegir otro spring vivo o perder el evento que la tesis ya estaba siguiendo.

**Thesis binding en esta rebanada** = anclar el spring (hielo + rango + dirección) a la sesión cognitiva / `decision_id` ya persistida, revalidar hielo con barras en cada classify, y solo entonces caer al locator 4.6. **No** es tabla Alembic nueva ni motor de acumulación multi-semana.

### Qué entra vs qué queda fuera

| Incluye (thin 4.7)                                                                             | Excluye (→ 4.8+ / Ciclo 5)                                                  |
| ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Anchor `wyckoffSpringAnchor` en `runtime` de `DecisionSession` (JSONB ya existente)            | Alembic / tabla nueva / Prisma                                              |
| Lookup prior por `decision_id` (o sesión abierta del instrumento) al propose/confirm           | Cache global por símbolo sin tesis; TTL de días arbitrario sin hielo        |
| Classify: prior intacto → mismo spring; hielo roto → none (no resucitar); sin prior → scan 4.6 | `wyckoffPhase` en TradePlan / `@bolsa/shared` / Board HTTP / `contract:gen` |
| Snapshot fase interna (`_wyckoff_phase_evidence`) opcional en runtime (no contrato FE)         | LPS como gate de setup o de `entry_ready`                                   |
| Tests spine + propose/confirm con store (binding + hielo + regresión 4.6)                      | UI panel Wyckoff; Why chip nuevo; Position Manager / thesis health / MFE    |
| Sigue refinando evidencia SETUP (ADR-031); **no** sustituye Ranking ni `check_opening`         | Acumulación/distribución completa, volumen/effort-result, ranges semanas    |

**No** es Lab paralelo · **no** cambia ladder `ARMED` 4.3 · **no** toca stop/size 4.0 ni régimen 4.1 · prioridad `breakout > pullback > wyckoff` intacta salvo D1 · reclaim `k` 4.4 intacto · lookback 4.6 intacto como fallback.

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                                  | Propuesta por defecto                                                                                                                                                                                                                                                                                 |
| --- | ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | ¿Alcance de **esta** rebanada?            | Binding thin: anchor en `DecisionSession.runtime` + wire propose/confirm + helpers en `trade_plan.py` (+ tests). **Sin** Alembic · **sin** tabla nueva · **sin** `wyckoffPhase` en TradePlan · **sin** tocar ladder ARMED / stop / size / régimen / prioridad EntrySetup / reclaim `k` / lookback 40. |
| D2  | ¿LPS / SM como **gate** o etiqueta?       | Igual 4.5–4.6: LPS/SOS **etiqueta**. `EntrySetup=wyckoff` = spring **resuelto** (bound o locate) + reclaim 4.4 + hielo intacto. LPS **no** fuerza ni bloquea. Si «wyckoff solo con LPS» → **parar y replanificar**.                                                                                   |
| D3  | ¿Dónde vive el estado?                    | **Session payload / runtime** (JSONB `decision_sessions`). Clave sugerida `wyckoffSpringAnchor`. Lookup: última sesión con mismo `decision_id` (fallback: ninguna → scan). **Sin** Alembic. Pedir tabla dedicada / cache por símbolo sin tesis → **parar y replanificar**.                            |
| D4  | ¿Campo JSON / `wyckoffPhase` en contrato? | **Sin** campo en TradePlan / `@bolsa/shared`. Anchor + fase opcional solo en `runtime` de sesión (y tests). Si se pide `wyckoffPhase` en TradePlan, Board HTTP o `contract:gen` → **parar y replanificar**.                                                                                           |
| D5  | ¿Interacción con `entry_ready`?           | Igual 4.2–4.6: `entry_ready_from_ta` **y** `setup != "none"`. LPS/SOS/anchor **no** entran en ready.                                                                                                                                                                                                  |
| D6  | ¿Interacción con `ARMED` (4.3)?           | **Intacta.** Binding no añade estados ni actionability distinta.                                                                                                                                                                                                                                      |
| D7  | ¿Códigos `why` / Why surface?             | **Sin** Why codes nuevos. Chip Hoy sin copy Wyckoff nueva.                                                                                                                                                                                                                                            |
| D8  | ¿Confirm sin barras / `contract:gen`?     | Sin barras → `classify_entry_setup` = `none` (conservador). **No** inventar wyckoff/ARMED/fase solo por anchor previo. Con barras + anchor: revalidar hielo; si muerto → none (o scan 4.6 solo si D3 lo permite — default: **no resucitar** tras hielo roto). **`contract:gen` = No.**                |

Si D2 = LPS gate, D3 = Alembic/tabla o cache sin tesis, D4 = `wyckoffPhase` / `contract:gen`, o D5 = ready exige LPS: **parar y replanificar**.

---

## 2. Alcance 4.7 (sí / no)

### Sí

| Pieza               | Regla                                                                                                                                                                                                                                                                                          |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Anchor              | Estructura mínima: `direction`, `ice` (precio), `springLow`/`springHigh` (o rango), opcional `springEndTs` / índice relativo, `phase` (`none`\|`spring`\|`reclaim`\|`sos`\|`lps`) solo evidencia. Escrito al propose cuando hay spring resuelto (hielo intacto).                               |
| Resolve             | `_resolve_wyckoff_spring(direction, bars, prior=None)`: si `prior` y hielo **no** roto por barras posteriores → usar prior; si prior y hielo roto → **None** (no resucitar ni caer a locate más viejo); si sin prior → `_locate_wyckoff_spring` 4.6.                                           |
| Reclaim / SOS / LPS | Mismos predicados 4.4–4.6 sobre el spring **resuelto**.                                                                                                                                                                                                                                        |
| EntrySetup          | `wyckoff` ⇔ spring resuelto + reclaim + hielo intacto. Prioridad `breakout > pullback > wyckoff > none` **intacta**.                                                                                                                                                                           |
| Wire propose        | Tras `build_trade_plan`, si hay locate/resolve vivo → meter `wyckoffSpringAnchor` en `runtime` de la sesión que ya se hace `append_decision_session`. Al construir plan, si store cableado → leer prior por `decision_id` (si existe sesión previa; en primer propose no hay).                 |
| Wire confirm        | Rebuild con barras: pasar prior desde sesión/runtime si existe; sin barras → none (D8).                                                                                                                                                                                                        |
| ARMED / ready       | Sin cambio 4.3 / 4.2 (D5–D6).                                                                                                                                                                                                                                                                  |
| Tests               | ≥4–5: (1) regresión 4.6 scan sin prior; (2) prior + hielo vivo → mismo spring aunque locate preferiría otro/más reciente; (3) prior + hielo roto → none / no wyckoff; (4) breakout sigue ganando; (5) confirm/rebuild sin barras → none; (+ propose con store escribe/lee anchor si cableado). |
| Docs cierre         | Tras implement: nota ADR-031 §6 Ciclo 4.7; stamp SoT + relevo.                                                                                                                                                                                                                                 |

### No

- Alembic / tabla nueva / Prisma / migración de schema
- `wyckoffPhase` en TradePlan / Board HTTP / `contract:gen` / UI panel
- LPS gate obligatorio; ready exige LPS
- Cache por símbolo sin `decision_id` / tesis
- Resucitar springs más viejos tras hielo roto del bound
- Cambiar ladder ARMED, stop/size 4.0, `NO_NEW_LONGS` 4.1, prioridad breakout>pullback, reclaim `k`, `WYCKOFF_LOOKBACK`
- `check_opening`, broker, F9-B, purge MONITOR, `PAPER_D_EXECUTE`, qty Confirm
- Position Manager / thesis health / MFE / trailing / T1 (Ciclo 5)
- Familias Lab como motor; pisar `suggestedQuantity` F3

---

## 3. Diseño (borrador)

```text
# resolve (nuevo 4.7)
_resolve_wyckoff_spring(direction, bars, prior=None):
  if prior:
    if ice_broken(prior, bars posteriores): return None
    return prior   # no re-locate
  return _locate_wyckoff_spring(...)   # 4.6

# reclaim / sos / lps / evidence — sobre resolve (no solo locate)
# classify_entry_setup — prioridad intacta; wyckoff = resolve + reclaim + hielo

# propose (wire)
prior = store.latest_session(decision_id)?.runtime.wyckoffSpringAnchor
plan = build_trade_plan(..., wyckoff_prior=prior)
session.runtime.tradePlan = plan
if spring_resuelto: session.runtime.wyckoffSpringAnchor = snapshot
append_decision_session(session)

# confirm rebuild
sin bars → none (no inventar desde prior)
con bars → resolve(prior desde sesión) + classify
```

**Ancla código (esperado tras OK):**

- `packages/py/analytics/.../trade_plan.py` — resolve + classify
- `packages/py/application/.../propose_recommendation.py` — leer/escribir runtime
- `packages/py/application/.../confirm_recommendation.py` — pasar prior al rebuild
- Tests: `test_trade_plan.py` + propose/confirm con store si aplica

**Invariant:** Ranking ≠ BUY. SETUP ≠ Lab. `ARMED` ≠ fill. Scan 4.6 = fallback sin tesis. Bound spring ≠ permiso. LPS/SM ≠ status ladder. Session JSONB ≠ Alembic.

---

## 4. Batería pactada

- ruff touched Python
- `pnpm test:decision-spine` (hoy **94**; +casos binding/hielo → esperado **98–100**)
- vitest `@bolsa/shared` **no** esperado (sin campo/tipo nuevo si D4 default)

---

## 5. Criterio de cierre 4.7

1. Sin prior: comportamiento = 4.6 (regresión).
2. Con prior + hielo vivo: classify usa el spring bound (no se “salta” a otro por lookback).
3. Hielo roto del bound → no `wyckoff`; no resucita.
4. Breakout artificial sigue ganando.
5. Confirm sin barras → `none` / no ARMED / no fase inventada por prior.
6. Diff `check_opening` vacío; stop/size/régimen/ARMED/prioridad/reclaim `k`/lookback intactos.
7. Sin `wyckoffPhase` en TradePlan; sin `contract:gen`; sin Alembic.
8. Relevo + stamp SoT. Commit/push solo con OK propietario.

---

## 6. Texto de arranque (tras OK D1–D8)

```text
Implementar Ciclo 4.7 Wyckoff thesis binding según plan-ciclo-47-wyckoff-thesis-binding-2026-08-25.md.
D1=anchor en DecisionSession.runtime thin · D2=LPS etiqueta; wyckoff=resolve+reclaim+hielo · D3=JSONB sesión por decision_id; sin Alembic · D4=sin wyckoffPhase/TradePlan/contract:gen · D5=ready=ta+setup · D6=ARMED 4.3 intacta · D7=sin why codes nuevos · D8=confirm sin barras=none; hielo roto no resucita.
No check_opening · no Alembic · no Position Manager · no thesis health · no F9-B/purge/broker · no Ciclo 5.
```
