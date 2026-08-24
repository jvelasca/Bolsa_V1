# Paquete de auditoría — ESTADO GLOBAL post-tag v1.7.0-beta + Ciclo 1 OrderProposal/Journal (2026-08-24d)

> **Propósito:** documento **único** para auditoría externa general tras el **cierre y tag** del ciclo beta slice **U6 → DS-05 → ops → DS-03 → higiene → Research→Radar → `v1.7.0-beta`**, más el **Ciclo 1 OrderProposal/Journal F1–F3 CERRADO** y **F9-A CERRADO**. Consolida identidad, freeze, arcos cerrados, verificación y riesgos ops.
> **AsOf:** 2026-08-24 · HEAD **`8a1e64d`** = `origin/main` · tag **`v1.7.0-beta` → `e3b943a`** verificado en `origin` · R-13 **CERRADA** · Track B **CERRADO** · Fase 0 spine **COMPLETA** · UX mesa **U0–U6 CERRADA** · **DS-05/DS-03 CERRADAS** · **ops propietario CERRADA** · **Research→Radar copy CERRADA** · **ciclo beta slice CERRADO y TAGGED** · **Ciclo 1 OrderProposal/Journal F1–F3 CERRADO** · **F9-A CERRADO**. F9-B **PARKED**.
> **Repo:** `https://github.com/jvelasca/Bolsa_V1`
> **Fuentes vivas:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [`backlog-trabajo-2026-08-20.md`](./backlog-trabajo-2026-08-20.md) §0 · [`traspaso-relevo-tag-v1-7-0-beta-cierre-ciclo-2026-08-24.md`](./traspaso-relevo-tag-v1-7-0-beta-cierre-ciclo-2026-08-24.md) · [`PROJECT_STATE.md`](./PROJECT_STATE.md)
> **Histórico:** [`audit-pack-estado-global-2026-08-24c.md`](./audit-pack-estado-global-2026-08-24c.md) (pre-tag; stamp pendiente; supersedido) · [`audit-pack-estado-global-2026-08-24b.md`](./audit-pack-estado-global-2026-08-24b.md) · [`audit-pack-estado-global-2026-08-24.md`](./audit-pack-estado-global-2026-08-24.md) · R-1→R-8: [`audit-pack-estado-global-2026-08-20.md`](./audit-pack-estado-global-2026-08-20.md).

---

## 0. Resumen ejecutivo

| Pieza                       | Estado                                                                                                                    |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **Rama**                    | `origin/main` = **`8a1e64d`** · tag **`v1.7.0-beta` → `e3b943a`** (intacto) · previo **`v1.6.0-beta` → `c3964fc`**        |
| **Identidad**               | QROS + Investment OS + **Decision Spine** · Lab/Radar **fuera** (D3)                                                      |
| **R-1..R-13**               | ✅ CERRADOS (money-path + JWT + BETA)                                                                                     |
| **Track B split backtests** | ✅ CERRADO (B0–B12)                                                                                                       |
| **Fase 0 Decision Spine**   | ✅ COMPLETA (Fit · Decision Board · D1/D2/D3 · Prove · H5 · **DS-05** · **DS-03**)                                        |
| **UX mesa U0–U6**           | ✅ CERRADA (`04e441e` U0–U5 · U6 `9e9a346`)                                                                               |
| **Spine residual DS-05**    | ✅ CERRADA (`15e86a4`) — Data Freshness Gate en `check_opening`                                                           |
| **Spine residual DS-03**    | ✅ CERRADA (`41adb8e`) — Account Mandate Gate en `check_opening`                                                          |
| **Ops propietario**         | ✅ CERRADA (`5100d23`) — secret scanning + push protection enabled · runbook `TRUSTED_PROXIES`                            |
| **Higiene dev**             | ✅ CERRADA (`ea9a985`, dato local) — residuos R8C + verify EXIT 0                                                         |
| **Research→Radar copy**     | ✅ CERRADA (`2c26fe6`) — Asesor vs Señales; sin fusión hubs                                                               |
| **Release tag**             | ✅ **`v1.7.0-beta` → `e3b943a`** (stamp + tag git en origin)                                                              |
| **Ciclo 1 OP/Journal**      | ✅ **F1–F3 CERRADOS** (`9dc6f49`…`3192d39` + stamp `8a1e64d`) · Alembic `010` en `bolsa_v1`                               |
| **F9-A analytics↔market**   | ✅ A1+A2+A3 (tests · import-linter 4/4 · CI lint-imports) · **F9-B PARKED**                                               |
| **Freeze**                  | OrderProposal/Journal **cerrado** (ADR-029); `PAPER_D_EXECUTE` off · sin broker live · Belief frozen · Track B no reabrir |

**Mensaje clave:** el núcleo financiero R-7→R-13, el Decision Spine, la mesa U0–U6, ops ejecutable, copy Research→Radar y el tag **`v1.7.0-beta`** están **cerrados** en **`e3b943a`**. Post-tag: **Ciclo 1 F1–F3** + **F9-A** en **`8a1e64d`**. Alembic `010` aplicado en `bolsa_v1`. **BETA / no producción.**

---

## 1. Identidad del sistema

- **QROS** (Lab / backtests, ADR-011) y **Investment OS** (mesa SEMI/AUTO) unidos por el **Decision Spine**.
- Lab/Radar **recomiendan**; **no** entran en la columna autoritativa de decisión (**D3**, ADR-019).
- LLM **nunca** ejecuta. Auth viva = **JWT + cookie HttpOnly** (ADR-027); `APP_PASSWORD` = overlay opcional de login en dev.

Camino de ejecución (resumen): `Assessment → DecisionPackage → Policy Gate + check_opening (Fit + DS-05 freshness + DS-03 mandate) → Confirm SEMI | AUTO router → ExecuteTrade (paper)`.

Detalle file:line: [`decision-spine-cadena-2026-08-24.md`](./decision-spine-cadena-2026-08-24.md).

---

## 2. Mapa de releases (tags)

| Tag           | Commit        | Nota                                                |
| ------------- | ------------- | --------------------------------------------------- |
| `v1.2.0`      | `b28e956`     | R-9                                                 |
| `v1.2.1`      | `2093296`     | R-10                                                |
| `v1.3.0`      | `b778292`     | R-11                                                |
| `v1.5.0-beta` | `5e52bd6`     | R-12                                                |
| `v1.6.0-beta` | `c3964fc`     | R-13                                                |
| `v1.7.0-beta` | **`e3b943a`** | beta slice post-R-13 — **tag verificado en origin** |

HEAD **`8a1e64d`** = `origin/main` (F1–F3 + F9-A). Tag **`v1.7.0-beta`** permanece en **`e3b943a`**.

---

## 3. Arcos cerrados (beta slice → tag v1.7.0-beta)

| Arco                | Qué entrega                                                                | Anclas típicas |
| ------------------- | -------------------------------------------------------------------------- | -------------- |
| UX mesa U6          | Preview ticket margen/comisión en Confirm/drawer (UI-only)                 | `9e9a346`      |
| Spine residual      | **DS-05** Data Freshness Gate fail-closed (SEMI ohlcv + AUTO signal ts)    | `15e86a4`      |
| Spine residual      | **DS-03** Account Mandate Gate fail-closed (tenure BD + mismatch AUTO)     | `41adb8e`      |
| Ops propietario     | Secret scanning + push protection enabled · runbook `TRUSTED_PROXIES` prod | `5100d23`      |
| Higiene dev         | Residuos R8C eliminados · verify EXIT 0 (dato local)                       | `ea9a985`      |
| Research→Radar copy | Asesor vs Señales CTAs/cross-links; sin fusión hubs                        | `2c26fe6`      |
| Tag beta            | Stamp + tag git **`v1.7.0-beta`**                                          | `e3b943a`      |

Arcos previos (pack 24b/24c): Fase 0 spine · Prove · H5 · UX U0–U5 · ops residual símbolos `/`.

R-1→R-13 + Track B: ver pack histórico 2026-08-24.

---

## 4. Ciclo 1 — OrderProposal/Journal (CERRADO)

> **Estado:** `origin/main` **`8a1e64d`** · tag **`v1.7.0-beta` → `e3b943a`** intacto.

| Ítem                          | Estado                                                                                               |
| ----------------------------- | ---------------------------------------------------------------------------------------------------- |
| **ADR-029**                   | Aceptado — [`029-order-proposal-decision-journal.md`](../adr/029-order-proposal-decision-journal.md) |
| **Plan F1–F3**                | [`plan-order-proposal-journal-2026-08-24.md`](./plan-order-proposal-journal-2026-08-24.md)           |
| **F1 dominio + persistencia** | ✅ `9dc6f49` — DTOs · mapper · Alembic `010` · `JournalWriter` · hooks best-effort · tests journal   |
| **F2 wire/API**               | ✅ `1024d56` — `GET /api/accounts/{id}/decision-journal` · `contract:gen` pactado                    |
| **F3 UI journal**             | ✅ `3192d39` — `/decision-journal` timeline read-only                                                |
| **Alembic `010` en dev**      | ✅ `bolsa_v1` head `010_decision_journal_entries` (tabla+índices; 0 filas al aplicar)                |

**Alcance:** OrderProposal = proyección refs-only desde `decision_sessions` `kind='propose'`; DecisionJournal = tabla append-only; hooks observan, **no relajan** gates D1/D2/H3.

Relevo cierre: [`traspaso-relevo-order-proposal-journal-cierre-f1-f3-2026-08-24.md`](./traspaso-relevo-order-proposal-journal-cierre-f1-f3-2026-08-24.md).

---

## 5. Freeze vigente

| Ítem                                         | Estado                                                                                      |
| -------------------------------------------- | ------------------------------------------------------------------------------------------- |
| OrderProposal / Journal                      | **F1–F3 CERRADOS** — ADR-029; UI `/decision-journal` read-only; Alembic `010` en `bolsa_v1` |
| Attribution / orquestador                    | **No**                                                                                      |
| `PAPER_D_EXECUTE`                            | **off**                                                                                     |
| Broker live                                  | **No**                                                                                      |
| Track B B1–B12                               | **Cerrado** — no reabrir                                                                    |
| Belief / gobernanza IA                       | **Freeze**                                                                                  |
| `contract:gen`                               | Solo fase pactada                                                                           |
| Motor money (`ExecuteTrade`, custodia apply) | **No tocar**                                                                                |
| H3 orphan `contract=absent`                  | **Congelado** — journal solo audita                                                         |
| F9-B `legacy_portfolio_id`                   | **PARKED** — no abrir sin ADR                                                               |
| Purge storage / pending-delete riesgo alto   | **MONITOR** — E8 **N** · 0 purges                                                           |

---

## 6. Cómo verificar

**Firma release:** `git fetch && git rev-parse origin/main` → **`8a1e64d`** · `git rev-parse v1.7.0-beta` → **`e3b943a`**

```bash
pnpm test:decision-spine   # cadena decisión (confirm, Fit, risk, DS-05, DS-03, AUTO veto, Golden) — 53 tests
pnpm test:semi             # UI/libro DEMO F3 — NO es el spine
```

**Journal / F9-A:** `pytest packages/py/application/tests/test_decision_journal.py` · `uv run python -c "from importlinter.cli import lint_imports; raise SystemExit(lint_imports(config_filename='packages/py/.importlinter'))"` → 4/4.

Docs de lectura rápida: [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · relevo tag [`traspaso-relevo-tag-v1-7-0-beta-cierre-ciclo-2026-08-24.md`](./traspaso-relevo-tag-v1-7-0-beta-cierre-ciclo-2026-08-24.md) · backlog §0.

Batería money/contrato completa (opcional, pack 2026-08-24 §11): `pnpm contract:check` · web typecheck/lint/test · ruff/mypy/pytest application · `verify_ledger_balance_chain.py`.

**Ops (propietario):** UI GitHub → Settings → Code security and analysis → confirmar Secret scanning + Push protection **Enabled**. Runbook: [`ops-trusted-proxies-prod-runbook-2026-08-24.md`](./ops-trusted-proxies-prod-runbook-2026-08-24.md).

---

## 7. Open risks (ops, propietario)

1. **`TRUSTED_PROXIES` en prod** — IPs/CIDR reales del edge proxy **bloqueado en el propietario** (runbook listo; valor no va en repo).
2. **Secret scanning UI** — habilitado vía API 2026-08-24; **recomendado confirmar en UI** del repo.
3. **Purga historial git dev** (opcional) — decisión explícita pendiente.
4. **F9-B PARKED** — no abrir `legacy_portfolio_id` sin ADR. Purge storage / motor money / gobernanza IA **congelados**.

---

## 8. Limitaciones conocidas (honestas; no son bugs de esta rebanada)

Copiado de [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) (HEAD `8a1e64d`):

- Ranking IO sigue en cliente (`operativa-index.ts`).
- Dos call-sites a `ExecuteTrade` (TO-BE: convergencia **antes** del fill).
- Dictamen (`DailyOpinionService`) no entra solo al Runtime; puede acabar en SEMI por alarma.
- Aperturas orphan sin package: `contract=absent`, **sí ejecutan** (H3).
- Confirm SEMI: perfil vía `active_profile_id` → `check_opening` (H5 CERRADA). Sin perfil → defaults moderate.
- Composite `portfolioConstraints` sigue `not_evaluated`; Fit vive al lado.
- DS-03 Account Mandate Gate **CERRADA** (`41adb8e`); OperatingMandate playbook ticker sigue siendo concepto distinto.
- OrderProposal / Journal **F1–F3 CERRADOS**; Attribution **sin abrir**.

---

## 9. Índice de fuentes

| Tema               | Doc                                                              |
| ------------------ | ---------------------------------------------------------------- |
| SoT corto          | `docs/CURRENT_SYSTEM.md`                                         |
| Relevo tag beta    | `traspaso-relevo-tag-v1-7-0-beta-cierre-ciclo-2026-08-24.md`     |
| Ciclo 1 OP/Journal | `docs/adr/029-order-proposal-decision-journal.md`                |
| Cadena spine       | `decision-spine-cadena-2026-08-24.md`                            |
| Backlog §0         | `backlog-trabajo-2026-08-20.md`                                  |
| Pack previo        | `audit-pack-estado-global-2026-08-24c.md` (pre-tag; supersedido) |
| Pack R-13 era      | `audit-pack-estado-global-2026-08-22.md`                         |

---

## Ap. A — Quick lookup

| Pieza             | Commit / nota           |
| ----------------- | ----------------------- |
| HEAD / ancla viva | `8a1e64d`               |
| Tag latest        | `v1.7.0-beta`=`e3b943a` |
| Tag previo        | `v1.6.0-beta`=`c3964fc` |
| Research→Radar    | `2c26fe6`               |
| DS-03 mandate     | `41adb8e`               |
| U6 ticket preview | `9e9a346`               |
| DS-05 freshness   | `15e86a4`               |
| U0–U5 mesa        | `04e441e`               |
| Prove Spine       | `5e81350`               |
| H5 código         | `f56af2f`               |
| D2 confirm pkg    | `f7b1f6c`               |
| D3 Lab fuera      | `ea0c93f`               |
| Ciclo 1 F3 UI     | `3192d39`               |
| Stamp F1–F3/F9-A  | `8a1e64d`               |

## Ap. B — Lectura sugerida (20–30 min)

1. Este doc §0 + §4 + §5 + §6 + §7
2. `CURRENT_SYSTEM.md`
3. Relevo tag v1.7.0-beta §1–§3
4. ADR-029 §1–§2 (si audita Ciclo 1)
5. (Opcional) pack 2026-08-24c para contexto pre-tag
