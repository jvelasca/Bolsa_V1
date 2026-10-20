# Endurecimiento P2 de `v2.88.153-beta` — guarda fail-closed en la 057 y tri-estado de la identidad

> **Naturaleza:** cambio **acotado** sobre `v2.88.153-beta`, **sin nuevo sello** (no se mueve
> `package.json`, no hay tag, no se reescribe la evidencia publicada).
> **`Δ motor = 0`** · **`Δ decisión = 0`** · **contrato HTTP sin cambio** · **sin migración nueva**.
>
> **AUTO sigue OFF** y la ventana PAPER sigue **`INCONCLUSIVE`**. Este documento cierra dos
> hallazgos de robustez; **no** certifica operativa ni rentabilidad.

## 1. Origen

Dos auditorías independientes sobre el sello `v2.88.153-beta` coincidieron en dos mejoras **P2**
que no invalidaban el certificado pero sí dejaban un hueco de robustez:

| Hallazgo | Dónde | Por qué importa |
| --- | --- | --- |
| **A · la 057 terminaba sin error si faltaba la tabla base** | [`057_top3_opportunity_identity.py`](../../packages/py/infrastructure/alembic/versions/057_top3_opportunity_identity.py) | `upgrade()` hacía `return` si no existía `top3_opportunities`. Alembic marcaría la revisión como **aplicada** sin haber creado las columnas y el lector (`read_top3_snapshot`) fallaría después al seleccionarlas. |
| **B · `COMPLETE` con identidad parcial** | [`auto_chain_durable_reader.py`](../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py) | `strategyMeasurement` era `COMPLETE` con **solo** preset o **solo** versión. `COMPLETE` se lee como «la identidad está medida»; media identidad declarada completa afirma una cobertura inexistente. |

## 2. Cambio A — la migración 057 falla cerrado

- Nueva guarda pura `assert_base_table_present(table_exists: bool)`: no hace nada si la tabla
  existe y lanza `RuntimeError` con un mensaje accionable si falta.
- `upgrade()` la invoca **antes** de tocar el esquema: un esquema incompleto ya **no** se marca
  como migrado ni crea columnas a medias.
- `downgrade()` queda **asimétrico a propósito** y documentado: sin tabla no hay columnas que
  retirar, así que sale sin error (bajar de revisión no puede exigir un prerrequisito que la
  propia bajada puede haber eliminado).

```python
def assert_base_table_present(table_exists: bool) -> None:
    if table_exists:
        return
    raise RuntimeError(
        "057: falta la tabla base 'top3_opportunities'; la crea 052_top3_opportunities y "
        "es prerrequisito obligatorio de la cadena. Esquema incompleto: la revisión NO se "
        "marca como aplicada. Aplica la cadena hasta la 056 y reintenta."
    )
```

**Prueba falsable** — [`test_057_top3_opportunity_identity.py`](../../packages/py/infrastructure/tests/test_057_top3_opportunity_identity.py),
`test_057_upgrade_aborts_without_touching_the_schema_when_the_table_is_missing`: con un doble
de `op`, `upgrade()` lanza y **no registra ni un** `add_column`. La implementación anterior
habría pasado este test en verde con cero columnas: el test habría sido rojo con el código viejo
porque no lanzaba.

## 3. Cambio B — la identidad se mide en tri-estado

Nueva regla única `_identity_measurement(preset_measured, version_measured)`:

| Preset | Versión | Estado |
| --- | --- | --- |
| medido | medido | `COMPLETE` |
| medido | no | `PARTIAL` |
| no | medido | `PARTIAL` |
| no | no | `UNKNOWN` |

Se aplica en los **tres** puntos que publican identidad, para no crear una segunda verdad:

- `resolve_executed_vs_best` → `strategyMeasurement` (ejecutada vs mejor puntuada).
- `build_chain_evidence_artifact` → `bestScored.strategyMeasurement` (lo que **declara** la foto).
- `executed_identity` → `measurement` del bloque ejecutado; si no hay identidad pero **sí** puesto
  medido, el bloque es `PARTIAL` (el puesto no completa la identidad, pero el bloque no queda sin
  ninguna medición).

`MeasurementV1` en [`estudio-daily-ops.ts`](../../packages/shared/src/estudio-daily-ops.ts) pasa a
`"COMPLETE" | "PARTIAL" | "UNKNOWN"`. La ficha añade `· identidad: parcial (solo se pudo contrastar
uno de preset/versión)` **solo** en ese caso: los textos de `COMPLETE` y de hueco quedan idénticos.

El campo `measurement` (contraste rank/activo) **no cambia**: un hueco de identidad sigue sin
degradar una comparación de puesto que sí se pudo hacer.

## 4. Qué NO cambia

- Motor, broker, scheduler, sizing, umbrales, pesos A/B, `TOP_N`, régimen, entradas/salidas,
  orquestador y replay OOS: intactos (`Δ motor = 0`).
- El lector sigue siendo **read-only** (`SELECT`).
- La migración 057 sigue siendo **aditiva y nullable**, sin índice, sin default y **sin backfill**;
  no hay revisión nueva ni cambio de `head`.
- El contrato HTTP no cambia: `bestScored`/`executedVsBest` viajan como `dict[str, Any]`, y
  `openapi.json`/`schema.d.ts` no tienen diff (`contract:check` **OK**).
- La evidencia sellada **no se reescribe**: la §10 de `docs/engineering/evidence/v2.88.153/README.md`
  ya quedó completada post-tag en `cef3c550`; el árbol del tag (`2af7f0d9`) conserva «Pendiente»
  porque así se selló.

## 5. Verificación (medida)

| Comprobación | Resultado |
| --- | --- |
| `pytest packages/py/infrastructure/tests/test_057_top3_opportunity_identity.py` | **9 passed** |
| `pytest test_auto_chain_durable_reader.py test_auto_estudio_chain_route.py` | **27 passed** |
| `pytest packages/py/infrastructure/tests packages/py/application/tests` | **3028 passed** (4m09s) |
| `vitest src/features/auto-monitor` | **21 ficheros · 169 tests passed** |
| `pnpm typecheck` | **4 successful / 4** |
| `pnpm lint` | **0 errores**, 23 avisos preexistentes |
| `pnpm lint:py` | **`All checks passed!`** |
| `pnpm imports:py` | **`Contracts: 4 kept, 0 broken.`** |
| `pnpm types:py` | **`Success: no issues found in 567 source files`** |
| `contract:check` | **OK** (sin diff de contrato) |
| `pnpm window:test` | **50 passed** |

**Freeze.** El cambio mueve `apps` y `packages`, así que el pin PAPER se **re-ancla** al árbol
nuevo (`apps 438e9bef…` / `packages b2792181…`) para que el run de las 18:00 no aborte con
`TREE_MOVED`; tras el re-anclaje, `pnpm window:freeze` ⇒ **`freeze OK (b0d0f7b2)`**.

## 6. Límites declarados (sin fabricar)

- **No hay nuevo sello ni certificado**: la versión publicada sigue siendo `v2.88.153-beta` y su
  cita POST-TAG sigue siendo el run [`39389152689`](https://github.com/jvelasca/Bolsa_V1/actions/runs/39389152689).
- La guarda **convierte un fallo silencioso en un aborto explícito**: una base a la que le falte
  `top3_opportunities` deja de «migrar en falso» y debe reconciliarse hasta la 056. Es el
  comportamiento buscado, no una regresión.
- `PARTIAL` es una **declaración de cobertura**, no un juicio sobre el resultado: no dice que la
  estrategia ejecutada sea buena ni mala, solo qué parte de su identidad se pudo contrastar.
- La prueba demuestra **trazabilidad y robustez de esquema**, **no** rentabilidad. **AUTO sigue
  OFF**, la ventana PAPER sigue **`INCONCLUSIVE`** y la operativa es **100 % SIM**.
- Sigue pendiente, en un cambio **separado**, la batería integrada por valor (identidad ganadora →
  señal diaria → plan → ciclo SIM → DÍA-D → resultado conciliado): el CI verde no sustituye esa
  evidencia operativa.
