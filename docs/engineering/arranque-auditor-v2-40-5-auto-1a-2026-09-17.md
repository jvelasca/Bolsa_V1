# Arranque del auditor — V2.40.5 / AUTO-1A Position Materialization & Partial-Fill Integrity (`1.65.5-beta`)

> **Qué auditar:** el slice `V2.40.5/AUTO-1A`: la posición del AUTO pasa a ser **Σ fills `APPLIED`**
> (`POSITION = Σ APPLIED BUY − Σ APPLIED SELL`), el exit se dimensiona contra la posición **materializada**,
> la cola de un llenado parcial queda como **capital pendiente** (nunca posición ni realizado), la autoridad
> canónica tras un reinicio se reconstruye desde el ledger `APPLIED` y ningún skip de gestión queda mudo.
> **Sin migración** (Alembic head `041_unique_natural_keys`).
> **Qué commit auditar:** tag anotado **`v2.40.5-beta` → `d15f0a18`** (26 ficheros, `+3538/−120`).
> `main` está en `d15f0a18` + el commit **docs-only** de sellado que estás leyendo, que **no** forma parte
> del tag.
> **Estado de CI (sellado, medido con `gh`):** `Python CI` **GREEN** en `main` (run
> [`35194186488`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35194186488), 5/5) y `Release-tag CI`
> **GREEN** (run [`35194658271`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35194658271), 10 jobs
> requeridos + `certify`; `playwright (integrated E2E)` `skipped` por opt-in).
> **De dónde leer (orden recomendado, 15-30 min):**
>
> 1. **Este fichero** (alcance, mapa de artefactos, qué NO se afirma).
> 2. [`audit-pack-v2.40.5-auto-1a-position-materialization-2026-09-17.md`](./audit-pack-v2.40.5-auto-1a-position-materialization-2026-09-17.md) — matriz afirmación→código→test, mutaciones **medidas**, límites declarados y la evidencia de CI.
> 3. [`plan-v2-40-5-auto-1a-position-materialization-2026-09-17.md`](./plan-v2-40-5-auto-1a-position-materialization-2026-09-17.md) — plan de implementación (su **§8** es el arranque del auditor original).
> 4. [`traspaso-relevo-post-v2-40-5-auto-1a-2026-09-17.md`](./traspaso-relevo-post-v2-40-5-auto-1a-2026-09-17.md) — relevo autocontenido, causa raíz por consecuencia y deuda conocida (§3, incluidos los rojos **ajenos** al slice).
> 5. [`roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md) — roadmap por fases (`AUTO-1`…`AUTO-8`) con invariante, gate y criterio de salida por fase.
> 6. El tag: `git show --stat v2.40.5-beta` (código auditado) y `CHANGELOG.md` `[1.65.5-beta]`.

---

## 1. Qué afirma esta versión (y qué no)

**Afirma**

- La posición contabilizada es **Σ fills `APPLIED`**; lo pedido, lo llenado y lo materializado son tres
  números **distintos y auditables**.
- El exit **no puede** exceder la posición materializada (`applied_qty <= held`, con journal
  `exit_qty_over_position` si se violara).
- La cola de un llenado parcial queda como **capital reservado** (`fill_not_materialized`,
  `fill_partially_materialized`, `fill_unapplied`), nunca como posición ni como realizado.
- Un libro **no interpretable** no se descarta en silencio: baja el `measurement`
  (`COMPLETE`/`PARTIAL`/`UNKNOWN`) ⇒ aperturas vetadas y **salidas protectoras siempre permitidas**.
- Tras un reinicio con RAM vacía la autoridad se reconstruye desde Σ `APPLIED`; una proyección inflada se
  reescribe a la materializada (`REBUILT`); libro ilegible ⇒ `POSITION_PROJECTION_UNKNOWN`.
- Ningún skip de gestión de posición queda mudo (`auto_position_skip` con `attention="high"`).
- El bucle de la jornada completa con PG real cierra **30/30** (el antiguo «flake» era un bug de dinero).

**No afirma**

- Que exista un **ledger de reservas** explícito con `release`/`rollback`/`replay`: eso es `AUTO-1`
  (Portfolio Reservation Engine) y la cola en `RETRY` es, por ahora, **capital reservado sin liberación
  explícita**.
- Que exista el índice parcial `execution_events(account_id, status)`: no lo hay (deuda con migración
  asignada a `AUTO-1`).
- Que `CanonicalPositions` sea la fuente de verdad de **todos** los consumidores de posición: es la
  autoridad del worker; el barrido de riesgo/exposición/sizing es una **pregunta abierta** (§5.2).
- Que el `limit` de `list_applied` cubra la jornada real más larga medida (§5.3).
- Que `PositionLedger` persista: es un **read-model** sin tabla propia.

---

## 2. Las cinco consecuencias del P0 y su cierre

| Consecuencia medida (plan §2)                                                        | Cierre                                                               | Test que lo muerde                                                                         |
| ------------------------------------------------------------------------------------ | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `_settle` daba por aplicadas las `FillObservation` `RETRY` (contabilizaba lo pedido) | `_Settlement(applied, unapplied, requested_qty)` + modo `structural` | `test_auto_v2_partial_fills.py` (6 rojos con la mutación M1)                               |
| La posición / `PositionState` / T1 / stop / trailing usaban la pedida                | `auto_turn` usa `applied_qty` en todos esos caminos                  | idem                                                                                       |
| Un `SELL` podía exceder la posición real (100 sobre 73,5)                            | clamp `applied_qty <= held` ⇒ `exit_qty_over_position`               | `test_protective_exit_never_exceeds_the_applied_position` (M4)                             |
| Los `RETRY` entraban en `_v2_known_fill_ids` ⇒ desaparecían del libro de pendientes  | los no aplicados **no** son conocidos; el capital queda reservado    | `test_auto_v2_partial_fills.py` (M2), `test_execution_event.py`                            |
| El helper de equity sumaba **todas** las filas de contexto ⇒ «flake» del scheduler   | el helper filtra `APPLIED` (`applied_fill_equity.py`)                | `test_equity_realized_ignores_unapplied_fill_context` (M3; el bucle 30× **no** lo detecta) |

---

## 3. Dónde mirar el código (mapa mínimo)

| Pieza                                           | Fichero                                                                                                                                                                           |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Read-model de posición + medición + violaciones | `packages/py/analytics/src/bolsa_analytics/cognitive/position_ledger.py` (**nuevo**)                                                                                              |
| Lectura de fills `APPLIED` y autoridad canónica | `packages/py/application/src/bolsa_application/applied_fills.py` (**nuevo**)                                                                                                      |
| Settlement del worker (el P0)                   | `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` (`_settle`, `auto_turn`, `_record_applied_event`, `_compose_canonical_reader`, `_reconcile_before_trusting`) |
| Stores ampliados                                | `packages/py/application/src/bolsa_application/execution_event.py` (`list_applied`), `.../sim_durable_store.py` (`get_many`)                                                      |
| Gestión de posición y skips                     | `packages/py/application/src/bolsa_application/position_manager.py` (`manage_position_outcome`, `PositionManagerSkip`), `.../auto_investment_system.py` (`run_auto_cycle`)        |
| Reason codes / journal (dueño único)            | `packages/py/application/src/bolsa_application/auto_reason_codes.py`, `.../auto_daily_journal.py`                                                                                 |
| Helper de equity de las suites PG               | `apps/api-python/tests/applied_fill_equity.py` (helper compartido, **no** es un fichero de test)                                                                                  |
| Seam determinista del settlement                | `apps/api-python/tests/test_auto_v2_partial_fills.py`                                                                                                                             |

---

## 4. Cómo verificar (comandos listos)

```bash
# 1) Suites herméticas del slice (segundos)
uv run pytest packages/py/analytics/tests/test_position_ledger.py \
               packages/py/application/tests/test_applied_fills.py \
               packages/py/application/tests/test_execution_event.py \
               packages/py/application/tests/test_position_manager.py \
               packages/py/application/tests/test_auto_investment_system.py -q

# 2) Camino del worker (stores in-memory)
uv run pytest apps/api-python/tests/test_auto_v2_partial_fills.py \
               apps/api-python/tests/test_auto_simulation_worker.py -q

# 3) PG real (reinicio + jornada completa). El bucle ×30 es el que cierra el «flake».
AUTO_V2_DURABLE_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_v2_durable_pg.py -q
AUTO_SCHEDULER_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_auto_scheduler_real_pg_zero_human_intervention.py -q
AUTO_SCHEDULER_PROCESS_PG_REQUIRED=1 uv run pytest apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py -q
```

### Mutaciones sugeridas (deben poner suites en rojo)

1. Volver `applied_qty = exec_qty` (la pedida) ⇒ **6 rojos** en `test_auto_v2_partial_fills.py`.
2. Pasar también `settlement.unapplied` a `_record_applied_event` ⇒ **1 rojo** (la cola `RETRY`
   desaparece del libro de pendientes).
3. Quitar el filtro `APPLIED` del helper de equity ⇒ **1 rojo determinista**; en el bucle 30× de la
   jornada **no** se detecta (0/30) ⇒ hace falta el test determinista.
4. Quitar el clamp `applied_qty <= held` ⇒ **1 rojo**.
5. Devolver `None` en los skips de `manage_position_outcome` ⇒ **2 rojos**.

(Las cinco están **medidas**; el resultado exacto está en §3 del audit-pack.)

---

## 5. Preguntas abiertas que el auditor debería intentar romper

1. **¿El modo `structural` de `_settle` puede enmascarar un `RETRY` en un camino con `finance_applier`
   real?** Debe ser **no**: `structural` existe solo donde no hay dinero que mover. Ver su test y el
   camino real.
2. **¿`CanonicalPositions` se reutiliza como fuente de verdad en TODOS los consumidores de posición**
   (riesgo, exposición, sizing) **o queda alguno leyendo `_open`/`position_state`?** Es una pregunta
   declarada, **no** una afirmación de este pack: el barrido completo está pendiente.
3. **¿El `limit` de `list_applied` es suficiente con la jornada real más larga medida?** Agotarlo baja el
   `measurement` (no publica un libro plausible), pero no está medido contra la jornada más larga.
4. **¿Puede una fila `APPLIED` ilegible convertirse en una posición plausible?** Debe ser **no**: declara
   el hueco en el `measurement`.
5. **¿Una sobreventa aplicada puede fabricar un corto?** Debe ser **no**: es violación explícita
   (`oversell_above_position` / `oversell_without_position`).
6. **¿Puede una proyección inflada sobrevivir a un reinicio?** Debe ser **no**: se reescribe (`REBUILT`) y
   el libro ilegible veta aperturas sin bloquear salidas protectoras.
7. **¿La liberación del capital en `RETRY` existe?** **No** todavía: es la deuda que abre `AUTO-1`
   (Portfolio Reservation Engine) — el problema no se ha cerrado, se ha **declarado con nombre y número**.
8. **¿El antiguo «flake» del scheduler era realmente un flake?** **No**: era el test detectando que el
   helper de equity sumaba contexto de fills no aplicados. Corregido y cerrado (30/30). La frase
   «criterio: re-ejecutar el job» de `PROJECT_STATE` (entrada `v2.40.4`) queda **corregida**.
