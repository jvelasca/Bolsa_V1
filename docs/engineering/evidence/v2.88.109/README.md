# Evidencia — `v2.88.109-beta` / **`§6` — bucle diario con el MOTOR REAL**: las nueve etapas canónicas desde hechos durables

> **Base funcional:** `v2.88.108-beta` (commit `5fbb0e4f`). Cierra el grueso de `§6` de la [auditoría profundizada](https://github.com/jvelasca/Bolsa_V1) (`Bucle diario certificado`).
> **Naturaleza:** **`Δ motor = 0`** (solo se añaden/refuerzan PRUEBAS; no se toca código de producto) · `Δ decisión = 0` · **SIN migración** (head `052_top3_opportunities`) · **contrato sin cambio** (`contract:check` verde).

---

## 1. Qué cierra (el hueco de `§6`)

La auditoría declaró que el E2E `S5` y el CLI de siembra certificaban la **presentación** (con un ciclo SEMBRADO), pero no que el **motor** generase espontáneamente el ciclo `señal→decisión→reserva→orden→fill→protección→liquidación→cierre`. Y, medido sobre el repositorio, **ningún** test arrancaba el worker/runtime REAL y asertaba las **nueve etapas canónicas** (`SIGNAL → TOP_N → RISK → RESERVATION → ORDER → FILL → PROTECTION → SETTLEMENT → CYCLE_CLOSED`) del ciclo **producido** por él.

Este sello lo cierra con **pruebas gated sobre PostgreSQL real**, reutilizando los arneses que YA corren el camino real (no se inventa un harness nuevo).

## 2. `§6-a` — las NUEVE etapas del ciclo del WORKER (Golden Day)

[`test_golden_day_v2_process_pg.py`](../../../../apps/api-python/tests/test_golden_day_v2_process_pg.py) conduce el **proceso real** `python -m bolsa_api.workers.scheduler_worker` (con `AUTO_OPERATIONAL_AUDIT=1`), abre posiciones y cierra el libro. Su `FASE 3` ahora **aserta la cadena canónica completa**:

- Toma el ciclo que **CERRÓ** (`closed is True`) reconstruido del material durable y exige, para **cada** una de las nueve etapas, `state == "reached"` leída del **read model durable** (`read_operational_monitor`), no de la proyección ni de la RAM.
- Si una etapa no enciende, el fallo nombra **cuál** y su estado (`unknown`/`absent`) ⇒ un hueco del motor se ve como hueco, no como un verde.
- **Régimen declarado (premisa §5.2):** este certificado corre el sandbox `DÍA-D AUTO` con PRECIO INYECTADO (`flat_price_script`); el régimen de PRECIO REAL es el test hermano `..._real_price_process_...` (`AUTO_ENGINE_SIM_REAL_PRICE=1`, `price_source == MARKET_CLOSE`).

**Control negativo (`§6` — «debe rechazar una asociación incorrecta»).** El drill-down por un `cycle_id` **ajeno** al día devuelve **ese** ciclo (se lo pidieron) pero con las etapas **SIN encender**: un id incorrecto **no hereda** el `SIGNAL` de otro ciclo. Cierra el riesgo de que la superficie de detalle «preste» hechos de un ciclo a otro.

## 3. `§6-b` / `H1` — la identidad EXACTA viaja y se presenta (dos mitades)

H1 se certifica en las **dos mitades** del camino real:

1. **Propagación por el lifecycle (DISCOVERY → ACTIVE).** En [`test_a11_discovery_to_auto_sim_pg.py`](../../../../apps/api-python/tests/test_a11_discovery_to_auto_sim_pg.py) las candidatas de discovery declaran un `preset_key` **distinto del nombre de familia** (`a11_cert_preset` ≠ `sma_crossover`). Tras el embudo real (DISCOVERY → SHADOW → PROMOTION), se exige `record.active.preset_key == "a11_cert_preset"`: si el motor sustituyera la identidad por el nombre de familia (la fabricación que `v2.88.108` eliminó), la aserción **fallaría**.
2. **Sello durable + presentación por el monitor (V2 real).** En [`test_auto_v2_durable_pg.py`](../../../../apps/api-python/tests/test_auto_v2_durable_pg.py) (worker REAL con `AUTO_ENGINE_SIM_V2=1` y `AUTO_OPERATIONAL_AUDIT=1`) se añade, sobre la fuente `active-strategy:ver-abc::sma_crossover`, que el **paso `SIGNAL` del monitor** exponga `strategyPresetKey == "sma_crossover"` leído de PostgreSQL. Cierra el eslabón «identidad sellada → identidad **presentada**» sin la RAM del worker. El control negativo ya existente (fuente sin `::`) prueba que la clave se **omite**, no se fabrica.

## 4. Verificación (local, PostgreSQL real)

- **Los tres ficheros gated** (`test_auto_v2_durable_pg.py`, `test_a11_discovery_to_auto_sim_pg.py`, `test_golden_day_v2_process_pg.py`) → **9 passed** (`AUTO_V2_DURABLE_PG_REQUIRED=1`, `AUTO_ORCHESTRATOR_PG_REQUIRED=1`, `AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1`).
- **Regresión de vecinos** (`test_auto_operational_monitor_pg.py`, `test_auto_operational_monitor.py`, `test_auto_v2_worker_integration.py`, `test_auto_scheduler_real_pg_zero_human_intervention.py`, `test_auto_m2_operational_audit_seam.py`) → **137 passed**.
- **Guardián DÍA-D** [`test_dia_d_bump_guard.py`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) → **1 passed**.
- **Estilo:** `ruff` **All checks passed** · `lint-imports --config packages/py/.importlinter` → **4 kept, 0 broken** · `mypy` no cubre `tests/` (scope CI = `src`), así que no cambia.
- **CI de tag:** `lifecycle-pg` ya ejecuta ambos ficheros con sus gates (`AUTO_ORCHESTRATOR_PG_REQUIRED=1`, `AUTO_GOLDEN_DAY_V2_PG_REQUIRED=1`, `AUTO_V2_DURABLE_PG_REQUIRED=1`), así que un skip es fallo duro — **sin cambio de workflow**.

## 5. Límites declarados (sin fabricar)

- **`Δ motor = 0`:** este sello añade **solo pruebas**; no toca motor, umbrales, reparto, `TOP_N`/régimen/selección/protección. Por eso **`Δ decisión = 0`** es por construcción (no hay artefacto OOS que comparar).
- **DÍA-D ENLAZADO al ciclo (P2) sigue ABIERTO:** el feedback DÍA-D es un artefacto de replay offline; compartir la forma de `cycleId` (`cyc-…`) y la ventana `entryDay` **no** es una unión en tiempo de lectura. Enlazarlo exige materializar esa costura (fase separada).
- **Validación OOS por valor (`§8`, P3) sigue FUERA de alcance:** sin retorno neto/drawdown/Sharpe reproducibles no se afirma rentabilidad.
- **El Golden Day no cubre identidad H1** (su spine es `unversioned`): las nueve etapas y la identidad se certifican en arneses **distintos** y complementarios.
- **Tag `unsigned`** (limitación de certificación, no defecto).
