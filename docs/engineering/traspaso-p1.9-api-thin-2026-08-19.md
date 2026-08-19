# Traspaso — F-DEBT-1 P1.9 API thin (adelgazar endpoints FastAPI) — CERRADO

| Campo      | Valor                                                                                 |
| ---------- | ------------------------------------------------------------------------------------- |
| **Rama**   | `stage/f1-integridad-financiera-2026-08-11`                                           |
| **AsOf**   | 2026-08-19                                                                            |
| **Fase**   | F-DEBT-1 = P1.9 API thin (alcance exclusivo SOLO P1.9) · Riesgo Medio                 |
| **Estado** | **CERRADO** (10 slices commiteados)                                                   |
| **Padre**  | `docs/engineering/PROJECT_STATE.md` (§3/§6/§7) · `engineering-index-2026-08-03.md` §5 |

> Propósito: cierre del hilo que ejecutó los slices de P1.9 y relevo a F-WORKER-1 / F-DEBT-2
> (tareas fuera del alcance de P1.9, requieren hilo propio).
> Estado vivo y deuda priorizada en `PROJECT_STATE.md` §3 (LEER PRIMERO). Protocolo en §5.

---

## 1. Lo que cierra este relevo (commits P1.9 en `stage/f1-*`)

Tabla de los **9 slices de P1.9 commiteados** (orden cronológico):

| #   | Commit    | Slice                                                                                                                                             | Batería                                                     |
| --- | --------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| 1   | `21d3dd0` | Unificar serialización `_iso` (x6) y `SignalEventV1Dto` (x3)                                                                                      | golpes verdes                                               |
| 2   | `19cd433` | Desacoplar scans/trackers via `schemas.scans`                                                                                                     | ruff/mypy/pytest/contract                                   |
| 3   | `8d63ea7` | blob-sync a use-cases (core_r/supervised_f3/mandates) vía `account_blob_state`                                                                    | ruff/mypy/pytest/contract                                   |
| 4   | `4297528` | Adelgazar `instrument_daily_opinions` via schemas + DI                                                                                            | ruff/mypy/pytest/contract                                   |
| 5   | `836348c` | Serialización research (8 `_to_*_dto`) → `schemas/research.py`                                                                                    | ruff/mypy/pytest/contract                                   |
| 6   | `8406d55` | Mover 15 DTOs de `ai_governance.py` → `schemas/ai_governance.py`                                                                                  | ✅ api 56✓ · contract ✓                                     |
| 7   | `6a1c57f` | DI `get_cognitive_repository` en 9 instanciaciones de handlers                                                                                    | ✅ api 56✓ · contract ✓                                     |
| 8   | `2331ad9` | Getters-DI `get_propose_recommendation_use_case`/`get_confirm_intent_use_case` + `_EdgeReportAdapter` en `dependencies.py`                        | ✅ api 56✓ · contract ✓                                     |
| 9   | `939e477` | Use-case `EnsureAccountInvestorProfile` + `DeclaredProfileInput`; `create_account` delega perfil inversor                                         | ✅ api 56✓ / 164✓ · contract ✓                              |
| 10  | `cbfac26` | **A4-safe**: `response_model` tipado en `list_decision_sessions` (`DecisionSessionSummaryDto`/`ListDecisionSessionsResponseDto`) + contrato regen | ✅ ruff/mypy/pytest 56✓ · contract ✓ · web typecheck/lint ✓ |

**Slices 6–10 (esta sesión)**: batería completa ruff 0 · mypy 244 files 0 · pytest api 56 passed / 164+flake
pre-existente · `contract:check` OK. **A4-safe (`cbfac26`)**: el único endpoint de shape determinista; `contract:gen`
regenerado y `contract:check` OK (wire idéntico).

**Patrón aplicado** conforme al protocolo:

- Mappers → `schemas/*.py` con `to_*_dto` (importan dominio `bolsa_domain` o infra `*_Repository`/`Record`).
- DI: la ruta mantiene `session: Annotated[AsyncSession, Depends(get_db_session)]` y llama getters
  `get_xxx(session)` (NO inyectar el use-case como parámetro `Annotated` — FastAPI falla al registrar).
- Orquestación/persistencia → `bolsa_application` (use-cases) + `dependencies.py` (getters).

---

## 2. Deuda residual de P1.9 (no tipada — shape abierto, fuera de D5)

> **A4/B2 = `response_model` tipado en endpoints `dict[str,Any]`** — el **A4-safe** (`list_decision_sessions`)
> se completó (`cbfac26`). El **resto es shape abierto** y NO se tipa: tipar `response_model` ahí dropea claves
> en runtime (cambio de wire, fuera de la regla D5). Solo mediante `regen_full` (cambio de contrato + revisión FE)
> sería viable, y es decisión explícita aparte.

- **A4 (ai_governance, shape abierto)** — `decision_session_learning_summary`, `get_decision_session` (payload
  JSONB), `get_decision_session_replay` (`to_dict()` timeline), `close_decision_session_outcome` (payload
  free), `propose_recommendation` (`.to_dict()`), `confirm_intent` (dict libre), `analyze_backtest_coach`
  (3 shapes), `explain_instrument_fundamentals`/`explain_dia_d_session_evidence`/`explain_core_r_review_evidence`
  (dicts LLM), `summarize_instrument_filing`/`ask_instrument_filing` (dicts LLM).
- **B2 (accounts)** — `get_daily_ops_report` (`week`/`opinions` = dicts libres), `download_daily_ops_digest_pdf`
  (Response PDF, `response_model` no aplica), `delete_account` (Response 204, sin cuerpo).

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

> CONTEXTO: Ola de hardening `stage/f1-*` con **F-DEBT-1 = P1.9 API thin COMPLETADO (cerrado)**. Rama
> `stage/f1-integridad-financiera-2026-08-11`. Árbol limpio · CI verde.
> Estado vivo y deuda priorizada en `docs/engineering/PROJECT_STATE.md` (LEER PRIMERO). Mapa de fases mergeadas
> en `docs/engineering/engineering-index-2026-08-03.md` §5 · cierre de la sub-ola hardening:
> `docs/engineering/traspaso-ola-hardening-cierre-2026-08-19.md` · cierre P1.9:
> `docs/engineering/traspaso-p1.9-api-thin-2026-08-19.md` (10 slices hechos + A4/B2 shape-abierto no tipado).
>
> FASE CERRADA: **F-DEBT-1 = P1.9 API thin** (adelgazar endpoints FastAPI). **mypy ~450 ya cerrado (P1.6
> `6a89f6c`)** · **P2.6 DTOs TS↔Py → F-DEBT-2** (deuda futura). **10 slices COMMITEADOS** (scans/trackers,
> blob-sync, instrument_daily_opinions, research, DTOs+DI ai_governance, use-cases propose/confirm, perfil
> inversor create_account, A4-safe `list_decision_sessions`) — ver §1.
> **A4/B2 restante NO tipado = shape abierto** (payload JSONB, `to_dict()` timelines, dicts LLM, `week`/`opinions`
> libres, Response/204): tipar ahí dropea claves en runtime (fuera de la regla D5). Solo viable con `regen_full`
> (cambio de contrato + revisión FE), decisión explícita aparte.
>
> SIGUIENTE (fuera de P1.9, hilo propio): **F-WORKER-1** (auto-sync `BP/.L`, retomar subagente con `resume`) ·
> **F-DEBT-2** (P2.6 consolidar tipos web-only en `packages/shared`).
>
> Protocolo: un subagente acotado + batería + aprobación por commit. No tocar fuera del alcance declarado.
> Auth JWT diferida (D4). NO reabrir Belief/H ni gobernanza IA. Warning operativo: auto-sync `BP/.L` (Yahoo 404,
> F-WORKER-1).
>
> Batería (desde la raíz): `uv run ruff check packages/py apps/api-python --config pyproject.toml` ·
> `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src apps/api-python/src
--follow-imports=silent` (NO incluir `packages/py/application/src` al gate; application se valida
> transitivamente vía apps/api-python) · `uv run pytest packages/py/market/tests apps/api-python/tests -q -m
"not integration"` (única falla habitual = `test_lists_crud_flow` FLAKY preexistente, pasa en aislamiento) ·
> `$env:PYTHONIOENCODING='utf-8'; pnpm --filter @bolsa/web contract:check` (PowerShell, puntos y comas; git commit
> con múltiples `-m`, heredoc no soportado).
