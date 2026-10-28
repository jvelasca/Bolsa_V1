# Evidencia `v2.88.168-beta` — el monitor publica el motivo del HOLD y la UI distingue «no evaluable» de «sin señal»

## 1. Qué publica este sello

Tercer y **último** sello del bloque funcional posterior a `v2.88.165-beta`. Cierra **B-5** y **O-6**
de la auditoría de detección.

El journal ya sellaba `auto_active_strategy_hold` con motivo y procedencia desde `.164`, pero **nada
de eso llegaba al monitor**: la UI veía `action: "HOLD"` y pintaba igual un HOLD porque *el motor no
llegó a evaluar* y un HOLD porque *evaluó y no había señal*. El operador no podía saber si el
silencio era una decisión o un hueco.

- **`Δ motor = 0`**: no cambia ninguna regla, indicador ni umbral de señal.
- **`Δ decisión = 0`**: se publica lo que ya se decidía; no se decide distinto.
- **Contrato HTTP ADITIVO**: `signalHolds` en `AutoOperationalMonitorDto` (y `AutoMonitorSignalHoldDto`),
  con `openapi.json`/`schema.d.ts` regenerados y `contract:check` verde.
- **SIN migración nueva**: `head` sigue `058_estudio_daily_proposals`.
- **Bump** `2.11.167-beta` → `2.11.168-beta` (+ `meta.bump` de los **13** CLIs;
  `test_dia_d_bump_guard`).

## 2. Los cuatro frentes

| Frente | Qué estaba mal | Qué se publicó | Prueba |
| --- | --- | --- | --- |
| **B-5 · el HOLD llega al monitor** | El motivo y la procedencia vivían sólo en el journal | `_signal_holds` proyecta los `auto_active_strategy_hold` del **mismo** journal a `signalHolds[]`; `reason` sale de `payload.reasonCodes[0]` **sin reinterpretarlo** | `test_the_hold_declaration_reaches_the_dto_with_its_reason` |
| **B-5 · nada se rellena** | Un `false`/`0` de relleno convertiría «no pude medir» en «medí cero» | La procedencia (`holdDetail`, `featureSource`, `signalWindowBars`, `warmupBars`, `signalWindowSource`, `gatedState`, `strategyVersion`, `strategyPresetKey`) se eleva **sólo si existe**, como hecho con su `measurement` | `test_the_hold_projection_omits_the_fields_the_producer_did_not_declare` · `test_the_hold_projection_carries_the_gated_state_and_the_window` · `test_without_hold_declarations_the_list_is_empty_not_invented` |
| **B-5 · el filtro no mezcla símbolos** | Un read-model filtrado que devuelve HOLD de otro símbolo miente | `instrument_id` se aplica igual que al resto del read-model; el orden es el del journal | `test_the_hold_projection_filters_by_instrument` |
| **O-6 · el paso SIGNAL declara con qué se llegó** | «SIGNAL reached» no decía con qué dato | `featureSource`, `signalWindowBars`, `warmupBars`, `signalWindowSource`, `gatedState` **anidado** (ADR-048: el cliente no deriva el libro), `holdReason`/`holdDetail`; aditivos y omitidos sin dato | `test_the_signal_step_publishes_the_provenance_of_the_decision` · `test_the_signal_step_omits_the_provenance_when_the_producer_did_not_declare_it` |

## 3. La clasificación (UI) es del vocabulario, no de la prosa

`apps/web/src/lib/decision-silence.ts` clasifica HOLD por el **literal exacto** del vocabulario
cerrado `ACTIVE_HOLD_REASONS`:

| Causa | Literales | Lectura |
| --- | --- | --- |
| `not_evaluable` | `warmup_unmeasurable`, `no_snapshot`, `evaluation_failed`, `gated_unavailable`, `warmup_insufficient` (prefijo estable de `@bolsa/shared`) | el motor **no pudo decidir**: es un hueco a resolver |
| `no_signal` | `no_signal` | evaluó y no había señal: es un hecho del mercado |
| `disabled` | `active_signal_disabled` | señal apagada por configuración |
| `not_executable` | `no_executable` | sin definición ejecutable |
| `unmeasured` | ausente, vacío o fuera del vocabulario | no consta el motivo; **no** se presenta como causa conocida |

Reglas que la prueba fija (`decision-silence.test.ts`, **14 passed**):

- un prefijo a mitad de frase **no** clasifica (`"warmup"` ⇒ `unmeasured`; `"warmup_insufficient"` ⇒
  `not_evaluable`);
- sin motivo **no** se puede afirmar «sin señal»;
- el titular **nunca** dice «sin señal» si no se evaluó nada: sin declaraciones dice «Sin HOLD
  declarados en la ventana», y si todo lo declarado es no evaluable dice «Ningún HOLD con señal
  evaluada» con el desglose;
- `notEvaluableHolds` lista no evaluables **y** no medidos, sin arrastrar decisiones.

## 4. El delta medido (no supuesto)

Con dos declaraciones —`AAA` con `warmup_unmeasurable` y `BBB` con `no_signal`— el panel real montado
con la API mockeada pinta:

- titular «1 sin señal · 1 HOLD no evaluable»;
- dos filas con `data-cause` `not_evaluable` y `no_signal`;
- el motivo concreto del hueco («warmup no medible»), no prosa genérica;
- aviso «1 de 2 no se pudieron evaluar: AAA (warmup no medible)», **sin** mencionar `BBB`.

Ese es exactamente el hueco que cierra el sello: antes las dos filas se leían «HOLD». Prueba:
`test("separa «no evaluable» de «sin señal» en los HOLD declarados (.168)")`. El control negativo
—sin declaraciones— declara que **no consta el motivo** en vez de afirmar «sin señal».

## 5. Ficheros

| Capa | Ficheros |
| --- | --- |
| Python · aplicación | `auto_operational_monitor.py` (`_signal_holds`, `_HOLD_PAYLOAD_KEYS`, `AUTO_ACTIVE_STRATEGY_HOLD_EVENT`, procedencia del paso SIGNAL) |
| Python · API | `routes/auto_operational_monitor.py` (`AutoMonitorSignalHoldDto`, `signalHolds`) |
| Contrato | `apps/web/api/openapi.json`, `apps/web/src/api/schema.d.ts` |
| TS · shared | `packages/shared/src/cognitive/auto-operational-monitor.ts` (`AutoMonitorSignalHoldV1`) |
| Web · lógica | `apps/web/src/lib/decision-silence.ts` (+ `.test.ts`) |
| Web · UI | `apps/web/src/features/auto-monitor/auto-operation-story-panel.tsx` (+ `.test.tsx`) |
| Python · pruebas | `packages/py/application/tests/test_auto_operational_monitor.py` |
| Docs | `CHANGELOG.md` (§`2.11.168-beta`), `docs/engineering/PROJECT_STATE.md`, este pack |

## 6. Verificación medida (local, sobre este árbol)

| Comprobación | Resultado |
| --- | --- |
| `pytest` `application` (hermético, `*_db.py` excluidos: su fixture conecta a PostgreSQL real) | **2968 passed** (3:09) |
| `pytest` `analytics` + `domain` + `market` | **1616 passed** (0:32) |
| `pytest` `api-python` (filtro `monitor or auto`) | **801 passed, 623 deselected** (3:40) |
| `pnpm --filter @bolsa/web test` | **2399 passed / 320 ficheros** |
| `pnpm --filter @bolsa/shared test` | **855 passed / 99 ficheros** (1 todo) |
| `test_auto_operational_monitor` | **79 passed** (7 nuevos) |
| `decision-silence` | **14 passed** |
| `auto-operation-story-panel` | **31 passed** (2 nuevos) |
| `contract:check` | **OK** — `openapi.json` y `schema.d.ts` coinciden |
| `typecheck` | **4/4 tareas** |
| `lint` | **0 errores** (23 avisos preexistentes) |
| `ruff` (CI: `packages/py apps/api-python --config pyproject.toml`) | limpio |
| `mypy` (alcance CI) | **573 ficheros, sin issues** |
| `test_dia_d_bump_guard` | **2 passed** |
| Migración | **sin delta** (`head` `058_estudio_daily_proposals`) |

## 7. Límites declarados

- **AUTO sigue OFF**; operativa **100 % PAPER virtual**, sin LIVE ni XTB real.
- La ventana PAPER sigue **`INCONCLUSIVE`** (`episodios 0/2`, `ciclos 0/32`): este sello **no la mueve**
  y **no demuestra rentabilidad**.
- Publicar el motivo **no** demuestra que el motivo sea correcto: eso lo fija la prueba del
  productor, no la UI.
- `signalHolds` vacío **no** prueba que no hubiera HOLD: prueba que no consta la declaración, y así
  se rotula.
- El HOLD **no** se asigna a ningún ciclo «parecido» por símbolo o fecha: es un hecho de la **señal**,
  no de una operación.
- El sello publica y clasifica; **no** cambia ninguna decisión de operar ni de no operar.
