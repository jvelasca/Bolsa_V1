# Plan — Ciclo 4.8 Wyckoff surface + effort-result (cierre línea SETUP)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §1 SETUP · §6 (`Alembic / tabla dedicada Wyckoff / wyckoffPhase en contrato FE — 4.8+`, prohibido sin plan + decisión) · relevo [`traspaso-relevo-ciclo-47-wyckoff-thesis-binding-2026-08-25.md`](./traspaso-relevo-ciclo-47-wyckoff-thesis-binding-2026-08-25.md) · ancla en [`plan-ciclo-47-wyckoff-thesis-binding-2026-08-25.md`](./plan-ciclo-47-wyckoff-thesis-binding-2026-08-25.md) (excluye UI Why / effort-result → 4.8+).
> **AsOf:** 2026-08-25 · HEAD **`a10c356`** = `origin/main`; feat **`b381d06`**.
> **Estado:** **CERRADO en origin** (`b381d06` vía `a10c356`). D1–D8 OK · batería **104**.
> **Método:** rebanada fina de **cierre**; SETUP sigue ≠ motor paralelo; Ranking ≠ BUY; sin `contract:gen`; sin LLM.
> **Secuencia pedida (1+2+3):** (1) evidencia en superficie Hoy · (2) effort-result / volumen thin · (3) **cerrar** la línea Wyckoff SETUP; siguiente arco ADR-031 **fuera** de este plan (no Ciclo 5 PM).

---

## 0. Objetivo

Tras 4.0–4.7 la SM Wyckoff ya **clasifica**, **mira atrás** y **ancla** el spring a la tesis. Lo que falta para cerrar la línea SETUP es:

1. **Superficie:** que la mesa vea `entrySetup` + fase ya guardada en `runtime.wyckoffSpringAnchor.phase` (Hoy / panel Why), sin inventar motor ni `wyckoffPhase` en TradePlan.
2. **Effort-result thin:** etiquetar si el spring (y opcional reclaim) muestra esfuerzo vs resultado (volumen y/o rango vs ATR) sobre el spring **resuelto** 4.7; **sin** gate de setup ni de ready.
3. **Cierre de línea:** tras 4.8, no abrir más rebanadas Wyckoff (Alembic / `wyckoffPhase` contrato / acumulaciones multi-semana quedan **parked** hasta decisión distinta). E1 = otro arco ADR-031 (permiso/mesa/attribution…), **no** Position Manager.

### Qué entra vs qué queda fuera

| Incluye (thin 4.8)                                                                                         | Excluye (parked / otro arco)                                                |
| ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Hoy: mostrar `entrySetup` + fase (`spring`/`reclaim`/`sos`/`lps`) cuando el payload F3 trae anchor/runtime | `wyckoffPhase` en TradePlan / `@bolsa/shared` / Board HTTP / `contract:gen` |
| Echo thin de evidencia setup en F3 `extra`/`payload` si Hoy no ve `DecisionSession.runtime`                | Alembic / tabla dedicada Wyckoff / Prisma                                   |
| Helper effort-result sobre spring bound; snapshot opcional en `wyckoffSpringAnchor` (JSONB)                | LPS / effort como **gate** de `EntrySetup` o `entry_ready`                  |
| Tests spine + vitest Hoy si toca strip                                                                     | UI panel Wyckoff dedicado; Why codes nuevos en `whyNot` (vetos)             |
| Nota ADR-031 §6 «línea SETUP Wyckoff 4.0–4.8 CERRADA»; relevo + stamp                                      | Acumulación/distribución completa, ranges semanas, thesis health / MFE      |
| Sigue refinando evidencia SETUP; **no** sustituye Ranking ni `check_opening`                               | Ciclo 5 PM · F9-B · purge · broker · `PAPER_D_EXECUTE` · qty Confirm        |

**No** es Lab paralelo · **no** cambia ladder `ARMED` 4.3 · **no** toca stop/size 4.0 ni régimen 4.1 · prioridad `breakout > pullback > wyckoff` intacta · reclaim `k` / lookback / binding 4.7 intactos · LPS/SOS siguen etiqueta.

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                                       | Propuesta por defecto                                                                                                                                                                                                                                                                                                                                                 |
| --- | ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | ¿Alcance de **esta** rebanada?                 | **Cierre thin 4.8 = (1)+(2)+(3):** superficie Hoy + effort-result etiqueta + stamp «línea Wyckoff SETUP cerrada». **Sin** Alembic · **sin** `wyckoffPhase` en TradePlan · **sin** tocar ARMED / stop / size / régimen / prioridad EntrySetup / reclaim `k` / lookback / resolve 4.7. Si solo superficie **o** solo effort → **replanificar** (este plan asume ambos). |
| D2  | ¿LPS / effort como **gate** o etiqueta?        | **Etiqueta.** `EntrySetup=wyckoff` sigue = spring **resuelto** + reclaim 4.4 + hielo intacto. Effort-result / LPS / SOS **no** forzan ni bloquean. Si «wyckoff solo con LPS o effort OK» → **parar y replanificar**.                                                                                                                                                  |
| D3  | ¿Dónde vive la evidencia nueva?                | Extender snapshot `wyckoffSpringAnchor` en `DecisionSession.runtime` (JSONB): `phase` ya existe; añadir `effort` (p.ej. `none`\|`spring_low_effort`\|`spring_high_effort`\|`result_ok`\|`result_weak` — nombres finales en impl). Echo thin hacia F3 payload para Hoy. **Sin** Alembic. Pedir tabla / campo TradePlan → **parar**.                                    |
| D4  | ¿Campo JSON / `wyckoffPhase` en contrato?      | **Sin** `wyckoffPhase` / `effort` en TradePlan / `@bolsa/shared` tipos canónicos. Hoy lee `entrySetup` (ya en TradePlan) + fase/effort desde echo F3/`runtime` no tipado en contrato OpenAPI. Si se pide Board HTTP tipado o `contract:gen` → **parar y replanificar**.                                                                                               |
| D5  | ¿Interacción con `entry_ready`?                | Igual 4.2–4.7: `entry_ready_from_ta` **y** `setup != "none"`. Fase / effort **no** entran en ready.                                                                                                                                                                                                                                                                   |
| D6  | ¿Interacción con `ARMED` (4.3)?                | **Intacta.** Superficie/effort no añaden estados ni actionability distinta.                                                                                                                                                                                                                                                                                           |
| D7  | ¿Códigos `why` / Why surface?                  | **Sí superficie thin (opción 1):** Hoy panel muestra bloque «Setup» (`entrySetup` + fase + effort si hay). **Sin** códigos nuevos en `whyNot` (siguen siendo vetos: `entry`/`regime`/…). Sin chip/kind nuevo en la cola. Copy mínima, sin panel Wyckoff.                                                                                                              |
| D8  | ¿Confirm sin barras / `contract:gen` / cierre? | Sin barras → `none` / no inventar fase ni effort desde prior (igual 4.7). **`contract:gen` = No.** Tras merge: ADR-031 §6 marca **línea SETUP Wyckoff 4.0–4.8 CERRADA**; E1 = otro arco (propietario), **no** 4.9 Wyckoff ni Ciclo 5 PM por defecto.                                                                                                                  |

Si D2 = gate, D3 = Alembic/TradePlan, D4 = `contract:gen` / `wyckoffPhase` tipado, D5 = ready exige effort/LPS, o D1 = solo uno de (1)/(2) sin el otro: **parar y replanificar**.

---

## 2. Alcance 4.8 (sí / no)

### Sí

| Pieza            | Regla                                                                                                                                                                                                                            |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Effort-result    | Sobre spring **resuelto** (`_resolve_wyckoff_spring`): comparar volumen (bars ya traen `volume` en propose) y/o rango de la barra spring vs media prior / ATR. Etiqueta en anchor; sin volumen usable → fallback rango o `none`. |
| Anchor           | `snapshot_wyckoff_spring_anchor` incluye `effort` (opcional) además de `phase`. Parse tolera ausencia (regresión 4.7).                                                                                                           |
| Classify / gates | **Sin cambio** a predicado `wyckoff` ni prioridad ni ready ni ARMED.                                                                                                                                                             |
| Superficie Hoy   | Strip/dialog: línea Setup con `entrySetup`; si `entrySetup===wyckoff` y hay fase/effort en payload echo → mostrarlos. Tests vitest Hoy.                                                                                          |
| Wire propose     | Echo `runtime.wyckoffSpringAnchor` (o subset phase/effort) en sitio que F3/Hoy ya lean (mismo patrón tradePlan en extra) **sin** OpenAPI nuevo.                                                                                  |
| Cierre docs      | ADR-031 §6 + CURRENT_SYSTEM + relevo 4.8 + índice: «SETUP Wyckoff 4.0–4.8 cerrado»; siguiente ≠ Wyckoff thin.                                                                                                                    |
| Tests            | Spine: effort etiqueta + regresión 4.7 binding/hielo; classify sin cambio. Hoy: render Setup. Diff `check_opening` vacío.                                                                                                        |

### No

- Alembic / tabla / Prisma / `wyckoffPhase` en TradePlan / Board tipado / `contract:gen`
- Effort o LPS como gate; ready exige effort
- Cambiar ladder ARMED, stop/size, `NO_NEW_LONGS`, prioridad breakout>pullback, reclaim `k`, lookback, resolve/hielo 4.7
- `check_opening`, broker, F9-B, purge, `PAPER_D_EXECUTE`, qty Confirm
- Position Manager / thesis health / MFE / trailing / T1 (Ciclo 5)
- Acumulación multi-semana / distribution full / ranges
- Ciclo 4.9 Wyckoff por defecto tras este cierre

---

## 3. Diseño (borrador)

```text
# effort (nuevo 4.8) — etiqueta, no gate
_wyckoff_effort_evidence(direction, bars, prior=None, atr=None):
  locate = _resolve_wyckoff_spring(...)
  if locate is None: return "none"
  # volume spring vs mean(prior)  y/o  range spring vs ATR
  → etiqueta thin (impl fija umbrales constantes, documentados)

# snapshot anchor
{ direction, ice, springLow, springHigh, phase, effort? }

# classify_entry_setup — INTACTO (4.7)

# propose
anchor = snapshot_...(prior=...)
session.runtime.wyckoffSpringAnchor = anchor
# echo subset a F3 payload para Hoy (sin contract:gen)

# Hoy dialog
Why not (vetos)  |  Setup: entrySetup · phase · effort
```

**Ancla código (esperado tras OK):**

- `packages/py/analytics/.../trade_plan.py` — effort helper + snapshot
- `packages/py/application/.../propose_recommendation.py` — echo F3 si hace falta
- `apps/web/.../hoy-command-strip.tsx` (+ test) · posiblemente `hoy-queue` solo si hace falta tipar item local
- Tests: `test_trade_plan.py` · Hoy vitest
- Docs: ADR-031 §6 · CURRENT_SYSTEM · relevo 4.8 · engineering-index

**Invariant:** Ranking ≠ BUY. SETUP ≠ Lab. `ARMED` ≠ fill. Bound spring ≠ permiso. Effort/LPS ≠ ladder. Superficie ≠ contrato OpenAPI. Cierre 4.8 ≠ abrir Ciclo 5.

---

## 4. Batería pactada

- ruff touched Python
- `pnpm test:decision-spine` (hoy **100**; +casos effort/regresión → esperado **102–106**)
- vitest Hoy / `@bolsa/shared` **solo** si toca strip o cola (sin tipos TradePlan nuevos si D4 default)

---

## 5. Criterio de cierre 4.8

1. Classify / ARMED / ready / prioridad / binding hielo = regresión 4.7.
2. Anchor puede llevar `effort`; ausencia = comportamiento 4.7.
3. Hoy muestra Setup (`entrySetup` ± fase/effort) sin `whyNot` nuevos.
4. Effort **no** cambia `EntrySetup=wyckoff`.
5. Confirm sin barras → none / no inventa fase ni effort.
6. Diff `check_opening` vacío; sin Alembic; sin `wyckoffPhase` TradePlan; sin `contract:gen`.
7. Docs: línea SETUP Wyckoff **cerrada**; E1 ≠ 4.9 Wyckoff ni Ciclo 5 PM por defecto.
8. Relevo + stamp SoT. Commit/push solo con OK propietario.

---

## 6. Texto de arranque (tras OK D1–D8)

```text
Implementar Ciclo 4.8 Wyckoff surface + effort-result (cierre SETUP) según plan-ciclo-48-wyckoff-surface-effort-cierre-2026-08-25.md.
D1=superficie Hoy + effort etiqueta + cierre línea · D2=effort/LPS etiqueta; wyckoff=resolve+reclaim+hielo · D3=effort en wyckoffSpringAnchor JSONB + echo F3 · D4=sin wyckoffPhase/TradePlan/contract:gen · D5=ready=ta+setup · D6=ARMED 4.3 intacta · D7=Hoy Setup thin; sin whyNot nuevos · D8=confirm sin barras=none; stamp línea Wyckoff cerrada; E1≠PM.
No check_opening · no Alembic · no Position Manager · no thesis health · no F9-B/purge/broker · no Ciclo 5.
```

---

## 7. Tras 4.8 (opción 3 — no implementar aquí)

Candidatos de **otro arco** (elige el propietario en el chat post-relevo 4.8):

- Integrity / mesa (orphan, Board echo, Actionability server…)
- Attribution / Journal thin (ADR-031 diferido Ciclo 6)
- Shadow AUTO / paper flags (solo con decisión explícita)
- **No** por defecto: Alembic Wyckoff · `wyckoffPhase` contrato · Ciclo 5 PM
