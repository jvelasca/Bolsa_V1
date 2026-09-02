# Arranque auditor — V1.67 Browser E2E Mercado Integrated (2026-09-02)

> **Padre:** [`spec-v167-browser-e2e-mercado-integrated-2026-09-02.md`](./spec-v167-browser-e2e-mercado-integrated-2026-09-02.md) · partida **V1.66** CERRADA.

## Punta de partida

- Producto: **V1.66** Decision Explainability (`a23c8e8b`)
- Brecha: GP-V164 cubre Journal/Consola browser; Mercado solo mock (GP-E2E-03)

## Qué auditar

1. `apps/web/e2e/gp-v167-mercado-integrated.spec.ts` — journey real `/trading`
2. `apps/web/e2e/integration.ts` — `ensureMercadoIntegrationFixture` + guard DB
3. `apps/api-python/tests/integration/test_v167_mercado_e2e_seed.py` — paridad HTTP
4. Sin COMPRAR · cockpit fase ≠ sin_contexto · explain panel V1.66 cableado

## Run integración (opt-in)

```bash
# Terminal 1: API + PG
# Terminal 2:
E2E_INTEGRATION=1 E2E_RUN=1 E2E_ALLOW_DEV_DB=1 pnpm --filter @bolsa/web e2e -- gp-v167-mercado
```

## Next aparcado

Paper Autonomous Desk (V1.68) · LISTA→GRÁFICO→ACCIÓN · CI Playwright Release-tag.
