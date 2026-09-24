# Traspaso de relevo — `AUTO-16` **CERRADA** (`V2.57` / `1.82.0-beta`)

**Fecha:** 2026-09-24 · **Rama:** `main` en **fast-forward** · **Tag:** `v2.57-beta` ·
**Fase anterior:** `AUTO-15` (tag `v2.56-beta` → `8ad54416`) · **Commit de partida del paquete:** `3081ed78`.

**Documentos de la fase:** [plan](./plan-v2-57-auto-16-coste-real-por-ciclo-2026-09-24.md) ·
[audit-pack](./audit-pack-v2-57-auto-16-coste-real-por-ciclo-2026-09-24.md) ·
[arranque del auditor](./arranque-auditor-v2.57-auto-16-coste-real-por-ciclo-2026-09-24.md) ·
[arranque del agente siguiente](./arranque-agente-post-v2.57-auto-16-2026-09-24.md).

---

## 0. Qué está ratificado y qué se ejecutó

El propietario ratificó la opción **C · Coste REAL por ciclo** y el plan **«tal cual»**, incluidas sus
dos decisiones abiertas:

1. **Qué se persiste por fill:** **solo la referencia cruda** (`reference_mid`). Una fuente de verdad;
   la fricción se computa pura. (Descartado: persistir también la fricción aplicada.)
2. **Qué base usa el R neto cuando el aplicado falta:** el **estimado, declarado**. El camino sin
   referencia publica **el mismo número que `v2.56`** byte a byte y la diferencia viaja en la base.

Los cinco pasos del plan se ejecutaron en orden, cada uno con su gate. **Una desviación declarada**
(§2) y **un defecto medido y corregido dentro de la fase** (§5).

---

## 1. Estado medido del repo (2026-09-24)

| Hecho | Valor medido |
| --- | --- |
| Alembic head | `045_adaptive_gate_state` → **`046_fill_reference_mid`** (en el árbol; el tag lo certifica) |
| Guardia `_ALEMBIC_HEAD` | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` = **`046_fill_reference_mid`** |
| Sello del reparto | `ADAPTIVE_POLICY_VERSION = "auto16-v1"` (`auto_adaptive.py:175`) |
| Sello del gate | `DATA_GATE_POLICY_VERSION = "auto15-v1"` (**intacto**) |
| Compuertas | ruff **`All checks passed!`** · mypy **`0` en `499` ficheros** · import-linter **`4 kept, 0 broken`** |
| Tramo de la fase | **`105 passed`** (`+5` PG) en las cinco suites de la fase, `0` rojos |
| Matriz de mutaciones | **`M1…M128`** — ver §5 (medida en la fase) |
| Freeze | `auto_adaptive_journal.py` y `v2_43_governor_evidence.py`: **diff vacío**; `governor.json` sin trackear |
| Flag Adaptive | **OFF** (sin plan, sin lectura de la referencia, sin encogimiento) |

---

## 2. Lo ya HECHO y verificado (Pasos 1 a 5)

### Paso 1 — Migración `046` + columna ORM + el campo en el modelo/store

- `046_fill_reference_mid.py`: `revision`/`down_revision` (`:38`/`:39`), `op.add_column`
  `reference_mid Numeric(18,6) NULL` (`:71`), `downgrade` simétrico (`:85`), idempotente.
- `tables.py:2248`: la columna `reference_mid` en `SimFillFinanceContextRow`.
- `SimFillFinanceContext.reference_mid` (`sim_durable_store.py:106`) con **normalización y validación**
  (`usable_reference_mid`, `:64`): un valor que no describe un precio es **ausencia**, nunca `0`.
- Lector por ciclo `list_by_cycle_ids` en los dos stores (`:300` memoria, `:581` PG) y `save` del PG
  escribiendo la columna (`:447`).
- **Guardia de head bumpeada `045` → `046` en el MISMO paso** (la lección del re-sello de `v2.56`).

### Paso 2 — Módulo puro `applied_cost` + la referencia en el settlement

- `applied_cost.py`: `applied_leg` (`:157`, signo por dirección y magnitud —un coste, nunca una
  rebaja—), `_cycle_applied_cost` (`:200`, exige **ida y vuelta**), `applied_cost_from_fills` (`:244`),
  `applied_cost_is_complete` (`:274`), vocabulario de notas (`without_reference`, `favourable_leg`,
  `without_round_trip`).
- `sim_finance_context.persist_fill_finance_context(reference_mid=...)` (`:45`/`:61`/`:78`) y
  `simulated_settlement.py:331` (`reference_mid=base_mid`): la referencia viaja en la escritura del
  settlement **que ya existía**.

**Desviación declarada del plan:** el plan decía «persistencia… gateado por el flag». La
implementación **persiste siempre** (es la MISMA escritura, sin I/O nuevo) y lo que el flag gatea es
su **uso**. Gatear la escritura por el flag dejaría un hueco **permanente** en el histórico el día que
se encienda la lectura. Queda escrito en el audit-pack §3.

### Paso 3 — La base declarada: `CycleRisk.cost_applied`, el punto único y `cycle_r`

- `cycle_risk.py`: `cost_applied` + `cost_applied_measurement` (`:145`/`:157`), `to_cycle_fields`
  publicando `costApplied` **con su medición** (`:161`) y el pegador puro `attach_applied_cost`
  (`:348`) —**solo un aplicado `COMPLETE` se pega**: un `PARTIAL` es un SUELO y no entra al neto—.
- `auto_self_evaluation_feed.py:214` (`_risk_with_applied_cost`, el **único** punto por el que pasan
  informe `AUTO-7`, confianza `AUTO-12` y rampa `AUTO-13`): **sin I/O nuevo** (los fills ya leídos
  llevan su referencia).
- `auto_self_evaluation.py`: bases (`:130`/`:132`), la comisión del MODELO (`:195`), `cycle_r` con la
  base declarada (`:435`), `CycleR.cost_applied`/`cost_basis` (`:416`/`:420`), `_net_r_basis` (`:1124`)
  y `netRBasis` en las dos filas (`:768`/`:839`).
- Sello: `ADAPTIVE_POLICY_VERSION = "auto16-v1"` (`auto_adaptive.py:175`). **La regla no se toca**;
  cambia la **procedencia de un input** del eje del R neto.

### Paso 4 — La costura (con CONTROL) y la certificación PG

- `test_auto_v57_auto16_applied_cost_seam.py` (**9** tests): el neto del plan sale del aplicado
  (`1.16` vs el `1.09` del estimado); **control negativo** sin `reference_mid` ⇒ el número de `v2.56`
  byte a byte; **control de composición** sin comisión ⇒ no se compone a medias; la pata de otro tick
  se compone; el aplicado **mueve los pesos**; y **cero I/O nuevo** (2 lecturas por versión, 0 por
  ciclo).
- `test_auto_v57_auto16_applied_cost_pg.py` (**5** tests, job `auto-v2-durable-pg` con
  `APPLIED_COST_PG_REQUIRED=1`): roundtrip de la `046`, **reinicio real**, fila legacy declarada,
  cuenta ajena fuera.

### Paso 5 — Cierre: mutaciones, compuertas, delta, docs, bump y sello

- **Paso 5 — Cierre: mutaciones, compuertas, delta, docs, bump y sello.** Compuertas §3 verdes; delta
  simétrico con **9 rojos declarados** y solo ésos; `M119…M128` muerden y la **matriz completa** da
  **`128/128`** (con un **realineo declarado** de `M32`); paquete de docs, bump `1.82.0-beta` y tag
  `v2.57-beta` (`c5e14ae1`). **El CI del tag salió GREEN a la primera**
  ([`35968175990`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35968175990), `10 success` + `1
  skipped`, job `python` del tag **`2649 passed / 35 skipped`**) y el `Python CI` per-commit cerró
  **`5/5`** jobs (los cuatro de PG incluidos) — **no hubo re-sello**, porque la guardia de head se
  bumpeó en el paso 1 (§11 del audit-pack).

---

## 3. Anclas de código (verificadas sobre el árbol que se sella)

| Qué | Dónde |
| --- | --- |
| Migración `046` | `packages/py/infrastructure/alembic/versions/046_fill_reference_mid.py:38` |
| Columna ORM | `packages/py/infrastructure/src/bolsa_infrastructure/database/models/tables.py:2248` |
| Normalización del mid | `packages/py/application/src/bolsa_application/sim_durable_store.py:64` |
| Campo del contexto | `.../sim_durable_store.py:106` |
| Escritura del mid en el settlement | `.../simulated_settlement.py:331` |
| Persistencia en el contexto | `.../sim_finance_context.py:61` / `:78` |
| Lector por ciclo (memoria / PG) | `.../sim_durable_store.py:300` / `:581` |
| Fricción de una pata | `.../applied_cost.py:157` |
| Agregado por ciclo | `.../applied_cost.py:200` |
| Agregado de todos los ciclos pedidos | `.../applied_cost.py:244` |
| `CycleRisk.cost_applied` + medición | `.../cycle_risk.py:145` / `:157` |
| Pegador puro | `.../cycle_risk.py:348` |
| Punto único de la alimentación | `.../auto_self_evaluation_feed.py:214` |
| Comisión del modelo | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_self_evaluation.py:195` |
| `cycle_r` (cociente + base) | `.../auto_self_evaluation.py:435` |
| Base del agregado | `.../auto_self_evaluation.py:1124` |
| Sello del reparto | `.../auto_adaptive.py:175` |
| Guardia de head de Alembic | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` |
| Bloque de la sonda (`M119…M128`) | `apps/api-python/scripts/v2_44_mutation_audit.py` (`MUTATIONS`) |

---

## 4. El método de verificación del repo (no improvisar)

1. **Compuertas con el comando de CI** (no rutas sueltas): `ruff check packages/py apps/api-python
   --config pyproject.toml`, el `mypy` exacto del YAML y `lint-imports --config packages/py/.importlinter`.
2. **pytest con `uv run --no-sync python -m pytest`**: en esta máquina `uv run pytest` lo bloquea la
   directiva de Control de aplicaciones (`os error 4551`).
3. **Sonda de mutaciones**: mide, restaura **byte a byte** y verifica la huella `git status`. Filtro
   por etiqueta para verificar un tramo (`... M119 M120 …`).
4. **Delta simétrico fichero a fichero**: se corre **la versión de `HEAD`** de cada test modificado
   contra el árbol de la fase (nunca se restan totales).
5. **Los tests PG exigen PostgreSQL real** levantado (compose local); con el puerto cerrado la sonda
   usa un DSN *fast-fail*.

---

## 5. El cierre, hecho y medido

- **Compuertas:** `ruff` limpio, `mypy` **`0` en `499` ficheros** (`+1`: el módulo puro),
  `import-linter` **`4 kept, 0 broken`**.
- **Tramo de la fase:** `test_applied_cost.py` (9) + `test_sim_fill_reference.py` (9) +
  `test_auto_v57_auto16_applied_cost_seam.py` (9) + `test_auto_self_evaluation.py` (45) +
  `test_cycle_risk.py` (33) ⇒ **`105 passed`**, `0` rojos; `+5` PG contra el PostgreSQL del compose.
- **Delta simétrico:** **9 rojos declarados** y solo ésos — **4** por el **sello** (`auto16-v1` en
  `test_auto_adaptive.py` ×2, `test_auto_v53` ×1, `test_auto_v54` ×1) y **5** por la **guardia de head**
  de Alembic (`test_discovery_evidence_snapshot_pg.py`, solo en los jobs PG). **Un defecto medido y
  corregido dentro de la fase:** el campo `netRBasis` se añadió **sin defecto** y produjo **76 rojos**
  más (`TypeError` al construir `StrategySelfEvaluation`); se corrigió a defecto `None` = «no
  declarada» y el delta quedó en los 9 declarados (pack §7).
- **Matriz COMPLETA `M1…M128`:** corrida entera, con el resultado en el audit-pack §7.

---

## 6. Límites declarados y freeze

- **La comisión aplicada no existe en SIM**: el neto aplicado se completa con la comisión **del
  modelo** y su base lo nombra. No se finge un coste realizado completo.
- **Sin backfill**: el histórico anterior a `2.57` no tiene referencia y lo **declara**.
- **Solo se persiste la referencia**, no la fricción (una fuente de verdad).
- **Freeze:** `auto_adaptive_journal.py` y el gobernador **intactos** (diff vacío); sin UI, sin SHORT,
  `*.md` sin `prettier`; `governor.json` sigue sin trackear.

---

## 7. Punto de entrada para el siguiente agente

El [arranque del agente post `v2.57`](./arranque-agente-post-v2.57-auto-16-2026-09-24.md) trae el
prompt listo, las anclas re-medidas y los candidatos declarados (**no decididos**) para `AUTO-17`. La
fase está **cerrada**: lo que falta es la decisión del propietario, no trabajo pendiente.
