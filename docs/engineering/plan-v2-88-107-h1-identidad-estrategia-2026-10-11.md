# Plan — `v2.88.107-beta` / **AUTO·H1**: identidad exacta de la estrategia ejecutada por ciclo (`strategyDefinitionId`)

> **Estado:** **PROPUESTO** (2026-10-11) — no ejecutado. Requiere aprobación del propietario antes de tocar código (premisa E1).
> **Base funcional:** `v2.88.106-beta` (tag anotado `v2.88.106-beta`, commit `2070dd47`). HEAD del árbol al redactar: `65d45404`.
> **Naturaleza prevista:** `Δ motor ≠ 0` **aditivo** · `Δ decisión = 0` · **Migración Alembic `053`** · **Contrato ampliado** (`contract:gen`).
> **Origen:** hallazgo `H1` (identidad exacta de estrategia) de la auditoría externa, profundizado en [`auditoria-profundizada-auto-h1-sim-dia-d-2026-10-11.md`](./auditoria-profundizada-auto-h1-sim-dia-d-2026-10-11.md) §3.1/§5, y en el gate [`gate-f0-identidad-estrategia-y-pnl-realizado-2026-10-10.md`](./gate-f0-identidad-estrategia-y-pnl-realizado-2026-10-10.md).
> **Decisión de diseño ratificada:** la clave de unión canónica es el **`strategyDefinitionId`** (identidad de definición de estrategia), hilvanada `candidata → versión → activa → ciclo` y comparada por **igualdad exacta** con el slot #1 del TOP de Finalistas. Se elimina la heurística por token.

---

## 0. Objetivo

Cerrar `H1`: que **cada ciclo** del motor AUTO conserve y presente la identidad **exacta** (`strategyDefinitionId`) de la estrategia que generó la señal, de modo que la comparación «estrategia ejecutada ↔ mejor estrategia del valor (TOP #1)» sea una **igualdad por id**, no una aproximación textual.

**Criterio de aceptación (falsable).** Para un ciclo con identidad disponible:

- `cycle.strategyDefinitionId == top1.strategyDefinitionId` se **afirma** (`same`) o se **niega** (`differs`) por igualdad exacta de cadena.
- Sin `strategyDefinitionId` (ciclo sin definición enlazable) ⇒ `unknown` declarado como «Sin dato todavía». **Nunca** se colapsa a un valor de relleno (`UNKNOWN ≠ 0`, §5.1.4 de premisas).
- La función heurística `resolveAutoOperationStrategyMatch` **desaparece** del código.

---

## 1. Precedente y reutilización (no duplicar)

- **Gate F0 (2026-10-10)** ya verificó que el ciclo expone `strategyVersion` = `ActiveStrategy.version_id` y **no** el `strategyDefinitionId` del slot del TOP; concluyó que la igualdad exacta **exige motor** y que `F3` se resolvía **UI-only** (separar y declarar el gap).
- **`F3` (`v2.88.105`)** separó en superficie «Mejor estrategia del valor (Finalistas TOP #1)» de «Estrategia ejecutada declarada por el ciclo» y declaró la coincidencia como heurística ([`auto-operation-strategy.ts:56-63`](../../apps/web/src/features/auto/auto-operation-strategy.ts)). Este plan materializa lo que allí se declaró pendiente.
- **ADR-044/045:** AUTO compone superficies por enlace; no reimplementa. Este plan **no** añade una superficie nueva: rellena el dato que falta y refina la comparación existente.
- **La alternativa `templateId`** (presente en el `trade_plan_snapshot` vía [`execution_router.py:94-140`](../../packages/py/application/src/bolsa_application/execution_router.py) y [`auto_v2_entry.py:1647`](../../packages/py/application/src/bolsa_application/auto_v2_entry.py)) queda **descartada como clave primaria** por decisión del propietario; se puede citar como identidad secundaria declarada, nunca como sustituto.

### 1.1 Hallazgo crítico verificado (riesgo de origen)

Los candidatos del lifecycle **no rellenan** `strategy_definition_id` en la ruta de producción:

- [`strategy_lab_phase.py:109-117`](../../packages/py/application/src/bolsa_application/strategy_lab_phase.py) — `StrategyCandidate(origin="estudio", preset_key=…)` sin `strategy_definition_id`.
- [`auto_orchestrator.py:255-261`](../../packages/py/application/src/bolsa_application/auto_orchestrator.py) — candidata directa sin `strategy_definition_id`.
- [`strategy_discovery_engine.py:255-264, 384, 563`](../../packages/py/application/src/bolsa_application/strategy_discovery_engine.py) — candidatas `origin="discovery"` con `preset_key`, sin `strategy_definition_id`.

El único punto que **persiste/lee** el campo es el store ([`strategy_lifecycle_store.py:278,889`](../../packages/py/application/src/bolsa_application/strategy_lifecycle_store.py)): si la candidata no lo trae, se guarda `None`.

**Consecuencia:** si no se **puebla en el origen**, el ciclo sellará `None` y la UI declarará «Sin dato todavía» para la mayoría de operaciones AUTO. Por eso la **Fase 1 es la crítica** y decide el éxito real de H1, no solo la migración.

---

## 2. Diseño por fases

### Fase 0 — Migración Alembic `053_strategy_version_definition_id`

- Nueva revisión `053_strategy_version_definition_id`, `down_revision = "052_top3_opportunities"` (head actual: [`versions/052_top3_opportunities.py`](../../packages/py/infrastructure/alembic/versions/052_top3_opportunities.py)).
- Columna **nullable** `strategy_definition_id` en `strategy_versions` ([`tables.py:2412-2430`](../../packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py)).
- Guardas idempotentes `_column_exists`/`_table_exists` (patrón de [`030_strategy_lifecycle.py`](../../packages/py/infrastructure/alembic/versions/030_strategy_lifecycle.py)).
- **Sin backfill**: los ciclos/versiones previos quedan `None` ⇒ «Sin dato todavía» (nunca se fabrica).
- **Test:** `upgrade`/`downgrade` sobre DB limpia y sobre DB existente; columna nullable y ausente en el `downgrade`.

### Fase 1 — Dominio y poblado del id en el origen (crítico)

- `StrategyFinalist` ([`strategy_lifecycle.py:182-190`](../../packages/py/domain/src/bolsa_domain/entities/strategy_lifecycle.py)) y `ActiveStrategy` ([`strategy_lifecycle.py:484-494`](../../packages/py/domain/src/bolsa_domain/entities/strategy_lifecycle.py)) ganan `strategy_definition_id: str | None = None`.
- `build_strategy_version()` propaga `candidate.strategy_definition_id` ([`strategy_promotion_phase.py:51-75`](../../packages/py/application/src/bolsa_application/strategy_promotion_phase.py)).
- **Poblar el campo donde la definición es conocida** (el corazón de H1):
  - `strategy_lab_phase.py` / `auto_orchestrator.py` / `strategy_discovery_engine.py`: sellar el `strategy_definition_id` de la definición de estrategia que origina la candidata cuando exista (el mismo id que consumen `strategies`/`research_trials`/`backtests`, ver `strategy_definition_id=` en [`research_trials.py:47`](../../packages/py/application/src/bolsa_application/research_trials.py), [`backtests.py:272,298`](../../packages/py/application/src/bolsa_application/backtests.py)).
  - Si la candidata nace de una familia+params sin definición de estrategia asociada **no se inventa**: `None` (hueco declarado).
- **Test de dominio:** candidata con id ⇒ finalista/activa con el mismo id; candidata sin id ⇒ `None` (no se propaga cadena vacía ni valor sintético).

### Fase 2 — Store del lifecycle

- `save_finalist` escribe la columna ([`strategy_lifecycle_store.py:382-390`](../../packages/py/application/src/bolsa_application/strategy_lifecycle_store.py)).
- `get_active` la reconstruye en `ActiveStrategy` ([`strategy_lifecycle_store.py:659-698`](../../packages/py/application/src/bolsa_application/strategy_lifecycle_store.py)).
- Espejo **InMemory** (mismo contrato): [`strategy_lifecycle_store.py:140,155`](../../packages/py/application/src/bolsa_application/strategy_lifecycle_store.py).
- **Test PG:** round-trip `save_finalist` → `get_active` conserva el id; una fila antigua (sin valor) ⇒ `None`.

### Fase 3 — Motor: sellar `strategyDefinitionId` por ciclo (aditivo, `Δ decisión = 0`)

- Publicar el id de la activa **junto a la versión** en el origen del paquete:
  - `DecisionProvider` de la activa: [`active_strategy_signal_evaluator.py:126-128`](../../packages/py/application/src/bolsa_application/active_strategy_signal_evaluator.py) (`source = f"active-strategy:{version_id}"`).
  - Decider directo: [`auto_orchestrator.py:765`](../../packages/py/application/src/bolsa_application/auto_orchestrator.py).
  - Reducción en el worker: [`auto_simulation_worker.py:527-540`](../../apps/api-python/src/bolsa_api/background/auto_simulation_worker.py) (`_strategy_version_from_source`) — extender para extraer también el id, o sellarlo en el payload del paquete.
- Sellarlo **durable** en el mismo punto que la versión:
  - Reserva: [`auto_v2_entry.py:2038`](../../packages/py/application/src/bolsa_application/auto_v2_entry.py) (+ columna nueva en `portfolio_reservations`, o solo en el payload JSONB — decisión de Fase 0).
  - Decisión de entrada: [`auto_v2_entry.py:2334-2335`](../../packages/py/application/src/bolsa_application/auto_v2_entry.py).
  - Posición materializada: [`auto_operational_audit.py:434`](../../packages/py/application/src/bolsa_application/auto_operational_audit.py).
  - Régimen del ciclo: [`auto_cycle_journal.py:107`](../../packages/py/application/src/bolsa_application/auto_cycle_journal.py).
- **Regla dura:** si no hay id, la clave **se omite** (no se sella cadena vacía), igual que hoy hace `strategyVersion`.
- **Test:** un ciclo con estrategia identificable sella el id; sin él, el campo no aparece (mirada negativa).

### Fase 4 — Monitor DTO

- Exponer `strategyDefinitionId` en el ciclo/señal junto a `strategyVersion` ([`auto_operational_monitor.py:276,395-396,875`](../../packages/py/application/src/bolsa_application/auto_operational_monitor.py)), con la política de huecos (`UNKNOWN ≠ 0`).
- **Test:** el DTO distingue «no medido» de «medido sin estrategia».

### Fase 5 — Contrato + `shared`

- Ampliar el tipo `cycle.strategyVersion` con `strategyDefinitionId` en [`auto-operational-monitor.ts:153`](../../packages/shared/src/cognitive/auto-operational-monitor.ts) y el schema OpenAPI del monitor.
- `contract:gen` (regenera `openapi.json` + `schema.d.ts`) y `contract:check` verde.

### Fase 6 — UI: identidad exacta (sustituye la heurística)

- Sustituir `resolveAutoOperationStrategyMatch` por comparación **exacta** de `strategyDefinitionId` en [`auto-operation-strategy.ts:145-177`](../../apps/web/src/features/auto/auto-operation-strategy.ts) y [`use-auto-operation-strategy.ts`](../../apps/web/src/features/auto/use-auto-operation-strategy.ts).
- Retirar el rótulo de heurística ([`auto-operation-strategy.ts:56-63`](../../apps/web/src/features/auto/auto-operation-strategy.ts)); mantener el tri-estado `same`/`differs`/`unknown` y la tarjeta [`auto-operation-strategy-card.tsx`](../../apps/web/src/features/auto-monitor/auto-operation-strategy-card.tsx).
- **Tests vitest:** `same` por id igual, `differs` por id distinto, `unknown` por hueco; sin rastro de tokenización.

---

## 3. Afirmaciones falsables

1. **Migración reversible:** `alembic upgrade head` / `downgrade` desde DB limpia y existente; `strategy_versions.strategy_definition_id` nullable.
2. **Propagación con hueco honesto:** candidata↔versión↔activa conservan el id; sin id ⇒ `None` (nunca cadena vacía ni valor sintético).
3. **Sello por ciclo:** un ciclo con estrategia identificable publica `strategyDefinitionId`; sin ella, el campo no se emite.
4. **Igualdad exacta:** la coincidencia ejecutada↔TOP es `same`/`differs` por igualdad de cadena; **no** queda ninguna ruta de comparación por token.
5. **Ciclos históricos:** un ciclo previo a la migración declara «Sin dato todavía»; **no** se rellena.
6. **`Δ decisión = 0`:** `replay-repro` byte a byte idéntico (el cambio es aditivo y no altera umbrales/selección/reparto).
7. **Contrato coherente:** `contract:check` verde con los campos nuevos; sin breaking change (campos nullable/opcionales).

---

## 4. Sello, docs y freeze

- **Bump** `2.11.106-beta → 2.11.107-beta` en `package.json` ([`package.json`](../../package.json), hoy `2.11.106-beta`) + `meta.bump` de los 9 CLIs DÍA-D `v2_89`…`v2_97` ([`v2_89_dia_d_auto_replay.py`](../../apps/api-python/scripts/v2_89_dia_d_auto_replay.py) … [`v2_97_dia_d_thesis_exit.py`](../../apps/api-python/scripts/v2_97_dia_d_thesis_exit.py)); guardián [`test_dia_d_bump_guard.py`](../../apps/api-python/tests/test_dia_d_bump_guard.py) verde.
- `CHANGELOG.md` (entrada `2.11.107-beta`), [`versioning.md`](./versioning.md), [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) si aplica.
- **Nueva evidencia** `docs/engineering/evidence/v2.88.107/README.md` y este plan en `docs/engineering/plan-v2-88-107-h1-identidad-estrategia-2026-10-11.md`.
- **Re-anclaje del freeze** en `scripts/lib/window-forward.mjs` (`WINDOW_CONFIG`) al commit funcional si el árbol se mueve; dry-run `freeze OK`.
- Tag anotado `v2.88.107-beta` + push + cita del `Release tag CI` (POST-TAG).

---

## 5. Verificación y gates

- **Python:** `ruff check packages/py apps/api-python --config pyproject.toml` (0) · `lint-imports` (4 kept, 0 broken) · `mypy` (scope CI) · `pytest` de la zona + dirigidos nuevos.
- **Migración:** `alembic upgrade head` / `downgrade` (limpieza y upgrade sobre DB existente); test de la tabla `strategy_versions`.
- **Web:** `tsc -b --noEmit` · `eslint src` (0 errores) · `vitest` (identidad exacta + regresiones de la tarjeta) · `build`.
- **Contrato:** `contract:gen` + `contract:check`.
- **Δ decisión = 0:** `replay-repro` `REPRODUCIDO` con la huella de motor esperada (o `Δ motor ≠ 0` aditivo **confirmado por CI**, como en `v2.88.105`).
- **Smoke real:** `seed_auto_cycle_for_ui.py` (que ya sella `strategyVersion`) extendido para sellar el `strategyDefinitionId` real de la estrategia sembrada; verificar en navegador que la tarjeta declara `same`/`differs` por id y que sin id declara «Sin dato todavía».

---

## 6. Límites declarados (sin fabricar)

- **Ciclos históricos y candidatas sin definición** quedan en «Sin dato todavía»; el plan **no** promete cerrar el 100 % de las operaciones, solo eliminar la heurística y sellar el id cuando existe.
- **Dependencia de la Fase 1:** si la ruta de producción de candidatas no conoce una definición de estrategia, H1 seguirá declarando el hueco de forma honesta (mejora de trazabilidad, no de cobertura).
- **`Δ decisión = 0`:** no se tocan umbrales, reparto, `TOP_N`/régimen/selección/protección. El cambio es aditivo (nuevos campos nullable).
- **`templateId`** queda como identidad secundaria declarada, **no** como clave primaria.
- **Tag `unsigned`** (limitación de certificación, no defecto).
- Este plan **no** cierra el «bucle con motor real» (§6 de la auditoría) ni la validación OOS (§8): son fases posteriores.

---

## 7. Fuera de alcance (deliberado)

- **No** se implementa aquí: bucle diario con el worker real, endurecimiento runtime del blindaje SIM, validación OOS por valor.
- **No** se refactoriza la superficie de Finalistas ni el motor de decisión.
- **No** se resuelve el mapeo histórico retroactivo (no hay backfill).

---

_Plan de fase (premisa E1): no se ejecuta hasta aprobación del propietario. Toda afirmación `file:line` es verificable en el árbol de `v2.88.106-beta`._
