# Audit Pack — V2.39.2 · Cierre de flaky y orden real del ledger

> **Punto de entrada único para auditoría externa desde GitHub**, sin acceso al entorno.
> Fase: **v2.39.2** — cierre de los `flaky` residuales detectados en la **auditoría interna
> previa a la externa** sobre `v2.39.1`.
>
> **Base auditada:** `v2.39-beta` (`e94f2632`).
> **Commit de esta fase:** `51e4f305` (fix) + `cc50ae36` (bump de versión).
> **Alembic head:** `039_research_trials_regime` (esta fase **no** añade migración).
> **Bump:** `1.64.1-beta` → `1.64.2-beta`.
> **Flags:** sin cambios (`AUTO_ORCHESTRATOR_ADAPTIVE_REGIME` sigue **OFF** por defecto).

---

## 0. Resumen ejecutivo

La auditoría interna de `v2.39.1` dejó **4 tests PG no deterministas**. Al atacarlos con
instrumentación forense (volcado del entrelazado de `executed_at` cuando la cadena
`balance_after` rompía), el "flaky" resultó ser **un bug real de producción** que la primera
pasada no alcanzó a cerrar, más **una configuración de test que enmascaraba el veredicto**.

| Hallazgo                                                                             | Naturaleza        | Impacto                                                       |
| ------------------------------------------------------------------------------------ | ----------------- | ------------------------------------------------------------- |
| **P1** — El `executed_at` del ledger se derivaba del **reloj de pared**              | Bug de producción | Ledger **no reproducible/auditable** bajo concurrencia        |
| **P1** — `ApplyCustodyFees` calculaba `balance_after` con cash **PRE-lock**          | Bug de producción | `balance_after` desalineado de su `amount`                    |
| **P2** — `pool_size=64` agotaba `max_connections` del PG local                       | Config de test    | Fallos **en ráfaga** que **enmascaraban** el veredicto        |
| **P2** — `test_two_workers_claim_disjoint_unknown_batch` no certificaba lo que decía | Test deshonesto   | Afirmaba exclusión mutua con un escenario que la **refutaba** |
| **P3** — El bucle antirrecompra del A9 agotaba el presupuesto **siempre**            | Test ineficiente  | ~518 s por pasada y fallos por agotamiento de plazo           |

**Veredicto:** el ledger ya es **secuenciado por estado** (no por reloj), los chaos tests son
deterministas y el A9 pasó de ~518 s a **~28 s**.

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

## 6. Qué auditar

| Artefacto                                           | Ruta                                                                                                                  |
| --------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Secuenciador del ledger                             | `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/ledger_repository.py` (`next_executed_at`) |
| Trade usa el secuenciador                           | `packages/py/application/src/bolsa_application/accounts/trade.py`                                                     |
| Custodia (secuenciador + `balance_after` post-lock) | `packages/py/application/src/bolsa_application/accounts/custody.py`                                                   |
| Depósito/retiro                                     | `packages/py/application/src/bolsa_application/accounts/cash.py`                                                      |
| Pool del chaos + test de lease reescrito            | `packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py`                                                |
| Claim/Lock del recovery                             | `apps/api-python/tests/test_live_order_recovery_concurrency_pg.py`                                                    |
| Certificación por proceso del scheduler             | `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py`                                                    |

---

## 7. Cómo reproducir la verificación

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

## 8. Matriz de aserciones → código/tests

| Aserción                                             | Código                                        | Test                                                         |
| ---------------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------ |
| El `executed_at` sale del secuenciador, no del reloj | `trade.py` (`next_executed_at`)               | `test_trade_usa_el_secuenciador_del_ledger_no_el_reloj`      |
| El secuenciador es estrictamente creciente           | `ledger_repository.py`                        | `test_secuenciador_es_estrictamente_creciente`               |
| Trade precede a su fee (1 µs)                        | `trade.py` (`_ledger_ordering`)               | `test_ledger_trade_y_fee_comparten_el_executed_at_del_trade` |
| Custodia deriva `balance_after` del POST-lock        | `custody.py`                                  | `test_custody_job.py` (suite)                                |
| Concurrencia: la cadena `balance_after` encadena     | `ledger_repository.py` (secuenciador)         | `test_load_concurrency_flow.py` (5 escenarios)               |
| Los leases vivos son disjuntos                       | `live_order_store.py` (`claim_unknown_batch`) | `test_two_workers_claim_disjoint_unknown_batch`              |
| El proceso scheduler produce ticks/eventos           | `scheduler_worker`                            | `test_a9_scheduler_process_pg_zero_human.py` (2)             |

---

## 9. Invariantes intactas

`AUTO ⇒ SIMULATED` · LIVE bloqueado · sin LLM en hot path · fail-closed · H1/H2 · long-only ·
gates CPCV/PBO/DSR/WFE/OOS sin relajar · anti-explosión `len(plans) == 1784` · clave compuesta
`familia|region` y `_collapse_regions` sin modificar · Alembic head `039_research_trials_regime`
(**sin migración nueva en esta fase**).

---

## 10. Verificación local ejecutada

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

---

## 11. Nota de entorno (no del código)

Los flaky restantes se reprodujeron **solo** bajo ejecuciones back-to-back masivas en la
**máquina local**: el PostgreSQL agotaba conexiones y los tests que dependen del arranque de
un subproceso agotaban su plazo. Con el pool de los chaos acotado a 24 y la BD en reposo,
**10/10 del chaos y 8/8 del A9** fueron verdes. El CI (máquina limpia, un job por vez) no
reproduce esa saturación. Se anota para no confundirla con una regresión de código.

---

## 12. Cobertura de CI pendiente (hallazgo para la auditoría)

El job `quality` de `.github/workflows/python-ci.yml` corre **una lista explícita** de tests,
no las suites completas. En particular **no** ejecuta:

- `packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py` (el escenario de
  estrés que cerró el bug del ledger).
- `apps/api-python/tests/test_live_order_recovery_concurrency_pg.py` y el A9 por proceso.

Es decir: los chaos tests requieren PostgreSQL y hoy se validan **localmente**. Es una
**deuda de cobertura** honesta: el fix del ledger está cubierto por un test que la CI no
ejecuta, aunque **sí** lo está por la suite de aplicación (`1470 passed` en CI) y por la
regresión del secuenciador, que es pura y hermética.
