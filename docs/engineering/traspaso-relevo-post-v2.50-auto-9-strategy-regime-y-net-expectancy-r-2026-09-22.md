# Traspaso de relevo — post `V2.50` (`AUTO-9` Strategy × Regime y net expectancy_R)

**Fecha:** 2026-09-22 · **Tag:** `v2.50-beta` (`1.75.0-beta`) · **Migración:** **NO** (Alembic head
`044_auto_cycle_trace`).
**Commit de código:** `df2002e7` (los **documentos de fase** van dentro del mismo tag) ·
**Tag anotado:** `v2.50-beta` → commit de documentos de `main` · **CI real:**
**10/10 `success`**, `Release tag CI`
[`35723747813`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35723747813) (2026-09-22).
**Pack de evidencia:**
[`audit-pack-v2.50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md`](./audit-pack-v2.50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md)
**Plan de la fase:**
[`plan-v2-50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md`](./plan-v2-50-auto-9-strategy-regime-y-net-expectancy-r-2026-09-22.md)

---

## 0. Posición en la línea AUTO

```
AUTO-6   Crash / Concurrent          ✅
AUTO-7   Self-Evaluation             ✅
AUTO-8   Adaptive Recommendation     ✅ (v2.48)
AUTO-8.1 Adaptive correcto/estable   ✅ (v2.49)
AUTO-9   Strategy x Regime y R neto  ✅ (v2.50 — esta fase)
AUTO-10  Adaptive production         ⏭️ siguiente
```

La regla de la línea sigue intacta: **la recomendación Adaptive solo estrecha; el motor determinista decide
y el gobernador manda.** Esta fase añade el dato que faltaba para que «estrechar» se pueda justificar con
**riesgo normalizado** en vez de con moneda bruta — y solo cuando ese dato está medido para todo el grupo.

---

## 1. Qué quedó HECHO y medido en esta fase

1. **El `r_multiple` por ciclo deja de ser `None` para siempre.** Productor read-only nuevo
   (`cycle_risk.py`) que ata por `cycle_id` el **denominador** (`portfolio_reservations.reserved_risk`) y
   el **coste estimado** (`cost`). Con eso el R pasa a ser un dato **medido** o un hueco **declarado**.
2. **Denominador único y declarado**: la reserva de ENTRADA más antigua con riesgo positivo; con varias
   candidatas se usa la más antigua y se declaran. Las reservas **liberadas cuentan** (si no, el
   denominador faltaría justo en los ciclos con resultado). Prohibido repartir el riesgo.
3. **Agregación `strategy × regime`** con `UNKNOWN` como cubo propio, `min_trades` por celda, dedupe de
   ciclos repetidos y orden canónico. `declared_regime` no elige régimen si hay dos celdas decisivas.
4. **Consumo en Adaptive con eje por POOL**: `net_expectancy_r` **solo** si está `COMPLETE` para todo el
   grupo que compite; si no, `expectancy_currency` (histórico). El eje se declara en el plan y en el journal.
5. **`adaptivePolicyVersion` → `auto9-v1`** y `net_expectancy_r` + `regime` mapeados en `StrategyHealth`.
6. **Fail-closed por degradación declarada**: lectura rota ⇒ informe con forma `AUTO-7`; lectura saturada ⇒
   esos ciclos sin denominador (nunca con el de otro) y `warning`. No se confunde «no pude leer» con «sin
   muestra».
7. **`list_by_cycle_ids`** en `ReservationStore` (Protocol + `InMemory` + `Postgres`), vivas y liberadas.
8. **Verificación**: `quality` **2287/2287** y tag **2298/2298** (delta **+69** simétrico, 0 rojos);
   **33/33** mutaciones muerden con árbol intacto; `mypy` **0/492**; `import-linter` **4/4**.

---

## 2. Límites declarados (no silenciosos)

- **El régimen por ciclo NO es durable hoy**, y esto es lo importante del relevo: el payload de la decisión
  sí lleva `cycleId` y las tres dimensiones del gobernador, y `decision_journal_entries` sí es durable —
  pero **ese** journal es el del camino `plan_v2_tick`. El worker que ejecuta el ciclo simulado
  (`auto_simulation_worker`) escribe su journal **en memoria** (`_v2_journal`), así que **no hay fila
  durable con `cycleId`** para los ciclos AUTO. Comprobado contra la base real. El plan §4.3 queda
  **corregido por escrito**.
- **Consecuencia**: `StrategyHealth.regime` solo se puebla si el cruce `strategy × regime` trae un régimen
  medido; hoy, sin régimen por ciclo, la celda es `UNKNOWN` y el sistema lo **declara** en vez de
  inventarlo. **`AUTO-10` está gated por esto**: sin régimen durable, el cruce existe pero está vacío.
- **Deuda con nombre (la siguiente pieza natural)**: hacer durable el journal del worker — que sus
  decisiones de ciclo lleguen a `decision_journal_entries` con `cycleId` y `marketRegime`. Es un cambio
  **del worker** (escritura), no del adaptador read-only, y **no** exige migración si se reutiliza la tabla
  del journal. Cuando exista, se rellenan `regime_by_cycle` (ya está la costura) y `portfolio_reservations`
  / `sim_fill_finance_context` empiezan a llevar `cycle_id` en lo nuevo, y el cruce se enciende solo.
- **Cooldown de pausa en memoria** (heredado de `v2.49`): se reinicia con el proceso.
- **Sin UI**: la evidencia solo es observable vía el informe (`byRegime`, `cyclesWithoutRegime`,
  `cyclesWithoutCost`) y el detalle del journal.

---

## 3. Trampas del entorno medidas (para no repetirlas)

1. **La sonda de mutaciones puede dejar el mutante dentro del árbol.** `M16` no pudo restaurar
   `auto_v2_entry.py` (`OSError [Errno 22]` de Windows, reproducible, con el árbol limpio) y dos corridas
   abortaron con `return best, ()` en el fichero. Ya está blindado: reintento con pausa, `os.replace` y
   `git checkout` **solo si el fichero está limpio** (si no, **aborta declarándolo**). Y admite **filtro por
   rótulo** para verificar un tramo.
2. **`ruff format` no es un invariante del repo.** La compuerta es `ruff check … --config pyproject.toml`;
   `ruff format` no está en ningún job. Formatear en masa reescribió **608 ficheros ajenos** (revertido con
   criterio exacto: 610 analizados, 597 ruido, 13 míos). **Usar `ruff format` solo sobre lo tocado.**
3. **Escribir muchos `.py` seguidos dispara `OSError [Errno 22]`** en esta máquina: toda restauración
   masiva va con reintento y `os.replace`.
4. **No usar `--follow-tags`** al sellar si hay tags locales antiguos: empujar el tag de la fase **de uno en
   uno** (medido en `v2.49`, aplicado aquí sin incidencias).

---

## 4. Qué mirar primero si hay que auditar esta fase

1. `packages/py/application/src/bolsa_application/cycle_risk.py` — las cuatro reglas duras y sus notas.
2. `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py` — `_allocation_weights` (`:495`)
   y el por qué del eje por POOL.
3. `packages/py/analytics/src/bolsa_analytics/cognitive/auto_self_evaluation.py` — `cycle_r` (`:353`),
   `aggregate_by_regime` (`:1150`), `declared_regime` (`:1193`).
4. `apps/api-python/src/bolsa_api/background/auto_simulation_worker.py` — `_v2_cycle_risk` (`:2814`) y el
   tope de lectura (`:230`).
5. Los dos ficheros de test nuevos: `test_cycle_risk.py` (21) y `test_auto_v50_auto9_cycle_risk_seam.py` (7).
