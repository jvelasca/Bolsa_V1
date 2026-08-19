# Traspaso R-3 — Fidelidad de valor de tipos + reconciliación DTOs wire

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §5.
> **Fase:** R-3 del plan de refactor 2026-08-19 (fidelidad de valor de tipos + reconciliación ~87 DTOs wire).
> **Rama/estado:** commit directo en `main` `df269f0` (árbol limpio antes/después). Sin PR (fix acotado a `packages/shared`, precedente F-HLTH-1).
> **AsOf:** 2026-08-19.

---

## 1. Resumen

R-3 buscaba corregir la **fidelidad de valor** de los DTOs: que el tipo que declara el FE (`@bolsa/shared`) refleje la **verdad real del wire** (nullable / opcionalidad / nullvsundefined), más allá de la igualdad de CLAVES que ya garantiza el gate `contract-check.ts` (G1–G11, bidireccional).

**Hallazgo clave:** los docs previos asumían que R-3 requería `regen_full` (cambio de contrato + revisión FE) y reconciliación de ~87 DTOs. **La auditoría demostró lo contrario: ya no es necesario `regen_full`.** El `contract:check` está VERDE y el artefacto generado (`schema.d.ts`) ya refleja correctamente la nullabilidad/opcionalidad real del wire. El gap estaba en los **tipos shared**, que prometían no-nulo donde el wire puede entregar `null`.

- 143 DTOs shared mapean 1:1 a un schema de wire (de ~200 `*Dto` exportados).
- Auditoría profunda sobre ~40 DTOs de las familias dinero/valor (accounts, cash, portfolio, position, backtest, tax, optimize/lab, scan, market-index, research, signals).
- **Solo 5 DTOs (14 campos) tenían gaps reales de verdad de valor.** El resto está alineado o son blobs/discrepancias documentadas por diseño.

## 2. Hallazgos y fix (commit `df269f0`)

Todos los fixes son **FE-only** (añadir `| null` / `?`), no eliminan claves, no estrechan unions, y **NO requieren cambio de backend ni `regen_full`**.

| #   | DTO (fichero)                                                           | Campos                                                                                            | Problema (wire real)               | Fix                                  |
| --- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ---------------------------------- | ------------------------------------ |
| 1   | `BacktestRunDto`/`BacktestRunDetailDto` (`types.ts`) — **sentinela G1** | `timeframe`, `dataVersion`, `commissionBps`, `slippageBps`, `strategyDefinitionId`, `equityCurve` | Wire `X \| null`, FE `X`           | añadido `\| null`                    |
| 1b  | idem                                                                    | `manifest`                                                                                        | Wire `object \| null`              | añadido `\| null` (documentado P2.6) |
| 2   | `ScanRunResultDto` (`scan-api.ts`)                                      | `strategyDefinitionId`, `listId`                                                                  | Wire `string \| null`, FE `string` | añadido `\| null`                    |
| 3   | `IndexSubscribeJobDto` (`market-indices.ts`)                            | `result`, `error`, `completedAt`                                                                  | Wire opcional, FE requerido        | añadido `?`                          |
| 4   | `InstrumentRecordDto` (`types.ts`)                                      | `profileFetchedAt`                                                                                | Wire opcional, FE requerido        | añadido `?`                          |
| 5   | `ScanUniverseDto` (`scan-api.ts`)                                       | `listId`, `instrumentIds`                                                                         | Wire `X \| null`, FE `X`           | añadido `\| null`                    |

Verificación independiente del hallazgo #1: `schema.d.ts:3500-3536` declara `commissionBps?: number | null`, etc., mientras `types.ts:339-344` los declaraba no-nulo → confirmado.

## 3. Batería (verificada)

| Check                   | Resultado                                                           |
| ----------------------- | ------------------------------------------------------------------- |
| shared typecheck        | 0 ✓                                                                 |
| shared lint             | 0 ✓ (warning module preexistente)                                   |
| shared test             | 15 ✓                                                                |
| web typecheck           | 0 ✓                                                                 |
| web lint                | 0 errores (2 warnings preexistentes `backtests-page.tsx:1228,1231`) |
| **D5 `contract:check`** | **VERDE** — `openapi.json`/`schema.d.ts` sin cambios, cero wire     |
| web test                | **714 passed** ✓                                                    |

## 4. Nota operativa (no obstruye): churn de formato del hook pre-commit

El hook `.lintstagedrc` ejecuta `prettier --write` con **config por defecto (comillas dobles)** sobre `.ts`. Varios ficheros de `packages/shared` estaban commiteados con **comillas simples** (no hay `.prettierrc`), por lo que al tocarlos el hook los **re-normaliza a comillas dobles**, inflando el diff con churn de formato **ajeno al cambio semántico**.

- `df269f0`: 106/100 líneas en total, de las cuales ~14 son el fix semántico y el resto = normalización prettier (comillas/imports).
- **Comportamiento pre-existente**, ya presente en commits R-2 (`97c47a7` 77/57, `2f5e458` 91 del). No es regresión de esta fase.
- **Opción de mejora** (R-5 / decisión aparte, no esta fase): añadir `.prettierrc` con `singleQuote: true` (alinea con el estilo legacy y elimina el churn) y/o normalizar con prettier las familias de `packages/shared` en un commit limpio aparte.

## 5. Deuda / fuera de alcance de R-3

- **`regen_full` explícito de wire: NO fue necesario** para la fidelidad de valor auditada (el artefacto ya era correcto). Si en el futuro se decide cambiar shapes de wire (p. ej. tipar A4/B2, `manifest` en objeto estructurado), sigue siendo decisión explícita aparte (R-4 / nueva).
- **`number↔integer`**: no accionable (ambos emiten `number` en openapi-typescript) — informativo.
- **Resto de DTOs no auditados en profundidad** (~100, familias UI-sidecar/request: tracker, execution-policy, position-policy, instrument-filings, chart DTOs): menor riesgo de dinero/valor; un pase posterior puede aplicar el mismo null-scan si se requiere cobertura total.
- **Blobs por diseño**: CoreR/SupervisedF3 (G4/G5), A4/B2 shape-abierto (`payload`/`params` `Record<string,unknown>`), `manifest` (documentado P2.6). No tocar.
- **R-4** A4/B2 `response_model` (requiere `regen_full`, decisión explícita) · **R-5** CI Node.js 20 deprecado (bump actions) + opcional `.prettierrc`.

## 6. Relevo / texto de paso (para el próximo chat)

> CONTEXTO (2026-08-19): **R-3 (fidelidad de valor de tipos) COMPLETADO en `main`** — commit directo `df269f0`, árbol limpio, sin PR (fix acotado a `packages/shared`).
>
> **Resultado clave:** R-3 **NO requirió `regen_full`**. La auditoría encontró que `contract:check` estaba VERDE y el artefacto generado (`schema.d.ts`) ya reflejaba la verdad del wire; el gap real estaba en los tipos shared. Solo **5 DTOs (14 campos)** tenían gaps de verdad de valor, todos FE-only: `BacktestRunDto`/`Detail` (`timeframe`/`dataVersion`/`commissionBps`/`slippageBps`/`manifest`/`strategyDefinitionId`/`equityCurve`), `InstrumentRecordDto.profileFetchedAt`, `ScanRunResultDto` (`strategyDefinitionId`/`listId`), `ScanUniverseDto` (`listId`/`instrumentIds`), `IndexSubscribeJobDto` (`result`/`error`/`completedAt`). Fix: añadir `\| null` / `?` (sin eliminar claves, sin estrechar unions, sin degradar el FE).
>
> **Batería verde:** shared typecheck/lint/test 15 · web typecheck/lint 0 errores · web test **714** · **D5 `contract:check` VERDE** (cero wire).
>
> **Nota:** churn de formato en `df269f0` (106/100 vs ~14 semánticas) por el hook `.lintstagedrc` que corre `prettier` con config por defecto (comillas dobles) sobre ficheros legacy de comillas simples. Preexistente en R-2. Opcional limpiar con `.prettierrc` (`singleQuote`) en R-5.
>
> Estado vivo y deuda: `docs/engineering/PROJECT_STATE.md` (LEER PRIMERO, §3 deuda · §6 texto · §7 registro) · `docs/engineering/engineering-index-2026-08-03.md` §5.
> SIGUIENTE (plan 2026-08-19): **R-4** A4/B2 `response_model` shape-abierto (requiere `regen_full`, decisión explícita) · **R-5** CI Node.js 20 deprecado (bump actions).
>
> Regla: una fase = un subagente acotado + batería + aprobación por commit + relevo documentado al cerrar chat. Freeze vigente: sin features nuevas · no reabrir Belief/H · no tocar gobernanza IA. Auth JWT diferida (D4).
