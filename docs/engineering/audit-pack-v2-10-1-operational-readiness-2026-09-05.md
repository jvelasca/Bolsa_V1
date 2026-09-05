# Audit pack — V2.10.1 operational readiness (post PRODUCT FREEZE)

> **AsOf:** 2026-09-05 · **Tip:** [`v2.10.1-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.10.1-beta) → [`a060af37`](https://github.com/jvelasca/Bolsa_V1/commit/a060af37) · package `1.39.1-beta`.  
> **Padre:** [audit pack cabina V2.10](./audit-pack-v2-10-final-certification-2026-09-05.md) · [arranque post-tip](./arranque-agente-post-tip-v2-10-1-2026-09-05.md) · [relevo tag](./traspaso-relevo-tag-v2-10-1-beta-2026-09-05.md).  
> **Para:** auditoría **operacional** (uso real · carga · resiliencia · observabilidad · seguridad ops) · **no** certificación de paneles · **no** V2.11 · **PRODUCT FREEZE**.

---

## 0. Alcance y honestidad

Este pack **no** reabre cabina ni motor. La cabina V2.10 ya es CERTIFICABLE ([CI tip 33983574346](https://github.com/jvelasca/Bolsa_V1/actions/runs/33983574346) `success`).

Aquí se mide si el sistema **aguanta uso real** como BETA local / PAPER preparado, sin afirmar producción.

| Afirmar                                                                               | No afirmar                                        |
| ------------------------------------------------------------------------------------- | ------------------------------------------------- |
| Checklist de uso real con evidencias locales                                          | Que CI GREEN = carga / chaos / pixel Linux        |
| Gates LIVE bloqueado · `PAPER_D_EXECUTE` default off                                  | Que DEMO execute está “siempre listo” sin runbook |
| Observabilidad existente (Consola · ops-self-eval · excepciones)                      | Observabilidad completa tipo SRE                  |
| Resiliencia cubierta por suites ya stampadas (lifecycle / failure injection / golden) | Nueva batería de stress sin diseño                |

Freeze: NO LIVE · `PAPER_D_EXECUTE` off · no `TRANSITIONS` · Confirm = firma · Arm ≠ Execute · Ranking ≠ BUY · **NO MÁS PANELES**.

---

## 1. Inventario (ya existe — no inventar)

### 1.1 Uso real de cabina

| Pieza                          | Path                                                                                                          | Uso en auditoría                               |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Seed birth + Journal MFE·MAE   | [runbook V2.10 seed](./runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md) · `scripts/ops_seed_cabin_smoke.mjs` | Sembrar Position protegida + ficha Journal     |
| Cert visual/DOM cabina         | `apps/web/e2e/gp-e2e-v28-*` · `gp-e2e-v29-*`                                                                  | Regresión mock; **no** sustituye sesión humana |
| Hoy / Mercado / AUTO / Confirm | CURRENT_SYSTEM · ADR-040/042 · audit pack V2.10                                                               | Contrato semántico                             |
| OE-1 autoeval                  | [ops-autoeval checklist](./ops-autoeval-checklist-2026-08-26.md) · `scripts/ops_operativa_self_eval.mjs`      | Measure ≠ Accept                               |

### 1.2 Carga / resiliencia (evidencia histórica, no re-ejecutar motor)

| Pieza                               | Path                                                          | Límite                                            |
| ----------------------------------- | ------------------------------------------------------------- | ------------------------------------------------- |
| Failure injection V1.93             | tip `v1.93-beta` · lifecycle-pg                               | Crash/idempotencia worker — **no** load test HTTP |
| Operational atomicity / worker FIFO | V1.91–V1.92                                                   | Outbox — **no** multi-usuario concurrente UI      |
| Chaos ledger / crash-consistency    | `packages/py/infrastructure/tests/chaos/` · specs V1.75/V1.77 | Money-path / mock — **no** soak cabina UI         |
| Verify invariants                   | `scripts/verify/verify_*.py`                                  | Ledger/isolation — adyacente, no sustituto UI     |
| Dev stack bajo sync                 | [relevo F37](./traspaso-relevo-f37-dev-stack-2026-09-01.md)   | Vite/API bajo sync — deuda ops local              |
| E2E integrado opt-in                | V1.59 / V1.64                                                 | No es default Release-tag                         |

### 1.3 Observabilidad / seguridad ops

| Pieza                           | Path                                                                                                                                 | Límite                                                     |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------- |
| Consola `/operational-console`  | ADR-040 · GP-E2E-02 · [plan](./plan-operational-console-2026-08-26.md)                                                               | Diagnóstico; **no** L1                                     |
| `OperationalIncident` DEX-3     | ADR-035                                                                                                                              | Drift → review → resolve · sin auto-heal                   |
| `GET /api/risk/ops-self-eval`   | OE-1                                                                                                                                 | Scorecard SEMI/AUTO                                        |
| Health / doctor                 | `scripts/health-check.mjs` · `scripts/dev-doctor.mjs`                                                                                | Smoke local · **≠** SLO                                    |
| Ops security checklist          | [ops-r1](./ops-r1-seguridad-operaciones-2026-08-19.md)                                                                               | Manual · histórico                                         |
| `TRUSTED_PROXIES` prod          | [runbook](./ops-trusted-proxies-prod-runbook-2026-08-24.md) · [checklist](./traspaso-relevo-trusted-proxies-checklist-2026-09-01.md) | **BLOCKED_ON_OWNER** (IPs)                                 |
| Release-tag security (gitleaks) | workflow Release tag CI                                                                                                              | Secrets scan · **≠** threat model completo                 |
| Auth JWT + roles                | CURRENT_SYSTEM Auth · ADR-027                                                                                                        | `require_role` disponible; la mayoría de rutas solo sesión |

---

## 2. Checklist auditoría operacional (humano + smoke)

Marcar PASS / PARTIAL / FAIL / N/A con URL o log. **No** inventar PASS.

### A — Uso real cabina (sesión guiada)

1. Stack local up · cuenta DEMO limpia.
2. Seed birth estructural ([runbook](./runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md)) → Mercado: Planificado / MANTENER / stop ≠ −5 %.
3. Hoy: cubos · deny/stale visibles tras expand `no_operar` si aplica.
4. AUTO Desk: MANUAL / SEMI / AUTO DESARMADO / AUTO ARMADO · `executeEligible` coherente con env off.
5. Confirm drawer: frase · firma · Cancelar (teclado OK en mock v28; aquí sesión real).
6. Journal: `runtime.mfeMae` finito en ficha tras seed Journal.
7. Consola: excepciones-only · sin inventar inbox Mesa.

### B — Carga / resiliencia (observar, no romper freeze)

1. Un ciclo sync instrumento bajo stack `run-dev` — anotar caídas (F37).
2. `ops-self-eval` tras sesión A — recon ≠ drift en cuenta limpia.
3. Kill switch ON → AUTO DENY (si se arma UI; **sin** encender `PAPER_D_EXECUTE`).
4. Documentar PARTIAL si no hay harness de load formal (esperado).

### C — Observabilidad / seguridad ops

1. Consola muestra incidentes / excepciones sin CTA de trading L1.
2. Logs API no exponen secretos en smoke local.
3. Cookie HttpOnly / logout / 401 en ruta protegida (smoke manual).
4. Confirmar `.env` local no commiteado · `PAPER_D_EXECUTE` unset.
5. Anotar `TRUSTED_PROXIES` prod como **BLOCKED_ON_OWNER** (no PASS).

---

## 3. Huecos honestos (P3 operacionales — no P0 producto)

| ID        | Hueco                                         | Política bajo freeze                                      |
| --------- | --------------------------------------------- | --------------------------------------------------------- |
| **OR-01** | No hay load test formal HTTP/UI / soak cabina | Diferir · medir solo sesión A/B · chaos ledger ≠ cabina   |
| **OR-02** | Chaos multi-proceso fuera de lifecycle-pg     | Diferir · no reabrir worker                               |
| **OR-03** | Observabilidad ≠ métricas SRE / alertas       | Consola + OE-1 suficientes para BETA                      |
| **OR-04** | Threat model / pen-test no stampado           | Security CI = gitleaks · no afirmar más                   |
| **OR-05** | Pixel Linux / WCAG full                       | Ver [triage P2](./triage-p2-v2-10-deferred-2026-09-05.md) |
| **OR-06** | `TRUSTED_PROXIES` prod sin IPs owner          | **BLOCKED_ON_OWNER** · no inventar PASS seguridad edge    |

---

## 4. Qué NO reabrir

FSM · `TRANSITIONS` · outbox · ledger · Alembic `019` · paneles · V2.11 · tip/bump · `PAPER_D_EXECUTE` default on · LIVE · Accept estricto.

Siguiente corte relacionado (docs): [preparación PAPER](./traspaso-relevo-paper-prep-post-v2101-2026-09-05.md).

---

## 5. Lectura para el auditor

1. Tip [`v2.10.1-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.10.1-beta) · pack cabina [V2.10 final](./audit-pack-v2-10-final-certification-2026-09-05.md).
2. Este pack = **readiness operacional**, no re-score de cabina.
3. Arranque: [arranque operacional](./arranque-agente-post-freeze-operational-2026-09-05.md).
4. Evidencias = checklist §2 con stamps locales; sin stamp → PARTIAL/N/A.
