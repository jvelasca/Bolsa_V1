# Relevo para re-auditoría de la APP (2026-08-19)

> **Propósito:** texto de paso listo para el próximo hilo de chat (re-auditoría de toda la app), consolidando el estado REAL de `main` tras R-2/R-3/R-4.
> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §5 · estado vivo en `docs/engineering/PROJECT_STATE.md`.
> **AsOf:** 2026-08-19 · tip `f9767d8` (local = origin/main, árbol limpio).

---

## Texto de traspaso (pegar directo en el nuevo hilo)

> **CONTEXTO (2026-08-19) — hilo de CADENA (R-2/R-3/R-4). Estado REAL de la app:**
>
> **Arbol limpio y sincronizado:** `local main = origin/main = f9767d8`, `git status` sin cambios, sin nada sin-pushear.
>
> **Fases de refactor completadas en `main` (plan 2026-08-19), TODAS sin PR (commits directos) y con `regen_full` NO necesario:**
>
> 1. **R-2 (F-DEBT-2/P2.6) MERGED vía PR #54 (fast-forward `4271ccf..7e6cb24` código + `9d290d5` docs)**: consolidar tipos web-only en `packages/shared`. 3 commits código + 1 docs: `2f5e458` (familia CORE-R → `packages/shared/src/core-r-judgment.ts` + espejo `core-r-api.ts`, web re-exporta, call-sites intactos) · `97c47a7` (cola Supervised-F3 → `supervised-f3-api.ts`, elimina cast `as unknown as`) · `7e6cb24` (dedupe `MandateActor/MandateReason` → `*Dto` de shared). Batería: shared 15 ✓ · web typecheck/lint ✓ · web test 714 ✓ · build ✓. **Deuda anotada**: `MandateTenure/MandateTradeLink` quedan web-only (localStorage+engine, no consolidados por D5). Relevo: `docs/engineering/traspaso-r2-fdebt2-...2026-08-19.md`.
> 2. **R-3 (fidelidad de valor de tipos) COMPLETADO en `main` (`df269f0` código + `a82068f` docs)**: **hallazgo clave: NO requirió `regen_full`** — `contract:check` VERDE y `schema.d.ts` ya reflejaba la verdad del wire; el gap estaba en tipos shared. 143 DTOs mapeados, deep en ~40 dinero/valor. **Solo 5 DTOs (14 campos) FE-only** con gaps reales, fix = añadir `| null`/`?`: `BacktestRunDto/Detail` (timeframe/dataVersion/commissionBps/slippageBps/manifest/strategyDefinitionId/equityCurve), `InstrumentRecordDto.profileFetchedAt`, `ScanRunResultDto` (strategyDefinitionId/listId), `ScanUniverseDto` (listId/instrumentIds), `IndexSubscribeJobDto` (result/error/completedAt). Sin eliminar claves, sin estrechar unions. Batería: shared typecheck/lint 0, test 15 ✓ · web typecheck/lint 0 · web test 714 ✓ · **D5 `contract:check` VERDE (cero wire)**.
> 3. **R-4 (A4/B2 `response_model` shape-abierto) COMPLETADO en `main` (`38b31d1` + `01b3093` código, `f9767d8` docs)**: **hallazgo clave: NO requirió `regen_full`** — auditoría: los 13 endpoints JSON comparten envelope exterior fijo `{data: <open>}` → reutilizar `AiEffectivenessResponseDto` (wrapper `data: dict[str,Any]`, componente ya existente) es **wire-safe** (tipar solo la clave `data` no dropea claves internas). **13 categoría A** (12 AI en `ai_governance.py` + `daily-ops-report` en `accounts.py`) · **0 B** · **2 C excluidos** (`daily-ops-report.pdf` Response + `DELETE /accounts/{id}` 204). `contract:gen`: 13 paths de objeto anónimo `additionalProperties` a `$ref` del componente existente (**cero componentes nuevos**, zero runtime). **Fix colateral R-3 (`38b31d1`)**: al regenerar, `tsc` completo destapó 2 assignaciones latentes de R-3 (cache `tsc -b`): `equityCurve ?? undefined` (`backtest-deep-coach.ts:1197`) + `profileFetchedAt ?? null` (`instrument-db-tab.tsx:421`). Batería R-4: ruff (full-tree) 0 · mypy (2 files) 0 · pytest (startup/sprint/core_p/ai_authoring/accounts) 16 ✓ · **D5 `contract:check` VERDE** · web typecheck/lint/build ✓ · web test **714 ✓**.
>
> **Conclusión general del trío R-2/R-3/R-4:** la reconciliación de wire (~87 DTOs según el plan original) se resolvió **sin ningún `regen_full`**: R-3 fue fidelidad de valor FE-only y R-4 fue tipar el envelope sin cambiar runtime. `contract:check` (D5) siempre VERDE.
>
> **PENDIENTES (orden sugerido):**
>
> - **R-5 FASE SIGUIENTE**: CI `Node.js 20` deprecado (bump actions en `.github/workflows/`) + opcional `.prettierrc` (el churn de formato del hook pre-commit viene por usar comillas dobles por defecto sobre legacy comillas simples). Aviso no-bloqueante adicional en CI: 2 warnings React en `backtests-page.tsx:1228,1231` (react-hooks/exhaustive-deps).
> - **Deuda operativa/futura** (NO abrir sin decisión explícita): `MandateTenure`/`MandateTradeLink` web-only sin consolidar; inner `data` de endpoints AI NO tipado (por diseño; tiparlo dropearía claves condicionales); alias semántico del wrapper `AiEffectivenessResponseDto`→`OpenPayloadResponseDto` (cosmético); transferencias/dividendos (P2.3 README); registro `BP.L` en BD (F-WORKER-1, acción manual no código).
>
> **Freeze vigente:** sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA. **Auth JWT diferida (D4).**
>
> **Docs (LEER PRIMERO):** `docs/engineering/PROJECT_STATE.md` (§3 deuda · §6 texto traspaso · §7 registro) · maestro: `docs/engineering/engineering-index-2026-08-03.md` · traspasos por fase: `traspaso-r2-fdebt2-...`, `traspaso-r3-fidelidad-valor-tipos-...`, `traspaso-r4-response-model-shape-abierto-2026-08-19.md`.

> **Regla de la fase:** una fase = un subagente acotado + batería + aprobación por commit + relevo documentado al cerrar chat. Vigilar hilo; si se satura, crear doc y texto de paso al siguiente agente. Documentar bien siempre.

---
