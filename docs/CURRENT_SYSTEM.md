# CURRENT_SYSTEM — estado real de Bolsa V1

> **Padre:** [engineering-index](./engineering/engineering-index-2026-08-03.md) §1 (Architecture).
> **Para quién:** el siguiente chat, un auditor, Cursor. No es el historial (`PROJECT_STATE.md`).
> **AsOf:** 2026-08-25 · **ADR-031** tesis ≠ plan ≠ permiso. HEAD previo **`17a386d`** = `origin/main` (TradePlan en propose/confirm). Ciclo 4.0 stop/entry_ready/size **en working tree (pendiente commit)**. Relevo: [`traspaso-relevo-ciclo-40-stop-entry-size-2026-08-25.md`](./engineering/traspaso-relevo-ciclo-40-stop-entry-size-2026-08-25.md). Alembic `010` en `bolsa_v1`.
> **Tag:** **`v1.7.0-beta` → `e3b943a`** (en origin). Previo: `v1.6.0-beta` → `c3964fc`. **BETA / no producción.**

---

## Stack

React 19 + Vite (`apps/web`) · FastAPI `:8000` (`apps/api-python`) · PostgreSQL · SQLAlchemy + **Alembic = autoridad de migraciones** · Prisma en `packages/database` **degradado** (seed/léxico, no schema dual) · JWT multi-user (ADR-027 C).

## Identidad

Doble cara congelada: **QROS** (Lab, ADR-011) + **Investment OS** (mesa) unidos por el **Decision Spine**. Lab/Radar **fuera** del spine (D3, ADR-019). LLM **nunca** ejecuta.

## Features activas

Embudo / Lista AUTO / Finalistas · DÍA D · CORE-R · CORE-P · FA/FIE · SEMI (Trading · **Señales** `/screeners` · Confirmar · Libro) · strip **Hoy** en mesa (ADR-031; no rival de las 5 puertas) · **Asesor** `/research` (ledger/tesis; nav menú, no bucle diario) · UX mesa U0–U6 (Ayuda tips · S/R presets · Confirm drawer · Fit chips · proyección orden chart F3 · **preview ticket margen/comisión** en Confirm/drawer, UI-only) · Decision Board **solo lectura** (`/decision-board`) · **Decision Journal** **solo lectura** (`/decision-journal`, ADR-029) · **TradePlan v0** (WATCH/TRIGGERED/BLOCKED/EXPIRED) · PortfolioFit v1 (concentración cesta activo+sector, VETO) · **DS-05 Data Freshness Gate** en `check_opening` (SEMI ohlcv + AUTO `signal.timestamp`, VETO >5d) · **DS-03 Account Mandate Gate** en `check_opening` (tenure BD `mandate_tenures`, VETO sin mandato abierto / mismatch AUTO) · paper/DEMO · prep AUTO A0–A5.

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
- Dos call-sites a `ExecuteTrade` (TO-BE: convergencia **antes** del fill) — diferido.
- Dictamen (`DailyOpinionService`) no entra solo al Runtime; puede acabar en SEMI por alarma.
- Aperturas orphan sin package: con store cableado (producción) → **`orphan_opening_blocked`** (H3, ADR-031). Wiring de test sin store = legado.
- Confirm SEMI: TTL `expiresAt` y revalidación de último close vs `suggestedPrice` (banda 2 %).
- `pending_orders` fill: `POST /api/pending-orders/{id}/fill` (ya no `executeTrade` directo desde el monitor).
- Confirm SEMI: perfil activo vía `active_profile_id` → `check_opening` (H5 CERRADA; mismo SoT AUTO). Sin perfil → defaults moderate.
- Composite `portfolioConstraints` sigue `not_evaluated`; Fit vive al lado.
- **DS-03 Account Mandate Gate CERRADA (`41adb8e`):** tenure abierto server-side (`mandate_tenures` vía sync cliente) → `check_opening` VETO fail-closed sin mandato / mismatch estrategia AUTO. Adopción UI (`strategy-adoption`) sigue proyección cliente; el gate usa BD. Exits fuera. Batería `pnpm test:decision-spine` **75**.
- TradePlan Ciclo 4.0: stop ATR×1.5 + swing (más lejano), `entry_ready` por bias TA, size con equity de cartera. Confirm rebuild sin barras → `WATCH`/`no_stop`. `suggestedQuantity` del ticket F3 **no** se pisa con `TradePlan.quantity`. Decision Board HTTP **no** expone `tradePlan` en sesiones (sin `contract:gen`).
- OrderProposal / Journal **F1–F3 CERRADOS** (timeline `/decision-journal` read-only; Alembic `010` en `bolsa_v1`). Attribution **sin abrir** (Ciclo 6, ADR-031 §6).
- Diferido ADR-031: Entry families, `NO_NEW_LONGS`, thesis health / exit radar, MFE-MAE, Shadow AUTO, broker.

## Tests

| Comando                    | Qué cubre                                                                                                                                                |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pnpm test:decision-spine` | Cadena decisión: confirm SEMI (TTL/precio/H3), Fit, risk, pending fill, TradePlan A/B/C/H + 4.0 stop/ready/size, AUTO veto, Golden, **DS-05**, **DS-03** |
| `pnpm test:semi`           | UI/libro DEMO F3 (no es el spine)                                                                                                                        |
| `pnpm test:operativa`      | DÍA D + CORE-R                                                                                                                                           |
| `pnpm test:py`             | Pytest amplio                                                                                                                                            |

## Open risks (ops, no código)

`TRUSTED_PROXIES` prod — IPs/CIDR reales del edge proxy pendientes del propietario (runbook: `ops-trusted-proxies-prod-runbook-2026-08-24.md`). GitHub secret scanning + push protection **enabled** 2026-08-24 (verificar UI). Purga opcional historial git dev (decisión explícita).
