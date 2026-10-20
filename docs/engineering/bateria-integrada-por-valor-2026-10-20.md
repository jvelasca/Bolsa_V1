# Batería integrada POR VALOR — identidad ganadora → señal/plan → ciclo SIM → DÍA-D → P&L

**Fecha:** 2026-10-20 · **Árbol:** `2.11.153-beta` (`[Unreleased]`) · **Sin sello nuevo**.

**Naturaleza:** frente de **medición pura** (pytest + PostgreSQL real). **`Δ motor = 0`**,
**`Δ decisión = 0`**, **`Δ contrato HTTP = 0`** (no se toca ningún DTO), **sin migración**
(`head` sigue `057_top3_opportunity_identity`). Lo único que cambia fuera de `tests/` es el
**lector** `auto_operational_monitor._build_cycle` (selección de la reserva de entrada) y el
cableado del gate en CI: el motor de decisión no se toca.

**Fichero nuevo:** [`apps/api-python/tests/test_auto_identity_chain_battery_pg.py`](../../apps/api-python/tests/test_auto_identity_chain_battery_pg.py)
· **Gate fail-if-skipped:** `AUTO_IDENTITY_CHAIN_PG_REQUIRED=1`.

---

## 1. Qué demuestra (los seis eslabones)

| # | Eslabón | Hecho durable que lo sostiene | Aserción |
|---|---|---|---|
| 1 | **Identidad GANADORA** | `top3_opportunities` (migración `057`) `strategy_preset_key`/`strategy_version` del `rank 1` | `bestScoredPresetKey == "sma_crossover"`, `bestScoredStrategyVersion == "v1"`, `strategyMeasurement == COMPLETE` |
| 2 | **Identidad EJECUTADA** | `decision_journal_entries.auto_entry_decision` con `signalId`, `opportunityId`, `rank`, `strategyPresetKey`, `strategyVersion` | recuperada por `cycle_decision_id(cycleId)` (`cyc-<x>` → `dec-<x>`), sin recalcular ningún digest |
| 3 | **Señal y plan** | `V2Signal` con preset/versión desde `DecisionPackage.source = active-strategy:v1::sma_crossover`; `TradePlan` con `thesis_id = decision_id` | el ciclo declara `opportunityId`, el `rank` es entero `> 0` y la decisión de cartera está enlazada |
| 4 | **Ciclo SIM** | reserva, orden, fill (`sim_fill_finance_context`), protección (`source=plan`), liquidación y cierre | las **nueve** etapas canónicas `SIGNAL`…`CYCLE_CLOSED` valen `1` (`chain.complete is True`) |
| 5 | **DÍA-D** | `dia_d_cycle_verifications` escrita con la identidad **copiada del ciclo** | `diaDLink.linkable is True`, `executedVsDiaD.matches is True`, `measurement == COMPLETE` |
| 6 | **Resultado conciliado** | `CYCLE_CLOSED.pnl` ↔ `SETTLEMENT.pnl` ↔ libro **aplicado** (`execution_events.status='APPLIED'`) | `reconciled is True` y ambos lados iguales al quantum `0.000001`, con notional bruto `> 0` |

El día se conduce por el camino **productivo** (`AutoSimRuntime.run_tick` →
`auto_turn`), no por una siembra a mano: abre con un `BUY` real, **re reinicia** el worker
para demostrar la readopción durable (`opened == 0`: no se apila un segundo `BUY`), lleva
el `holdingDeadlineAt` al pasado (seam `E1` del Golden Day) y **cierra por `time_exit`** con
un tercer worker que rehidrata el plan vencido. Todo `in-process`, sin subproceso.

## 2. El TRI-ESTADO, fijado con un control NEGATIVO

Segundo test del mismo fichero: la fuente declara versión pero **no** preset
(`auto-2.0:v1`, sin `::<preset>`). Lo esperado —y ahora **falsable**— es:

- `executed.measurement == "PARTIAL"` (nunca `COMPLETE`: afirmaría una identidad completa);
- `executed.strategyPresetKey is None` (la ausencia es información, no relleno);
- `executedVsBest.presetMatch is None` (**nunca** `False`: no hay término de comparación);
- tras escribir la verificación DÍA-D **copiando el hueco**, `diaDLink.linkable is True` pero
  `executedVsDiaD.matches is None` y `measurement == "UNKNOWN"`.

Sin el control negativo, `PARTIAL` podría degradarse a `COMPLETE` sin que nada se pusiera
rojo: ese es exactamente el defecto que la auditoría del sello `.153` encontró.

## 3. Defecto de lectura que la batería destapó (corregido)

`_build_cycle` tomaba `reservations[0]` como la reserva del ciclo. Desde `V2.47` la **salida**
también declara `cycle_id` (para reconstruir el PnL hacia atrás), así que un ciclo cerrado
tiene **dos** reservas y el orden durable pone primero la de salida
(`exit:<orderId>`, `side='sell'`, **sin** `strategy_version_id`). Consecuencia medida en el
arnés: un ciclo con identidad **completa** en su entrada se publicaba como
`direction = "short"` y `strategyVersion = None` ⇒ el monitor (y con él la evidencia y la
ficha) degradaba a **parcial** una identidad que sí estaba sellada.

Corrección (`auto_operational_monitor._entry_reservation`): se prefiere la reserva de
**entrada** (`side == 'buy'`) y, solo si no hay ninguna, se conserva el orden histórico. No
se rellena nada: la salida sigue declarando lo que declara.

## 4. Límites declarados (no se cierran aquí, y no se finge que sí)

- **El parte diario ESTUDIO no comparte identidad.** `estudio_auto_hits` fija
  `strategyVersion=1` y `presetKey="estudio_auto"`, y `estudio_daily_ops` descarta
  `decisionId`: el enlace identidad-del-TOP3 → **parte diario** sigue sin existir. Esta
  batería mide la identidad del **motor AUTO 2.0**, no la del parte.
- **El `TradePlan` no publica `planId`/`signalId` en el DTO del ciclo.** La atribución
  plan↔ciclo se demuestra por `decisionId` (y `thesis_id` en el plan), no por el contrato de
  la UI.
- **La verificación DÍA-D del test es una fila derivada del ciclo, no un replay real.** Se
  compone con `build_dia_d_cycle_verification_draft` a partir de los hechos del ciclo para
  demostrar el **enlace**; no se ejecuta el replay del día.
- **`executedIsBestScoredAsset` compara `instrumentId` sin canonizar símbolos.** En este
  arnés coincide (`True`) porque la foto colapsa al `instrument_id` base; si el catálogo
  usara el SÍMBOLO como `instrument_id` la comparación sería `False` sin que haya divergencia
  real. Se documenta como observación; no se fija como contrato.
- **AUTO sigue OFF**, la ventana PAPER sigue **`INCONCLUSIVE`**, **`CONFIRMED` no se emite** y
  la operativa es **100 % SIM**: esto demuestra **trazabilidad**, no rentabilidad.
- Las fotos `top3_opportunities` anteriores a la `057` siguen `NULL` y se leen como
  desconocidas (sin backfill).
- El arnés exige un `instrument_id` **determinista que llene** (`_filling_instrument_id`,
  barrida pura sobre las dos barras que un run puede atravesar): con un id aleatorio el ancla
  de barra deja ~12 % de días sin cierre por cola noisy, que sería un rojo espurio del
  harness, no del motor.

## 5. Cómo se ejecuta

```powershell
# Batería nueva (positivo + control negativo)
$env:AUTO_IDENTITY_CHAIN_PG_REQUIRED="1"
uv run pytest apps/api-python/tests/test_auto_identity_chain_battery_pg.py -q

# Regresión del TRI-ESTADO en la cadena ESTUDIO (proceso real)
$env:AUTO_ESTUDIO_CHAIN_PG_REQUIRED="1"
uv run pytest apps/api-python/tests/test_auto_estudio_chain_evidence_pg.py -q
```

Sin PostgreSQL real ambos hacen `pytest.skip`; **con el gate a `1` un skip es FALLO DURO**.

## 6. Cableado CI

En [`.github/workflows/release-tag-ci.yml`](../../.github/workflows/release-tag-ci.yml) (job
`lifecycle-pg`):

- `AUTO_IDENTITY_CHAIN_PG_REQUIRED: '1'` junto a los demás gates del job;
- el fichero entra en el paso **DEDICADO** `Pytest AUTO universe coverage + DÍA-D trace +
  daily watch ESTUDIO + PAPER window + ESTUDIO chain + identity battery (PG, fail if
  skipped)`, cuyo guard **anti-skip** (log no vacío + `grep` de `skipped` ⇒ `::error`) ya
  cubre la corrida;
- el censo [`scripts/ci/test_selection.py`](../../scripts/ci/test_selection.py) `--report`
  cierra en **651/651 ejecutados · 0 sin declarar · 0 obsoletas**.

## 7. Verificación medida (local, PostgreSQL real)

| Comprobación | Resultado |
|---|---|
| `test_auto_identity_chain_battery_pg.py` (gate ON) | **2 passed in 2.91s** (objetivo `< 5 s`) |
| `test_auto_estudio_chain_evidence_pg.py` (gate ON, proceso real) | **1 passed in 9.14s** |
| Lector/monitor/AUTO identity + ruta de cadena + DÍA-D (hermético) | **142 passed in 4.49s** |
| `test_auto_operational_monitor_pg` + `test_auto_dia_d_trace_pg` + `test_auto_v2_durable_pg` | **20 passed in 20.86s** |
| `pnpm lint:py` | **`All checks passed!`** |
| `pnpm imports:py` | **4 kept / 0 broken** |
| `pnpm types:py` | **no issues in 567 source files** |
| Censo `test_selection.py --report` | **651/651 · 0 sin declarar · 0 obsoletas** |
