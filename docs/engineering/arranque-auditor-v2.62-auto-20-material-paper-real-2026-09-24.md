# Arranque del AUDITOR — `v2.62-beta` (`AUTO-20` · material PAPER real + cierre de O1/O2)

Eres el auditor **independiente** de esta fase. Audítala **contra el tag**, no contra el resumen del
autor. Contexto: [plan](./plan-v2-62-auto-20-material-paper-real-2026-09-24.md) ·
[audit-pack](./audit-pack-v2-62-auto-20-material-paper-real-2026-09-24.md).

## 1. Qué se afirma (y qué NO)

**Se afirma:** el instrumento de calibración **declara** el material que no pudo medir (O1), su ratio
de walk-forward **no mezcla** muestras distintas (O2), y el material PAPER real **puede** llegar al
instrumento con su base de riesgo por la MISMA costura que el informe durable.

**NO se afirma:** que la estrategia tenga edge, ni que la incertidumbre esté calibrada **en datos
reales** (el fixture es sintético), ni que el exportador esté probado end-to-end.

## 2. Cómo empezar

```powershell
git checkout v2.62-beta
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync pytest packages/py/analytics/tests packages/py/application/tests -q
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M165 M166 M167 M168
```

## 3. Los seis puntos donde atacaría

1. **¿O1 se declara de verdad, o se declara mal?** Una versión con **algunas** filas sin R **no**
   debe salir como `unmeasured_r`: solo la que **no tiene ninguna** medible. Y una versión **con**
   material medible no debe cambiar de salida.
2. **¿O2 empareja o sigue mezclando?** Construye pliegues con IS y OOS de conjuntos distintos y
   comprueba que `walkForwardEfficiency` usa **solo** los emparejados (y que los cuatro conteos no se
   contradicen).
3. **¿La costura del material es la MISMA que el informe?** `adaptive_instrument_cycles` debe
   devolver exactamente `_cycles_with_risk`; si alguien reimplementara el pegado del riesgo, la
   calibración y el informe podrían medir ciclos distintos.
4. **¿El exportador miente sin PG?** Sin base de datos debe salir **2 (BLOQUEADO)**, nunca un JSON
   vacío leído como "sin edge".
5. **¿El sello del reparto se movió?** `ADAPTIVE_POLICY_VERSION` (`auto18-v1`) y
   `DATA_GATE_POLICY_VERSION` (`auto15-v1`) intactos; `governor.json` byte a byte.
6. **¿Se colaron cambios no declarados?** El replay (`auto_adaptive_replay.py`, contrato
   `statistical_oos_v1`) **no** debe haber cambiado.

## 4. Trampas declaradas (no son fallos, están escritas)

* **O1 se cierra solo en la calibración**, no en el replay: el replay es el contrato sellado de
  `AUTO-19A`. Si lo ves sin `unmeasured_r`, es **a propósito**.
* **`CALIBRATION_METHOD` sube a `v2`**: es un cambio **buscado**. Un informe `v2` no es comparable
  campo a campo con uno `v1`.
* **El exportador no está ejercitado end-to-end**: declarado como deuda en el plan (§9) y en el
  relevo (§4). No lo leas como verificado.

## 5. Qué entregar

Un veredicto con lo **verificado** (con su comando y su salida), los **hallazgos** con severidad, y
lo que la fase **no** cubre. Si un punto del §3 no lo pudiste romper, dilo — eso también es resultado.
