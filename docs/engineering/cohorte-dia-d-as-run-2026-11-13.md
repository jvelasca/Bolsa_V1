# Cohorte DÍA-D as-run con datos reales — 2026-11-13

**Nivel 3 del plan de sellado.** Resultado real de la rejugada retrospectiva DÍA-D sobre la base de datos de
desarrollo, con la función pura de certificación del repositorio. **No** se ha sembrado ningún dato, **no** se
ha bajado ningún umbral y **no** se ha fabricado ninguna posición.

**Veredicto de cohorte:** `insufficient_sample` — **2 días certificados de 12 exigidos**
(`insufficient_sample:4/12`: 4 artefactos presentados, 2 certificados).

> **Corrección de la primera versión de este documento (2026-11-13, mismo día).** La versión que entró en
> `main` con el PR #117 daba por buenos cuatro datos que no lo eran, porque el preflight no separó **residuo
> huérfano** de **universo real**. La §7 recoge el error, la causa y lo que se ha corregido. Los números de
> arriba sustituyen a los publicados.

> **Segunda actualización (2026-11-13, mismo día).** El veredicto y la tabla de §5 son los del artefacto **anterior**
> a la reparación del instrumento. Reparadas las cinco causas del `not_certified`
> ([reparación del instrumento as-run](reparacion-as-run-2026-11-13.md), `2.11.191-beta`), los **cuatro** días
> certifican: el veredicto pasa a `insufficient_sample` con `failed = (ninguno)` y motivo único
> `insufficient_sample:4/12`. La cohorte no certifica por falta de muestra, no por falta de medición.
>
> La reparación también **cambia lo que el instrumento dice de `2026-11-09`**: sus 4 ventas sin compra observable eran
> una posición real (BAS) cuya pérdida no se imputaba, así que la caja del día pasa de `+18.18` a **`−697.70`**. El
> artefacto anterior certificaba con el signo del día invertido.

## 1 · Preflight de solo lectura (corregido)

Consultas ejecutadas contra `DATABASE_URL`, sin escrituras. La distinción clave es si la fila apunta a
entidades que **existen**: `sim_auto_positions` y `sim_fill_finance_context` **no tienen claves foráneas**
(solo PK), así que aceptan filas de cuentas e instrumentos borrados.

| Medida | Valor |
| --- | --- |
| Cuentas en `investment_accounts` | **2** (`default-account-seed` y la cuenta PAPER de la ventana) |
| `account_id` distintos en `sim_auto_positions` | 47, de los que **46 no existen** en `investment_accounts` |
| Posiciones totales | 54 |
| Posiciones reales (cuenta **e** instrumento existen) | **8** |
| Posiciones huérfanas (cuenta o instrumento inexistente) | **46** (la misma fila falla por ambos lados) |
| Fills totales en `sim_fill_finance_context` | 765 |
| Fills de cuentas inexistentes | **722** |
| Fills de la cuenta de la ventana | **43** |
| Días con fills reales | **4** (`2026-11-05`, `2026-11-06`, `2026-11-09`, `2026-11-10`) |
| Instrumentos en catálogo | 197 |
| Instrumentos del catálogo sin barras `1d` | 16 |
| Instrumentos de la ventana con barras `1d` | **8 de 8** |
| Barras `1d` totales | 226.997 |
| Rango de barras `1d` | 2021-10-27 → 2026-11-12 |

**El residuo no es un hueco de datos.** Las 46 filas apuntan a ids `inst-a11-*`, la familia sintética que crean
los tests de A11, cuyos instrumentos ya no están en `instruments`. No hay nada que sincronizar: un instrumento
que no existe no se puede cubrir con el pipeline de ingesta. Se declaran como lo que son, residuo, y se
excluyen del universo.

**El hueco real es otro y es menor:** 16 instrumentos **del catálogo** (con `yahoo_symbol` real) no tienen
barras `1d`. No bloquean esta cohorte porque la ventana opera 8 instrumentos distintos, todos cubiertos.

## 2 · Selección de días D

Criterio: días con fills reales de la cuenta de la ventana. Son **4**, y los cuatro se rejuegan. La primera
versión sólo presentó tres porque el `JOIN` con posiciones descartó `2026-11-06`, que sí tiene 4 fills.

## 3 · Ejecución

```text
python apps/api-python/scripts/v2_102_dia_d_as_run.py \
  --at <D> --account-id 1484e253d2d54645945a6b1d7 \
  --universe-instrument <inst>… (8, repetido por instrumento) \
  --verify-bars --json --out operability_runs/dia-d-as-run/<cuenta>/as-run-<D>.json
```

Universo declarado, los 8 instrumentos con barras de la cuenta:

`02f4563312794f9a813d60f1a` · `0ade61bff8ea4005b1dcbbaef` · `0fc9b8cad8474e0f811568bb9` ·
`103c29b5256749c0a93550397` · `1c55566d5eac48ffa9566ea48` · `2323f09f3b7f42399e69735a6` ·
`320b1fcc2a4d453da942684c5` · `34673ecf981044e986cf670e7`

Artefactos sellados (hash del artefacto):

| Día | `hash` | `status` | `gaps` |
| --- | --- | --- | --- |
| 2026-11-05 | `6937e296d8d48250d2431607b8a5b4d96cdae14da1fad7c09cc04355387ccaf9` | `measured` | 2 |
| 2026-11-06 | `6c2f9bd16663679d0d1504076b9afda912d43bb000c4bb41bd2915f7032d233e` | `measured` | 3 |
| 2026-11-09 | `141ebdf1ec32efe4ea2921a8ddcc52094e93e8c10f6ecb15bd7ea2dfbe813c39` | `measured` | 2 |
| 2026-11-10 | `b5c765c6a1fc7e0c0fe9df4e7adfe19fbb8dd71412fe4bb47c4ba2268142274c` | `measured` | 3 |

Los cuatro pasan `--verify-bars`: el `barsManifest` declarado coincide con las barras leídas de `ohlcv_bars`.

## 4 · Certificación de cohorte

Invocación puntual de `certify_cohort(artifacts)` (script en memoria, **sin commit y sin bump**):

```json
{
  "version": "DiaDCertificationV1",
  "verdict": "insufficient_sample",
  "certified": false,
  "samples": 4,
  "required": 12,
  "certifiedDays": ["2026-11-05", "2026-11-09"],
  "failed": [
    { "day": "2026-11-06", "verdict": "not_certified", "reasons": ["benchmarks:benchmark_not_measured:as_run"] },
    { "day": "2026-11-10", "verdict": "not_certified", "reasons": ["benchmarks:benchmark_not_measured:as_run"] }
  ],
  "reasons": ["insufficient_sample:4/12"],
  "hash": "e8f3b2585a4b042263cb5a4dacbdf557e2e0af5388ee3e4aa5c2f77bb8e02a7b"
}
```

**Lectura honesta de los dos fallos (corregida el mismo día):** la versión inicial de este documento afirmaba que
ninguno de los dos días tenía un ciclo de venta cerrado. **Era falso para `2026-11-06`**, y los dos fallos tienen
causas distintas. El diagnóstico completo está en
[`cohorte-dia-d-benchmark-no-medido-2026-11-13.md`](cohorte-dia-d-benchmark-no-medido-2026-11-13.md):

| Día | Lotes cerrados | `pnlCurrency` | Motivo real | Certifica |
| --- | --- | --- | --- | --- |
| `2026-11-05` | 16 (sólo 4 con riesgo) | — | — | sí |
| `2026-11-06` | **12** | `-697.70` | `no_risk_reference`: el denominador de riesgo se busca sólo en las patas de `D` y `_read_legs` lee únicamente posiciones **abiertas** (`quantity > 0`), así que las cerradas desaparecen. El stop inicial sí está durable en `decision_journal_entries` (`PROTECT_APPLIED`). | no |
| `2026-11-09` | 8 | — | — | sí |
| `2026-11-10` | **0** | — | `no_closed_cycles`: `run_as_run_arm` arranca `open_lots` vacío y descarta 8 ventas de posiciones abiertas en `D` como `unmatched_sell`. | no |

No es «ausencia real de material medible»: es el **instrumento** midiendo de menos. Son defectos reparables del
as-run (no del motor), y bajarlos de categoría sin repararlos sería maquillar la medición. El brazo
`hold_structural` sí mide esos días (`-0.684159` y `6.599107`), pero el camino as-run no, y es el as-run el que
certifica.

**Dos avisos que el diagnóstico añade sobre las muestras ya certificadas:** `2026-11-05` certifica midiendo sólo
**4 de 16** lotes cerrados, y el `34.21` de `2026-11-09` sale de un trailing stop por **encima** del precio de
entrada (`23.93` frente a `24.1088`); con el stop inicial daría `≈3.19`. La certificación de esos dos días es
correcta según las reglas actuales, pero su R no mide lo mismo que el de un día sin ese efecto.

## 5 · Lo medido, por día (sin presentarlo como rentabilidad)

Métricas internas del replay (`realizedR`, `toDay = 2026-11-13`, coste 32 bps):

| Día | `as_run` | `hold_structural` | `market_bh` | Certificación |
| --- | --- | --- | --- | --- |
| 2026-11-05 | `-1.325811` | `-1.428287` | medido (`capitalBasis=initial_notional`) | `certified` (8/8 PASS) |
| 2026-11-06 | no medido | `-0.684159` | medido | `not_certified` |
| 2026-11-09 | `34.211983` | `10.894597` | medido (`capitalBasis=initial_notional`) | `certified` (8/8 PASS) |
| 2026-11-10 | no medido | `6.599107` | medido | `not_certified` |

**Esto no es una medida de rentabilidad de la estrategia.** Son 4 sesiones de una sola cuenta sobre 8
instrumentos, con 2 muestras certificadas. Un `realizedR` de `34.21` en un día no acredita nada sobre el
sistema: la muestra es insuficiente por construcción y el veredicto lo dice.

## 6 · Defecto corregido durante la cohorte

La primera pasada falló en **todas** las cuentas con `bars_unexpected:<instrumento>`. Causa real:
`verify_bars_manifest` trataba el **doble vacío** (el manifiesto declara `[]` y las barras aportadas también
están vacías) como una huella rota, así que un hueco de datos se reportaba como manipulación del manifiesto y
el artefacto no se podía publicar nunca.

Corregido en el cierre as-run (commit `dbd14e5f`, PR #115) con regresión explícita en
`test_dia_d_as_run_eval.py`: el doble vacío se acepta como hueco declarado, mientras que **declarar velas que
no se aportaron sigue siendo `bars_unexpected`**. La verificación no se relajó: se distinguió «no hay datos»
de «los datos no coinciden».

## 7 · Corrección de la primera versión (autoauditoría)

Lo que la primera versión afirmaba y lo que dicen las consultas:

| Primera versión (PR #117) | Realidad | Por qué |
| --- | --- | --- |
| «47 cuentas con `sim_auto_positions`» | **2 cuentas**; 47 son `account_id` distintos, 46 inexistentes | El preflight contó ids de una tabla **sin FK**, no cuentas |
| «765 fills, 10 días con fills» | **43 fills reales, 4 días**; 722 fills de cuentas inexistentes | Misma causa: se contó la tabla entera |
| «3 días D, 3 artefactos» | **4 días D, 4 artefactos** | El `JOIN` con posiciones descartó `2026-11-06` |
| «46 cuentas sin cobertura `1d`; se arregla cubriendo esos símbolos por ingesta» | **46 filas huérfanas sobre instrumentos inexistentes**; no hay nada que sincronizar | Se confundió residuo con hueco de datos y se propuso un camino imposible |

La causa raíz es una sola: **contar filas sin comprobar que sus referencias existen**. La lección se aplica al
preflight, no al motor: no cambia ninguna medición certificada, que siempre usó las barras y las cuentas reales.

### El residuo no lo limpia la red de seguridad

`purge_all_residuals` (en `apps/api-python/tests/conftest.py`) recorre **`investment_accounts`** y purga los
instrumentos sintéticos `inst-*`. Con esta base de datos, su recuento en seco es **0 cuentas y 0 instrumentos a
borrar**, así que no toca el problema: las 46 filas huérfanas viven en una tabla **sin FK** que ni está en
`_ACCOUNT_CHILD_TABLES` ni se alcanza por el recorrido de cuentas. Se ha verificado además que la cuenta
protegida es `1484e253d2d54645945a6b1d7` (fuente única: `scripts/lib/window-forward.mjs`), la misma que sostiene
los dos días certificados.

Consecuencia práctica: **cualquier conteo de `sim_auto_positions` o `sim_fill_finance_context` sin verificar
referencias miente**. Queda como hueco abierto, no como algo arreglado por este documento.

## 8 · Qué falta para llegar a 12 (sin tocar el umbral)

1. **Acumular días de calendario en la ventana PAPER.** Hoy hay 4 días con fills de 12 exigidos. Es la única
   fuente real de D y avanza con el calendario, no con datos sembrados. Los 8 días restantes deben además
   traer cierres dentro de la ventana para que `as_run` sea medible (2 de 4 sí lo hicieron).
2. **Cubrir los 16 instrumentos del catálogo sin barras `1d`** si se quiere ampliar el universo más allá de
   los 8 instrumentos de la ventana. Aquí sí aplica el pipeline de ingesta (`SyncInstrumentDailyBars`), porque
   esos instrumentos **sí existen** y tienen `yahoo_symbol`.
3. **Cerrar el hueco del residuo**: un guardián que falle cuando `sim_auto_positions` o
   `sim_fill_finance_context` contengan referencias inexistentes, para que el preflight no pueda volver a
   contar fantasmas.

Ninguna de esas condiciones se satisface bajando `DEFAULT_MIN_COHORT_SAMPLES`, rellenando velas a mano ni
certificando artefactos que `certify_artifact` no certifica.

## 9 · Invariantes respetados

- `activationAllowed` sigue `false`; este trabajo no lo toca ni lo automatiza.
- Sin bump: `2.11.189-beta` es la versión declarada.
- Sin cambios de umbrales ni de reglas de decisión.
- Sin datos sembrados y sin borrados: esta corrección **no** ha modificado la BD.
- Los artefactos viven en `operability_runs/` (ignorado por git); lo que se publica es esta evidencia y los
  hashes, no los JSON.

## 10 · Reproducción

```text
# preflight: separar real de huerfano
SELECT count(*) FROM investment_accounts;                                      -- 2
SELECT count(*) FROM sim_auto_positions p
  WHERE EXISTS (SELECT 1 FROM investment_accounts a WHERE a.id=p.account_id)
    AND EXISTS (SELECT 1 FROM instruments i WHERE i.id=p.symbol);              -- 8
SELECT count(*) FROM sim_fill_finance_context f
  WHERE NOT EXISTS (SELECT 1 FROM investment_accounts a WHERE a.id=f.account_id); -- 722

# un día
python apps/api-python/scripts/v2_102_dia_d_as_run.py --at 2026-11-06 \
  --account-id 1484e253d2d54645945a6b1d7 \
  --universe-instrument <inst> … --verify-bars --json \
  --out operability_runs/dia-d-as-run/1484e253d2d54645945a6b1d7/as-run-2026-11-06.json

# cohorte (invocación puntual, sin commit)
python -c "from bolsa_application.dia_d_certification import certify_cohort; ..."
```
