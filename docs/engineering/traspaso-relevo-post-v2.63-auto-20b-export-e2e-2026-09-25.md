# Traspaso / relevo — post `v2.63-beta` (`AUTO-20B` · Export E2E + oráculo same-material)

**Para el siguiente agente.** Lee esto antes de tocar nada. Fuente de verdad de la fase:
[plan](./plan-v2-63-auto-20b-export-e2e-2026-09-25.md) ·
[audit-pack](./audit-pack-v2-63-auto-20b-export-e2e-2026-09-25.md) ·
[arranque del auditor](./arranque-auditor-v2.63-auto-20b-export-e2e-2026-09-25.md).

## 1. Dónde estamos

* **`v2.63-beta` (`1.88.0-beta`)** sellada. Base de auditoría: el cierre de `v2.62-beta`.
* `AUTO-20B` cierra la **deuda nº 1** de la [auditoría de `v2.62`](./auditoria-v2-62-auto-20-material-paper-real-2026-09-24.md):
  el camino durable del exportador **ya no está verificado solo por estática** — se ejercita
  end-to-end contra PostgreSQL real con oráculo independiente y test same-material.
* El **reparto no se movió**: `auto18-v1` / `auto15-v1`; **sin migración** (head en `046_fill_reference_mid`).

## 2. Qué se hizo (y por qué)

| Pieza | Qué cambia |
|---|---|
| **Completitud del volcado** | `list_by_cycle_ids` gana `offset` (keyword-only, aditivo) en `Protocol`/InMemory/Postgres. El exportador **pagina hasta agotar** y, si una página satura sin progreso, **se bloquea con `2`** en vez de emitir un JSON sesgado. `--limit` pasa a ser **tamaño de página**. |
| **Huella del material** | Nuevo `auto_material_manifest.py` (analytics, puro): `material_fingerprint` + `MATERIAL_FINGERPRINT_METHOD = "material_fingerprint_v1"`. Determinista, orden-invariante, **sin reloj**, sensible a versión/régimen/riesgo/coste; normaliza números por VALOR, **no** identificadores. |
| **Manifest de conteos** | Nuevo `auto_material_manifest.py` (application): conteos del **MISMO** material del instrumento (`closedCycles`, `cyclesWithRisk`/`WithoutRisk`, `cyclesWithVersion`/`WithoutVersion`, `cyclesWithoutIdentity`, `costAppliedCycles`, `perVersion`, `regimeRead`, `reservationsRead`, `riskReadSaturated`, `riskBasis`) + huella. Viaja como `material_manifest` en el JSON, **nunca** dentro de `cycles`. |
| **Propagación** | `auto_replay_battery.py` lee el manifest y lo pasa como `material=` a la calibración; `CalibrationReport.as_dict()` emite la clave **solo si se aporta** (sin manifest: byte-idéntico al informe ya auditado; el sello `walk_forward_calibration_v2` **no** cambia). |
| **E2E + oráculo** | Fixture PG determinista (A 12/9/3, B 8/8, C 5/0, 1 ciclo sin versión, 2 regímenes, coste aplicado en 17 ciclos) → exportador REAL → JSON → calibración; cardinalidades contra un **oráculo independiente**, caso `--limit` pequeño (varias páginas), exit 2 en saturación, y **same-material** `build_auto_self_evaluation` vs `adaptive_instrument_cycles`. |

**Por qué el bloque `material` es opcional**: el informe es el **contrato sellado** de `AUTO-19B/20` y
un informe sin manifest no puede cambiar de forma. La huella es metadata de **entrada declarada**, no
una medición; si un futuro agente quiere que el informe **dependa** del manifest, tiene que decidirlo
explícitamente y subir el sello.

## 3. Estado medido (compuertas)

* `ruff check packages/py apps/api-python --config pyproject.toml` — **All checks passed!**
* `lint-imports --config packages/py/.importlinter` — **4 kept / 0 broken** (626 ficheros).
* `mypy … --follow-imports=silent` — **500 ficheros, 0 errores**.
* Puros `packages/py/analytics/tests` + `packages/py/application/tests` — **3147 passed**.
* E2E PG con `AUTO20B_EXPORT_PG_REQUIRED=1` — **3 passed** (postgreSQL real, sin skips).
* Mutaciones nuevas **M169–M174** — **6/6** muerden y restauran byte a byte.
* Matriz completa **M1–M174** — corrida con restauración byte a byte y huella `git status` idéntica,
  `0` mutaciones sin fragmento.

## 4. Huecos declarados (lo que ESTA fase NO cierra)

1. **El walk-forward real sigue sin ejecutarse.** Los umbrales por defecto (`folds=3`, `min_is=8`,
   `min_oos=4`) exigen ≥32 ciclos medidos por estrategia: el fixture del E2E es **sintético** y mide la
   **cadena de material**, no el edge. Ejecutar el instrumento sobre una cuenta PAPER real es un paso
   **operativo del propietario** (`paper_cycles_export.py` → `auto_replay_battery.py --walk-forward`).
2. **La huella no es una prueba de procedencia criptográfica**: sella la **igualdad de universo** entre
   dos corridas, no que el material venga de una fuente concreta.
3. **`P(R > 0)`, correlación entre estrategias y current-regime gating** siguen fuera de alcance
   (AUTO-21).

## 5. Ficheros clave

* `packages/py/application/src/bolsa_application/reservation_store.py` — `offset` aditivo (worker intacto).
* `apps/api-python/scripts/paper_cycles_export.py` — paginación + manifest + fail-closed (`exit 2`).
* `packages/py/analytics/src/bolsa_analytics/cognitive/auto_material_manifest.py` — huella pura.
* `packages/py/application/src/bolsa_application/auto_material_manifest.py` — manifest de conteos.
* `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_calibration.py` — bloque `material` opcional.
* `scripts/research/auto_replay_battery.py` — passthrough del manifest.
* `apps/api-python/tests/test_auto_v63_auto20b_export_e2e_pg.py` — E2E PG (job `auto-v2-durable-pg`).
* `apps/api-python/tests/test_auto_v63_auto20b_export_completeness.py` — puros (job offline).
* `apps/api-python/scripts/v2_44_mutation_audit.py` — M169–M174.

## 6. Cómo re-verificar en frío

```powershell
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync pytest packages/py/analytics/tests packages/py/application/tests -q
$env:AUTO20B_EXPORT_PG_REQUIRED="1"; uv run --no-sync pytest apps/api-python/tests/test_auto_v63_auto20b_export_e2e_pg.py -q -rs
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M169 M170 M171 M172 M173 M174
```

## 7. Reglas de la casa que siguen vigentes

* **Lo que no se midió se declara** — nunca un veredicto, un conteo ni un cero inventados.
* **Un solo productor por medida** — sin segundos caminos que puedan divergir en silencio.
* **Nada de evidencia mueve el reparto** — el sello `auto18-v1` no se toca sin fase propia.
* **Una cadena end-to-end no está certificada hasta que se recorre con PG real** — la estática no basta.
* **Lo que el trabajo real ejercita es lo que hay que fijar** — un `pip install` sin lock es una
  medición de PyPI, no del repo: si el metadato del paquete no basta por sí solo, el CI miente tarde.

## 8. Re-sello `v2.63.1-beta` (2026-09-25, INFRAESTRUCTURA)

* **Qué pasó:** el push del sello encendió `Optimize lab` en rojo (main, tag y rama) con
  `ModuleNotFoundError: No module named 'greenlet'`. **No era de `AUTO-20B`** (la fase no toca JS ni
  el laboratorio): `packages/py/infrastructure` declaraba `sqlalchemy>=2.0` **sin el extra
  `[asyncio]`** y ese job instala con **pip crudo, sin lock**; al publicarse **SQLAlchemy 2.1.0**
  (que movió `greenlet` al extra) la resolución dejó de traerlo. Las corridas de `v2.62`
  (2026-09-24 19:52) estaban verdes porque aún resolvían 2.0.x: era una bomba de relojería de PyPI.
* **Qué se hizo:** `sqlalchemy[asyncio]>=2.0,<2.1` en `packages/py/infrastructure/pyproject.toml` +
  `uv lock` (el extra entra en el **metadato**; el techo declara que 2.1 no está evaluada). Cero
  cambios de producto, cero migración, reparto intacto.
* **Evidencia:** venv limpio con el `pip install -e` del workflow → `sqlalchemy 2.0.54` +
  `greenlet 3.5.6` + `sqlalchemy.ext.asyncio` importa **OK**; lock en 2.0.51. Y tras el cambio:
  `ruff`, `lint-imports` (4 kept/0 broken), `mypy` (500/0), **3147 puros** y las suites de `AUTO-20B`
  (**18 passed** con `AUTO20B_EXPORT_PG_REQUIRED=1`).
* **Sellos:** `v2.63-beta` **no se mueve** (queda con su rojo de infra en el historial); el sello
  vigente para auditar es **`v2.63.1-beta`**. El `Release tag CI` de `v2.63-beta` ya estaba **GREEN
  9/9** (incluido `lifecycle-pg` con el E2E real de AUTO-20B): lo que faltaba en verde era solo el
  laboratorio.
