# Spec — V1.67 Browser E2E Mercado Integrated

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (pre-flight local 2026-09-02).  
> **Padre:** [`spec-v166-decision-explainability-2026-09-02.md`](./spec-v166-decision-explainability-2026-09-02.md) · partida **V1.66** (`a23c8e8b`). **No** LIVE.

Cierra la brecha **navegador → FastAPI → PostgreSQL** en el terminal **Mercado** (`/trading`), con cuenta/seed aislados por corrida. Complementa GP-V164-UI (Journal/Consola) y GP-E2E-03 (mock placement).

```text
P0  GP-V167-01 — Journey Mercado contra API real (cockpit DECISIÓN visible)
P0  GP-V167-02 — Sin CTA COMPRAR indebido
P0  GP-V167-03 — Superficie CONTEXTO · ESTADO · ACCIÓN
P0  GP-V167-04 — Posición o entrada según portfolio seed (fail-closed honesto)
P1  GP-V167-05 — Toggle ¿Por qué? → decision-explain-panel
P1  GP-V167-06 — Aislamiento: cuenta e2e-v167-* + guard DB documentado
P1  GP-V167-07 — pytest seed harness (paridad HTTP con Playwright)
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · sin bump package · V1.66 intacto · GP-V164-UI mock intacto.

## 1. IN

| ID         | Comportamiento                                                                                                             |
| ---------- | -------------------------------------------------------------------------------------------------------------------------- |
| GP-V167-01 | Playwright `/trading` sin mocks cuando `E2E_INTEGRATION=1` · health OK · `operativa-cockpit` visible · fase ≠ sin_contexto |
| GP-V167-02 | Sin botón primario `COMPRAR` en Mercado                                                                                    |
| GP-V167-03 | `decision-contexto` · `decision-estado` · `decision-accion` visibles                                                       |
| GP-V167-04 | Si seed buy OK → `position-operational-star-card`; si no → `entry-decision-surface` (entrada honesta)                      |
| GP-V167-05 | Click `operativa-cockpit-why` → `decision-explain-panel` visible                                                           |
| GP-V167-06 | `ensureMercadoIntegrationFixture` crea cuenta `e2e-v167-{uuid}`; doc aislamiento DB                                        |
| GP-V167-07 | pytest valida seed HTTP (cuenta + mandate + trade opcional + portfolio)                                                    |

**Modos:**

| Env                               | Uso                                      |
| --------------------------------- | ---------------------------------------- |
| `E2E_RUN=1`                       | Mock API — GP-E2E-01..03                 |
| `E2E_INTEGRATION=1` + `E2E_RUN=1` | API real — GP-V164-UI + **GP-V167**      |
| `E2E_ALLOW_DEV_DB=1`              | Opt-in mutar PG local (cuentas efímeras) |
| `E2E_DATABASE_URL` (doc)          | PG dedicado E2E ≠ dev (recomendado CI)   |

## 2. OUT

CI Playwright obligatorio en Release-tag · LIVE · sustituir GP-V159 · journeys Confirm live · LISTA→GRÁFICO→ACCIÓN unificado.

## 3. Pre-flight

```bash
# Mock browser (sin PG)
E2E_RUN=1 pnpm --filter @bolsa/web e2e

# Integración Mercado (opt-in, requiere API+PG)
E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v167-mercado

# Regresión stacks previos
python -m pytest apps/api-python/tests/integration/test_v167_mercado_e2e_seed.py -m integration -q
pnpm --filter @bolsa/web exec vitest run src/features/trading/operativa-cockpit-card.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
```
