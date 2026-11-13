# DÍA-D retrospectivo as-run (2026-11-13)

> **Estado:** implementado · **ADR:** [ADR-049](../adr/049-adaptacion-gobernada-por-ia.md)  
> **Método:** rejugar **la operativa que realmente llevábamos** desde el día `D` hasta hoy y compararla con cinco brazos contrafactuales y un benchmark de mercado.  
> **Código:** [`dia_d_as_run.py`](../../packages/py/application/src/bolsa_application/dia_d_as_run.py) · [`dia_d_certification.py`](../../packages/py/application/src/bolsa_application/dia_d_certification.py) · [`adaptation_validation.py`](../../packages/py/application/src/bolsa_application/adaptation_validation.py) · [`v2_102_dia_d_as_run.py`](../../apps/api-python/scripts/v2_102_dia_d_as_run.py) · [`auto_ops_dia_d_as_run.py`](../../apps/api-python/src/bolsa_api/background/auto_ops_dia_d_as_run.py) · [`auto_dia_d.py`](../../apps/api-python/src/bolsa_api/api/v1/routes/auto_dia_d.py)

---

## 1. Qué responde y en qué se diferencia

El DÍA-D **forward** (`v2_89`–`v2_93`) rejuega **el motor** desde `D`: mide qué *habría decidido* la estrategia con el reloj y los precios inyectados. Ese método responde «¿qué habría hecho la estrategia?».

El DÍA-D **as-run** parte del **estado durable real de `D`** —posiciones abiertas, stops estructurales, targets, mandato y órdenes— y evalúa hacia hoy. Responde otra pregunta:

> *«Si en `D` hubiéramos seguido exactamente la operativa que llevábamos, ¿qué habría pasado hasta hoy, y qué aportó o costó cada decisión?»*

La diferencia no es cosmética: el forward mide una hipótesis; el as-run mide **la decisión que ya estaba tomada**. Un stop real que estaba a 3 ATR no se reemplaza por el stop que el motor habría calculado hoy.

## 2. Brazos

| Brazo | Estado inicial | Regla de salida | Para qué sirve |
| --- | --- | --- | --- |
| `as_run` | posiciones durables de `D` | **fills reales** posteriores a `D` | Mide lo ejecutado. Es la referencia. |
| `hold_structural` | las mismas posiciones | stop estructural real hasta hoy | ¿Aportó valor salir antes? |
| `cash` | sin posiciones | `realizedR = 0` medido | ¿Aportó valor estar expuesto? |
| `engine_params` | las mismas posiciones | stop/target del motor con los parámetros vigentes | ¿El motor actual habría hecho mejor? |
| `candidate` | posiciones de la candidata (si existe) | igual que `hold_structural` | Mide la propuesta antes de promoverla. |
| `market_bh` | instrumentos del estado inicial | compra y mantiene equiponderado | Benchmark de mercado: ¿el mercado habría pagado más? |

`cash` es el único brazo con `realizedR = 0.0` de forma legítima: **es** una decisión de no exponerse, no un hueco rellenado.

`market_bh` **no tiene stop**, así que no tiene denominador de riesgo: publica `returnPct` y `pnlCurrency`, y deja `realizedR = null`. Convertirlo en `0 R` sería inventarse una medida. No compite en la comparación de R de las cohortes; está ahí para saber si el mercado pagaba más que la operativa.

Para que esa comparación signifique algo, el benchmark comparte con la estrategia **universo** (el declarado en D, no las claves de barras cargadas), **capital** (el notional inicial de las patas, repartido equiponderado; si el día es solo caja se declara `capitalBasis = "unit"`), **periodo** (primera barra posterior a D hasta la última `<= toDay`) y **coste** (el mismo modelo, con deslizamiento por ser contrafactual). La liquidez se evalúa con la cantidad real del reparto, nunca con una unidad simbólica.

## 3. Las ocho condiciones de validez

Un DÍA-D es válido como reconstrucción histórica si cumple las ocho. `dia_d_certification.certify_artifact` las verifica una a una:

| # | Condición | Qué exige | Cómo falla |
| --- | --- | --- | --- |
| 0 | `artifact_integrity` | `hash` recalculable sobre el artefacto completo | sin hash ⇒ `NOT_EVALUATED`; distinto ⇒ `FAIL` |
| 1 | `temporal_freeze` | día `D`, fuente del estado y `legsHash` declarados; `sourceIsReconstructed = false` | dato ausente ⇒ `NOT_EVALUATED`; día distinto o estado reconstruido ⇒ `FAIL` |
| 2 | `initial_state` | patas reales con instrumento, cantidad y entrada; `legsHash` recalculable; universo de D **declarado** | hash manipulado o `cashOnly` con patas ⇒ `FAIL`; universo derivado ⇒ `NOT_EVALUATED` |
| 3 | `sequential_replay` | decisiones por brazo medido, ordenadas y `>= D` | ausentes o desordenadas ⇒ `FAIL` |
| 4 | `real_market_data` | fuente, timeframe, `barsHash` y manifest por vela recomputable | sin huella ⇒ `NOT_EVALUATED`; manifest roto, desordenado o con otra huella ⇒ `FAIL` |
| 5 | `realistic_execution` | `roundTripBps > 0` igual a `costBps`, deslizamiento declarado, cota de liquidez, política de gaps y base de coste de los fills reales | coste 0, incoherente o `effective` con coste en caja ⇒ `FAIL` |
| 6 | `benchmarks` | `as_run`, `cash` y `market_bh` medidos, con universo, capital y coste del benchmark declarados | benchmark no medido o incomparable ⇒ `FAIL`/`NOT_EVALUATED` |
| 7 | `audit` | motor, esquema, bump, `paramsHash` **recomputado** desde `audit.params` y límites declarados | ausente ⇒ `NOT_EVALUATED`; motor, esquema o params incoherentes ⇒ `FAIL` |

Veredictos: `certified`, `not_certified` (con `failures`, `notEvaluated` y `reasons`) y, a nivel de cohorte, `insufficient_sample` si no hay muestra mínima. **`NOT_EVALUATED` nunca cuenta como PASS.** Los artefactos v1 sin sobre de auditoría se siguen leyendo y salen `not_certified`: no se reescriben.

**Qué detecta y qué no la cadena de hashes.** Detecta cualquier edición posterior al sellado: cambiar una vela, un parámetro, una pata, un `realizedR`, el `bump` o la propia certificación rompe la condición correspondiente. **No** puede distinguir a un productor que reescriba artefacto *y* hashes de forma coherente: eso exige una firma o un sello externo al propio fichero. La certificación es verificación de integridad, no autenticidad.

La certificación **no mira el signo del resultado**. Un DÍA-D certificado puede ser negativo y sigue siendo útil: certifica el método, no la rentabilidad.

## 4. Modelo de ejecución

`AsRunExecutionModel` se declara una vez y se aplica a todos los brazos:

| Campo | Efecto |
| --- | --- |
| `commissionBps` | comisión por lado, cobrada en caja |
| `slippageBps` | empeora el precio de ejecución (comprar más caro, vender más barato) |
| `spreadBps` | coste de ida y vuelta añadido en caja |
| `roundTripBps` | `2 × (comisión + deslizamiento) + spread`; es el `costBps` publicado |
| `executionCostBps` | `2 × comisión + spread`: lo que se cobra en caja (el deslizamiento ya va en el precio) |
| `maxParticipationPct` | cota de la cantidad que una barra puede absorber (`volumen × pct`) |
| `gapPolicy` | `open` (real) o `theoretical` (solo para comparar metodologías) |
| `realFillsCostBasis` | `quoted` (el fill es bruto y se cobra el coste) o `effective` (ya es neto y no se cobra) |

Reglas:

- **Un solo coste.** El coste en caja se imputa **una vez** sobre el notional de cierre: `|cantidad × precio de salida| × executionCostBps/10⁴`. Es la única función de coste del módulo, así que el mismo ciclo paga lo mismo medido por `as_run` (fills) que por `hold_structural` (barras): 1.000 € y 32 bps son 3,20 € en ambos. Antes había dos convenciones y el brazo real pagaba medio coste por lado.
- **Gap adverso**: largo con `open <= stop` ⇒ fill al `open`; el R sale peor que el stop teórico. Corto, espejo. Un hueco favorable al target se ejecuta igualmente al `open`.
- **Deslizamiento** solo en brazos contrafactuales. `as_run` usa fills reales: su precio ya está ejecutado y no se toca. `realFillsCostBasis = "effective"` declara que ese precio además ya es neto de coste; con `quoted` el coste se cobra en caja. `effective` exige `executionCostBps = 0` (cobrar otra vez lo duplicaría) y se publica en el sobre de auditoría.
- **Excursiones sin futuro.** MAE/MFE se acumulan mientras la posición sigue viva; en la barra de salida solo cuentan el `open` y el precio ejecutado. Un máximo posterior a la salida no infla el MFE ni el `capture`.
- **Liquidez**: si la cantidad supera `volumen × maxParticipationPct`, el cierre se difiere al `open` de la primera barra que sí la absorba (se marca `*_deferred` y `deferred_exits:n`). Si no existe, `liquidity_insufficient` y brazo no medido. Nunca se asume liquidez infinita.
- **Compatibilidad**: `cost_bps` es el coste **round-trip** declarado; sin modelo explícito se construye uno con `commission = cost_bps / 2`, deslizamiento 0 y la misma cota de liquidez por defecto (10 % del volumen).

## 5. Sobre de auditoría `DiaDAsRunAuditV1`

| Bloque | Contenido |
| --- | --- |
| `pointInTime` | `day`, `toDay`, `stateSource`, `sourceIsReconstructed`, `legsHash`, patas completas, `candidateAsOf`, `universe` y `universeSource` (`declared`/`derived`) |
| `data` | `barsSource`, `timeframe`, `barsHash`, **`barsManifest`** (`[día, sha256(vela)]` por instrumento), barras y primer/último día por instrumento |
| `versions` | `engine`, `schema`, `bump`, `strategy`, `mandate`, `paramsHash` |
| `params` | los parámetros declarados cuyo hash se recomputa al certificar |
| `execution` | el modelo del §4 serializado (incluida `realFillsCostBasis`) |
| `benchmark` | `universe`, `capitalBasis`, `capital`, `costBps`, `toDay`: con qué se comparó el benchmark |
| `decisions` | por brazo: `{date, instrument, action, price, reason}` ordenado |
| `limits` | límites declarados que el usuario debe leer |

`barsHash` y `legsHash` usan el mismo canonicalizado determinista (`sort_keys`, separadores compactos) que el `hash` del artefacto. Mismo input ⇒ mismo hash. `barsHash` es el hash del **manifest**, no de un resumen: cada vela aporta `[día, sha256(día|open|high|low|close|volume)]`, así que cambiar una sola vela —o quitar una— cambia el hash y la certificación lo ve. `verify_bars_manifest(manifest, barras)` vuelve a comparar el manifest con la fuente; el CLI lo aplica con `--verify-bars` y aborta si no coincide.

## 6. Artefacto `DiaDAsRunArtifactV2`

```json
{
  "engine": "dia-d-as-run-v2",
  "schemaVersion": "DiaDAsRunArtifactV2",
  "day": "2026-09-30",
  "toDay": "2026-11-13",
  "account": "acc",
  "universe": "watch",
  "costBps": 32.0,
  "startingState": {"legs": 2, "instruments": ["AAA", "BBB"], "cashOnly": false},
  "arms": [
    {
      "arm": "as_run",
      "measured": true,
      "realizedR": 1.25,
      "pnlCurrency": 100.0,
      "maeR": -0.4,
      "mfeR": 2.0,
      "capture": 0.62,
      "returnPct": 1.5,
      "exits": 1,
      "stops": 0,
      "targets": 1,
      "legs": 2,
      "reasonCodes": [],
      "decisions": [
        {"date": "2026-09-30", "instrument": "AAA", "action": "carried_in", "price": 100.0, "reason": "initial_state"},
        {"date": "2026-10-08", "instrument": "AAA", "action": "exit", "price": 112.5, "reason": "target"}
      ]
    }
  ],
  "gaps": [{"arm": "candidate", "reason": "candidate_not_point_in_time"}],
  "measured": true,
  "audit": {
    "pointInTime": {"day": "2026-09-30", "stateSource": "sim_auto_positions", "sourceIsReconstructed": false, "legsHash": "<sha256>", "legs": [], "candidateAsOf": null, "universe": ["AAA", "BBB"], "universeSource": "declared"},
    "data": {"barsSource": "postgres:ohlcv_bars", "timeframe": "1d", "barsHash": "<sha256>", "barsManifest": {"AAA": [["2026-10-01", "<sha256>"]], "BBB": [["2026-10-01", "<sha256>"]]}, "instruments": []},
    "versions": {"engine": "dia-d-as-run-v2", "schema": "DiaDAsRunArtifactV2", "bump": "2.11.189-beta", "paramsHash": "<sha256>"},
    "params": {"engineStopMultiplier": null, "engineTargetMultiplier": null, "universe": "watch", "execution": {"...": "..."}},
    "execution": {"commissionBps": 10.0, "slippageBps": 5.0, "spreadBps": 2.0, "roundTripBps": 32.0, "executionCostBps": 22.0, "maxParticipationPct": 0.1, "gapPolicy": "open", "realFillsCostBasis": "quoted"},
    "benchmark": {"universe": ["AAA", "BBB"], "capitalBasis": "initial_notional", "capital": 1000.0, "costBps": 32.0, "toDay": "2026-11-13"},
    "decisions": {},
    "limits": []
  },
  "certification": {"version": "DiaDCertificationV1", "verdict": "certified", "certified": true, "checks": [], "failures": [], "notEvaluated": [], "reasons": [], "hash": "<sha256>"},
  "hash": "<sha256>",
  "meta": {"account": "acc", "bump": "2.11.203-beta", "stateSource": "sim_auto_positions"}
}
```

Tipos TypeScript: [`packages/shared/src/dia-d-as-run.ts`](../../packages/shared/src/dia-d-as-run.ts) (`DiaDAsRunArtifactV1` se mantiene como contrato legible de v1; `DiaDAsRunAuditV1`, `DiaDAsRunCertificationV1`, `DiaDAsRunExecutionModelV1` son aditivos).

## 7. LAB y DÍA-D: veredictos separados

| | LAB | DÍA-D as-run |
| --- | --- | --- |
| Qué mide | el experimento (hold-out WF) | la reproducción histórica de la operativa real |
| Entrada | métricas del candidato | artefactos as-run + estado durable |
| Gates | retorno neto, DD, ventanas, exceso vs compra, coste, muestra, pruebas múltiples | `as_run_certification` + `as_run_cohort` |
| Hash | `lab.hash` | `asRun.hash` |
| Puede sustituir al otro | **no** | **no** |

`validate_lab_gates` no recibe artefactos as-run; `validate_as_run_gates` no recibe métricas LAB. `validate_adaptation_proposal` compone ambos y solo devuelve `requires_human_approval` si los dos están en verde **y** la cohorte as-run está certificada. En cualquier otro caso: `rejected` con motivos prefijados (`lab:*`, `as_run:*`).

`activationAllowed` sigue siendo `false` en todas las rutas. Como mucho se devuelve `humanApprovalRequired: true` y el motivo `human_approval_required`.

## 8. Cohortes y veredicto

`evaluate_multi_day` agrega artefactos y compara la media de `as_run` contra el **mejor** brazo medido distinto de sí mismo:

- `as_run_beats_arms` — la operativa ejecutada superó a los contrafactuales.
- `arms_beat_as_run` — algún brazo contrafactual habría sido mejor.
- `insufficient_sample` — menos de `DEFAULT_MIN_COHORT_SAMPLES` (12) artefactos medidos. La muestra manda.

Un brazo no medido jamás participa en la comparación ni se imputa con cero. `market_bh` queda fuera de la comparación de R porque no publica R.

## 9. Ejecución

```powershell
# CLI directo (lee PostgreSQL en modo read-only, escribe el artefacto)
.venv\Scripts\python.exe apps/api-python/scripts/v2_102_dia_d_as_run.py `
  --account-id acc --at 2026-09-30 `
  --commission-bps 10 --slippage-bps 5 --spread-bps 2 `
  --max-participation-pct 0.10 --gap-policy open `
  --universe-instrument AAA --universe-instrument BBB `
  --verify-bars

# Por cola durable (job kind dia_d_as_run)
curl -X POST http://localhost:8000/api/auto/dia-d-as-run `
  -H "Content-Type: application/json" `
  -d '{"day":"2026-09-30","accountId":"acc","universeInstruments":["AAA","BBB"],"verifyBars":true}'

# Lectura
curl http://localhost:8000/api/auto/dia-d-as-run
curl http://localhost:8000/api/auto/dia-d-as-run/2026-09-30
```

`--universe-instrument` es la **declaración** del universo de D: sin ella el artefacto se mide igual, pero el universo se deriva de patas y barras y la certificación lo marca `NOT_EVALUATED` (`universe_not_declared`). `--verify-bars` re-verifica el manifest contra las barras leídas y falla el proceso si no coincide.

| Superficie | Pieza |
| --- | --- |
| Job | `JOB_KIND_DIA_D_AS_RUN = "dia_d_as_run"` |
| Worker | `auto_ops_job_worker.py` → `auto_ops_dia_d_as_run.py` |
| HTTP | `POST/GET /api/auto/dia-d-as-run[/{day}]` |
| Shared | `DiaDAsRunArtifactV1`, `DiaDAsRunArtifactV2`, `DiaDAsRunAuditV1`, `DiaDAsRunCertificationV1`, `DIA_D_AS_RUN_ARMS` |
| UI | `/auto-monitor` → pestaña **As-run** (`dia-d-as-run-panel.tsx`) |
| Programación | `DIA_D_AS_RUN_SCHEDULED=0` (**OFF por defecto**) |

## 10. Fail-closed declarado

| Situación | Resultado |
| --- | --- |
| Día sin barras | brazo `measured: false` con `reason`, artefacto con `gaps` |
| Cuenta sin posiciones | `startingState.cashOnly = true`; brazos de posición no medidos |
| Sin candidata | `candidate` no medido, `candidate_not_provided` |
| Candidata construida después de D | `candidate_not_point_in_time`, no se mide |
| Candidata fuera del universo de D | `candidate_outside_universe:<ids>` |
| Universo de D no declarado | artefacto medido igualmente; `initial_state` ⇒ `NOT_EVALUATED` (`universe_not_declared`) |
| Barra que dispara sin liquidez | cierre diferido al `open` siguiente; si no hay, `liquidity_insufficient` |
| `barsManifest` no coincide con la fuente | `--verify-bars` aborta el proceso; no se publica el artefacto |
| Sin datos para certificar | `not_certified` con la condición y el motivo |
| Muestra insuficiente | `insufficient_sample` en la cohorte |
| Subproceso ≠ 0 o artefacto inválido | el handler falla el job; no se guarda un éxito falso |
| Sin período/cuenta | rutas HTTP devuelven motivo explícito, no lista vacía con éxito |

## 11. Por qué esto no promete ganar

La línea base medida es negativa (AUTO V2 2021–2026: −169,7 % neto, −0,204 R/ciclo, hit 41,7 %). El as-run **no cambia el pasado**: lo mide. Sirve para atribuir qué decisión aportó o costó R y para alimentar el bucle APL con evidencia que no puede inventarse. Si la operativa era mala, el as-run lo dice; no la convierte en buena. Y aunque saliera buena, el método solo habilita **pedir** aprobación humana: `activationAllowed` sigue siendo `false`.

## 12. Reproducir la verificación

```powershell
.venv\Scripts\python.exe -m pytest packages/py/application/tests/test_dia_d_as_run_eval.py -q
.venv\Scripts\python.exe -m pytest packages/py/application/tests/test_adaptation_validation.py -q
.venv\Scripts\python.exe -m pytest apps/api-python/tests/test_auto_ops_dia_d_as_run.py -q
.venv\Scripts\python.exe -m pytest apps/api-python/tests/test_auto_dia_d_as_run_route.py -q
.venv\Scripts\python.exe -m pytest apps/api-python/tests/test_ai_adaptation_routes.py -q
cd apps/web; npm test -- dia-d-as-run-panel
```

Criterios: mismo hash con las mismas entradas; ningún `0` donde no hay medida; un artefacto sin certificación no habilita el gate as-run; y `activationAllowed` sigue siendo `false` en todas las rutas.

## 13. Niveles de evidencia

Distinguirlos evita leer «implementado» como «apto»:

1. **Implementado** — motor, DTO, auditoría, certificación y UI. *(Evidencia: este documento y el código.)*
2. **Verificado técnicamente** — tests dirigidos, suite amplia, tipos, lint y contrato. *(Evidencia: §12.)*
3. **Validado históricamente** — reproducciones con datos reales en varios D y escenarios de mercado, con cohorte `certified` y muestra ≥ 12. *(Pendiente: requiere ejecuciones reales.)*
4. **Apto para consideración operativa** — robustez demostrada, rentabilidad neta ajustada al riesgo y aprobación humana. *(No demostrado; `activationAllowed = false`.)*

Este cierre deja los niveles 1 y 2 con evidencia y **no** reclama los niveles 3 y 4. Una certificación acredita que la simulación satisface condiciones metodológicas; no demuestra que la estrategia vaya a ganar.

## 14. Referencias

- [ADR-049 — Adaptación gobernada por IA y DÍA-D retrospectivo as-run](../adr/049-adaptacion-gobernada-por-ia.md)
- [Cierre de auditoría DÍA-D as-run 2026-11-13](./cierre-auditoria-dia-d-as-run-2026-11-13.md)
- [Dictamen externo del cierre DÍA-D as-run `2.11.189-beta`](./dictamen-externo-dia-d-as-run-2026-11-13.md)
- [Operativa secuencial extremo a extremo](./operativa-secuencial-extremo-a-extremo-2026-11-13.md) §E5 y §E7
- [Evidencia de política DÍA-D](./dia-d-evidencia-politica-2026-11-05.md)
- [Línea base y evidencia](./linea-base-y-evidencia-2026-11-08.md)
