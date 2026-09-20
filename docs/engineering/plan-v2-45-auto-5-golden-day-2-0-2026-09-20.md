# Plan de fase — `V2.45` / `AUTO-5` — Golden Day 2.0 (`1.70.0-beta`)

**Fecha:** 2026-09-20 · **Punto de partida:** tag `v2.44-beta` → `c95819c1` (AUTO-4 Portfolio Optimizer
cerrado) · **Migración:** **ninguna** (decidido: head sigue en `043_exit_identity_and_kill_state`).
**Roadmap:** §7 de [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md).
**Relevo de entrada:** [`traspaso-relevo-post-v2-44-auto-4-golden-day-2-0-2026-09-20.md`](./traspaso-relevo-post-v2-44-auto-4-golden-day-2-0-2026-09-20.md).

> **Aviso de numeración (declarado):** el plan de `v2.43.2` reutilizó la etiqueta «v2.44» para Exit
> Governance. Esta fase es la **`V2.45` del roadmap**: `AUTO-5 — Golden Day 2.0` / `1.70.0-beta`. Es el aviso
> que el plan de `v2.44` dejó escrito y que aquí se mantiene para que nadie confunda las dos etiquetas.

---

## 0. Decisiones del owner (fijadas 2026-09-20)

| Decisión       | Elección                                                                                                                                                                  |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Alcance        | **Fase completa**: certificación end-to-end con PG real + proceso de scheduler real, **más** atribución por estrategia, MAE/MFE y coste de oportunidad de las rechazadas. |
| Migración      | **NINGUNA.** La identidad de estrategia entra como clave **aditiva** del `payload` JSONB del journal; `mfe_mae` ya vive en el JSONB de posición.                          |
| Capas del gate | **DOS**: embudo hermético en `quality` (por commit) **+** día real de proceso en `lifecycle-pg` del tag (al sellar).                                                      |
| Arranque       | **Agente nuevo** con este plan y el relevo; no se continúa la sesión de `v2.44`.                                                                                          |

## 1. Invariante que instala

> _El día completo (mercado → régimen → señales → ranking → decisión → reservas → orden → fills múltiples →
> posición → protección → T1 → trailing → salida → ledger → reconciliación → P&L → atribución → informe) se
> reproduce con **PostgreSQL real** y **proceso de scheduler real**, y **toda** oportunidad del día termina
> con un estado final y un motivo._

Corolario operativo: el informe del día debe ser **reconstruible desde la BD**, sin discrepancias de ledger y
con las decisiones **tomadas y no tomadas** atribuidas. «No tomada» con motivo tipificado, nunca en silencio.

## 2. Qué NO cambia (freeze)

- **`v2_43_governor_evidence.py` byte a byte igual y `exit 0`**, con su `"bump"` conservado en `1.68.0-beta`.
  Los ejes, la tabla, el gate y los umbrales del gobernador **no se tocan**.
- **Sin migración**: Alembic head `043`.
- **Byte-identidad con el flag OFF** (`AUTO_ENGINE_SIM_V2_OPTIMIZER=0`) ⇒ el camino V2 sigue siendo `v2.43.3`.
- **`AUTO-ENGINE_SIM_V2=0`** sigue siendo el comportamiento histórico (el camino legacy no se toca).
- **Los tags no se mueven**: `v2.44-beta` y anteriores quedan donde están; `v2.45-beta` será ref nueva.
- **Los gates PG** (`*_PG_REQUIRED`) y los ficheros PG en el `--ignore` de los jobs offline: un skip mudo
  **no** certifica.

## 3. Piezas (qué se extiende, no qué se reinventa)

### 3.1 El día real (capa de proceso) — **extender** `test_a9_scheduler_process_pg_zero_human.py`

El patrón ya está en el repo y **no se reinventa**: `subprocess.Popen([sys.executable, "-m",
"bolsa_api.workers.scheduler_worker"])` (líneas 520-525 y 757-770), gate
`AUTO_SCHEDULER_PROCESS_PG_REQUIRED` (línea 34), presupuestos declarados `_TIMEOUT_S = 90`,
`_STARTUP_GRACE_S = 120`, `_RESTART_WATCH_S = 20`, `_CLOSED_DAY_POLLS = 4`.

Lo nuevo es el **día dorado 2.0**: un fichero `apps/api-python/tests/test_golden_day_v2_*_pg.py` que conduce
el mismo proceso real sobre PostgreSQL real y certifica:

1. **3–10 señales** en el día (el rango del roadmap), con al menos **dos estrategias** distintas.
2. **Fills múltiples por orden** (no una trancha): `count(distinct venue_order_id)` y `fills > orders`.
3. **T1 parcial**, **trailing** posterior a T1 y **cierre por régimen** (`REGIME_EXIT`/`RISK_EXIT`), cada uno
   atribuido en el journal.
4. **Cierre de día con libro plano**: posiciones a cero y ningún fill en vuelo.
5. **Todos los `execution_events` en `APPLIED`** y **todo fill con su transacción en el ledger** (el gate que
   en `V2.40.3` habría nombrado el fallo en una línea).
6. **`Σ motivos de salida == exits`**: ningún cierre sin explicar.
7. **Atribución por estrategia** del día, agregada desde la BD.
8. **MAE/MFE por operación** (ya persistidos en `mfe_mae` del JSONB) **leídos desde la BD**.
9. **Coste de oportunidad de las rechazadas**: toda rechazada conserva su motivo y su **precio posterior**
   cuando el dato existe; si falta, **se declara** (`unmeasured`), no se inventa.

Aviso de coste: el job `lifecycle-pg` del tag ya corre dos suites de proceso real (líneas 564-580). Un día de
3–10 señales con fills múltiples **alarga el job**; el presupuesto debe declararse (los `_*_S` de arriba) y el
test debe **fallar de forma informativa**, no quedarse minutos esperando.

### 3.2 El embudo (capa hermética) — **extender** `auto_daily_journal.py`

`AutoDailyReport` (líneas 69-122) hoy tiene `orders`, `fills`, `positions_created`, `exits`, `exit_reasons`,
`atr_sources`, `ledger_balance_status`, `errors`, `healthy`. Falta todo lo de §3.1 puntos 7-9. Los campos
nuevos son **aditivos** y con la **disciplina de medición del repo**: un agregado que no se puede medir se
declara (`UNKNOWN`/`PARTIAL` + `notes`), **jamás** se publica como `0`.

El invariante del embudo, hermético y por commit:

```
seen == traded + rejected + expired + missed      # y cada rechazo con motivo tipificado
```

Gate: extender el día hermético existente
(`apps/api-python/tests/test_auto_v2_golden_day_evidence.py`, 288 líneas) o su gemelo en
`packages/py/application/tests/` para el agregado puro. **La lista de `quality` es explícita**: un fichero
nuevo en `packages/py/application/tests` hay que **registrarlo** o no corre.

### 3.3 Identidad de estrategia en el journal (sin migración)

El journal durable es `DecisionJournalEntryRow`
(`packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py:720-739`):
`(id, decision_id, session_id, account_id, instrument_id, event_type, actor, payload JSONB, created_at)`, **sin
columna de estrategia**. La identidad entra como **clave aditiva del `payload`** (mismo patrón que `AUTO-2` y
la `043` con el JSONB). La atribución del día se agrega desde ahí y desde las tablas `sim_*`, y la maquinaria
de atribución **ya existente** (`packages/py/application/tests/test_sim_strategy_attribution.py`, certificada
por commit en `lifecycle-pg`) **se reutiliza, no se duplica**.

### 3.4 Reason codes (aditivos)

Los motivos del embudo y de la atribución van a `auto_reason_codes.py` (la **casa única** del journal). Un
motivo nuevo **no** puede reutilizar un texto existente que signifique otra cosa: en `v2.44` la lección fue
que journalizar `edge_below_threshold` para una candidata no elegida por el optimizador habría sido **falso**.

## 4. Gate (lo que mide el roadmap §7)

| Capa             | Dónde                        | Fichero                                                       | Gate                                |
| ---------------- | ---------------------------- | ------------------------------------------------------------- | ----------------------------------- |
| Hermética (tick) | `quality` de `python-ci.yml` | embudo del día (3.2)                                          | sin gate PG (no toca la BD)         |
| **Real (PG)**    | `lifecycle-pg` del **tag**   | `test_golden_day_v2_*_pg.py` (proceso real, sin `run_tick()`) | `fail-if-skipped` + guard anti-skip |

Requisitos de cableado (un fichero nuevo **no entra solo**):

- Añadirlo a la lista del job `lifecycle-pg` del tag (junto a las líneas 564-580).
- Añadirlo a los **`--ignore`** de los jobs offline (`quality` de `python-ci.yml`, líneas 183-212; job
  `python` del tag). Comentario **fuera** del bloque plegado (trampa medida en V2.40.2) y `set -o pipefail`.
- Guard anti-skip en el job (log no vacío + `grep` de `skipped`), como ya hace `auto-v2-durable-pg`.
- **Sin `run_tick()` manual**: el día lo conduce el proceso.

## 5. Criterios de salida

1. **Informe de día reconstruible desde la BD**, sin discrepancias de ledger (`BALANCED`), y `healthy`.
2. **Todas las decisiones atribuidas**: `seen == traded + rejected + expired + missed`, con motivo en cada
   rechazo y con el **precio posterior** de la rechazada cuando el dato existe (declarado si falta).
3. **`Σ exit_reasons == exits`** y **todos los `execution_events` en `APPLIED`** con su transacción.
4. **Ambas capas en verde en CI real**, con las cifras citadas **del run que las produjo**.
5. **Matriz de mutaciones medida**: cada invariante nuevo debe tener su mutación que ponga la suite en rojo
   (patrón de `apps/api-python/scripts/v2_44_mutation_audit.py`: script de auditoría de mutaciones **propio de
   la fase, a crear**, con la huella del árbol intacta antes y después de medir).

## 6. Límites previstos (declarar, no maquillar)

1. **Sin productor de economía en el tick**: el día real **no** lleva el optimizador ON con economía real
   (`p_win`/medias son de `AUTO-7`). La evidencia «ON ≠ ranking» sigue siendo de **capa de test**.
2. **MAE/MFE: se recogen, no se calibran.** Calibrar stop/T1/T2/trailing/tiempo con ellos es `AUTO-7`.
3. **Coste de oportunidad: se recoge, no se decide con él.** Ninguna regla se relaja por esta medición.
4. **Correlación de hoy, no matriz por pares** (heredado de `AUTO-4`).
5. **Presupuesto de tiempo del job del tag**: el día real alarga `lifecycle-pg`; el coste se declara medido.
6. **La identidad de estrategia viaja en `payload` JSONB**: consultable, pero **no** indexada. Si el informe
   del día exigiera reconstrucción por SQL a gran escala, eso sería una migración **de otra fase**, declarada.

## 7. Estado de ejecución (2026-09-20) — lo implementado, con sus desviaciones

**PENDIENTE.** Se rellena al ejecutar la fase, por el agente que la implemente: qué se hizo, qué se
midió (con el **run** de CI de cada cifra), qué se desvió del plan y qué límite se **confirmó** al medir.

## 8. Verificación (a rellenar con artefactos)

Cada cifra del informe final debe citar **el artefacto que la produjo** (aprendizaje declarado de `v2.44` §5:
una cifra atribuida al instrumento equivocado es un defecto de honestidad, no un redondeo).
