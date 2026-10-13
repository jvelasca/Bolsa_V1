# Entrega a auditoría externa (MIA) — `v2.88.117-beta` · **`H1.1`: la confianza estadística exige PROCEDENCIA verificable** · fuente única `band_validity` endurecida · **`Δ motor ≠ 0`** aditivo · **`Δ decisión = 0`** · contrato **sin cambio** · **sin migración**

> **Fecha:** 2026-10-12 · **Producto:** `V2.88.117-beta` · **Package:** `2.11.117-beta` · **Alembic head:** `053_dia_d_cycle_verifications` (sin `054`; **sin migración**).
> **Base:** `v2.88.116-beta` (tag anotado objeto `cfed89bb` → commit `932cbdcf`; `Release tag CI` [`38290903444`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38290903444) **VERDE**).
> **Unidad de esta auditoría:** cerrar el subhallazgo **`H1.1`** de la **AUDITORIA 1**, que aceptaba la separación `sensitivityBand`/`statisticalConfidence` de `v2.88.116-beta` como avance, pero dejaba abierto que «el código permite declarar una muestra como independiente sin verificar esa independencia».
> **Regla del hueco:** una afirmación que no se puede sostener se declara **abierta** con su remediación, **nunca** se silencia. Un dato ausente se rotula hueco; **jamás** se rellena con `0` ni con verde. **Banda ≠ punto.**
> **`Δ motor ≠ 0` aditivo · `Δ decisión = 0`.** El diff toca `packages/py/**` y el bump; **no** toca umbrales, reparto de capital, `TOP_N`, régimen, selección ni protección.
> **Contrato HTTP sin cambio:** el sello no toca `openapi.json` ni `schema.d.ts`.
> **Evidencia cruda:** [`docs/engineering/evidence/v2.88.117/README.md`](./evidence/v2.88.117/README.md) · **Plan:** [`plan-v2-88-117-h1-1-procedencia-estadistica-2026-10-12.md`](./plan-v2-88-117-h1-1-procedencia-estadistica-2026-10-12.md).

---

## 1. Qué se entrega (y qué NO)

**Se entrega**, en un único commit de sello:

1. **`H1.1` Puerta de PROCEDENCIA (fuente única).** `band_validity` gana `provenance` y `venue_seeded`. Con `design = "independent_sample"`, `statisticalConfidence.status = "MEASURED"` exige procedencia **completa y bien formada** (`PROVENANCE_REQUIRED_FIELDS`: `evaluationWindows`, `samplingMethod`, `sampleSize`, `observationUnit`, `temporalDependence`); si no, queda `NOT_MEASURED` con motivo (`provenance_missing` / `provenance_incomplete`) y `missingProvenance`. **Enforcement graceful:** nunca levanta; siempre publica el hueco. `SCHEMA_VERSION` `dia-d-multi-band-v2` → **`v3`**.
2. **`H1.1` Contradicción de independencia declarada.** Un `seed_shift` NO vacío (incl. clave vacía `{"": ""}`) revela un **re-sorteo del venue** ⇒ `venue_draw_declared_independent`, aunque la procedencia sea válida.
3. **Misma puerta en la banda financiera.** `oos_finance_band._validity`/`build_finance_band` delegan en la **misma** función ⇒ las dos bandas **no pueden divergir**; `SCHEMA_VERSION` `oos-finance-band-v3` → **`v4`**.
4. **Tolerancia y determinismo.** `_provenance_gaps` es puro y no levanta con input malformado (`None`/lista/texto/número ⇒ todos los campos como huecos, orden determinista). La rama `venue_draw` por defecto **no** cambia su salida.
5. **Pruebas negativas** de los tres desenlaces, más el bump `2.11.117-beta` y la evidencia/plan/`CHANGELOG`/`PROJECT_STATE`.

**NO se entrega**, y se declara:

- **NO** se implementa una **confianza estadística real**: la puerta **verifica la procedencia declarada**, **no** la valida científicamente (no existe un procedimiento estadístico auditado en el repo). No se finge lo contrario.
- **NO** se toca el **motor de decisión/ejecución** (`Δ decisión = 0`).
- **NO** hay migración (head `053`).
- **NO** cambia el **contrato HTTP**.
- **NO** se regenera el artefacto de evidencia `finance-band-w32-k12.json`: sigue en su esquema antiguo; regenerarlo exige **PostgreSQL** ⇒ **no reproducible sin PG**, y **no se finge**.
- **NO** se cierran **`R-ev`**, **`P3-2`/`P3-3`** (PAPER longitudinal) ni la **auditoría de UI**. *(Nota posterior: `R-ev` se cerró en `v2.88.119-beta`.)*

---

## 2. Cambios verificables (todo con gate)

| Pieza | Fichero(s) | Qué hace |
| --- | --- | --- |
| `H1.1` puerta | `packages/py/application/src/bolsa_application/dia_d_multi_uncertainty.py` | `_provenance_gaps` (puro, tolerante); `band_validity(..., provenance, venue_seeded)` con los tres desenlaces; constantes `PROVENANCE_REQUIRED_FIELDS`, `..._PROVENANCE_MISSING_REASON`, `..._PROVENANCE_INCOMPLETE_REASON`, `..._VENUE_DRAW_CONTRADICTION_REASON`; `SCHEMA_VERSION` → `dia-d-multi-band-v3`. |
| `H1.1` delegación | `packages/py/application/src/bolsa_application/oos_finance_band.py` | `_validity`/`build_finance_band` propagan `provenance`; `SCHEMA_VERSION` → `oos-finance-band-v4`. |
| Lector | `packages/py/application/src/bolsa_application/dia_d_multi_sampling.py` | Nota de versión del lector actualizada (lee `validity.sensitivityBand`; **sin** cambio funcional). |
| Pruebas | `packages/py/application/tests/test_dia_d_multi_uncertainty.py`, `.../test_oos_finance_band.py` | Negativas: sin procedencia, incompleta, sembrado declarado independiente; positiva con procedencia válida; invariancia por permutación. |
| Bump | `package.json` + `apps/api-python/scripts/v2_87` y `v2_89`…`v2_97` | `2.11.117-beta` + `meta.bump` (guardián `test_dia_d_bump_guard.py`). |

---

## 3. Medición

- **Python (local):** `ruff check packages/py apps/api-python --config pyproject.toml` **All checks passed**; `mypy packages/py/application/src --follow-imports=silent` **263 source files, no issues**.
- **Batería de aplicación:** `pytest packages/py/application/tests -q` ⇒ **2705 passed** (+6 sobre los `2699` de `v2.88.116-beta`).
- **Batería focalizada:** `test_dia_d_multi_uncertainty` + `test_oos_finance_band` + `test_replay_oos_cli_renderers` ⇒ **48 passed**; `test_dia_d_bump_guard` ⇒ **1 passed**.
- **Comprobación empírica de bordes:** sin bypass hacia `MEASURED`; `venue_draw` por defecto intacto; input malformado no levanta; `venue_seeded` bloquea incluso con clave vacía; orden de `missingProvenance` determinista.
- **`Δ motor ≠ 0` sin mover el sello:** las bandas son **ficheros**, no el artefacto congelado del replay ⇒ el job `replay-repro` del tag debe reproducir sin mover el payload (a confirmar en la cita POST-TAG).
- **No reproducible en CI:** la medición de la banda `K` con `K=12` exige PostgreSQL sembrado ⇒ **medición local**, no gate de CI.

---

## 4. Hallazgos y estado tras esta entrega

| ID | Hallazgo | Estado |
| --- | --- | --- |
| `H1` (AUDITORIA 1) | la banda no debe confundirse con un intervalo de confianza estadístico (dos etiquetas) | **✅ CERRADO** en `v2.88.116-beta` |
| `H1.1` (AUDITORIA 1) | declarar `independent_sample` bastaba para `MEASURED`, sin verificar procedencia | **✅ CERRADO** aquí (graceful: sin evidencia ⇒ `NOT_MEASURED`) |
| `H2` (AUDITORIA 1) | identidad de estrategia ambigua en el plegado de la banda | **✅ CERRADO** en `v2.88.115-beta` |
| `H3` (AUDITORIA 1) | reutilización de informes de sorteos previos | **✅ CERRADO** en `v2.88.115-beta` |
| `P1` (AUDITORIA 2) | atribución cruzada de dinero entre estrategias en `estudio_audit` | **✅ CERRADO** en `v2.88.115-beta` |
| `R-ev` | regenerar `finance-band-w32-k12.json` con el esquema nuevo | **✅ CERRADO** en `v2.88.119-beta` (`oos-finance-band-v4`; era `⏳ PENDIENTE` aquí; reproducible con PostgreSQL sembrado) |
| `P3-2`/`P3-3` | validación longitudinal PAPER por activo | **⏳ ABIERTO** (evidencia de replay **no** sustituye ventana PAPER) |

- **Revisión independiente:** la revisión Bugbot solicitada **no pudo completarse** (el validador de hallazgos descartó sus resultados en dos intentos). Se declara y se sustituye por la comprobación empírica de bordes de §3.

---

## 5. Gates

| Gate | Resultado (local) |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed** |
| `mypy packages/py/application/src --follow-imports=silent` | **263 source files, no issues** |
| `pytest packages/py/application/tests -q` | **2705 passed** |
| `pytest` focales (bandas + render CLI) | **48 passed** |
| `pytest apps/api-python/tests/test_dia_d_bump_guard.py` | **1 passed** |
| `alembic heads` | `053_dia_d_cycle_verifications (head)` — **sin migración** |
| `Release tag CI` (autoridad externa) | [`38302937561`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302937561) **VERDE** (`replay-repro` **`success`**) |

---

## 6. Sello

- **Producto:** `V2.88.117-beta`. **Package:** `2.11.117-beta`. **Sin migración** (head `053`). **Contrato sin cambio.** **`Δ motor ≠ 0` aditivo · `Δ decisión = 0`.**
- **Añadidos:** `docs/engineering/evidence/v2.88.117/README.md`, `docs/engineering/plan-v2-88-117-h1-1-procedencia-estadistica-2026-10-12.md`, este documento.
- **Modificados:** `packages/py/application/src/bolsa_application/{dia_d_multi_uncertainty.py,oos_finance_band.py,dia_d_multi_sampling.py}`; tests de aplicación; `package.json` + `apps/api-python/scripts/v2_87` y `v2_89`…`v2_97` (`meta.bump`); `CHANGELOG.md`; `docs/engineering/PROJECT_STATE.md`.
- **Tag anotado `v2.88.117-beta`** (objeto `277d33ca` → commit `2195ad7f`): `Release tag CI` [`38302937561`](https://github.com/jvelasca/Bolsa_V1/actions/runs/38302937561) **VERDE** (`11m39s`; 12 jobs + `certify`; `replay-repro` **`success`**); resto de workflows del tag y CI de rama (`main`, `2195ad7f`) **VERDES**. `origin/main` == `HEAD` == `2195ad7f`. **Tag unsigned** (declarado).

---

## 7. Guion de auditoría desde GitHub

1. **Evidencia.** Abrir [`docs/engineering/evidence/v2.88.117/README.md`](https://github.com/jvelasca/Bolsa_V1/blob/v2.88.117-beta/docs/engineering/evidence/v2.88.117/README.md).
2. **Entrega MIA.** Leer este documento.
3. **`Δ decisión = 0`.** Revisar `dia_d_multi_uncertainty.band_validity`: **solo** compone el bloque `validity`; no cambia selección, umbrales ni reparto.
4. **`H1.1` — que la declaración no baste.** `test_dia_d_multi_uncertainty.py::test_h1_1_independent_sample_without_provenance_is_not_measured` y `::test_h1_1_incomplete_provenance_declares_the_missing_field` fijan los huecos; `::test_h1_1_venue_seeded_data_cannot_claim_independence` fija la contradicción.
5. **`H1.1` — misma puerta en dinero.** `test_oos_finance_band.py::test_h1_1_*` replica los tres desenlaces; el esquema publicado es `oos-finance-band-v4`.
6. **Reproducción local.**
   ```bash
   uv run ruff check packages/py apps/api-python --config pyproject.toml
   uv run mypy packages/py/application/src --follow-imports=silent
   uv run pytest packages/py/application/tests -q
   uv run pytest packages/py/application/tests/test_dia_d_multi_uncertainty.py packages/py/application/tests/test_oos_finance_band.py apps/api-python/tests/test_replay_oos_cli_renderers.py -q
   uv run pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
   (cd packages/py/infrastructure && uv run alembic heads)   # 053_dia_d_cycle_verifications (head)
   ```
7. **Qué falsaría el sello:** que `statisticalConfidence.status` volviera a `MEASURED` sin procedencia completa · que un `seed_shift` no bloqueara la independencia declarada · que `_provenance_gaps` levantara con input malformado · que apareciera una migración o un cambio de contrato no declarados · que `replay-repro` dejara de reproducir el artefacto congelado.
