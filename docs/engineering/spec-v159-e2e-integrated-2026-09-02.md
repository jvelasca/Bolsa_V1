# Spec — V1.59 E2E Integrated (FastAPI + PostgreSQL)

> **AsOf:** 2026-09-02 · **Estado:** **implementación CERRADA** (tag pendiente).  
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [ADR-043](../adr/043-position-automation.md) · [`spec-v158-adversarial-execution-2026-09-01.md`](./spec-v158-adversarial-execution-2026-09-01.md) · tip certificado previo **`v1.58-beta` → `4c42f1fc`**. **No** LIVE.  
> **Arranque auditor:** [`arranque-auditor-v1-59-e2e-integrated-2026-09-02.md`](./arranque-auditor-v1-59-e2e-integrated-2026-09-02.md).

Cierra la brecha entre Golden Session pytest (application, in-memory / fakes) y el wire HTTP real. **Enfoque A** del relevo V1.58 §4: **pytest + ASGI client + PostgreSQL test** — reproducible en CI sin browser. **No** sustituye GP-SESSION / GOLDEN-DAY / INV en `packages/py/application`; los **complementa** con contratos API/DB.

```text
P0  Harness integration (create_app + lifespan + PG skip)
P0  GP-V159-01..03 — trade → portfolio operational → paper-desk dry-run
P1  GP-V159-04..06 — recon clean · journal read · incident resolve/clear HTTP
P2  GP-V159-07 — position-automation execute-auto dry_run (opcional si P0/P1 verdes)
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** (prod default; tests usan `dryRun=true` o seed explícito) · no LIVE · sin Alembic · sin bump package (`1.35.0-beta`) · sin scheduler · V1.54–V1.58 intactos salvo harness + tests nuevos.

Regla global: `Ranking ≠ Signal ≠ Proposal ≠ Authorization ≠ Order ≠ Fill`.

Regla de esta versión: **HTTP E2E certifica el wire, no re-certifica la política PAPER**. Golden Session / GOLDEN-DAY-ADV siguen siendo autoridad de ciclo; GP-V159-\* demuestran que `create_app()` + PG producen DTOs coherentes en rutas Mesa/Consola.

## 1. Harness — IN

| Pieza     | Comportamiento                                                                                                                                      |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ubicación | `apps/api-python/tests/integration/test_v159_e2e_*.py` + `v159_harness.py`                                                                          |
| Cliente   | `httpx.AsyncClient` + `ASGITransport(app=create_app())` dentro de `async with lifespan(app)` — patrón existente en `test_position_policies_flow.py` |
| DB        | PostgreSQL real (`docker bolsa-postgres` / `DATABASE_URL`); `@pytest.mark.integration`; `pytest.skip` si no hay conexión                            |
| Seed      | Reutilizar `tests/opening_gate_seed.seed_http_opening_allow` (serie plana 120d, sin veto sanity DS-05) para buys que pasen `check_opening`          |
| Auth      | JWT dev overlay existente; sin flujo Confirm live en suite                                                                                          |
| Windows   | `WindowsSelectorEventLoopPolicy` (ya en `apps/api-python/tests/conftest.py`)                                                                        |

**OUT harness:** Playwright obligatorio · levantar `:5173` · sustituir application Golden tests · CI job nuevo en Release-tag (opt-in local como V1.56 GP-E2E).

## 2. IN — P0 GP-V159-01..03 (paper desk + posiciones)

Archivo sugerido: `apps/api-python/tests/integration/test_v159_e2e_paper_desk.py`.

| ID         | Ruta / acción                                                                     | Comportamiento                                                                                                                                                                       |
| ---------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| GP-V159-01 | `POST /api/accounts` → `POST /api/portfolio/trade` (buy) → `GET /api/portfolio`   | Cuenta nueva + mandato/barras seed → trade 200 → posición abierta con `quantity > 0`; si el DTO expone `operational`, campos mínimos presentes (`operatingState` o equivalente wire) |
| GP-V159-02 | `POST /api/paper-desk/cycle?accountId=` body `{ "dryRun": true }`                 | 200 · `data.cycle` + `data.autoDesk` · **sin** mutación de qty (dry-run) · no exige `PAPER_D_EXECUTE`                                                                                |
| GP-V159-03 | `POST /api/paper-desk/cycle` body `{ "dryRun": false }` con `PAPER_D_EXECUTE` off | **403** `paper_auto_env_blocked` — gate I3 intacto                                                                                                                                   |

Secuencia mínima GP-V159-01→02 sobre **una** cuenta/instrumento; limpieza best-effort al final (delete policy/account si helpers existen; no dejar drift en PG compartida).

## 3. IN — P1 GP-V159-04..06 (recon · journal · incidentes)

Archivo sugerido: `apps/api-python/tests/integration/test_v159_e2e_operational_wire.py`.

| ID         | Ruta / acción                                              | Comportamiento                                                                                                                                                                                                                                 |
| ---------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| GP-V159-04 | `GET /api/risk/ops-self-eval?accountId=` tras trade limpio | `portfolioReconciliation.status` ∈ `{ "ok", "clean", "not_wired" }` — nunca `drift` en cuenta recién sembrada sin manipulación                                                                                                                 |
| GP-V159-05 | `GET /api/accounts/{id}/decision-journal`                  | 200 · envelope `data.entries` array · DTO valida (solo lectura; complementa GP-E2E-01 browser)                                                                                                                                                 |
| GP-V159-06 | Drift sintético → incident API → resolve → clear           | Sembrar drift reconocible (mismo patrón GP-SESSION-10r application) vía HTTP: `GET .../operational-incidents/active` → `POST .../resolve` (nota) → recon `clean` → `POST .../clear` · estados `open` → `resolved` → cleared; **sin** auto-heal |

GP-V159-06 reutiliza contrato DEX-3 ya certificado en application; aquí certifica **wire** Mesa/Consola (`accounts.py` incident routes).

## 4. IN — P2 GP-V159-07 (opcional)

| ID         | Ruta                                                                                       | Comportamiento                                                                                                     |
| ---------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| GP-V159-07 | `POST /api/position-automation/execute-auto?accountId=&instrumentId=` `{ "dryRun": true }` | 200 con posición abierta sembrada · `dryRun: true` · sin sell real; 403 si `dryRun: false` y `PAPER_D_EXECUTE` off |

Implementar solo si P0+P1 verdes sin flake; no bloquea cierre V1.59.

## 5. Relación con stacks previos

| Capa                           | Autoridad                                                                           | V1.59                                |
| ------------------------------ | ----------------------------------------------------------------------------------- | ------------------------------------ |
| Application Golden / ADV / INV | `packages/py/application/tests/test_paper_desk_*` · `test_inv_operational_truth.py` | **Intacto** — pre-flight obligatorio |
| Browser smoke                  | GP-E2E-01..02 Playwright                                                            | **Intacto** — skip default           |
| HTTP integrado                 | **Nuevo** GP-V159-\*                                                                | Complementa, no reemplaza            |

## 6. OUT / parked

Playwright full stack obligatorio · LIVE · scheduler · bump package · `PAPER_D_EXECUTE` default on · Alembic · encolar STRUCTURAL_STOP a apertura · UX Mercado (V1.60) · re-certificar GOLDEN-DAY-ADV vía HTTP · CI Release-tag job nuevo · Confirm UNKNOWN día PAPER · thaw Accept.

## 7. Pre-flight (post-implementación)

Bloque V1.58 intacto + suite V1.59:

```bash
python -m pytest packages/py/application/tests/test_paper_desk_golden_day_adversarial.py packages/py/application/tests/test_paper_desk_golden_day.py packages/py/application/tests/test_paper_desk_golden_session_adverse.py packages/py/application/tests/test_inv_operational_truth.py -q
python -m pytest apps/api-python/tests/integration/test_v159_e2e_paper_desk.py apps/api-python/tests/integration/test_v159_e2e_operational_wire.py -m integration -q
python -m ruff check apps/api-python/tests/integration/test_v159_e2e_paper_desk.py apps/api-python/tests/integration/test_v159_e2e_operational_wire.py packages/py/application/src/bolsa_application --config pyproject.toml
```

Playwright (opt-in, sin regresión):

```bash
E2E_RUN=1 pnpm --filter @bolsa/web e2e
```
