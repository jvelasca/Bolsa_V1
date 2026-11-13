# Cohorte DÍA-D as-run con datos reales — 2026-11-13

**Nivel 3 del plan de sellado.** Resultado real de la rejugada retrospectiva DÍA-D sobre la base de datos de
desarrollo, con la función pura de certificación del repositorio. **No** se ha sembrado ningún dato, **no** se
ha bajado ningún umbral y **no** se ha fabricado ninguna posición. El único artefacto publicado como
`certified` es el que `certify_artifact` certifica.

**Veredicto de cohorte:** `insufficient_sample` — **2 días certificados de 12 exigidos**
(`insufficient_sample:3/12`, 3 artefactos presentados, 2 certificados).

## 1 · Preflight de solo lectura

Consultas ejecutadas contra `DATABASE_URL` (PostgreSQL local, sin escrituras):

| Medida | Valor |
| --- | --- |
| Cuentas con `sim_auto_positions` | 47 |
| Posiciones durables | 54 |
| Símbolos con barras `1d` | 8 |
| Símbolos **sin** barras `1d` | 46 |
| Fills en `sim_fill_finance_context` | 765 |
| Días distintos con fills | 10 |
| Barras `1d` totales | 226.997 |
| Rango de barras `1d` | 2021-10-27 → 2026-11-12 |

**Hueco declarado, no sustituido:** 46 de las 47 cuentas sostienen una posición cuyo símbolo **no tiene ni una
barra `1d`** en `ohlcv_bars`. Esas cuentas no pueden producir un artefacto medible: sin barras no hay replay
secuencial ni benchmark. No se han rellenado con datos sembrados ni se han inventado velas para completarlas.

Sólo **una** cuenta (`1484e253d2d54645945a6b1d7`) tiene las 8 posiciones cubiertas por barras `1d` y, por
tanto, es la única fuente real de días D.

## 2 · Selección de días D

Criterio: días con fills reales de esa cuenta (estado durable, no backdating). Resultado: **3 días** con
actividad — `2026-11-05`, `2026-11-09` y `2026-11-10`. El resto de días del histórico de la cuenta no tiene
fills y no constituye un D observable.

## 3 · Ejecución

Comando por día (universo declarado, barras verificadas contra la fuente):

```text
python apps/api-python/scripts/v2_102_dia_d_as_run.py \
  --at <D> --account-id 1484e253d2d54645945a6b1d7 \
  --universe-instrument <inst>… (8, repetido por instrumento) \
  --verify-bars --json --out operability_runs/dia-d-as-run/<cuenta>/as-run-<D>.json
```

Artefactos sellados (hash del artefacto, no del fichero):

| Día | `hash` | `status` |
| --- | --- | --- |
| 2026-11-05 | `6937e296d8d48250d2431607b8a5b4d96cdae14da1fad7c09cc04355387ccaf9` | `measured` |
| 2026-11-09 | `141ebdf1ec32efe4ea2921a8ddcc52094e93e8c10f6ecb15bd7ea2dfbe813c39` | `measured` |
| 2026-11-10 | `b5c765c6a1fc7e0c0fe9df4e7adfe19fbb8dd71412fe4bb47c4ba2268142274c` | `measured` |

Los tres pasan `--verify-bars`: el `barsManifest` declarado coincide con las barras leídas de `ohlcv_bars`.
`gaps` por artefacto: 2, 2 y 3 respectivamente (declarados en el propio artefacto).

## 4 · Certificación de cohorte

Invocación puntual de `certify_cohort(artifacts)` (script en memoria, **sin commit y sin bump**):

```json
{
  "version": "DiaDCertificationV1",
  "verdict": "insufficient_sample",
  "certified": false,
  "samples": 3,
  "required": 12,
  "certifiedDays": ["2026-11-05", "2026-11-09"],
  "failed": [
    {
      "day": "2026-11-10",
      "verdict": "not_certified",
      "reasons": ["benchmarks:benchmark_not_measured:as_run"]
    }
  ],
  "reasons": ["insufficient_sample:3/12"],
  "hash": "99e4b735aae4f48b3a6f974202d954dbbba6a720aa84e7bad414542ebcd22f1c"
}
```

**Lectura honesta del fallo de `2026-11-10`:** ese D no tiene ningún ciclo de venta cerrado dentro de la
ventana `D → toDay`, así que el brazo `as_run` no se puede medir y `benchmarks` lo declara
`benchmark_not_measured:as_run`. No es un error del artefacto: es ausencia real de material medible. `hold_structural`
sí mide ese día (`realizedR = 6.599107`), pero el camino as-run no.

## 5 · Lo medido, por día (sin presentarlo como rentabilidad)

Métricas internas del replay (`realizedR`, `toDay = 2026-11-13`, coste 32 bps):

| Día | `as_run` | `hold_structural` | `market_bh` | Certificación |
| --- | --- | --- | --- | --- |
| 2026-11-05 | `-1.325811` | `-1.428287` | medido (`capitalBasis=initial_notional`) | `certified` (8/8 PASS) |
| 2026-11-09 | `34.211983` | `10.894597` | medido (`capitalBasis=initial_notional`) | `certified` (8/8 PASS) |
| 2026-11-10 | no medido | `6.599107` | medido | `not_certified` |

**Esto no es una medida de rentabilidad de la estrategia.** Es una rejugada de 3 sesiones de una sola cuenta
sobre 8 instrumentos, con 2 muestras certificadas. Un `realizedR` de `34.21` en un día no acredita nada sobre
el sistema: la muestra es insuficiente por construcción y el veredicto lo dice.

## 6 · Defecto encontrado y corregido durante la cohorte

La primera pasada falló en **todas** las cuentas con `bars_unexpected:<instrumento>`. Causa real:
`verify_bars_manifest` trataba el **doble vacío** (el manifiesto declara `[]` y las barras aportadas también
están vacías) como una huella rota. Es decir, un hueco de datos se reportaba como manipulación del manifiesto y
el artefacto no se podía publicar nunca.

Corregido en el cierre as-run (commit `dbd14e5f`, PR #115) con regresión explícita en
`test_dia_d_as_run_eval.py`: el doble vacío se acepta como hueco declarado, mientras que **declarar velas que
no se aportaron sigue siendo `bars_unexpected`**. La verificación no se relajó: se distinguió «no hay datos»
de «los datos no coinciden».

## 7 · Qué falta para llegar a 12 (sin tocar el umbral)

1. **Cobertura `1d` de los 46 símbolos hoy sin barras.** Es el bloqueo principal: sin barras no hay replay.
   La fuente legítima es el propio pipeline de ingesta (`ohlcv_bars`), no un sembrado manual.
2. **Más días con fills reales en cuentas cubiertas.** Hoy sólo una cuenta tiene posiciones con barras y sólo
   3 días con actividad. Se necesitan al menos 12 D observables; cada D extra debe traer ventana hacia delante
   y cierres dentro de la ventana para que `as_run` sea medible.
3. **Cuentas adicionales cubiertas**, para no depender de una sola cuenta.

Ninguna de esas tres condiciones se satisface bajando `DEFAULT_MIN_COHORT_SAMPLES`, rellenando velas a mano ni
certificando artefactos que `certify_artifact` no certifica.

## 8 · Invariantes respetados

- `activationAllowed` sigue `false`; este trabajo no lo toca ni lo automatiza.
- Sin bump: `2.11.189-beta` es la versión declarada.
- Sin cambios de umbrales ni de reglas de decisión.
- Sin datos sembrados: los 46 símbolos sin barras quedan declarados como hueco.
- Los artefactos viven en `operability_runs/` (ignorado por git); lo que se publica es esta evidencia y los
  hashes, no los JSON.

## 9 · Reproducción

```text
# preflight (solo lectura)
SELECT count(DISTINCT account_id) FROM sim_auto_positions;                     -- 47
SELECT count(*) FROM sim_auto_positions;                                       -- 54
SELECT count(*) FROM ohlcv_bars WHERE timeframe = '1d';                        -- 226997

# un día
python apps/api-python/scripts/v2_102_dia_d_as_run.py --at 2026-11-09 \
  --account-id 1484e253d2d54645945a6b1d7 \
  --universe-instrument <inst> … --verify-bars --json \
  --out operability_runs/dia-d-as-run/1484e253d2d54645945a6b1d7/as-run-2026-11-09.json

# cohorte (invocación puntual, sin commit)
python -c "from bolsa_application.dia_d_certification import certify_cohort; ..."
```
