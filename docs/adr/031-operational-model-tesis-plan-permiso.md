# ADR-031: Modelo operativo — tesis ≠ plan ≠ permiso (TradePlan v0)

**Estado:** Aceptado  
**Fecha:** 2026-08-24  
**Contexto:** Hoja de ruta operativa post-`v1.7.0-beta` (auditoría externa + auditoría propia). El Decision Spine (Fase 0) ya es autoridad de **permiso**. Falta el objeto de **plan condicional** (RFC-008 Execution Engine) y comprimir la mañana a 2–5 acciones firmables.

**Depende de:** [RFC-008](../rfc/008-cognitive-decision-architecture.md) · [ADR-019](./019-dual-universes-lab-vs-trading.md) · [ADR-029](./029-order-proposal-decision-journal.md) · [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [estudio SEMI](../engineering/estudio-flujo-semi-vs-tops-2026-08-21.md).

---

## 1. Decisión

Tres capas, un solo spine. **No** se crea un segundo motor de decisión.

| Capa        | Objeto                                              | Pregunta                                                              | Autoridad                 |
| ----------- | --------------------------------------------------- | --------------------------------------------------------------------- | ------------------------- |
| **Tesis**   | `DecisionPackage`                                   | ¿Qué creemos y con qué evidencia?                                     | `run_decision_runtime`    |
| **Plan**    | `TradePlan` v0 (extiende la tesis, no la sustituye) | Si ocurre X, ¿qué haríamos? (estado, stop, size, caducidad, `whyNot`) | mapper determinista       |
| **Permiso** | `check_opening`                                     | ¿Podemos llenar ahora?                                                | Risk Engine (SEMI = AUTO) |

```text
QUALITY / OPPORTUNITY     →  score TA + TOP + opinion (calculan; no son BUY)
SETUP                     →  Wyckoff / DÍA D / CORE-R (evidencia; no motor paralelo)
ENTRY READINESS           →  WATCH | ARMED | TRIGGERED | BLOCKED | EXPIRED
TRADEPLAN                 →  DecisionPackage + EntryPlan mínimo + size + expiry + whyNot
PERMISSION                →  check_opening (único veto de fill)
ACTION QUEUE              →  proyección UI (Hoy) sobre Decision Board + cola F3
```

**Ranking ≠ BUY.** Un TOP o un dictamen `buy` es candidato. BUY operativo = `TradePlan.status == TRIGGERED` **y** `check_opening` ALLOW **y** firma humana (SEMI).

**0 operaciones hoy** con gates correctos es una métrica de calidad, no un fallo.

---

## 2. TradePlan v0 (mínimo; no el mockup de 40 campos)

Campos canónicos:

- identidad: `decisionId`, `instrumentId`, dirección
- `status`: `WATCH` \| `ARMED` \| `TRIGGERED` \| `BLOCKED` \| `EXPIRED`
- entry: zona + trigger **o** no listo
- `structuralStop` obligatorio para `TRIGGERED`; no se acerca el stop para caber en el riesgo — se reduce size o se rechaza
- `quantity` = `risk_amount / (entry − stop)` cuando hay stop válido
- `expiresAt` (TTL de sesión; típico barra diaria + 1)
- `whyNot[]`: `fit` / `freshness` / `mandate` / `entry` / `no_stop` / `expired` / `orphan`

**No** en v0: T2, trailing, thesis-health, MFE/MAE, attribution, familias Entry Engine completas, `NO_NEW_LONGS` por régimen (Ciclo 4+).

Jerarquía de perfil (ya cierta en código; solo nombrar):

`InvestorProfile` → `TradingPolicy` → Mandate (DS-03) → `ExecutionPolicy` (SEMI/AUTO) → `PositionPolicy`

LLM **nunca** calcula SL/TP/size ni salta un gate. Como mucho, revisor narrativo (fuera de v0).

---

## 3. Integridad SEMI (Ciclo 1) — decisiones

1. **TTL:** `Recommendation.expiresAt` en el pasado → `rejected_by_gate` / `expired`; no fill.
2. **Precio:** aperturas con OHLCV cableado revalidan último `close` vs `suggestedPrice` (desviación relativa máxima 2 %). Fuera de banda → `stale_price`.
3. **pending_orders:** el fill ya no llama `ExecuteTrade` desde el monitor FE. Pasa por `FillPendingOrder` → `check_opening` (compras / aperturas) → ledger.
4. **Doble confirm concurrente:** la clave de idempotencia sigue siendo `decision_id`; test de carrera verifica un solo fill lógico.
5. **H3 orphan (aperturas):** con `cognitive_store` cableado (producción), una apertura sin `DecisionPackage` de sesión → `orphan_opening_blocked` fail-closed. Exits sin package siguen `unknown_position_side`. Wiring de test sin store conserva el comportamiento legado (mismo patrón que `ohlcv=None`).

---

## 4. Daily Command (Ciclo 3)

**No** es una god-page ni una sexta puerta. Las 5 puertas aprobadas (Trading · Señales · Confirmar · Libro + Lab fuera) se mantienen.

**Hoy** = strip de compresión en la mesa (`TradingLayout`) sobre `GetDecisionBoard` + cola F3. Click → panel Why / Why not + firmar (drawer Confirmar existente).

---

## 5. Golden scenarios (papel; tests cubren A/B/C/D/G/H; E/F diferidos)

| Id    | Nombre                        | Entrada                                                   | Resultado                                                                               |
| ----- | ----------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| **A** | Breakout perfecto             | Bull, calidad alta, entry ready, stop estructural, Fit OK | `TRIGGERED` + size > 0                                                                  |
| **B** | Gran activo / mala entrada    | Quality alta, `entry_ready=False`                         | `WATCH` (no BUY)                                                                        |
| **C** | Gran setup / veto cartera     | Fit concentración/sector                                  | `BLOCKED`                                                                               |
| **D** | Stop demasiado lejos          | Size se reduce; no se mueve el stop                       | **Ciclo 4.0:** swing más lejano gana; qty baja                                          |
| **E** | Posición ganadora T1          | Protección / trail                                        | **Ciclo 5.1:** advisory `protectPlan` (T1 + protect_hint; sin mutar stop; trail → 5.2+) |
| **F** | Tesis se degrada, precio > SL | `REVIEW`                                                  | **Ciclo 5.0:** advisory `thesisHealth.status=review` (≠ TradePlan ladder)               |
| **G** | Régimen BULL → BEAR           | `NO_NEW_LONGS`                                            | **Ciclo 4.1:** long + `risk_off`/`crisis` → `BLOCKED`/`regime`                          |
| **H** | Plan caducado                 | `expiresAt` pasado                                        | `EXPIRED` / confirm no ejecuta                                                          |

---

## 6. Qué queda diferido (Ciclo 4+)

**Ciclo 4.0 (cerrado `1cbd021`):** stop estructural ATR×1.5 + swing 10 barras cerradas (el más lejano), `entry_ready` por bias TA (sin exhaustion), size con `GetPortfolioSummary.total_equity` y `max_risk_per_trade_pct` de la plantilla. Sin familias `EntrySetup`. Confirm rebuild sin barras sigue `WATCH`/`no_stop`. `check_opening` intacto.

**Ciclo 4.1 (cerrado `97f4862`):** `NO_NEW_LONGS` en capa Plan — long + régimen `risk_off`/`crisis` → `BLOCKED` + `whyNot: regime`. Shorts permitidos. Confirm sin régimen no inventa veto. `check_opening` intacto.

**Ciclo 4.2 (cerrado `a7eeaee`):** `EntrySetup` `breakout|pullback|wyckoff|none` refina `entry_ready` (ta + setup≠none). Campo `entrySetup` en TradePlan. Sin `ARMED`. Sin `contract:gen`. `check_opening` intacto.

**Ciclo 4.3 (cerrado `4eb99a2`):** `ARMED` en ladder — stop válido + `entry_setup≠none` + `!entry_ready` → `ARMED` (qty 0, `whyNot: entry`, actionability 0.7). `TRIGGERED` solo con ready + stop + size. Confirm sin barras no inventa `ARMED`. Wyckoff stub 4.2 intacto. Sin `contract:gen`. `check_opening` intacto.

**Ciclo 4.4 (cerrado `7003ddf`):** Wyckoff formal thin — spring + reclaim estricto (`k×ATR=0.25` o fuera del rango spring) → `entrySetup=wyckoff`. SOS etiqueta interna; LPS diferido. Sin `wyckoffPhase`. Ladder ARMED 4.3 intacta. Sin `contract:gen`. `check_opening` intacto.

**Ciclo 4.5 (cerrado `baaa9b4`):** LPS etiqueta + SM single-window (`_detect_wyckoff_lps` · `_wyckoff_phase_evidence`: spring → reclaim → sos? → lps?). `EntrySetup=wyckoff` sigue = spring+reclaim 4.4 (LPS no gate). Sin `wyckoffPhase`. Sin multi-sesión. Sin `contract:gen`. `check_opening` intacto.

**Ciclo 4.6 (cerrado `fb6e801`):** SM Wyckoff lookback — `_locate_wyckoff_spring` (`WYCKOFF_LOOKBACK=40`) localiza spring vivo; reclaim/SOS/LPS sobre ese evento; hielo roto en cerradas posteriores → ninguna (no resucita). LPS sigue etiqueta. Sin persistencia store. Sin `wyckoffPhase`. Sin `contract:gen`. `check_opening` intacto.

**Ciclo 4.7 (cerrado `604fd90`):** thesis binding thin — `_resolve_wyckoff_spring` + `wyckoffSpringAnchor` en `DecisionSession.runtime` (JSONB); prior bound por `decision_id` si hielo intacto; hielo roto → none (no resucita ni cae a locate). LPS etiqueta. Sin Alembic. Sin `wyckoffPhase` en TradePlan. Sin `contract:gen`. `check_opening` intacto.

**Ciclo 4.8 (cerrado `b381d06`):** surface + effort-result — `_wyckoff_effort_evidence` en anchor; echo F3; Hoy Setup (`entrySetup` + phase + effort); Board `extra` anidado. Effort/LPS etiqueta. **Línea SETUP Wyckoff 4.0–4.8 CERRADA.** Sin Alembic. Sin `wyckoffPhase` TradePlan. Sin `contract:gen`. `check_opening` intacto.

**Ciclo 4.9 (cerrado `e569003`):** mesa Board session echo — `tradePlan` + `wyckoffSpringAnchor` desde `runtime` en `DecisionSessionView` / DTO a mano; Hoy usa plan vivo (heurística solo sin plan); WhyNot labels `regime`/`orphan`/`rr`. Sin Alembic. Sin `contract:gen`. Sin Actionability/IO server. `check_opening` intacto.

**Ciclo 6 Attribution thin (cerrado `7de91e5`):** snapshot setup en journal payloads · `human_confirm`/`human_reject` · SEMI `gate_evaluated` · UI Setup + Replay. **Sin** MFE/expectancy. Sin Alembic. Sin `contract:gen`. `check_opening` intacto.

**Ciclo 5.0 Thesis Health thin (cerrado `a2f32bb`):** mapper Golden F → `runtime.thesisHealth` · Board/Hoy «Revisar tesis» · **sin** `TradePlan.status=REVIEW` · sin trail/T1/MFE · `check_opening` intacto.

**Ciclo 5.1 Protect/T1 thin (cerrado `12d05d2`):** mapper Golden E → `runtime.protectPlan` · Hoy «Proteger» si MFE≥1R · T1=entry±1R · `suggestedProtectStop=entry` · **sin** mutar `structuralStop` · sin trail/exit · `check_opening` intacto.

**Ciclo 5.2 Exit Radar thin (cerrado `e813aa3`):** mapper → `runtime.exitRadar` · Hoy «Salida» · prioridad exit > time_stop > trail · **sin** auto-exit · **sin** EvaluatePositionExits · **sin** mutar stop · `check_opening` intacto.

**Ciclo 5.3 MFE/MAE thin (cerrado `fd44a03`):** mapper → `runtime.mfeMae` · peak MFE/MAE (barras / close_proxy) · Hoy «Excursión» métricas · **sin** expectancy · **sin** CTA acción · `check_opening` intacto.

**Ciclo I1 ExecuteTrade converge (cerrado `2bd5cd8`):** `allow_opening_fill` compartido Confirm + Fill + HTTP. `POST /portfolio/trade` buy → `check_opening` (403 `risk_veto`); sell skip. Router AUTO no fusionado. Sin Alembic / `contract:gen` / Shadow. `check_opening` intacto.

**Ciclo I2 Actionability/IO (código; stamp SHA pendiente):** fórmula `compute_indice_operativo` + echo `indiceOperativo` en chip Composite. Rank Estudio sigue cliente. IO ≠ permiso. `TradePlan.actionability` intacta. Sin Alembic / `contract:gen` / Shadow. `check_opening` intacto.

No abrir sin fase propia:

- Alembic / tabla dedicada Wyckoff / `wyckoffPhase` en contrato FE — **parked** (no 4.9 por defecto)
- Trailing continuo broker, bracket, T1 parcial fill
- Thesis Health **plena** (persistencia Confidence lifecycle cableada)
- Expectancy por setup (Attribution **plena**; MFE/MAE thin = 5.3)
- Shadow AUTO / `PAPER_D_EXECUTE` / broker live
- Reescritura de `bolsa_application/`, microservicios, LLM en la decisión crítica
- F9-B, purge storage E8

Freeze vigente: LAB ≠ TRADING · LLM no ejecuta · Actionability TradePlan es server · fórmula IO es server (chip) · rank Estudio puede seguir en cliente · **SETUP Wyckoff cerrado** · advisory Thesis Health / Protect / Exit Radar / MFE-MAE ≠ permiso.

---

## 7. Consecuencias

- Un ADR más no compite con `CURRENT_SYSTEM`: este documento fija **política**; el estado vivo sigue en [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
- Código: tipos en `@bolsa/shared` + mapper puro en `bolsa_analytics.cognitive.trade_plan`; confirm/fill/HTTP buy no duplican autoridad de `check_opening` (`allow_opening_fill`).
