# Evidencia `v2.88.115-beta` — Endurecimiento de la banda OOS: identidad ambigua (`H2`), no reutilización de artefactos (`H3`) y atribución financiera honesta (`P1`)

> **Sello:** `v2.88.115-beta` (base `v2.88.114-beta`).
> **Bump:** `2.11.114-beta` → **`2.11.115-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87` y de los 9 CLIs `v2_89`…`v2_97`).
> **Naturaleza:** sello **correctivo/aditivo** · **`Δ motor ≠ 0`** (dominio puro de auditoría + orquestador **opt-in**) · **`Δ decisión = 0`** (no toca decisión/ejecución, umbrales, `TOP_N`, régimen ni reparto) · **SIN migración** (head `053_dia_d_cycle_verifications`) · **contrato SIN cambio**.
> **Cierra:** `P1` de la **AUDITORIA 2** (`estudio_audit` atribuía dinero de OTRA estrategia a un valor con identidad propia) y los hallazgos **`H2`** y **`H3`** de la **AUDITORIA 1** sobre la banda `K` de `v2.88.114-beta`.
> **Fecha:** 2026-10-12.

---

## 1. Qué cambia (correctivo/aditivo)

| Pieza | Fichero | Contenido |
| --- | --- | --- |
| **`P1` atribución EXACTA** | [`estudio_audit.py`](../../../../packages/py/application/src/bolsa_application/estudio_audit.py) | `_pick_finance_group`: con identidad **declarada** y sin coincidencia, un grupo con **OTRA** clave **NO** se usa. El fallback «grupo único» solo aplica si el valor **no** declara identidad, o si el único grupo tampoco la declara. Cuando hay grupos del símbolo pero ninguno declara la clave del valor, el hueco se declara con motivo explícito (**«Sin dato todavía»**, nunca atribución cruzada). |
| **`H2` identidad ambigua** | [`oos_finance_band.py`](../../../../packages/py/application/src/bolsa_application/oos_finance_band.py) | `_fold` recoge **todas** las claves `strategyPresetKey` distintas por cubo entre los `K` sorteos: una sola ⇒ identidad; **más de una** ⇒ `strategyPresetKey = None` + `strategyPresetKeyAmbiguous = True` + `strategyPresetKeys[]` con todas (ninguna «ganadora»); ninguna ⇒ hueco (`None`, no ambiguo). Determinista bajo permutación. `SCHEMA_VERSION` `oos-finance-band-v1` → **`v2`**. |
| **`H3` sin reutilización** | [`v2_87_replay_oos_durable_cycle.py`](../../../../apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py) | `_run_finance_band`: **purga** restos previos al arrancar; por sorteo **borra y verifica ausencia** de sus salidas antes de lanzar; tras el subproceso exige reporte **nuevo** (`mtime` posterior al lanzamiento) y **bien formado**, y valida los metadatos del payload (**cuenta**, **versión A** y **ventana** declarada) antes de plegarlo. |
| **Pruebas puras** | [`test_oos_finance_band.py`](../../../../packages/py/application/tests/test_oos_finance_band.py) · [`test_estudio_audit.py`](../../../../packages/py/application/tests/test_estudio_audit.py) · [`test_replay_oos_cli_renderers.py`](../../../../apps/api-python/tests/test_replay_oos_cli_renderers.py) | `H2`: ambiguo/consistente/ausente/agregado + invariancia por permutación. `P1`: grupo único con otra clave no se atribuye; grupo sin clave sí se usa si el valor declara preset. `H3`: purga, reset+ausencia, rechazo de reporte reutilizado, aceptación de reporte nuevo, y validación de cuenta/versión/ventana del payload. |

---

## 2. `H2` — identidad ambigua, sin «ganadora» arbitraria

En `v2.88.114-beta` el plegado conservaba la **primera** clave no vacía de cada cubo (`presets.get(key) is None`): si dos sorteos declaraban claves **distintas** para el mismo `(strategyVersion, symbol)`, la banda publicaba **una** de ellas como si fuera la identidad del motor.

Ahora el cubo declara la identidad solo si **todos** los sorteos que la declaran coinciden:

```json
{
  "strategyVersion": "…",
  "symbol": "…",
  "strategyPresetKey": null,
  "strategyPresetKeyAmbiguous": true,
  "strategyPresetKeys": ["breakout_v3", "mean_reversion_v1"],
  "drawsWithCell": 2,
  "bands": { "…": {} }
}
```

`SCHEMA_VERSION` sube a **`oos-finance-band-v2`** (cambio de forma) y `DEFAULT_LIMITS` declara la regla. La ordenación del conjunto de claves hace el veredicto **invariante** ante permutación de los sorteos.

---

## 3. `H3` — la banda solo se pliega con artefactos REGENERADOS

El orquestador leía el reporte por su mera **existencia**: una corrida previa podía dejar `draw-NN.finance.json` y un sorteo posterior con código `0` sin regenerarlo hacía pasar por nuevo un informe **viejo**.

Correcciones aplicadas (todas en `_run_finance_band`, opt-in `--finance-band K`):

1. **Purga inicial** de `draw-*.finance.json` / `draw-*.payload.json` de la carpeta de sorteos.
2. Por sorteo: `_reset_draw_outputs` **borra y verifica la AUSENCIA** de las dos salidas antes de lanzar el subproceso (si algo sobrevive ⇒ `ABORTO`).
3. Tras el subproceso: `_read_fresh_draw_report` exige **frescura** (`mtime` posterior al lanzamiento) y **forma** válida (`groups[]` + `aggregate`).
4. `_validate_draw_payload` verifica **cuenta**, **versión A** y **ventana** (`startDay`/`endDay`) del payload del sorteo antes de incorporarlo.

La banda sigue viviendo en fichero **aparte** y con el flag **apagado por defecto** ⇒ el payload del sello `replay-repro` **no** se mueve.

---

## 4. Verificación (local)

| Compuerta | Resultado |
| --- | --- |
| `ruff check packages/py apps/api-python --config pyproject.toml` | ✅ `All checks passed!` |
| `mypy packages/py/application/src --follow-imports=silent` | ✅ `Success: no issues found in 263 source files` |
| `pytest packages/py/application/tests -q` | ✅ **2691 passed** + **1 fallo AMBIENTAL** declarado (`ImportError: DLL load failed … _devicearray` — Windows Application Control bloqueó una DLL de numpy/`numba`; **ajeno** al código tocado) |
| `pytest apps/api-python/tests/test_replay_oos_cli_renderers.py` | ✅ **15 passed** |
| `pytest test_dia_d_bump_guard + test_ci_test_selection_census + test_oos_finance + test_oos_finance_band + test_estudio_audit` | ✅ **42 passed** |
| `pytest apps/api-python/tests/test_auto_estudio_audit_route.py` | ✅ **6 passed** |

> El fallo ambiental se **declara**, no se disimula: es un `ImportError` de una DLL nativa bloqueada por la política de Control de Aplicaciones de Windows, no un fallo lógico; el resto de la batería pasa sin cambios.

---

## 5. Límites declarados

- **Compone/observa, no decide:** `Δ decisión = 0`; no toca motor, umbrales, `TOP_N` ni reparto.
- **El artefacto de evidencia de `v2.88.114` (`finance-band-w32-k12.json`) sigue siendo `oos-finance-band-v1`:** regenerarlo en `v2` exige PostgreSQL con la entrada sembrada (`replay-repro` fixture) ⇒ **no reproducible sin PG** y **no** se finge. La forma nueva está fijada por tests puros.
- **Banda, no punto:** sigue vigente `pointCitable = False` mientras la banda cruce cero; este sello **no** convierte el sorteo del venue en una propiedad del motor.
- **`H1` (AUDITORIA 1) sigue ABIERTO:** la separación formal de la sensibilidad del simulador (`sensitivityBand`) frente a la inferencia estadística (`statisticalConfidence`) no se aborda aquí.
- **Tag `unsigned`:** el tag anotado no está firmado (la verificación de GitHub reporta `unsigned`).

---

## 6. Residuos

| ID | Descripción | Estado |
| --- | --- | --- |
| `P1` (AUDITORIA 2) | atribución cruzada de dinero entre estrategias en `estudio_audit` | **✅ CERRADO por este sello** |
| `H2` (AUDITORIA 1) | identidad de estrategia «elegida por orden de llegada» en el plegado de la banda | **✅ CERRADO por este sello** |
| `H3` (AUDITORIA 1) | posible reutilización de informes de sorteos previos en `_run_finance_band` | **✅ CERRADO por este sello** |
| `H1` (AUDITORIA 1) | sensibilidad del simulador vs inferencia estadística (`pointCitable`) | **⏳ ABIERTO** (sello propio) |
| `R-ev` | regenerar `finance-band-w32-k12.json` con el esquema `v2` | **⏳ PENDIENTE** (requiere PostgreSQL) |

---

## 7. Cita POST-TAG

**PENDIENTE** (tag `v2.88.115-beta` por publicar desde esta sesión). La cita se completa con el `Release tag CI` resuelto en GitHub.
