# ADR-047 — Gate direccional POR SÍMBOLO (el régimen agregado pasa a declaración de riesgo)

**Estado:** **Proposed — docs-only.** Este ADR **no implementa nada**: el árbol de decisión queda
**byte-idéntico** (`Δ motor = 0` · `Δ decisión = 0` · `Δ contrato HTTP = 0` · SIN migración). La
implementación exige **aceptación explícita del propietario** y un sello propio con
**`Δ decisión ≠ 0`**.
**Fecha:** 2026-10-19
**Contexto:** [auditoría de alcanzabilidad del gate de régimen](../engineering/auditoria-alcanzabilidad-ventana-paper-2026-10-19.md) ·
evidencia [`v2.88.149`](../engineering/evidence/v2.88.149/README.md) (tag `v2.88.149-beta` → `637a4433`).
**Depende de:** [ADR-046](./046-protocolo-longitudinal-paper.md) (ventana PAPER acumulativa y veredicto
humano) · [ADR-029](./029-order-proposal-decision-journal.md) (spine append-only) ·
[ADR-043](./043-position-automation.md) (automatización de posición, `PAPER_D_EXECUTE` off).
**Afecta a:** la barrera §3 de [`PortfolioDecisionEngine`](../../packages/py/application/src/bolsa_application/portfolio_decision_engine.py)
y la fuente de régimen del tick [`DiscoveryRegimeSource`](../../packages/py/application/src/bolsa_application/auto_v2_entry.py).

---

## 1. El problema, medido (no supuesto)

En la ventana PAPER el veredicto es `NO_MEDIDO` y se venía explicando como «falta **OPERACIÓN**». La
auditoría `.149` midió la causa real:

| Hecho | Medida |
| --- | --- |
| El detector **no** sesga | 22/35 `trend_down` con caída 10d-vs-40d entre **−1,11 %** y **−9,07 %**; **0** bajistas con movimiento `< 1 %` |
| El detector **no** usa datos viejos | **120** barras por símbolo; última barra `2026-10-16` (34 símbolos) / `2026-10-19` parcial (1) |
| El preflight **es** el motor | misma composición: loader → `classify_market_regime` → `aggregate_trial_regime` → eje |
| El veto de hoy **es de mercado** | 22 `trend_down` / 8 `range` / 5 `trend_up` ⇒ `BEAR_TREND` ⇒ LONG vetadas |
| El gate de la ventana es **alcanzable** | **FALSO**: **0/61** fechas as-of con LONG permitidas; la mejor tuvo **30/35 (85,7 %)** no bajistas y **también** fue vetada |

**Cadena causal (código):**

1. `aggregate_trial_regime` devuelve el veredicto **más conservador presente**
   (`_REGIME_CONSERVATIVE_PRIORITY = high_vol, trend_down, range, trend_up, low_vol`): **un** símbolo
   en `trend_down` etiqueta el universo entero.
2. `DiscoveryRegimeSource` expone **un único** régimen por tick; no hay lectura por símbolo en la
   decisión.
3. `regime_allows_entry_for(regime, "long")` bloquea LONG en `BEAR_TREND` ⇒ `regime_invalid` para
   **todos** los símbolos del tick.
4. El `.135` ensanchó el watch de **20** a **35** (ESTUDIO): con una regla de **AND** sobre símbolos,
   más universo ⇒ **monótonamente menos** probable un día medible.

**El alcance real del defecto es más estrecho de lo que parece** (y eso lo hace arreglable): el
agregado **solo** puede vetar por dos resultados — `trend_down` (⇒ `BEAR_TREND`) y `NO_REGIME`
(⇒ `UNKNOWN`). `high_vol` **no** veta: mapea a `HIGH_VOLATILITY`, que está fuera del conjunto
bloqueado (`_BLOCKED_ENTRY = {UNKNOWN, RISK_OFF}`; `regime_blocks_new_long = {UNKNOWN, RISK_OFF,
BEAR_TREND}`). Es decir: **el único efecto del agregado sobre la decisión es el contagio de un
símbolo bajista a los otros 34.**

**La asimetría ya existe en la observabilidad.** [`symbols_operable`](../../packages/py/application/src/bolsa_application/market_operability.py)
cuenta cuántos símbolos admitirían LONG **por sí mismos** y su docstring declara literalmente la
tensión («con el agregado en `BEAR_TREND` TODAS las entradas están vetadas, aunque varios símbolos
estén en `range` o `trend_up`»). El sistema **ya sabe** representar el hecho por símbolo; lo que no
hace es **decidir** con él.

## 2. Decisión propuesta

**El veto de entrada pasa a evaluarse con el régimen del PROPIO símbolo. El régimen agregado del
universo se conserva, se calcula igual y se expone igual, pero deja de vetar: pasa a ser
declaración de contexto / dial de riesgo.**

El cambio es de **una sola pieza**: *qué régimen se le entrega* a
`regime_allows_entry_for`. La función, sus conjuntos bloqueados, el clasificador, sus umbrales y la
prioridad conservadora **no se tocan**.

### 2.1 Resolución por símbolo (precedencia explícita)

Para cada símbolo `s` del watch, en el mismo tick, con barras as-of `bars[s]`:

| Paso | Regla | Resultado |
| --- | --- | --- |
| 1 | `macro_regime ∈ {risk_off, crisis}` | **`RISK_OFF` global** ⇒ veta **todas** las entradas de **todos** los símbolos (hecho de mercado, no de instrumento) |
| 2 | `map_trial_regime(classify_market_regime(bars[s]))` clasificable | régimen **de `s`** ⇒ decide **solo** la entrada de `s` |
| 3 | sin barras / clasificación vacía | **`UNKNOWN` para `s`** ⇒ `s` **no** entra (**fail-closed por símbolo**, no por universo) |
| 4 | agregado `aggregate_trial_regime(...)` | se calcula y se **declara** (`marketRegime`); **no** veta |

Reglas duras que se conservan:

- **Long-only sigue igual**: un símbolo en `trend_down` **no** recibe LONG (no se relaja nada).
- **Fail-closed sigue igual**: `UNKNOWN` **no** entra; `RISK_OFF` **no** entra.
- **Un símbolo no puede contaminar a otro**: ni por `trend_down`, ni por `high_vol`, ni por ausencia
  de barras.

### 2.2 Qué cambia y qué no

| Elemento | Hoy | Con este ADR |
| --- | --- | --- |
| `classify_market_regime` (params `v0`: 60 barras, 40/10, vol 14, `\|slope\| ≥ 0,5`) | — | **sin cambio** |
| `_REGIME_CONSERVATIVE_PRIORITY` / `aggregate_trial_regime` | alimenta el veto | **se conserva**; pasa a **declaración** |
| `regime_allows_entry_for` (conjuntos bloqueados) | — | **sin cambio** |
| Régimen que consume la barrera §3 del motor | **global** | **del símbolo** |
| Régimen macro `risk_off/crisis` | veto global | **veto global** (sin cambio) |
| Tamaño de posición, `risk_scale`, gobernador | — | **sin cambio** (el agregado **no** dimensiona hoy; ver §7) |
| Watch (ESTUDIO, 35) | — | **sin cambio** (no se recorta por régimen: ver §3-D) |
| Contrato HTTP | — | **aditivo**: `marketRegime` (global) y el régimen de entrada **coexisten** en la lectura; ninguna clave se elimina ni se re-tipa |
| Esquema | — | **sin migración** (el journal es JSONB, ADR-029) |

### 2.3 Procedencia en el journal (para que el sello no mienta)

El spine durable pasa a distinguir **dos** hechos, sin fusionarlos:

- `marketRegime` = regime **agregado** del tick (declaración de contexto; es el que ya escribe
  `auto_cycle_journal`).
- `entryRegime` = regime **del símbolo** que la barrera usó para decidir (procedencia del
  `regime_invalid` cuando lo haya).

`reason_codes` **no** cambia: `regime_invalid` sigue siendo el código del veto de régimen. Un
`regime_invalid` con `entryRegime = trend_down` significa «este símbolo estaba bajista», no «el
mercado estaba bajista»; la lectura deja de ser ambigua.

### 2.4 Una sola fuente de verdad para «entradas permitidas»

Toda superficie que hoy declare «entradas permitidas» con el eje global debe usar **la misma** regla
por símbolo, o el sello sería incoherente:

- [`replay_oos`](../../packages/py/application/src/bolsa_application/replay_oos.py) (`entries_allowed_long`),
  que hoy hace `regime_allows_entry_for(operational, "long")` con el régimen global.
- [`symbols_operable`](../../packages/py/application/src/bolsa_application/market_operability.py), que
  **ya** cuenta por símbolo (queda como está; es la referencia de la semántica nueva).
- [`opportunity_evidence_adapter`](../../packages/py/application/src/bolsa_application/opportunity_evidence_adapter.py)
  (`regime_fit` por trial), que ya es por instrumento.

Regla: **si dos superficies pueden declarar alcanzabilidad, tienen que dar el mismo número.**

## 3. Alternativas consideradas (y por qué se rechazan)

| Opción | Qué hace | Por qué NO |
| --- | --- | --- |
| **B. Cuórum/mayoría solo en la ventana** | La ventana mediría con una regla distinta a la del motor | Instrumento inválido: certificaría algo que el motor no hace. Rechazada en la auditoría |
| **C. Aceptar y declarar** | Sin cambio; la ventana solo certifica en rally ancho | Honesta, pero deja la ventana **sin horizonte** (0/61 medido). Es el **statu quo** del `.149` |
| **D. Recortar el watch a símbolos operables** | Escoger el universo **después** de ver el régimen | Sesgo de selección / look-ahead. Rechazada |
| **E. Cambiar el agregado a mayoría (un solo eje)** | Menos conservador, pero **sigue** habiendo un eje | Una mayoría bajista seguiría vetando un símbolo en `trend_up`: el defecto semántico persiste, solo se mueve el umbral |
| **F. Quitar la barrera de régimen** | Nada veta | Elimina una protección real (LONG en tendencia bajista confirmada). Rechazada |

## 4. Consecuencias (lo que este ADR obliga a pagar)

1. **`Δ decisión ≠ 0` declarado.** No es un refactor: es un cambio de contrato del gate. Exige
   sello propio, no puede colarse como «docs».
2. **Baseline de replay nuevo.** El `sha256` del sello dejará de ser `1E3ADAC2…929A37E7`
   (idéntico en `.136`…`.149`). El cambio de hash es **la prueba** de que la decisión cambió; no es
   un accidente que se tolere.
3. **Re-emisión de evidencia `.136`…`.149` como segmento PRE.** No se reescriben documentos
   históricos (son append-only): se declaran **superseded as a segment** y el sello que implemente
   este ADR emite el segmento POST con sus propias medidas.
4. **La ventana PAPER se re-abre por segmentos.** Las filas del ledger anteriores a la
   implementación siguen siendo `NO_MEDIDO_REGIMEN` con sus conteos reales; **no** se
   re-clasifican (sería reescribir la historia). Días PRE y POST **no** son comparables.

### 4.1 Plan de baseline y replay (secuencia concreta)

1. **Aceptación del ADR** (propietario). Sin ella no hay rama ni cambio.
2. **Implementación en un sello propio** (`Δ decisión ≠ 0`): barrera por símbolo + procedencia
   `entryRegime` + paridad en `replay_oos`.
3. **Fixture/baseline:** regenerar el artefacto del sello **en el mismo commit** del cambio de
   comportamiento, registrar el `sha256` **nuevo** en la evidencia del sello y conservar el viejo
   como PRE. `replay-repro` debe quedar **VERDE con el hash nuevo** (no con el viejo: un verde con el
   hash viejo probaría que la decisión **no** cambió).
4. **Evidencia POST:** tabla antes/después sobre las **mismas 61 fechas** as-of, con el mismo
   instrumento read-only; número de símbolos vetados por día; y declaración explícita de que el P&L
   PRE/POST **no** es comparable (regla de decisión distinta).
5. **Ventana:** nueva entrada de ledger con el `segment` del sello; `latestByDay` intacto; ninguna
   fila histórica se toca.

### 4.2 Política de re-emisión de la evidencia `.136`…`.149`

- **No** se editan los README de esos sellos (ni sus hashes, ni sus veredictos).
- El sello implementador añade una nota **al principio** de su propio README: «el baseline de replay
  cambia aquí; `.136`…`.149` quedan como segmento PRE, con `sha256 1E3ADAC2…929A37E7`».
- Cualquier afirmación de alcanzabilidad anterior se lee **con su segmento**: `NO_MEDIDO` PRE era
  correcto y **no** se reinterpreta como fallo del motor.
- La cadena de hashes **no se rompe**: se **segmenta** en un punto declarado y fechado.

## 5. Verificación que la implementación deberá traer (falsable)

| Test | Si falla |
| --- | --- |
| **Un** símbolo `trend_down` + resto `range` ⇒ los `range` **sí** pueden entrar y el bajista **no** | el contagio global sigue vivo ⇒ no se implementó |
| Símbolo sin barras ⇒ **solo** él queda `UNKNOWN`; los demás deciden | el fail-closed se filtró de símbolo a universo |
| `trend_down` del propio símbolo ⇒ `regime_invalid` (no se relajó el long-only) | se abrió una entrada contra tendencia |
| `macro risk_off/crisis` ⇒ **todo** vetado | el eje macro dejó de ser global |
| `aggregate_trial_regime` sigue devolviendo el más conservador (contrato intacto) | se cambió el clasificador en vez del consumidor |
| `replay_oos.entries_allowed_long` coincide con la barrera del tick en el mismo día | dos verdades distintas |
| `replay-repro` con el hash **nuevo** (y falla con el viejo) | la decisión no cambió o el baseline se actualizó sin medir |
| As-of: **> 0/61** fechas con al menos un símbolo operable | el cableado por símbolo no llegó al camino real |

El último es el **criterio de éxito**: hoy es `0/61`; con el gate por símbolo debe ser **> 0** (y el
instrumento `.149` ya sabe medirlo). Si sigue en `0`, el ADR no arregló la alcanzabilidad.

## 6. Qué falsaría este ADR

- Que con el gate por símbolo la alcanzabilidad as-of siga en **0/61** ⇒ el cuello no era el agregado
  (o la implementación no lo cableó).
- Que el cambio mueva el **tamaño** de posición, los pesos A/B o las salidas ⇒ se filtró alcance
  (`Δ decisión` mayor que el declarado).
- Que un símbolo bajista reciba entrada por efecto de borde (precedencia mal implementada) ⇒ el ADR
  debilita la protección en vez de corregir la semántica.
- Que la ventana PRE y POST se mezclen en una misma serie ⇒ comparación inválida.

## 7. Por qué el agregado puede pasar a «declaración» sin cambiar el tamaño

Medido en código: el agregado **solo** llega a la decisión a través de la barrera §3
(`regime_allows_entry_for`). `HIGH_VOLATILITY` **no** está bloqueado y el tamaño lo fijan
`risk_scale`/gobernador (`ENTRY_REDUCED`/`ENTRY_RESTRICTED` **no** vetan). Por tanto, retirar el
agregado del veto **no** altera el dimensionamiento ni las salidas: el único efecto conductual es
que un símbolo bajista deja de vetar a los demás. Si en el futuro se quiere que el agregado
**module** tamaño (dial de riesgo real), será **otro** ADR con su propia medida.

## 8. Fuera de alcance (declarado)

- Bajar umbrales, acortar ventanas o tocar `discovery_market_regime_v0`/`v1`.
- Cambiar pesos A/B, `risk_scale`, gobernador o la lógica de salidas.
- Recortar el watch o elegir universo por régimen (look-ahead).
- Promover evidencia o emitir `CONFIRMED` (sigue siendo humano, ADR-046).
- Operar en real: la operativa es **100 % SIM** (`PAPER_D_EXECUTE` off).
- Implementar nada en este incremento: **este ADR no toca código**.

## 9. Referencias

- Auditoría: [`auditoria-alcanzabilidad-ventana-paper-2026-10-19.md`](../engineering/auditoria-alcanzabilidad-ventana-paper-2026-10-19.md).
- Evidencia: [`evidence/v2.88.149/README.md`](../engineering/evidence/v2.88.149/README.md) ·
  instrumento: [`audit_regime_reachability.py`](../engineering/evidence/v2.88.149/audit_regime_reachability.py).
- Código del gate: `packages/py/analytics/src/bolsa_analytics/cognitive/market_regime_gate.py` ·
  agregado y fuente: `packages/py/application/src/bolsa_application/auto_v2_entry.py` ·
  barrera: `packages/py/application/src/bolsa_application/portfolio_decision_engine.py` §3.
- Protocolo de la ventana: [ADR-046](./046-protocolo-longitudinal-paper.md).
