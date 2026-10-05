# Evidencia `v2.88.52-beta` — `AUTO · UI`: **AUTO UI REFACTOR 1.0** (modelo semántico implementado)

**Objeto:** el **siguiente chat, un auditor externo, o un Cursor distinto**. No es el historial (`PROJECT_STATE.md`).

**Producto:** `V2.88.52-beta` · **Package:** `2.11.52-beta` · **AsOf:** 2026-10-05 · **Nature:** `UI / read-model` · **Fase:** `AUTO UI 1.0` · **Δ AUTO decision/execution motor = 0**.

**Schemas:** sin cambios (`dia-d-multi-band-v1`, `dia-d-thesis-exit-v5`, `dia-d-multi-cycle-ledger-v7`, `dia-d-thesis-stop-sequences-v2`). **Alembic:** head `048_journal_entry_dedupe_key` — **SIN migración**. **Contrato HTTP:** **sin cambio** (`contract:check` OK; `openapi.json`/`schema.d.ts` no se mueven).

**Padre:** [`v2.88.51`](../v2.88.51/README.md) (tag `fa487409`, `Release tag CI` [`37305844986`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37305844986) VERDE) → [`v2.88.50`](../v2.88.50/README.md) → [`v2.88.48`](../v2.88.48/README.md) → [`v2.88.47`](../v2.88.47/README.md).

**Decisión de alcance (declarada).** `v2.88.51` **congeló por escrito** el `AUTO UI SEMANTIC MODEL 1.0` (spec `docs/engineering/spec-auto-ui-semantic-model-1-2026-10-05.md`) y dejó su implementación como trabajo posterior. Este sello **implementa** ese modelo sobre el piloto: **`SELECTION` ≠ `DECISION`**, **`EXIT` ≠ `SETTLEMENT`**, **`OPPORTUNITY` como contexto**, medición unificada, Operación por defecto, selección en URL y enlace EXPLICACIÓN → DÍA-D. **NO** se re-corre el pipeline `DÍA-D` (A/C cerrada en `v2.88.50`; las cifras OOS se **heredan y citan**). **NO** se reestructura la navegación global ni se borra ninguna pantalla (refactor **aditivo**).

---

## 0. Qué añade este sello (y qué NO)

Cinco bloques, todos **de UI / read-model** (cero motor):

1. **View-model semántico** (`@bolsa/shared`): 14 etapas con `kind`/`group`; `SELECTION` ← `TOP_N`; `DECISION` separada (`NOT_MEASURED`); `EXIT` derivada de `SETTLEMENT`; `OPPORTUNITY` fuera de los hechos → bloque `context`.
2. **`MeasurementValue`/`MeasurementBadge`** (web): representación única valor + medición; refactor de los 4 paneles AUTO ⇒ el bug del PnL de `v2.88.50` es **imposible por accidente**.
3. **Operación por defecto** + **selección en URL** (`mode`/`cycle`/`day`/`window`/`symbol`); `current` queda como vista cruda/experta; `enabled: mode !== "dia-d"`.
4. **Enlace EXPLICACIÓN → DÍA-D** («Ver heatmap de {symbol}»), con símbolo/ventana preseleccionados.
5. **Sello**: bump `2.11.52-beta`, `meta.bump` alineado, docs y re-anclaje del freeze del runner.

**NO** toca el motor, los umbrales, `TOP_N`, la allocation ni las costuras de decisión. **NO** introduce estados `STALE`/`BLOCKED` (el DTO de ciclo no los produce). **NO** re-mide `DÍA-D`. **NO** cambia el contrato HTTP.

---

## 1. Afirmaciones falsables (cada una con su forma de romperse)

| # | Afirmación | Cómo se rompe (falsación) | Evidencia |
| --- | --- | --- | --- |
| **1** | **`SELECTION` (TOP-N) ≠ `DECISION` (cartera).** La selección se copia del paso durable `TOP_N`; la decisión de cartera queda `NOT_MEASURED` con su nota declarada. | Que `DECISION.sourceStepId === "TOP_N"` o que su estado no sea `NOT_MEASURED`. | §3.1; `auto-operation-story.test.ts` (test «separa SELECTION (TOP-N) de DECISION»). |
| **2** | **`EXIT` (DERIVED) ≠ `SETTLEMENT` (FACT).** La salida se deriva de la liquidación; no se pintan como dos hechos independientes. | Que `EXIT.kind !== "DERIVED"` o `EXIT.sourceStepId !== "SETTLEMENT"`. | §3.1; `auto-operation-story.test.ts` (test «deriva EXIT de SETTLEMENT»). |
| **3** | **`OPPORTUNITY` es contexto, no un hecho.** Sale del array de hechos y vive en `story.context`; PIT/régimen/ranking se declaran `NO MEDIDO`. | Que `OPPORTUNITY` aparezca entre las etapas de `group: OPERATION` o que el `context` invente un valor. | §3.1; `auto-operation-story.test.ts` + `auto-operation-story-panel.test.tsx` (contexto). |
| **4** | **Un valor sin medición NUNCA se pinta como medido.** Un `null`/`UNKNOWN` se rotula `NO MEDIDO`/`PARCIAL`; una cifra no afirmable se puede retener. | Que `MeasurementValue` muestre una cifra junto a una medición ≠ `COMPLETE` cuando se pide `withhold`. | §3.2; `measurement-value.test.tsx` (8). |
| **5** | **El modo por defecto es `operation`.** Abrir `/auto-monitor` sin query abre la historia de operación, no la ventana cruda. | Que la pestaña `current` salga seleccionada por defecto. | §3.3; `auto-monitor-page.test.tsx` (test «por defecto abre Operación»). |
| **6** | **La selección sobrevive en la URL.** `cycle`/`day`/`window`/`symbol`/`view` se leen de la query y se escriben al cambiar. | Que un selector ignore la query o no la actualice. | §3.3; `auto-monitor-page.test.tsx` (`cycle`/`window`), `dia-d-auto-*` (día/ventana/símbolo). |
| **7** | **`Δ AUTO decision/execution motor = 0`.** Ningún fichero de motor cambia; sólo el view-model `@bolsa/shared` y la UI. | Que `git diff` del motor no esté vacío. | §2 (`git diff` sin ficheros de motor; contrato HTTP sin cambio). |
| **8** | **Sin cambio de contrato HTTP.** `openapi.json`/`schema.d.ts` no se mueven. | Que `contract:check` no coincida. | §2 (`contract:check OK`). |

---

## 2. Verificación (gates)

| Gate | Resultado |
| --- | --- |
| `pytest packages/py/application/tests/test_auto_operational_monitor.py apps/api-python/tests/test_dia_d_bump_guard.py` | **53 passed** |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** (`659` ficheros) |
| `mypy` (gate CI: `domain/market/infrastructure/application/src` + `api-python/src`, `--follow-imports=silent`) | **Success: no issues found in 531 source files** |
| Web `vitest` (suite completa) | **1385 passed** (`241` ficheros) |
| Web `vitest` (`src/features/auto-monitor` + `measurement-value`) | **40 passed** (`8` ficheros; `measurement-value` `8`, story panel `4`, page `6`, monitor `11`, …) |
| `@bolsa/web` `typecheck` (`tsc -b --noEmit`) | limpio |
| `@bolsa/web` `lint` | **0 errores** (`24` warnings pre-existentes) |
| `@bolsa/web` `contract:check` | **OK** — `openapi.json`/`schema.d.ts` coinciden |
| `@bolsa/shared` `vitest` | **808 passed | 1 todo** (`97` ficheros) |
| `@bolsa/shared` build | limpio |
| Guard de versión | `test_dia_d_bump_guard.py` verde ⇒ `meta.bump` de `v2_89`…`v2_97` == `package.json` (`2.11.52-beta`) |

> **Nota de método (auditable).** El único rojo de la sesión fue un `navigate` **sin usar** en `auto-operation-story-panel.tsx` (`tsc`/`eslint` lo detectaron): se eliminó el hook sobrante, no se relajó ninguna regla. Tras el fix, `typecheck` y `lint` quedan limpios.

---

## 3. El refactor, en detalle

### 3.1 View-model semántico — `packages/shared/src/cognitive/auto-operation-story.ts`

Orden canónico de **14 etapas** (`AUTO_OPERATION_STORY_ORDER`): `OPPORTUNITY → SIGNAL → SELECTION → DECISION → RISK → RESERVATION → ORDER → FILL → POSITION → PROTECTION → EXIT → SETTLEMENT → RESULT → EXPLANATION`. Cada etapa declara `kind` (`FACT`/`DERIVED`/`CONTEXT`/`EXPLANATION`) y `group` (`OPERATION`/`CONTEXT`).

- **`SELECTION`** ← paso durable `TOP_N` («Selección · TOP-N»). **`DECISION`** pasa a `sourceStepId: null`, `NOT_MEASURED`, `derivedNote` «no hay traza durable de decisión de cartera» — resuelve `TOP_N ≠ DECISIÓN`.
- **`EXIT`** es `kind: "DERIVED"`, `sourceStepId: "SETTLEMENT"`, con `derivedNote` «salida = intención/motivo; el hecho durable es la liquidación». **`SETTLEMENT`** sigue `kind: "FACT"` — resuelve `SALIDA ≠ LIQUIDACIÓN`.
- **`OPPORTUNITY`** sale del array de hechos (`kind`/`group` `CONTEXT`) y aparece en el nuevo bloque **`context`** (`AutoOperationStoryContextItem[]`): instrumento/estrategia/dirección desde el DTO; **universo PIT / régimen / ranking** declarados `NO MEDIDO` (no se materializan por ciclo).
- Los hechos viajan **CRUDOS** (`AutoOperationStoryFact.value: unknown` + `measurement`); el formateo honesto se centraliza en la UI. La regla `UNKNOWN ≠ 0` se mantiene (un `null` con `COMPLETE` **degrada** a `NO MEDIDO`).

### 3.2 `MeasurementValue` unificado — `apps/web/src/components/measurement-value.tsx`

- `MeasurementValue({ value, measurement, incomplete, formatValue })`: delega el formateo en `formatMonitorFactValue`/`formatMeasurementLabel` de `@bolsa/shared`. Sin valor ⇒ rotula la medición (y **degrada** `COMPLETE` sin muestra a `NO MEDIDO`); con valor y medición ≠ `COMPLETE` ⇒ **anota** `valor · PARCIAL`; con `incomplete="withhold"` ⇒ **retiene** la cifra (sólo la medición).
- `MeasurementBadge({ measurement })`: sólo la medición, para badges de cabecera/paso.
- Refactor de `auto-cycle-timeline.tsx` (PnL `withhold` + hechos + badge de paso), `auto-reservation-panel.tsx`, `auto-concurrency-panel.tsx` (métrica + último conflicto) y `auto-operation-story-panel.tsx`. **Esto hace el bug del PnL de `v2.88.50` imposible por accidente.**

### 3.3 Operación por defecto + selección en URL

- `auto-monitor-page.tsx`: `useSearchParams`; `readAutoMonitorMode` **cae a `operation`** con `mode` ausente/inválido; el hook pasa a `enabled: mode !== "dia-d"` (Operación y Ventana actual necesitan el monitor vivo; DÍA-D no sondea).
- El selector de ciclo del story panel escribe `cycle` en la URL; `dia-d-auto-toolbar.tsx` escribe `mode`; `dia-d-auto-panel.tsx` lee/escribe `view` y `day`; `dia-d-auto-feedback-panel.tsx` lee/escribe `window` y **preselecciona** `symbol` (resalta la fila del instrumento).

### 3.4 Enlace EXPLICACIÓN → DÍA-D

- En la etapa `EXPLANATION` del story panel, botón «Ver heatmap de {symbol}» que navega a `?mode=dia-d&view=feedback&window=<latest>&symbol=<symbol>` (un clic en vez de tres saltos).

---

## 4. Límites declarados (NO se cierran aquí)

- **No** se reestructura la navegación global (`OPERAR · CARTERA · RIESGO · ANÁLISIS · SISTEMA`): queda documentada en el spec como objetivo post-1.0.
- **No** se borra ninguna pantalla; el refactor es **aditivo** (los paneles expertos siguen como detalle).
- **No** se introducen estados `STALE`/`BLOCKED`: el DTO de ciclo no los produce hoy (no se inventan).
- **No** se toca el motor ni el contrato HTTP: `Δ AUTO decision/execution motor = 0`, sin migración, `contract:check` OK.
- **No** se re-mide `DÍA-D`: las cifras OOS se **heredan** de `v2.88.51`/`v2.88.50`.
- **PIT histórico institucional** (P3) y los `23 orden_creada_sin_fill` (futura Execution Analysis) siguen **abiertos**; `CONFIRMED` **NO** se emite.

---

## 5. Cómo se reproduce

```bash
# 1) Guards backend (53 passed; incluye el guard de versión).
uv run --no-sync python -m pytest \
  packages/py/application/tests/test_auto_operational_monitor.py \
  apps/api-python/tests/test_dia_d_bump_guard.py -q

# 2) Gates estáticos.
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync lint-imports --config packages/py/.importlinter
uv run --no-sync mypy packages/py/domain/src packages/py/market/src \
  packages/py/infrastructure/src packages/py/application/src \
  apps/api-python/src --follow-imports=silent

# 3) UI.
pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web contract:check
```

**No** se reproduce el pipeline `DÍA-D` en este sello (declarado): las cifras OOS se **citan** de `v2.88.50`/`v2.88.51`.

---

## 6. Sello

- **Añadidos:** `apps/web/src/components/measurement-value.tsx`, `apps/web/src/components/measurement-value.test.tsx`, `docs/engineering/evidence/v2.88.52/README.md`, `docs/engineering/entrega-auditoria-externa-mia-v2.88.52-2026-10-05.md`.
- **Modificados:** `packages/shared/src/cognitive/auto-operation-story.ts` (+ test), `apps/web/src/features/auto-monitor/{auto-operation-story-panel,auto-cycle-timeline,auto-reservation-panel,auto-concurrency-panel,auto-monitor-page,dia-d-auto-panel,dia-d-auto-feedback-panel}.tsx` (+ tests), `package.json` (`2.11.52-beta`), `v2_89`…`v2_97` (`meta.bump`), `CHANGELOG.md`, `docs/CURRENT_SYSTEM.md`, `docs/engineering/versioning.md`, `scripts/lib/window-forward.mjs` (re-anclaje del freeze).
- **`Δ AUTO decision/execution motor = 0`:** ningún fichero de motor tocado; el cambio vive en un view-model puro (`@bolsa/shared`) y en la UI; el contrato HTTP no se mueve.
- **Tag:** `v2.88.52-beta` (anotado) → **cita POST-TAG** del `Release tag CI` en §7 (escrita en `main` **después** del tag) y en el `GitHub Release`. (`Release tag CI` **sólo** corre al empujar el tag ⇒ **ningún tag contiene su propio resultado de CI**; límite estructural declarado.)
- **Entrega a auditoría externa (MIA):** [`docs/engineering/entrega-auditoria-externa-mia-v2.88.52-2026-10-05.md`](../../entrega-auditoria-externa-mia-v2.88.52-2026-10-05.md) — pack autocontenido (§7 = guion de auditoría desde GitHub: tag → evidencia → `Release` → reproducción).

---

## 7. Cita del CI (POST-TAG)

> **`Release tag CI` **VERDE** — run [`37319677455`](https://github.com/jvelasca/Bolsa_V1/actions/runs/37319677455)** (`ref=refs/tags/v2.88.52-beta` → commit `2fccbf538a187159a04eb2b25779517d3d988b32`, `attempt 1`, `2026-10-05T13:48:37Z → 13:56:53Z`).
>
> - **`12` jobs: `11` `success` + `1` `skipped`** por diseño (`playwright (integrated E2E, opt-in)`); **`certify (aggregate + artifact)` `success`**.
> - `python (ruff/imports/mypy/pytest offline)` — **`4538 passed, 45 skipped, 7 warnings in 80.85 s`** (`ruff` `All checks passed!`).
> - `lifecycle-pg (Alembic + auth + golden restart)` — `success`; **`Pytest Golden Day 2.0 (proceso scheduler V2 + PG, fail if skipped)` → `2 passed in 20.23 s`** (el paso que cayó en `v2.88.50`).
> - `frontend (typecheck/lint/test/build + contract:check)` — **`241` ficheros / `1385 passed`**.
> - `shared (build/typecheck/test)` — `success`.
> - **`replay-repro (regenera el artefacto del sello desde el fixture)` → `REPRODUCIDO`**: `sha256 LF 1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7` (`3 340 728 B` LF; sello `3 445 622 B` CRLF, **mismo CONTENIDO**), 2ª corrida **`IDÉNTICA (el runner es determinista consigo mismo)`** ⇒ **`Δ motor = 0` CONFIRMADO POR CI**.
> - **`GitHub Release` `v2.88.52-beta` publicado** (pre-release): [`releases/tag/v2.88.52-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v2.88.52-beta).
>
> Comprobación directa: `gh run view 37319677455` → `Release tag CI | completed | success`; `gh run view --job 111795245965 --log` → `VEREDICTO REPRODUCIDO`.
