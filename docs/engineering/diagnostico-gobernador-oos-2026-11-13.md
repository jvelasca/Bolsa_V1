# Diagnóstico del gobernador en el replay OOS V2.86

- Fecha: 2026-11-13
- Naturaleza: **investigación read-only**. No se ha tocado código fuente, ni PostgreSQL, ni el artefacto. Este documento es el único fichero creado.
- Artefacto analizado: `operability_runs/oos/v2_86.json`
- Motor: `AutoSimulationWorker` congelado sobre stores en memoria.

## 1. Hecho medido

### 1.1 Números del artefacto (leídos con `json`, no de memoria)

| Campo | Valor |
| --- | --- |
| `venue` / `account` | `paper` / `1484e253d2d54645945a6b1d7` |
| `watchSize` | 20 |
| `historyDays` (censo) | 1.303 |
| `replay.ticks` | 1.239 |
| `replay.startDay` → `endDay` | 2022-01-27 → 2026-11-12 |
| `totals.proposals` | 1.200 |
| `totals.decided` | 24.780 |
| `totals.vetoes` | 24.779 |
| `totals.orders` | 1 |
| `totals.fills` | 4 |
| `journalReasons` | `top_n_excluded` 4.957 · `governor_halted` 3.650 · `regime_invalid` 2.544 · `approved` 1 |
| `regimeCounts` | `BEAR_TREND` 844 · `HIGH_VOLATILITY` 392 · `SIDEWAYS` 3 |
| `score.realizedCount` | 0 |
| `score.roundTrips` | `[]` |
| `score.meanR` / `medianR` / `positiveShare` | `null` / `null` / `null` |
| `score.openPositions` | 1 (`07621d3dc7b945a3be08c1840`, entry 105,48, last 90,16, stop 102,1418, `unrealizedR` −4,588309) |

`fills = 4` **no son cuatro operaciones**: son cuatro fills parciales de la única orden de compra del primer día, que suman la posición entera.

| Día | Lado | Precio | Cantidad | Stop |
| --- | --- | --- | --- | --- |
| 2022-01-27 | buy | 105,4409 | 94,89465 | 102,1418 |
| 2022-01-27 | buy | 105,4791 | 44,600485 | 102,1418 |
| 2022-01-27 | buy | 105,5217 | 22,129433 | 102,1418 |
| 2022-01-27 | buy | 105,5866 | 28,164732 | 102,1418 |
| | | | **Σ = 189,7893** | |

La posición abrió el 2022-01-27 y **no se cerró en ninguno de los 1.239 ticks**, pese a que el precio (90,16) está por debajo del stop (102,1418) desde hace años. `perDay[*].open` vale 1 en los 1.239 días.

### 1.2 Censo: la "contradicción" aparente no es tal

| Campo del censo | Valor |
| --- | --- |
| `operableDays` | 1.240 |
| `maxOperableStreak` | 1.059 |
| `entriesAllowedLong` | `true` en 1.240 días, `false` en 63 |
| `entriesAllowedLongGlobal` | `true` en 396, `false` en 907 |
| `entryGateScope` | `per_symbol` |
| `operational` (por día) | `BEAR_TREND` 848 · `HIGH_VOLATILITY` 393 · `UNKNOWN` 59 · `SIDEWAYS` 3 |
| `aggregateCounts` | `trend_down` 848 · `high_vol` 393 · `sin_regimen` 59 · `range` 3 |

Correcciones a la premisa del encargo, verificadas en el JSON:

- `operational` **no** es un estado de operabilidad: es `map_trial_regime(aggregate)` (`packages/py/application/src/bolsa_application/replay_oos.py:366`), es decir, la etiqueta del régimen agregado. Toma cuatro valores distintos; `UNKNOWN` sólo en 59 días (los 59 sin barras suficientes). No hay ningún día con `operational = "OPERABLE"` porque ese literal no existe en el artefacto.
- La tensión real es `entriesAllowedLong` (por símbolo, 1.240 `true`) frente a `entriesAllowedLongGlobal` (agregado conservador, 396 `true`). Son dos lecturas distintas a propósito (`replay_oos.py:259-292`): la barrera del hot path es **por símbolo**, y el agregado se conserva como declaración.
- En consecuencia, el censo **no** dice que el gobernador permita entrar: no evalúa al gobernador en absoluto. Mide el gate de régimen de mercado. El estado del gobernador no aparece en el censo.

## 2. Traza del estado del gobernador

### 2.1 Cadena completa, con fichero:línea

1. **Entrada al motor.** `apps/api-python/scripts/v2_86_replay_oos_viability.py:279-303` construye el worker y le inyecta `exec_store`, `context_store`, `position_store`, `consumed_signal_store`, `reservation_store` y `finance_applier`. **No inyecta `exit_order_store`**. Tampoco fija `AUTO_ENGINE_SIM_V2_GOVERNOR` en `_configure_env` (`:61-81`), así que el gobernador queda OFF (default de `V2Tunables.governor_enabled`, `packages/py/application/src/bolsa_application/auto_v2_entry.py:250`).
2. **Primer intento de salida del replay.** El 2022-02-03 la gestión de posición pide una salida. `_v2_save_exit_order` devuelve `False` sin store: `apps/api-python/src/bolsa_api/background/auto_worker_state.py:845-849` (`if store is None: return False`).
3. **Política B.** Al no poder persistir el INTENT ni su versión de emergencia, se engancha la parada dura: `apps/api-python/src/bolsa_api/background/auto_worker_execution.py:810-823` → `engage_kill_switch_durable("SYSTEM_ERROR")`.
4. **Lectura del latch en cada tick.** `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:1405` pasa `halted=self._v2_kill_switch_halted()` a `plan_v2_tick`; el predicado es `apps/api-python/src/bolsa_api/background/auto_worker_safety.py:539-542`. El latch solo se libera con una reconciliación explícita (`release_kill_switch`), que el replay nunca invoca.
5. **Se consulta la tabla del gobernador.** `packages/py/application/src/bolsa_application/auto_v2_entry.py:1651` (`if cfg.governor_enabled or halted:`) hace que, con el flag OFF, la tabla se evalúe igualmente por la parada dura. La llamada (`:1652-1669`) pasa `drawdown_pct=tick_drawdown_pct` y `drawdown_measurement=COMPLETE` sólo si ese número existe.
6. **El drawdown no existe.** `tick_drawdown_pct` sale de `snapshot.drawdown_pct` (`auto_v2_entry.py:1618`), que el worker sólo rellena si el gobernador está ON: `auto_worker_safety.py:924-928` (`account_drawdowns.daily_pct if ... governor_enabled else None`); y `_v2_account_drawdowns` devuelve `None` si gobernador y corte están OFF (`auto_worker_safety.py:489-493`). Verificado en ejecución: 100 % de las lecturas con `drawdown_pct = None`.
7. **Resolución del estado.** `packages/py/analytics/src/bolsa_analytics/cognitive/operational_governor.py:323-324` (`if halted: return "HALTED"`) tiene precedencia sobre todos los ejes. Sin parada, el mismo insumo habría dado `EXIT_ONLY` (`_DRAWDOWN_CAP["UNKNOWN"]`, `:167`; `_RISK_CAP["UNKNOWN"]`, `:157`), es decir `governor_exit_only`, **no** `HALTED`.
8. **Veto del motor.** `packages/py/application/src/bolsa_application/portfolio_decision_engine.py:543-547`: `if governor_state in ("EXIT_ONLY","HALTED")` → `governor_halted` si `HALTED`. El paso 3.b va **después** de `regime_invalid` (`:536-537`), así que todo `governor_halted` implica que el régimen de ese símbolo **sí** permitía entrar.

`market_operability.py` no alimenta el gobernador: sólo clasifica el código de motivo en la familia `governor` (`packages/py/application/src/bolsa_application/market_operability.py:155-161`). Es un lector del journal, no la fuente del estado.

### 2.2 Verificación empírica: el estado es constante

Reproducción instrumentada del replay completo (mismo comando, sin `--out`, parcheando en proceso `auto_turn` y `assess_from_measurements`; no se escribió ningún fichero):

- Totales idénticos al artefacto: `decided` 24.780, `proposals` 1.200, `vetoes` 24.779, `orders` 1, `fills` 4; `journalReasons` idénticos; `regimeCounts` idénticos.
- Transiciones del latch: `(2022-01-27, False/None)` → `(2022-02-03, True/SYSTEM_ERROR)`. **Nunca vuelve a `False`** en los 1.237 ticks restantes.
- Llamadas a `assess_from_measurements`: **6.165**, todas con la misma firma:

| n | régimen | drawdown_pct | medición | halted | estado | eje vinculante | risk_regime |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 4.190 | `BEAR_TREND` | `None` | `UNKNOWN` | `true` | `HALTED` | `halted` | `UNKNOWN` |
| 1.960 | `HIGH_VOLATILITY` | `None` | `UNKNOWN` | `true` | `HALTED` | `halted` | `UNKNOWN` |
| 15 | `SIDEWAYS` | `None` | `UNKNOWN` | `true` | `HALTED` | `halted` | `UNKNOWN` |

- `governor_halted`: 3.650 ocurrencias en **1.177 de 1.239 días** (95,0 %), primera el 2022-02-09, última el 2026-11-12; media 2,96/día (máx. 5). Cero ocurrencias antes del `2022-02-03`. Motivo dominante del día en 145 jornadas.
- `governor_exit_only`: **0 ocurrencias**. Es la prueba negativa del diagnóstico: si el gobernador estuviera evaluando una cuenta *no medida*, el código habría sido `governor_exit_only`, no `governor_halted`.
- Eventos de gestión que acompañan a la parada: `exit_permission` 1.199, `kill_switch` 1.198, `exit_not_emitted` 1.198 — la parada pide salir todos los días y la salida no se emite porque su INTENT no se puede persistir.

### 2.3 Contraste con el mismo replay cableado

Mismos 40 ticks (2022-01-27 → 2022-03-23), mismo código, **una sola diferencia**: inyectar `exit_order_store=InMemoryExitOrderStore()` (lo que ya hace `apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py:402`).

| | Artefacto / cableado actual | Con `exit_order_store` en memoria |
| --- | --- | --- |
| latch | `SYSTEM_ERROR` desde el tick 6, permanente | nunca se engancha |
| llamadas al gobernador | 40 (todas `HALTED`) | **0** (flag OFF ⇒ ni se consulta) |
| `governor_halted` | 1/día desde el 2022-02-09 | **0** |
| órdenes / fills | 1 / 4 (parciales de la misma compra) | 14 / 49 |
| idas y vueltas cerradas | 0 | 5 |
| `meanR` | `null` | −1,2756 |
| `positiveShare` | `null` | 0,2 |

Tercer control, para aislar al gobernador del latch: mismos 40 ticks con `exit_order_store` **y** `AUTO_ENGINE_SIM_V2_GOVERNOR=1`.

- Estados: 150 × `ENTRY_RESTRICTED` (eje `market`, `BEAR_TREND`), 50 × `ENTRY_REDUCED` (eje `market`, `HIGH_VOLATILITY`). `drawdown_pct = 0.0`, `risk_regime = RISK_ON`. **Cero `HALTED`, cero `EXIT_ONLY`.**
- Resultado: 6 órdenes, 19 fills, 2 idas y vueltas, `meanR` −1,1169, `positiveShare` 0,0.

## 3. Veredicto

**(b), con la siguiente precisión de mecanismo.** El `governor_halted` masivo no es el gobernador de riesgo decidiendo: es el **latch de parada dura** (`HardKillSwitch`) enganchado por una escritura que el replay no puede hacer y que, por la política B de execution, degrada a `SYSTEM_ERROR`. El gobernador sólo aparece en el journal porque `halted=True` fuerza la evaluación de la tabla (`auto_v2_entry.py:1651`) y `HALTED` tiene precedencia absoluta (`operational_governor.py:323-324`).

Evidencia que lo sostiene:

1. **El gobernador no tiene insumo de cuenta**: `governor_enabled=False` y `account_max_drawdown_pct=None` en el replay, así que `drawdown_pct` es `None` en las 6.165 lecturas. No hay `core_r_account_state` ni equivalente, pero el efecto **no** es un `HALTED` fail-closed del gobernador: con ese insumo el estado sería `EXIT_ONLY` y el motivo `governor_exit_only`, que aparece **0 veces**.
2. **El eje vinculante es `halted`**, no `drawdown` ni `risk`, en el 100 % de las lecturas.
3. **El latch nace de un fallo de cableado, no de mercado**: `_v2_save_exit_order` devuelve `False` porque `exit_order_store` no se inyecta; el propio repo lo inyecta en el replay siguiente (`v2_87...py:402`) y en los tests.
4. **Basta corregir ese cableado para que el gobernador desaparezca del journal** (0 llamadas, 0 `governor_halted`) y el motor vuelva a operar en la misma ventana.
5. **La posición congelada es el mismo fallo visto por el otro lado**: cada tick pide salir, la salida no se emite (`exit_not_emitted` 1.198), el stop lleva años rebasado y el `score` no puede cerrar ni una ida y vuelta.

Proporción: de las 3.650 ocurrencias de `governor_halted`, **3.650 son artefacto** (0 son parada legítima por drawdown). De la ausencia práctica de operaciones, la parte atribuible al artefacto es la totalidad de lo observado: 1 orden y 0 cierres en el artefacto frente a 14 órdenes y 5 cierres en los mismos 40 ticks con el cableado corregido.

Lo que **sí** es del motor y no del artefacto (y por tanto sobrevive a la corrección):

- `regime_invalid` 2.544: el gate direccional por símbolo funciona. La ventana es mayoritariamente bajista (`trend_down` 848 días).
- `top_n_excluded` 4.957: `AUTO_ENGINE_SIM_V2_TOP_N=5` deja fuera del motor de decisión a la mayoría del watch. Es una compuerta de evaluación, no un veto de riesgo.
- Con el cableado corregido, el resultado sigue siendo malo (`meanR ≈ −1,2`, `positiveShare` 0,0-0,2 en 40 ticks). Eso es una señal sobre la ventana/estrategia, no sobre el gobernador.

Lo que **no** se puede concluir con este artefacto:

- No se puede afirmar nada sobre viabilidad del motor (ni a favor ni en contra): el `score` del artefacto no mide al motor.
- No se puede afirmar ni descartar que el gobernador de drawdown frene en producción: en el replay nunca se le da un drawdown medido y, con `GOVERNOR=1`, el `daily_pct` es 0,0 en los 200 ticks observados porque en D1 la marca se reabre cada día (`EquityMarkBook` diario) y no hay serie de cuenta durable.
- No se puede extrapolar el `meanR` de los 40 ticks corregidos a los 1.239: sólo se ha ejecutado la ventana corta.
- El censo no mide al gobernador: `operableDays=1240` es el gate de régimen por símbolo, no un permiso del gobernador.

## 4. Qué habría que cambiar para que el replay mida viabilidad

Nada de esto es una mejora del motor; es reparación del instrumento.

1. **Inyectar `exit_order_store=InMemoryExitOrderStore()`** en `v2_86_replay_oos_viability.py` (como ya hace `v2_87_replay_oos_durable_cycle.py:402`). Sin él, cualquier salida protectora engancha `SYSTEM_ERROR` y el replay pasa a medir la parada dura.
2. **Declarar el latch en el artefacto y tratarlo como fallo de la corrida, no como veto.** Hoy el JSON no tiene campo de parada dura: `governor_halted` es indistinguible de un veto legítimo. Debería publicarse por tick `killState {engaged, reason, day}` y abortar/declarar la corrida si el latch se engancha y no se libera.
3. **No reutilizar `governor_halted` para la parada dura.** El paso 3.b (`portfolio_decision_engine.py:543-547`) colapsa `halted` y `EXIT_ONLY` en dos códigos que ocultan el eje que fijó el techo. El `OperationalAssessment` ya publica `binding_axis`; el `reasonCodes` del journal debería permitir atribuirlo (código propio para kill switch, o `bindingAxis` en el payload).
4. **Decidir explícitamente el flag del gobernador y su insumo.** Si el replay quiere medir el gobernador: `AUTO_ENGINE_SIM_V2_GOVERNOR=1` **y** una serie de equity declarada. Hoy `_v2_account_drawdowns` usa `AUTO_ENGINE_SIM_V2_EQUITY` como depósito inicial y P&L realizado/no realizado del propio simulado; es una base sintética, no estado durable, y en D1 el `daily_pct` se resetea cada tick (medido: 0,0 siempre). Para el corte pico-valle haría falta además `AUTO_ENGINE_SIM_V2_ACCOUNT_MAX_DD_PCT` (`auto_v2_entry.py:501-515`), que tampoco está fijado.
5. **Guardarraíl de coherencia.** Fallar la corrida si aparece `governor_halted`/`governor_exit_only` mientras `drawdown_band == UNKNOWN` o si el latch está enganchado más de N ticks. Esa combinación es siempre un síntoma de cableado, nunca una medición.
6. **Separar en el informe las tres familias** que hoy se leen juntas: `regime` (hecho de mercado), `top_n` (tope de evaluación) y `governor` (permiso). El artefacto ya tiene el vocabulario (`market_operability.py`); lo que falta es que el replay no mezcle la parada dura con el permiso.

## 5. Reproducción exacta

Todos los comandos se ejecutaron desde la raíz del repo, con el árbol de trabajo intacto y sin `--out` (para no sobrescribir el artefacto).

### 5.1 Verificación de los números del artefacto

```powershell
.venv\Scripts\python.exe -c "import json; d=json.load(open('operability_runs/oos/v2_86.json',encoding='utf-8')); print(d['replay']['totals']); print(d['replay']['journalReasons']); print(d['replay']['regimeCounts']); print(d['replay']['score']['realizedCount'], d['replay']['score']['meanR']); print(d['census']['operableDays'], d['census']['operableByOperational'])"
```

### 5.2 Replay corto (6 ticks) con el cableado del artefacto

```powershell
.venv\Scripts\python.exe apps\api-python\scripts\v2_86_replay_oos_viability.py --max-ticks 6
```

Resultado: `2022-01-27 → 2022-02-03`, `orders 1`, `fills 4`, y en el tick del 2022-02-03 el log
`ERROR ... auto_sim v2 exit intent persist failed intent=...; HALT`. A partir de ahí el latch queda en `SYSTEM_ERROR`.

### 5.3 Reproducción completa instrumentada (mismos totales que el artefacto)

Sin `--out`; el parche es en proceso (no se crea ni edita ningún fichero). Esqueleto exacto:

```python
import bolsa_api.background.auto_simulation_worker as w
import bolsa_application.auto_v2_entry as a2
orig_turn, orig_assess = w.AutoSimulationWorker.auto_turn, a2.assess_from_measurements

# envuelve assess_from_measurements para registrar
# (régimen, drawdown_pct, medición, halted, estado, binding_axis)
# envuelve auto_turn para registrar por día: reasonCodes del journal, latch y posiciones abiertas.

spec = importlib.util.spec_from_file_location(
    "v286", "apps/api-python/scripts/v2_86_replay_oos_viability.py")
m = importlib.util.module_from_spec(spec); sys.modules["v286"] = m; spec.loader.exec_module(m)
m.main([])   # sin --out
```

Salida verificada:

El artefacto sólo agrega la población `auto_entry_decision` (`top_n_excluded`, `regime_invalid`,
`approved`, `governor_halted`); en la traza aparecen además los eventos de gestión de posición
(`exit_permission`, `kill_switch`, `exit_not_emitted`), que el artefacto no publica y que son los
que muestran la salida pedida y no emitida.

```
turn totals   {'decided': 24780, 'proposals': 1200, 'vetoes': 24779, 'orders': 1, 'fills': 4}
journal total {'top_n_excluded': 4957, 'regime_invalid': 2544, 'approved': 1,
               'exit_permission': 1199, 'kill_switch': 1198, 'exit_not_emitted': 1198,
               'governor_halted': 3650}
kill_transitions [('2022-01-27', (False, None)), ('2022-02-03', (True, 'SYSTEM_ERROR'))]
dias con governor_halted 1177 (2022-02-09 .. 2026-11-12), media 2.96/dia, max 5
assess: 4190 BEAR_TREND + 1960 HIGH_VOLATILITY + 15 SIDEWAYS,
        todas (drawdown=None, UNKNOWN, halted=True, HALTED, axis='halted', RISK=UNKNOWN)
```

### 5.4 Contraste: mismo replay con el store de salidas en memoria

Mismo `main(['--max-ticks','40'])`, mismo parche de observación, añadiendo:

```python
from bolsa_application.exit_order_store import InMemoryExitOrderStore
orig_init = w.AutoSimulationWorker.__init__
def init_patch(self, *a, **kw):
    kw.setdefault("exit_order_store", InMemoryExitOrderStore())
    return orig_init(self, *a, **kw)
w.AutoSimulationWorker.__init__ = init_patch
```

Salida: `orders 14`, `fills 49`, `realizedCount 5`, `meanR −1.2756161350783195`, `positiveShare 0.2`,
`assess calls = 0`, `governor_halted = 0`, latch nunca enganchado.

### 5.5 Contraste: gobernador ON y store de salidas

Igual que 5.4 más `os.environ['AUTO_ENGINE_SIM_V2_GOVERNOR'] = '1'` antes de construir el worker.

Salida: `orders 6`, `fills 19`, `realizedCount 2`, `meanR −1.1168927520737748`, `positiveShare 0.0`;
estados `150 × ENTRY_RESTRICTED (eje market, BEAR_TREND)` y `50 × ENTRY_REDUCED (eje market, HIGH_VOLATILITY)`,
con `drawdown_pct = 0.0` y `risk_regime = RISK_ON`. Cero `HALTED`.
