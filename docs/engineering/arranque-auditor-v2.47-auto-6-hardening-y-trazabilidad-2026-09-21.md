# Arranque — guía de ataque para el auditor (`v2.47-beta`) — 2026-09-21

**Qué es esto.** Ordena **por qué atacar primero** y **cómo medirlo** en la ref sellada **`v2.47-beta`**
(`1.72.0-beta`). Las `ruta:línea` están **verificadas en el árbol** y cada bloque trae el **comando exacto**.
**No** sustituye al [audit-pack](./audit-pack-v2.47-auto-6-hardening-y-trazabilidad-2026-09-21.md): si hay
contradicción, **manda el pack**.

**Sello de partida:** tag anterior `v2.46-beta`; este sello incluye **migración `044_auto_cycle_trace`**.

---

## 0. Si solo tienes una hora

1. **§1 — la economía direccional**: ¿queda algún camino en el que una dirección no soportada se trate como
   larga? Es el defecto que la auditoría encontró y el único con consecuencia **económica directa**.
2. **§2 — la parada dura durable**: ¿puede un reinicio olvidar el halt, o una liberación externa no llegar?
3. **§3 — exactly-once bajo muerte**: el invariante de dinero, en cada costura.
4. **§4 — `cycle_id`**: ¿hay ciclo acuñado **sin** señal (loteria) o heredado mal en la salida?

Todo lo demás (auto-evaluación, UI, móvil) es importante pero **no** mueve dinero.

---

## 1. La economía dejó de ser largo-only (ataca primero)

**Por qué.** `_risk_geometry` rechazaba `s >= e` (la geometría **invertida de una larga**) y el coste estaba
**hardcodeado** a `direction="long"`. El defecto era **latente** (el motor de entrada es largo-only), pero de
la misma familia que el `stop_worsens` de larga que ya se corrigió en el kernel de trailing.

**Dónde mirar (verificado).**

| Punto                                         | `ruta:línea`                                                                              |
| --------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Geometría direccional                         | `packages/py/analytics/src/bolsa_analytics/cognitive/expected_value.py:286`               |
| Premio de la corta (hacia **abajo**)          | `expected_value.py:315`                                                                   |
| Motivo tipado fail-closed                     | `expected_value.py:59` (`EV_DIRECTION_UNSUPPORTED`), usado en `:300` y `:178`             |
| Entrada pública que propaga la dirección      | `expected_value.py:140`                                                                   |
| Coste por dirección (firma real)              | `packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_reservation.py:263`        |
| **Fuente única** de dirección en el motor     | `packages/py/application/src/bolsa_application/auto_v2_entry.py:833` (`_ENTRY_DIRECTION`) |
| `BUY → long`, cualquier otra cosa → `None`    | `auto_v2_entry.py:836` (`entry_direction`)                                                |
| Dimensionado, snapshot y economía leen de ahí | `auto_v2_entry.py:737`, `:878`, `:1253`                                                   |

**Preguntas incómodas (y cómo contestarlas).**

- **¿Existe una segunda fuente de dirección?** `rg -n 'direction="long"' packages/py apps/api-python` y
  `rg -n '"long"' packages/py/application/src/bolsa_application/auto_v2_entry.py`. Hoy debe salir **solo** el
  literal de `_ENTRY_DIRECTION` y los defaults de firma.
- **¿Una dirección desconocida se asume larga en algún punto?** Míralo con la mutación **M9**: si la matriz
  sigue verde, la suite dejó de cubrirlo.
- **El test del coste corto, ¿muerde?** Es el hallazgo de método de esta pasada: el test que **ya existía** era
  **autorreferencial** (recalculaba el neto con el propio `cost_currency`) y la mutación de la dirección del
  coste **no lo mordía**. Se añadió
  `test_a_short_is_charged_with_the_short_legs_not_with_the_long_ones` con el **tarifario real**
  (`packages/py/analytics/tests/test_expected_value.py`) y **M18**. **Verifícalo tú**: revierte la dirección
  del coste y exige rojo.
- **¿Se ha habilitado SHORT por la puerta de atrás?** No debe existir ninguna ruta donde `entry_direction`
  devuelva `long` para un `SELL`, ni un `decide_portfolio(direction="short")`.

---

## 2. La parada dura es DURABLE (P0 de la pasada anterior)

**Por qué.** En `v2.46` el halt vivía **en RAM**: un reinicio lo olvidaba. Y la liberación con
`reconciliation_id` estaba implementada **sin emisor de producción**.

**Dónde mirar (verificado).**

| Punto                                                      | `ruta:línea`                                                                                      |
| ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Adopción del halt durable al arrancar (y de su liberación) | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:1370` (`_v2_load_kill_state`) |
| Liberación durable (exige `reconciliation_id`)             | `auto_simulation_worker.py:1503` (`release_kill_switch_durable`)                                  |
| Endpoint de producción                                     | `apps/api-python/src/bolsa_api/api/v1/routes/risk.py:135` (`POST /kill-switch/durable-release`)   |
| Contrato (body/response, `missing_reconciliation_id`)      | `risk.py:70`, `:83`, `:156`                                                                       |
| Estado durable (con `release_reconciliation_id`)           | `packages/py/application/src/bolsa_application/kill_switch_store.py:61`                           |
| Golden hermético                                           | `apps/api-python/tests/test_auto_v46_hardkill_recovery.py` (5)                                    |
| Gemelo PG                                                  | `apps/api-python/tests/test_auto_v46_hardkill_recovery_pg.py` (2)                                 |

**Preguntas incómodas.**

- **¿Un halt persistido por otro proceso se adopta en el arranque?** Sí debe: `_v2_load_kill_state` no solo
  restaura el engagement, también adopta una **liberación externa posterior** al halt local. **M17** lo mide:
  si dejas de adoptarlo, caen **2** tests.
- **¿La liberación por API toca el proceso del worker?** **No** (a propósito): escribe la liberación durable y
  el worker la adopta en su siguiente turno. Si alguien "arregla" esto hablando con el worker en memoria, se
  rompe el aislamiento que hace que funcione con varios procesos.
- **`BROKER_DESYNC`: ¿sigue sin productor?** Se declara en el pack (§2.3). Si el auditor encuentra un camino
  que **finge** cubrirlo, es un hallazgo; si no lo hay, es una deuda declarada, no un fallo.
- **`not_engaged`**: debe ser **no-op idempotente** (`risk.py:167`), no un error.

---

## 3. Exactly-once bajo muerte, en cada costura

**Por qué.** En `v2.46` el Crash Day de proceso **no podía** morir _mid-fill_ (el broker SIM liquidaba todas
las tranchas en el mismo tick): la ventana **no existía**. Eso sigue siendo verdad; lo que cambia es que ahora
se cubre **por inyección**.

**Dónde mirar.**

- `apps/api-python/tests/test_auto_v46_crash_injection_matrix.py` (6): `save_claim`, `start_apply`
  (capturado), `apply_finance` **antes** de `mark_applied` (aplicando), **tras el primer chunk APPLIED**
  (parcial), lease vencido y reclaim.
- `apps/api-python/tests/test_auto_v46_crash_injection_pg.py` (2): las transiciones críticas contra
  PostgreSQL real.
- La máquina de estados y el lease: `packages/py/application/src/bolsa_application/execution_event.py:1068`
  (`apply_execution_financial_once`).

**Preguntas incómodas.**

- **¿Se inyecta desde producción?** **No**: los wrappers que lanzan `CrashInjected` viven **solo en test**
  (patrón `test_a9_1_crash_battery.py`). Si encuentras una ruta de crash añadida al código de producción, es
  un hallazgo.
- **¿El invariante se comprueba sobre el ledger real o sobre la RAM?** Debe ser sobre los **stores durables**
  tras "reiniciar" (worker nuevo sobre los mismos stores), no sobre el objeto en memoria.
- **¿Converge siempre?** `RETRY → APPLIED` o reclaim del lease vencido, **sin** segunda materialización y
  **sin** pérdida.

---

## 4. `cycle_id`: identidad del ciclo financiero

**Dónde mirar (verificado).**

| Punto                                        | `ruta:línea`                                                                                |
| -------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Acuñado determinista por `(cuenta, señal)`   | `packages/py/application/src/bolsa_application/auto_v2_entry.py:1641` (`auto_cycle_id`)     |
| Clave de candidato                           | `auto_v2_entry.py:1663` (`candidate_key`) · `:1681` (`_dedupe_candidates`)                  |
| Journal con `cycleId`                        | `auto_v2_entry.py:2122` (`_journal_entry`) · `:2080` (`_expected_value_for_decision`)       |
| Ciclo de la posición / del plan              | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py:2030` (`_v2_cycle_for`) |
| Migración (3 columnas + 3 índices, nullable) | `packages/py/infrastructure/alembic/versions/044_auto_cycle_trace.py:29`                    |
| Prueba de la cadena                          | `packages/py/application/tests/test_auto_v47_cycle_trace.py` (11)                           |

**Preguntas incómodas.**

- **¿Dos workers con la misma señal acuñan el MISMO ciclo?** Debe: es determinista (`cyc-<sha256[:12]>`), como
  la identidad de la decisión. **M11** lo mide (3 rojos si se rompe).
- **¿Qué pasa sin `signal_id`?** Se conserva el fallback **aleatorio** histórico: no hay clave estable que
  reclamar y un id compartido por accidente sería **peor** que no tenerlo. Compruébalo en `auto_cycle_id`.
- **El trazado inverso, ¿de verdad funciona?** `fill → cycle_id → reserva/salida → decisión`. Sin
  `sim_fill_finance_context.cycle_id` (migración `044`, tercera columna) sería **imposible**: es la razón de
  existir del índice.
- **¿Backfill?** **No hay**: `NULL` = fila anterior a `2.47`. Si ves filas "rellenadas con un ciclo
  inventado", es un hallazgo.

---

## 5. Identidad formal de señales (colisión ya no silenciosa)

**Dónde mirar.** `auto_v2_entry.py:1915` (`SIGNAL_SUPERSEDED_BY_CANDIDATE`),
`:1920` (`SIGNAL_DISTINCT_STRATEGY_NOT_REPRESENTABLE`), `:2045` (`_superseded_candidate_entry`),
`:1288`–`:1314` (dos estrategias seleccionadas ⇒ declaración), y el interruptor
`AUTO_ENGINE_SIM_V2_ALLOW_DISTINCT_STRATEGIES` (`:443`, default **OFF**).

**Preguntas incómodas.**

- **¿Sigue habiendo colapso silencioso?** **M16** (3 rojos): el dedupe debe **devolver** las superadas y el
  journal debe publicar **ambos** `signal_id` y `strategy_version`.
- **¿La política está por escrito?** Sí: la discriminación depende de `strategy_version` + `signal_id` +
  política de cartera, **nunca** de `(cuenta, instrumento, barra)`.
- **Con la opción ON, ¿quién decide entre dos estrategias del mismo instrumento?** El **optimizador de
  cartera** (capital/correlación), **no** el dedupe. Y si no caben en una posición, se **declara**.

---

## 6. `AUTO-7` slice 1 (self-evaluation puro, read-only)

**Dónde mirar.** `packages/py/analytics/src/bolsa_analytics/cognitive/auto_self_evaluation.py:576`
(`evaluate_auto_self_evaluation`), el puente `packages/py/application/src/bolsa_application/auto_self_evaluation_feed.py:155`,
y el endpoint `GET /api/v1/auto/self-evaluation?version=…`.

**Preguntas incómodas (es la superficie más nueva).**

- **¿Declara huecos o los rellena con ceros?** Es la prueba de carácter del módulo: sin oportunidades,
  `seen = None` (**no** cierra el embudo); un coste de rechazo sin **ambos** precios es `None` (**jamás**
  `0.0`); un ciclo repetido se cuenta **una vez y se declara**; un ciclo **sin** versión **no se reparte**
  entre estrategias. **M13/M14/M15** son exactamente esas tres preguntas (1 + 3 + 1 rojos).
- **¿Es de verdad read-only?** No debe tocar pesos, umbrales ni sizing (≥3 llamadas a `pure`/sin escrituras).
  Si alguien conecta sus métricas al sizing, es una fase nueva con su pack.
- **¿El muestreo fino bloquea el flag de "decisivo"?** Debe (`sample_quality`).

---

## 7. UI (valor esperado y móvil)

**Dónde mirar.** `packages/shared/src/cognitive/expected-value-copy.ts` (formateador propio: signo y `€`),
`entry-operating-truth.ts` / `decision-explain-view.ts` (DTO compartido), y las dos superficies
(`apps/web/src/features/trading/entry-operating-summary.tsx`, `decision-explain-panel.tsx`). Móvil:
`apps/web/src/features/trading/use-narrow-cabin.ts` + `apps/web/src/lib/use-media-query.ts` (endurecido: sin
`matchMedia` degrada a `false`, no revienta) y `apps/web/src/lib/test-viewport.ts`.

**Preguntas incómodas.**

- **¿Se pinta un `0 €` cuando no hay medida?** **No**: sin `expectedR` ni `netExpectedCurrency` la fila/sección
  **no aparece**. Hay tests que lo afirman; verifica que **no** son vacíos.
- **¿Puede discrepar lo publicado del valor que dimensionó la decisión?** Si el optimizador no corrió,
  `_expected_value_for_decision` (`auto_v2_entry.py:2080`) lo recalcula con la **misma** geometría.
- **¿El móvil oculta información?** Debe **apilar**, no ocultar: `data-cabin-width="narrow"` en la raíz y todo
  el contenido presente. Es medible en test (`stubNarrowViewport`).

---

## 8. Comandos exactos (no los reinventes)

```bash
# Estático
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# El gobernador NO se movió
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run python apps/api-python/scripts/v2_43_governor_evidence.py; echo "exit=$?"

# Los dos bloques offline de CI (targets EXTRAÍDOS del YAML; medida por JUnit XML)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores

# Suites PG nuevas CON gate (un skip mudo NO certifica)
AUTO_HARDKILL_PG_REQUIRED=1 AUTO_CRASH_INJECT_PG_REQUIRED=1 AUTO_MULTIPROCESS_PG_REQUIRED=1 \
  uv run pytest apps/api-python/tests/test_auto_v46_hardkill_recovery_pg.py \
                apps/api-python/tests/test_auto_v46_crash_injection_pg.py \
                apps/api-python/tests/test_auto_v46_multiprocess_pg.py -q -rs

# Migración
uv run alembic -c packages/py/infrastructure/alembic.ini heads     # 044_auto_cycle_trace

# La matriz de mutaciones (18/18; restaura byte a byte y verifica la huella del árbol)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py

# Frontend
pnpm --filter @bolsa/shared build && pnpm --filter @bolsa/shared typecheck && pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/web typecheck && pnpm --filter @bolsa/web lint && pnpm --filter @bolsa/web test
pnpm --filter @bolsa/web contract:check
```

---

## 9. Cinco preguntas abiertas que el autor NO cierra

1. **¿Es `044` suficiente para el trazado inverso completo?** Con `cycle_id` en reservas, salidas y contexto
   del fill, el camino está cubierto; pero un ciclo **sin** `signal_id` (fallback aleatorio) no es reclamable
   por dos workers. ¿Cuál es el **coste** de ese hueco en producción?
2. **¿Convergen de verdad N procesos?** El invariante se mide **en la BD** (1 orden, 1 reserva, 1 efecto),
   con `N` pequeño. ¿Aguanta el patrón con contención alta y un `kill` en medio?
3. **¿El orquestador de release por API es suficiente?** El endpoint escribe la liberación durable y el worker
   la adopta en su siguiente turno: hay una **ventana** entre la liberación y su adopción. ¿Qué pasa si el
   worker muere en esa ventana?
4. **¿`allow_distinct_strategies` debe seguir en OFF?** Con ON, dos versiones de estrategia compiten por el
   mismo instrumento sujetas al optimizador. La pregunta del owner es **de producto**: ¿queremos eso, o
   queremos que una estrategia nueva no pueda arrebatar el instrumento a la que ya está?
5. **¿Debe el broker SIM dejar de liquidar por tick?** La ventana _mid-fill_ está cubierta **por inyección**,
   no por construcción: es la única desviación grande que queda viva en la línea AUTO.

---

## 10. Lo que **no** debes asumir

- Que `2178`/`2189` signifiquen "todo corre": significa que corre **lo listado**. La lista de
  `packages/py/application/tests` es explícita; esta pasada encontró **un fichero entero** (10 tests) que
  **nunca** había corrido en CI. Auditar la lista es trabajo legítimo.
- Que un test verde proteja nada: la pasada destapó un test **autorreferencial** que no mordía a su propia
  línea (M18) y un `.pyc` que hacía que la sonda midiera bytecode en vez del árbol.
- Que `skipped` sea inocuo: los pasos PG llevan guard **anti-skip** justamente porque un skip mudo no
  certifica.
