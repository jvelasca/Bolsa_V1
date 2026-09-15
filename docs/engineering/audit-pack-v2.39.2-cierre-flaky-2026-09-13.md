# Audit Pack — V2.39.2 · Cierre de flaky y orden real del ledger

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.39.2** — cierre de los `flaky` residuales detectados en la **auditoría interna
> previa a la externa** sobre `v2.39.1`.
>
> **Base auditada:** `v2.39-beta` (`e94f2632`).
> **Commit de código:** `9444b364` (certificado GREEN por Release-tag CI).
> **Tag:** `v2.39.2-beta` — sella `main` incluyendo la documentación de auditoría
> (código idéntico a `9444b364`). Package **`1.64.2-beta`**.
> **Alembic head:** `039_research_trials_regime` (esta fase **no** añade migración).
> **Bump:** `1.64.1-beta` → `1.64.2-beta`.
> **Flags:** sin cambios (`AUTO_ORCHESTRATOR_ADAPTIVE_REGIME` sigue **OFF** por defecto).
>
> **Nota de alcance.** Este documento empezó cubriendo el **cierre de flaky** (secciones 1–5,
> commits `b1d382c8`…`cc50ae36`). La **tercera pasada** de la auditoría interna —hecha justo
> antes de publicar el tag— añadió tres hallazgos más (secciones 6–9, commits `f0e21d95`,
> `f536776d`, `9444b364`). Los dos bloques se auditan **juntos**: el tag apunta al último.

---

## 0. Resumen ejecutivo

La auditoría interna de `v2.39.1` dejó **4 tests PG no deterministas**. Al atacarlos con
instrumentación forense (volcado del entrelazado de `executed_at` cuando la cadena
`balance_after` rompía), el "flaky" resultó ser **un bug real de producción** que la primera
pasada no alcanzó a cerrar, más **una configuración de test que enmascaraba el veredicto**.

Al correr después la **batería exacta del CI** (secciones 6–9) aparecieron dos fallos que
**no** eran flaky y un tercer agujero de certificación: una **lista con instrumentos
imborrable** (500 por FK), una **gramática de Discovery que emitía planes sin evidencia
posible** (el `PBO CSCV` quedaba sin matriz en silencio) y un **gate de CI que toleraba
skips**.

| Hallazgo                                                                             | Naturaleza            | Impacto                                                          |
| ------------------------------------------------------------------------------------ | --------------------- | ---------------------------------------------------------------- |
| **P1** — El `executed_at` del ledger se derivaba del **reloj de pared**              | Bug de producción     | Ledger **no reproducible** bajo concurrencia                     |
| **P1** — `ApplyCustodyFees` calculaba `balance_after` con cash **PRE-lock**          | Bug de producción     | `balance_after` desalineado de su `amount`                       |
| **P1** — La gramática de Discovery emitía planes **inoperables** (tres causas)       | Bug de producción     | Gates `robustness`/`walk_forward` **sin evidencia**, en silencio |
| **P1** — Una lista **con instrumentos** no se podía borrar                           | Bug de producción     | `DELETE /api/lists/{id}` → **500** en vez de 204                 |
| **P2** — `pool_size=64` agotaba `max_connections` del PG local                       | Config de test        | Fallos **en ráfaga** que enmascaraban el veredicto               |
| **P2** — `test_two_workers_claim_disjoint_unknown_batch` no certificaba lo que decía | Test deshonesto       | Afirmaba exclusión mutua con un escenario que la **refutaba**    |
| **P2** — `lifecycle_outbox` **envenenaba suites** entre sí                           | Hermeticidad          | `claim_batch` global reclamaba filas ajenas                      |
| **P3** — El bucle antirrecompra del A9 agotaba el presupuesto **siempre**            | Test ineficiente      | ~518 s por pasada                                                |
| **P3** — El job de CI de A14 **toleraba skips silenciosos**                          | Gate de certificación | Certificación **fantasma** posible                               |

**Veredicto:** el ledger es **secuenciado por estado** (no por reloj), la gramática emite
**1684 planes con 0 degenerados**, los chaos son deterministas, el A9 pasó de ~518 s a ~28 s y
la tabla `lifecycle_outbox` ya no contamina suites.

---

## 1. P1 — El `executed_at` del ledger se derivaba del reloj de pared

**Diagnóstico (con evidencia).** La primera pasada (`v2.39.1`) hizo que **trade y fee**
compartieran el instante de la **transacción**, pero ese instante se sigue tomando con
`datetime.now(UTC)`. Bajo concurrencia eso **no ordena**:

```
Tx A: lee el reloj → T_A        Tx B: lee el reloj → T_B
Tx A: toma el lock de cartera   Tx B: espera el lock
Tx A: aplica (commitea)         Tx B: aplica
```

Si `T_B < T_A` (el reloj de B se leyó antes, pero aplicó después), el consumidor que ordena
por `(executed_at, id)` coloca a B **delante** de A, aunque el `balance_after` de B sea el
**posterior**. El desempate por `id` **no rescata el orden**: es un UUID v4 **aleatorio**.

**Prueba forense.** Se capturó el entrelazado real en el momento del fallo: el salto entre
dos asientos consecutivos **no coincidía con su `amount`**, evidencia directa de que el
asiento se había aplicado en otra posición del orden reconstruido:

```
[459] buy         exec=08:01:13.078141  amt=-1.000000   bal=4979460.954328
[460] fee         exec=08:01:13.078142  amt=-1.212000   bal=4979459.742328
[461] custody-2026 exec=08:01:12.653179 amt=-9999.397  bal=4979477.438328  ← ¡exec ANTERIOR!
[462] buy         exec=08:01:13.095123  amt=-1.000000   bal=4979458.742328
```

La custodia `[461]` tiene un `executed_at` **anterior** a `[459]`/`[460]` pero un
`balance_after` que ya incorpora sus efectos: el orden por reloj es **falso**.

**Fix — secuenciador por cuenta.** Nuevo
`SqlAlchemyLedgerRepository.next_executed_at(account_id)`:

```python
async def next_executed_at(self, account_id: str) -> datetime:
    last = último executed_at de la cuenta (misma transacción del llamador)
    now = datetime.now(UTC)
    return max(now, last + 1µs)
```

Se invoca **con el lock de la cartera ya tomado**, así que la lectura del último instante y
la escritura del asiento son **atómicas** frente al resto de escritores. El instante se
deriva del **estado persistido**, no del reloj ⇒ **estrictamente creciente con el orden de
aplicación**. El paso de 1 µs vuelve irrelevante el desempate por `id`.

Conectado en las **cuatro rutas** que escriben asientos:

| Ruta                          | Fichero               | Punto de invocación                |
| ----------------------------- | --------------------- | ---------------------------------- |
| Trade (`ExecuteTrade`)        | `accounts/trade.py`   | tras `execute_trade` (lock tomado) |
| Custodia (`ApplyCustodyFees`) | `accounts/custody.py` | tras `deduct_cash` (lock tomado)   |
| Depósito                      | `accounts/cash.py`    | tras `add_cash` (lock tomado)      |
| Retiro                        | `accounts/cash.py`    | tras `deduct_cash` (lock tomado)   |

**Regresión:** `test_trade_usa_el_secuenciador_del_ledger_no_el_reloj`,
`test_secuenciador_es_estrictamente_creciente` — **verificadas por mutación** (revertir el
fix a `_parse_executed_at(result.transaction.executed_at)` hace fallar el test).

---

## 2. P1 — `ApplyCustodyFees` calculaba `balance_after` con el cash PRE-lock

**Diagnóstico.** Mismo patrón que `ExecuteTrade` ya había corregido (EXEC-B-CONC) y que la
custodia **nunca recibió**: leía `get_summary().portfolio.cash` **antes** de `deduct_cash`
—que es quien toma el `with_for_update`— y escribía ese balance desfasado. Si un trade
commiteaba entre la lectura y el lock, el `balance_after` de la custodia **no correspondía**
al cash real aplicado.

**Fix.** El `balance_after` se toma del cash **POST-lock** que `deduct_cash` **ya devolvía**,
en las dos ramas (liquidación de PENDING y periodo actual).

---

## 3. P2 — `pool_size=64` agotaba las conexiones del PostgreSQL local

**Diagnóstico.** El escenario de estrés abría **64 conexiones por test**. Con
`max_connections=100` y la convivencia con otros engines (otras suites, `scheduler_worker`,
API) el servidor respondía:

```
FATAL:  sorry, too many clients already
```

Los tests fallaban **en ráfaga** con un error de **entorno** que **enmascaraba el veredicto
real** del test (se leía como "flaky de concurrencia" cuando era agotamiento del servidor).

**Fix.** `pool_size=24`. El escenario serializa igualmente sobre la fila de cartera
(`with_for_update`), así que un pool grande **no aceleraba** el test y sí monopolizaba el
servidor. Además, el sondeo de conexiones confirmó que **no hay fuga persistente** (18
conexiones antes y después de la suite).

**Resultado:** **0/10 fallos** y **~38 s** por pasada (antes ~45 s **con** fallos
intermitentes).

---

## 4. P2 — `test_two_workers_claim_disjoint_unknown_batch` no certificaba lo que decía

**Diagnóstico.** El test hacía `asyncio.gather` de dos `claim_unknown_batch` con **rollback
inmediato** de cada uno y exigía que los resultados fueran **disjuntos**. Eso **no
certifica** la exclusión mutua: la **refuta**. El contrato de producción
(`FOR UPDATE SKIP LOCKED` + lease) excluye **mientras el lock está vivo**; con rollback
inmediato el segundo `SELECT` puede ejecutarse **después** de que el primero libere y ver
las filas — el resultado dependía del **entrelazado del event loop** (verde/rojo aleatorio).

**Fix.** El test ahora certifica la propiedad **real y determinista**: retiene las **dos**
transacciones abiertas, afirma que el segundo worker obtiene **vacío** (todas lockeadas) y,
tras liberar el primero, comprueba el **relevo** cubriendo el lote completo.

---

## 5. P3 — El bucle antirrecompra del A9 agotaba el presupuesto siempre

**Diagnóstico.** Tras el crash+restart, el test esperaba «a que ocurra una re-compra» para
fallar; pero el camino **correcto** es que **nunca** ocurra, así que el bucle agotaba el
plazo completo en **cada** pasada (≈ **518 s**, y fallos intermitentes por agotamiento).

**Fix.** Ese sondeo usa un plazo **corto y acotado** (`_RESTART_WATCH_S = 20 s`) —una
re-compra aparecería en los primeros ticks— y los tres bucles comprueban `proc.poll()` para
**fallar al instante con el log del subproceso** si el worker muere.

**Resultado:** ~518 s → **~28 s**; **8/8** pasadas en verde.

---

## 6. P1 — La gramática de Discovery emitía planes inoperables (tres causas)

**Diagnóstico.** La certificación A14 (`test_a14_grammar_discovery_pg`) fallaba en la batería
del CI con _«ningún plan gramatical produjo evidencia CPCV/PBO real»_. La investigación midió
el grid completo:

> **1784 planes → 1184 con 1 sola columna operable y 600 con 0. Ninguno alcanzaba 2.**

El `PBO CSCV` exige `len(candidates) >= 2`; con menos, `build_lab_pbo_summary` devuelve `None`
y los gates `robustness`/`walk_forward` quedan **sin evidencia** sobre candidatas gramaticales,
**en silencio**. El orquestador real recorre la **misma** ruta, así que el defecto era de
**producción**, no del test.

### Causa 6.1 — El trigger y el trend filter Donchian eran matemáticamente inalcanzables

El canal `dc:upper` es `max(high)` de la ventana **incluyendo la barra actual**, luego
`close > upper` es **imposible**: el máximo de la ventana es siempre `≥ high[i] ≥ close[i]`.
**Medido: 0 disparos incluso en una serie estrictamente creciente.**

**Fix.** Trigger y trend filter usan la banda **media** (`dc:mid`), como el preset
`donchian_breakout` de producción (que sí opera: 381/400 barras con `close > mid`).

### Causa 6.2 — El eje de permutación rompía el par trigger/exit homónimo

Al rotar el eje sobre el trigger (lo introdujo el `P2-01` de la fase anterior), el
`exit_ema10_cross_ema50` (bajista) seguía mirando **las mismas EMAs** que el trigger nuevo. Un
cruce alcista y otro bajista de las mismas series **no coinciden nunca** ⇒ trigger
inalcanzable.

**Fix.** El exit homónimo se permuta **con** el trigger, por par (`_AXIAL_TRIGGER_EXIT_PAIRS`),
y el eje rota **preferentemente** sobre los bloques opcionales (regime/trend/momentum), cayendo
en los axiales solo si el plan no tiene ninguno. Se conserva la rotación que arreglaba el
`P2-01`.

### Causa 6.3 — Incompatibilidad estructural entre bloques, no vetada

`trigger_ema10_cross_ema50` + `trend_ema20_gt_ema50`: el cruce de EMA10 sobre EMA50 es
**necesariamente anterior** a que EMA20 confirme por encima de EMA50, y los gates del plan se
exigen **simultáneamente**. **Medido: 210 barras cumplen ambas condiciones, 0 cruces.**

**Fix.** Dos vetos de inanición deterministas y fail-closed
(`_mutually_unreachable_trigger_exit`, `_conjunctive_ema_starvation`) sacan esas combinaciones
de la enumeración en vez de emitirlas sin evidencia posible.

**Resultado:** **1684 planes, 0 degenerados.** La serie de integración del test también se
reescribió (sembraba una rampa donde `close > sma200` eran **0 barras**): ahora son ciclos con
tramo alcista **más largo que el período del canal** y retrocesos que cruzan las EMAs. El test
pasa de **fallar a los 146 s** a pasar en **5,8 s**.

**Regresión:** `test_grammar_variants_produce_at_least_two_operable_columns` (exige ≥2 columnas
operables por plan) y `test_grammar_donchian_trigger_is_reachable`.

---

## 7. P1 — Una lista con instrumentos no se podía borrar

**Diagnóstico.** `SqlAlchemyListRepository.delete` borraba la fila de `instrument_lists`
**sin vaciar antes** `instrument_list_items`. La FK `list_id` **no** es `ON DELETE CASCADE`:

```
sqlalchemy.exc.IntegrityError: (psycopg.errors.ForeignKeyViolation)
update or delete on table "instrument_lists" violates foreign key constraint
"instrument_list_items_list_id_fkey" on table "instrument_list_items"
DETAIL:  Key (id)=(3dd4578c8afc410fa27494fc2) is still referenced from table "instrument_list_items".
```

⇒ Cualquier lista **con** instrumentos violaba la integridad referencial y
`DELETE /api/lists/{id}` devolvía **500 en vez de 204**.

**Fix.** Los items se borran en la **misma transacción** (sesión) justo antes que la lista.
**Regresión:** `test_delete_list_with_items_does_not_violate_fk`.

---

## 8. P2 — La tabla `lifecycle_outbox` envenenaba suites entre sí

**Diagnóstico.** `claim_batch` es una barrida **global** (FIFO por posición, **sin filtrar por
posición**) con sanitizado de huérfanas. `test_financial_integrity_pg` dejaba una cabeza FIFO
`dead` sin limpieza y otras suites filas `pending`/`processing`, de modo que el worker de
`test_lifecycle_outbox_worker_pg` reclamaba filas **ajenas** y el hook inyectado
(`on_before_apply_commit`) consumía su **único** disparo antes de que la fila propia pasara a
`processing`:

```
AssertionError: outbox lox-... status='applied' expected='processing'
```

El test pasaba **en aislado** y fallaba **en la batería**: la firma clásica de un test **no
hermético** que depende de filas residuales de otras suites.

**Fix.** El test de integridad limpia su fila en `finally`; el fichero del worker aísla la
tabla (purga `pending`/`processing` antes y después de cada test, dejando intactas las
`applied`/`dead`, que son historia legítima y no se re-reclaman).

**Verificado:** `apps/api-python/tests` + `packages/py/infrastructure/tests` pasan **521 en
dos pasadas consecutivas** (antes 2 failed en cada intento de la batería completa).

---

## 9. P3 — El gate de CI de A14 toleraba skips silenciosos

El job `grammar-discovery-pg` declara `A14_GRAMMAR_PG_REQUIRED=1` para exigir PostgreSQL real,
pero `test_a14_grammar_discovery_pg` **no leía ese gate**: podía quedar `skipped` y el job
seguir **en verde**, convirtiendo la certificación en un **fantasma**. Un step nuevo inspecciona
el log (`-rs`) y **falla el job** si algo quedó `SKIPPED`, independientemente de qué gate lea
cada test. Además, `load_dotenv(_DOTENV)` en `test_strategy_lifecycle_pg` se condiciona a que el
fichero exista (en CI no hay `.env`; el entorno del job ya trae `DATABASE_URL`).

---

## 10. Qué auditar

| Artefacto                                           | Ruta                                                                                                                  |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Secuenciador del ledger                             | `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/ledger_repository.py` (`next_executed_at`) |
| Trade usa el secuenciador                           | `packages/py/application/src/bolsa_application/accounts/trade.py`                                                     |
| Custodia (secuenciador + `balance_after` post-lock) | `packages/py/application/src/bolsa_application/accounts/custody.py`                                                   |
| Depósito/retiro                                     | `packages/py/application/src/bolsa_application/accounts/cash.py`                                                      |
| Gramática de Discovery (vetos + pares axiales)      | `packages/py/application/src/bolsa_application/discovery_grammar.py`                                                  |
| Borrado de listas (items antes de la lista)         | `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/list_repository.py` (`delete`)             |
| Claim/Lock del outbox                               | `packages/py/application/src/bolsa_application/lifecycle_outbox.py` (`claim_batch`)                                   |
| Gate de CI de A14 (anti-skip)                       | `.github/workflows/python-ci.yml` (job `grammar-discovery-pg`)                                                        |
| Pool del chaos + test de lease reescrito            | `packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py`                                                |
| Claim/Lock del recovery                             | `apps/api-python/tests/test_live_order_recovery_concurrency_pg.py`                                                    |
| Certificación por proceso del scheduler             | `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py`                                                    |

---

## 11. Cómo reproducir la verificación

```bash
# --- Calidad (invocación EXACTA de CI) ---
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent

# --- Tests puros (sin DB) ---
uv run pytest packages/py/application/tests -q

# --- Con PostgreSQL: el orden del ledger bajo concurrencia ---
uv run pytest packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py -q
uv run pytest apps/api-python/tests/test_live_order_recovery_concurrency_pg.py \
              apps/api-python/tests/integration/test_idempotency_reused_409.py -q
uv run pytest apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py -q
```

---

## 12. Matriz de aserciones → código/tests

| Aserción                                             | Código                                        | Test                                                          |
| ---------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------- |
| El `executed_at` sale del secuenciador, no del reloj | `trade.py` (`next_executed_at`)               | `test_trade_usa_el_secuenciador_del_ledger_no_el_reloj`       |
| El secuenciador es estrictamente creciente           | `ledger_repository.py`                        | `test_secuenciador_es_estrictamente_creciente`                |
| Trade precede a su fee (1 µs)                        | `trade.py` (`_ledger_ordering`)               | `test_ledger_trade_y_fee_comparten_el_executed_at_del_trade`  |
| Custodia deriva `balance_after` del POST-lock        | `custody.py`                                  | `test_custody_job.py` (suite)                                 |
| Concurrencia: la cadena `balance_after` encadena     | `ledger_repository.py` (secuenciador)         | `test_load_concurrency_flow.py` (5 escenarios)                |
| Los leases vivos son disjuntos                       | `live_order_store.py` (`claim_unknown_batch`) | `test_two_workers_claim_disjoint_unknown_batch`               |
| El proceso scheduler produce ticks/eventos           | `scheduler_worker`                            | `test_a9_scheduler_process_pg_zero_human.py` (2)              |
| Todo plan gramatical tiene ≥2 columnas operables     | `discovery_grammar.py` (vetos + pares)        | `test_grammar_variants_produce_at_least_two_operable_columns` |
| El trigger Donchian es alcanzable en serie creciente | `discovery_grammar.py` (`_donchian_break`)    | `test_grammar_donchian_trigger_is_reachable`                  |
| La certificación A14 produce PBO real (no 0 trials)  | `strategy_discovery_engine.py`                | `test_a14_grammar_discovery_pg.py`                            |
| Borrar una lista con items no viola la FK            | `list_repository.py` (`delete`)               | `test_delete_list_with_items_does_not_violate_fk`             |

---

## 13. Invariantes intactas

`AUTO ⇒ SIMULATED` · LIVE bloqueado · sin LLM en hot path · fail-closed · H1/H2 · long-only ·
gates CPCV/PBO/DSR/WFE/OOS **sin relajar** · clave compuesta `familia|region` y
`_collapse_regions` sin modificar · Alembic head `039_research_trials_regime` (**sin migración
nueva en esta fase**).

> **Nota sobre el conteo de planes.** El `1784` que figuraba como «anti-explosión» **ya no es
> el número correcto tras la sección 6**: los dos vetos de inanición retiran planes
> genéticamente inoperables, y el grid queda en **1684 con 0 degenerados**. El invariante de
> «anti-explosión» que sigue vigente es el **techo del presupuesto** (`GrammarBudget`), no el
> número exacto: el conteo exacto es una **consecuencia** de los vetos y se recalcula en
> `test_default_budget_yields_a_bounded_exact_plan_count`. La auditoría debe verificar que
> **ninguna candidata emitida queda sin evidencia posible**, no que el número sea 1784.

---

## 14. Verificación local ejecutada

**Cierre de flaky (secciones 1–5):**

```
ruff (--config pyproject.toml)                    → All checks passed
import-linter (packages/py/.importlinter)         → 4 contratos OK (578 ficheros, 3020 deps)
mypy (fuentes tocadas)                            → Success: no issues found in 272 files
pytest packages/py/application/tests              → 1470 passed
pytest packages/py/infrastructure/tests           → 137 passed, 1 xfailed
pytest recovery + idempotencia 409                → 8 passed
chaos test_load_concurrency_flow (10 pasadas)     → 0 fallos (10/10)
test_a9_scheduler_process_pg_zero_human (8)       → 8/8 (~28 s/pasada)
test_two_workers_claim_disjoint_unknown_batch (5) → 5/5
mutación del secuenciador (revertir el fix)       → el test NUEVO falla (detecta la regresión)
```

**Tercera pasada (secciones 6–9), ya sobre el commit que apunta el tag:**

```
ruff (--config pyproject.toml)                    → All checks passed
mypy (fuentes tocadas)                            → Success: no issues found in 477 files
batería EXACTA del job `quality` de CI            → 1306 passed, 0 failed
gramática + A14 (test_discovery_grammar + pg)     → 40 passed
apps/api-python/tests + infrastructure/tests      → 521 passed × 2 pasadas consecutivas (antes 2 failed)
```

---

## 15. Nota de entorno (no del código)

Los flaky restantes se reprodujeron **solo** bajo ejecuciones back-to-back masivas en la
**máquina local**: el PostgreSQL agotaba conexiones y los tests que dependen del arranque de
un subproceso agotaban su plazo. Con el pool de los chaos acotado a 24 y la BD en reposo,
**10/10 del chaos y 8/8 del A9** fueron verdes. El CI (máquina limpia, un job por vez) no
reproduce esa saturación. Se anota para no confundirla con una regresión de código.

---

## 16. Cobertura de CI pendiente (hallazgo para la auditoría)

El job `quality` de `.github/workflows/python-ci.yml` corre **una lista explícita** de tests,
no las suites completas. En particular **no** ejecuta:

- `packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py` (el escenario de
  estrés que cerró el bug del ledger).
- `apps/api-python/tests/test_live_order_recovery_concurrency_pg.py` y el A9 por proceso.

Es decir: los chaos tests requieren PostgreSQL y hoy se validan **localmente**. Es una
**deuda de cobertura** honesta: el fix del ledger está cubierto por un test que la CI no
ejecuta, aunque **sí** lo está por la suite de aplicación (1468 passed en CI) y por la
regresión del secuenciador, que es pura y hermética.

**Estado tras la tercera pasada:** el `Release tag CI` de `v2.39.2-beta` **sí** corre
`lifecycle-pg`, `dr-verify` y `certify`; el `Python CI` (push a `main`) corre `quality`,
`lifecycle-pg`, `paper-forward-pg` y `grammar-discovery-pg`, los cuatro **GREEN** en
`9444b364`. La deuda de los **chaos** sigue siendo la única pieza que no entra en CI.
