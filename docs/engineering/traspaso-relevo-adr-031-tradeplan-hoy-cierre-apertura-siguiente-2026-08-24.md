# RELEVO / TRASPASO — ADR-031 TradePlan v0 + integridad SEMI + strip Hoy (2026-08-24)

> **Padre:** [`engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md) §1 (Product / Ops).
> **Política:** [`docs/adr/031-operational-model-tesis-plan-permiso.md`](../adr/031-operational-model-tesis-plan-permiso.md).
> **SoT corto:** [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).
> **Propósito:** texto de paso para el **NUEVO AGENTE / NUEVO CHAT** tras implementar la hoja de ruta operativa (Ciclos 0–3). **Stamp 2026-08-24:** código en **`818b0c7`** (local, **sin push**).
> **AsOf:** 2026-08-24.
> **Chat origen:** [Hoja ruta operativa](96e2bb7b-7223-4a9d-ad34-00ecbc90b39b).

---

## 1. Estado verificado (firma — no adivinar)

| Campo            | Valor                                                                                                                           |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **HEAD**         | **`818b0c7`** (ADR-031 Ciclos 0–3). `origin/main` = **`020975c`**. **Verificar:** `git fetch && git rev-parse HEAD origin/main` |
| **Tag**          | `v1.7.0-beta` → `e3b943a` (intacto). Previo `v1.6.0-beta` → `c3964fc`                                                           |
| **Working tree** | **LIMPIO** post-`818b0c7` + stamp docs de este cierre                                                                           |
| **Alembic**      | `010_decision_journal_entries` en `bolsa_v1` (no-op; este slice no migró)                                                       |
| **F9-B**         | **PARKED**                                                                                                                      |
| **Purge V2**     | MONITOR · E8 **N**                                                                                                              |
| **Commit**       | **`818b0c7`** · **NO pusheado**                                                                                                 |

`git status -sb` al stamp: `main` 1 commit ahead of `origin/main` (`818b0c7` sobre `020975c`).

---

## 2. Qué está HECHO (Ciclos 0–3)

Tres capas, **un solo spine**. No se creó un segundo motor.

| Capa        | Objeto            | Pregunta                         |
| ----------- | ----------------- | -------------------------------- |
| **Tesis**   | `DecisionPackage` | ¿Qué creemos?                    |
| **Plan**    | `TradePlan` v0    | Si ocurre X, ¿qué haríamos?      |
| **Permiso** | `check_opening`   | ¿Podemos llenar ahora? SEMI=AUTO |

**Ranking ≠ BUY.** BUY operativo = `TradePlan.status == TRIGGERED` **y** gate ALLOW **y** firma humana.

### Ciclo 0 — docs

- ADR-031 (golden A–H en papel; diferido §6).
- `CURRENT_SYSTEM` · HELP · CHANGELOG Unreleased · engineering-index · backlog · cadena H3.

### Ciclo 1 — integridad SEMI

| Hueco           | Comportamiento                                                                 |
| --------------- | ------------------------------------------------------------------------------ |
| TTL             | `expiresAt` pasado → `rejected_by_gate` / `expired`, sin fill                  |
| Precio          | último close vs `suggestedPrice`, banda **2 %** → `stale_price`                |
| H3 orphan       | store cableado (prod) → `orphan_opening_blocked`. Tests **sin** store = legado |
| pending_orders  | `POST /api/pending-orders/{id}/fill` → `check_opening` en compras              |
| Carrera confirm | mismo `decision_id` → 1 fill + replay                                          |

Monitor FE: `api.fillPendingOrder` (**fetch crudo**, no openapi-fetch). Éxito/expired invalidan query; **no** DELETE de nuevo (el backend ya borra).

### Ciclo 2 — TradePlan v0

- Py: `bolsa_analytics.cognitive.trade_plan` (`build_trade_plan`, `compute_risk_size`).
- TS: `@bolsa/shared` `trade-plan.ts`.
- Size = `(equity × risk%) / |entry − stop|`. Sin stop estructural → no `TRIGGERED`.
- Goldens A/B/C/H en `test_trade_plan.py`.

**Hueco real:** el mapper **existe y se testea**; **aún no** viaja en el payload de `propose` / confirm. La tira Hoy **no** llama a `build_trade_plan`.

### Ciclo 3 — Hoy (no 6ª puerta)

- `mapDecisionBoardToHoyQueue` = proyección de Decision Board + cola F3 (máx. 8).
- UI: `hoy-command-strip.tsx` en `trading-layout.tsx`. Clic → Why / Why not + drawer Confirmar.
- **No** es TradePlan live. Chips de estado son heurística de buckets (pending→BUY, veto→BLOCKED, deferred→WATCH, auto→ARMED).

### Ciclo 4+ — diferido (ADR-031 §6)

Entry families · `NO_NEW_LONGS` · Thesis Health / Exit Radar · MFE-MAE · attribution · Shadow AUTO · broker · LLM en path crítico · mover `bolsa_application/`. **No abrir sin fase nueva + E1.**

---

## 3. Ficheros clave (working tree)

| Área         | Path                                                                                                   |
| ------------ | ------------------------------------------------------------------------------------------------------ |
| Política     | `docs/adr/031-operational-model-tesis-plan-permiso.md`                                                 |
| Confirm      | `packages/py/application/src/bolsa_application/confirm_recommendation.py`                              |
| Fill pending | `packages/py/application/src/bolsa_application/fill_pending_order.py`                                  |
| Mapper       | `packages/py/analytics/src/bolsa_analytics/cognitive/trade_plan.py`                                    |
| Shared       | `packages/shared/src/cognitive/trade-plan.ts` · `hoy-queue.ts`                                         |
| Mesa         | `apps/web/src/features/trading/hoy-command-strip.tsx`                                                  |
| Monitor      | `apps/web/src/features/trading/pending-orders-monitor.tsx`                                             |
| API client   | `apps/web/src/lib/api.ts` (`fillPendingOrder`)                                                         |
| Contrato     | `apps/web/api/openapi.json` + `schema.d.ts` (regen del fill)                                           |
| Batería      | `scripts/research/verify_decision_spine_battery.mjs` (+ `test_trade_plan` + `test_fill_pending_order`) |

---

## 4. Batería (sesión implementación)

| Check                                       | Resultado                                                     |
| ------------------------------------------- | ------------------------------------------------------------- |
| Spine pytest (TTL/precio/H3/fill/TradePlan) | **63 passed** (antes ~53)                                     |
| `pnpm --filter @bolsa/shared build`         | **obligatorio** antes de vitest web (usa dist)                |
| Hoy strip + hoy-queue vitest                | OK tras build shared                                          |
| `tsc -b --noEmit` `@bolsa/web`              | OK                                                            |
| Ruff touched Python                         | limpio (I001)                                                 |
| Smoke navegador `/trading` Hoy              | **NO hecho** (sin browser en la sesión)                       |
| `dump_openapi.py` print                     | spec **sí** escrito; print `→` puede fallar cp1252 en Windows |

---

## 5. Residuos / trampas (el nuevo agente DEBE saber)

1. **Sin commit.** No inventar que está en `origin/main`.
2. **Hoy ≠ TradePlan.** Cablear `build_trade_plan` en propose/confirm es **fase nueva**, no “arreglar el strip”.
3. Shared: web importa **dist**. Tras tocar `packages/shared`, `pnpm --filter @bolsa/shared build`.
4. Precio: si `get_latest_close` es `None`, se **salta** la banda 2 % (compat tests); DS-05 sigue gating por fecha de barra.
5. H3: producción inyecta `cognitive_store` → orphan bloqueado. Tests sin store ejecutan (legado, como `ohlcv=None`).
6. `FillPendingOrder` vive en application e importa repos SQLAlchemy (mismo patrón que `pending_orders.py` existente).
7. Freeze: `PAPER_D_EXECUTE` off · sin broker · F9-B parked · E8 N · LLM no calcula SL/TP/size/gates.
8. `contract:check` si se commitea el OpenAPI regen (endpoint fill nuevo).

---

## 6. Tarea del siguiente chat

**PASO 0 — E1:** el propietario decide. El agente **no** abre Ciclo 4+ ni Entry Engine por inercia.

Candidatas ancladas:

| Prioridad | Acción                                                          | Notas                                                                    |
| --------- | --------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **P0**    | **Commit** del working tree ADR-031                             | **HECHO** `818b0c7`. Stamp docs este cierre. **No push** salvo petición. |
| P1        | Smoke navegador tira Hoy + drawer Confirmar + fill pending      | Tras `run-dev`                                                           |
| P1        | Cablear TradePlan en `propose` / payload confirm                | Fase acotada; Hoy podría leer el plan de verdad                          |
| —         | Ciclo 4+ ADR-031 §6                                             | **Prohibido** sin plan + decisión                                        |
| Ops       | Purge V2 T+4 sem (~2026-09-19) · `TRUSTED_PROXIES` prod = owner | Sin código                                                               |

---

## 7. TEXTOS DE PASO (pegar en el chat nuevo)

### 7.1 Brief de arranque

```
CONTEXTO (2026-08-24): repo Bolsa_V1. HEAD local `818b0c7` (ADR-031 Ciclos 0–3) + stamp docs.
origin/main = `020975c`. Tag v1.7.0-beta → e3b943a. Working tree LIMPIO. Sin push.

LEE PRIMERO (read-first, obligatorio):
- docs/engineering/traspaso-relevo-adr-031-tradeplan-hoy-cierre-apertura-siguiente-2026-08-24.md
- docs/adr/031-operational-model-tesis-plan-permiso.md
- docs/CURRENT_SYSTEM.md
- docs/engineering/backlog-trabajo-2026-08-20.md §0
- docs/PROJECT_PREMISES.md ⭐§0
- docs/engineering/PROJECT_STATE.md (header)

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine. TradePlan EXTIENDE el spine,
no lo sustituye. Ranking ≠ BUY. LAB ≠ TRADING. LLM nunca ejecuta.

HECHO (`818b0c7`): TTL + precio 2% + H3 orphan fail-closed (store on) + pending fill
vía check_opening + TradePlan mapper A/B/C/H + strip Hoy (proyección Decision Board, NO
mapper live). Batería spine 63. Shared build obligatorio para tests web.

TAREA INMEDIATA: el propietario decide (E1).
1) Smoke Hoy en navegador.
2) Fase nueva: cablear TradePlan en propose/confirm.
3) Push de `818b0c7` (+ stamp) solo si lo pide.
NO abrir Ciclo 4+ (Entry / NO_NEW_LONGS / thesis health / MFE / Shadow AUTO / broker)
sin plan + decisión.

NO TOCAR: F9-B · purge storage · motor money internals · gobernanza IA · PAPER_D_EXECUTE ·
Track B B1–B12 · 5ª puerta extra · god-page Command Center.

Protocolo: una fase = subagente acotado + batería + aprobación por commit.
```

### 7.2 Coordinador — commit (solo si el propietario lo pide)

No inventar mensaje. Verificar `git status` / `git diff` / `git log -8`. Incluir untracked ADR-031. No `--no-verify`. No push. No tag.

---

## 8. Enlaces

- ADR-031 · CURRENT_SYSTEM · HELP
- Plan Cursor (no editar): `hoja_ruta_operativa_5bf68e81.plan.md`
- Relevo previo (histórico CI): [`traspaso-relevo-ruff-i001-ci-stamp-24e-2026-08-24.md`](./traspaso-relevo-ruff-i001-ci-stamp-24e-2026-08-24.md)
- Journal F1–F3: [`traspaso-relevo-order-proposal-journal-cierre-f1-f3-2026-08-24.md`](./traspaso-relevo-order-proposal-journal-cierre-f1-f3-2026-08-24.md)
- Premisas E1–E9: `docs/PROJECT_PREMISES.md`
