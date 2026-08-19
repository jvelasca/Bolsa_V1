# Traspaso R-4 — A4/B2 `response_model` shape-abierto

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §5.
> **Fase:** R-4 del plan de refactor 2026-08-19 (tipar `response_model` shape-abierto A4/B2 de P1.9).
> **Estado:** **COMPLETADO en `main`** (2 commits directos `38b31d1` + `01b3093`, árbol limpio).
> **AsOf:** 2026-08-19.

---

## 1. Resumen

R-4 cierra la deuda de **`response_model` shape-abierto** dejada por P1.9: los endpoints que devolvían `dict[str, Any]` sin `response_model` (payload JSONB, `to_dict()` timelines, dicts LLM, `week`/`opinions` libres, `Response`/204).

**Hallazgo clave (igual que R-3): NO requirió `regen_full`.** Los docs precondicionaban R-4 a `regen_full` ("tipar `response_model` ahí dropea claves en runtime"). La auditoría verificó que **los 13 endpoints JSON comparten un envelope exterior fijo `{data: <open>}`** (una sola clave top-level siempre presente). Declarar un `response_model` con solo la clave `data` (valor abierto `dict[str, Any]`) **no dropea ninguna clave en runtime** → wire-safe.

- **13 categoría A** (tipables sin cambio de runtime): 12 AI + `daily-ops-report`.
- **0 categoría B** (ninguno requiere `regen_full`).
- **2 categoría C** (sin cuerpo, excluidos): `daily-ops-report.pdf` (`Response` PDF) y `DELETE /accounts/{id}` (204 No Content).

## 2. Implementación (commit `01b3093`)

- **Reuso del wrapper existente `AiEffectivenessResponseDto`** (`data: dict[str, Any]`, componente ya presente en el contrato, ya usado por 4 endpoints) → **cero componentes nuevos**.
- `ai_governance.py`: +`response_model=AiEffectivenessResponseDto` a los 12 endpoints AI shape-abierto.
- `accounts.py`: +`response_model=AiEffectivenessResponseDto` a `daily-ops-report` (import añadido de `schemas.ai_governance`).
- Los `return {"data": ...}` se mantienen intactos (FastAPI serializa vía el `response_model`; misma salida runtime).
- `contract:gen`: los 13 paths pasan de **objeto anónimo `additionalProperties:true`** a **`$ref` del componente existente** `AiEffectivenessResponseDto`. Diff OK: 26 insertions / 78 deletions en `openapi.json`/`schema.d.ts`, sin componentes nuevos ni claves eliminadas.

## 3. Fix adicional de R-3 (commit `38b31d1`)

Al regenerar el contrato, el `tsc` completo destapó **2 assignaciones latentes** de la fase R-3 (que R-3 no detectó por el cache de `tsc -b`), por los `| null`/`?` añadidos en R-3 a tipos shared:

- `backtest-deep-coach.ts:1197` — `d.equityCurve` ahora `BacktestEquityPointDto[] | null | undefined` → coaccion `?? undefined`.
- `instrument-db-tab.tsx:421` — `profileFetchedAt` ahora `string | null | undefined` → coaccion `?? null`.

Son correcciones del propio R-3 (no introducidas por R-4); se commitean aparte para historial limpio.

## 4. Batería (verificada)

| Check                                                                                         | Resultado                              |
| --------------------------------------------------------------------------------------------- | -------------------------------------- |
| ruff (full-tree, CI-style)                                                                    | 0 ✓                                    |
| mypy (ai_governance + accounts)                                                               | 0 ✓                                    |
| pytest (startup_route_check, sprint1_endpoints, core_p_multi_profile, ai_authoring, accounts) | 16 ✓                                   |
| **D5 `contract:check`**                                                                       | **VERDE** (tras `contract:gen`)        |
| web typecheck                                                                                 | 0 ✓ (tras fix call-sites R-3)          |
| web lint                                                                                      | 0 errores (2 warnings preexistentes) ✓ |
| web build                                                                                     | ✓                                      |
| web test                                                                                      | 714 ✓                                  |

## 5. Nota / deuda remanente

- **Semántica del wrapper**: `AiEffectivenessResponseDto` se reutiliza en 13 endpoints AI + daily-ops-report por su shape (pura `data: dict[str,Any]`). El nombre ("effectiveness") queda como matiz cosmético; si se quiere un nombre genérico (`OpenPayloadResponseDto`/alias), es decisión de estilo futura, no bloquea.
- **`number↔integer` / deep-typing del interior de `data`** (los `*Assessment` condicionales de propose, los 3 branches de coach, dicts LLM, `week`/`opinions`): NO tipados por diseño — tipar el interior dropearía claves (drift) y degradaría/cambiaría el contrato. Si se quiere estructura interna, es decisión explícita aparte (no R-4).
- **2 `Response`/204** (`daily-ops-report.pdf`, `DELETE /accounts/{id}`): sin `response_model` posible por diseño.
- **R-5** está pendiente (CI Node.js 20 deprecado + opcional `.prettierrc`).

## 6. Relevo / texto de paso (para el próximo chat)

> CONTEXTO (2026-08-19): **R-4 (A4/B2 `response_model` shape-abierto) COMPLETADO en `main`** — 2 commits directos (`38b31d1` fix R-3 call-sites latentes, `01b3093` R-4 response_model), árbol limpio, sin PR.
>
> **Resultado clave:** R-4 **NO requirió `regen_full`**. Auditoría: los 13 endpoints JSON comparten envelope fijo `{data: <open>}` → tipar con wrapper `AiEffectivenessResponseDto` (ya existente) es wire-safe. **13 categoría A, 0 B, 2 C** (excluidos pdf/204). `contract:gen`: 13 paths `$ref` al componente existente, cero componentes nuevos. D5 `contract:check` VERDE.
>
> **Fix adicional de R-3** (`38b31d1`): al regenerar se destaparon 2 assignaciones latentes por el cache de `tsc -b` en R-3 (`equityCurve ?? undefined` en `backtest-deep-coach.ts:1197`; `profileFetchedAt ?? null` en `instrument-db-tab.tsx:421`).
>
> **Batería:** ruff 0 · mypy 0 · pytest 16 ✓ · `contract:check` VERDE · web typecheck/lint/build ✓ · web test **714 ✓**.
>
> Estado vivo y deuda: `docs/engineering/PROJECT_STATE.md` (LEER PRIMERO, §3 deuda · §6 texto · §7 registro) · `docs/engineering/engineering-index-2026-08-03.md` §5.
> SIGUIENTE (plan 2026-08-19): **R-5 FASE SIGUIENTE** = CI Node.js 20 deprecado (bump actions) + opcional `.prettierrc` (churn de formato del hook pre-commit). No queda fase que requiera `regen_full`: la reconciliación de wire de R-3 y R-4 se resolvió sin cambio de contrato runtime.
>
> Regla: una fase = un subagente acotado + batería + aprobación por commit + relevo documentado al cerrar chat. Freeze vigente: sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA. Auth JWT diferida (D4).
