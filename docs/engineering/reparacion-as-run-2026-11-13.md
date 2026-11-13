# Reparación del instrumento as-run y recertificación de la cohorte — 2026-11-13

**Nivel 3 del plan de sellado (continuación).** El [diagnóstico de los dos días que no certificaban](cohorte-dia-d-benchmark-no-medido-2026-11-13.md)
identificó **por qué** fallaban y estimó offline que, reparadas las causas, los cuatro días serían medibles. Este documento
ejecuta la reparación, la vuelve a correr sobre los mismos datos y **declara el resultado sin adornos**, incluido lo que
sigue sin medirse bien.

`Δ motor = 0` y `Δ decisión = 0`: se toca el **instrumento que mide** el replay, no la estrategia. Ningún umbral, reparto,
`TOP_N`, régimen, selección ni protección cambia. **SIN migración** (head `067_opinion_account_scope`) · **bump**
`2.11.190-beta` (14 CLIs DÍA-D re-sellados) · artefactos as-run regenerados en disco (no versionados).

---

## 1 · Tres defectos, no dos

El diagnóstico declaró dos causas. Al implementarlas apareció una tercera, que sólo se ve cuando la primera se
corrige: **las dos reparaciones juntas seguían dando `no_risk_reference` en tres días**.

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

---

## 2 · Resultado: 4 de 4 días certifican

Cohorte re-certificada por la herramienta del repo (`scripts/ops/cohorte_as_run.py --run`), cuenta
`1484e253d2d54645945a6b1d7`, universo de 8 instrumentos, `toDay = 2026-11-13`, coste 32 bps:

| Día | Brazo `as_run` antes | Brazo `as_run` después |
| --- | --- | --- |
| 2026-11-05 | medido, `realizedR = −1.325811`, **4 de 16 lotes con riesgo** | medido, `realizedR = 2.744128`, **16 de 16** |
| 2026-11-06 | **`no_risk_reference`**, `pnlCurrency = −697.70` sin R | medido, `realizedR = 2.829882`, 12 ciclos |
| 2026-11-09 | medido, `realizedR = 34.211983` con stop de **trailing** | medido, `realizedR = 7.769171`, 8 ciclos |
| 2026-11-10 | **`no_closed_cycles`** (8 ventas descartadas) | medido, `realizedR = 7.943172`, 8 ciclos |

| Día | Patas de `D` sembradas | Ciclos cerrados | Instrumentos con denominador | `pnlCurrency` | `returnPct` |
| --- | --- | --- | --- | --- | --- |
| 2026-11-05 | 0 | 16 | 4 | −702.55 | −2.9756 |
| 2026-11-06 | 3 | 12 | 3 | −697.70 | −3.4057 |
| 2026-11-09 | 3 | 8 | 2 | 18.18 | 3.7119 |
| 2026-11-10 | 7 | 8 | 2 | 18.60 | 3.8007 |

**Veredicto de cohorte:** `insufficient_sample` — `certifiedDays = 2026-11-05, 2026-11-06, 2026-11-09, 2026-11-10`,
`failed = (ninguno)`, motivo único `insufficient_sample:4/12`, hash
`c2a42b99b96ae0a8561664b832386ac242ba97a2f2711e7f45822c43d6208ccc`.

Es decir: **el instrumento ya no es el motivo del `not_certified`**. Lo que queda es lo que hay: 4 días de una cuenta.
La cohorte no certifica por **falta de muestra**, no por un defecto de medición.

La estimación offline del diagnóstico se reprodujo casi exacta con datos sellados (`≈2.84` → `2.744`; `≈2.85` →
`2.830`; `≈7.94` → `7.943`). La de `2026-11-09` no (`≈3.19` → `7.769`) por el motivo de §3.2.

---

## 3 · Lo que sigue sin medirse bien (declarado, no maquillado)

### 3.1 `realizedR` no es aditivo en moneda

`2026-11-05` da **R positivo con pérdida en euros**: `+2.744128` frente a `−702.55`. No es un error de signo — cada
ciclo tiene el signo de su `pnl` — es una **propiedad del agregado**: el brazo suma `(salida−entrada)/riesgo_por_unidad`,
así que **cada tramo de venta aporta su propio R** (una posición vendida en 4 tramos suma ≈4× su R) y el denominador no
está ponderado por tamaño. En este día los ganadores son tramos pequeños con riesgo estrecho (0.79–2.59) y el perdedor
es un lote grande con riesgo ancho (1.62), así que la suma de R sale positiva mientras la caja sale negativa.

**Consecuencia práctica:** `realizedR` sirve para comparar días **con el mismo patrón de tramos y tamaños**, no como
rentabilidad ni como suma de dinero. Un `realizedR` no se debe citar como resultado —ya lo decía el diagnóstico— y
ahora tampoco se puede leer como «cuánto se ganó en R». Queda **abierto** como defecto de método: la corrección natural
es normalizar por el riesgo **en moneda de la posición completa** (una fila por posición, no por tramo). No se hace aquí
porque cambia el número de todos los artefactos históricos y merece su propio sello.

### 3.2 Cuatro ventas de `2026-11-09` siguen sin emparejar

`1343457a3c0c4b398f6c5b182` tiene 4 ventas en la ventana sin compra observable: no está en el universo declarado de
`sim_auto_positions` ni en `position_states` en `D`. Se declaran como `unmatched_sell` (4 códigos en
`reasonCodes`), **no** se imputan a `pnlCurrency` ni a R. Por eso `2026-11-09` mide 8 ciclos y no 12. Resolverlo exige
una fuente de inventario anterior a `D` que hoy no existe: es un hueco **de datos**, no del emparejador.

### 3.3 La BD de desarrollo tiene 768 filas SIM huérfanas

El guardián nuevo (`assert_no_orphan_sim_rows.py`) encuentra **768** filas con referencias rotas en la BD local
(`sim_auto_positions` 46/54, `sim_fill_finance_context` 722/765), sembradas por tests de la cadena A11/A12. No se
limpian aquí: son residuo de test, no datos de la ventana PAPER, y borrarlas sin ventana de referencia sería peor que
declararlas. El guardián las cuenta y devuelve **2**; por eso su cableado en CI es informativo (§5).

---

## 4 · Tests

`packages/py/application/tests/test_dia_d_as_run_eval.py` (58 casos) cubre las tres reparaciones:

- `test_as_run_arm_sell_of_carried_in_leg_is_a_closed_cycle`: vender una pata sembrada cierra ciclo y no es
  `unmatched_sell`; `carriedInLots` lo declara.
- `test_as_run_arm_sell_without_lot_stays_unmatched`: sin lote (ni pata ni compra previa) la venta **sigue** declarada
  y no se imputa: la reparación no inventa inventario.
- `test_as_run_arm_durable_risk_wins_over_live_stop`: con un trailing a `0.1` del precio el R sería `100`; con el stop
  inicial (`90`) es `1`, y `riskSource` dice `durable_journal` frente a `state_at_d`.

---

## 5 · Cableado en CI (informativo, decisión explícita)

`assert_no_orphan_sim_rows.py` corre en **dos** sitios, ninguno bloqueante:

1. **`quality`** — no levanta PostgreSQL, así que el paso **declara el skip** (`::notice::`) en vez de fingir un verde
   o romper el job. Es la forma pedida: informativo y no rompe.
2. **`lifecycle-pg`** — sí tiene BD migrada: ahí el guardián **audita de verdad** (solo `SELECT`, sesión `read_only`) y
   `continue-on-error` lo deja informativo hasta que exista una ventana limpia de referencia. El día que se exija
   verde, se quita esa línea y el código `2` corta el job.

Un escaneo truncado (`--max-rows`) devuelve `3`, nunca `0`: «no vi huérfanas» no es «no hay huérfanas».

---

## 6 · Límites de este documento

- Certificar **no** es medir completo: `2026-11-09` certifica midiendo 8 de 12 lotes (§3.2).
- Los `realizedR` de la tabla son **internos y sellados**, no rentabilidad (§3.1).
- `n = 4` días de **una** cuenta sobre 8 instrumentos: describe esta muestra, no predice la tasa futura.
- El artefacto prueba **qué datos** produjeron la medición (`barsManifest` + `hash`), no que el productor sea honesto:
  un productor que reescriba artefacto y hashes de forma coherente exige firma o sello externo.
