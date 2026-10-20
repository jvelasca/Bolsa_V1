# Auditoría del sello `v2.88.154-beta` — los cuatro commits sin sello de la batería por valor

**Fecha:** 2026-10-20 · **Árbol auditado:** `2.11.153-beta` + `[Unreleased]` (`b0d0f7b2`…`4523f171`)
· **Naturaleza:** auditoría **de verificación** (no abre frentes nuevos, no toca el motor).

**Veredicto:** **ningún defecto P1** de motor, decisión, contrato ni esquema. **Cuatro hallazgos**
reales de documentación y de cobertura (`P2`/`P3`), **todos cerrados aquí** antes de sellar.

---

## 0. Alcance y método

Se auditan los cuatro commits que quedaron en `main` **después** del tag `v2.88.153-beta`
(`2af7f0d9`), es decir, lo que el sello `.154` publicaría:

| Commit | Qué entrega |
|---|---|
| `b0d0f7b2` | P2 de `.153`: guarda fail-closed de la `057` + medición de identidad en tri-estado |
| `55fb31da` | re-anclaje del pin PAPER al árbol del P2 |
| `1ac2dd72` | batería integrada POR VALOR (positivo + control negativo) y lector `_entry_reservation` |
| `4523f171` | re-anclaje del pin PAPER al árbol de la batería |

Método: lectura del **diff completo** (no del mensaje), contraste de cada afirmación documental
con el código que la sostiene, y comprobación de que las correcciones son **falsables** (que un
retroceso vuelva a poner el test rojo). Lo que se declara medido en los docs se re-ejecutó.

---

## 1. Hallazgos

### H1 · `P3` · docstring del arnés que describía un cierre que no ocurre

`_drive_cycle` documentaba: «el cierre es una SALIDA determinista (`SELL` de la cantidad viva
tras reinicio), el seam que ya usa `test_auto_scheduler_real_pg_zero_human_intervention`». La
implementación **no** inyecta ninguna `SELL`: lleva el `holdingDeadlineAt` durable al pasado
(seam `E1`) y un tercer worker rehidrata el plan vencido ⇒ **`time_exit`**. El docstring del
módulo ya decía `time_exit`, así que el fichero se contradecía a sí mismo.

**Riesgo:** quien lea el arnés creería que el cierre se fuerza, y el valor probatorio del
`CYCLE_CLOSED` (que sí es el productivo) quedaría infravalorado.

**Cierre:** docstring corregido al mecanismo real (`time_exit` + `auto_cycle_settlement`).

---

### H2 · `P2` · `direction` no tenía **ninguna** aserción y es justo el campo que el defecto deformaba

El hallazgo que la batería destapó —`_build_cycle` tomando `reservations[0]`— publicaba
`direction = "short"` en **todo** ciclo cerrado. Se corrigió el lector, pero `direction` no se
afirmaba en ningún test del repositorio: **una regresión habría vuelto a pasar en verde**.

**Cierre (dos capas):**

1. **Puro** (`packages/py/application/tests/test_auto_operational_monitor.py`, +4 tests):
   `_entry_reservation` elige la entrada aunque la salida vaya primero (y aunque el orden se
   invierta), conserva la primera fila si **no** hay entrada, devuelve `None` sin filas, y un
   ciclo cerrado —con la salida primera, `side='sell'` y `strategy_version_id=None`— se lee
   `direction == "long"`, `strategyVersion == "sv-1"` y con el paso `RESERVATION` describiendo
   la **entrada** (`side='buy'`, `reservedRisk=50.0`).
2. **PG real** (batería, positivo y control negativo): `cycle_row["direction"] == "long"`.

---

### H3 · `P3` · la regla de entrada no declaraba su precondición (largo solamente)

`_entry_reservation` discrimina por `side == 'buy'`. Eso es correcto **porque AUTO 2.0 abre
siempre con `BUY` y reduce con `SELL`**; si algún día se abriesen cortos, la entrada sería
`sell` y la regla elegiría la **salida** (que sería `buy`), invirtiendo `direction` en silencio.

**Cierre:** la precondición queda declarada en el docstring del helper y en el §3 del documento
de la batería, con el discriminador correcto para ese futuro (`reservation_id` con prefijo
`exit:`). No se cambia la regla: no hay ciclos cortos que leer y una segunda regla sin caso que
la ejerza sería una segunda verdad sin prueba.

---

### H4 · `P2` · el radio de impacto de la corrección estaba **subdeclarado**: también repara la escritura DÍA-D

El documento de la batería atribuía el defecto a la ficha y al read-model. No es todo: la ruta
productiva `POST /api/auto/dia-d-verifications` deriva la identidad del ciclo por
`resolve_dia_d_cycle_facts`, que lee `read_operational_monitor`. Con el lector antiguo, un ciclo
**cerrado** aportaba `strategy_version = None` y la verificación DÍA-D se persistía con un
**hueco** donde la entrada declaraba la versión. Consecuencias medidas:

- la fila DÍA-D quedaba `NULL` en versión (y `executedVsDiaD` no podía afirmar coincidencia);
- **no** había `409` espurio: `_declared_conflicts` ignora el contraste cuando el hecho durable
  es `None` (fail-closed correcto), así que el efecto era un hueco silencioso, no un falso
  conflicto.

**Cierre:** se declara en el documento de la batería y en el sello. **Sin backfill**: las filas
escritas antes de la corrección conservan su hueco y se leen como desconocidas; las nuevas
sellan la identidad de la entrada. `Δ decisión = 0` (la regla de contraste no se toca).

---

### H5 · `P3` · cita de freeze obsoleta en el `[Unreleased]`

El bloque del P2 citaba `pnpm window:freeze ⇒ freeze OK (b0d0f7b2)`, que era cierto cuando se
escribió, pero los dos commits siguientes movieron el árbol y el pin se re-ancló dos veces. El
sello `.154` escribe la cita fresca (verificado: `freeze OK (4523f171)` con
`apps ef0ca05a…` / `packages 4a7a456b…` antes de este frente).

---

## 2. Lo que la auditoría **no** encontró (y se declara)

- **Sin defecto de motor ni de decisión:** umbrales, pesos A/B, `TOP_N`, régimen, sizing,
  entradas/salidas, orquestador y replay OOS intactos (`Δ motor = 0`, `Δ decisión = 0`).
- **Sin cambio de contrato HTTP:** `strategyMeasurement` viaja en `dict[str, Any]` del DTO
  (`EstudioChainResponseDto.best_scored`/`values`), así que `PARTIAL` cruza la frontera sin
  cambio de esquema; `MeasurementV1` de `@bolsa/shared` es un tipo **interno** del cliente.
  `contract:check` sigue verde.
- **Sin migración nueva:** `head` sigue `057_top3_opportunity_identity`. La guarda
  `assert_base_table_present` es pura y su test es falsable en el punto exacto del hallazgo.
- **Sin `PARTIAL` mal renderizado:** `formatMeasurementLabel("PARTIAL") = "PARCIAL"` y
  `MeasurementValue` lo anota en lugar de esconderlo; una medición parcial nunca se pinta como
  «no medida» ni como afirmada.
- **Censo de tests:** `test_selection.py --report` ⇒ **651/651 ejecutados · 0 sin declarar · 0
  obsoletas** (la batería entra por el paso dedicado de `lifecycle-pg`).

---

## 3. Verificación medida de este frente de auditoría

| Comprobación | Resultado |
|---|---|
| `test_auto_operational_monitor.py` (puros, incluye los 4 nuevos) | **67 passed** |
| `test_auto_chain_durable_reader.py` | **17 passed** |
| Batería PG (positivo + control negativo, gate ON) | **2 passed in 2.83s** |
| Cadena ESTUDIO PG (regresión del tri-estado, gate ON) | **1 passed** |
| `pnpm lint:py` | **`All checks passed!`** |
| `pnpm imports:py` | **4 kept / 0 broken** |
| `pnpm types:py` | **0 issues** |

---

## 4. Límites declarados

- Esto es una **auditoría interna del diff**, no una auditoría externa ni una certificación de
  rentabilidad: **AUTO sigue OFF**, la ventana PAPER sigue **`INCONCLUSIVE`** y **`CONFIRMED`
  no se emite**.
- La operativa es **100 % SIM**; no se envían órdenes reales.
- Las filas DÍA-D anteriores a esta corrección **no** se reparan (sin backfill) y se leen como
  desconocidas.
- `executedIsBestScoredAsset` sigue comparando `instrumentId` sin canonizar símbolos: se declara
  como observación, no como contrato.
