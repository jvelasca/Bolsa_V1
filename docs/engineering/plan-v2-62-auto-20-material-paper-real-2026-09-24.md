# Plan de fase — AUTO-20 · Material PAPER real + cierre de O1/O2 (`V2.62` / `1.87.0-beta`)

**Estado:** 🟢 SELLADA (`v2.62-beta`) · **Fecha:** 2026-09-24 · **Base de auditoría:** `f55e6921`

## 1. Por qué existe esta fase

La auditoría de `v2.61-beta` ([`auditoria-v2-61-…`](./auditoria-v2-61-auto-19b-calibracion-walk-forward-2026-09-24.md))
cerró `AUTO-19B` con **🟢 APROBADO** y **dos observaciones P3** declaradas:

* **O1** — una estrategia cuyos ciclos existen pero **ninguno tiene R medible** desaparece del informe
  **sin dejar nota** (heredado de `AUTO-19A`).
* **O2** — `aggregate.foldCount` cuenta pliegues que **no aportan** a la media OOS, y
  `walkForwardEfficiency` podía **mezclar** la media OOS de unos pliegues con la media IS de otros.

Al mirar el camino a **PAPER real** apareció el bloqueante de verdad: el material que produce
`cycles_from_fills` **no trae base de riesgo**, y `cycle_r` declara `risk_unmeasured` sin
denominador. Es decir, **la calibración sobre ciclos reales saldría vacía** —honesta, pero inútil—.
Y, en ese caso, era exactamente **O1** el que mordía: la estrategia desaparecía sin explicación.

## 2. Invariante de la fase

> **El instrumento mide el MISMO material que el informe durable, y lo que no se pudo medir se
> declara.** Nada de esta fase mueve el reparto, el worker, el plan ni el journal.

El sello del reparto sigue en **`auto18-v1`** y el del gate en **`auto15-v1`**; esta fase es
**evidencia y material**, no sizing.

## 3. Decisiones

1. **La base de riesgo entra por la MISMA costura, no por un segundo camino.** Se expone
   `adaptive_instrument_cycles` (público) que devuelve lo que ya devolvía `_cycles_with_risk`
   (`AUTO-16/17`): mismos ciclos, mismo cierre, misma fricción aplicada. Un exportador que
   reimplementara el pegado podría medir ciclos distintos en silencio.
2. **El cierre de O1 se hace en el instrumento de CALIBRACIÓN**, no en el replay. El replay
   (`statistical_oos_v1`) es el contrato sellado de `AUTO-19A`; tocar sus notas cambiaría una
   lectura ya auditada. La calibración es el instrumento que va a correr sobre datos reales, así que
   ahí se cierra. El hueco heredado del replay se **declara**, no se disimula.
3. **O1 y O2 cambian la lectura ⇒ sube el sello del instrumento.** `CALIBRATION_METHOD` pasa de
   `walk_forward_calibration_v1` a **`…_v2`**: dos informes con el mismo aspecto no pueden venir de
   instrumentos distintos (regla del propio módulo).
4. **O2 se cierra emparejando.** `walkForwardEfficiency` se calcula SOLO sobre pliegues con IS **y**
   OOS; los conteos (`foldCount`, `isFoldCount`, `oosFoldCount`, `pairedFoldCount`) se publican
   separados para que un pliegue que no aporta no se cuente como si aportara.
5. **Sin PG no hay medición, y "no medido" no se imprime como medido.** El exportador sale con
   código **2** (BLOQUEADO) si no puede leer, en vez de soltar un JSON vacío.

## 4. Flujo

```
fills durables ──┐
                 ├─► adaptive_instrument_cycles ─► JSON ─► auto_replay_battery.py --walk-forward
reservas (AUTO-9)┤        (misma costura             │              │
régimen (AUTO-10)┘         que el informe)           │              ▼
                                              riskAmount/cost   walk_forward_calibration_v2
```

`paper_cycles_export.py` es el único sitio con I/O; el resto es puro.

## 5. Pasos

1. Cerrar **O1** en `build_calibration_report`: notas `unmeasured_r:<version>` y
   `unversioned_cycles`; subir `CALIBRATION_METHOD`.
2. Cerrar **O2** en `_aggregate`: WFE sobre pliegues emparejados + cuatro conteos publicados.
3. Exponer **`adaptive_instrument_cycles`** (público) sobre `_cycles_with_risk`.
4. Añadir el **exportador** `apps/api-python/scripts/paper_cycles_export.py` (fills → reservas →
   régimen → JSON) y la nota de material REAL.
5. Tests de O1, O2 y de la costura del material; no-regresión de `AUTO-19A`/`AUTO-19B`.
6. Mutaciones **M165–M168** y matriz completa `M1–M168` con restauración byte a byte.
7. CI, cinco documentos de fase, `CHANGELOG`/`PROJECT_STATE`/índice y sello `1.87.0-beta`.

## 6. Ficheros tocados

* `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_calibration.py` (O1 + O2 + sello).
* `packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py` (costura pública).
* `apps/api-python/scripts/paper_cycles_export.py` (**nuevo**).
* `packages/py/analytics/tests/test_auto_adaptive_calibration.py` (O1/O2 + forma).
* `packages/py/application/tests/test_auto_self_evaluation_feed.py` (material con riesgo).
* `apps/api-python/scripts/v2_44_mutation_audit.py` (M165–M168).
* `package.json`, `CHANGELOG.md`, `PROJECT_STATE.md`, `engineering-index`,
  `.github/workflows/release-tag-ci.yml`.

## 7. Compuertas

`ruff` · `lint-imports` · `mypy` (499 ficheros, 0 errores) · puros de `packages/py/analytics` +
`packages/py/application` · matriz de mutaciones `M1–M168` · CI de sello.

## 8. Freeze

No se toca: `auto_adaptive.py` (sello `auto18-v1`), `auto_adaptive_data_gate.py` (`auto15-v1`),
`auto_simulation_worker.py`, `auto_adaptive_journal.py`, `v2_43_governor_evidence.py` y el
`governor.json`. `auto_adaptive_replay.py` **tampoco** se toca (contrato `statistical_oos_v1`).
**Sin migración.**

## 9. Límites declarados

* El **camino durable** del exportador está **cableado y verificado por trozos** (costuras ya
  selladas + `ruff`/`mypy`/sonda de bloqueo), pero **no se ejercita end-to-end** en esta fase: no hay
  fixture PG que siembre fills + reservas reales para él. Queda declarado como deuda.
* Esta fase **no** demuestra que la estrategia tenga edge: pone el material y cierra dos huecos de
  honestidad. La calibración sigue siendo **evidencia**, no un permiso.
