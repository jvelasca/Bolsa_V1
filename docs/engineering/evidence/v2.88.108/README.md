# Evidencia — `v2.88.108-beta` / **REMEDIACIÓN `H1`**: la identidad de estrategia no se fabrica + durabilidad real del sello (`presetKey`)

> **Base funcional:** `v2.88.107-beta` (commit `756d4e44`). Remedia los dos hallazgos de la verificación independiente de esa versión.
> **Naturaleza:** `Δ motor ≠ 0` **aditivo** · `Δ decisión = 0` · **SIN migración** (head `052_top3_opportunities`) · **contrato SIN cambio** (`contract:check` verde).

---

## 1. Qué cierra

Dos afirmaciones de `v2.88.107-beta` eran más fuertes de lo que el código sostenía:

1. **La identidad se fabricaba en discovery.** Dos productores sustituían un `presetKey` ausente por el **nombre de familia**, en contradicción con la doctrina «identidad exacta cuando existe, hueco declarado cuando no existe».
2. **La "prueba de durabilidad" era en memoria.** El test del worker real afirmaba contra `worker._v2_journal` (lista RAM), no contra PostgreSQL.

## 2. `H1-a` — la identidad NO se fabrica (discovery)

En [`strategy_discovery_engine.py`](../../../../packages/py/application/src/bolsa_application/strategy_discovery_engine.py) los dos productores hacían:

```python
# ANTES (carril catálogo, ~262)
preset_key=str(executable.get("presetKey") or family.name)
# ANTES (carril adaptativo, ~409)
preset_key=str(executable.get("presetKey") or adaptive_family.name)
```

Ahora ambos usan un helper puro que **declara el hueco**:

```python
def _preset_key_of(definition: Mapping[str, Any] | None) -> str | None:
    """Identidad EXACTA (``presetKey``); ``None`` si la definición no la declara."""
    if not definition:
        return None
    key = definition.get("presetKey")
    return str(key) if key else None
```

- **Sin cambio en producción:** el catálogo curado (14 familias) siempre declara `presetKey` e **igual a `family.name`**, así que el valor emitido es idéntico. El fallback solo se disparaba en plantillas personalizadas sin `presetKey` (hoy, ninguna prueba).
- **Efecto:** esos casos pasan de identidad **fabricada** a `None` ⇒ `format_active_strategy_source` sin sufijo ⇒ `strategyPresetKey` omitido ⇒ UI `unknown` («Sin dato todavía»). Elimina un posible **falso `same`**.

### Auditoría del mismo patrón (sin cambio, registrado)

- [`optimization_runs.py:328`](../../../../packages/py/application/src/bolsa_application/optimization_runs.py) — `preset_key=family` con `family = result.strategy_family or STRATEGY_FAMILY_SMA`: es la **ledger de trials del LAB**, no la identidad del ciclo AUTO (que nace de `strategy_candidates.preset_key`). Default legítimo del laboratorio.
- [`llm_draft.py:37`](../../../../packages/py/analytics/src/bolsa_analytics/research/llm_draft.py) — `preset_key = str(llm_payload.get("presetKey") or heuristic.preset_key)` con rechazo si difiere y resultado final `preset_key=heuristic.preset_key` (ruta de borrador IA). **No fabrica** identidad.

Ninguno alimenta la identidad del ciclo AUTO ⇒ no se tocan.

## 2.1. Registro de residuos (auditoría independiente de `v2.88.108-beta`)

La auditoría de esta versión (desde el tag `5fbb0e4f`) **cerró** los dos hallazgos, pero dejó constancia de **residuos que no afectan a la identidad del ciclo AUTO** y que no se declaran como fabricación. Se registran aquí para no perderlos:

1. **`optimization_runs.py:328` — acoplamiento de evidencia (no identidad).** El *shape* `preset_key=family` persiste, y **este código se ejecuta dentro de la fase LAB del orquestador AUTO** (`auto_orchestrator_worker.py` construye `RunSmaGridOptimizeAndSave`), no solo en el laboratorio aislado. Escribe `research_trials` con la **clave de evidencia por familia** que consume el carril adaptativo (`discovery_evidence.py`), por lo que puede influir en **pesos** de búsqueda — nunca en la **identidad** del ciclo. La declaración del release («capa lab») es correcta para identidad; queda **no declarado** el acoplamiento de evidencia.
2. **`research_trial_repository.py:358` — default de presentación.** `"presetKey": row.preset or "unknown"` inventa el literal `"unknown"` en el payload de observabilidad del laboratorio (endpoint read-only). Es *display*, no identidad del ciclo; el release no lo menciona.
3. **`backtests.py:299` — patrón familia/tipo-como-preset.** `preset_key=strategy_type` en la ruta manual/lab de backtest (research trial). No declarado.
4. **Invariante de catálogo no forzado.** La identidad exacta en producción se sostiene porque el catálogo curado (14 familias) declara `presetKey == family.name`; lo prueba un test (`test_catalog_preset_key_equals_declared_preset_key`), pero **no** se valida en la construcción del catálogo. Si una familia lo omitiera, el candidato degrada a `None` (hueco declarado, comportamiento correcto) ⇒ **reduce cobertura en vez de fallar**.

Ninguno de los cuatro alimenta la identidad del ciclo AUTO; el veredicto «remediación cerrada» se mantiene.

## 3. `H1-b` — durabilidad REAL del sello (PostgreSQL)

Nueva prueba en [`test_auto_v2_durable_pg.py`](../../../../apps/api-python/tests/test_auto_v2_durable_pg.py):

- **`test_auto_entry_decision_strategy_preset_key_is_durable_in_pg`** — corre el worker **REAL** (`AutoSimRuntime.run_tick` → `auto_turn`) con el sumidero M2 encendido (`AUTO_OPERATIONAL_AUDIT=1`); la identidad viaja en la fuente del `DecisionPackage` (`active-strategy:ver-abc::sma_crossover`). Lee el `auto_entry_decision` desde una **sesión NUEVA** (`decision_journal_entries.payload`, JSONB) y afirma `payload["strategyPresetKey"] == "sma_crossover"` y `payload["strategyVersion"] == "ver-abc"`.
- **Control negativo** en el mismo test (`active-strategy:ver-xyz`, sin sufijo): `"strategyPresetKey" not in payload` y `strategyVersion == "ver-xyz"` (la ausencia **no** se rellena).
- Los tests **en memoria** de [`test_auto_v2_worker_integration.py`](../../../../apps/api-python/tests/test_auto_v2_worker_integration.py) se re-documentan: afirman la **forma del payload durable** sobre el journal del turno; la **durabilidad** la cubre la prueba PG.

## 4. Pruebas de no-fabricación (discovery)

- [`test_strategy_discovery_engine.py`](../../../../packages/py/application/tests/test_strategy_discovery_engine.py) — definición **sin** `presetKey` ⇒ `candidate.preset_key is None`; definición **con** `presetKey` ⇒ identidad exacta; invariante del catálogo real: `preset_key == params["definition"]["presetKey"]`.
- [`test_discovery_search_policy.py`](../../../../packages/py/application/tests/test_discovery_search_policy.py) — identidad del carril adaptativo = `presetKey` declarado.

## 5. Verificación (local)

- **Python:** `ruff check packages/py apps/api-python --config pyproject.toml` → **All checks passed** · `lint-imports` → **4 kept, 0 broken** · `mypy` (scope CI) → **544 files, no issues**.
- **Pytest:** `packages/py/application/tests` + `packages/py/domain/tests` → **2 729 passed**.
- **Durabilidad real (PostgreSQL):** `test_auto_v2_durable_pg.py` + `test_auto_v2_worker_integration.py` → **45 passed** (incluye la nueva prueba PG y su control negativo).
- **Contrato:** `contract:gen`/`contract:check` → **OK** (sin cambio de contrato).
- **CI del tag:** `Release tag CI` [38127345052](https://github.com/jvelasca/Bolsa_V1/actions/runs/38127345052) **VERDE** — **11 jobs `success` + `certify` `success`** (`playwright (integrated E2E, opt-in)` `skipped`, esperado). `replay-repro` **REPRODUCIDO** `1E3ADAC2…929A37E7` (byte a byte idéntico al sello previo ⇒ **`Δ decisión = 0`** confirmado en CI: el `Δ motor ≠ 0` es aditivo). Tag `v2.88.108-beta` = objeto `1c97c633` → commit `5fbb0e4f` (**unsigned**).

## 6. Límites declarados (sin fabricar)

- **Sin migración:** head de Alembic sigue `052_top3_opportunities`; `strategyPresetKey` sigue en el JSONB del journal.
- **No aumenta la cobertura de identidad:** solo elimina una fabricación. Las candidatas ESTUDIO/directas (`auto_orchestrator.py:231-239`, `:254-262`) siguen sin `presetKey` y declaran «Sin dato todavía» (la cobertura es una **fase separada**).
- **Durabilidad probada del SELLO, no calidad de señal:** no valida indicadores ni rentabilidad; la validación OOS por valor sigue **fuera de alcance**.
- **`Δ decisión = 0`:** la autoridad es el `replay-repro` del CI del tag (el cambio de datos solo afecta a plantillas sin `presetKey`, inexistentes en el catálogo real ⇒ artefacto idéntico).
- **Tag `unsigned`** (limitación de certificación, no defecto).
