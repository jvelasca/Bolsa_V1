# Cohorte DÍA-D as-run: por qué 2 de 4 días no certifican — 2026-11-13

**Naturaleza:** diagnóstico read-only. No se ha modificado código, ni artefactos, ni PostgreSQL. Todas las
lecturas se hicieron con `psycopg` síncrono y `connection.read_only = True`; los experimentos vivieron en
`operability_runs/_tmp_diag/` y se borraron.

**Cuenta:** `1484e253d2d54645945a6b1d7` · **Ventana de los artefactos:** `D → 2026-11-12` · **Coste declarado:**
32 bps round-trip (`commissionBps=16`, `slippageBps=0`, `spreadBps=0`) · **`stateSource`:**
`sim_auto_positions` · **`bump`:** `2.11.189-beta`.

> **Reparado y re-verificado el mismo día** ([reparación del instrumento as-run](reparacion-as-run-2026-11-13.md),
> `2.11.190-beta`): los cuatro días certifican y los artefactos están regenerados. Este documento sigue siendo el
> diagnóstico de **causas**; sus cifras de §1 son las del artefacto **anterior** a la reparación y se conservan como
> registro. La única cifra de este documento que la reparación corrige es la de §4.2 (ver allí).

---

## 0 · Corrección al informe anterior

`docs/engineering/cohorte-dia-d-as-run-2026-11-13.md` §4 dice que **ninguno** de los dos días que fallan tiene
«un ciclo de venta cerrado dentro de la ventana». Eso es falso para `2026-11-06`.

| Día | Lo que decía el informe | Lo que dice el artefacto |
| --- | --- | --- |
| 2026-11-06 | «no hay ciclo cerrado» | **12 lotes cerrados**, `pnlCurrency = -697.70`, `reason = no_risk_reference` |
| 2026-11-10 | «no hay ciclo cerrado» | 0 lotes cerrados, 8 ventas sin compra previa, `reason = no_closed_cycles` |

Los dos fallos tienen **causas distintas** y la recomendación es distinta para cada uno. Esta es la primera
conclusión del diagnóstico.

---

## 1 · Hecho medido y tabla comparativa

### 1.1 Cohorte

Re-ejecutado hoy con `certify_cohort` sobre los cuatro JSON en disco:

```text
verdict = insufficient_sample
samples = 4      required = 12
certifiedDays = ["2026-11-05", "2026-11-09"]
failed = [
  {day: "2026-11-06", reasons: ["benchmarks:benchmark_not_measured:as_run"]},
  {day: "2026-11-10", reasons: ["benchmarks:benchmark_not_measured:as_run"]}
]
reasons = ["insufficient_sample:4/12"]
```

Los dos días que fallan fallan **solo** por `benchmarks`. Ningún otro check (`artifact_integrity`,
`temporal_freeze`, `initial_state`, `sequential_replay`, `real_market_data`, `realistic_execution`, `audit`)
falla o queda `NOT_EVALUATED`. Por tanto, si el brazo `as_run` fuera medible, esos dos artefactos certificarían
tal y como están.

### 1.2 Tabla

Fills del día = filas de `sim_fill_finance_context` con esa fecha. Fills en ventana = filas que entran en
`D → 2026-11-12` (la ventana crece con D, por eso el número sube en los días tempranos). Lotes cerrados =
pares FIFO venta↔compra que produce `run_as_run_arm`. Lotes con riesgo = lotes cerrados cuyo instrumento tiene
entrada y stop en `audit.pointInTime.legs`.

| | 2026-11-05 | 2026-11-06 | 2026-11-09 | 2026-11-10 |
| --- | --- | --- | --- | --- |
| Fills del día (BD) | 13 | 4 | 14 | 12 |
| Fills en ventana | 43 | 30 | 26 | 12 |
| `startingState.legs` | 3 | 3 | 7 | 8 |
| Lotes cerrados (`as_run.exits`) | **16** | **12** | **8** | **0** |
| Lotes con referencia de riesgo | 4 de 16 | **0 de 12** | 8 de 8 | 0 de 0 |
| Ventas sin compra previa | 0 | 0 | 4 | **8** |
| `arms.as_run.measured` | `true` | **`false`** | `true` | **`false`** |
| `arms.as_run.reason` | `null` | **`no_risk_reference`** | `null` | **`no_closed_cycles`** |
| `arms.as_run.realizedR` | `-1.325811` | **`null`** | `34.211983` | **`null`** |
| `arms.as_run.pnlCurrency` | `-702.55` | **`-697.70`** | `18.18` | **`null`** |
| `arms.hold_structural.realizedR` | `-1.428287` | `-0.684159` | `10.894597` | `6.599107` |
| `arms.market_bh.measured` | `true` | `true` | `true` | `true` |
| `arms.market_bh.pnlCurrency` | `-349.93` | `-580.76` | `-248.99` | `412.67` |
| `arms.market_bh.returnPct` | `-0.7372` | `-1.2236` | `-0.2820` | `0.4196` |
| `benchmark.capital` | `47464.80` | `47464.80` | `88280.95` | `98341.26` |
| `benchmark.universe` (n) | 3 | 3 | 7 | 8 |
| `certification.verdict` | `certified` | `not_certified` | `certified` | `not_certified` |

`market_bh` está medido en los cuatro días y con `capitalBasis=initial_notional`: el fallo de `benchmarks` es
siempre `as_run`, nunca `market_bh` ni `cash`. El orden del bucle en `dia_d_certification.py:440` hace que el
primer brazo no medido sea el que da el motivo, y `as_run` va primero.

### 1.3 Dos matices que la certificación no ve

1. **`2026-11-05` certifica midiendo solo 4 de sus 16 lotes.** Los otros 12 lotes no tienen referencia de
   riesgo, así que suman al `pnlCurrency` (-702.55) pero **no** al `realizedR` (-1.325811). El brazo solo es
   `no_risk_reference` si **todos** los lotes cerrados carecen de riesgo (`dia_d_as_run.py:1036`); si falta una
   parte, se descarta en silencio. Certificado ≠ medido por completo.
2. **El `realizedR` de `2026-11-09` usa como denominador un stop de trailing que está por encima de la entrada.**
   `2323f09f…` tiene `entry=23.93` y `structuralStop=24.1088` en las patas; `_risk_per_unit` toma
   `abs(entry - stop) = 0.1788` (0.75 % del precio) y el R se dispara. Con el stop **inicial** que sí está
   registrado en el journal (`23.1388`, riesgo 0.7912) el mismo día da `≈3.19` en vez de `34.21`. La métrica
   actual mezcla «riesgo inicial» y «distancia al stop actual» sin declararlo.

---

## 2 · La condición `measured` del brazo `as_run`

### 2.1 Dónde se construye

El artefacto se compone en `packages/py/application/src/bolsa_application/dia_d_as_run.py:1244`:

```text
run_as_run_arm(legs, fills, execution=model),
```

y el resultado se serializa en `"arms"` (`:1288`), se resume en los `gaps` (`:1266-1270`) y en el `measured`
de nivel superior (`:1290`, que es `any(...)`: por eso los cuatro artefactos tienen `status="measured"` aunque
`as_run` no mida).

El CLI `apps/api-python/scripts/v2_102_dia_d_as_run.py` solo aporta las entradas: `_read_legs` (`:102-200`) y
`_read_fills` (`:203-244`). **No** decide `measured`.

### 2.2 Las tres salidas de `run_as_run_arm`

`run_as_run_arm` (`dia_d_as_run.py:965-1054`) empareja compras y ventas por instrumento con FIFO. Devuelve
`measured=False` en tres casos, y solo en esos:

| Línea | Condición | `reason` |
| --- | --- | --- |
| `:973-974` | `not fills` | `no_fills` |
| `:1013-1019` | `not realized` (ninguna venta consumió un lote) | `no_closed_cycles` |
| `:1036-1044` | `missing_risk` cubre **todos** los lotes realizados | `no_risk_reference` |

Si hay al menos un lote realizado con riesgo, devuelve `measured=True` (`:1046-1054`).

Dos detalles del productor que son la raíz de todo:

```text
dia_d_as_run.py:976-980
    risk_by_id: dict[str, float] = {}
    for leg in legs:
        risk = _risk_per_unit(leg)
        if risk is not None:
            risk_by_id[leg.instrument_id] = risk
```

La única fuente de riesgo son las **patas del estado inicial de D**.

```text
dia_d_as_run.py:982
    open_lots: dict[str, list[list[float]]] = {}
```

El inventario de apertura nace **vacío**: las patas de D no se siembran como lotes. Solo alimentan el mapa de
riesgo.

### 2.3 Cadena hasta el motivo reportado

`dia_d_certification.py:439-445` exige `measured is True` para `as_run`, `cash` y `market_bh`:

```text
for arm in (ARM_AS_RUN, ARM_CASH, ARM_MARKET_BH):
    row = arms.get(arm)
    if row is None: return _missing(...)
    if row.get("measured") is not True:
        return _failed(name, f"benchmark_not_measured:{arm}")
```

Con `as_run` primero, el motivo es siempre `benchmarks:benchmark_not_measured:as_run`. El código de motivo es
correcto y apunta al brazo correcto; lo que hay que explicar es por qué el brazo no mide.

---

## 3 · Causa: dato ausente vs decisión de código

### 3.1 `2026-11-10` — decisión de código, dato presente en el propio artefacto

Las 8 ventas del día son de `2323f09f3b7f42399e69735a6` (4 lotes) y `34673ecf981044e986cf670e7` (4 lotes).
**Los dos instrumentos están en las patas de D con entrada y stop**:

| Instrumento | `entry` (pata) | `structuralStop` (pata) | Riesgo/unidad |
| --- | --- | --- | --- |
| `2323f09f3b7f42399e69735a6` | `23.93` | `24.1088` | `0.1788` |
| `34673ecf981044e986cf670e7` | `55.099998` | `54.5079` | `0.592098` |

Aun así las 8 ventas se declaran `unmatched_sell` porque `open_lots` empieza vacío (`:982`) y solo las compras
**dentro de la ventana** crean lote (`:995-999`). La posición venía abierta de D: es exactamente el caso que
el brazo «as-run» debería medir —la decisión de salir de una posición que se llevaba— y hoy la descarta.

**Clasificación: decisión de código. El dato para medir está en el artefacto. Reparable.**

### 3.2 `2026-11-06` — decisión del productor; el dato existe en la BD, no en el artefacto

Los 12 lotes cerrados son de tres instrumentos que **no** están en las patas de D (`1343457a…`,
`2323f09f…`, `34673ecf…`). El `pnlCurrency` se calcula igual (`-697.70`), así que los ciclos y los precios
existen; lo que falta es el denominador de riesgo. `risk_by_id` solo contiene los 3 instrumentos de D
(`02f456…`, `0ade61…`, `103c29…`), que en esa ventana no se venden. Resultado: `missing_risk == all` →
`no_risk_reference`.

¿Existe el stop en algún sitio durable? **Sí, en `decision_journal_entries`.** Para esta cuenta:

```text
2026-11-06 20:05:11  auto_position_materialized  1343457a…  entryPrice=55.299999  quantity=361.1788
2026-11-06 20:05:11  auto_protection_event      1343457a…  kind=PROTECT_APPLIED  stopAfter=53.6789
2026-11-09 17:30:07  auto_protection_event      2323f09f…  kind=PROTECT_APPLIED  stopAfter=23.1388
2026-11-09 17:31:09  auto_protection_event      34673ecf…  kind=PROTECT_APPLIED  stopAfter=52.5079
```

Hay entrada, cantidad y stop inicial por ciclo (`cycleId`). Lo que no hay es una lectura que los use.

Por qué no están en las patas: `_read_legs` (`v2_102_dia_d_as_run.py:126-130`) lee

```text
SimAutoPositionRow.account_id == account_id,
SimAutoPositionRow.quantity > 0,
SimAutoPositionRow.opened_at < end,
```

es decir **las posiciones que siguen abiertas hoy**, filtradas por `opened_at < D+1`. Cuando una posición se
cierra, su fila desaparece y con ella su entrada y su stop. Comprobado en la BD: para esta cuenta hay
**0 filas** en `position_states`, **0** en `lifecycle_events`, **8** en `positions` (solo las vivas) y **0**
en `auto_exit_orders` para los instrumentos cerrados. La única historia de stops es el journal.

**Clasificación: no es un hueco de datos de mercado ni falta una barra. Es una decisión del productor (leer
el estado actual en vez del estado en D) más un uso incompleto del journal durable. Reparable sin inventar
nada.**

### 3.3 Por qué el informe anterior se equivocó

El motivo que ve el operador es siempre `benchmark_not_measured:as_run`, y el campo `gaps` del artefacto
(`:1266-1270`) solo guarda `{"arm", "reason"}`. Ninguno de los dos casos dice «cuántos lotes había». Además,
las dos salidas tempranas (`:1013-1044`) **no incluyen `decisions`**, así que
`audit.decisions.as_run` está **vacío** justo en los dos días que fallan, aunque hay 12 lotes cerrados y
`pnlCurrency` calculado. El artefacto oculta la evidencia precisamente cuando más se necesita.

### 3.4 Resumen de la clasificación

| Día | ¿Falta un dato? | ¿Es decisión de código? | Detalle |
| --- | --- | --- | --- |
| 2026-11-06 | No en la BD; sí en el artefacto | Sí, del productor | `_read_legs` no lee historia; `risk_by_id` solo mira patas |
| 2026-11-10 | No, el dato está en las patas | Sí, del evaluador | `open_lots` no se siembra con `legs` |

Ninguno de los dos fallos es «no hay ciclo cerrado ese día». Uno es «hay ciclos y no hay denominador»; el
otro es «hay ventas de posiciones de D y el evaluador no las reconoce como inventario».

---

## 4 · Alcanzabilidad del objetivo de 12 y tope estructural

### 4.1 La aritmética de `certify_cohort`

`dia_d_certification.py:552-582`:

- `samples = len(rows)`: cuenta **artefactos**, no días certificados.
- Si `samples < required` → `insufficient_sample` (12 por `DEFAULT_MIN_COHORT_SAMPLES`, `dia_d_as_run.py:103`).
- Si `samples >= required` y **algún** día falla → `not_certified` con `days_not_certified:n`.
- Solo si `samples >= required` y **todos** certifican → `certified`.

Consecuencia: **los 12 exigidos no son el cuello de botella de los dos fallos.** Hoy solo existen 4 días con
fills; aunque los 4 certificaran, el veredicto seguiría siendo `insufficient_sample:4/12`. Reparar los dos días
cambia `certifiedDays` de 2 a 4, no el veredicto.

Pero cuando haya 12 artefactos, el veredicto exige **12/12 certificados**. Un solo día inmedible convierte la
cohorte en `not_certified`. Ahí sí muerde el problema de medición.

### 4.2 Fracción de días medibles, medida

- Sin reparar: **2 de 4** (50 %) — los artefactos actuales.
- Reparando las dos causas de §3 (sembrar `open_lots` con las patas + tomar el riesgo inicial del journal):
  **4 de 4** en esta muestra.

La segunda cifra no es una opinión: se ejecutó el mismo emparejamiento FIFO con (a) inventario inicial igual a
las patas de D y (b) riesgo por ciclo tomado de `auto_position_materialized.entryPrice` y
`auto_protection_event(PROTECT_APPLIED).stopAfter`, sobre los mismos fills y el mismo `toDay = 2026-11-12`.

| Día | Lotes cerrados | Lotes con riesgo | ¿Medible? | `realizedR` estimado con stop inicial |
| --- | --- | --- | --- | --- |
| 2026-11-05 | 16 | 16 | sí | `≈2.84` |
| 2026-11-06 | 12 | 12 | sí | `≈2.85` |
| 2026-11-09 | 12 | 12 | sí | `≈3.19` |
| 2026-11-10 | 8 | 8 | sí | `≈7.94` |

**Estos `realizedR` no son un resultado y no deben citarse como tal.** Están calculados offline, no sellados y
no certificados; y cambian porque cambia el denominador (§1.3), no porque cambie la operativa. Lo que acredita
la tabla es solo la columna «¿medible?».

**Reproducido con datos sellados** ([reparación](reparacion-as-run-2026-11-13.md), `toDay = 2026-11-13`):

| Día | `realizedR` estimado | `realizedR` sellado | Diferencia |
| --- | --- | --- | --- |
| 2026-11-05 | `≈2.84` | `2.744128` | el estimado usaba `toDay = 2026-11-12` |
| 2026-11-06 | `≈2.85` | `2.829882` | idem |
| 2026-11-09 | `≈3.19` | `7.769171` | el sellado mide **8** de 12 lotes: 4 ventas de un instrumento fuera del universo declarado siguen declaradas como `unmatched_sell` |
| 2026-11-10 | `≈7.94` | `7.943172` | idem |

Las tres primeras filas confirman la estimación; la de `2026-11-09` **no** la confirma y la diferencia está explicada
(hueco de inventario, no del emparejador).

Advertencia sobre `n=4`: 2/4 y 4/4 son proporciones con un intervalo de confianza enormérrimo. Sirven para
describir esta muestra, no para predecir la tasa futura.

### 4.3 Cadencia real de días con fills

En `ohlcv_bars` (timeframe `1d`) hay 9 sesiones entre `2026-11-02` y `2026-11-12`. La cuenta tiene fills en 4
de ellas (`11-05`, `11-06`, `11-09`, `11-10`); el 11-11 y el 11-12 no operó. Es decir: 4 de 9 sesiones desde
el 2 de noviembre, o 4 de 6 en la parte de la ventana que empieza el 5.

Para pasar de 4 a 12 artefactos faltan **8 días más con fills**. A la cadencia observada (≈44 % de sesiones)
eso son **≈18 sesiones ≈ 3,5 semanas**; contando solo desde el inicio de la ventana (≈67 %) serían **≈12
sesiones ≈ 2,5 semanas**. Es una extrapolación, no una promesa: depende de que el motor siga operando.

### 4.4 ¿Hay tope estructural?

- **El umbral de 12 no es un tope estructural.** Es una restricción de calendario: hoy faltan días, no
  capacidad de medirlos.
- **El diseño actual sí impone un tope estructural a la certificación**: un día cuyas únicas salidas sean
  posiciones que ya venían de D es inmedible, y un día cuyas ciclos se abran y cierren dentro de la ventana
  tampoco se mide porque el riesgo solo se busca en las patas de D. Con la muestra actual eso deja 2 de 4
  fuera. Con `p=0.5` por día, la probabilidad de un 12/12 es `0.5¹² ≈ 0,02 %`; con `p=1` es 1. No es un
  pronóstico, es la aritmética de la conjunción que exige `certify_cohort`.
- **Ese tope se levanta reparando el instrumento, no bajando el umbral.** Con el journal como fuente de
  riesgo, un día pasa a ser medible en cuanto alguna de sus posiciones se cierra, y la ventana `D → toDay` es
  abierta: el cierre acaba llegando. El único caso que seguiría sin medir es un día que no cierre nada nunca,
  y eso es un hecho de la operativa, no del instrumento.

---

## 5 · Recomendaciones

### (a) Reparaciones legítimas del instrumento

Ninguna de estas toca el motor ni cambia una decisión: cambian **qué lee** el instrumento de medición.

1. **Sembrar `open_lots` con `legs`** (`dia_d_as_run.py:982`). Una posición que venía de D y se vende dentro
   de la ventana es un ciclo cerrado con entrada y stop conocidos. Efecto medido: `2026-11-10` pasa de 0 a 8
   lotes cerrados, todos con riesgo. No inventa nada: usa el estado inicial ya declarado y ya hasheado en el
   artefacto.
2. **Tomar el riesgo del ciclo de los hechos durables de entrada** (`auto_position_materialized.entryPrice` +
   `auto_protection_event` con `kind=PROTECT_APPLIED` y `stopAfter`), usando las patas de D solo como respaldo.
   Efecto medido: `2026-11-06` pasa de 0 a 12 lotes con riesgo.
3. **Leer el estado en D desde la historia, no desde el conjunto abierto de hoy** (`v2_102:126-130`). Mientras
   `_read_legs` dependa de `quantity > 0`, un artefacto viejo **no es reproducible**: si se regenera mañana,
   las posiciones que se hayan cerrado desaparecen del estado inicial de D. Eso ya está pasando: las patas de
   `11-05` son 3 y las de `11-10` son 8, no porque el libro creciera así, sino porque las cerradas se borran.
4. **No truncar el timestamp de los fills a fecha** (`v2_102:235`). `AsRunFill.timestamp = str(at)[:10]` hace
   que el orden intra-día se pierda y que el FIFO dependa del orden que devolvió la consulta. Los fills tienen
   `created_at` con microsegundos.
5. **Conservar `decisions` en las salidas tempranas** (`:1013-1044`). Hoy `audit.decisions.as_run` está vacío
   en los dos días que fallan, aunque los fills y el `pnlCurrency` existen. Un artefacto de auditoría no puede
   borrar la evidencia cuando el brazo no mide.
6. **Declarar el denominador de R y usarlo de forma consistente.** Hoy se usa la distancia al stop *actual*
   (que puede estar por encima de la entrada tras un trailing) y se mezcla con posiciones cuya pata trae el
   stop inicial. Es una decisión metodológica, no un detalle: cambia `34.21` por `≈3.19` en `11-09`. Debe
   declararse explícitamente y aplicarse igual a todos los brazos.
7. **Decidir si R se pondera por cantidad.** Hoy cada lote suma un R sin peso (`:1033`), así que 4 lotes de 1
   unidad pesan lo mismo que 4 de 1.000. Es una definición de métrica, no un bug de ejecución; pero debe
   declararse antes de comparar días.
8. **Invariante de universo a nivel de cohorte.** Los cuatro artefactos declaran universos de 3, 3, 7 y 8
   instrumentos, y `_check_benchmarks` solo compara `benchmark.universe` con `pointInTime.universe`
   (`:462-467`). Un `market_bh` sobre 3 instrumentos no es comparable con uno sobre 8, y hoy eso certifica.

### (b) Lo que sería maquillar la medición (no hacer)

1. **Regenerar los artefactos con un `toDay` posterior hasta que midan, y publicar solo los que pasan.** La
   ventana `D → toDay` es parte del diseño, pero elegirla *después* de ver el resultado es selección por
   resultado. Si se cambia, se fija a priori y se aplica igual a todos los días.
2. **Deducir el stop a posteriori** (ATR, porcentaje fijo, «el stop que debería haber tenido») cuando el
   journal no lo tiene. Eso es inventar el denominador y hace que R diga lo que uno quiera.
3. **Tratar una venta sin compra previa como ciclo cerrado** con una entrada sintética.
4. **Excluir los dos días que fallan y presentar «2 de 2 certificados»** sin declarar la población. Si se
   redefine la cohorte como «días con al menos un ciclo cerrado medible», hay que declararlo antes de mirar
   los datos y publicar también el recuento completo.
5. **Marcar `measured=True` con 0 ciclos** o imputar `R=0` a un día sin cierres. Un cero es una medición; la
   ausencia no.
6. **Bajar `DEFAULT_MIN_COHORT_SAMPLES`** (`dia_d_as_run.py:103`) de 12 a 4 para que el veredicto cambie.
7. **Relajar `_check_benchmarks`** para que no exija `as_run` medido.

### (c) Sobre el umbral de 12

**No debe revisarse a la baja, y el argumento no es «no llegamos».**

- 12 es la muestra mínima declarada para emitir un veredicto **comparativo** entre brazos. Con 4 días, la media
  de R no tiene valor inferencial: cualquier diferencia entre `as_run` y `hold_structural` cabe dentro del
  ruido. Bajarlo a 4 no aceleraría nada; convertiría una muestra insuficiente en una falsa precisión.
- El umbral **no es la causa** del `insufficient_sample` actual en el sentido de bloqueo lógico: la causa es que
  solo existen 4 días con fills. La cohorte avanzará con el calendario.
- Lo que sí conviene revisar es **la conjunción** «12 artefactos **y** todos certificados». Es más estricta que
  «12 muestras» y no está declarada como tal en ningún sitio. Recomendación: mantener la conjunción (es la
  lectura honesta: si un día no se puede medir, la cohorte no está certificada) y **añadir, por separado y
  declarado a priori, el recuento de la subpoblación medible** («días con ≥1 ciclo cerrado»), publicando
  siempre ambos números. Nunca sustituir uno por el otro.

---

## 6 · Comandos exactos de reproducción

Todo es lectura. `DATABASE_URL` del `.env` trae `?schema=public`, que `psycopg` rechaza como parámetro libpq:
hay que descartarlo antes de conectar (los snippets ya lo hacen).

### 6.1 Releer la cohorte y los cuatro artefactos

```powershell
.\.venv\Scripts\python.exe -c "import json,glob,sys; sys.path.insert(0,'packages/py/application/src'); from bolsa_application.dia_d_certification import certify_cohort; a=[json.load(open(p,encoding='utf-8')) for p in sorted(glob.glob('operability_runs/dia-d-as-run/1484e253d2d54645945a6b1d7/*.json'))]; r=certify_cohort(a); print(r.verdict, r.samples, r.required, r.certified_days, r.failed)"
```

### 6.2 Fills, patas y estado durable (read-only)

```powershell
@'
import os, pathlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from dotenv import load_dotenv
load_dotenv(".env", override=False)
import psycopg
p = urlsplit(os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1))
dsn = urlunsplit((p.scheme, p.netloc, p.path,
                  urlencode([(k, v) for k, v in parse_qsl(p.query) if k in {"sslmode", "connect_timeout"}]),
                  p.fragment))
ACC = "1484e253d2d54645945a6b1d7"
with psycopg.connect(dsn, autocommit=False) as c:
    c.read_only = True
    with c.cursor() as cur:
        cur.execute("""
            SELECT created_at, instrument_id, side, quantity, price
            FROM sim_fill_finance_context WHERE account_id=%s ORDER BY created_at
        """, (ACC,))
        for r in cur.fetchall(): print("FILL", r)
        cur.execute("""
            SELECT created_at, instrument_id, event_type, payload
            FROM decision_journal_entries WHERE account_id=%s
              AND event_type IN ('auto_protection_event','auto_position_materialized')
            ORDER BY created_at
        """, (ACC,))
        for at, inst, et, pl in cur.fetchall():
            print("J", at, inst, et, {k: pl.get(k) for k in ("kind","stopAfter","entryPrice","quantity","cycleId") if k in pl})
    c.rollback()
'@ | .\.venv\Scripts\python.exe -
```

### 6.3 Reproducir los dos motivos sin escribir nada

```powershell
@'
import json, pathlib, sys
sys.path.insert(0, "packages/py/application/src")
from datetime import datetime
from bolsa_application.dia_d_as_run import AsRunFill, AsRunLeg, run_as_run_arm
ACC = "1484e253d2d54645945a6b1d7"
for day in ("2026-11-05","2026-11-06","2026-11-09","2026-11-10"):
    a = json.loads(pathlib.Path(f"operability_runs/dia-d-as-run/{ACC}/as-run-{day}.json").read_text(encoding="utf-8"))
    legs = [AsRunLeg(instrument_id=x["instrumentId"], direction=x["direction"], quantity=x["quantity"],
                     entry=x["entry"], structural_stop=x.get("structuralStop"))
            for x in a["audit"]["pointInTime"]["legs"]]
    fills = [AsRunFill(timestamp=d["date"], instrument_id=d["instrument"], side=d["action"],
                       quantity=1.0, price=d["price"])
             for d in a["audit"]["decisions"]["as_run"]]
    row = a["arms"][0]
    print(day, row["measured"], row["reason"], row["exits"], len(fills))
'@ | .\.venv\Scripts\python.exe -
```

Nota: las `decisions` de los dos días que fallan están vacías (§3.3), así que este último snippet reproduce la
condición de `measured` de los días certificados y el vacío de los otros dos; para reconstruir los ciclos de
`11-06` y `11-10` hay que leer los fills de la BD (6.2), como se hizo en el diagnóstico.

### 6.4 Lo que **no** se ejecutó

`apps/api-python/scripts/v2_94_dia_d_multi_band.py` no se ejecutó (muta `auto_simulation_worker.py`). Los
artefactos de `operability_runs/dia-d-as-run/` no se reescribieron ni regeneraron. No se ejecutó
`git add`, `git commit` ni `git push`. No se escribió en PostgreSQL.

---

## Anexo · Hashes de los artefactos analizados

Los hashes en disco **no** coinciden con los publicados en `cohorte-dia-d-as-run-2026-11-13.md` §3: los
artefactos se regeneraron el 2026-11-13 por la tarde con otro universo declarado (3/3/7/8 instrumentos en vez
de 8). Cualquier evidencia que cite hashes debe regenerarse contra los ficheros actuales.

| Día | `hash` | `benchmark.universe` |
| --- | --- | --- |
| 2026-11-05 | `2d38cb1c06197bc46314c5023b8a461453146adc293891de1d5fbbd5ef75b7f8` | 3 |
| 2026-11-06 | `1cea8666b945884c8cdbb7db16b115b2b584d92bd5df8d3351b72ee289101cf9` | 3 |
| 2026-11-09 | `d5904b78aa224c953d52cae7b3af39eec54f3af6cf81c64c5fe731e583fd5214` | 7 |
| 2026-11-10 | `599139cf02479038a0fb4a71e7a70e862987cd6b06966e81e1321eef18936fd9` | 8 |
