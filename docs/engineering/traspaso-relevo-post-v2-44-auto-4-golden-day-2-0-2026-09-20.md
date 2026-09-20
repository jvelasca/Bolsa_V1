# Traspaso de relevo — post `v2.44-beta` (AUTO-4 cerrado) → **AUTO-5** (Golden Day 2.0)

**Fecha:** 2026-09-20 · **Versión:** `1.69.0-beta` · **Tag:** `v2.44-beta` → `c95819c1` · **Migración:**
**ninguna** (Alembic head sigue en `043_exit_identity_and_kill_state`). Sello **verde**: commit de fase
`f692159d` (18 ficheros, `+2728/−2`), `Python CI` **5/5** en `main`
([`35510546044`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510546044); `quality` **2075 passed /
38 skipped**, `auto-v2-durable-pg` **43 passed / 0 skipped**) y en la ref del tag
([`35510840771`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510840771)); `Release tag CI`
([`35510840734`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510840734)) **GREEN** con `certify` en
`success` (job `python` offline **2086 passed / 35 skipped**, `lifecycle-pg` con **PG real** **148 + 45
passed**, `playwright (integrated E2E)` `skipped` por opt-in). Correcciones posteriores al sello en `main`:
`1dc93005` (evidencia de CI de la ref del tag) y `527739af` (**corrección de procedencia**: ver §6, trampa 1).

**Punto de entrada obligatorio:** el
[audit-pack-v2.44](./audit-pack-v2.44-auto-4-portfolio-optimizer-2026-09-20.md) (su §5 lleva la corrección de
procedencia), el [arranque del auditor](./arranque-auditor-v2.44-auto-4-portfolio-optimizer-2026-09-20.md) y
el [plan de fase](./plan-v2-44-auto-4-portfolio-optimizer-2026-09-20.md) (§7 = estado de ejecución y
desviaciones). Después, este documento y el **[plan de `AUTO-5`](./plan-v2-45-auto-5-golden-day-2-0-2026-09-20.md)**.

---

## 1. Estado en una frase

`AUTO-4` deja instalado que **el ranking ya no es la decisión**: con `AUTO_ENGINE_SIM_V2_OPTIMIZER=1` el
`top_n` es el tamaño del **conjunto candidato** y la cartera elige la combinación por **valor esperado
económico** sujeto a restricciones duras — y con el flag **OFF** (default) el camino V2 es **byte-idéntico**.
Lo que queda es **`AUTO-5`**: certificar el día **entero y real** (proceso de scheduler + PostgreSQL), con la
atribución de **todas** las decisiones (tomadas y no tomadas).

## 2. Lo que este ciclo deja instalado (y cómo se mide)

| Invariante                                                        | Dónde vive                                                                   | Cómo se mide                                                                         |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| El ranking **no** decide; decide la combinación                   | `packages/py/analytics/src/bolsa_analytics/cognitive/portfolio_optimizer.py` | `test_portfolio_optimizer.py` (12) + `test_auto_v4_optimizer_wiring.py` (8)          |
| Existe una magnitud **económica** (Expected R/€) y es fail-closed | `.../cognitive/expected_value.py`                                            | `test_expected_value.py` (12)                                                        |
| OFF ⇒ byte-identidad del camino V2                                | `apps/api-python/.../auto_v2_entry.py` (`optimizer_enabled`)                 | gate de cableado + `v2_44_mutation_audit.py` **M7**                                  |
| El HALT y la identidad de salida **sobreviven** al proceso        | `043_exit_identity_and_kill_state` + stores                                  | `test_auto_v44_exit_identity_pg.py` (job `auto-v2-durable-pg`, gate fail-if-skipped) |
| El fold del ledger ordena por **instante UTC**                    | `.../cognitive/position_ledger.py`                                           | `test_position_ledger.py` (23 casos)                                                 |
| Política **B** de fallo de reserva (intent de emergencia o nada)  | worker `_v2_reserve_exit`                                                    | `test_auto_v44_exit_crash_matrix.py` (C1–C4)                                         |

## 3. Qué queda abierto (deuda declarada, por orden de importancia para `AUTO-5`)

1. **NO existe productor de economía en el camino del tick.** `_v2_signals` **no** aporta `p_win` ni medias:
   el productor real es de `AUTO-7`. Con el flag **ON**, **todas** las candidatas son
   `optimizer_expected_value_unmeasured` y el tick **no opera** (fail-closed declarado y fijado en test). Con
   el flag OFF, la producción no cambia. **Consecuencia directa para `AUTO-5`: el día dorado real NO puede
   llevar el optimizador ON con economía real**; su evidencia ON ≠ ranking es de **capa de test** (así se
   declaró en el pack §7) hasta que `AUTO-7` traiga el productor.
2. **`max_drawdown_used_pct` no existe** como restricción numérica: el veto de drawdown entra como
   `new_risk_allowed` (y su negativa es una decisión **COMPLETA** de no operar).
3. **Correlación de hoy, no matriz por pares**: el optimizador usa `TradeContext.correlation`; la matriz por
   pares está asignada a fases posteriores.
4. **Umbrales declarados y no calibrados**: `max_combinations = 4096`, `max_positions = top_n`.
5. **Duplicidad declarada de gates**: el optimizador mide el encaje de **conjunto** sobre la foto **inicial**
   y el motor sigue siendo la autoridad final sobre lo **reservado**.
6. **Dos ficheros con normalización CRLF/LF pendiente** en el worktree
   (`arranque-auditor-v2-40-4-…`, `audit-pack-v2.40.4-…`): diff de contenido **vacío**. Se dejaron **fuera**
   de los commits de `v2.44` a propósito. Un `git add` descuidado mete ruido de 2 ficheros en el sello.

## 4. El terreno de `AUTO-5` (rutas verificadas en el árbol)

**Lo que ya existe y hay que EXTENDER, no reinventar:**

| Pieza                                 | Ruta                                                                                                     | Qué es hoy                                                                                                                                                                                                                                                          |
| ------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Evidencia del día (hermético, sin PG) | `apps/api-python/tests/test_auto_v2_golden_day_evidence.py` (288 líneas)                                 | 3 posiciones, 3 desenlaces (`time_exit`/`thesis_exit`/`structural_stop`), día `healthy`, libro plano. Usa **decider manual** y `worker.auto_turn()` (**tick manual**)                                                                                               |
| Informe del día                       | `packages/py/application/src/bolsa_application/auto_daily_journal.py` (`AutoDailyReport`, líneas 69-122) | `orders`, `fills`, `positions_created`, `exits`, `exit_reasons`, `atr_sources`, `ledger_balance_status`, `errors`, `healthy`. **NO** tiene atribución por estrategia, MAE/MFE ni coste de oportunidad                                                               |
| Proceso **real** del scheduler        | `apps/api-python/src/bolsa_api/workers/scheduler_worker.py`                                              | `python -m bolsa_api.workers.scheduler_worker`                                                                                                                                                                                                                      |
| Patrón de proceso real en test        | `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` (858 líneas)                          | `subprocess.Popen([sys.executable, "-m", "bolsa_api.workers.scheduler_worker"])` (líneas 520-525 y 757-770) con gate `AUTO_SCHEDULER_PROCESS_PG_REQUIRED` (línea 34); `_TIMEOUT_S = 90`, `_STARTUP_GRACE_S = 120`, `_RESTART_WATCH_S = 20`, `_CLOSED_DAY_POLLS = 4` |
| Atribución por estrategia (ya existe) | `packages/py/application/tests/test_sim_strategy_attribution.py`                                         | Certificada **por commit** en el job `lifecycle-pg` de `python-ci.yml` (líneas 259-266)                                                                                                                                                                             |
| MAE/MFE (ya se persiste)              | `auto_simulation_worker.py` (líneas 344-350, 3085-3093) → `mfe_mae` en el JSONB                          | Marca del tick: pico observado + MFE/MAE                                                                                                                                                                                                                            |
| Journal durable                       | `packages/py/infrastructure/.../models/tables.py:720-739` (`DecisionJournalEntryRow`)                    | `(id, decision_id, session_id, account_id, instrument_id, event_type, actor, payload JSONB, created_at)`: **no hay columna de estrategia**                                                                                                                          |

**El test de proceso real solo corre en el TAG** (`release-tag-ci.yml` → job `lifecycle-pg`, con
`AUTO_SCHEDULER_PROCESS_PG_REQUIRED: '1'` en la línea 471 y los ficheros en las líneas 564-580), **no** por
commit: `python-ci.yml` es el que certifica por push (`quality` hermético + `auto-v2-durable-pg` PG).

## 5. Cómo se mide `AUTO-5` (decidido por el dueño: **dos capas**)

1. **Capa hermética (por commit, job `quality` de `python-ci.yml`)**: el **embudo** del día —
   `seen == traded + rejected + expired + missed` — con cada rechazo tipificado y con su motivo. Sin PG, sin
   proceso. Es el gate que protege **cada push**.
2. **Capa real (al sellar, job `lifecycle-pg` de `release-tag-ci.yml`)**: `test_golden_day_v2_*_pg` con
   **proceso de scheduler real** y PostgreSQL real, **sin** `run_tick()` manual, con gate `fail-if-skipped`.
   Es la certificación del día entero.

Un fichero nuevo **no entra solo** en la red de CI: hay que añadirlo a las listas **y** a los `--ignore` de
los jobs offline (`quality` en `python-ci.yml`, líneas 183-212; job `python` del tag). Y el job del tag debe
llevar el **guard anti-skip** (log no vacío + `grep` de `skipped`, patrón ya usado en `auto-v2-durable-pg`).

## 6. Trampas medidas (no las repitas)

1. **No atribuyas una cifra al instrumento que no la produjo.** En `v2.44` el pack declaró `2075`/`2086` como
   medidos por los bloques offline locales y **no era cierto**: los bloques completos **no llegaron a
   término** en la máquina del autor (ver trampa 2). Los números eran correctos y los certificaba **CI real**;
   lo que estaba mal era **dónde**. Se corrigió de forma aditiva y declarada (`527739af`), y la ref sellada
   conserva la redacción original. Regla: **cada cifra cita el artefacto que la produjo**.
2. **PG local no está y no se queja**: el `connect` **no rechaza, expira** (un _timeout_ por test). Medido en
   `v2.44`: `test_account_isolation.py` **23 failed en 261,73 s** por `psycopg.errors.ConnectionTimeout`
   contra `localhost:5432`, y el bloque del tag **matado a los ~34 min**. Los ficheros PG van a `--ignore`
   (`--with-pg-ignores` del runner versionado) y **la durabilidad la certifica CI**.
3. **Mide con el runner del YAML, nunca con una copia a mano de la lista.** `scripts/verify/offline_ci_run_yaml.py`
   extrae el `run` **del YAML**, comprueba que cada ruta existe (una ruta inexistente es `exit 4`) y mide por
   **JUnit XML** (bajo `subprocess` en Windows el stdout de pytest llega truncado).
4. **YAML: los comentarios dentro de un `run: >` son texto del comando.** Ya provocaron un `quality` corriendo
   **936** tests (V2.40.2). Comentarios **fuera** del bloque y `set -o pipefail` en todo `... | tee log`.
5. **Procesos `python` huérfanos**: las corridas matadas dejan hijos vivos que falsean la siguiente medición.
   Mátalos antes de medir.
6. **El plugin local `pytest_winloop`** (workaround de la política de event loop en Windows) **no es del
   repo**: no se commitea.

## 7. Freeze (congelado, no tocar sin motivo)

- **`apps/api-python/scripts/v2_43_governor_evidence.py` byte a byte igual y `exit 0`**, con su `"bump"`
  conservado en `1.68.0-beta`. Cualquier diff ahí es un hallazgo.
- **Sin migración**: head `043`. `AUTO-5` **no** trae migración (decision del dueño: la identidad de
  estrategia entra como clave **aditiva** del `payload` JSONB, coherente con `AUTO-2`/`043`).
- **Byte-identidad con el flag OFF**: `AUTO_ENGINE_SIM_V2_OPTIMIZER=0` debe seguir siendo `v2.43.3`.
- **Los tags no se mueven**: `v2.44-beta` es una ref nueva y aditiva; `v2.43*` quedan donde están.
- **Los gates PG** (`*_PG_REQUIRED`) y los ficheros PG en el `--ignore` de los jobs offline: un skip mudo
  **no** certifica nada.

## 8. Checklist antes de tocar `AUTO-5`

```bash
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
             packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# el día hermético vigente + el informe del día + la atribución que ya existe
uv run pytest apps/api-python/tests/test_auto_v2_golden_day_evidence.py \
              packages/py/application/tests/test_auto_daily_journal.py \
              packages/py/application/tests/test_sim_strategy_attribution.py -q

# el gobernador NO se movió (debe salir vacío y exit 0)
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py
uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json; echo "exit=$?"

# bloques offline EXTRAÍDOS del YAML (baseline de v2.44: 2075 y 2086 con los tests nuevos)
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores
uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores
```

Con PG real **solo en CI**: `auto-v2-durable-pg` (por commit) y `lifecycle-pg` del tag (proceso real).

## 9. Decisiones del dueño ya tomadas para `AUTO-5`

1. **Migración: NINGUNA.** La identidad de estrategia entra como clave aditiva del `payload` JSONB del
   journal; `mfe_mae` ya vive en el JSONB de posición. Head `043` sin cambios.
2. **Gate en DOS CAPAS**: embudo hermético en `quality` (por commit) + día real de proceso en `lifecycle-pg`
   del tag (al sellar).
3. **Arranque con agente nuevo**, con este relevo + el plan de fase como punto de partida: no se continúa la
   sesión de `v2.44` (contexto agotado y `AUTO-5` es una fase de evidencia, no de refactor).

Next = **`AUTO-5` — Golden Day 2.0 (`V2.45` / `1.70.0-beta`)**, plan:
[`plan-v2-45-auto-5-golden-day-2-0-2026-09-20.md`](./plan-v2-45-auto-5-golden-day-2-0-2026-09-20.md).
