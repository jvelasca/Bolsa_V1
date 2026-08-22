# Paquete de auditoría — ESTADO GLOBAL consolidado R-1→R-13 (2026-08-22)

> **Propósito:** documento **único** para auditoría externa o lectura rápida tras R-13. Consolida R-1→R-13, deuda cerrada, freeze vigente y checklist operativo.
> **AsOf:** 2026-08-22 · `origin/main` = **`b4efeff`** · árbol limpio · R-13 **CERRADA**.
> **Repo:** `https://github.com/jvelasca/Bolsa_V1`
> **Fuentes:** [`PROJECT_STATE.md`](./PROJECT_STATE.md) · [`backlog-trabajo-2026-08-20.md`](./backlog-trabajo-2026-08-20.md) §0 · [`engineering-index-2026-08-03.md`](./engineering-index-2026-08-03.md)
> **Histórico R-1→R-8:** [`audit-pack-estado-global-2026-08-20.md`](./audit-pack-estado-global-2026-08-20.md) (supersedido).

---

## 0. Resumen ejecutivo

| Pieza                      | Estado                                                 |
| -------------------------- | ------------------------------------------------------ |
| **Rama**                   | `main` = `b4efeff` · tag **`v1.6.0-beta` → `c3964fc`** |
| **R-1..R-8**               | ✅ COMPLETADOS (ver histórico 2026-08-20)              |
| **R-9**                    | ✅ CERRADA `5c557fa` (F1–F8; F9 diferida → ADR-028)    |
| **R-10 / v1.2.1**          | ✅ CERRADA tag `2093296`                               |
| **R-11 / v1.3.0**          | ✅ CERRADA tag `b778292`                               |
| **R-12**                   | ✅ CERRADA tag `5e52bd6`                               |
| **R-13**                   | ✅ CERRADA (A0–A3 + docs)                              |
| **Deuda money/verdad R-7** | ✅ Completa (M-4/T-M4 cerrado R-10 F4b)                |
| **Auth**                   | ✅ JWT-only (R-12, ADR-027)                            |
| **Purge storage V2**       | MONITOR (T+0 19/19; E8 N)                              |
| **Track B producto**       | BLOQUEADO                                              |
| **Ciclo activo**           | Ninguno — decisión propietario                         |

**Mensaje clave:** deuda de dinero real R-6/R-7 **cerrada**. R-8→R-13 añaden prevención (idempotencia, custodia job, JWT, invariantes verify, chaos tests). BETA consolidada en `v1.6.0-beta`. Sin P0 abierto en money-path.

---

## 1. Mapa de releases

| Tag           | Commit      | Ciclo           |
| ------------- | ----------- | --------------- |
| `v1.0.0`      | (histórico) | R-1..R-5        |
| `v1.1.0`      | (histórico) | R-6/R-7         |
| `v1.2.0`      | `b28e956`   | R-9 release doc |
| `v1.2.1`      | `2093296`   | R-10            |
| `v1.3.0`      | `b778292`   | R-11            |
| `v1.5.0-beta` | `5e52bd6`   | R-12            |
| `v1.6.0-beta` | `c3964fc`   | R-13            |

---

## 2. Log histórico R-1→R-8

Ver [`audit-pack-estado-global-2026-08-20.md`](./audit-pack-estado-global-2026-08-20.md) §1. Resumen: reconciliación wire R-2/R-3, R-7 deuda money completa, R-8 prevención + CONTRACT-STALE resuelto.

---

## 3. Log R-9 → R-13 (commits ancla)

### R-9 — Refactor/hardening (2026-08-20) — `5c557fa`

F1 `fa070ec` idempotencia dep/ret · F2 `31954dd` 409 runtime · F3 `26f5ca1` custodia concurrente · F4 `b384f31` DTOs estrictos · F5 `ef4c136` sesión epoch · F6 `e5d8926` balance_after docs · F7 `5d59671` concurrencia + verify · F8 `5ea336f` E8 · **F9 diferida** (ADR-028).

### R-10 / v1.2.1 (2026-08-21) — `2093296`

F1 key obligatoria · F2 TaxProfile · F3 balance_after secuencial · F4a ADR-026 + custody table · **F4b `e12a125` custodia fuera GET → `RunCustodyJob` (cierra M-4/T-M4)** · F5 tag.

### R-11 / v1.3.0 (2026-08-21) — `b778292`

C1 custodia multi-periodo · C2 idempotency_key 16–128 · C3 Decimal ExecuteTrade · C4 contract:check · C5 mypy CI · C6 ADR-026 · D1/D2 E8 + docs.

### R-12 (2026-08-21/22) — `5e52bd6`

Relevo UNO/DOS verify+chaos · R12-ACCOUNTS split · R12-AUTH JWT F1–F10 · R12-409 OpenAPI 409 · EXEC-B-CONC · R12-SCHED (cierra R-8C.2) · Track C UX · Purge V2 T+0 19/19.

### R-13 (2026-08-22) — `c3964fc` / docs `b4efeff`

A0–A2 inventario + E8 micro · A3 tag `v1.6.0-beta` · cierre documental.

---

## 4. Deuda cerrada delta (2026-08-20 → 2026-08-22)

| Ítem                       | Commit    | Ciclo      |
| -------------------------- | --------- | ---------- |
| M-4/T-M4 custodia en GET   | `e12a125` | R-10 F4b   |
| R-8C.2 scheduler-vs-worker | `5e52bd6` | R12-SCHED  |
| 409 OpenAPI idempotency    | `eb24608` | R12-409    |
| EXEC-B-CONC balance_after  | `ca60d0a` | R-12       |
| Auth JWT (D4 diferida)     | R12-AUTH  | R-12       |
| verify ledger A+B          | `f7a4ab0` | Relevo UNO |
| Chaos F4–F5                | `f7a86cc` | Relevo DOS |
| mypy application CI        | `6762614` | R-11 C5    |

---

## 5. Deuda / freeze vigente

| Ítem                     | Estado                                                       |
| ------------------------ | ------------------------------------------------------------ |
| Sin features nuevas      | Freeze                                                       |
| Gobernanza IA / Belief/H | Freeze — no tocar                                            |
| Motor money              | Freeze                                                       |
| `contract:gen`           | Freeze salvo fase                                            |
| Track B producto         | **BLOQUEADO**                                                |
| Purge storage V2         | **MONITOR** 4–8 sem (E8 N)                                   |
| Apply F7b prod           | Ops — local hecho                                            |
| R-9 F9 / legacy bridge   | Diferida (ADR-028)                                           |
| Research→Radar código    | APARCADO (F1–F3 doc ✅)                                      |
| Ops manuales             | secret scanning UI · TRUSTED_PROXIES prod · BP/.L · logs/dev |

---

## 6. Auth y multi-tenant

- **JWT-only** (ADR-027): HMAC legacy retirado R-12.
- Scoping owner, refresh, F7b backfill local (103→0 NULL).
- F7c hard close cuentas.

---

## 7. Núcleo financiero e invariantes

- `balance_after`: postcondición app (test-suite), no constraint DB.
- `scripts/verify/verify_ledger_balance_chain.py`: invariantes A+B, EXIT 0 esperado dev limpio.
- `scripts/verify/verify_financial_invariants.py`: wrapper A–E (R-12 A3).
- Custodia: `RunCustodyJob` periódico; GET solo lectura.
- Chaos: `tests/chaos/` (crash-consistency, load 500×).

---

## 8. Checklist operativo manual

Ver [`ops-r1-seguridad-operaciones-2026-08-19.md`](./ops-r1-seguridad-operaciones-2026-08-19.md):

1. GitHub Secret Scanning + Push protection (UI)
2. `TRUSTED_PROXIES` prod
3. `BP/.L` → `BP.L` en BD dev
4. Limpieza `logs/dev/*.log`
5. Purga historial git dev (opcional)

---

## 9. Índice de fuentes por ciclo

| Ciclo    | Plan                                                                                        | Traspaso                                                                |
| -------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| R-9      | `plan-r9-refactor-hardening-2026-08-20.md`                                                  | `traspaso-relevo-cierre-r9-f1-f8-apertura-f9-2026-08-20.md`             |
| R-10     | `plan-r10-v1-2-1-correcciones-auditoria-2026-08-20.md`                                      | `traspaso-relevo-cierre-r10-v1-2-1-apertura-siguiente-2026-08-21.md`    |
| R-11     | `plan-r11-hardening-auditoria-v1-2-1-2026-08-21.md`                                         | `traspaso-relevo-cierre-r11-c1-c6-d1-d2-siguiente-2026-08-21.md`        |
| R-12     | `plan-r12-auditoria-ux-2026-08-21.md`                                                       | `traspaso-relevo-r12-apertura-2026-08-21.md`                            |
| R-13     | `plan-r13-consolidacion-beta-2026-08-22.md`                                                 | `traspaso-relevo-cierre-r13-consolidacion-beta-siguiente-2026-08-22.md` |
| Track B  | `plan-unificacion-research-radar-2026-08-21.md` · `plan-split-backtests-page-2026-08-22.md` | —                                                                       |
| F9       | ADR-028                                                                                     | —                                                                       |
| Purge V2 | `plan-r12-pending-delete-v2-purge-2026-08-22.md`                                            | `pending-delete/README.md`                                              |

---

## 10. Batería de referencia (auditor externo)

**Firma:** `git rev-parse origin/main` → `b4efeff`

```bash
# Contrato
pnpm contract:check

# Frontend
pnpm --filter @bolsa/web typecheck && pnpm --filter @bolsa/web lint && pnpm --filter @bolsa/web test
pnpm --filter @bolsa/shared typecheck && pnpm --filter @bolsa/shared build

# Python (zona money)
ruff check packages/py apps/api-python
uv run mypy --config-file pyproject.toml  # gate CI
pytest packages/py/application/tests packages/py/infrastructure/tests

# Invariantes (dev limpio, Postgres)
uv run python scripts/verify/verify_ledger_balance_chain.py
uv run python scripts/verify/verify_financial_invariants.py

# Purge V2 monitor
pnpm --filter @bolsa/web exec vitest run \
  src/lib/legacy-storage-metrics.test.ts \
  src/features/trading/use-pending-orders.migration.test.ts \
  src/stores/workspace-legacy-timeframe-favorites.test.ts
```

**Última batería monitor conocida (2026-08-22):** vitest purge **19/19 pass**.

---

## Ap. A — Quick lookup commits

| Código      | Commit               |
| ----------- | -------------------- |
| M-4/T-M4    | `e12a125`            |
| R-8C.2      | `5e52bd6`            |
| R12-409     | `eb24608`            |
| EXEC-B-CONC | `ca60d0a`            |
| JWT-only    | R12-AUTH + `a93ac9f` |

## Ap. B — Lectura sugerida (30 min)

1. Este doc §0 + §5 + §10
2. `backlog-trabajo-2026-08-20.md` §0
3. `traspaso-relevo-cierre-r13-consolidacion-beta-siguiente-2026-08-22.md` §1–§3
