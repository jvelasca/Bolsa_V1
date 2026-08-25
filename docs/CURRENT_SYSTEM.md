# CURRENT_SYSTEM — estado real de Bolsa V1

> **Padre:** [engineering-index](./engineering/engineering-index-2026-08-03.md) §1 (Architecture).
> **Para quién:** el siguiente chat, un auditor, Cursor. No es el historial (`PROJECT_STATE.md`).
> **AsOf:** 2026-08-25 · **ADR-031** tesis ≠ plan ≠ permiso. HEAD **`a2f32bb`** = Ciclo 5.0 Thesis Health thin. Relevo vivo: [`traspaso-relevo-ciclo-5-thesis-health-thin-2026-08-25.md`](./engineering/traspaso-relevo-ciclo-5-thesis-health-thin-2026-08-25.md). Alembic `010` en `bolsa_v1`.
> **Tag:** **`v1.7.0-beta` → `e3b943a`** (en origin). Previo: `v1.6.0-beta` → `c3964fc`. **BETA / no producción.**

---

## Stack

React 19 + Vite (`apps/web`) · FastAPI `:8000` (`apps/api-python`) · PostgreSQL · SQLAlchemy + **Alembic = autoridad de migraciones** · Prisma en `packages/database` **degradado** (seed/léxico, no schema dual) · JWT multi-user (ADR-027 C).

## Identidad

Doble cara congelada: **QROS** (Lab, ADR-011) + **Investment OS** (mesa) unidos por el **Decision Spine**. Lab/Radar **fuera** del spine (D3, ADR-019). LLM **nunca** ejecuta.

## Features activas

Embudo / Lista AUTO / Finalistas · DÍA D · CORE-R · CORE-P · FA/FIE · SEMI (Trading · **Señales** `/screeners` · Confirmar · Libro) · strip **Hoy** en mesa (ADR-031; no rival de las 5 puertas) · **Asesor** `/research` (ledger/tesis; nav menú, no bucle diario) · UX mesa U0–U6 (Ayuda tips · S/R presets · Confirm drawer · Fit chips · proyección orden chart F3 · **preview ticket margen/comisión** en Confirm/drawer, UI-only) · Decision Board **solo lectura** (`/decision-board`) · **Decision Journal** **solo lectura** (`/decision-journal`, ADR-029) · **TradePlan v0** (WATCH/ARMED/TRIGGERED/BLOCKED/EXPIRED) · PortfolioFit v1 (concentración cesta activo+sector, VETO) · **DS-05 Data Freshness Gate** en `check_opening` (SEMI ohlcv + AUTO `signal.timestamp`, VETO >5d) · **DS-03 Account Mandate Gate** en `check_opening` (tenure BD `mandate_tenures`, VETO sin mandato abierto / mismatch AUTO) · paper/DEMO · prep AUTO A0–A5.

## Features congeladas

`PAPER_D_EXECUTE` **off** · sin broker live · Belief / gobernanza IA · Track B B1–B12 cerrado (no reabrir) · `pending-delete` E8 N · purge storage N.

## Auth (real)

Auth viva = **JWT + cookie HttpOnly** (R-12 / ADR-027). `APP_PASSWORD` es un **overlay opcional de login en dev**, no el modelo de auth. La frase histórica «auth JWT diferida (D4)» está **obsoleta**.

## Ejecución (camino actual)

Tres capas (ADR-031): **tesis** (`DecisionPackage`) ≠ **plan** (`TradePlan` v0) ≠ **permiso** (`check_opening`). Ranking / TOP / dictamen **no** son BUY.

```
Dato → Assessment → run_decision_runtime → DecisionPackage (tesis)
  → TradePlan v0 en propose (`data.tradePlan` + `runtime.tradePlan`) y echo en confirm
  → Policy Gate + check_opening (Fit de cesta + DS-05 freshness + DS-03 mandate)
  → ConfirmRecommendationIntent (SEMI, humano; TTL + precio + H3 orphan fail-closed)
     O  ExecutionRouter (AUTO paper, flag off)
     O  FillPendingOrder (pending_orders; mismo check_opening en aperturas)
  → ExecuteTrade (ledger paper)
```

SEMI y AUTO son **el mismo risk de cesta**, distinta autorización (D1). `DecisionPackage` es el contrato de identidad en el confirm (D2). `TradePlan` **no** sustituye el spine: lo extiende.

Mesa: strip **Hoy** en Trading (compresión Decision Board + cola F3). Prefiere `tradePlan` vivo del payload F3; si no hay, heurística de buckets. No es una sexta puerta; Confirmar sigue siendo la firma.

## Limitaciones conocidas (no son bugs de esta rebanada)

- Ranking IO sigue en cliente (`operativa-index.ts`).
- Tres call-sites spine a `ExecuteTrade` (Confirm · ExecutionRouter · FillPendingOrder) + HTTP crudo `POST /portfolio/trade` (sin `check_opening`). TO-BE convergencia pre-fill / unificación de puertos — **parked M–L** (no thin post-Ciclo 6).
- Dictamen (`DailyOpinionService`) no entra solo al Runtime; puede acabar en SEMI por alarma.
- Aperturas orphan sin package: con store cableado (producción) → **`orphan_opening_blocked`** (H3, ADR-031). Wiring de test sin store = legado.
- Confirm SEMI: TTL `expiresAt` y revalidación de último close vs `suggestedPrice` (banda 2 %).
- `pending_orders` fill: `POST /api/pending-orders/{id}/fill` (ya no `executeTrade` directo desde el monitor).
- Confirm SEMI: perfil activo vía `active_profile_id` → `check_opening` (H5 CERRADA; mismo SoT AUTO). Sin perfil → defaults moderate.
- Composite `portfolioConstraints` sigue `not_evaluated` (peso 0); Fit real en `check_opening`. Nota/UI: no es «pendiente de puntuar en Composite».
- **DS-03 Account Mandate Gate CERRADA (`41adb8e`):** tenure abierto server-side (`mandate_tenures` vía sync cliente) → `check_opening` VETO fail-closed sin mandato / mismatch estrategia AUTO. Adopción UI (`strategy-adoption`) sigue proyección cliente; el gate usa BD. Exits fuera. Batería `pnpm test:decision-spine` **75**.
- TradePlan Ciclo 4.0: stop ATR×1.5 + swing (más lejano), `entry_ready` por bias TA, size con equity de cartera. Confirm rebuild sin barras → `WATCH`/`no_stop`. `suggestedQuantity` del ticket F3 **no** se pisa con `TradePlan.quantity`. Decision Board HTTP **sí** expone `tradePlan` (+ anchor) en sesiones desde Ciclo 4.9 (sin `contract:gen`).
- TradePlan Ciclo 4.1: `NO_NEW_LONGS` — long + `risk_off`/`crisis` → `BLOCKED`/`regime`. Shorts OK. Confirm sin régimen no veta. `check_opening` intacto.
- TradePlan Ciclo 4.2: `entrySetup` breakout/pullback/wyckoff/none; `entry_ready` = bias TA **y** setup≠none. Sin `contract:gen`.
- TradePlan Ciclo 4.3: `ARMED` = stop válido + setup≠none + `!entry_ready` (qty 0, `executionAllowed=false`, `whyNot: entry`, actionability 0.7). Golden A sigue `TRIGGERED`. Confirm sin barras no inventa `ARMED`. Sin `contract:gen`.
- TradePlan Ciclo 4.4: Wyckoff formal — spring + reclaim estricto (`WYCKOFF_RECLAIM_ATR_K=0.25` **o** close fuera del rango spring). SOS etiqueta interna. Sin `wyckoffPhase`. Sin `contract:gen`.
- TradePlan Ciclo 4.5: LPS etiqueta + SM single-window (`spring→reclaim→sos?→lps?`); `wyckoff` sigue = spring+reclaim. Sin multi-sesión. Sin `wyckoffPhase`. Sin `contract:gen`.
- TradePlan Ciclo 4.6: `_locate_wyckoff_spring` lookback 40; reclaim/SOS/LPS sobre spring vivo; hielo roto (cerradas) → none. LPS etiqueta. Sin store. Sin `wyckoffPhase`. Sin `contract:gen`.
- TradePlan Ciclo 4.7: `_resolve_wyckoff_spring` + `wyckoffSpringAnchor` en `DecisionSession.runtime`; bound por `decision_id` si hielo intacto; hielo roto → none. Sin Alembic. Sin `wyckoffPhase` en TradePlan. Sin `contract:gen`.
- TradePlan Ciclo 4.8 (**cierre línea SETUP Wyckoff**): `_wyckoff_effort_evidence` en anchor (`effort`); echo `wyckoffSpringAnchor` en propose/F3; Hoy dialog Setup (`entrySetup` + phase + effort); Board `semiF3.extra` anidado. Effort/LPS **etiqueta**. Sin Alembic. Sin `wyckoffPhase` TradePlan. Sin `contract:gen`.
- Mesa Ciclo 4.9: Board sesiones echo `tradePlan` + `wyckoffSpringAnchor` desde `runtime` (`DecisionSessionViewDto` a mano); Hoy usa plan vivo (deja heurística); WhyNot labels `regime`/`orphan`/`rr`. Sin Alembic. Sin `contract:gen`. Sin Actionability/IO server.
- **Ciclo 5.0 Thesis Health thin:** mapper Golden F (`mapThesisHealth` / `map_thesis_health`) → `runtime.thesisHealth` en propose; Board/Hoy echo; dialog «Revisar tesis» si `status=review`. **No** `TradePlan.status=REVIEW`. **No** trail/T1/MFE. `check_opening` intacto. Cola Hoy `REVIEW` (EXPIRED) ≠ thesis review.
- OrderProposal / Journal **F1–F3 CERRADOS** (timeline `/decision-journal` read-only; Alembic `010` en `bolsa_v1`). **Attribution thin Ciclo 6:** snapshot setup en payloads (`entrySetup`/`tradePlanStatus`/phase/effort) · `human_confirm`/`human_reject` · SEMI `gate_evaluated` · UI Setup line + Replay. **MFE/expectancy** siguen parked.
- Diferido ADR-031: Alembic/tabla Wyckoff / `wyckoffPhase` contrato (parked), Position Manager / Exit Radar / trailing / T1 (Golden E → 5.1+), thesis health **plena** (persistencia Confidence lifecycle), MFE-MAE/expectancy plena, Shadow AUTO, broker, ExecuteTrade converge. **No** reabrir Wyckoff thin por defecto.

## Tests

| Comando                    | Qué cubre                                                                                                                                                                                                             |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm test:decision-spine` | Cadena decisión: confirm SEMI (TTL/precio/H3), Fit, risk, pending fill, TradePlan A/B/C/H/G + 4.0–4.8 + Board echo 4.9 + Journal Attribution 6 + Thesis Health 5.0, AUTO veto, Golden, **DS-05**, **DS-03** (**121**) |
| `pnpm test:semi`           | UI/libro DEMO F3 (no es el spine)                                                                                                                                                                                     |
| `pnpm test:operativa`      | DÍA D + CORE-R                                                                                                                                                                                                        |
| `pnpm test:py`             | Pytest amplio                                                                                                                                                                                                         |

## Open risks (ops, no código)

`TRUSTED_PROXIES` prod — IPs/CIDR reales del edge proxy pendientes del propietario (runbook: `ops-trusted-proxies-prod-runbook-2026-08-24.md`). GitHub secret scanning + push protection **enabled** 2026-08-24 (verificar UI). Purga opcional historial git dev (decisión explícita).
