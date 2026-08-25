# Plan — Ciclo 4.9 Board session TradePlan echo (mesa / Daily Command)

> **Padre:** [ADR-031](../adr/031-operational-model-tesis-plan-permiso.md) §4 Daily Command · §6 (Actionability server diferida; ranking IO puede seguir en cliente) · relevo [`traspaso-relevo-ciclo-48-wyckoff-surface-effort-cierre-2026-08-25.md`](./traspaso-relevo-ciclo-48-wyckoff-surface-effort-cierre-2026-08-25.md) §4 E1 · síntesis subagentes 2026-08-25 (mesa integrity + audit docs).
> **AsOf:** 2026-08-25 · feat **`e569003`**; D1–D8 **OK**.
> **Estado:** **CERRADO** en `e569003`. Batería spine **106**.
> **Método:** rebanada fina mesa; Ranking ≠ BUY; sin Alembic; sin `contract:gen`; sin LLM; sin Ciclo 5 PM.
> **Secuencia:** (A) echo `tradePlan` (+ anchor thin) en sesiones Board · (B) labels WhyNot en Hoy.

---

## 0. Objetivo

Tras 4.8, F3→Hoy ya ve `tradePlan` / Setup. Las **sesiones** del Decision Board **no** exponen `tradePlan` ni `wyckoffSpringAnchor`: `DecisionSessionView.to_dict` y `DecisionSessionViewDto` los omiten; Hoy lee `session.tradePlan` (tipo TS ya opcional) y cae a **heurística de gate** (AUTO/veto/defer pueden verse como ARMED/BUY/BLOCKED sin plan real).

Cerrar el eslabón Daily Command (ADR-031 §4): Board HTTP → Hoy usa plan vivo de sesión cuando existe en `payload.runtime`.

### Qué entra vs qué queda fuera

| Incluye (thin 4.9 mesa)                                                                          | Excluye (parked / otro arco)                                                          |
| ------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| Mapear `runtime.tradePlan` (y opcional `wyckoffSpringAnchor`) al construir `DecisionSessionView` | Wyckoff classify / lookback / binding / effort gate · Alembic · `wyckoffPhase`        |
| Echo en `to_dict` + campo opcional en `DecisionSessionViewDto` (edición a mano)                  | `contract:gen` / OpenAPI regenerado                                                   |
| Hoy: si hay `tradePlan` en sesión → status/whyNot/Setup del plan (ya cableado en `hoy-queue`)    | Mover ranking IO (`operativa-index`) a servidor · Actionability nueva                 |
| (B) Labels WhyNot: `regime` / `orphan` / `rr` (y afines ya en enum)                              | Deep-link Confirmar por símbolo (salvo micro si cabe sin scope creep)                 |
| Tests Board + hoy-queue (+ strip si B)                                                           | Dual `ExecuteTrade` · Attribution Ciclo 6 · Shadow AUTO · H3/TTL/precio (ya cerrados) |
| Docs stamp + relevo 4.9                                                                          | Ciclo 5 PM · F9-B · purge · broker · `PAPER_D_EXECUTE` · qty Confirm                  |

**No** toca `check_opening` · ladder ARMED · stop/size · EntrySetup classify · F3 shape (salvo consumo).

---

## 1. Decisión pendiente (propietario)

| Id  | Pregunta                            | Propuesta por defecto                                                                                                                                                                                                                   |
| --- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | ¿Alcance?                           | **A + B mínimo:** Board echo `tradePlan` (+ anchor thin opcional) **y** labels WhyNot (`regime`/`orphan`/`rr`). Si solo A → OK; si solo B sin A → **replanificar** (B sin echo no cierra el gap).                                       |
| D2  | ¿Qué campos echo en sesión?         | `tradePlan` desde `payload.runtime.tradePlan` (dict ya persistido). Opcional: `wyckoffSpringAnchor` (o subset phase/effort) para Setup en sesiones igual que F3. Sin plan en runtime → omitir (Hoy sigue heurística **solo** entonces). |
| D3  | ¿Anchor en DTO tipado o libre?      | **Libre / opcional:** `tradePlan: dict \| None` (o modelo mínimo ya usado) + `wyckoffSpringAnchor: dict \| None` en vista/DTO. **Sin** tipar `wyckoffPhase` en TradePlan. Pedir OpenAPI estricto nuevo → parar.                         |
| D4  | ¿`contract:gen`?                    | **No.** Editar `DecisionSessionViewDto` a mano (patrón 4.x). Shared `DecisionSessionViewV1.tradePlan?` **ya existe** — alinear wire.                                                                                                    |
| D5  | ¿Heurística F3/sesión sin plan?     | **Intacta como fallback.** Con plan vivo → `toHoyItem` usa plan (ya). **No** inventar `TRIGGERED`/BUY desde gate solo. (B no cambia gate→kind; solo copy WhyNot.)                                                                       |
| D6  | ¿`check_opening` / Confirm / H3?    | **Intacto.** Echo es lectura Board. Sin tocar fill paths.                                                                                                                                                                               |
| D7  | ¿Actionability / ranking IO server? | **Fuera.** `TradePlan.actionability` ya es server; IO ranking sigue cliente (ADR-031 §6).                                                                                                                                               |
| D8  | ¿Cierre / E1 siguiente?             | Tras merge: stamp CURRENT_SYSTEM + ADR-031 nota mesa echo · relevo 4.9. E1 ≠ Wyckoff · ≠ Ciclo 5 PM · Attribution solo con brief aparte.                                                                                                |

Si D1 = solo B, D4 = `contract:gen`, D7 = mover IO, o pedir dual ExecuteTrade en esta rebanada: **parar y replanificar**.

---

## 2. Alcance 4.9 (sí / no)

### Sí

| Pieza   | Regla                                                                                                                                                  |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Extract | Al listar sesiones: leer `rec.payload` → `runtime.tradePlan` / `runtime.wyckoffSpringAnchor` (tolerar ausencia; snake/camel si hace falta como en F3). |
| View    | `DecisionSessionView` campos opcionales + `to_dict` emite `tradePlan` / `wyckoffSpringAnchor` solo si hay.                                             |
| HTTP    | `DecisionSessionViewDto` campos opcionales; Pydantic no stripea.                                                                                       |
| Hoy     | Sin cambio de contrato TS si shared ya tipa `tradePlan?`; tests sesión **con** plan → no heurística de status. Setup desde anchor si se echo.          |
| B       | `whyLabel`: `regime`, `orphan`, `rr` (copy corta ES).                                                                                                  |
| Tests   | `test_decision_board` (+ API smoke si existe); `hoy-queue.test` sesión con plan; strip test si B. Diff `check_opening` vacío.                          |

### No

- Alembic / Prisma / `wyckoffPhase` TradePlan / classify Wyckoff / effort gate
- `contract:gen` · Actionability/IO server · dual `ExecuteTrade`
- Attribution / Journal writers · Shadow AUTO · PM / thesis health / MFE
- Cambiar buckets Board · inventar plan en confirm sin barras

---

## 3. Diseño (borrador)

```text
# decision_board.py
trade_plan = _runtime_trade_plan(rec.payload)   # runtime.tradePlan | None
anchor = _runtime_wyckoff_anchor(rec.payload)   # opcional
DecisionSessionView(..., trade_plan=..., wyckoff_spring_anchor=...)

# to_dict
+ tradePlan? / wyckoffSpringAnchor?

# DecisionSessionViewDto (a mano)
trade_plan: dict | None = Field(None, alias="tradePlan")
wyckoff_spring_anchor: dict | None = Field(None, alias="wyckoffSpringAnchor")

# hoy-queue (ya)
asLiveTradePlan(session.tradePlan)  # deja de ser siempre null vía HTTP

# hoy-command-strip whyLabel
regime | orphan | rr → copy ES
```

**Ancla código:**

- `packages/py/application/.../decision_board.py` (+ tests)
- `apps/api-python/.../schemas/accounts.py` (`DecisionSessionViewDto`)
- `packages/shared/src/decision-board.ts` (solo si falta `wyckoffSpringAnchor?`)
- `apps/web/.../hoy-command-strip.tsx` (+ test) si D1 incluye B
- Docs: CURRENT_SYSTEM · ADR-031 §6 nota · relevo 4.9 · index

**Invariant:** Ranking ≠ BUY. Echo ≠ permiso. Heurística solo sin plan. SETUP Wyckoff línea **sigue cerrada**.

---

## 4. Batería pactada

- ruff touched Python
- `pnpm test:decision-spine` (hoy **104**; +casos Board echo → esperado **105–108**)
- vitest `@bolsa/shared` hoy-queue (+ strip si B)

---

## 5. Criterio de cierre 4.9

1. Sesión con `runtime.tradePlan` → Board JSON incluye `tradePlan`; Hoy muestra status/whyNot del plan.
2. Sesión sin plan → omitir campos; heurística fallback intacta.
3. (Si B) WhyNot `regime`/`orphan`/`rr` con copy, no código crudo.
4. Diff `check_opening` vacío; sin Alembic; sin `contract:gen`; sin Wyckoff classify.
5. Relevo + stamp SoT. Commit/push solo con OK propietario.

---

## 6. Texto de arranque (tras OK D1–D8)

```text
Implementar Ciclo 4.9 Board session TradePlan echo (mesa) según plan-ciclo-49-board-session-tradeplan-echo-2026-08-25.md.
D1=A+B mínimo · D2=tradePlan (+ anchor thin) desde runtime · D3=DTO opcional a mano · D4=sin contract:gen · D5=heurística solo sin plan · D6=check_opening intacto · D7=sin Actionability/IO server · D8=stamp; E1≠Wyckoff/PM.
No Alembic · no classify Wyckoff · no dual ExecuteTrade · no Attribution · no Shadow AUTO · no Ciclo 5.
```

---

## 7. Fuera (no implementar aquí)

- Attribution Ciclo 6 (brief aparte)
- Actionability / ranking IO server
- Dual `ExecuteTrade` pre-fill
- Shadow AUTO / `PAPER_D_EXECUTE` / broker
- Ciclo 5 PM · thesis health · MFE · Wyckoff 4.9+
