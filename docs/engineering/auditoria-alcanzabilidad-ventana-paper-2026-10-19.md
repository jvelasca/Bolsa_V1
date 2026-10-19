# Auditoría de alcanzabilidad del gate de régimen de la ventana PAPER — 2026-10-19

> **Alcance:** auditoría **read-only** sobre `v2.88.148-beta` (`main` `99a574a8`; tag `a4c8de56`).
> **`Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0` · SIN migración**: no se toca ni una
> línea de código de producción, ni umbrales, ni pesos, ni el gate. El único artefacto ejecutable
> nuevo es el instrumento read-only [`evidence/v2.88.149/audit_regime_reachability.py`](./evidence/v2.88.149/audit_regime_reachability.py).
>
> **Pregunta:** el veto `BEAR_TREND` que mantiene la ventana PAPER en `NO_MEDIDO`, ¿es un **hecho
> de MERCADO**, un **sesgo del detector**, o una **propiedad de construcción** del gate?

## 0. Veredicto

| Hipótesis | Dictamen | Evidencia |
| --- | --- | --- |
| El clasificador está **sesgado** (marca bajista un mercado plano) | **FALSA** | 22/35 `trend_down` con caída 10d-vs-40d entre **-1,11 %** y **-9,07 %**; 0 bajistas con movimiento `·<1 %·` |
| El detector usa **datos viejos** | **FALSA** | **120** barras por símbolo; última barra `2026-10-16` (34) / `2026-10-19` (1, parcial) |
| El preflight es **más estricto** que el motor | **FALSA** | Misma composición (`make_bar_snapshot_loader` → clasificador → agregado → eje) y el motor aplica ese **único** eje global |
| El veto de hoy es un **hecho de mercado** | **CIERTA** | 22 `down` / 5 `up` / 8 `range` ⇒ `BEAR_TREND` ⇒ LONG vetadas (motor long-only) |
| **El gate de la ventana es alcanzable** | **FALSA** | **0/61** fechas as-of con LONG permitidas; el máximo no-bajista fue **30/35 (85,7 %)** y **también** se vetó |

**Dictamen en una frase:** el detector está bien y el veto es correcto **respecto al motor**, pero
el gate de la ventana exige que **los 35 símbolos** estén simultáneamente no-bajistas; eso no ha
ocurrido en **ninguna** de las 61 fechas as-of medidas. `NO_MEDIDO` no es «paciencia operativa»:
es una **propiedad de construcción** del agregado + la lane long-only.

## 1. Método (reproducible, solo lectura)

Piezas — las **mismas** que el tick y el preflight de la ventana:

- barras: `make_bar_snapshot_loader(SqlAlchemyOhlcvRepository(session), watch)` (D1, 120 barras);
- clasificador: `classify_market_regime` (`discovery_market_regime_v0`);
- agregado: `aggregate_trial_regime` (prioridad **más conservadora**);
- eje: `map_trial_regime` + `regime_allows_entry_for(regime, "long")`.

Parámetros inmutables de `v0` ([`discovery_market_regime.py`](../../packages/py/application/src/bolsa_application/discovery_market_regime.py)):
`MIN_REGIME_BARS = 60`, ventana larga **40**, corta **10**, volatilidad **14**,
`|slope| ≥ 0,5` para tendencia y `vol_ratio > 0,045` para `high_vol`. **No se cambian aquí.**

Comandos:

```text
pnpm window:preflight                                  # preflight real (read-only)
uv run --no-sync python \
  docs/engineering/evidence/v2.88.149/audit_regime_reachability.py --watch-from-estudio
```

El instrumento emite, además de la etiqueta, las **medidas crudas** por símbolo (medias 10/40,
volatilidad relativa y pendiente normalizada) y un **backtest as-of**: para cada índice `t`
clasifica cada símbolo **sólo con `bars[:t+1]`** y agrega. Nunca usa datos posteriores.

## 2. Mediciones

### 2.1 Preflight de hoy (`2026-10-19`, 10:44 local)

```text
watch 35 (estudio) · barras 35
counts: trend_down 22 · range 8 · trend_up 5
agregado (más conservador): trend_down
eje operativo: BEAR_TREND → entradas LONG VETADAS (exit 2)
```

**Matiz de frescura declarado:** 34 símbolos tienen la última barra del **viernes `2026-10-16`** y
uno la barra **parcial** de hoy (`2026-10-19`, con `high = low = close` ⇒ `vol_ratio = 0`). El
preflight de la mañana mide, en la práctica, el cierre del viernes.

### 2.2 Por símbolo — falsación del «detector sesgado»

| Etiqueta | n | Movimiento 10d-vs-40d | Pendiente normalizada |
| --- | --- | --- | --- |
| `trend_down` | 22 | **-9,07 % … -1,11 %** | -3,73 … -0,60 |
| `range` | 8 | -0,58 % … +1,08 % | -0,44 … +0,48 |
| `trend_up` | 5 | +1,44 % … +4,18 % | +0,52 … +2,88 |

Los 22 bajistas tienen una **caída real** (el menor, -1,11 %), y **ninguno** cae en la zona de
ruido (`|movimiento| < 1 %`). Las tres etiquetas quedan separadas por el umbral `|slope| ≥ 0,5`
tal y como lo define `v0`. **No hay sesgo medible ni clasificación de ruido.**

### 2.3 Histórico del ledger del runner

| Día | Watch | `trend_down` / `range` / `trend_up` | Agregado | Estado |
| --- | --- | --- | --- | --- |
| `20261014` | 20 (catálogo) | 7 / 7 / 6 | `trend_down` | `NO_MEDIDO_REGIMEN` |
| `20261015` | 35 (ESTUDIO) | 24 / 5 / 6 | `trend_down` | `NO_MEDIDO_REGIMEN` |
| `20261016` | 35 (ESTUDIO) | 23 / 7 / 5 | `trend_down` | `NO_MEDIDO_REGIMEN` |
| `20261017` | 35 (ESTUDIO) | 22 / 8 / 5 | `trend_down` | `NON_MARKET_DAY` (sábado) |
| `20261018` | — | — | — | `NON_MARKET_DAY` (domingo) |

**El `14/10` es el caso que mejor expone la construcción:** **13 de 20** símbolos eran operables
(`range`/`trend_up`) y el eje global los vetó **a todos** porque otros **7** estaban `trend_down`.
El ledger es **append-only**: la fila `NO_MEDIDO_REGIMEN` del sábado `17/10` (de antes del arreglo
`.143`) sigue ahí, pero `latestByDay` toma la última ⇒ `NON_MARKET_DAY`.

### 2.4 Alcanzabilidad as-of — la medida decisiva

Sobre las **61** fechas que permiten las 120 barras (clasificando cada símbolo sólo con
`bars[:t+1]`):

```text
as-of: dias=61  barras_alineadas=120  LONG_permitida=0/61
as-of agregado        { trend_down: 61 }
as-of eje operativo   { BEAR_TREND: 61 }
as-of max no-bajista  0.857 (30/35) — y AUN ASÍ el eje fue BEAR_TREND
```

**Cero días alcanzables en 61.** La mejor fecha del trimestre tuvo **30 de 35** símbolos no
bajistas: los otros **5** bastaron para vetar el universo completo.

## 3. Cadena causal (código, no opinión)

1. **El agregado es el peor caso presente**
   ([`auto_v2_entry.py`](../../packages/py/application/src/bolsa_application/auto_v2_entry.py)):
   `_REGIME_CONSERVATIVE_PRIORITY = (high_vol, trend_down, range, trend_up, low_vol)` y
   `aggregate_trial_regime` devuelve **el primero presente**. Es una regla de **seguridad**
   declarada («nunca se pinta de verde un universo mixto»), no un error.
2. **El motor consume UN solo eje por tick**
   ([`DiscoveryRegimeSource`](../../packages/py/application/src/bolsa_application/auto_v2_entry.py),
   `_v2_regime()` en `auto_simulation_worker`): el régimen es **global** para todo el watch; no hay
   lectura por símbolo en la decisión.
3. **El gate direccional es binario y long-only**
   ([`portfolio_decision_engine.py`](../../packages/py/application/src/bolsa_application/portfolio_decision_engine.py)
   paso 3): `regime_allows_entry_for(regime, "long")` ⇒ `BEAR_TREND` ⇒ `regime_invalid` para
   **todos** los símbolos del tick.
4. **El watch se ensanchó en el `.135`**: de **20** (catálogo) a **35** (ESTUDIO,
   `watchFromEstudio: true` en [`window-forward.mjs`](../../scripts/lib/window-forward.mjs)). Con
   una regla de **AND sobre símbolos**, más universo ⇒ **monótonamente menos** probable un día
   alcanzable.

**Consecuencia aritmética:** un día medible exige `P(ningún símbolo bajista)` sobre 35 símbolos
correlacionados del mismo mercado. Medido: **0/61**.

## 4. Qué falsaría este dictamen

- Encontrar **una** fecha con los 35 símbolos no bajistas (abriría el gate) ⇒ el gate no sería
  inalcanzable. Medido: **0/61**.
- Demostrar que el preflight usa una composición **distinta** a la del tick ⇒ el veto no sería
  fiel al motor. Revisado en código: es la **misma**.
- Demostrar que el clasificador marca bajista con movimientos de ruido ⇒ habría sesgo. Medido: el
  menor bajista cae **-1,11 %** y 0 bajistas por debajo del 1 %.
- Demostrar que el agregado **no** es el peor caso ⇒ no aplicaría la AND. Revisado en código y
  cubierto por tests del módulo.

## 5. Consecuencias (sin maquillar)

1. **`NO_MEDIDO` es la declaración honesta y correcta** de lo que ocurre; el instrumento no
   inventa un día medible ni fuerza el régimen.
2. Pero **la frase «falta OPERACIÓN» es incompleta**: operar más días no desbloquea el gate
   mientras la composición exija unanimidad. Sólo lo desbloquearía un **rally ancho y
   sincronizado** del universo ESTUDIO.
3. La **magnitud del P&L** sigue **NO MEDIDA** y la ventana **no demuestra rentabilidad**: aquí no
   se promociona evidencia ni se emite `CONFIRMED`.
4. **No** se propone bajar umbrales, acortar la ventana ni escoger símbolos «que suben» (sería
   sesgo de selección). Cualquier cambio debe ser explícito y con baseline nuevo.

## 6. Opciones (decisión del propietario; ninguna aplicada)

| Opción | Qué cambia | Coste / riesgo | Veredicto de esta auditoría |
| --- | --- | --- | --- |
| **A. Gate DIRECCIONAL POR SÍMBOLO** | El eje global pasa a **declaración/dial de riesgo**; el veto de entrada usa el régimen del **propio símbolo** | **`Δ decisión ≠ 0`**: nuevo hash de replay, ADR, re-baseline de la evidencia `.136`…`.148` | **Semánticamente correcta**: un símbolo bajista no debería vetar los otros 34 |
| **B. Cambiar sólo el agregado de la ventana** (mayoría/cuórum en SIM) | La ventana mediría una regla que **no** es la del motor | Rompe la comparabilidad y la validez de la certificación | **Rechazada** por instrumento inválido |
| **C. Aceptar y declarar** | Sin cambio de motor; se documenta que la ventana sólo certifica en rally ancho | Ninguno | **Honesta**, pero deja la ventana sin horizonte operativo |
| **D. Reducir el watch a símbolos operables** | Escoger el universo **después** de ver el régimen | Sesgo de selección / look-ahead | **Rechazada** |

**Recomendación:** si se quiere que la ventana mida el motor real, la opción **A** es la única que
arregla la semántica sin mentir; exige tratarse como incremento propio (`Δ decisión ≠ 0`), con
ADR, nuevo baseline de replay y evidencia. Si no hay apetito para ese cambio, la opción **C** es
correcta **si y sólo si** se declara el criterio de alcanzabilidad de forma explícita y se deja de
presentar `NO_MEDIDO` como algo que se resolverá operando.

**Decisión del propietario (2026-10-19):** se abre la opción **A** como
[ADR-047](../adr/047-gate-direccional-por-simbolo.md) en estado **Proposed** y **docs-only**: fija el
contrato (gate por símbolo, agregado como declaración), el plan de baseline de replay y la política
de re-emisión de la evidencia `.136`…`.149` por segmentos. **No implementa nada**: el motor sigue
byte-idéntico hasta que se acepte y se abra un sello propio con `Δ decisión ≠ 0`.

**Medida previa del POST (simulación read-only, 2026-10-19):** con el gate por símbolo, **61/61**
fechas as-of tendrían al menos **un** símbolo operable (frente a **0/61** del eje global); mediana
**22 de 35** operables por día, mínimo **10**, máximo **30**, **0** días de un solo símbolo y **0**
símbolos nunca operables. Es un **techo** (falta señal/ciclo), no un veredicto de P&L.

## 7. Límites declarados (sin fabricar)

- **5 filas** de ledger observadas; la del `14/10` se lee de sus etiquetas (watch de 20 símbolos
  del catálogo, ya no reconstruible con las barras actuales).
- El backtest usa el **watch ACTUAL** (ESTUDIO, 35) y alinea por **índice** desde el final de cada
  símbolo, no por calendario: mide **alcanzabilidad del gate**, no el histórico de la ventana. El
  universo está **seleccionado a día de hoy** (activos con sector e histórico) ⇒ sesgo de
  supervivencia **declarado**.
- Incluye la barra **parcial** de hoy en un símbolo (`vol_ratio = 0`); no cambia el dictamen.
- El instrumento **sólo hace SELECT**: no escribe ledger, journal, pin ni BD; no promociona
  evidencia ni emite `CONFIRMED`.
- **No** se toca el motor, ni los umbrales, ni los pesos A/B, ni el contrato HTTP; **sin
  migración**. `replay-repro` debe seguir reproduciendo el mismo `sha256` (Δ decisión = 0).
- La auditoría **no** demuestra rentabilidad ni mide la magnitud del P&L.
