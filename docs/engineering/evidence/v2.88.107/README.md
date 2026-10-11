# Evidencia — `v2.88.107-beta` / **AUTO·H1**: identidad exacta de la estrategia ejecutada por ciclo (`presetKey`)

> **Base funcional:** `v2.88.106-beta` (commit `2070dd47`). Planeado como `strategyDefinitionId`; ejecutado con la clave **`preset_key`** (pivote declarado en el plan y en `PROJECT_STATE`).
> **Naturaleza:** `Δ motor ≠ 0` **aditivo** · `Δ decisión = 0` · **SIN migración** (head `052_top3_opportunities`) · **Contrato ampliado** (campo nullable, `contract:gen`).

---

## 1. Qué cierra

Cada ciclo del motor AUTO publica ahora la **identidad exacta** de la estrategia que lo generó — el **`presetKey`** que el motor sí conoce — y la UI compara esa identidad por **igualdad exacta** contra el TOP #1 de Finalistas, eliminando la heurística por token. Un hueco se declara «Sin dato todavía»; nunca se rellena (`UNKNOWN ≠ 0`).

## 2. Pivote: por qué `preset_key` y no `strategyDefinitionId`

`strategyDefinitionId` **no existe en el origen del motor**: los productores de candidatas del lifecycle trabajan con `preset_key`/familia/params, y el `strategyDefinitionId` del TOP lo **deriva la UI** del `presetKey` del slot (`coach-top-save.ts:64-84` → `createFromPreset`). El único espacio de claves compartido es **`presetKey` ≡ `strategyType` del slot**. Ver el pivote completo en el [plan](../../plan-v2-88-107-h1-identidad-estrategia-2026-10-11.md).

## 3. Cambios por fase (estado de ejecución)

### Dominio (candidate → finalista → activa)

- `StrategyFinalist` y `ActiveStrategy` ganan `preset_key: str | None = None` ([`strategy_lifecycle.py`](../../../../packages/py/domain/src/bolsa_domain/entities/strategy_lifecycle.py)).
- `build_strategy_version()` propaga `candidate.preset_key` ([`strategy_promotion_phase.py`](../../../../packages/py/application/src/bolsa_application/strategy_promotion_phase.py)).
- `AutoOrchestrator` hereda `finalist.preset_key` en la `ActiveStrategy` ([`auto_orchestrator.py`](../../../../packages/py/application/src/bolsa_application/auto_orchestrator.py)).
- **Productores de origen:** NO se tocan (no tienen el dato ⇒ hueco declarado; `strategy_lab_phase`/`auto_orchestrator`/`strategy_discovery_engine`).

### Transporte y sellado (sin migración)

- Fuente canónica **única** ([`decision_contract.py`](../../../../packages/py/application/src/bolsa_application/decision_contract.py)): `format_active_strategy_source(version_id, preset_key)` → `active-strategy:<version>` o `active-strategy:<version>::<presetKey>`. La usan **ambos** decisores ([`auto_orchestrator.py`](../../../../packages/py/application/src/bolsa_application/auto_orchestrator.py), [`active_strategy_signal_evaluator.py`](../../../../packages/py/application/src/bolsa_application/active_strategy_signal_evaluator.py)).
- Reducción en el worker ([`auto_simulation_worker.py`](../../../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py)): `_strategy_version_from_source` recorta el sufijo `::` (retrocompatible) y `_strategy_preset_from_source` lo extrae.
- Sello durable **aditivo** ([`auto_v2_entry.py`](../../../../packages/py/application/src/bolsa_application/auto_v2_entry.py)): `V2Signal.strategy_preset_key` → `payload.strategyPresetKey` (clave **omitida** si no hay dato).

### Store del lifecycle (sin migración)

- [`strategy_lifecycle_store.py`](../../../../packages/py/application/src/bolsa_application/strategy_lifecycle_store.py) — `get_active` **resuelve** el `preset_key` desde la **candidata de origen** (`strategy_candidates.preset_key`, ya durable), sin tocar `definition` ni el hash inmutable. Sin candidato/preset ⇒ `None`.

### Monitor DTO + contrato

- Read model ([`auto_operational_monitor.py`](../../../../packages/py/application/src/bolsa_application/auto_operational_monitor.py)): `strategyPresetKey` por ciclo (desde el journal) + hecho aditivo en el paso `SIGNAL`.
- DTO API ([`auto_operational_monitor.py`](../../../../apps/api-python/src/bolsa_api/api/v1/routes/auto_operational_monitor.py)): `strategyPresetKey` nullable.
- `shared` ([`auto-operational-monitor.ts`](../../../../packages/shared/src/cognitive/auto-operational-monitor.ts)) + `contract:gen` (`openapi.json` + `schema.d.ts`).

### UI (identidad exacta)

- [`auto-operation-strategy.ts`](../../../../apps/web/src/features/auto/auto-operation-strategy.ts) — `resolveAutoOperationStrategyMatch` compara **exactamente** `presetKey` contra `{slot.strategyType, definition.presetKey}`; `same`/`differs`/`unknown`. Se retira `AUTO_OPERATION_STRATEGY_MATCH_IS_HEURISTIC` → `AUTO_OPERATION_STRATEGY_MATCH_IS_EXACT`. El CTA DÍA-D **no** depende del match.
- **Honestidad del tri-estado:** si el #1 **no declara** ninguna identidad (`strategyType` y `definition.presetKey` ambos ausentes) la comparación es `unknown` («Sin dato todavía»), **nunca** `differs`: sin término de comparación no se afirma divergencia (`UNKNOWN ≠ 0`, §5.1.4).
- [`use-auto-operation-strategy.ts`](../../../../apps/web/src/features/auto/use-auto-operation-strategy.ts), [`auto-operation-strategy-card.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx), [`auto-operation-story-panel.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx).

## 4. Verificación (local)

- **Python:** `ruff check packages/py apps/api-python --config pyproject.toml` → **All checks passed** · `lint-imports` → **4 kept, 0 broken** · `mypy` (scope CI) → **544 files, no issues**.
- **Pytest dirigido + PG real:** `test_strategy_lifecycle_pg.py` **6 passed** (incluye round-trip `get_active` con `preset_key`), batería de `worker`/`auto_v2_entry`/`monitor`/`orchestrator`/`promotion`/`evaluator`/`decision_contract` → **244 passed**.
- **Integración «motor real» (criterio 5):** `test_auto_v2_worker_integration.py` gana 2 pruebas que corren **el worker** (`auto_turn`) desde un `DecisionPackage` real (no un ciclo sembrado) y afirman que el `presetKey` de `source` aterriza en el payload durable de la decisión aprobada (`strategyPresetKey`) y que la versión queda recortada (`ver-abc`, sin `::<preset>`); control negativo: sin sufijo la clave se **omite**. **41 passed** (archivo completo).
- **Guardián de bump:** `test_dia_d_bump_guard.py` **1 passed** (`package.json` y los 9 CLIs DÍA-D sellan `2.11.107-beta`).
- **Web:** `contract:gen` + `contract:check` **OK** · `typecheck`/`lint`/`build` **OK** · `vitest` **2 080 passed**.

## 5. Límites declarados (sin fabricar)

- **Sin migración:** head de Alembic sigue `052_top3_opportunities`. La identidad viaja en JSONB (journal) y en `strategy_candidates.preset_key`.
- **Cobertura honesta:** las candidatas nacidas de familia+params **sin** preset siguen declarando «Sin dato todavía»; H1 mejora la **trazabilidad**, no promete el 100 % de los ciclos.
- **`Δ decisión = 0`:** no se tocan umbrales, reparto, `TOP_N`/régimen/selección/protección. La autoridad del `Δ motor` aditivo y del no-cambio de decisión es el CI del tag (`replay-repro`).
- **Tag `unsigned`** (limitación de certificación, no defecto).

## 6. Correspondencia con los criterios de aceptación del acta

| # | Criterio | Estado | Dónde comprobarlo |
| - | -------- | ------ | ----------------- |
| 1 | **Identidad exacta** conservada de la candidata al ciclo | **CUBIERTO** (con pivote a `presetKey`) | §2 y §3: `preset_key` en finalista/activa → `format_active_strategy_source` → `_strategy_preset_from_source` → `payload.strategyPresetKey`. Los **productores de origen no se tocan** (hueco declarado, no rellenado). |
| 2 | **Migración/persistencia** sin fabricar valores antiguos | **CUBIERTO — SIN migración** | Head `052`; identidad en JSONB y en `strategy_candidates.preset_key`; contrato nullable; operaciones antiguas **omiten** la clave. |
| 3 | **UI** distingue ejecutada vs mejor actual y declara «Sin dato todavía» | **CUBIERTO** | §3 UI + tri-estado `unknown` (incluso con #1 sin identidad). |
| 4 | **DÍA-D** enlaza instrumento + estrategia correctos | **CUBIERTO** | El CTA de verificación no depende del match y la vista separa bloques «mejor disponible» vs «ejecutada». |
| 5 | **Motor real**: prueba integrada genera la operación por el worker | **CUBIERTO** | §4: 2 pruebas en `test_auto_v2_worker_integration.py` corren `auto_turn` con decider real. |
| 6 | **Seguridad SIM** intacta | **SIN CAMBIO** | No se toca `ALLOWED_AUTO_VENUES` ni el gate de venue; `Δ decisión = 0`. |
| 7 | **Validación por valor** (resultados reproducibles OOS) | **FUERA DE ALCANCE de H1** | Track separado; H1 es trazabilidad, no calidad de señal. |
