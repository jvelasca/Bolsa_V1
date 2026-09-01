# Spec — V1.64 Browser E2E Integrated (UI journeys)

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA** (pre-flight local 2026-09-02).  
> **Padre:** [`spec-v163-decision-surface-placement-2026-09-02.md`](./spec-v163-decision-surface-placement-2026-09-02.md) · [`spec-v159-e2e-integrated-2026-09-02.md`](./spec-v159-e2e-integrated-2026-09-02.md). **No** LIVE.

Cierra la brecha **navegador → FastAPI → PostgreSQL** para journeys UI mínimos, complementando V1.59 (pytest ASGI) y V1.56 (GP-E2E mock).

```text
P0  GP-V164-UI-01 — Journal browser contra API real
P0  GP-V164-UI-02 — Consola operativa browser contra API real
P0  GP-V164-UI-03 — Mercado DECISIÓN panel/chart (GP-E2E-03 mock · opt-in integración)
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` off · no LIVE · package `1.35.0-beta` · V1.59 integration **intacta** · GP-E2E-01..02 mock **intactos**.

## 1. IN

| ID            | Comportamiento                                                                                           |
| ------------- | -------------------------------------------------------------------------------------------------------- |
| GP-V164-UI-01 | Playwright `/decision-journal` sin mocks cuando `E2E_INTEGRATION=1` · health OK · sin COMPRAR            |
| GP-V164-UI-02 | Playwright `/operational-console` sin mocks · excepciones-only                                           |
| GP-V164-UI-03 | Playwright configuración Mercado · toggle Panel/Gráfico (`GP-E2E-03`; cockpit cubierto por vitest V1.63) |

**Modos:**

| Env                               | Uso                                         |
| --------------------------------- | ------------------------------------------- |
| `E2E_RUN=1`                       | Mock API (Vite dev) — GP-E2E-01..03         |
| `E2E_INTEGRATION=1` + `E2E_RUN=1` | API real vía proxy Vite — GP-V164-UI-01..02 |

## 2. OUT

CI Playwright obligatorio en Release-tag · LIVE · sustituir GP-V159 · journeys Confirm live.

## 3. Pre-flight

```bash
# Mock browser (siempre reproducible sin PG)
E2E_RUN=1 pnpm --filter @bolsa/web e2e

# Integración (opt-in, requiere API+PG)
E2E_INTEGRATION=1 E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v164-ui

# Regresión stacks previos
python -m pytest apps/api-python/tests/integration/test_v159_e2e_paper_desk.py apps/api-python/tests/integration/test_v159_e2e_operational_wire.py -m integration -q
pnpm --filter @bolsa/web exec vitest run src/features/trading/operativa-cockpit-card.test.tsx src/features/charts/chart-decision-surface-hud.test.tsx
pnpm --filter @bolsa/web exec tsc --noEmit
```
