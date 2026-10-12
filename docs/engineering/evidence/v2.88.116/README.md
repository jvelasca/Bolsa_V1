# Evidencia `v2.88.116-beta` — `H1`: separación de `sensitivityBand` y `statisticalConfidence`

> **Sello:** `v2.88.116-beta` (base `v2.88.115-beta`).
> **Bump:** `2.11.115-beta` → **`2.11.116-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87` y de los 9 CLIs `v2_89`…`v2_97`).
> **Naturaleza:** sello **aditivo** · **`Δ motor ≠ 0`** (dominio puro de banda, con cambio de forma de artefacto) · **`Δ decisión = 0`** (no toca decisión/ejecución, umbrales, `TOP_N`, régimen ni reparto) · **SIN migración** (head `053_dia_d_cycle_verifications`) · **contrato HTTP SIN cambio** (las bandas son **ficheros**, no endpoints).
> **Cierra:** `H1` de la **AUDITORIA 1** («la banda no debe confundirse con un intervalo de confianza estadístico»).
> **Fecha:** 2026-10-12.

---

## 1. Qué cambia (aditivo)

| Pieza | Fichero | Contenido |
| --- | --- | --- |
| **Fuente ÚNICA** | [`dia_d_multi_uncertainty.py`](../../../../packages/py/application/src/bolsa_application/dia_d_multi_uncertainty.py) | `band_validity(crosses_key, stats, draws_with_cell, design)` compone el bloque `validity` con **dos etiquetas separadas**: `sensitivityBand` (`crossesZero…` + `pointCitable` acotado por `pointCitableScope`) y `statisticalConfidence` (`NOT_MEASURED` con `design = "venue_draw"`; `MEASURED` solo si el llamante declara `"independent_sample"`). Constantes nuevas: `DESIGN_VENUE_DRAW`, `DESIGN_INDEPENDENT`, `POINT_CITABLE_SCOPE`, `STATISTICAL_CONFIDENCE_NOT_MEASURED_REASON`, `STATISTICAL_CONFIDENCE_REQUIRES`. `SCHEMA_VERSION` `dia-d-multi-band-v1` → **`v2`**; el payload gana `design`. |
| **Consumidor auditado** | [`oos_finance_band.py`](../../../../packages/py/application/src/bolsa_application/oos_finance_band.py) | `_validity` **delega** en `band_validity` con `crosses_key = "crossesZeroNetReturn"`; `build_finance_band(draws=…, design=…)`. `SCHEMA_VERSION` `oos-finance-band-v2` → **`v3`**; el payload gana `design`. |
| **Lector tolerante** | [`dia_d_multi_sampling.py`](../../../../packages/py/application/src/bolsa_application/dia_d_multi_sampling.py) | `_venue_band_cross_check` lee la sensibilidad **anidada** (`validity.sensitivityBand`), con **respaldo plano** para artefactos sellados anteriores. No finge otra cosa ni pierde el autochequeo. |
| **Render** | [`v2_87_replay_oos_durable_cycle.py`](../../../../apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py) · [`v2_94_dia_d_multi_band.py`](../../../../apps/api-python/scripts/v2_94_dia_d_multi_band.py) | El render imprime **ambas** etiquetas: `sensitivityBand` (cruce + `pointCitable`) y `statisticalConfidence` (estado + `established`). |
| **Pruebas puras** | [`test_dia_d_multi_uncertainty.py`](../../../../packages/py/application/tests/test_dia_d_multi_uncertainty.py) · [`test_oos_finance_band.py`](../../../../packages/py/application/tests/test_oos_finance_band.py) · [`test_replay_oos_cli_renderers.py`](../../../../apps/api-python/tests/test_replay_oos_cli_renderers.py) | `H1`: etiquetas separadas, `NOT_MEASURED` por defecto con motivo/requisito, `pointCitableScope`, **invariancia bajo permutación**, `independent_sample` sí mide, hueco sin muestra, agregado sin muestra. |

---

## 2. `H1` — dos etiquetas, nunca confundidas

**Antes:** el bloque `validity` publicaba `crossesZero…` y `pointCitable = (no cruza) and |media| > 1.96·SE`
al mismo nivel. El `1.96·SE` **parecía** inferencia estadística, pero los `K` sorteos desplazan el ancla de
la semilla del simulador sobre el **MISMO** dato histórico ⇒ **no** son observaciones independientes.

**Ahora:** el bloque declara el **diseño** y publica dos etiquetas separadas:

```json
{
  "design": "venue_draw",
  "crossesKey": "crossesZeroNetReturn",
  "sensitivityBand": {
    "label": "sensitivityBand",
    "scope": "venue_draw_sensitivity",
    "crossesZeroNetReturn": true,
    "pointCitable": false,
    "pointCitableScope": "sensitivity_band_only_not_statistical_confidence",
    "se": 0.294333,
    "ci95HalfWidth": 0.576893,
    "note": null
  },
  "statisticalConfidence": {
    "label": "statisticalConfidence",
    "design": "venue_draw",
    "status": "NOT_MEASURED",
    "established": false,
    "se": null,
    "ci95HalfWidth": null,
    "reason": "Los K sorteos desplazan el ancla de la semilla del simulador sobre el MISMO dato historico…",
    "requires": "Observaciones INDEPENDIENTES declaradas por el llamante (design='independent_sample')…"
  }
}
```

- `pointCitable` **se conserva** (lectura de sensibilidad) pero **acotado** por `pointCitableScope`.
- `statisticalConfidence` con `design = venue_draw` queda **`NOT_MEASURED`**, con **motivo** y **requisito**. **Jamás** se infiere de re-sorteos.
- Solo `design = "independent_sample"` (declarado por el llamante) computa `status = "MEASURED"`.
- La lógica vive en **una** función ⇒ las dos bandas no pueden divergir.

---

## 3. Verificación (local)

| Compuerta | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | ✅ `All checks passed!` |
| `mypy packages/py/application/src --follow-imports=silent` | ✅ `Success: no issues found in 263 source files` |
| `pytest packages/py/application/tests -q` | ✅ **2699 passed** (191.07s) — **sin** el fallo ambiental de `_devicearray` que apareció en el sello anterior |
| `pytest` focales (`test_dia_d_bump_guard` + `test_replay_oos_cli_renderers` + `test_oos_finance_band` + `test_dia_d_multi_uncertainty` + `test_dia_d_multi_sampling`) | ✅ **77 passed** |

> **+8 tests** sobre los `2691` del sello anterior: la cobertura `H1` añadida en los dos módulos de banda.

---

## 4. Límites declarados

- **No** se implementa una confianza estadística real: exige observaciones **independientes** y un procedimiento adecuado ⇒ queda `NOT_MEASURED` con su requisito **declarado**, no simulado.
- **Los artefactos de evidencia sellados siguen en su esquema antiguo** (`v2.88.114/finance-band-w32-k12.json` es `oos-finance-band-v1`): regenerarlos exige PostgreSQL con la entrada sembrada ⇒ **no reproducible sin PG** y **no** se finge. La forma nueva está fijada por tests puros.
- **`H3`/`H2`/`P1`** (sellos anteriores) siguen cerrados; **`R-ev`** (regenerar el artefacto `K=12` en el esquema nuevo) sigue **pendiente** por la misma dependencia de PostgreSQL.
- **Hueco declarado en `CHANGELOG.md`:** las entradas `2.11.114-beta` y `2.11.115-beta` **no** se añadieron (los dos sellos no tocaron el `CHANGELOG`); esta entrada documenta el salto `113 → 116`. Se declara, no se disimula.
- **Tag `unsigned`:** el tag anotado no está firmado.

---

## 5. Cita POST-TAG

**PENDIENTE** (tag `v2.88.116-beta` por publicar desde esta sesión). La cita se completa con el `Release tag CI` resuelto en GitHub.
