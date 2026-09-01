# Plan — V1.59 E2E Integrated (FastAPI + PostgreSQL)

> **Padre:** [`spec-v159-e2e-integrated-2026-09-02.md`](./spec-v159-e2e-integrated-2026-09-02.md) · [ADR-043](../adr/043-position-automation.md).  
> **AsOf:** 2026-09-02.  
> **Estado:** **implementación CERRADA** — tag **`v1.59-beta` → `b5c5c6ab`**.

| ID  | Entrega                                                                 | Estado |
| --- | ----------------------------------------------------------------------- | ------ |
| D0  | spec/plan V1.59 (+ stamp CURRENT_SYSTEM / relevo cuando owner pida tag) | DONE   |
| P0a | Harness `@pytest.mark.integration` + skip sin PG                        | DONE   |
| P0b | `test_v159_e2e_paper_desk.py` GP-V159-01..03                            | DONE   |
| P1a | `test_v159_e2e_operational_wire.py` GP-V159-04..05                      | DONE   |
| P1b | GP-V159-06 incident resolve/clear HTTP                                  | DONE   |
| P2  | GP-V159-07 execute-auto dry_run                                         | DONE   |
| R1  | relevo + arranque auditor + pre-flight                                  | DONE   |

Local post close-out: integration **7/7** · application V1.58 block **22/22** · ruff OK · `opening_gate_seed` serie plana 120d (fix sanity DS-05) · relevo + arranque auditor stampados.

## Orden de implementación

1. **P0a** — Extraer helper `_integration_client()` (app + lifespan + AsyncClient) si reduce duplicación; no tocar rutas prod.
2. **P0b** — GP-V159-01 trade + portfolio operational; GP-V159-02 cycle dry-run; GP-V159-03 gate 403.
3. **P1a** — ops-self-eval recon + decision-journal list.
4. **P1b** — GP-V159-06: traducir seed drift de `test_paper_desk_golden_session_adverse` / GP-SESSION-10r a llamadas HTTP incident.
5. **P2** — GP-V159-07 solo si 01..06 estables.
6. **R1** — `traspaso-relevo-v1-59-e2e-integrated-2026-09-02.md` + `arranque-auditor-v1-59-*.md` al cerrar.

## Criterios de cierre

```bash
python -m pytest packages/py/application/tests/test_paper_desk_golden_day_adversarial.py packages/py/application/tests/test_paper_desk_golden_day.py packages/py/application/tests/test_paper_desk_golden_session_adverse.py packages/py/application/tests/test_inv_operational_truth.py -q
python -m pytest apps/api-python/tests/integration/test_v159_e2e_paper_desk.py apps/api-python/tests/integration/test_v159_e2e_operational_wire.py -m integration -q
python -m ruff check apps/api-python/tests/integration packages/py/application/src/bolsa_application --config pyproject.toml
```

Con PG levantado: GP-V159-01..06 **passed**. Sin PG: integration **skipped**, application block **22+ passed** (sin regresión V1.58).

## No hacer

LIVE · bump package · encender `PAPER_D_EXECUTE` default · scheduler · Alembic · Playwright CI obligatorio · reescribir Golden Session en HTTP · cambiar política PAPER stop cerrado · UX Mercado (V1.60).
