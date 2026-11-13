# Reparación del instrumento as-run y recertificación de la cohorte — 2026-11-13

**Nivel 3 del plan de sellado (continuación).** El [diagnóstico de los dos días que no certificaban](cohorte-dia-d-benchmark-no-medido-2026-11-13.md)
identificó **por qué** fallaban. Este documento ejecuta la reparación, la vuelve a correr sobre los mismos datos y
**declara el resultado sin adornos**, incluido lo que sigue sin medirse bien.

`Δ motor = 0` y `Δ decisión = 0`: se toca el **instrumento que mide** el replay, no la estrategia. Ningún umbral,
reparto, `TOP_N`, régimen, selección ni protección cambia. **SIN migración** (head `067_opinion_account_scope`) ·
**bump** `2.11.189-beta` → `2.11.190-beta` → `2.11.191-beta` (14 CLIs DÍA-D re-sellados en cada paso) · artefactos
as-run regenerados en disco (no versionados).

> **Corrección de la primera versión de este mismo documento (2026-11-13, mismo día).** La versión que entró en
> `main` con el PR #126 afirmaba en §3.2 que *«no existe una fuente de inventario anterior a `D`»* y que las 4 ventas
> sin compra de `2026-11-09` eran un **hueco de datos**. Era **falso**: las compras existen en
> `sim_fill_finance_context` (4 fills del `2026-11-06`, cantidades 1:1 con las ventas) y el CLI las cortaba en el
> inicio de `D`. Era un **defecto del instrumento**, no un hueco. Las §2 y §3 de esta versión lo corrigen y
> sustituyen a las cifras anteriores.

---

## 1 · Cinco defectos, no dos

### 1.1 (a) Una venta de una posición arrastrada no era un ciclo cerrado

`run_as_run_arm` empezaba con `open_lots` vacío: una posición abierta **antes** de `D` y vendida **en** la ventana no
tenía compra que consumir y se declaraba `unmatched_sell`. En `2026-11-10` eso descartó **8 ventas reales**.

**Corrección.** Las patas de `D` (`legs`) se siembran en el FIFO antes de procesar fills, y se cuentan en
`carriedInLots`. No hay doble conteo porque el llamante sólo pasa posiciones abiertas **estrictamente antes** de `D`
(`SimAutoPositionRow.opened_at < start`): la compra intradía entra como fill, no como pata.

### 1.2 (b) El riesgo se buscaba en un estado vivo que ya no tenía el ciclo

Con el lote sembrado, el ciclo existía pero se quedaba sin denominador: `_risk_per_unit` leía el stop de
`sim_auto_positions`, y `2026-11-06` cerraba **12 lotes** (`pnl = −697.70`) sin ninguno con `quantity > 0` vivo.

**Corrección.** Nuevo `AsRunRiskReference` con los **hechos durables** de entrada, leídos del journal:
`auto_position_materialized.entryPrice` + `auto_protection_event(kind=PROTECT_APPLIED).stopAfter`. Gana sobre el stop
vivo (que puede venir arrastrado por un trailing y entonces R no mediría entrada→stop inicial) y el origen aplicado
por instrumento se publica en `riskSource` (`durable_journal` / `state_at_d`). Cuando no hay hecho durable se cae al
estado vivo y **se declara** en `limits`, en vez de descartar el lote en silencio.

### 1.3 (c) El emparejamiento entrada↔stop dependía del orden de las filas

`PROTECT_APPLIED` y `auto_position_materialized` del **mismo ciclo** comparten timestamp: se escriben en el mismo
instante. La primera implementación recorría las filas en orden y exigía haber visto la materialización **antes** del
stop; con el orden real (`PROTECT_APPLIED` primero) se descartaban todas las referencias y los tres días seguían en
`no_risk_reference` — el resultado *parecía* que la reparación (b) no funcionaba.

**Corrección.** Dos pasadas: se acumulan entradas y stops por instrumento y luego se empareja con una regla
determinista — **última** materialización, **primer** `PROTECT_APPLIED` con `timestamp >= entrada`. El orden físico de
las filas deja de importar.

### 1.4 (d) El inventario anterior a `D` no se leía — y sí existía

`_read_legs` sólo miraba el **conjunto abierto actual**. Una posición abierta antes de `D` y cerrada dentro de la
ventana desaparece de `sim_auto_positions` al cerrarse, así que el inventario inicial del replay era incompleto: en
`2026-11-09`, la posición de `1343457a3c0c4b398f6c5b182` (BAS) —361.1788 unidades compradas en 4 fills el `11-06`—
se vendió en 4 fills el `11-09`, y las 4 ventas quedaron como `unmatched_sell`.

**Corrección.** Nueva `carried_in_legs_from_fills(fills)` (dominio puro): reconstruye el inventario previo con la
**misma semántica FIFO** del brazo, un lote por pata (no a precio medio: dos lotes a precios distintos son dos
riesgos). El CLI lee los fills `created_at < inicio de D` (`_read_fills_before`) y añade **sólo** los instrumentos
que el estado vivo no conoce. Un corto previo no se reconstruye (el FIFO del brazo es de largos) y se declara como
`prior_short_not_reconstructed:<instrumento>`.

### 1.5 (e) El R se sumaba por tramo de venta y no ponderaba por tamaño

`realizedR` sumaba `(salida−entrada)/riesgo_por_unidad` por **cada fill de venta**. Una posición vendida en 4 tramos
aportaba su R **cuatro veces**, y con tramos de tamaño distinto el resultado dependía de cómo el bróker había troceado
la orden. Ese era el origen del «R positivo con caja negativa» de `2026-11-05`.

**Corrección.** La unidad de medición es el **episodio de tenencia**: mientras el libro del instrumento no quede
plano, los fills son la misma posición; al quedar plano y volver a comprar, empieza un ciclo nuevo con su propio
riesgo. El P&L del episodio se agrega completo y se normaliza por su **riesgo en moneda**
(`distancia_entrada→stop × cantidad`). Se publican tres números para que no haya ambigüedad:

| Campo | Qué es |
| --- | --- |
| `realizedR` | Σ del R de cada posición cerrada. Es «R total si cada posición arriesgara 1R»: **cada posición pesa igual**, arriesgue 10 € o 10.000 €. |
| `riskCurrency` | Riesgo en moneda de las posiciones medidas. `pnlCurrency / riskCurrency` es el **R de cartera**. |
| `cycles` | Posiciones cerradas (episodios), no tramos. `exits` sigue contando tramos de venta. |

Agrupar por `cycle_id` habría sido lo canónico, pero en estos 43 fills **está a `NULL`** (los sembró la cadena
E2E/A11, no el camino que lo atribuye). Por eso la agrupación es por episodio, que no depende de un dato ausente.

---

## 2 · Resultado: 4 de 4 días certifican

Cohorte re-certificada por la herramienta del repo (`scripts/ops/cohorte_as_run.py --run`), cuenta
`1484e253d2d54645945a6b1d7`, universo de 8 instrumentos, `toDay = 2026-11-13`, coste 32 bps.

**Las tres columnas de R NO son comparables entre sí**: cada una usa una definición o un inventario distinto. Se
publican juntas justo para que el cambio no se pueda confundir con una mejora de la operativa. El `pnlCurrency` sí es
comparable y es la prueba de que la caja no se ha tocado.

| Día | `2.11.189` (original) | `2.11.190` (patas + journal) | `2.11.191` (inventario + R por posición) |
| --- | --- | --- | --- |
| 2026-11-05 | R `−1.325811`, caja `−702.55`, 4/16 tramos con riesgo | R `2.744128`, caja `−702.55` | R `0.711648`, **4 ciclos**, `riskCurrency 870.28`, R cartera `−0.8073`, caja `−702.55` |
| 2026-11-06 | **`no_risk_reference`**, caja `−697.70` sin R | R `2.829882`, caja `−697.70` | R `0.729867`, **3 ciclos**, `riskCurrency 603.73`, R cartera `−1.1556` |
| 2026-11-09 | R `34.211983` con stop de **trailing**, caja `+18.18`, 8/12 tramos | R `7.769171`, caja `+18.18`, 8/12 tramos | R `0.729867`, **3 ciclos**, `riskCurrency 603.73`, R cartera `−1.1556`, caja **`−697.70`** |
| 2026-11-10 | **`no_closed_cycles`** (8 ventas descartadas) | R `7.943172`, caja `+18.60` | R `1.996030`, **2 ciclos**, `riskCurrency 18.22`, R cartera `1.0209`, caja `+18.60` |

**El cambio más incómodo es el de `2026-11-09`.** La caja pasa de `+18.18` a **`−697.70`**: el artefacto anterior
**omitía una pérdida real de ≈715.88 €**. No era un día bueno mal medido; era un día malo presentado como bueno,
porque las 4 ventas de BAS no se imputaban a nadie. Certificar no es medir: `2026-11-09` certificaba ya en `2.11.189`
midiendo 8 de 12 tramos y con el signo del día invertido.

**Veredicto de cohorte:** `insufficient_sample` — `certifiedDays = 2026-11-05, 2026-11-06, 2026-11-09, 2026-11-10`,
`failed = (ninguno)`, motivo único `insufficient_sample:4/12`, hash
`c2a42b99b96ae0a8561664b832386ac242ba97a2f2711e7f45822c43d6208ccc`.

Es decir: **el instrumento ya no es el motivo del `not_certified`**. Lo que queda es lo que hay: 4 días de una cuenta.

---

## 3 · Lo que sigue sin medirse bien (declarado, no maquillado)

### 3.1 `realizedR` (suma por posición) y `pnlCurrency` pueden tener signos opuestos — y es correcto

`2026-11-05`: `realizedR = +0.7116` con caja `−702.55`. Ya no es un artefacto del troceado: son **4 posiciones**,
y la que perdió dinero perdió `−1.12 R` (riesgo en moneda 585.5 €) mientras dos posiciones pequeñas ganaron `≈+1 R`
cada una (riesgo 6.9 € y 11.3 €). Si cada posición arriesga 1R, el total es positivo; en euros, no.

La lectura correcta la da el R de cartera: `−702.55 / 870.28 = −0.8073`. **Los dos números se publican**; citar solo
el primero como «resultado» sería engañoso, y citar solo el segundo escondería que la pérdida se concentró en una
posición de tamaño muy superior a las otras.

Límite que queda: con reentrada en la ventana, el denominador es el del **último** ciclo del instrumento
(`_read_entry_risk` no distingue ciclos porque `cycle_id` está a `NULL` en estos fills). Los días con reentrada
quedan con esa aproximación declarada.

### 3.2 `2026-11-09` mide ya 12 de 12 tramos

Con el inventario reconstruido, las 4 ventas de BAS emparejan: `unmatched_sell` desaparece de los cuatro días
(`reasonCodes = []`) y el día mide **3 ciclos / 12 tramos**. Lo que antes era «hueco de datos» era el defecto (d).

### 3.3 La BD de desarrollo tiene 768 filas SIM huérfanas

El guardián (`assert_no_orphan_sim_rows.py`) encuentra **768** filas con referencias rotas en la BD local
(`sim_auto_positions` 46/54, `sim_fill_finance_context` 722/765), sembradas por tests de la cadena A11/A12. No se
limpian aquí: son residuo de test, no datos de la ventana PAPER, y borrarlas sin ventana de referencia sería peor que
declararlas. El guardián las cuenta y devuelve **2**; por eso su cableado en CI es informativo.

---

## 4 · Tests

`packages/py/application/tests/test_dia_d_as_run_eval.py` (67 casos) cubre los cinco defectos:

- `test_as_run_arm_sell_of_carried_in_leg_is_a_closed_cycle`: vender una pata sembrada cierra ciclo y no es
  `unmatched_sell`.
- `test_as_run_arm_sell_without_lot_stays_unmatched`: sin lote la venta **sigue** declarada; la reparación no
  inventa inventario.
- `test_as_run_arm_durable_risk_wins_over_live_stop`: con un trailing a `0.1` del precio el R sería `100`; con el
  stop inicial (`90`) es `1`, y `riskSource` lo declara.
- `test_as_run_arm_r_is_per_position_not_per_slice`: 4 tramos de la misma posición dan R `2`, no `8`.
- `test_as_run_arm_r_weights_slices_by_quantity`: 2 uds a `+2R` y 8 a `+4R` dan `3.6`, no `3.0`.
- `test_as_run_arm_treats_fragmented_buys_as_one_position`: 4 compras troceadas + 4 ventas son **un** ciclo.
- `test_as_run_arm_reentry_after_flat_is_a_new_cycle`: quedar plano y recomprar abre ciclo nuevo.
- `test_as_run_arm_partial_risk_is_declared_not_silent`: un lote sin denominador ya no se descarta en silencio
  (`partial_risk:1/2`).
- `test_carried_in_legs_from_fills_rebuilds_fifo_lots` / `..._ignores_orphan_sells` /
  `test_as_run_arm_measures_sale_of_ledger_carried_inventory`: la cadena completa del inventario previo.

---

## 5 · Cableado en CI (informativo, decisión explícita)

`assert_no_orphan_sim_rows.py` corre en **dos** sitios, ninguno bloqueante:

1. **`quality`** — no levanta PostgreSQL, así que el paso **declara el skip** (`::notice::`) en vez de fingir un verde
   o romper el job.
2. **`lifecycle-pg`** — sí tiene BD migrada: ahí el guardián **audita de verdad** (solo `SELECT`, sesión `read_only`) y
   `continue-on-error` lo deja informativo hasta que exista una ventana limpia de referencia.

Un escaneo truncado (`--max-rows`) devuelve `3`, nunca `0`: «no vi huérfanas» no es «no hay huérfanas».

---

## 6 · Límites de este documento

- Certificar **no** es medir completo, y esta reparación lo demuestra dos veces: `2026-11-09` certificaba con el día
  invertido.
- Los `realizedR` de la tabla son **internos y sellados**, no rentabilidad. El R de cartera se deriva de
  `pnlCurrency / riskCurrency`.
- `n = 4` días de **una** cuenta sobre 8 instrumentos: describe esta muestra, no predice la tasa futura.
- El artefacto prueba **qué datos** produjeron la medición (`barsManifest` + `hash`), no que el productor sea honesto:
  un productor que reescriba artefacto y hashes de forma coherente exige firma o sello externo.
