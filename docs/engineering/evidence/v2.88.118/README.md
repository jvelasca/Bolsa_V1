# Evidencia `v2.88.118-beta` — `H1.1`: sin muestra efectiva no hay `MEASURED`, ni con procedencia completa

> **Sello:** `v2.88.118-beta` (base `v2.88.117-beta`).
> **Bump:** `2.11.117-beta` → **`2.11.118-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87` y de los 9 CLIs `v2_89`…`v2_97`).
> **Naturaleza:** sello **aditivo** · **`Δ motor ≠ 0`** (dominio puro de banda) · **`Δ decisión = 0`** (no toca decisión/ejecución, umbrales, `TOP_N`, régimen ni reparto) · **SIN migración** (head `053_dia_d_cycle_verifications`) · **contrato HTTP SIN cambio** (las bandas son **ficheros**, no endpoints) · **SIN cambio de forma de artefacto** (`SCHEMA_VERSION` NO sube: se mantienen `dia-d-multi-band-v3` y `oos-finance-band-v4`).
> **Cierra:** caso límite (P1) de **`H1.1`** detectado por la **AUDITORIA 1** al auditar `v2.88.117-beta` y no cubierto por la **AUDITORIA 2**: una banda **sin muestra** con procedencia completa quedaba en `MEASURED`.
> **Fecha:** 2026-10-13.

---

## 1. Qué cambia (aditivo)

| Pieza | Fichero | Contenido |
| --- | --- | --- |
| **Guarda de máxima precedencia** | [`dia_d_multi_uncertainty.py`](../../../../packages/py/application/src/bolsa_application/dia_d_multi_uncertainty.py) | En `band_validity`, la rama `design == DESIGN_INDEPENDENT` gana `if not measured:` **antes** de las demás: `status = "NOT_MEASURED"`, `reason = STATISTICAL_CONFIDENCE_NO_SAMPLE_REASON`, `missing = list(gaps)`. Constante nueva `STATISTICAL_CONFIDENCE_NO_SAMPLE_REASON = "no_effective_sample"`, exportada en `__all__`. Se actualizan docstring de módulo, docstring de `band_validity` y el texto del límite H1.1 (`DEFAULT_LIMITS`). |
| **Consumidor auditado** | [`oos_finance_band.py`](../../../../packages/py/application/src/bolsa_application/oos_finance_band.py) | Su límite H1.1 homólogo se actualiza; la lógica se hereda por delegación en la **misma** `band_validity` ⇒ las dos bandas **no pueden divergir**. |
| **Pruebas** | [`test_dia_d_multi_uncertainty.py`](../../../../packages/py/application/tests/test_dia_d_multi_uncertainty.py) | `test_h1_gap_still_marks_statistical_confidence_not_measured` ahora exige `status == "NOT_MEASURED"`, `reason == STATISTICAL_CONFIDENCE_NO_SAMPLE_REASON`, `established is False`, `se is None`, `ci95HalfWidth is None`. |
| **Prueba negativa nueva** | [`test_oos_finance_band.py`](../../../../packages/py/application/tests/test_oos_finance_band.py) | `test_h1_1_no_effective_sample_blocks_measured_even_with_provenance` (`draws=[]`, `design=DESIGN_INDEPENDENT`, `provenance=_provenance()` ⇒ agregado `NOT_MEASURED` / `no_effective_sample` / `established False`). |
| **Límites sellados** | [`v2.88.117/README.md`](../v2.88.117/README.md) | §4 Límites: bullet «`MEASURED` también exige muestra efectiva». |

---

## 2. El borde — sin muestra no hay medición

**Antes (`v2.88.117`):** con `draws = []` (⇒ `stats is None`) y procedencia completa, la rama
`independent_sample` llegaba hasta el final y publicaba `status = "MEASURED"` con `established = False`.
Un consumidor leía `MEASURED` como «hay una medición estadística» cuando **no existía muestra**.

**Ahora:** la guarda `if not measured:` corta **antes** que cualquier otra causa. Sin muestra efectiva,
la confianza queda `NOT_MEASURED` con el motivo más específico:

```json
{
  "design": "independent_sample",
  "crossesKey": "crossesZeroNetReturn",
  "statisticalConfidence": {
    "label": "statisticalConfidence",
    "design": "independent_sample",
    "status": "NOT_MEASURED",
    "established": false,
    "se": null,
    "ci95HalfWidth": null,
    "reason": "no_effective_sample",
    "requires": "Observaciones INDEPENDIENTES declaradas por el llamante (design='independent_sample')…",
    "provenance": { "evaluationWindows": ["2019", "2021"], "samplingMethod": "blocked_cross_year", "sampleSize": 12, "observationUnit": "cycle", "temporalDependence": "year_blocked" },
    "missingProvenance": []
  }
}
```

Orden de precedencia exacto de la rama `independent_sample` tras el cambio:

1. **sin muestra** (`stats is None`) ⇒ `no_effective_sample` (**máxima precedencia**; es el motivo más específico cuando varios aplican).
2. `venue_seeded` ⇒ `venue_draw_declared_independent`.
3. sin procedencia ⇒ `provenance_missing`.
4. procedencia incompleta ⇒ `provenance_incomplete`.
5. procedencia completa **y** muestra presente ⇒ `MEASURED`, `established = pointCitable`.

---

## 3. Verificación (local)

| Compuerta | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | ✅ `All checks passed!` |
| `mypy packages/py/application/src --follow-imports=silent` | ✅ `Success: no issues found in 263 source files` |
| `pytest packages/py/application/tests -q` | ✅ **2706 passed** (175.27s) — **+1** sobre los `2705` del sello anterior |
| `pytest` focales (`test_dia_d_multi_uncertainty` + `test_oos_finance_band` + `test_replay_oos_cli_renderers`) | ✅ **49 passed** (antes 48; +1 por el test nuevo) |
| `pytest packages/py/application/tests/test_dia_d_multi_sampling.py -q` | ✅ **34 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py -q` | ✅ **1 passed** |
| `alembic heads` | `053_dia_d_cycle_verifications (head)` — **sin migración** |

---

## 4. Límites declarados

- **La puerta verifica la procedencia declarada, NO la valida científicamente.** Sigue sin existir un
  procedimiento estadístico real: `MEASURED` acredita que **hay muestra efectiva** y que la procedencia
  declarada es completa y coherente, no que el muestreo sea correcto. No se finge lo contrario.
- **`MEASURED` también exige muestra efectiva.** Aun con procedencia completa, sin banda (o con menos de
  `MIN_DRAWS_FOR_BAND` sorteos) la confianza queda `NOT_MEASURED` con `reason=no_effective_sample`:
  declarar independencia no crea la medición que no existe.
- **Los artefactos de evidencia sellados siguen en su esquema antiguo** (`v2.88.114/finance-band-w32-k12.json`):
  regenerarlos exige PostgreSQL con la entrada sembrada ⇒ **no reproducible sin PG**.
- **`R-ev`** (regenerar el artefacto `K=12` en el esquema nuevo) sigue **pendiente**.
- **`P3-2`/`P3-3`** (validación longitudinal PAPER) y la **auditoría de UI** siguen **abiertos**; la
  evidencia de replay OOS **no** sustituye una ventana PAPER.
- **Tag `unsigned`:** el tag anotado no está firmado.

---

## 5. Cita POST-TAG

Tag anotado **`v2.88.118-beta`** (objeto `370af6ff` → commit `340b49ef`) sellado y publicado en `origin`
(`git ls-remote origin refs/tags/v2.88.118-beta*` resuelve objeto + `^{}`); `origin/main` == `HEAD` == `340b49ef`.
Tag **anotado sin firmar** (`unsigned`) — declarado, no disimulado.

- `Release tag CI` [**38356133040**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38356133040) → **`success`** (`11m51s`): **12 jobs `success` + `certify` `success`** (`playwright (integrated E2E, opt-in)` `skipped`, esperado). **`replay-repro`** → **`success`**: regenera el artefacto del sello desde el fixture **sin** mover el payload ⇒ el endurecimiento (fichero puro de banda) **no** tocó el artefacto congelado (`Δ decisión = 0`).
- `Python CI` [**38356133017**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38356133017) `success` (`3m06s`) · `Frontend CI` [**38356133072**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38356133072) `success` (`3m12s`) · `Fase 2 scientific` [**38356133062**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38356133062) `success` (`1m22s`) · `Optimize lab` [**38356133116**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38356133116) `success` (`2m19s`).
- CI de **rama** (`main`, `340b49ef`): `Python CI` [**38356115031**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38356115031) `success` · `Frontend CI` [**38356115053**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38356115053) `success` · `Fase 2 scientific` [**38356115030**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38356115030) `success` · `Optimize lab` [**38356115042**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38356115042) `success` · `Gitleaks` [**38356115029**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38356115029) `success`.
- **Anotaciones del run:** solo avisos **preexistentes** y ajenos al diff (deprecación de Node 20 en `actions/*`, migración `ubuntu-latest`→26, avisos de `react-hooks/exhaustive-deps` en `apps/web`). **Ninguna** referida a `dia_d_multi_uncertainty`/`oos_finance_band`.
- **Distinción:** *estado comunicado* (implementado y verificado localmente) vs *verificación externa* (tag/commit/run resueltos en GitHub) — aquí **ambos** confirmados. El sello **no** demuestra rentabilidad.
