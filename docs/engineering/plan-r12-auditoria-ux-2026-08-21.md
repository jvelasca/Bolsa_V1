# PLAN R-12 — Auditoría residual, higiene y estudio UX (2026-08-21)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (`Product / Ops`).
> **Ancla:** `docs/engineering/estado-verificado-auditoria-vs-main-2026-08-21.md` · `docs/engineering/backlog-trabajo-2026-08-20.md` §0/§1 · `docs/engineering/PROJECT_STATE.md` · premisas E1–E9 + ciclo R-12 en `docs/PROJECT_PREMISES.md` ⭐§0.
> **Estado de partida (verificado):** `main` local = `origin/main` = **`f7a86cc`** · tag **`v1.3.0` → `b778292`** · árbol limpio al abrir · `v1.3.0-5-gf7a86cc`.
> **Estado del plan (AsOf 2026-08-22):** … **R12-AUTH F1–F10 + F8b–F8e** · **F7b script** · **JWT-only**. **`origin/main` `a93ac9f`**. Siguiente: monitor ventana purge V2 (E8 N) · apply F7b en ventana · F7c opcional.
> **Supersede:** `plan-refactor-refuerzo-post-v1-3-0-2026-08-21.md` (Relevo UNO/DOS ejecutados; Relevo TRES/Fase 6 higiene se absorbe aquí).

---

## 0. Anti-alucinación — qué NO se repite

La auditoría externa pegada el 2026-08-21 (tarde) evaluó `main` ~`49ecbcd`. **No ve** `f7a4ab0` (Relevo UNO) ni `f7a86cc` (Relevo DOS). Ya cerrado en código:

- R-11 C1–C6 + D1 + D2 (custodia multi-periodo, idempotency_key, Decimal, contract:check, mypy gate, DEFAULT_PORTFOLIO docs, E8 métodos muertos).
- F1 invariante A+B en `verify_ledger_balance_chain.py`.
- F2 tests de concurrencia de custodia (PG real).
- F3 contrato 409 → **R12-409 B1 HECHO `eb24608`** (supersede Opción A).
- ExecuteTrade B → **EXEC-B-CONC HECHO `ca60d0a`** (`balance_after` post-lock).
- F4 crash-consistency · F5 500-ops chaos · R000 cleanup tests m7/m2.
- R-8C.2 scheduler-vs-worker → **R12-SCHED HECHO `5e52bd6`**.

**Prohibido** reabrir producción financiera, `PAPER_D_EXECUTE`, gobernanza IA, layout de workers (salvo fase), purge de `pending-delete` riesgo alto, `contract:gen` salvo fase pactada.

---

## 1. Premisas del ciclo (refuerzan E1–E9, no las sustituyen)

Ver `docs/PROJECT_PREMISES.md` ⭐§0. Resumen operativo R-12:

1. BETA / fuera de producción: refactor OK si se mantiene la idea (embudo científico → IA gobernada → Confirm humano → paper; integridad financiera).
2. Nada sin plan + aprobación. Una fase = un subagente acotado. Coordinador re-verifica file:line + batería. Máx. ~3 subagentes en paralelo, ficheros disjuntos. 0 commits/push sin OK del propietario.
3. Relevo anti-saturación: doc de traspaso + firma (HEAD, rama, árbol, tag, batería, deuda). El documento manda sobre la memoria del chat.
4. Docs + docstrings + tests/scripts en cada fase.
5. Limpieza E8 estricta: 0 imports, sin storage por nombre, batería verde; docs antiguos se marcan/archivan, no se pierde evidencia.

Plantilla de paso:

> Firma: `HEAD=` · rama · árbol · tag · fase cerrada · siguiente · NO tocar · batería · deuda.

---

## 2. Track A — Cierre de auditoría (orden fijo)

| Fase   | Qué                                                                              | Riesgo        | Archivos típicos                                                                     |
| ------ | -------------------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------ |
| **A0** | Firma HEAD `f7a86cc` + plan R-12 + premisas                                      | Docs          | `PROJECT_PREMISES.md`, `PROJECT_STATE.md`, `backlog`, `estado-verificado`, este plan |
| **A1** | README v1.3.0 BETA · CHANGELOG tag `b778292`                                     | Docs          | `README.md`, `CHANGELOG.md`                                                          |
| **A2** | Test DEFAULT_PORTFOLIO (A cash=0, B cash=10k, fee=500 → PENDING, sin transferir) | Tests-only    | `packages/py/infrastructure/tests/test_custody_default_portfolio_policy.py`          |
| **A3** | Verificador C/D/E (wrapper sobre A+B)                                            | Scripts       | `scripts/verify/verify_financial_invariants.py`                                      |
| **A4** | Chaos residual: retry HTTP misma `idempotency_key`                               | Tests-only    | `apps/api-python/tests/integration/test_http_retry_idempotency.py`                   |
| **A5** | Inventario pending-delete (read-only, **sin purge**)                             | Docs          | `docs/engineering/pending-delete/inventory-r12-2026-08-21.md`                        |
| **A6** | Higiene E8: índice histórico + residuos m7-win/M2 + mypy medir                   | Docs + script | `engineering-index`, `scripts/verify/cleanup_dev_test_residues.py`                   |

### Gates (NO auto-abrir salvo los ya cerrados)

| Gate                               | Recomendación                                                                               | Estado                                            |
| ---------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| 409 en OpenAPI                     | Opción B1 (deposit/withdraw/trade)                                                          | ✅ **HECHO** R12-409 B1 (`eb24608`)               |
| ExecuteTrade / invariante B        | `balance_after` desde cash **post-lock** (`summary.portfolio.cash`)                         | ✅ **HECHO** EXEC-B-CONC (`ca60d0a`)              |
| scheduler-vs-worker (R-8C.2)       | Una autoridad: crons=`scheduler`; colas=`queue_poll`\|`arq`                                 | ✅ **HECHO** R12-SCHED (`5e52bd6`)                |
| Split `accounts.py` (~978 LOC)     | Paquete `bolsa_application/accounts/` + fachada                                             | ✅ **HECHO** R12-ACCOUNTS (`3c958f1`)             |
| Auth User→Account→Resource         | F1 `user_id`/404 (`e52e016`) · F2 más rutas (`9f3354f`) · F3 cash/trade (`5fe5ace`); JWT D4 | ✅ **F1+F2+F3 HECHO** (`5fe5ace`) · plan D4 draft |
| Purge `pending-delete` riesgo alto | E8 sigue N; tests `851b545`; plan V2 con métricas/flags                                     | 📄 **plan draft** (sin purge)                     |
| `TRUSTED_PROXIES` prod             | Checklist operativo                                                                         | Fuera de repo                                     |
| SIGKILL real / PG restart mid-tx   | Ampliar F4                                                                                  | Opcional; F4 ya cubre rollback equivalente        |

---

## 3. Track B — Estudio teórico SEMI vs apps top (cero código FE)

Entregable: `docs/engineering/estudio-flujo-semi-vs-tops-2026-08-21.md`.

Comparativa: TradingView, IBKR Client Portal, thinkorswim, Trading 212, eToro, Koyfin, TrendSpider/Composer.

Hipótesis (solo papel): mesa diaria de 5 puertas — Universo · Señales · Dictamen · Confirmar (primer nivel, no Help) · Libro. Laboratorio fuera del camino diario.

La unificación Research→Radar (`plan-unificacion-research-radar-2026-08-21.md`) queda como **capítulo** de ese estudio; no abre código.

---

## 4. Track C — plan propio (hipótesis B aprobada)

Track B aprobado 2026-08-21. Plan de fases: [`plan-r12-track-c-frontend-2026-08-21.md`](./plan-r12-track-c-frontend-2026-08-21.md). **C1–C5 en `origin/main`** (`0eb8976`) + leftover CORE-R `8dd3caf` + copy E8 `ce601c9`. Split `backtests-page.tsx` y fusión Research→Radar **siguen fuera**.

---

## 5. Batería mínima (coordinador)

- ruff 0 · mypy de la zona (gate incluye `packages/py/application/src`) · pytest de la zona
- `scripts/verify/verify_ledger_balance_chain.py` EXIT 0
- `contract:check` si toca OpenAPI · **NO `contract:gen`** salvo fase pactada
- Chaos/PG-real: DB de test; no ensuciar dev (cleanup canónico)
- `git status` acotado a ficheros de la fase

---

## 6. Versionado

Producto **BETA**. Tag `v1.3.0` intacto sobre `b778292`. Tag **`v1.5.0-beta` → `5e52bd6`** (Track C + copy E8 + gates R12-409 / EXEC-B-CONC / R12-SCHED).

---

## 7. Enlaces

- Premisas: `docs/PROJECT_PREMISES.md`
- Estado vivo: `docs/engineering/PROJECT_STATE.md`
- Backlog: `docs/engineering/backlog-trabajo-2026-08-20.md`
- Ancla SHA: `docs/engineering/estado-verificado-auditoria-vs-main-2026-08-21.md`
- Estudio UX: `docs/engineering/estudio-flujo-semi-vs-tops-2026-08-21.md` (**APROBADO**)
- Plan Track C: `docs/engineering/plan-r12-track-c-frontend-2026-08-21.md`
- Plan D4 JWT: `docs/engineering/plan-r12-auth-d4-jwt-multiuser-2026-08-22.md` (draft, sin implementar)
- Plan purge V2: `docs/engineering/plan-r12-pending-delete-v2-purge-2026-08-22.md` (draft, E8 sigue N)
- Inventario pending-delete: `docs/engineering/pending-delete/inventory-r12-2026-08-21.md`
- ADR 026: `docs/adr/026-custodia-obligacion-pendiente.md`
- Relevo: `docs/engineering/traspaso-relevo-r12-apertura-2026-08-21.md`
