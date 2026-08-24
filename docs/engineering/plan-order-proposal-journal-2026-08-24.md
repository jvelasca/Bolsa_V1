# Plan — OrderProposal + DecisionJournal (Ciclo 1/5)

> **Padre:** [ADR-029](../adr/029-order-proposal-decision-journal.md) · [engineering-index](./engineering-index-2026-08-03.md) §1.
> **AsOf:** 2026-08-24 · HEAD verificado **`e3b943a`** (tag `v1.7.0-beta`) · `main` == `origin/main` · working tree limpio.
> **Estado:** docs-only — **F1 NO abierto** hasta subagente de implementación aprobado por coordinador.
> **Método:** citas `path:line` verificadas en disco; sin memoria.

---

## 0. Objetivo

Introducir **OrderProposal** (handle de fase, sin duplicar Recommendation/Intent) y **DecisionJournal** (audit trail append-only) como siguiente rebanada del spine, respetando D1/D2/D3 y freeze post-beta.

---

## 1. Fases

### F1 — Dominio + persistencia (sin HTTP)

**Entregables**

| #    | Entregable                                         | Detalle                                                                                                                                                                       |
| ---- | -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| F1.1 | `OrderProposalV1` en `@bolsa/shared`               | DTO refs-only: `proposalId`, `decisionId`, `recommendationId`, `sessionId`, `accountId`, `instrumentId`, `status`, `createdAt`, `closedAt?`. **Sin** action/quantity/metrics. |
| F1.2 | Mapper `decision_session → OrderProposalV1`        | Proyectar desde `DecisionSessionRecord` / fila `kind='propose'` (`tables.py:608` · `decision-session.ts:24`).                                                                 |
| F1.3 | `DecisionJournalEntryV1` + enum `JournalEventType` | Campos: `entryId`, `decisionId`, `sessionId?`, `accountId?`, `instrumentId?`, `eventType`, `actor` (`human` \| `system`), `payload` mínimo, `createdAt`.                      |
| F1.4 | Tabla `decision_journal_entries`                   | Alembic migration; PK `id`; índices `(account_id, created_at DESC)`, `(decision_id)`, `(session_id)`.                                                                         |
| F1.5 | `JournalWriter` (application)                      | Puerto + impl SQLAlchemy; **append-only**.                                                                                                                                    |
| F1.6 | Hooks internos (sin cambiar contrato HTTP)         | Llamadas best-effort desde puntos existentes (ver §3).                                                                                                                        |

**Persistencia — sketch DDL**

```sql
-- F1.4 sketch (Alembic authoritative)
CREATE TABLE decision_journal_entries (
  id              TEXT PRIMARY KEY,
  decision_id     TEXT NOT NULL,
  session_id      TEXT NULL REFERENCES decision_sessions(id) ON DELETE SET NULL,
  account_id      TEXT NULL,
  instrument_id   TEXT NULL,
  event_type      TEXT NOT NULL,
  actor           TEXT NOT NULL,
  payload         JSONB NULL,
  created_at      TIMESTAMPTZ NOT NULL
);
CREATE INDEX decision_journal_entries_account_created_idx
  ON decision_journal_entries (account_id, created_at DESC);
CREATE INDEX decision_journal_entries_decision_id_idx
  ON decision_journal_entries (decision_id);
```

**OrderProposal:** **sin tabla nueva en F1** — ancla en `decision_sessions` (`fase0-decision-spine-mapping-2026-08-24.md:32`).

**Batería F1 esperada**

| Comando                                                                  | Objetivo                |
| ------------------------------------------------------------------------ | ----------------------- |
| `ruff check packages/py apps/api-python`                                 | 0                       |
| `mypy` (gate CI)                                                         | 0 en ficheros tocados   |
| `pytest packages/py/application/tests/test_*journal*` (nuevos)           | mapper + writer + hooks |
| `pytest packages/py/application/tests/test_propose_recommendation_f3.py` | regresión propose       |
| `pytest packages/py/application/tests/test_confirm_recommendation*.py`   | regresión confirm       |
| `pnpm --filter @bolsa/shared typecheck`                                  | DTOs nuevos             |
| `pnpm test:decision-spine`                                               | **53** (sin regresión)  |

---

### F2 — Wire / API (solo si aprobado)

**Entregables**

| #    | Entregable                                        | Notas                                                                                                                                       |
| ---- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| F2.1 | `GET /api/accounts/{account_id}/decision-journal` | Lista paginada `DecisionJournalEntryV1[]`; filtros `instrumentId?`, `since?`, `eventType?`.                                                 |
| F2.2 | (Opcional) `GET .../order-proposals`              | Proyección desde `list_decision_sessions` filtrado `kind=propose`; puede reutilizar API existente `list_decision_sessions` (`api.ts:1308`). |
| F2.3 | `contract:gen` + `contract:check`                 | **Solo con OK explícito** del propietario (freeze `CURRENT_SYSTEM.md:62`).                                                                  |

**Batería F2 esperada:** F1 + `pnpm contract:check` · pytest API route · `pnpm --filter @bolsa/web typecheck`.

---

### F3 — UI read-only journal view

**Entregables**

| #    | Entregable                                              | Notas                                                                                              |
| ---- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| F3.1 | Ruta `/decision-journal` o pestaña en `/decision-board` | Solo lectura; sin confirm ni execute. Patrón: `decision-board-page.tsx:6` (GET only).              |
| F3.2 | Timeline por cuenta                                     | Lista cronológica de `DecisionJournalEntryV1`; link a Decision Replay existente (`api.ts:1301`).   |
| F3.3 | Copy UX                                                 | «Session = foto del razonamiento · Journal = historial de transiciones» (`decision-session.ts:3`). |

**Batería F3 esperada:** F2 + `pnpm --filter @bolsa/web lint|test` · smoke manual cuenta DEMO.

---

## 2. NO TOUCH (todas las fases)

| Área                        | Cita / razón                                                                                  |
| --------------------------- | --------------------------------------------------------------------------------------------- |
| **ExecuteTrade internals**  | `accounts/trade.py:17` — único fill; ADR-029 §2.4                                             |
| **Motor money / ledger**    | `CURRENT_SYSTEM.md:62` freeze                                                                 |
| **H3 orphan behavior**      | `contract=absent` sigue ejecutando — `confirm_recommendation.py:288` · `CURRENT_SYSTEM.md:46` |
| **`contract:gen`**          | Salvo F2 aprobado — freeze                                                                    |
| **Belief / gobernanza IA**  | `CURRENT_SYSTEM.md:24`                                                                        |
| **Lab/Radar spine**         | ADR-019 / D3 cerrada                                                                          |
| **Track B B1–B12**          | Cerrado                                                                                       |
| **Dictamen → Runtime solo** | Sin forzar cola 3 al journal en v1                                                            |

---

## 3. Mapa consumidores / call-sites (verificado)

### 3.1 OrderIntent

| Consumidor   | path:line                                                                | Rol                              |
| ------------ | ------------------------------------------------------------------------ | -------------------------------- |
| DTO shared   | `order-intent.ts:20`                                                     | `OrderIntentV1`                  |
| Factory Py   | `order_intent.py:69`                                                     | `intent_from_recommendation`     |
| Confirm SEMI | `confirm_recommendation.py:279`                                          | crea intent desde Recommendation |
| API client   | `api.ts:1348`                                                            | `confirmOrderIntent`             |
| UI F3        | `supervised-f3-panel.tsx:362`                                            | POST confirm                     |
| Tests        | `test_recommendation_f3.py:40` · `test_execute_trade_idempotency.py:796` | regresión side/wait              |

### 3.2 Recommendation

| Consumidor | path:line                            | Rol                                      |
| ---------- | ------------------------------------ | ---------------------------------------- |
| DTO shared | `recommendation.ts:16`               | `RecommendationV1`                       |
| DTO Py     | `recommendation.py:23`               | `Recommendation` dataclass               |
| Propose F3 | `propose_recommendation.py:142`      | `ProposeRecommendationFromTa`            |
| Confirm    | `confirm_recommendation.py:259`      | reconstruye `Recommendation` del payload |
| UI propose | `supervised-f3-panel.tsx:313`        | `api.proposeRecommendation`              |
| UI alarm   | `trading-alarm-inbox-button.tsx:191` | propose desde dictamen                   |
| UI scan    | `scan-results-panel.tsx:177`         | propose desde radar                      |
| Lab puente | `finalist-propose-supervised.ts:75`  | propose supervisado                      |
| DI API     | `dependencies.py:1097`               | wiring use-case                          |

### 3.3 DecisionPackage

| Consumidor | path:line                           | Rol                                |
| ---------- | ----------------------------------- | ---------------------------------- |
| DTO shared | `decision-package.ts:39`            | `DecisionPackageV1`                |
| Runtime    | `decision_runtime.py:256`           | `run_decision_runtime`             |
| Confirm D2 | `confirm_recommendation.py:118`     | `resolve_session_decision_package` |
| Confirm D2 | `confirm_recommendation.py:290`     | `contract_status` present/absent   |
| UI chips   | `decision-package-chips-bar.tsx:42` | acción + Fit                       |
| Gate TS    | `apply-gate-to-decision.ts:51`      | mirror D2.4                        |

### 3.4 decision_sessions

| Consumidor      | path:line                          | Rol                           |
| --------------- | ---------------------------------- | ----------------------------- |
| ORM             | `tables.py:602`                    | `DecisionSessionRow`          |
| DTO shared      | `decision-session.ts:27`           | `DecisionSessionV1`           |
| Propose persist | `propose_recommendation.py:445`    | `append_decision_session`     |
| Confirm persist | `confirm_recommendation.py:569`    | `build_auto_session` + append |
| AUTO persist    | `execution_router.py:293` · `:338` | sesiones paper_auto / veto    |
| Repo            | `cognitive_repository.py:68`       | append                        |
| API list/get    | `api.ts:1294` · `:1308`            | GET session / list            |
| UI learning     | `operativa-outcomes.tsx:47`        | learning summary              |
| Decision Board  | `decision-board-page.tsx:192`      | agregado read-only            |

### 3.5 confirm_recommendation (spine SEMI)

| Punto         | path:line                       | Evento journal v1                       |
| ------------- | ------------------------------- | --------------------------------------- |
| Clase         | `confirm_recommendation.py:225` | —                                       |
| Intent        | `:279`                          | (precursor `human_confirm`)             |
| Contract D2   | `:290`–`:297`                   | `contract_verified` / `contract_absent` |
| Risk veto D1  | `:340`–`:352`                   | `risk_veto`                             |
| ExecuteTrade  | `:365`                          | `executed`                              |
| check_opening | `:469`                          | `gate_evaluated`                        |

### 3.6 mandate_trade_links (hook, no journal)

| Punto     | path:line                                         | Nota                  |
| --------- | ------------------------------------------------- | --------------------- |
| ORM       | `tables.py:1331`                                  | `MandateTradeLinkRow` |
| Migración | `20260802160000_mandate_tenures/migration.sql:29` | DDL                   |
| ADR       | `020-operating-mandate-tenure.md:10`              | atribución post-fill  |

### 3.7 ExecuteTrade (solo referencia — NO TOCAR)

| Entrada | path:line                       |
| ------- | ------------------------------- |
| SEMI    | `confirm_recommendation.py:365` |
| AUTO    | `execution_router.py:716`       |
| Clase   | `accounts/trade.py:17`          |

### 3.8 Risk / Gate (registrar, no reescribir)

| Punto           | path:line                          |
| --------------- | ---------------------------------- |
| `check_opening` | `risk_engine.py:98`                |
| AUTO gate       | `execution_router.py:604` · `:883` |
| SEMI gate       | `confirm_recommendation.py:469`    |

---

## 4. Hooks F1 (dónde escribir journal)

| Momento                                | Writer call                     | eventType                               |
| -------------------------------------- | ------------------------------- | --------------------------------------- |
| Post-`append_decision_session` propose | `propose_recommendation.py:445` | `proposal_recorded`                     |
| Post contract resolve                  | `confirm_recommendation.py:297` | `contract_verified` / `contract_absent` |
| Post risk veto SEMI                    | `confirm_recommendation.py:340` | `risk_veto`                             |
| Post ExecuteTrade OK SEMI              | `confirm_recommendation.py:365` | `executed`                              |
| Post gate AUTO deny/allow              | `execution_router.py:604`       | `gate_evaluated`                        |
| Post fill AUTO                         | `execution_router.py:716`       | `executed`                              |

Patrón de fallo: **best-effort** (como sesión `:448` · confirm `:406`) — no tumbar propose/confirm/router.

---

## 5. Riesgos / bloqueantes

| #   | Riesgo                                          | Mitigación                                                                 |
| --- | ----------------------------------------------- | -------------------------------------------------------------------------- |
| R1  | Duplicar campos Recommendation en OrderProposal | ADR-029 §2.1 refs-only; review verificador                                 |
| R2  | Journal vs Session confusión en UI              | Copy explícito F3; no borrar sesiones                                      |
| R3  | `contract:gen` en F2                            | Gate propietario antes de abrir F2                                         |
| R4  | Volumen JSONB payload                           | Payload mínimo (status, reason, contract); foto sigue en session           |
| R5  | Orphan H3                                       | Journal marca `contract_absent` + `executed`; **no** cambiar fail-open     |
| R6  | Prisma degradado                                | Alembic autoridad (`CURRENT_SYSTEM.md:12`); espejo Prisma opcional post-F1 |

---

## 6. Orden de ejecución recomendado

1. **Ciclo 1 (este doc)** — ADR + plan + traspaso ✅
2. **Subagente F1** — DTO + migration + writer + hooks + tests
3. Coordinador verifica + batería + aprobación commit
4. **F2** — solo con OK API/contract
5. **F3** — UI read-only

Ciclos 2–5 del owner (fuera de este plan): TBD por coordinador.

---

## 7. Fuera de alcance

Attribution engine · PortfolioFit nuevo · DailyOrchestrator · cambio H3 · Belief · money · purge E8.
