# Arranque del auditor — `v2.57-beta` (AUTO-16 · Coste REAL por ciclo)

**Qué se te pide:** revisar el delta de `V2.57`/`AUTO-16` **contra su invariante**, no contra el estilo.
Todo lo que sigue está **medido sobre el árbol sellado**; lo que **no** se pudo medir aquí está
declarado como tal (y se dice qué lo cierra). Superficie de revisión: el PR draft **#66**
(`auto-16-coste-real-por-ciclo` → `audit-base-v2.56-beta`).

Antes de empezar: `git status`, `git log --oneline -5`, la head de Alembic
(`046_fill_reference_mid`) y la guardia de head
(`apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43`).

---

## 0. Si solo tienes una hora

1. **El invariante** (§1) y las **cinco reglas duras**: base publicada con el número, aplicado +
   comisión del modelo, `PARTIAL` no entra, sin referencia ≠ `0`, la fricción nunca es una rebaja.
2. **La migración** (§2): una columna `NULL`able, sin backfill, `downgrade` simétrico.
3. **La costura con CONTROL** (§5): sin `reference_mid`, el neto es **el número de `v2.56` byte a
   byte**; con ella, sale del aplicado. Si el control no existiera, «el aplicado llegó» también
   pasaría con un modelo de coste que midiera cualquier cosa.
4. **El delta simétrico** (pack §7): **9 rojos declarados** — el sello y la guardia de head—, y el
   defecto del campo sin defecto que se midió y se corrigió **dentro** de la fase.

---

## 1. El invariante (ataca contra él, no contra el estilo)

> **El R neto declara su BASE.** El coste que descuenta el cociente puede venir del **decisor**
> (estimado) o del **simulador** (aplicado, medido contra el mid de referencia). Dos netos con el
> mismo aspecto y distinta base **no son comparables**: si la base no viaja con el número, un cambio de
> procedencia se lee como un cambio de rendimiento — y este neto es el eje con el que `AUTO-12`/`13`/`14`
> encogen, rampean y **reparten capital**.

Cinco corolarios, con test y con mutación que los mata:

1. **La base se publica.** `costBasis` por ciclo y `netRBasis` por agregado
   (`applied_friction+modelled_commission`/`estimated`/`mixed`/`undeclared`).
2. **El aplicado se completa con la comisión del MODELO y la base lo nombra.** El schedule del
   simulador **no cobra comisión**; restar solo la fricción haría el neto **más alto** sin que la
   ejecución haya mejorado. Sin comisión cuantificada, **no se compone a medias**: se vuelve al
   estimado completo.
3. **Un `PARTIAL` es un SUELO y no entra.** Media ida y vuelta (o una pata sin referencia) restaría de
   menos y **sobrestimaría** el R.
4. **Sin referencia no hay fricción, y jamás es `0`.** Un `0` diría «fricción gratis».
5. **La fricción es un COSTE, nunca una rebaja.** El monto es la magnitud del desvío; una pata
   favorable se **declara** (`applied_cost_favourable_leg`) en vez de restar.

**La compatibilidad es parte del invariante:** un log viejo y un consumidor viejo siguen leyéndose
(`costEstimate` se publica igual), el campo nuevo de las filas del informe tiene defecto seguro
(`None` = «no declarada»), y el camino sin referencia publica **el número de `v2.56` byte a byte**.

---

## 2. La migración: qué se escribe y qué **no**

`046_fill_reference_mid` añade **una** columna (`Numeric(18,6)`, `NULL`able) a
`sim_fill_finance_context`. **No** hay tabla nueva, **no** hay backfill, **no** hay clave nueva en el
journal y **no** se toca ningún contrato de API/DTO.

- **Idempotente** y con `downgrade` **simétrico** — el test PG corre `upgrade`/`downgrade`/`upgrade`
  contra PostgreSQL real.
- **La guardia de head se bumpeó en el mismo paso** (`045` → `046`), que es exactamente el rojo que
  obligó a **re-sellar** `v2.56`. Si encuentras una ruta que lea la head sin pasar por esa constante,
  eso **sí** es un hallazgo.
- **Pregunta incómoda:** ¿puede llegar a la tabla un `reference_mid = 0` (que diría «fricción
  gratis»)? La normalización está en `sim_durable_store.py:64` y la muerden `M123`/`M126`.

---

## 3. El punto único: la fricción aplicada **sin I/O nuevo**

| Punto | `ruta:línea` |
| --- | --- |
| Fricción de UNA pata | `applied_cost.py:157` |
| Agregado por ciclo (exige ida y vuelta) | `applied_cost.py:200` (`round_trip` en `:220`) |
| Una entrada por ciclo pedido (con sus huecos) | `applied_cost.py:244` |
| Predicado del `COMPLETE` | `applied_cost.py:274` |
| **Único** pegador a la evidencia | `auto_self_evaluation_feed.py:214` |
| Escritura del mid (misma escritura de siempre) | `simulated_settlement.py:331` |
| Lector por ciclo (verificación, **no** en el tick) | `sim_durable_store.py:300` / `:581` |

- **Un solo productor.** Si aparece un segundo sitio que calcule la fricción aplicada, los tres
  consumidores (informe, confianza, rampa) podrían medir costes distintos en silencio: **es hallazgo**.
- **Cero I/O nuevo, medido** (`version_reads == 2`, `cycle_reads == 0`). Con el flag **OFF**, el
  constructor del plan no se invoca.
- **Desviación declarada del plan (no un hallazgo, salvo que midas lo contrario):** la referencia se
  persiste **siempre** (en la escritura del settlement que ya existía); lo que el flag gatea es su
  **uso**. El plan decía «gateado por el flag» y la medida dice esto, con el motivo: gatear la
  escritura dejaría un hueco **permanente** en el histórico.

---

## 4. La declaración y el sello (medir ≠ publicar de más)

- El sello del reparto sube a **`auto16-v1`** (`auto_adaptive.py:175`): **no** cambia la regla
  (ninguna condición de `_allocation_weights` se toca), cambia la **procedencia de un input** del eje
  del R neto. El sello del gate (`auto15-v1`) **no** se toca.
- **El sello SÍ se compara** (vive en el journal del reparto): las filas históricas quedan marcadas como
  de otra política. Está declarado y medido en la costura.
- **`netRBasis` no es un permiso.** `decisive` sigue exigiendo el R **bruto** medido; quien decida con
  el neto debe exigir `netRMeasurement == COMPLETE` **y** mirar la base.

---

## 5. La costura del reinicio (con CONTROL) y la certificación PG

- **Costura hermética** (`test_auto_v57_auto16_applied_cost_seam.py`, 9 tests, por el camino **real**
  del worker) con **dos controles**:
  1. **Sin `reference_mid`** (el MISMO material): el neto es el estimado de `v2.56` **byte a byte**.
  2. **Sin comisión cuantificada**: el neto **no** se compone a medias (vuelve al estimado) y la
     medición aplicada se sigue publicando.
- **PG real** (`test_auto_v57_auto16_applied_cost_pg.py`, 5 tests, `APPLIED_COST_PG_REQUIRED=1`):
  roundtrip de la `046`, `reference_mid` **sobreviviente a una sesión nueva**, fricción **recompuesta
  fuera del proceso** que la midió, fila legacy declarada sin fricción (jamás `0`) y lectura por ciclo
  que **no cruza cuentas**.
- **Lo que NO se pudo medir aquí:** los runs de CI (no existen hasta empujar el tag) y la batería
  offline de los jobs `quality`/`python` del tag (recolectan suites PG que importan `asyncpg`, ausente
  en esta máquina). Ese límite lo cierra la CI del tag y el pack lo cita con su run (pack §11).

---

## 6. Mutaciones que YA se midieron (no las redisculpas)

`M119…M128` muerden **todas** (pack §6) y la matriz **completa** `M1…M128` está corrida con **0**
etiquetas en `NADA`, **0** fragmentos ausentes y restauración **byte a byte**. Si crees que una
mutación **no** muerde, reproduce su corrida antes de reportarlo: la sonda imprime, para cada etiqueta,
los tests que se pusieron rojos **por nombre**.

---

## 7. Comandos exactos (no los reinventes)

```bash
# Estático (los de CI, no rutas sueltas)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# El gobernador NO se movió: diff VACÍO
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py

# El contrato durable NO se movió: diff VACÍO
git diff -- packages/py/application/src/bolsa_application/auto_adaptive_journal.py

# La migración SÍ se movió
rg -n "revision = \"046" packages/py/infrastructure/alembic/versions/046_fill_reference_mid.py

# La GUARDIA de head también (esto fue el rojo del tag de v2.56):
rg -n "_ALEMBIC_HEAD" apps/api-python/tests/test_discovery_evidence_snapshot_pg.py

# La suite PG de la fase, contra el PostgreSQL del compose (~5 s)
APPLIED_COST_PG_REQUIRED=1 uv run --no-sync python -m pytest apps/api-python/tests/test_auto_v57_auto16_applied_cost_pg.py -q

# El tramo de la fase (unit + costura hermética; el PG va aparte)
uv run --no-sync python -m pytest packages/py/application/tests/test_applied_cost.py packages/py/application/tests/test_sim_fill_reference.py apps/api-python/tests/test_auto_v57_auto16_applied_cost_seam.py packages/py/analytics/tests/test_auto_self_evaluation.py packages/py/application/tests/test_cycle_risk.py -q

# La matriz de mutaciones (mide, restaura byte a byte y verifica la huella del árbol)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py
```

---

## 8. Qué NO es un hallazgo (declarado de antemano)

- **El aplicado se complete con la comisión del MODELO.** No existe comisión realizada en SIM; la base
  lo **nombra**, así que no finge un coste completo.
- **No hay backfill.** El histórico anterior a `2.57` no tiene referencia y se mide con el estimado
  **declarado**. Es un hueco honesto.
- **Solo se persiste la referencia**, no la fricción (una fuente de verdad).
- **La comisión del neto aplicado es la del modelo, no la del bróker.** Un bróker real cobraría otra (o
  ninguna): es otra fase y otra fuente.
- **El flag Adaptive sigue OFF.** Sin él no hay plan ni lectura.
- **Sin UI, sin SHORT, sin backfill.**

---

## 9. Preguntas abiertas que el autor NO cierra

1. ¿Debe el **sello del gate** (`DATA_GATE_POLICY_VERSION`, hoy `auto15-v1`) moverse cuando cambia la
   **base** del neto? Hoy no se mueve: el gate mide salud de datos, no procedencia de coste. Si crees
   que sí, argumenta contra qué invariante lo mide.
2. Un ciclo con **tres o más patas** mide su fricción sumando las patas medidas y exige las dos
   direcciones; **no** publica la composición (qué pata aportó qué). ¿Es suficiente para auditar la
   resta?
3. ¿Debe la fricción aplicada publicarse como **métrica agregada** del informe AUTO-7 (y no solo por
   ciclo)? Hoy viaja por ciclo (`costApplied` con su medición).
4. La **caducidad** de una racha durable vieja (cola de `AUTO-15`) sigue sin existir: hoy se cura en la
   primera publicación. Es un límite declarado, no un olvido.

---

## 10. Lo que **no** debes asumir

- Que el flag está ON: **está OFF**, y con él nada de esto corre en producción.
- Que el redondeo es libre: la fricción se cuantiza a 6 dp (`applied_cost.py`) y el neto se publica a 4
  (`_ratio`); el rastro está en el módulo puro.
- Que `costApplied` es un precio o un PnL: es un **coste** en moneda de la cuenta y **sin comisión**.
- Que los tests verdes locales cubren los jobs PG: los jobs PG necesitan PostgreSQL real.

---

## 11. Formato del hallazgo

Para cada hallazgo: **(a)** el invariante que se rompe, **(b)** el fichero y la línea, **(c)** el caso
mínimo que lo reproduce, **(d)** si hay un test que debería haberlo cazado y no lo hizo (y por qué),
**(e)** la mutación (`M…`) que debería cubrirlo si es del alcance de la sonda. Un hallazgo sin caso
mínimo es una opinión.
