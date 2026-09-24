# Arranque del agente — post `v2.60-beta` (`AUTO-19A` cerrada) · 2026-09-24

**Rama `main`** en fast-forward · **Tag `v2.60-beta`** · **`1.85.0-beta`** · **Fase anterior cerrada:**
`V2.60` / `AUTO-19A` «Incertidumbre del edge + Replay OOS».

---

## 0. El prompt para arrancar (cópialo tal cual)

> Trabajas en `Bolsa_V1` (repo del propietario). **No improvises el método**: el repo tiene un
> protocolo y se sigue. Antes de tocar nada:
>
> 1. Lee `docs/engineering/traspaso-relevo-post-v2.60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md`
>    (estado medido y anclas) y el `audit-pack-v2-60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md`
>    (qué se midió, qué no y por qué).
> 2. Comprueba el estado real del árbol (`git status`, `git log --oneline -5`, la head de Alembic y
>    `_ALEMBIC_HEAD`) **antes** de proponer nada. No des por hecho el estado de este documento.
> 3. Ejecuta las compuertas con **el comando de CI** (`ruff check packages/py apps/api-python --config
>    pyproject.toml`; el `mypy` exacto del YAML; `lint-imports --config packages/py/.importlinter`).
>    En esta máquina los tests se corren con `uv run --no-sync python -m pytest` (`uv run pytest` lo
>    bloquea la directiva de Control de aplicaciones).
> 4. Propón **una** opción de `AUTO-20` con su invariante, su superficie, su migración (¿sí o no?) y su
>    gate; **no la implementes** hasta que el propietario la ratifique.
> 5. Respeta el freeze del §4. Nada de UI, SHORT ni backfill sin ratificación explícita.

---

## 1. Estado en una tabla

| Qué | Dónde / valor |
| --- | --- |
| Árbol | limpio salvo los cambios de la fase (o `main` ya en el tag) |
| Alembic head | `046_fill_reference_mid` (sin cambio: AUTO-19A no migra) |
| Guardia de head | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` |
| Sello del reparto | `ADAPTIVE_POLICY_VERSION = "auto18-v1"` (`auto_adaptive.py:203`) — **no se movió** |
| Sello del gate | `DATA_GATE_POLICY_VERSION = "auto15-v1"` (intacto) |
| Tramo de la fase | `271 passed` |
| Batería pre-tag (CI exacto) | `2774 passed`, `0` rojos, `94.98 s` |
| Delta simétrico | `144 passed`, `0` rojos (aditiva) |
| Matriz | `M1…M158` (audit-pack §6) |
| Flag Adaptive | **OFF** |

---

## 2. Dónde está cada cosa (anclas re-medidas sobre el árbol sellado)

- **Incertidumbre (nuevo):** `auto_adaptive_uncertainty.py:94` (`bootstrap_episodes_v1`), `:99`
  (nivel), `:107` (semilla), `:111` (`min_episodes`), `:155` (`percentile`), `:175` (`ExpectancyInterval`),
  `:119-141` (bandas/notas de EDGE), `:295` (`_interval_from_episodes`), `:375` (`_edge_confidence`),
  `:438`/`:477`/`:554` (celda/estrategia/fachada).
- **Lectores públicos promovidos:** `auto_adaptive_confidence.py:407` (`measured_r`), `:417` (`regime_of`),
  `:422` (`order_cycles_by_instant`), `:434` (`regime_episodes`), `:503` (`coverage_band`).
- **Replay (nuevo):** `auto_adaptive_replay.py:91` (sello del método), `:95`/`:101` (clamp y mínimos),
  `:137` (`_compare`), `:147`/`:205`/`:225` (celdas/preguntas/informe), `:290` (`_build_cell`),
  `:401`…`:501` (las cuatro preguntas), `:539` (fachada).
- **CLI + fixture:** `scripts/research/auto_replay_battery.py` ·
  `packages/py/analytics/tests/fixtures/auto_replay_cycles.json`.
- **Cableado:** `auto_adaptive.py:460`/`:464` (campos), `:869` (evidencia), `:909` (frame `uncertainty`),
  `:203` (sello); `auto_self_evaluation_feed.py:326`; `auto_simulation_worker.py:3104`/`:3165`.
- **Sonda de mutaciones:** `apps/api-python/scripts/v2_44_mutation_audit.py` (bloque `AUTO-19A`,
  `M149…M158`).

---

## 3. El método (no se improvisa)

- **Ratificación antes de implementar.** El propietario ratifica la opción y el plan; el agente no decide
  alcance.
- **Un paso, un gate.** Cada paso se mide antes de pasar al siguiente.
- **Nada se afirma sin medirlo.** Los documentos citan cifras medidas y declaran lo que **no** se pudo
  medir (y qué límite lo cierra).
- **Los rojos se declaran.** Un delta simétrico con rojos previstos se publica tal cual; en esta fase el
  delta fue **cero rojos** porque la fase es aditiva, y así se publica.
- **Los `*.md` no pasan por `prettier`** (el repo lo declara). `governor.json` sigue sin trackear.

---

## 4. Freeze (no se toca sin ratificación)

- `auto_adaptive_journal.py` **byte a byte** (contrato durable de `AUTO-11`).
- `v2_43_governor_evidence.py` y el gobernador.
- `ADAPTIVE_POLICY_VERSION` (**`auto18-v1`**), `DATA_GATE_POLICY_VERSION` (**`auto15-v1`**),
  `ADAPTIVE_ADVERSE_REGIMES`, umbrales de rotación y la tabla estado→efecto del gate.
- Sin UI, sin SHORT, sin backfill. `governor.json` sin trackear.

---

## 5. Qué queda abierto (candidatos de `AUTO-20`, NO decididos)

1. **Correlación entre estrategias** (el bloque que `AUTO-19A` dejó fuera por ratificación explícita):
   dos versiones con edge propio pueden ser el MISMO edge.
2. **Validar la degradación del `edgeConfidence`** en el propio replay (¿las bandas que bajan por
   cobertura/deterioro predicen peor OOS?).
3. **Caducidad declarada** de una racha durable vieja (cola de `AUTO-15`).
4. **Bootstrap por bloques de tamaño fijo** si las rachas son muy desiguales (hoy se remuestrean rachas
   enteras, cota conservadora declarada).
5. La **primera toma de decisión con el flag ON** (hoy OFF: nada de esto corre en producción).
