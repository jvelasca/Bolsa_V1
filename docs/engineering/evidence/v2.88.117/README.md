# Evidencia `v2.88.117-beta` — `H1.1`: la confianza estadística exige PROCEDENCIA verificable

> **Sello:** `v2.88.117-beta` (base `v2.88.116-beta`).
> **Bump:** `2.11.116-beta` → **`2.11.117-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87` y de los 9 CLIs `v2_89`…`v2_97`).
> **Naturaleza:** sello **aditivo** · **`Δ motor ≠ 0`** (dominio puro de banda, con cambio de forma de artefacto) · **`Δ decisión = 0`** (no toca decisión/ejecución, umbrales, `TOP_N`, régimen ni reparto) · **SIN migración** (head `053_dia_d_cycle_verifications`) · **contrato HTTP SIN cambio** (las bandas son **ficheros**, no endpoints).
> **Cierra:** subhallazgo **`H1.1`** de la **AUDITORIA 1** («la garantía estadística necesita una salvaguarda adicional… exigir evidencia verificable de su procedencia… si esa evidencia no existe, debe mantenerse `NOT_MEASURED`, aunque el llamante solicite la etiqueta»).
> **Fecha:** 2026-10-12.

---

## 1. Qué cambia (aditivo)

| Pieza | Fichero | Contenido |
| --- | --- | --- |
| **Puerta de PROCEDENCIA** | [`dia_d_multi_uncertainty.py`](../../../../packages/py/application/src/bolsa_application/dia_d_multi_uncertainty.py) | `band_validity(crosses_key, stats, draws_with_cell, design, provenance, venue_seeded)`. Con `design = "independent_sample"`, `statisticalConfidence.status = "MEASURED"` exige procedencia **completa y bien formada**; si no, `NOT_MEASURED` con motivo (`provenance_missing` / `provenance_incomplete`) y `missingProvenance`. Constantes nuevas: `PROVENANCE_REQUIRED_FIELDS`, `STATISTICAL_CONFIDENCE_PROVENANCE_MISSING_REASON`, `STATISTICAL_CONFIDENCE_PROVENANCE_INCOMPLETE_REASON`, `STATISTICAL_CONFIDENCE_VENUE_DRAW_CONTRADICTION_REASON`. `SCHEMA_VERSION` `dia-d-multi-band-v2` → **`v3`**. |
| **Contradicción de independencia** | [`dia_d_multi_uncertainty.py`](../../../../packages/py/application/src/bolsa_application/dia_d_multi_uncertainty.py) | Un `seed_shift` NO vacío (incl. clave vacía `{"": ""}`) revela un **re-sorteo del venue** ⇒ `venue_draw_declared_independent`, aunque la procedencia sea válida. |
| **Consumidor auditado** | [`oos_finance_band.py`](../../../../packages/py/application/src/bolsa_application/oos_finance_band.py) | `_validity`/`build_finance_band` propagan `provenance` por la **misma** `band_validity` ⇒ las dos bandas **no pueden divergir**. `SCHEMA_VERSION` `oos-finance-band-v3` → **`v4`**. |
| **Tolerante** | [`dia_d_multi_uncertainty.py`](../../../../packages/py/application/src/bolsa_application/dia_d_multi_uncertainty.py) | `_provenance_gaps` es puro y **no levanta** con input malformado: devuelve TODOS los campos exigidos como huecos, en orden determinista. La rama `venue_draw` por defecto **no** cambia su salida. |
| **Pruebas negativas** | [`test_dia_d_multi_uncertainty.py`](../../../../packages/py/application/tests/test_dia_d_multi_uncertainty.py) · [`test_oos_finance_band.py`](../../../../packages/py/application/tests/test_oos_finance_band.py) | `independent_sample` **sin** procedencia ⇒ `provenance_missing`; procedencia **incompleta** ⇒ `provenance_incomplete` + campo declarado; datos **sembrados** declarados independientes ⇒ `venue_draw_declared_independent`; procedencia válida ⇒ `MEASURED`; **invariancia bajo permutación** con procedencia. |

---

## 2. `H1.1` — la declaración ya no basta

**Antes (`v2.88.116`):** `band_validity` cambiaba el estado a `MEASURED` con solo recibir
`design = "independent_sample"`. No verificaba que los datos procedieran de observaciones
independientes ni que se hubiera aplicado un diseño estadístico. Los tests ejercitaban esa
rama con informes sintéticos: probaban la rama del código, **no** la independencia de los datos.

**Ahora:** la etiqueta `MEASURED` exige evidencia de procedencia declarada por el llamante.

```json
{
  "design": "independent_sample",
  "crossesKey": "crossesZeroNetReturn",
  "sensitivityBand": { "label": "sensitivityBand", "pointCitable": true, "pointCitableScope": "sensitivity_band_only_not_statistical_confidence", "...": "..." },
  "statisticalConfidence": {
    "label": "statisticalConfidence",
    "design": "independent_sample",
    "status": "NOT_MEASURED",
    "established": false,
    "se": null,
    "ci95HalfWidth": null,
    "reason": "provenance_incomplete",
    "requires": "Observaciones INDEPENDIENTES declaradas por el llamante (design='independent_sample')…",
    "provenance": {
      "evaluationWindows": ["2019", "2021"],
      "samplingMethod": "blocked_cross_year",
      "observationUnit": "cycle",
      "temporalDependence": "year_blocked"
    },
    "missingProvenance": ["sampleSize"]
  }
}
```

Tres desenlaces, todos publicados sin levantar (enforcement **graceful**):

- **Sin procedencia** (`provenance` ausente o vacío) ⇒ `status = NOT_MEASURED`,
  `reason = provenance_missing`, `missingProvenance` = los cinco campos exigidos.
- **Procedencia incompleta** ⇒ `status = NOT_MEASURED`, `reason = provenance_incomplete`,
  `missingProvenance` = solo los campos ausentes o mal formados.
- **Datos sembrados** (`seed_shift` NO vacío) declarados independientes ⇒
  `status = NOT_MEASURED`, `reason = venue_draw_declared_independent`, aunque la procedencia
  sea válida.

Campos exigidos (`PROVENANCE_REQUIRED_FIELDS`): `evaluationWindows` (secuencia no vacía de
etiquetas no vacías), `samplingMethod` (texto no vacío), `sampleSize` (entero `>= MIN_DRAWS_FOR_BAND`),
`observationUnit` (texto no vacío) y `temporalDependence` (texto no vacío). Solo con los cinco
válidos y sin contradicción de venue: `status = MEASURED`, `established = pointCitable`.

---

## 3. Verificación (local)

| Compuerta | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | ✅ `All checks passed!` |
| `mypy packages/py/application/src --follow-imports=silent` | ✅ `Success: no issues found in 263 source files` |
| `pytest packages/py/application/tests -q` | ✅ **2705 passed** (189.92s) — **+6** sobre los `2699` del sello anterior |
| `pytest` focales (`test_dia_d_multi_uncertainty` + `test_oos_finance_band` + `test_replay_oos_cli_renderers`) | ✅ **48 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | ✅ **1 passed** |
| Comprobación empírica de bordes | ✅ **sin bypass** (`venue_draw` intacto; input malformado no levanta; `venue_seeded` bloquea incluso con clave vacía; orden determinista) |
| `alembic heads` | `053_dia_d_cycle_verifications (head)` — **sin migración** |

---

## 4. Límites declarados

- **La puerta verifica la procedencia declarada, NO la valida científicamente.** Sigue sin existir un
  procedimiento estadístico real: la etiqueta `MEASURED` acredita que el llamante **declaró** una
  procedencia completa y coherente, no que el muestreo sea correcto. No se finge lo contrario.
- **`MEASURED` también exige muestra efectiva.** Aun con procedencia completa, sin banda (o con menos
  de `MIN_DRAWS_FOR_BAND` sorteos) la confianza queda `NOT_MEASURED` con `reason=no_effective_sample`:
  declarar independencia no crea la medición que no existe.
- **Los artefactos de evidencia sellados siguen en su esquema antiguo** (`v2.88.114/finance-band-w32-k12.json`):
  regenerarlos exige PostgreSQL con la entrada sembrada ⇒ **no reproducible sin PG**.
- **`R-ev`** (regenerar el artefacto `K=12` en el esquema nuevo) sigue **pendiente**.
- **`P3-2`/`P3-3`** (validación longitudinal PAPER) y la **auditoría de UI** siguen **abiertos**; la
  evidencia de replay OOS **no** sustituye una ventana PAPER.
- **Tag `unsigned`:** el tag anotado no está firmado.
- **Revisión independiente:** la revisión Bugbot solicitada **no pudo completarse** (el validador de
  hallazgos descartó sus resultados en dos intentos); se sustituye por la comprobación empírica de
  bordes de §3, declarada como tal.

---

## 5. Cita POST-TAG

Tag anotado **`v2.88.117-beta`** (objeto `277d33ca` → commit `2195ad7f`) sellado y publicado en `origin`
(`git ls-remote origin refs/tags/v2.88.117-beta*` resuelve objeto + `^{}`); `origin/main` == `HEAD` == `2195ad7f`.
Tag **anotado sin firmar** (`unsigned`) — declarado, no disimulado.

- `Release tag CI` [**38302937561**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302937561) → **`success`** (`11m39s`): **12 jobs `success` + `certify` `success`** (`playwright (integrated E2E, opt-in)` `skipped`, esperado). **`replay-repro`** → **`success`**: regenera el artefacto del sello desde el fixture **sin** mover el payload ⇒ el cambio de forma de las **bandas** (ficheros) **no** tocó el artefacto congelado.
- `Python CI` [**38302937501**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302937501) `success` (`3m47s`) · `Frontend CI` [**38302937492**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302937492) `success` (`4m18s`) · `Fase 2 scientific` [**38302937508**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302937508) `success` (`1m24s`) · `Optimize lab` [**38302937490**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302937490) `success` (`1m31s`).
- CI de **rama** (`main`, `2195ad7f`): `Python CI` [**38302935816**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302935816) · `Frontend CI` [**38302935701**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302935701) · `Fase 2 scientific` [**38302935715**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302935715) · `Optimize lab` [**38302935705**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302935705) · `Gitleaks` [**38302935774**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302935774) — todos `success`.
- **Anotaciones del run:** solo avisos **preexistentes** y ajenos al diff (deprecación de Node 20 en `actions/*`, migración `ubuntu-latest`→26). **Ninguna** referida a `dia_d_multi_uncertainty`/`oos_finance_band`.
- **Distinción:** *estado comunicado* (implementado y verificado localmente) vs *verificación externa* (tag/commit/run resueltos en GitHub) — aquí **ambos** confirmados. El sello **no** demuestra rentabilidad.

**Cierre POST-TAG en `main`:** commit de documentación `b877f797` (`origin/main` == `HEAD` en el momento del cierre); CI de rama → solo `Gitleaks` [`38315472026`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38315472026) `success` (`12s`), porque los workflows de código **no** disparan en commits `docs`-only (mismo patrón que el cierre de `116`).
