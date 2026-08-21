# ESTADO VERIFICADO — Auditoría externa 2026-08-21 vs `main` (GitHub) — firma de anti-alucinación

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`).
> **Propósito:** documentar la **firma de estado verificada** que resuelve la aparente contradicción entre la **auditoría externa recibida el 2026-08-21** (que evalúa el estado `75e8c23`) y el **estado REAL de `main` en GitHub**. Cualquier agente/chat que retome este tema **LEE ESTE DOC OBLIGATORIAMENTE antes de abrir ninguna fase**, para no "corregir" cosas que ya están corregidas (premisa E3: documento manda · anti-alucinación).
> **Fuente de coordinación:** GitHub `jvelasca/Bolsa_V1` `origin/main`. SHA vivo = `git fetch && git rev-parse origin/main`. **No** usar SHAs de este doc como HEAD sin verificar.
> **Estado al abrir R-12 (verificado):** GitHub `main` = local = **`f7a86ccce6549e704e705e272db68a0fa863c65f`**. Tag `v1.3.0` → **`b778292`**. La auditoría externa de la mañana evaluó `75e8c23` (14 commits detrás de `49ecbcd`); la re-auditoría de la tarde evaluó ~`49ecbcd` y **no incluye** Relevo UNO (`f7a4ab0`) ni DOS (`f7a86cc`).
> **AsOf:** 2026-08-21 (actualizado R-12).

---

## 0. Firma de estado (convertida en hecho, no asunción)

| Comprobación                        | Comando / medio                                | Resultado verificado                                                      |
| ----------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------- |
| HEAD local                          | `git rev-parse HEAD`                           | `f7a86ccce6549e704e705e272db68a0fa863c65f`                                |
| `origin/main` (ref local)           | `git rev-parse origin/main`                    | `f7a86cc...` (idéntico a HEAD al abrir R-12)                              |
| Tag `v1.3.0`                        | `git log -1 --oneline v1.3.0`                  | **`b778292`** (no `deafa27`)                                              |
| Commits sin empujar                 | `git log origin/main..HEAD`                    | **vacío** (0)                                                             |
| Actualizaciones del remoto          | `git fetch --dry-run`                          | sin cambios entrantes                                                     |
| Remotes                             | `git remote -v`                                | `https://github.com/jvelasca/Bolsa_V1.git` (fetch/push)                   |
| **ESTADO REAL del servidor GitHub** | `gh api repos/jvelasca/Bolsa_V1/branches/main` | al abrir R-12 = `f7a86cc...` (**no** `49ecbcd`; verificar siempre el tip) |
| Fecha del commit HEAD               | `gh api .../commits/49ecbcd...`                | `2026-08-21T13:40:41Z`                                                    |
| Relación con el punto auditado      | `gh api .../compare/75e8c23...49ecbcd`         | `ahead_by: 14 · behind_by: 0 · status: "ahead"`                           |

**Conclusión de la firma:** GitHub es la fuente de coordinación. La aparente contradicción de la mañana **NO** era desincronización: la auditoría evaluó `75e8c23`, 14 commits detrás de `49ecbcd`. Al **abrir R-12** el tip ya era **`f7a86cc`** (Relevo UNO+DOS encima de `49ecbcd`). El tip actual se verifica siempre con `git rev-parse origin/main`.

---

## 1. Los 14 commits que la auditoría externa NO llegó a ver (delta `75e8c23 → 49ecbcd`)

Todos estos commits ya están **pusheados a `main`** y cierran exactamente los P1/P2 que la auditoría externa del 2026-08-21 pide en su "hallazgos nuevos" y en su batería recomendada:

| Commit    | Contenido (cierre de la auditoría)                                                                                                                                                                    |
| --------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `c3327c1` | **R-11 C1** — custodia **multi-periodo**: PK `id` + `UNIQUE(account_id, period)`, migración `006`, liquida el PENDING más antiguo primero (resuelve el P1 "obligaciones históricas" / multi-periodo). |
| `1ae93f9` | docs: plan R-11 hardening tras auditoría v1.2.1 (apertura).                                                                                                                                           |
| `17a1107` | **R-11 C2** — `idempotency_key` end-to-end: DTO 16–128 + `strip_whitespace`, repo obligatoria no vacía (resuelve el P2 "idempotency key vacía").                                                      |
| `cda26e9` | **R-11 C3** — precisión Decimal end-to-end en `ExecuteTrade` (float solo en el borde repo/ledger) (resuelve el P2 "Decimal → float → Decimal").                                                       |
| `157bb45` | **R-11 C4** — `contract:check` **EXIT 0** (regen acotada de `openapi.json`; Opción A).                                                                                                                |
| `6762614` | **R-11 C5** — mypy **== 0** en gate CI (incluso `packages/py/application/src`); 105 errores limpios en 33 ficheros (resuelve el P2 "7 errores mypy de accounts.py").                                  |
| `db95709` | **R-11 C6 + D2** — política `custody_charge_source = DEFAULT_PORTFOLIO` documentada en ADR 026 (resuelve el P2 "custodia multi-portfolio" a nivel de política explícita).                             |
| `870fb21` | **R-11 D1** — quitados métodos de custodia muertos (`get_by_account` / `get_by_account_period`), criterio E8.                                                                                         |
| `ab4db29` | docs: cierre R-11 + traspaso de relevo a siguiente fase.                                                                                                                                              |
| `deafa27` | **Release v1.3.0** — fix `test_execute_trade_con_fees_reconcilia` (pasa `idempotency_key`) → resuelve el **P1 "test roto"**.                                                                          |
| `b778292` | docs(release): cierre R-11 como v1.3.0 (CHANGELOG `[1.3.0]` + estado + deuda §3 cerrada).                                                                                                             |
| `b7af24b` | docs(engineering): plan draft Unificación Research→Radar (aparcado, read-only).                                                                                                                       |
| `5276d47` | docs(web): trazabilidad B0 del puente en consumidores instrumentales (Unificación Res→Radar F1).                                                                                                      |
| `49ecbcd` | docs(engineering): Unificación Research→Radar Fase 3 (pista documental DRAFT/APARCADO).                                                                                                               |

> **Nota de release:** tag **`v1.3.0`** anotado sobre `deafa27` (cierre deuda §3: test roto + fixture dev `acc_broken_72ab7c2aa881` eliminado → `verify_ledger_balance_chain.py` **EXIT 0 global**). Último tag previo: `v1.2.1` sobre `2093296`.

---

## 2. Mapeo: lo que la auditoría pide vs. lo que YA está cerrado en `main` (49ecbcd)

| Hallazgo / batería de la auditoría                                                                          | Estado REAL en `main` (49ecbcd)                          | Evidencia                                                                                                           |
| ----------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| 🔴 P1 custodia multi-periodo (`UNIQUE(account_id, period)`)                                                 | ✅ **CERRADO**                                           | `c3327c1` · migración `006` · `tables.py:1419` · `custody_obligation_repository.py:43-54` (order by `period.asc()`) |
| 🔴 P1 "test roto" `test_execute_trade_con_fees_reconcilia`                                                  | ✅ **CERRADO**                                           | `deafa27` · test corregido con `idempotency_key` estable                                                            |
| 🔴 P1 `verify_ledger_balance_chain.py` EXIT 1                                                               | ✅ **CERRADO** (EXIT 0 global)                           | `b778292` / `deafa27` · cuenta dev `acc_broken_72ab7c2aa881` eliminada por path canónico                            |
| 🔴 P1 `contract:check` rojo                                                                                 | ✅ **EXIT 0**                                            | `157bb45` · C4 Opción A; **R12-409 B1 HECHO en WT** (409 declarado en OpenAPI; SHA pending)                         |
| 🟠 P2 7 errores mypy                                                                                        | ✅ **CERRADO**                                           | `6762614` · mypy 0 gate, incluso `application/src`                                                                  |
| 🟠 P2 `idempotency_key` vacía                                                                               | ✅ **CERRADO**                                           | `17a1107` · DTO 16–128 + strip · repo obligatoria no vacía                                                          |
| 🟠 P2 Decimal→float→Decimal                                                                                 | ✅ **CERRADO en ExecuteTrade**                           | `cda26e9` · Decimal end-to-end; float solo en borde                                                                 |
| 🟠 P2 custodia multi-portfolio                                                                              | ✅ **Política documentada** (DEFAULT_PORTFOLIO)          | `db95709` · ADR 026                                                                                                 |
| 🟠 P2 invariante B `balance_after` chain                                                                    | ✅ **Verificada**                                        | `verify_ledger_balance_chain.py:72-79`                                                                              |
| 🟠 P2 Redis caído + 2 custody workers                                                                       | ⚠️ **GAP REAL (ver §3.2)**                               | No hay test que combine "Redis no disponible" + 2 workers de custodia                                               |
| 🟠 P2 2 custody jobs simultáneos (asyncio.gather)                                                           | ⚠️ **GAP REAL (ver §3.2)**                               | Solo hay custodia+trade racing y tests con fakes                                                                    |
| 🟠 P2 test Postgres real transición 2026→2027                                                               | ⚠️ **GAP REAL (ver §3.2)**                               | `test_custody_obligation_multi_period.py` cubre con **fakes**, no con PG real + 2 workers                           |
| 🟠 Invariante A (Σ ledger == cash) en `verify_ledger_balance_chain.py`                                      | ⚠️ **GAP REAL (ver §3.2)**                               | El script verify solo valida la cadena `balance_after` (B); Σ==cash solo vive en pytest (`test_m2`)                 |
| 🔴/🟠 `pending-delete` riesgo alto + "authority" scheduler-vs-worker + auth global + legacy portfolio model | ⏳ **DEUDA INVENTARIADA, NO CERRADA (V2, por decisión)** | `pending-delete/README.md` · `PROJECT_STATE.md` §3 · freeze                                                         |

---

## 3. Los gaps REALES que SÍ quedan abiertos en `main` (49ecbcd) — candidatos a plan

Los siguientes NO fueron cerrados por R-11/v1.3.0 y son los que un plan de mejora debería atacar primero (por riesgo dinero/verdad, según la matriz de la propia auditoría).

### 3.1 Contrato residual — `409 IDEMPOTENCY_KEY_REUSED` → **Opción B1 HECHA en WT** (P1 contractual, bajo)

> **Estado (2026-08-22):** propietario abrió gate **R12-409** y eligió **Opción B1**. Implementado en working tree (SHA pending commit): `responses` 409 con body `{detail: str}` en `deposit_cash` / `withdraw_cash` / `execute_trade`; shared `apps/api-python/src/bolsa_api/api/v1/idempotency_responses.py`; regen acotada `openapi.json` + `schema.d.ts`; `contract:check` EXIT 0. Runtime handler en `main.py` **sin cambios**.

- **Runtime (sin cambio):** handler global `apps/api-python/src/bolsa_api/main.py` → `JSONResponse(status_code=409, content={"detail": str(exc)})` para `IdempotencyKeyReused` + `IdempotencyKeyExists`.
- **OpenAPI (B1):** las tres write-paths declaran `409` con schema `{detail: string}` required. Paths: `/api/accounts/{account_id}/deposits`, `/api/accounts/{account_id}/withdrawals`, `/api/portfolio/trade`.
- **Gate de verificación:** `contract:gen` + `contract:check` EXIT 0 (no hay test barato aparte; el check es la batería).

### 3.2 Gaps de VERIFICACIÓN (lo que recomienda la auditoría como siguiente fase: chaos / invariantes bajo estrés) — ESTADO TRAS F1/F2 (2026-08-21)

1. **Invariante A (Σ ledger.amount == cash) en `verify_ledger_balance_chain.py`** → ✅ **CERRADA (Fase 1, 2026-08-21)** — `verify_ledger_balance_chain.py` ahora valida **A (Σ ledger == Σ portfolios.cash del account)** + **B (cadena balance_after)**, tolerancia `1e-6`, sin backfill. Rollback A-rota validado. **EXIT 0 global** tras limpiar cuentas `simulated` huérfanas de tests (m7-uniq/m2-insf/R8C) por path canónico `close_account`→`delete_simulated_account` (mismo criterio que `acc_broken` en v1.3.0). ruff 0 · mypy 0 · no-regresión custodia OK. **Interacción de datos (R000) → ✅ RESUELTA (Relevo DOS, 2026-08-21):** `test_m7_custody_single_charge_f3_guard.py` y `test_m2_ledger_cash_reconciliation.py` ahora **limpian sus cuentas simuladas** (`_cleanup_account`, `close_account`+`delete_simulated_account`+commit) y **m2 además sus instrumentos** (`_cleanup_instrument`) → **delta 0** de residuos nuevos y **EXIT 0 estable** del verify contra dev.
2. **Test de 2 `RunCustodyJob`/`ApplyCustodyFees` concurrentes** → ✅ **CERRADA (Fase 2, 2026-08-21)** — `test_custody_concurrency_chaos.py` (infra, PG real): `test_two_custody_workers_single_charge_no_double_fee` + `test_two_custody_workers_two_accounts_single_charge_each` (2 workers → 1 cargo/1 obligation APPLIED, cash − fee, nunca −2·fee, Σ==cash, cadena). Nota: se cubre con `ApplyCustodyFees` concurrente (no `RunCustodyJob`) porque el job barre todas las cuentas activas y una residual sin cartera falla `_load_scope` (documentado).
3. **Test "Redis caído + 2 custody workers"** → ✅ **CERRADA (Fase 2)** — `test_redis_down_two_workers_memory_fallback_single_charge` (no hay Redis en dev → fallback memoria natural; exactly one charge).
4. **Test Postgres real de transición de periodo con obligación PENDING antigua** → ✅ **CERRADA (Fase 2)** — `test_old_pending_preserved_and_oldest_liquidated_first_insufficient` + `test_oldest_pending_liquidated_before_current_period_full` (PG real; se siembra PENDING con `upsert(period=<año-anterior>)`; ninguna obligación desaparece; orden `[prior, current]`).
5. **Crash / kill entre cash y ledger** (atomicidad real) → ✅ **CERRADA (Fase 4, Relevo DOS, 2026-08-21)** — `tests/chaos/test_crash_consistency.py` (3 tests, DB aislada `bolsa_v1_chaos`): kill tras deducir cash sin ledger → ROLLBACK (cash=inicial, sin fila) · kill tras ledger sin commit → ROLLBACK total · control con commit → cash descontado + fila persistida. ruff 0 · mypy 0 · 3 passed.
6. **Concurrencia masiva / carga (chaos)** → ✅ **CERRADA (Fase 5, Relevo DOS, 2026-08-21)** — `tests/chaos/test_load_concurrency_flow.py` (5 tests): 500 depósitos · 500 retiros (no-negatividad) · 500 BUY+500 SELL · BUY+SELL · custodia+BUY; `cash ≥ 0`, inv. A (Σ==cash), inv. B (variante robusta para trades). **🔴 deja a la vista un hallazgo de diseño**: bajo `ExecuteTrade` concurrente la invariante B estricta no es postcondición (cash_before pre-lock) → deuda V2.

### 3.3 Deuda inventariada de alcance amplio (V2, por decisión — NO auto-abrir)

- `pending-delete` riesgo alto (migradores legacy con call-sites runtime reales pero **sin writers** en el árbol actual; solo re-export `presetRuleGroups` con 0 call-sites de la vía riesgosa). Requiere purga planificada (inventario → writers → readers → storage → test de ausencia).
- **R-8C.2** scheduler-vs-worker (coexistencia scheduler no‑ARQ) — NO tocar código salvo decisión.
- **Auth global** single-user (APP_PASSWORD opcional; JWT diferida) — V2.
- **Legacy portfolio model** / `legacy_portfolio_id` — V2, requiere ADR + fase.
- **Unificación Research→Radar** — APARCADO/DRAFT (solo pista documental F1–F3 cerradas; código pendiente de decisión).

---

## 4. PREMISAS ESENCIALES ACTUALES (confirmadas y vigentes)

> Estas refuerzan y NO sustituyen las premisas E1–E9 de `docs/PROJECT_PREMISES.md`. Se anotan aquí por ser las que rigen específicamente este plan de refactor/corrección y el protocolo anti-saturación ya pactado.

1. **Nada se implementa sin plan aprobado (E1).** El plan de fases se documenta en `/docs` y cada fase se abre solo tras aprobación explícita del propietario. **No lanzar código "en caliente".**
2. **Una fase = un subagente acotado + verificación del coordinador + batería real + aprobación por commit + push a `main` (rama protegida) (E2/E4/E6).** Máx. ~3 subagentes en paralelo con alcances disjuntos.
3. **Read-first anti-alucinación (E3).** Antes de abrir cualquier fase: leer `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1, `PROJECT_STATE.md`, las premisas E1–E9 y **este doc §0 (firma de estado)**. Si el repo no coincide con la documentación → PARAR y re-leer.
4. **La firma de estado de GitHub es la verdad para las auditorías externas.** Las próximas auditorías deben usarse contra **`origin/main`** (verificar `git rev-parse origin/main`), no contra `f7a86cc`/`49ecbcd`/`75e8c23` incrustados en un traspaso. Todo relevo incluye firma (HEAD GitHub/rama/árbol/tags).
5. **Documentación y DOCSTRINGS obligatorios (E5).** Todo cambio relevante: capa `docs/` (producto/decisión/ADR) + docstrings forward-only según [code-documentation-standard](./code-documentation-standard-2026-08-03.md).
6. **TESTS/SCRIPTS en cada fase (E6).** Especialmente para idempotencia, concurrencia/locking, rollback, invariantes de ledger, migración, multi-worker, aislamiento entre cuentas.
7. **Freeze vigente.** Sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA · auth JWT diferida · `contract:gen`/`regen_full` solo en fase pactada · `pending-delete` riesgo alto y R-8C.2 NO tocar salvo decisión.
8. **Verificación bajo estrés (chaos) es la siguiente frontera recomendada** (auditoría + premisa E7), porque el núcleo financiero ya está maduro y el gap real son las invariantes bajo estrés/crash, no la estructura.

---

## 5. Batería mínima obligatoria (re-verificada por el coordinador en cada fase)

- **Backend (py):** `ruff check packages/py apps/api-python --config pyproject.toml` → 0 · mypy de los ficheros en gate CI (incluye `packages/py/application/src`) · pytest de la zona.
- **Git:** `git status` acotado a los ficheros declarados por la fase.
- **Frontend/shared/contract:** `pnpm --filter @bolsa/web typecheck|lint|test` · `pnpm --filter @bolsa/shared typecheck|lint|test|build` · `contract:check` **si cambia OpenAPI** (precedido de `$env:PYTHONIOENCODING='utf-8'`). **NO ejecutar `contract:gen`** salvo fase pactada.
- **Verificación invariante ledger:** `scripts/verify/verify_ledger_balance_chain.py` → **EXIT 0 global** (+ `verify_account_isolation.py`).
- **Docstring coverage** cuando se toque una zona: `python scripts/research/docstring_coverage_report.py`.

---

## 6. Enlaces (fuentes de verdad — no inventar estado)

- Backlog (LEER PRIMERO): `docs/engineering/backlog-trabajo-2026-08-20.md` (§0/§1 · §6 historial)
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Premisas E1–E9: `docs/PROJECT_PREMISES.md` (⭐§0 · §4 orquestación)
- Plan R-11 (cerrado): `docs/engineering/plan-r11-hardening-auditoria-v1-2-1-2026-08-21.md`
- Traspaso R-11 de cierre (relevo previo): `docs/engineering/traspaso-relevo-cierre-r11-c1-c6-d1-d2-siguiente-2026-08-21.md`
- Inventario obsoleto no-borrable (riesgo alto): `docs/engineering/pending-delete/README.md`
- ADR 026 (custodia multi-periodo + `DEFAULT_PORTFOLIO`): `docs/adr/026-custodia-obligacion-pendiente.md`
- Verificadores invariante: `scripts/verify/verify_ledger_balance_chain.py` · `verify_account_isolation.py`
- Estándar docstrings: `docs/engineering/code-documentation-standard-2026-08-03.md`
