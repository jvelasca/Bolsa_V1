# Traspaso R-2 — F-DEBT-2/P2.6 consolidar tipos web-only en `packages/shared`

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §5.
> **Fase:** R-2 del plan de refactor 2026-08-19 (= F-DEBT-2/P2.6 deuda).
> **Rama:** `stage/r2-fdebt2-tipos-shared-2026-08-19` → **PR #54 MERGED a `main`** (`7e6cb24`, fast-forward `4271ccf..7e6cb24`).
> **Estado final:** `main` `=` `stage/r2-fdebt2-tipos-shared-2026-08-19` `=` `7e6cb24`. Árbol limpio. **CI PR #54 verde** (battery/quality/scan). **Gate D5:** `contract:check` VERDE por commit (cero cambios de wire).
> **AsOf:** 2026-08-19.

---

## 1. Resumen

R-2 consolida en `packages/shared` los tipos "web-only" del frontend, eliminando duplicación TS↔Py/wire. **Gate D5 respetado:** no se alteró el contrato OpenAPI/wire (`apps/web/api/openapi.json` y `apps/web/src/api/schema.d.ts` sin cambios; `contract:check` verde en cada commit). Re-declaración de forma pura: el valor en wire/localStorage queda idéntico.

Los 4 candidatos explícitos del plan (`RecommendationV1`, `execution-policies`, `tax-report`, `RunManifest`) **ya vivían en `packages/shared`** (verificado); el único realmente web-only era `CoreRVerdict` y su familia. El trabajo real fue la consolidación "web-rico vs shared-suelto" en 3 zonas.

## 2. Commits (PR #54 → main)

| Commit        | Zona                                             | Archivos                                                                                                                                                                   | Batería / D5                                                                                         |
| ------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **`2f5e458`** | **CORE-R family → shared**                       | `packages/shared/src/core-r-judgment.ts` (nuevo) + `index.ts`, `core-r-api.ts` + `apps/web/.../core-r-judgment.ts`, `backtest-list-auto.ts`, `backtest-list-auto-board.ts` | shared typecheck/lint/test 15 ✓ · web typecheck/lint ✓ · web test 714 ✓ · build ✓ · contract:check ✓ |
| **`97c47a7`** | **Supervised-F3 queue → shared**                 | `packages/shared/src/supervised-f3-api.ts` + `apps/web/src/stores/supervised-f3-queue-store.ts`, `apps/web/src/features/trading/supervised-f3-sync.ts`                     | idem ✓ · elimina cast `as unknown as` de frontera (`supervised-f3-sync.ts`)                          |
| **`7e6cb24`** | **Dedupe unions `MandateActor`/`MandateReason`** | `apps/web/src/features/platform/operating-mandate.ts`                                                                                                                      | idem ✓ · dominio tenure/link intacto en el web                                                       |

## 3. Detalle por zona

### 3.1 CORE-R (2f5e458)

- Hogar canónico en `packages/shared/src/core-r-judgment.ts` de: `CoreRVerdict`, `CoreRActionId`, `CoreRAction`, `CoreRJudgment`, `CoreRDualAuditSnap`, `CoreROosSnap`, `CoreRPaperPnlSnap`, `CoreRReportRow`, `CoreRReport` + deps puras `FullCycleSettleReason`, `ListAutoChangeKind`.
- `CORE_R_ENGINE`/`CORE_R_REPORT_KEY` se quedan en el web; los tipos usan literal `"core-r-v0"` (sin dependencia backward web←shared, sin ciclos).
- `core-r-api.ts` enriquece `verdict`/`actions`/`settleReason`/`change` al tipo rico manteniendo **`| string` de seguridad D5** (el BE no garantiza los literales → no asumimos restricción que no impone).
- El web re-exporta desde `@bolsa/shared` → **call-sites intactos** (`core-r-review-queue-store.ts`, `core-r-adopt-mandate.ts`, `strategy-monitor-panel.tsx`, `backtest-list-auto-board-panel.tsx`).

### 3.2 Supervised-F3 (97c47a7)

- `SupervisedQueueOriginDto`, `SupervisedProposePayloadDto` (= `RecommendationV1` + grafos opcionales: technical/fundamental/macro/evidence/news assessment, `decisionPackage: Record<string,unknown>` conservado como blob abierto), `SupervisedEnqueueMetaDto`, `SupervisedF3QueueItemDto` con **`payload` tipado** (antes `Record<string,unknown>`).
- El web re-exporta `SupervisedProposePayload`/`SupervisedQueueOrigin`/`SupervisedEnqueueMeta`/`SupervisedQueueItem` desde shared (call-sites intactos).
- **Eliminado el cast `as unknown as` de frontera** en `supervised-f3-sync.ts:45` → ahora `payload: item.payload` directa (mismo tipo compartido).
- D5: el wire es blob JSON opaco round-trip del BE; tipar es solo compile-time.

### 3.3 operating-mandate dedupe (7e6cb24)

- `MandateActor`/`MandateReason` (web) → alias a `MandateActorDto`/`MandateReasonDto` (shared), uniones de literales idénticas.
- **Decisión (usuario):** solo se deduplicaron las unions puras compartibles; el **tipo de dominio** `MandateTenure`/`MandateTradeLink`/stores del web se **mantiene en el web** (contrato localStorage con `engine`/storage, distinto del DTO de wire).

## 4. Punto abierto documentado (relevancia para fases futuras)

- **operating-mandate (dominio vs DTO):** el web conserva tipos de dominio (`MandateTenure`/`MandateTradeLink`) que NO son los `*Dto` de wire. Son dos contratos distintos (localStorage + storage layer vs espejo API). **No consolidarlos bajo D5** sin decidir el shape del wire (fuera de alcance). Queda como deuda futura si se quiere un único hogar.
- El resto de duplicación TS↔Py "web-rico/shared-suelto" analizada está resuelta en las 2 zonas anteriores. La reconciliación de **fidelidad de tipos de valor** (manifest/number↔integer/null↔undefined) y la reconciliación de ~87 DTOs wire quedan en **R-3** (requiere `regen_full`, decisión explícita). **A4/B2 response_model** → **R-4** (requiere `regen_full`). **CI Node.js 20 deprecado** → **R-5**.

## 5. Batería (resumen, verificado por agente)

- `@bolsa/shared`: build ✓ · typecheck 0 ✓ · lint 0 ✓ (warning preexisting MODULE_TYPELESS_PACKAGE_JSON tolerado) · test 15 passed ✓.
- `@bolsa/web`: typecheck 0 ✓ · lint 0 errores (2 warnings preexisting `backtests-page.tsx:1228,1231` tolerados) ✓ · **test 714 passed** ✓ · build ✓.
- **D5**: `$env:PYTHONIOENCODING='utf-8'; pnpm --filter @bolsa/web contract:check` → **VERDE** en el estado final. (Ojo: en consola Windows cp1252, `contract:check` dispara `uv run` Python y necesita `PYTHONIOENCODING='utf-8'` o falla por encoding, no por contrato.)
- **CI PR #54 (main):** `battery` (Optimize lab) pass · `quality` (Frontend CI) pass · `scan` (Gitleaks) pass.

## 6. Relevo / texto de paso (para el próximo chat)

> CONTEXTO (2026-08-19): **R-2 (F-DEBT-2/P2.6) consolidar tipos web-only en `packages/shared` MERGED a `main`** vía **PR #54** (fast-forward `4271ccf..7e6cb24`). Rama `stage/r2-fdebt2-tipos-shared-2026-08-19` sincronizada a `main` (mismo tip `7e6cb24`). Árbol limpio. **CI PR verde** (battery/quality/scan). **Gate D5 respetado**: `contract:check` VERDE, `openapi.json`/`schema.d.ts` sin cambios.
>
> **3 commits:** `2f5e458` (familia CORE-R → `packages/shared/src/core-r-judgment.ts` + espejo `core-r-api.ts`, web re-exporta) · `97c47a7` (cola Supervised-F3 → `supervised-f3-api.ts`, payload tipado, **elimina cast `as unknown as`** en `supervised-f3-sync.ts`) · `7e6cb24` (dedupe unions `MandateActor`/`MandateReason` → `MandateActorDto`/`MandateReasonDto`).
>
> Verificado: los candidatos explícitos `RecommendationV1`/`execution-policies`/`tax-report`/`RunManifest` ya estaban en shared; el único web-only era la familia CORE-R. **Punto abierto:** el web conserva los tipos de dominio `MandateTenure`/`MandateTradeLink` (localStorage+engine), distintos de los `*Dto` de wire (NO consolidados por D5, solo las unions puras).
>
> Estado vivo y deuda: `docs/engineering/PROJECT_STATE.md` (LEER PRIMERO, §3 deuda · §6 texto · §7 registro) · `docs/engineering/engineering-index-2026-08-03.md` §5.
> SIGUIENTE (plan 2026-08-19): **R-3** fidelidad de valor + reconciliación ~87 DTOs wire (requiere `regen_full`, decisión explícita) · **R-4** A4/B2 `response_model` (requiere `regen_full`) · **R-5** CI Node.js 20 deprecado (bump actions).
>
> Regla: una fase = un subagente acotado + batería + aprobación por commit + relevo documentado al cerrar chat. Freeze vigente: sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA. Auth JWT diferida (D4).
