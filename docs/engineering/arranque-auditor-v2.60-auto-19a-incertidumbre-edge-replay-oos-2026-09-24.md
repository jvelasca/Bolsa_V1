# Arranque del auditor — `v2.60-beta` (AUTO-19A · Incertidumbre del edge + Replay OOS)

**Qué se te pide:** revisar el delta de `V2.60`/`AUTO-19A` **contra su invariante**, no contra el estilo.
Todo lo que sigue está **medido sobre el árbol sellado**; lo que **no** se pudo medir aquí está declarado
como tal (y se dice qué lo cierra). Documentos de la fase: [plan](./plan-v2-60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md) ·
[audit-pack](./audit-pack-v2-60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md) ·
[relevo](./traspaso-relevo-post-v2.60-auto-19a-incertidumbre-edge-replay-oos-2026-09-24.md).

Antes de empezar: `git status`, `git log --oneline -5`, la head de Alembic
(`046_fill_reference_mid`) y la guardia de head
(`apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43`).

---

## 0. Si solo tienes una hora

1. **El invariante** (§1) y sus **seis corolarios**: la independencia se mide una sola vez, la ausencia se
   declara, el intervalo contiene su punto, el eje del EDGE es propio, el replay no inventa veredictos, la
   lectura es aditiva.
2. **El sello NO se mueve** (§4): `auto18-v1`; esto es **medición**, no reparto. `confidence` (medición) y
   `edgeConfidence` (edge) son **dos ejes** y van en campos separados.
3. **La costura con CONTROL** (§5): sin `uncertainty` el plan es **byte-idéntico**; con ella, el reparto y la
   rotación son **exactamente** los mismos.
4. **El delta simétrico** (pack §7) y la **matriz `M1…M158`** (pack §6): `158/158` muerden, **0** realineos,
   restauración **byte a byte** y huella `git status` idéntica.
5. **El replay es un INSTRUMENTO, no una decisión** (§6): pregunta, mide, y **declara inconcluso** cuando no
   tiene los dos grupos. El fixture por defecto es **sintético** (mide el instrumento, no la estrategia).

---

## 1. El invariante (ataca contra él, no contra el estilo)

> **Ninguna lectura de edge se publica como certeza ni como permiso.** La expectancy se publica con su
> **intervalo de incertidumbre**; la confianza de MEDICIÓN (`confidence`) se separa de la confianza de EDGE
> (`edgeConfidence`); y ninguna de las dos mueve el reparto (que sigue siendo `auto18-v1`).

Seis corolarios, con test y con mutación que los mata:

1. **La independencia se mide una sola vez.** El material sale de `regime_episodes`
   (`auto_adaptive_confidence.py:434`): `M149` (remuestrear ciclos) cae en
   `test_one_single_regime_phase_does_not_fabricate_an_interval`.
2. **La ausencia no es un defecto, pero se declara.** `no_cycles` / `insufficient_episodes`; `M153`.
3. **El intervalo contiene a su punto** por construcción (`auto_adaptive_uncertainty.py:357-358`): se
   **ensancha**, no se contradice.
4. **El eje del EDGE es propio** (`_edge_confidence`, `:375`): base por el **signo del intervalo**, con
   degradaciones a la baja (suelo `LOW`) y notas declaradas; `M151`, `M152`.
5. **El replay no inventa veredictos** (`REPLAY_*`, `auto_adaptive_replay.py:91-107`): `sample` declarado y
   `inconclusive` sin los dos grupos; `M155`, `M156`, `M157`.
6. **La lectura es ADITIVA** (`auto_adaptive.py:869`, `:909`): sin `uncertainty` nada cambia; `M158`.

**La compatibilidad es parte del invariante:** `StrategyHealth.expectancy_interval`/`edge_confidence`
tienen defecto `None`; el frame `uncertainty` del plan y las dos claves de la evidencia **solo** aparecen
con lectura; el journal durable queda byte a byte igual.

---

## 2. Sin migración: qué se declara

- **`_ALEMBIC_HEAD` sigue en `046_fill_reference_mid`**: el intervalo y el replay son **recomputables** del
  material ya medido; no hay columna, ni tabla, ni backfill.
- **La evidencia entra como claves ADITIVAS** en `evidence_for`; el **journal durable** no las proyecta
  (lista blanca `riskMultipliers` + `evidenceAxis`), así que el contrato de `AUTO-11` no cambia.
- **Sin clave nueva en la API** ni en los DTO.

---

## 3. Los dos módulos puros nuevos

| Punto | `ruta:línea` |
| --- | --- |
| `bootstrap_episodes_v1` + clamp del nivel + semilla | `auto_adaptive_uncertainty.py:94` / `:99` / `:107` |
| `min_episodes` / `percentile` / `ExpectancyInterval` | `auto_adaptive_uncertainty.py:111` / `:155` / `:175` |
| Bandas y notas de EDGE | `auto_adaptive_uncertainty.py:119-141` |
| `_interval_from_episodes` / `_edge_confidence` | `auto_adaptive_uncertainty.py:295` / `:375` |
| `_cell_uncertainty` / `_strategy_uncertainty` / fachada | `auto_adaptive_uncertainty.py:438` / `:477` / `:554` |
| `statistical_oos_v1` + fracción OOS + mínimos | `auto_adaptive_replay.py:91` / `:95` / `:101` |
| `_compare` / `ReplayCell` / `ReplayQuestion` / `ReplayReport` | `auto_adaptive_replay.py:137` / `:147` / `:205` / `:225` |
| `_build_cell` (split IS/OOS) | `auto_adaptive_replay.py:290` |
| Las cuatro preguntas / fachada | `auto_adaptive_replay.py:401`…`:501` / `:539` |
| Lectores promovidos a público (AUTO-18, sin cambio de semántica) | `auto_adaptive_confidence.py:407` / `:417` / `:422` / `:434` / `:503` |

- **`effective_n` y `episodes` no cambian de significado**: el intervalo usa el MISMO material y la MISMA
  noción de independencia que el peso. Si una celda no tiene racha propia, **no** se le presta la de otra.
- **`_edge_confidence` es pura** y recibe la banda de la celda (`RegimeConfidence`) como modulador; sin
  lectura de confianza, `coverage` se clasifica con la convención de `AUTO-18` y `decay`/`basis` quedan
  `UNKNOWN` (**no** se inventan).

---

## 4. El sello y la frontera de ejes

- `ADAPTIVE_POLICY_VERSION = "auto18-v1"` (`auto_adaptive.py:203`) **intacto**: esta fase **no** cambia
  ninguna condición del reparto. `DATA_GATE_POLICY_VERSION` sigue `auto15-v1`.
- **`confidence` ≠ `edgeConfidence`**: `confidence` dice **qué bien se midió** (banda de `AUTO-12`/
  `AUTO-18`); `edgeConfidence` dice **qué probable es que haya edge** (signo del intervalo frente a cero).
  `HIGH`/`LOW`/`UNKNOWN` de cada eje **no** se implican entre sí; por eso van en campos separados y no
  comparten vocabulario en el caso ausente.
- **`UNKNOWN` no es un nivel**: es una ausencia. Con medición, el suelo es `LOW`.

---

## 5. La costura (con CONTROL)

- **Costura hermética** (`apps/api-python/tests/test_auto_v60_auto19_uncertainty_seam.py`, por el camino
  **real** del worker, con lector de régimen inyectado): el plan lleva el frame `uncertainty` con
  `method=bootstrap_episodes_v1`, el intervalo con `episodes=12` (12 ciclos alternando regímenes = 12
  rachas) y `lower ≤ point ≤ upper`; la evidencia gana las dos claves **sin** perder ninguna histórica.
- **Control** de la ausencia: **sin** lector de régimen (un solo tramo) hay punto pero **no** intervalo
  (`insufficient_episodes`) y el edge es **`UNKNOWN`** — nunca un `LOW` fabricado.
- **Control del sello**: `_v2_adaptive_policy().policy_version == "auto18-v1"`.
- **Freeze byte a byte**: `auto_adaptive_journal.py` y `v2_43_governor_evidence.py` con diff **vacío**.
- **Byte-identidad**: en `test_auto_adaptive.py`, sin `uncertainty` el plan **no gana ninguna clave** y con
  ella el `allocation`/`rotation` son **los mismos**.
- **Batería pre-tag medida con la selección EXACTA del CI**: **`2774 passed`**, `0` rojos, **`94.98 s`**.
- **Lo que sigue sin poder medirse aquí:** las suites que exigen **PostgreSQL real** en local (las PG
  `--ignore`adas, `apps/api-python/tests/integration` y `chaos/live_a7`; importan `asyncpg`, ausente en
  esta máquina). Las **cerró** la CI del tag: el `Release tag CI`
  [`35999631671`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35999631671) salió **GREEN a la
  primera** (`10 success` + `1 skipped`, `certify` en `success`, **sin flakes**) y los `Python CI`
  per-commit del tag y de `main` quedaron **`5/5` verdes** (los cuatro jobs PG incluidos). Esta fase **no**
  añade tests PG (sin migración), así que esos jobs corren el **mismo** material que `v2.59` y certifican
  que `AUTO-19A` no rompió ninguno.

---

## 6. El replay: cómo se audita (y cómo NO)

- **Es un instrumento de MEDICIÓN**, no de decisión: su salida **no** mueve pesos, ni sizing, ni el reparto.
- **Reproduce el fixture** antes de opinar:

```bash
uv run --no-sync python scripts/research/auto_replay_battery.py
```

  Sobre el fixture **sintético**: `shrinkage=supported`, `effective_n=supported`,
  `high_confidence=not_supported`, `coverage=inconclusive`. **Que una pregunta refute y otra se declare
  inconclusa es la prueba de que no es un sello de goma.**
- **No le pidas un veredicto que la muestra no sostiene**: sin los dos grupos, `inconclusive` es la
  respuesta correcta, no un hueco pendiente.
- **El fixture es SINTÉTICO**: mide el instrumento. Un veredicto sobre la estrategia real exige material
  durable, y eso está fuera de esta fase.

---

## 7. Comandos exactos (no los reinventes)

```bash
# Estático (los de CI, no rutas sueltas)
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync lint-imports --config packages/py/.importlinter

# El gobernador NO se movió: diff VACÍO
git diff -- apps/api-python/scripts/v2_43_governor_evidence.py

# El contrato durable NO se movió: diff VACÍO
git diff -- packages/py/application/src/bolsa_application/auto_adaptive_journal.py

# La guardia de head NO cambió (la head sigue en 046)
rg -n "_ALEMBIC_HEAD" apps/api-python/tests/test_discovery_evidence_snapshot_pg.py

# El tramo de la fase (unit + costura hermética)
uv run --no-sync python -m pytest packages/py/analytics/tests/test_auto_adaptive_uncertainty.py packages/py/analytics/tests/test_auto_adaptive_replay.py packages/py/analytics/tests/test_auto_adaptive.py packages/py/analytics/tests/test_auto_adaptive_confidence.py packages/py/application/tests/test_auto_self_evaluation_feed.py apps/api-python/tests/test_auto_v60_auto19_uncertainty_seam.py apps/api-python/tests/test_auto_v59_auto18_confidence_seam.py apps/api-python/tests/test_auto_v53_auto12_confidence_seam.py apps/api-python/tests/test_auto_v54_auto13_recovery_seam.py apps/api-python/tests/test_auto_v54_auto13_data_gate_wiring_seam.py apps/api-python/tests/test_auto_v55_auto14_regime_cell_allocation_seam.py apps/api-python/tests/test_auto_v57_auto16_applied_cost_seam.py -q

# El instrumento del replay (fixture sintético)
uv run --no-sync python scripts/research/auto_replay_battery.py

# La matriz de mutaciones (mide, restaura byte a byte y verifica la huella del árbol)
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py
```

- **Batería pre-tag completa, con la selección EXACTA del CI** (`2774 passed`, `0` rojos): copia la línea
  `pytest` literal del job `quality` de `.github/workflows/python-ci.yml` y cámbiale el prefijo
  `uv run pytest` por `uv run --no-sync python -m pytest` (en esta máquina `uv run pytest` lo bloquea el
  Control de aplicaciones). Lo único que queda fuera es lo que exige **PostgreSQL real**.

---

## 8. Qué NO es un hallazgo (declarado de antemano)

- **El intervalo por episodios es una COTA conservadora.** Que 180 ciclos de un solo régimen cuenten como
  **1** racha (sin intervalo) es el diseño ratificado, no un defecto.
- **`dispersion_r` no es un error estándar.** Es la desviación de las medias bootstrap: sirve para comparar
  estabilidad, no como intervalo.
- **`confidence` no se renombró.** Es contrato JSON sellado; el eje nuevo va en campos nuevos.
- **El fixture del replay es sintético.** Sus veredictos miden el instrumento; el veredicto real es del
  material durable y puede ser `inconclusive`.
- **El replay no re-simula órdenes.** Es estadístico por decisión ratificada del propietario (sin Postgres).
- **`UNCERTAINTY`/`edgeConfidence` en el journal:** no viajan al journal durable (lista blanca de
  `AUTO-11`), y eso es **aditividad declarada**, no un olvido.
- **El CI del sello se mide DESPUÉS de sellar, no antes.** Las cifras viven en el `audit-pack` **§11**
  (añadido en el commit de docs posterior al sello, mismo patrón que `AUTO-13`…`AUTO-18`).
- **El flag Adaptive sigue OFF.** Sin él no hay plan ni lectura.
- **Sin UI, sin SHORT, sin backfill.**

---

## 9. Preguntas abiertas que el autor NO cierra

1. El bootstrap remuestrea **rachas enteras**; con rachas de tamaño muy distinto, ¿debería ponderarse por
   tamaño (block bootstrap de bloques fijos) o el percentil por rachas ya es la cota correcta?
2. ¿Debería el replay validar también la **degradación del `edgeConfidence`** (es decir, si las bandas que
   bajan por cobertura/deterioro predicen peor OOS), o eso pertenece a `AUTO-20` junto con la correlación?
3. El `dispersion_r` se publica como punto; con pocas rachas, ¿debería declararse también su propia
   incertidumbre?
4. La **caducidad** de una racha durable vieja (cola de `AUTO-15`) sigue sin existir.

---

## 10. Lo que **no** debes asumir

- Que el flag está ON: **está OFF**, y con él nada de esto corre en producción.
- Que `edgeConfidence = HIGH` implica confianza de medición alta: son **dos ejes distintos**.
- Que un intervalo estrecho implica edge: un intervalo estrecho con punto negativo es **`LOW`** (sabemos
  que no hay edge), y eso también es información.
- Que el replay "valida la estrategia": hoy valida el **instrumento** sobre un fixture sintético.
- Que los tests verdes locales cubren los jobs PG: los jobs PG necesitan PostgreSQL real.

---

## 11. Formato del hallazgo

Para cada hallazgo: **(a)** el invariante que se rompe, **(b)** el fichero y la línea, **(c)** el caso
mínimo que lo reproduce, **(d)** si hay un test que debería haberlo cazado y no lo hizo (y por qué),
**(e)** la mutación (`M…`) que debería cubrirlo si es del alcance de la sonda. Un hallazgo sin caso
mínimo es una opinión.
