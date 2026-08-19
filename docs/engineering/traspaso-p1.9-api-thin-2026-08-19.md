# Traspaso — F-DEBT-1 P1.9 API thin (adelgazar endpoints FastAPI)

| Campo     | Valor                                                                                 |
| --------- | ------------------------------------------------------------------------------------- |
| **Rama**  | `stage/f1-integridad-financiera-2026-08-11`                                           |
| **AsOf**  | 2026-08-19                                                                            |
| **Fase**  | F-DEBT-1 = P1.9 API thin (alcance exclusivo SOLO P1.9) · Riesgo Medio                 |
| **Padre** | `docs/engineering/PROJECT_STATE.md` (§3/§6/§7) · `engineering-index-2026-08-03.md` §5 |

> Propósito: relevo del hilo que ha ejecutado los primeros 9 slices de P1.9.
> Estado vivo y deuda priorizada en `PROJECT_STATE.md` §3 (LEER PRIMERO). Protocolo en §5.

---

## 1. Lo que cierra este relevo (commits P1.9 en `stage/f1-*`)

Tabla de los **9 slices de P1.9 commiteados** (orden cronológico):

| #   | Commit    | Slice                                                                                                                      | Batería                        |
| --- | --------- | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| 1   | `21d3dd0` | Unificar serialización `_iso` (x6) y `SignalEventV1Dto` (x3)                                                               | golpes verdes                  |
| 2   | `19cd433` | Desacoplar scans/trackers via `schemas.scans`                                                                              | ruff/mypy/pytest/contract      |
| 3   | `8d63ea7` | blob-sync a use-cases (core_r/supervised_f3/mandates) vía `account_blob_state`                                             | ruff/mypy/pytest/contract      |
| 4   | `4297528` | Adelgazar `instrument_daily_opinions` via schemas + DI                                                                     | ruff/mypy/pytest/contract      |
| 5   | `836348c` | Serialización research (8 `_to_*_dto`) → `schemas/research.py`                                                             | ruff/mypy/pytest/contract      |
| 6   | `8406d55` | Mover 15 DTOs de `ai_governance.py` → `schemas/ai_governance.py`                                                           | ✅ api 56✓ · contract ✓        |
| 7   | `6a1c57f` | DI `get_cognitive_repository` en 9 instanciaciones de handlers                                                             | ✅ api 56✓ · contract ✓        |
| 8   | `2331ad9` | Getters-DI `get_propose_recommendation_use_case`/`get_confirm_intent_use_case` + `_EdgeReportAdapter` en `dependencies.py` | ✅ api 56✓ · contract ✓        |
| 9   | `939e477` | Use-case `EnsureAccountInvestorProfile` + `DeclaredProfileInput`; `create_account` delega perfil inversor                  | ✅ api 56✓ / 164✓ · contract ✓ |

**Slices 6–9 (esta sesión)**: batería completa ruff 0 · mypy 244 files 0 · pytest api 56 passed / 164+flake
pre-existente · `contract:check` OK (OpenAPI sin cambios → D5 cero wire).

**Patrón aplicado** conforme al protocolo:

- Mappers → `schemas/*.py` con `to_*_dto` (importan dominio `bolsa_domain` o infra `*_Repository`/`Record`).
- DI: la ruta mantiene `session: Annotated[AsyncSession, Depends(get_db_session)]` y llama getters
  `get_xxx(session)` (NO inyectar el use-case como parámetro `Annotated` — FastAPI falla al registrar).
- Orquestación/persistencia → `bolsa_application` (use-cases) + `dependencies.py` (getters).

---

## 2. Deuda residual de P1.9 (pendiente)

> **A4/B2 = `response_model` tipado en endpoints `dict[str,Any]`** — **DIFERIDO por decisión del usuario**
> (cambio de contrato OpenAPI, fuera de la regla D5).

- **A4 (ai_governance, 13 endpoints)** — endpoints que devuelven `dict[str,Any]` sin `response_model`:
  `list_decision_sessions`, `decision_session_learning_summary`, `get_decision_session`,
  `get_decision_session_replay`, `close_decision_session_outcome`, `propose_recommendation`,
  `confirm_intent`, `analyze_backtest_coach`, `explain_instrument_fundamentals`,
  `explain_dia_d_session_evidence`, `explain_core_r_review_evidence`, `summarize_instrument_filing`,
  `ask_instrument_filing`.
- **B2 (accounts, 3 endpoints)** — `get_daily_ops_report` (dict), `download_daily_ops_digest_pdf` (Response
  PDF), `delete_account` (Response 204).

**Al hacer A4/B2 en el futuro**: hacerlo en commit aparte; escribir `response_model` que reconstruya
EXACTAMENTE el wire; verificar con `contract:check` (bidireccional) — si un campo no encaja, habrá drift
(`contract:check` lo detecta) y habrá que regen `openapi.json`/`schema.d.ts` (`contract:gen`) y validar el
typecheck FE. Separar el tipado-response_model del resto porque altera el contrato.

---

## 3. Estado del árbol / batería al cerrar

- Árbol **limpio** (`git status` = nothing to commit) · rama `stage/f1-integridad-financiera-2026-08-11`.
- CI gates: ruff 0 · mypy 244 files 0 · pytest api 56 passed / full 164+flake pre-existente
  (`test_lists_crud_flow`, pasa en aislamiento) · `contract:check` OK.
- Nota: `investor_profiles.py` produce warning de CRLF→LF al commitear (git normaliza; benigno, preexistente).

---

## 4. Texto de traspaso (pegar en el próximo hilo)

> CONTEXTO: Ola de hardening `stage/f1-*` con **P1.9 API thin EN CURSO**. Rama `stage/f1-integridad-financiera-2026-08-11`.
> Árbol limpio · CI verde.
> Estado vivo y deuda priorizada en `docs/engineering/PROJECT_STATE.md` (LEER PRIMERO). Mapa de fases mergeadas
> en `docs/engineering/engineering-index-2026-08-03.md` §5 · cierre de la sub-ola hardening:
> `docs/engineering/traspaso-ola-hardening-cierre-2026-08-19.md`.
> Relevo P1.9: `docs/engineering/traspaso-p1.9-api-thin-2026-08-19.md` (ESTE doc: 9 slices hechos + A4/B2 pendiente).
>
> FASE ACTIVA: **F-DEBT-1 = P1.9 API thin** (adelgazar endpoints FastAPI). **Alcance EXCLUSIVO: SOLO P1.9**.
> **mypy ~450 ya cerrado (P1.6 `6a89f6c`)** · **P2.6 DTOs TS↔Py → F-DEBT-2** (deuda futura). Riesgo Medio.
> **9 slices COMMITEADOS** (scans/trackers, blob-sync, instrument_daily_opinions, research, DTOs+DI ai_governance,
> use-cases propose/confirm, perfil inversor create_account) — ver §1.
> **Lo ÚNICO que queda de P1.9: A4/B2 = `response_model` tipado en endpoints `dict[str,Any]` (13 ai_governance +
> 3 accounts) — DIFERIDO por decisión usuario: cambia el contrato OpenAPI (fuera de la regla D5).** Hacerlo en
> commit aparte verificando `contract:check` (+ `contract:gen` si drift).
>
> Después de P1.9 (backlog, ver §3): **F-WORKER-1** (auto-sync `BP/.L`, retomar subagente con `resume`) · **F-DEBT-2**
> (P2.6 consolidar tipos web-only en `packages/shared`).
>
> Protocolo: un subagente acotado + batería + aprobación por commit. No tocar fuera de P1.9. Auth JWT diferida (D4).
> NO reabrir Belief/H ni gobernanza IA. Warning operativo: auto-sync `BP/.L` (Yahoo 404, F-WORKER-1).
>
> Batería (desde la raíz): `uv run ruff check packages/py apps/api-python --config pyproject.toml` ·
> `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src apps/api-python/src
--follow-imports=silent` (NO incluir `packages/py/application/src` al gate; application se valida
> transitivamente vía apps/api-python) · `uv run pytest packages/py/market/tests apps/api-python/tests -q -m
"not integration"` (única falla habitual = `test_lists_crud_flow` FLAKY preexistente, pasa en aislamiento) ·
> `$env:PYTHONIOENCODING='utf-8'; pnpm --filter @bolsa/web contract:check` (PowerShell, puntos y comas; git commit
> con múltiples `-m`, heredoc no soportado).
