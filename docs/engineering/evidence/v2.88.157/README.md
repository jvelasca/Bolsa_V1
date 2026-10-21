# Evidencia `v2.88.157-beta` — integridad del parte ESTUDIO y atribución DÍA-D

> **Naturaleza:** sello **posterior y acotado** a `v2.88.156-beta`.
> **`Δ motor = 0`** con cartera medida · **`Δ decisión = 0`** salvo el caso declarado
> (`position_open=None` ⇒ `no_trade` conservador) · **sin migración**
> (head `057_top3_opportunity_identity`) · contrato HTTP **aditivo/ampliado**
> (`positionOpen` pasa a `bool | null`, ya declarado en `.156`; el resto son campos nuevos en
> `dict[str, Any]`; `openapi.json`/`schema.d.ts` regenerados, `contract:check` **OK**).
>
> **Bump** `2.11.156-beta` → **`2.11.157-beta`** (+ `meta.bump` de los **13** CLIs) y tag
> anotado **`v2.88.157-beta`**. La evidencia publicada de `.153`, `.154`, `.155` y `.156`
> **no se reescribe**. **AUTO sigue OFF** y la ventana PAPER sigue **`INCONCLUSIVE`**: un CI
> verde no certifica rentabilidad.

## 1. Qué publica este sello

Los huecos residuales de `.156` y dos hallazgos mecánicos que quedaron abiertos. Ninguno toca
motor, umbrales, pesos A/B, `TOP_N`, régimen, sizing, entradas/salidas, orquestador ni replay
OOS con cartera medida: se corrigen **la honestidad del parte diario**, **la identidad durable
TOP3 ↔ parte** y **el sellado de atribución del replay DÍA-D real** (detrás de un flag).

| # | Severidad | Hallazgo | Cierre |
| --- | --- | --- | --- |
| **H-156-1 / R-1** | `P2` | El tri-estado de `positionOpen` moría en el borde: el motor recibía `False` cuando la cartera no se midió y podía recomendar comprar un valor ya en cartera. | `position_open: bool | None` de extremo a extremo; `None` ⇒ `no_trade` + `position_unmeasured`; `io_score=None` añade `io_unmeasured` sin cambiar la regla de 3★. |
| **R-3 / H-145-3** | `P2` | Un parte con mediciones ausentes se cerraba como `failed` (o se publicaba `ok` con errores por valor disfrazados). | Estado `partial` + `degraded`/`degradedReasons`/`coverage`; el worker lo completa con `result` y solo falla con `empty`/`unavailable`. |
| **R-2** | `P3` | El nivel 1 mostraba códigos crudos (`positions_unavailable`, `composite_chips_unavailable:12_ids`, …). | Traductor puro código → frase; el crudo solo dentro de `AutoTechnicalDetail`; banner de parte parcial, posición no medida e IO no medido. |
| **Gap 1** | `P2` | No había vínculo durable entre el ganador TOP3 del día y el parte diario; `planId` del parte era el `planId` cosmético del hit, no la identidad del `TradePlan`. | Foto del día + ganador + `isWinner` por valor (`selector`); `strategy.planId = tradePlan.decisionId` y `proposeRunId = scanId`. |
| **DÍA-D real** | `P2` | El replay real no sellaba `signalId`/`planId` en sus (`RoundTrip`/`OpenPosition`). | Atribución por `cycleId` capturada al nacer la posición, detrás de `capture_cycle_attribution` (default `False`; solo `v2_89` lo enciende). |
| **H-145-5** | `P2` | Un job abandonado se podía reclamar para siempre. | `claim_next(max_attempts=5)` + `fail_exhausted` (`max_attempts_exceeded:<n>`), configurable por `AUTO_OPS_JOB_MAX_ATTEMPTS`. |
| **R-4** | `P3` | Un `signalId` en blanco se publicaba como identidad. | `clean_signal = str(payload.get("signalId") or "").strip()`; sin hecho `SIGNAL` cuando solo hay blancos. |

## 2. H-156-1 / R-1 — la cartera no medida no es «sin posición»

[`daily_opinion_stance.py`](../../../../packages/py/application/src/bolsa_application/daily_opinion_stance.py)
declara `StanceInput.position_open: bool | None` y, tras las compuertas EOD/`allow_trading`:

```python
if inp.position_open is None:
    return StanceResult("no_trade", 1, reasons + ["position_unmeasured"], "WARNING")
```

El `fa_distress` solo reduce/vende con `position_open is True`; con `None` ya se ha fallado
cerrado antes. `io_score=None` añade `io_unmeasured` (la regla de estrellas no cambia; el
`3★` deja de leerse como medición).

[`daily_opinion_service.py`](../../../../packages/py/application/src/bolsa_application/daily_opinion_service.py)
conserva `OpinionHint.position_open: bool | None = None` y lo pasa **sin** `bool(...)`; los
guards de `sell_exit`/`reduce` y `fa_distress` usan `is False` / `is not True`.

[`estudio_daily_ops.py`](../../../../packages/py/application/src/bolsa_application/estudio_daily_ops.py)
(`_build_hints`) nace con `positions_measured = self._positions is not None`: un adaptador
**ausente** ya no es «cartera vacía». Si falta o la lectura cae, el mapa queda `None` por valor
y se declara `positions_unavailable`. El contrato HTTP
([`instrument_daily_opinions.py`](../../../../apps/api-python/src/bolsa_api/schemas/instrument_daily_opinions.py))
publica `position_open: bool | None`.

## 3. R-3 / H-145-3 — `partial` es un resultado, no un fallo

`ESTUDIO_STATUS_PARTIAL = "partial"` y `EstudioDailyReport` gana `degraded`,
`degraded_reasons` y `coverage` (posiciones medidas, chips caídos, errores de opinión). Motivos:

```text
positions_unavailable
composite_chips_unavailable:<n>_ids
fundamentals_chips_unavailable:<n>_ids
opinion_errors:<n>_values
propose_unavailable
selector_identity_unavailable
```

`universe_truncated` marca `degraded` pero **no** fuerza `partial` (es cobertura, no fallo de
medición). Todos los valores en `error` ⇒ `unavailable`; el resto con motivos ⇒ `partial`.

[`auto_ops_job_worker.py`](../../../../apps/api-python/src/bolsa_api/background/auto_ops_job_worker.py)
solo lanza `AutoOpsJobFailed` con `status not in ("ok", "partial")`; en `partial` registra el
warning con los motivos y **completa** el job con su `result`.

## 4. R-2 — nivel 1 en español; el crudo, en el detalle técnico

Nuevo [`estudio-daily-notes.ts`](../../../../apps/web/src/features/auto-monitor/estudio-daily-notes.ts):
`describeEstudioDailyNote`/`describeEstudioDailyNotes` son puras y totales (un código
desconocido se declara como hueco, no se silencia). Ejemplos:

- `positions_unavailable` → «No se pudo leer tu cartera: el dictamen no sabe si ya tienes este valor.»
- `composite_chips_unavailable:<n>_ids` → «No se pudieron leer los indicadores del motor en N valores…».
- `propose no disponible: …` → «La propuesta de planes no estuvo disponible…».
- `allowTrading=true …` → «El parte es informativo: la ejecución real se decide en el camino de ejecución.»

[`estudio-daily-ops-panel.tsx`](../../../../apps/web/src/features/auto-monitor/estudio-daily-ops-panel.tsx)
pinta solo el `headline` en nivel 1 y mueve el crudo a `AutoTechnicalDetail`. Añade:

- banner `data-testid="estudio-daily-partial"` con `degradedReasons` cuando `status === "partial"`;
  el parte se renderiza también en `partial` (el bloque de universo queda para `empty`/`unavailable`);
- por valor, `positionOpen` → «Con posición abierta» / «Sin posición abierta» / «Cartera sin medida»
  (`data-testid="estudio-daily-value-position"`), con explicación de que no se recomienda operar
  cuando no se midió;
- `indicators.io === null` ⇒ «IO sin medida», sin presentar el `3★` implícito como medición.

## 5. Gap 1 — identidad durable TOP3 ↔ parte diario

[`auto_chain_durable_reader.py`](../../../../packages/py/application/src/bolsa_application/auto_chain_durable_reader.py)
añade dos funciones **puras** (`snapshot_for_day`, `selector_winner`) y `raise_on_error` a
`read_top3_snapshots` para distinguir «sin fotos» de «lectura caída».

[`estudio_daily_ops.py`](../../../../packages/py/application/src/bolsa_application/estudio_daily_ops.py)
expone un puerto `selector` (cableado en el worker con `Top3SnapshotsSelector(session)`, la misma
fuente que la evidencia de cadena) y publica por valor:

```jsonc
"selector": {
  "measured": true,
  "runId": "top3-acc-…",
  "bar": "2026-10-18T09:00:00Z",
  "assetId": "inst-1",
  "presetKey": "estudio_auto",
  "strategyVersion": "1",
  "isWinner": true,
  "reason": null
}
```

Sin foto del día ⇒ `measured=false`/`reason="no_snapshot_for_day"`; sin adaptador ⇒
`selector_not_configured` (no degrada); lectura caída ⇒ `selector_identity_unavailable` (sí
degrada). Sin `rank == 1`, `isWinner=None` (no se puede afirmar que el valor **no** sea el
ganador).

La identidad del plan deja de confundirse: `strategy.planId = tradePlan.decisionId` y
`strategy.proposeRunId = hit.scanId`; `signalId` sigue saliendo de `signal.id`.

La UI sustituye «Indicador ganador: no declarado por el motor» por una frase humana
(«Ganador del selector: …», «Este valor no es el ganador», «Sin foto del selector para este día»)
y deja `runId`/`assetId` crudos en el detalle técnico.

## 6. DÍA-D real — atribución sellada sin tocar el congelado

[`replay_oos.py`](../../../../packages/py/application/src/bolsa_application/replay_oos.py):

- `score_replay(..., attribution_by_cycle=None)`.
- `RoundTrip` gana `signal_id`/`plan_id`; `OpenPosition` gana `cycle_id`/`signal_id`/`plan_id`.
- `to_dict(include_attribution=False)` **no añade claves** (artefacto de `replay-repro`
  byte a byte); con `True` publica `signalId`/`planId` (`cycleId` solo en posiciones vivas).

[`v2_87_replay_oos_durable_cycle.py`](../../../../apps/api-python/scripts/v2_87_replay_oos_durable_cycle.py)
captura, solo con `capture_cycle_attribution=True`, `cycleId → {signalId: worker._v2_tick_signals[symbol], planId: position.decision_id}`
al **nacer** la posición (antes de `close_tick`, para no perder las que mueren en el mismo tick).
El default sigue `False`, por lo que el replay congelado no cambia. `v2_89` lo enciende y
`_oos_for_day` copia las filas al artefacto DÍA-D.

## 7. H-145-5 — tope de intentos

[`auto_ops_job_repository.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/auto_ops_job_repository.py):
`claim_next(max_attempts=5)` filtra `attempt < max_attempts` y `fail_exhausted` cierra los
`queued`/`running` abandonados con `attempt >= max_attempts` (`error="max_attempts_exceeded:<n>"`).
Un `running` con latido vivo **no se toca**. [`config.py`](../../../../packages/py/infrastructure/src/bolsa_infrastructure/config.py)
expone `AUTO_OPS_JOB_MAX_ATTEMPTS` (default 5) y el worker lo pasa. El test PG
(`test_auto_ops_job_attempt_cap_pg.py`) está cableado al paso dedicado de `lifecycle-pg` con
`AUTO_OPS_JOB_ATTEMPT_CAP_PG_REQUIRED=1` y el guard anti-skip del job; además queda en el
`--ignore` de los jobs sin PostgreSQL para que no skipee en mudo.

## 8. R-4 — `signalId` en blanco no es identidad

[`auto_operational_monitor.py`](../../../../packages/py/application/src/bolsa_application/auto_operational_monitor.py)
calcula `clean_signal = str(payload.get("signalId") or "").strip()`; el hecho `SIGNAL` solo se
añade con identidad real y el DTO del ciclo publica `None` cuando solo hay blancos.

## 9. Verificación medida

| Comprobación | Resultado |
| --- | --- |
| `pytest` focalizado (stance, parte, lector, monitor, replay, feedback, worker) | **185 passed** |
| `pytest packages/py/application/tests` | **2839 passed in 176.12s** |
| `pytest apps/api-python/tests --ignore=tests/chaos` | **1296 passed** |
| `pytest test_auto_ops_job_attempt_cap_pg.py test_auto_identity_chain_battery_pg.py` (PG real) | **4 passed in 3.81s** |
| `pytest test_dia_d_bump_guard.py` | **2 passed** |
| `pnpm --filter @bolsa/web test -- estudio-daily` | **38 passed** (2 ficheros) |
| `pnpm --filter @bolsa/shared test` | **98 ficheros / 832 passed** (+1 todo) |
| `pnpm typecheck` | **4/4 OK** |
| `pnpm lint` | **0 errores** (23 avisos preexistentes) |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run mypy packages/py/application/src apps/api-python/src` | **no issues / 407 ficheros** |
| `pnpm --filter @bolsa/web contract:gen` + `pnpm contract:check` | **OK** (`openapi.json` + `schema.d.ts` en sync) |
| `pnpm window:freeze` | **`freeze OK`** |
| `pnpm window:test` | **50 passed** |

Pruebas nuevas / ampliadas:

- `test_daily_opinion_stance.py`: `position_open=None` ⇒ `no_trade` + `position_unmeasured`
  (nunca `buy`); `io=None` declara `io_unmeasured`.
- `test_estudio_daily_ops.py`: adaptador de posiciones ausente ⇒ `partial` +
  `positions_unavailable`; chips caídos ⇒ `partial` con contadores; todos los valores en
  `error` ⇒ `unavailable`; `coverage`; `selector` ganador/no ganador/sin foto/lectura caída;
  `planId` ≠ `proposeRunId`.
- `test_auto_ops_job_worker.py`: `partial` completa con `result`; `empty`/`unavailable` fallan.
- `test_auto_ops_job_attempt_cap_pg.py` (PostgreSQL real): N reclamos ⇒ el intento N+1 deja el
  job `failed` con `max_attempts_exceeded`; un `running` con latido vivo no se toca.
- `test_auto_chain_durable_reader.py`: `snapshot_for_day`, `selector_winner`, `raise_on_error`.
- `test_auto_operational_monitor.py`: `signalId` en blanco ⇒ `None` y sin hecho `SIGNAL`;
  con espacios alrededor se publica limpio.
- `test_replay_oos.py`: la atribución se sella solo con `include_attribution=True`; sin
  atribución consta `None` (nunca se re-deriva por símbolo); el `to_dict` congelado no gana claves.
- `estudio-daily-notes.test.ts` + `estudio-daily-ops-panel.test.tsx`: nota cruda invisible en
  nivel 1 y visible en `AutoTechnicalDetail`; banner `partial`; posición desconocida; ganador
  del selector; `planId`/`proposeRunId` distintos.

**Delta declarado.** Con cartera medida, el motor recibe exactamente el mismo booleano que
antes (`Δ decisión = 0`). Con cartera **no medida**, el dictamen pasa de poder recomendar
`buy`/`hold_watch` a `no_trade` con `position_unmeasured`: es el cambio **buscado** por
H-156-1/R-1, no una regresión.

## 10. Límites declarados (sin fabricar)

- **AUTO sigue OFF.** No se enciende la cadencia.
- La ventana PAPER sigue **`INCONCLUSIVE`** y **`CONFIRMED` no se emite**.
- Operativa **100 % SIM**; el bridge LIVE no se abre. **Rentabilidad no certificada.**
- El parte declara lo que midió: `partial` no es «todo bien», y `coverage` no se interpreta como
  rentabilidad.
- El ganador TOP3 es una **capa de identidad**: si el valor no es el ganador se declara, pero
  **no** se cambia la propuesta ni se fuerza que el ganador sea el plan del parte.
- El replay DÍA-D real solo sella desde ahora: los artefactos históricos ya emitidos sin
  `signalId`/`planId` **no se backfillean** y siguen sin atribución.
- La suite `apps/api-python/tests/chaos` es **live-A7** y exige acceso exclusivo a una BD con
  workers vivos; con el stack dev corriendo, `test_c3a` puede expirar por consumidores reales
  del outbox. No forma parte de la verificación offline de este sello.
- Tag **anotado, unsigned**.

## 11. Freeze

El bump mueve `apps` (los `meta.bump` de los **13** CLIs) y `packages` (dictamen, parte diario,
lector durable, monitor, replay OOS y `@bolsa/shared`) ⇒ el pin PAPER se **re-ancla** al árbol
del sello para que el run de las 18:00 no aborte con `TREE_MOVED`; `pnpm window:freeze` ⇒
**`freeze OK`** y `pnpm window:test` **50 passed**.

## 12. Publicación

Se publica como `v2.88.157-beta` (anotado, unsigned) sobre el commit de **re-anclaje del pin**,
inmediatamente posterior al commit del sello, igual que en `.154`/`.155`/`.156`: el gate
`window:freeze` del job `shared` es **fail-closed** y el tag no puede apuntar a un commit cuyo
pin no case con su árbol. El `Release tag CI` debe quedar **verde** (`certify`, `lifecycle-pg`,
`replay-repro`, `web`, `python`) antes de publicar el Release; en particular `replay-repro`
debe seguir **`REPRODUCIDO`** byte a byte porque la atribución nueva está apagada por defecto.
