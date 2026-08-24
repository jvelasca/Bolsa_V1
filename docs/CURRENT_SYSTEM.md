# CURRENT_SYSTEM — estado real de Bolsa V1

> **Padre:** [engineering-index](./engineering/engineering-index-2026-08-03.md) §1 (Architecture).
> **Para quién:** el siguiente chat, un auditor, Cursor. No es el historial (`PROJECT_STATE.md`).
> **AsOf:** 2026-08-24 · working tree **DS-03 mandate** (post audit-stamp `5100d23`). Ciclo **U6** `9e9a346` → **DS-05** `15e86a4` → **ops** `5100d23` **CERRADO** · **DS-03** en working tree. Prove Spine S0–S3 + H5 + UX mesa U0–U6 + **DS-05 freshness** + **DS-03 mandate gate**.
> **Tag:** `v1.6.0-beta` → `c3964fc`. **BETA / no producción.**

---

## Stack

React 19 + Vite (`apps/web`) · FastAPI `:8000` (`apps/api-python`) · PostgreSQL · SQLAlchemy + **Alembic = autoridad de migraciones** · Prisma en `packages/database` **degradado** (seed/léxico, no schema dual) · JWT multi-user (ADR-027 C).

## Identidad

Doble cara congelada: **QROS** (Lab, ADR-011) + **Investment OS** (mesa) unidos por el **Decision Spine**. Lab/Radar **fuera** del spine (D3, ADR-019). LLM **nunca** ejecuta.

## Features activas

Embudo / Lista AUTO / Finalistas · DÍA D · CORE-R · CORE-P · FA/FIE · SEMI (Trading · Señales · Confirmar · Libro) · UX mesa U0–U6 (Ayuda tips · S/R presets · Confirm drawer · Fit chips · proyección orden chart F3 · **preview ticket margen/comisión** en Confirm/drawer, UI-only) · Decision Board **solo lectura** (`/decision-board`) · PortfolioFit v1 (concentración cesta activo+sector, VETO) · **DS-05 Data Freshness Gate** en `check_opening` (SEMI ohlcv + AUTO `signal.timestamp`, VETO >5d) · **DS-03 Account Mandate Gate** en `check_opening` (tenure BD `mandate_tenures`, VETO sin mandato abierto / mismatch AUTO) · paper/DEMO · prep AUTO A0–A5.

## Features congeladas

`PAPER_D_EXECUTE` **off** · sin broker live · Belief / gobernanza IA · Track B B1–B12 cerrado (no reabrir) · `pending-delete` E8 N · purge storage N.

## Auth (real)

Auth viva = **JWT + cookie HttpOnly** (R-12 / ADR-027). `APP_PASSWORD` es un **overlay opcional de login en dev**, no el modelo de auth. La frase histórica «auth JWT diferida (D4)» está **obsoleta**.

## Ejecución (camino actual)

```
Dato → Assessment → run_decision_runtime → DecisionPackage
  → Policy Gate + check_opening (Fit de cesta + DS-05 freshness + DS-03 mandate)
  → ConfirmRecommendationIntent (SEMI, humano)  O  ExecutionRouter (AUTO paper)
  → ExecuteTrade (ledger paper)
```

SEMI y AUTO son **el mismo risk de cesta**, distinta autorización (D1). `DecisionPackage` es el contrato de identidad en el confirm (D2).

## Limitaciones conocidas (no son bugs de esta rebanada)

- Ranking IO sigue en cliente (`operativa-index.ts`).
- Dos call-sites a `ExecuteTrade` (TO-BE: convergencia **antes** del fill) — diferido.
- Dictamen (`DailyOpinionService`) no entra solo al Runtime; puede acabar en SEMI por alarma.
- Aperturas orphan sin package: `contract=absent`, **sí ejecutan** (H3; freeze doc-only).
- Confirm SEMI: perfil activo vía `active_profile_id` → `check_opening` (H5 CERRADA; mismo SoT AUTO). Sin perfil → defaults moderate.
- Composite `portfolioConstraints` sigue `not_evaluated`; Fit vive al lado.
- **DS-03 Account Mandate Gate CERRADA (working tree 2026-08-24):** tenure abierto server-side (`mandate_tenures` vía sync cliente) → `check_opening` VETO fail-closed sin mandato / mismatch estrategia AUTO. Adopción UI (`strategy-adoption`) sigue siendo proyección cliente; el gate usa BD. Exits fuera. Batería `pnpm test:decision-spine` **53**.
- Sin OrderProposal / Journal / Attribution.

## Tests

| Comando                    | Qué cubre                                                                     |
| -------------------------- | ----------------------------------------------------------------------------- |
| `pnpm test:decision-spine` | Cadena decisión: confirm SEMI, Fit, risk, AUTO veto router, Golden, **DS-05** |
| `pnpm test:semi`           | UI/libro DEMO F3 (no es el spine)                                             |
| `pnpm test:operativa`      | DÍA D + CORE-R                                                                |
| `pnpm test:py`             | Pytest amplio                                                                 |

## Open risks (ops, no código)

`TRUSTED_PROXIES` prod — IPs/CIDR reales del edge proxy pendientes del propietario (runbook: `ops-trusted-proxies-prod-runbook-2026-08-24.md`). GitHub secret scanning + push protection **enabled** 2026-08-24 (verificar UI). Purga opcional historial git dev (decisión explícita).
