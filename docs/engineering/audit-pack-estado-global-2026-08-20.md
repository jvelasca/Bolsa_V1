# Paquete de auditoría — ESTADO GLOBAL consolidado R-1→R-8 (2026-08-20)

> **Propósito:** documento **único** para revisar/consultar el estado global del proyecto tras completar la ola de auditoría de dinero real R-7 **y la ola de prevención de riesgo/fidelidad R-8**. Consolida log de fases, decisiones, deuda cerrada/pendiente, freeze y checklist operativo. Pensado para **pasar a un auditor externo o para lectura rápida de un nuevo chat/agente** sin _documentation archaeology_.
> **AsOf:** 2026-08-20 · rama `main` · `local main = origin/main = e7b4655` (CONTRACT-STALE: regen `aecbb28` + docs `e7b4655`) · árbol limpio · tag **`v1.1.0`**.
> **Repo:** `https://github.com/jvelasca/Bolsa_V1` (público).
> **Fuentes de verdad:** [`PROJECT_STATE.md`](./PROJECT_STATE.md) (estado vivo) · [`backlog-trabajo-2026-08-20.md`](./backlog-trabajo-2026-08-20.md) (ancla de trabajo; LEER PRIMERO) · [`engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md) (índice).
> **Freeze vigente:** sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA · auth JWT diferida (D4).

---

## 0. Resumen ejecutivo

| Pieza                                                                      | Estado                                                                      |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **Rama**                                                                   | `main` (`local main = origin/main = e7b4655`), árbol limpio · tag `v1.1.0`  |
| **R-1..R-5** (reconciliación wire + CI/higiene + refactor)                 | ✅ COMPLETADOS en `main`                                                    |
| **R-6** (re-auditoría superficie web+api+shared, 4 Altos + FE/shared)      | ✅ COMPLETADO en `main`                                                     |
| **R-7** (auditoría dinero real `packages/py/{application,infrastructure}`) | ✅ **COMPLETADO — deuda money/verdad completa** (Alto×3 + Medio×7 + Baja×5) |
| **R-8** (prevención de riesgo + fidelidad)                                 | ✅ **COMPLETADO en `main`** (R-8A/B/C/D + R-8B.3)                           |
| **CONTRACT-STALE** (drift contrato D5)                                     | ✅ **RESUELTO** (`aecbb28`) — `contract:check` VERDE                        |
| **Deuda de dinero/verdad restante**                                        | Ninguna. Solo **M-4/T-M4** (job dedicado) DIFERIDO por freeze               |
| **Batería** (al cierre CONTRACT-STALE)                                     | `contract:check` ok · web typecheck 0 · lint 0 · test 714/714               |
| **CI**                                                                     | Igual de sano (R-7/R-8 pusheadas directas a `main`; sin regresión en tests) |

**Mensaje clave para auditor:** la deuda de dinero real heredada de R-6 (lógica en `packages/py/{application,infrastructure}`) está **completamente cerrada** tras R-7, y la ola R-8 aporta **prevención de riesgo** (bootstrap advisory-lock + idempotencia concurrente, rate-limit auth, sesión HttpOnly, invariante `balance_after` como **postcondición de app en test-suite**, no constraint DB) y **fidelidad de contrato** (R-8B.3 wire + **CONTRACT-STALE D5 verde**). Los invariantes F1/FFIN (with_for_update, deduct_cash en lock, idempotencia, fail-closed F-FIN-1, atomicidad) quedan verificados INTACTOS.

---

## 1. Log de fases completadas (R-1→R-7)

### R-1..R-5 — Reconciliación de wire + CI/higiene + refactor (2026-08-12/08-19)

- R-2/R-3/R-4: reconciliación de ~87 DTOs TS↔Py con **cero `regen_full`**; `contract:check` VERDE. Fixes de `response_model` shape-abierto, call-sites R-3.
- R-5: bump de actions de CI (Node 20 deprecado) + higiene `.gitignore`/logs; `.prettierrc` NO tocado (obsoleto).
- F-IND-1/F-IND-2 (causalidad indicadores), F-FIN-1/F-FIN-2 (fiscal), F-SEG-1/2/3 (seguridad), F-HLTH-1, F-DEBT-1/2, F-WORKER-1: **TODO MERGED/cerrado** (ver PROJECT_STATE §3).

### R-6 — Re-auditoría de superficie completa (2026-08-20)

- Barrido transversal READ-ONLY (web + api-python + shared/domain/analytics). Corregidos alto: **F-1** (`parseLocalizedNumber`), **F-4** (lógica fiscal muerta), **F-2** (`TAX_PRESETS.US.dividendWithholdingPct` 15→30). Commits `a64f4d0`/`da8aee5`/`8731827` + docs.

### R-7 — Lógica de dinero real en `packages/py/{application,infrastructure}` (2026-08-20) — DEUDA COMPLETA

Auditoría read-only (3 subagentes + verificación coordinador) → inventario **Alto×3/Medio×7/Bajo×5**. Cerradas por fases (todas en `main`):

| Fase     | Código      | Commit    | Resumen                                                                                               |
| -------- | ----------- | --------- | ----------------------------------------------------------------------------------------------------- |
| F1       | A-1 + A-3   | `c957df1` | Mutex custodia `claim_custody_charge` (doble cargo en GET concurrentes) + release claim AUTO          |
| F2       | A-2         | `8c081ea` | Idempotencia Deposit/Withdraw (`idempotency_key` + guard `find_cash_movement_by_reference`)           |
| F3       | L-M3/M-5    | `d7b8db8` | UNIQUE parcial `ledger_entries (account_id, reference_type, reference_id, type)` (no rompe trade+fee) |
| M-1      | T-M1        | `a78eb29` | `get_summary` fallback mark-to-cost para posiciones sin close D1 (Opción B)                           |
| M-2      | T-M2        | `c8e9ced` | Reconciliación cash↔ledger (`sum_cash_amounts` + tests-postcondición)                                 |
| M-3      | T-M3        | `6962fd7` | Puente de conciliación cost-basis con fee en cara unrealized del tax-report (opción iv)               |
| M-6      | T-M6        | `604bfef` | Margen real en `_account_summary_from_portfolio` (`Σmv/leverage`)                                     |
| M-4/T-M5 | mezcla fees | `6a1759c` | `total_fees_for_account` excluye custodia (**T-M4 job diferido por freeze**)                          |
| M-7      | L-M5        | `f598e2d` | Postcondición: UNIQUE de F3 impide re-cargo de custodia                                               |
| B-1      | T-M7        | `4f43aeb` | Max drawdown → **high-water-mark** (`peakEquity` + running-max)                                       |
| B-3      | L-M4        | `7cffaa7` | `transfer_cash` muerto sin ledger ELIMINADO (decisión usuario)                                        |
| B-4      | L-M6        | `3712e63` | Trade+fee idempotente en AUTO execute/confirm (opción B)                                              |
| B-5      | T-M9/T-M10  | `76abe0f` | Guard `quantity==0` en FIFO buy + observabilidad PnL CORE-R                                           |
| **B-2**  | T-M8        | `7b3dd91` | `total_unrealized_gain` fail-closed con posiciones sin precio (opción A)                              |

> Detalle completo de cada fase: [`traspaso-r7-dinero-application-infrastructure-2026-08-20.md`](./traspaso-r7-dinero-application-infrastructure-2026-08-20.md) §4a–§4n.

### R-8 — Prevención de riesgo + fidelidad de contrato (2026-08-20) — COMPLETA

Ola de hardening tras el cierre completo de R-7, motivada por la auditoría externa de la 3ª ronda. Cerradas por fases (todas PUSHEADAS a `main`):

| Fase               | Commit(s)                                         | Resumen                                                                                                                                                                               |
| ------------------ | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| R-8A               | `edf2d0c` (+docs `7f327ab`)                       | P0-A `database_bootstrap()` con `pg_advisory_lock` (serializa Alembic+migración entre workers) · P0-B idempotencia concurrente (catch `IntegrityError`+savepoint+re-SELECT)           |
| R-8B.1             | `ac147fe` (+higiene `a1360bb`)                    | Rate-limit `/api/auth/login` (20/60s) y `/api/auth/status` (60/60s) via `SENSITIVE_PREFIXES`                                                                                          |
| R-8B.2             | `abf3dc2`                                         | Sesión HttpOnly firmada stateless (cookie fuera de localStorage) + `POST /api/auth/logout` + `authenticated`                                                                          |
| R-8C               | `3ad48aa`                                         | Invariante `balance_after` por grupo atómico (postcondición app en test-suite, NO constraint DB) + deuda R-8C.2 (scheduler-vs-worker) documentada                                     |
| R-8D               | `dbd1ee5`                                         | Limpieza transversal baja (14 símbolos/aliases muertos) + `pending-delete/README` al estado real                                                                                      |
| R-8B.3             | `158b3db`,`756e3a1`,`ce1d5ca`,`e6dde15`,`fb95b27` | Fidelidad wire de DTOs en `packages/shared` (cash · FIE FUND · signal-alerts · dictamen · account-settings)                                                                           |
| **CONTRACT-STALE** | `aecbb28` (+docs `e7b4655`)                       | **Regen acotada** `openapi.json`+`schema.d.ts` (idempotencyKey Deposit/Withdraw · `authenticated` required `@default false` · `logout` response/descripción) → `contract:check` VERDE |

> Detalle de cada fase R-8: [`plan-r8-prevencion-riesgo-2026-08-20.md`](./plan-r8-prevencion-riesgo-2026-08-20.md) (plan + §6 historial). **Anti-alucinación:** el doc de relevo daba `authenticated`/`logout` como missing en `schema.d.ts`, pero ya estaban en el spec commiteado; el drift real era `idempotencyKey` + el desfase `schema.d.ts`↔su propio spec. La regen los resuelve igualmente (D5 verde).

---

## 2. Deuda cerrada / pendiente

**Cerrada (R-7):** Alto×3 (A-1/A-2/A-3) · Medio×7 (M-1/M-2/M-3/M-4·T-M5/M-5=M-6/M-7) · Baja×5 (B-1/B-3/B-4/B-5/B-2).

**Cerrada (R-8):** R-8A (P0 bootstrap advisory-lock + idempotencia concurr.), R-8B.1 (rate-limit auth), R-8B.2 (sesión HttpOnly + logout + authenticated), R-8C (invariante balance_after), R-8D (limpieza cruzada), R-8B.3 (fidelidad wire shared), **CONTRACT-STALE** (regen de contrato → `contract:check` VERDE).

**Único pendiente de dinero/verdad:** **M-4/T-M4** — mover el cargo de custodia del path de lectura (GET `GetTaxReport`/`GetAccountSummary`, herencia `daily_ops_report`) a un **job dedicado**. **DIFERIDO por freeze** (colinda con «sin features»). Requiere decisión de usuario cuando se levante el freeze.

**Deuda operativa/manual (no código, no bloquea):** ver §4.

---

## 3. Freeze y decisiones de alcance vigentes (NO reabrir sin pedir)

- **Freeze:** sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA · auth JWT diferida (D4).
- **No `regen_full`** sin decisión. **No `contract:gen`** salvo fase pactada («regen acotada» de CONTRACT-STALE ya ejecutada: no repetir).
- **M-3** = puente (storage/`avg_cost` sigue fee-excluido). **M-4/T-M4** diferida (job dedicado). **B-3** = `transfer_cash` eliminado (no reabrir). **B-1** = high-water-mark (no reabrir). **B-4** = trade+fee idempotente (opción B, no reabrir). **B-5** = guard FIFO + obs. PnL CORE-R (no reabrir). **B-2** = `total_unrealized_gain` fail-closed (opción A, no reabrir). **M-6/M-7** cerradas.
- **R-8**: R-8A (advisory-lock bootstrap) · R-8B.1/R-8B.2 (rate-limit auth + sesión HttpOnly) · R-8C (invariante balance_after) · R-8D (limpieza) · R-8B.3 (fidelidad wire shared) · **CONTRACT-STALE** (regen contrato) — **cerradas, no reabrir**.
- **R-8C.2** (deuda scheduler-vs-worker, no-ARQ) documentada SOLA — **NO tocar código worker salvo decisión explícita**.
- **Ítems `pending-delete` de riesgo alto** (`readLegacyPendingOrders`, `chartDataStrip`/`chartNewTabSeed`/`newChartConfigSource`, `readLegacyTimeframeFavorites`, re-export `presetRuleGroups`) — **NO tocar hasta `purge storage`**.

---

## 4. Checklist operativo manual (FUERA de repo — acciones de GitHub UI / usuario)

> Acumulado de R-1/F-WORKER-1. NO bloquean código; requieren acción manual.

- [ ] Activar **GitHub secret scanning** nativo en la UI.
- [ ] Definir **`TRUSTED_PROXIES` prod** con las IPs del proxy de borde (bloqueado por valores reales del usuario).
- [ ] Corregir registro en BD **`BP/.L` → `BP.L`** (dato corrupto, F-WORKER-1) si se quiere dato real.
- [ ] Limpiar **`logs/dev`** locales (~150 MB de `dev-*.log`; gitignore ya cubre `logs/**`).
- [ ] Opcional: purga de **valores dev** en historial git público (filter-repo/BFG — decisión explícita).

---

## 5. Índice de fuentes de verdad / docs clave

| Doc                                                                                                                            | Rol                                                              |
| ------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| [`PROJECT_STATE.md`](./PROJECT_STATE.md)                                                                                       | Estado vivo (entrada/salida de cada chat/agente)                 |
| [`backlog-trabajo-2026-08-20.md`](./backlog-trabajo-2026-08-20.md)                                                             | Ancla anti-saturación / trabajo por delante (LEER PRIMERO)       |
| [`traspaso-r7-dinero-application-infrastructure-2026-08-20.md`](./traspaso-r7-dinero-application-infrastructure-2026-08-20.md) | Traspaso completo + inventario R-7 (detalle §4a–§4n + §8 relevo) |
| [`plan-r8-prevencion-riesgo-2026-08-20.md`](./plan-r8-prevencion-riesgo-2026-08-20.md)                                         | Plan + historial de cierres R-8 (incl. CONTRACT-STALE)           |
| [`traspaso-relevo-cierre-r8-auditoria-versiones-2026-08-20.md`](./traspaso-relevo-cierre-r8-auditoria-versiones-2026-08-20.md) | Texto de paso del relevo R-8/R-8B.3 (CONTRACT-STALE + release)   |
| [`engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md)                                                         | Índice único de la documentación de ingeniería                   |
| [`audit-consolidado-internas-externas-2026-08-11.md`](./audit-consolidado-internas-externas-2026-08-11.md)                     | Auditorías externas previas + plan F1–F5 + decisiones D0–D5      |

---

## 6. Cómo auditar / batería de referencia

1. Leer este doc §0–§3 y el backlog §0 (read-first).
2. Confirmar estado: `git status` (limpio) · `git rev-parse HEAD` == `git rev-parse origin/main` == `e7b4655` · tag `v1.1.0`.
3. Batería por fase (equivalente al gate CI):
   - **D5 (contrato):** `$env:PYTHONIOENCODING='utf-8'; pnpm --filter @bolsa/web contract:check` → **OK** (workaround de encoding en Windows).
   - **Frontend:** `pnpm --filter @bolsa/web typecheck|lint|test` (typecheck 0 · lint 0 · test 714/714) · `pnpm --filter @bolsa/shared typecheck|lint|test` (17).
   - **Backend (py):** `ruff check packages/py apps/api-python --config pyproject.toml` → 0 · `mypy` gate CI de ficheros `*/src` · pytest de la zona (domain / application / infra **Postgres real** — esta última requiere BD).
4. Nota batería: application es **mypy-blind en CI** (mypy solo en `*/src`); `accounts.py` conserva 6 errores `no-untyped-def` pre-existentes sin nuevos.
5. Para verificar un fix concreto de dinero/verdad: consultar la fase en el traspaso R-7 (evidencia + battery) · para R-8: el plan R-8 §6.
6. **Release elevada:** tag anotado `v1.1.0` en `e7b4655` (precedente R-8; `v1.0.0` fue tag anotado en `879ea23`; no se bumpean subversiones de web/shared — solo tag raíz).
