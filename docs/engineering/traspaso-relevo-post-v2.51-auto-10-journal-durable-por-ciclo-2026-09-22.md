# Traspaso de relevo - post `V2.51` (`AUTO-10` Journal durable por ciclo)

**Fase:** `AUTO-10` (`V2.51` / `1.76.0-beta`) · **Fecha:** 2026-09-22 · **Fase anterior:** `V2.50` (`AUTO-9`).
**Documentos de la fase:** [audit-pack](./audit-pack-v2.51-auto-10-journal-durable-por-ciclo-2026-09-22.md)
· [plan](./plan-v2-51-auto-10-journal-durable-por-ciclo-2026-09-22.md).
**Rótulo ratificado por el propietario:** `AUTO-10` sobre `V2.51` / `1.76.0-beta`.

---

## 0. Posición en la línea AUTO

`v2.48` = `AUTO-8` (Adaptive AUTO, slice 1) · `v2.49` = `AUTO-8.1` (Adaptive correcto, explícito y
reproducible) · `v2.50` = `AUTO-9` (Strategy × Regime y net expectancy_R) · **`v2.51` = `AUTO-10`
(Journal durable por ciclo)**: el hueco de régimen que `AUTO-9` **declaraba** (`regime_not_durable`) deja
de existir porque el ciclo lo publica en `decision_journal_entries` y el lector lo recupera
**confirmando** el payload. **Sin migración** (Alembic head sigue en `044_auto_cycle_trace`).

---

## 1. Qué quedó HECHO y medido en esta fase

1. **Contrato puro** `auto_cycle_journal.py`: `cycle_decision_id()` (derivación por intercambio de
   prefijo `cyc-`↔`dec-`, sobre el **índice ya existente**) y `build_auto_cycle_regime_entry()`
   (`cycleId` + `marketRegime` + `regimeMeasurement` + `cycleIdDerived`; `None` sin identidad).
2. **Puerto de escritura en el worker**, en la **apertura** del ciclo y **después** de commitear el
   capital (`_v2_journal_cycle_regime` desde `_v2_persist_tick_reservations`); sink inyectable y su
   **cableado real** en `run_tick` (`build_cycle_regime_sink(session)`: `append` + **`commit`**, y
   `rollback` + re-lanzar en el fallo).
3. **Lector** `auto_cycle_regime_reader.py`: pregunta por el `decision_id` **derivado** y **confirma**
   `payload['cycleId']` + `event_type`; tres huecos separados (`unconfirmed`/`absent`/`not_derivable`);
   tandas de `500`.
4. **`list_by_decision_ids`** en `SqlAlchemyJournalRepository` (por el índice existente, `created_at
   DESC`).
5. **El hueco de `cycle_risk` se parte en dos**: `regime_not_durable` (no se consultó fuente durable) y
   **`regime_not_found`** (se consultó y no está).
6. **Dedupe declarado**: gana la **confirmación** más nueva (no la fila más nueva), `duplicates` +
   `collapsedRows` visibles, y el worker lo declara sin gritar (`info` si solo hay duplicados).
7. **Verificación**: `quality` **2321 → 2368** y job `python` del tag **2329 → 2376** (**+47** simétrico,
   **0 rojos**; base medida con la misma extracción en `HEAD`, no restada de extracciones antiguas);
   `mypy` **0/494**; `import-linter` **4/4**; `ruff` limpio; PG (`AUTO_V2_DURABLE_PG_REQUIRED=1`)
   **14 passed**; **41/41** mutaciones muerden con árbol intacto.
8. **Test que muerde el circuito completo** con PG real: escritura en un turno → lectura desde **otra
   sesión** (`test_auto_cycle_regime_trace_is_durable_and_readable_from_another_session`), verificado que
   **falla** al desconectar el sink de `run_tick`.

---

## 2. Límites declarados (no silenciosos)

- **Solo ciclos del worker `AUTO`**: los ciclos históricos ya cerrados sin entrada durable siguen
  declarando su hueco. `AUTO-10` **no** reescribe el pasado (no hay backfill).
- **`netExpectancyR` necesita además su propia cadena**: que el régimen sea durable cierra el **insumo**
  del eje `strategy × regime`; que el número aparezca depende de que existan ciclos **medidos con coste**.
- **Coste del lector a escala: no medido.** A este volumen (1348 filas) la tanda del lector cuesta
  **0,082–0,086 ms** y el planner recorre la tabla; el punto en el que cambiaría a índice no está medido.
  Si el spine crece, la decisión es un índice parcial o de expresión — **nunca** cambiar la identidad del
  ciclo.
- **Cooldown en memoria** (heredado de `v2.49`): se reinicia con el proceso.
- **Sin UI** para `AUTO-7`/`AUTO-8`/`AUTO-9`/`AUTO-10`.
- **`governor.json` sigue sin trackear.**

---

## 3. Trampas del entorno medidas (para no repetirlas)

1. **Un fragmento de mutación que ya no existe es una mutación que NO mide.** `M25`, `M26` y `M33`
   llevaban desde `df2002e7` sin aplicar (reformateo) y la sonda **seguía**: el `33/33` de `v2.50` era
   sobrestimado (**aplicaban 30/33**). La sonda **ahora falla** si un fragmento no existe. Lección de
   método: **cada etiqueta dice en qué test muerde; si no muerde, la matriz tiene que doler**, no seguir.
2. **La base de un delta se mide, no se hereda.** Las cifras publicadas de `v2.50` (`2287`/`2298`)
   salieron de una lista de targets **distinta** (50 frentes); restarlas de las de hoy daría un número
   inventado. Para el delta: `git stash -u`, correr la batería en `HEAD`, `git stash pop`.
3. **Un PG sin `--ignore` en el YAML corre en local y se salta en CI.** En CI el job `python` no tiene
   PostgreSQL; en local, con `DATABASE_URL` apuntando a la base de desarrollo, esos ficheros **sí**
   corren y pueden fallar por **orden** (`test_simulated_finance_pg.py`). Aislado pasa; se declara.
4. **`*.md` fuera de `prettier`** y `tools/fix_md_spacing.py` como reparador determinista (decisión del
   tramo de tooling de `v2.50`); `prettier` **no** está en ningún workflow de CI, así que la exclusión no
   cambia ninguna compuerta.
5. **No usar `git push --follow-tags`** con tags locales antiguos: más de tres tags en un push **no**
   disparan los workflows de tag en GitHub.

---

## 4. Qué mirar primero si hay que auditar esta fase

1. **El invariante**: `packages/py/application/src/bolsa_application/auto_cycle_journal.py` (derivación
   del `decision_id`, `None` sin identidad, `regimeMeasurement` declarado) y
   `auto_cycle_regime_reader.py` (confirmación de payload y los **tres** huecos).
2. **El orden del efecto**: en `auto_simulation_worker.py`, `_v2_persist_tick_reservations` (primero el
   capital) y `_v2_journal_cycle_regime` (después la traza); el `commit` del sink real en `run_tick`.
3. **La partición del hueco** en `cycle_risk.py` (`regime_not_durable` vs `regime_not_found`).
4. **La frontera del dedupe**: `test_the_newest_CONFIRMING_row_wins_over_a_newer_window_entry` (gana la
   confirmación más nueva) y `test_an_unusable_row_of_more_is_declared_as_gap_not_as_duplicate`.
5. **La matriz**: `apps/api-python/scripts/v2_44_mutation_audit.py` (`M34…M41` y la guarda dura de
   fragmento ausente), y las **enmiendas** al `33/33` de `v2.50` en su plan, su audit-pack, el relevo
   anterior (`post-v2.50`) y `PROJECT_STATE`.

**Siguiente fase natural:** `AUTO-11` — la **UI de `AUTO-7`/`AUTO-8`/`AUTO-9`/`AUTO-10`** (el cruce
`strategy × regime` y la evidencia Adaptativa ya existen y **no** se ven) y/o el **cooldown durable**;
ambas siguen declaradas como deuda, sin migración decidida todavía.
