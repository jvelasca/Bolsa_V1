# Traspaso de relevo — `AUTO-17` **CERRADA** (`V2.58` / `1.83.0-beta`)

**Fecha:** 2026-09-24 · **Rama:** `main` en **fast-forward** · **Tag:** `v2.58-beta` ·
**Fase anterior:** `AUTO-16` (tag `v2.57-beta` → `c5e14ae1`) · **Commit de partida del paquete:** `7b664fb6`.

**Documentos de la fase:** [plan](./plan-v2-58-auto-17-integridad-poblacion-medida-2026-09-24.md) ·
[audit-pack](./audit-pack-v2-58-auto-17-integridad-poblacion-medida-2026-09-24.md) ·
[arranque del auditor](./arranque-auditor-v2.58-auto-17-integridad-poblacion-medida-2026-09-24.md) ·
[arranque del agente siguiente](./arranque-agente-post-v2.58-auto-17-2026-09-24.md).

---

## 0. Qué está ratificado y qué se ejecutó

El propietario ratificó **AUTO-17 completo** con **Opción A (dos series separadas)**: pre-2.57 =
`estimated`, post-2.57 = `applied`, **nunca** se promedian; el detector `basis_transition` evita leer el
cambio de base como señal. Core backend, **sin UI**, **sin tocar el gobernador**, **sin SHORT**, **sin
migración** y **sin backfill**.

Los cinco pasos del plan se ejecutaron en orden, cada uno con su gate. **Tres realineos declarados** de la
sonda (`M32`, `M122`, `M125`) y **un realineo adicional** de `M128`, todos publicados (§5).

---

## 1. Estado medido del repo (2026-09-24)

| Hecho | Valor medido |
| --- | --- |
| Alembic head | **`046_fill_reference_mid`** (sin cambio: AUTO-17 no migra) |
| Guardia `_ALEMBIC_HEAD` | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` = **`046_fill_reference_mid`** |
| Sello del reparto | `ADAPTIVE_POLICY_VERSION = "auto17-v1"` (`auto_adaptive.py:188`) |
| Sello del gate | `DATA_GATE_POLICY_VERSION = "auto15-v1"` (**intacto**) |
| Compuertas | ruff **`All checks passed!`** · mypy **`0` errores** · import-linter **`4 kept, 0 broken`** |
| Tramo de la fase | **`245 passed`** en las ocho suites tocadas, `0` rojos |
| Matriz de mutaciones | **`M1…M138`** (`138/138` muerden) — ver §5 |
| Freeze | `auto_adaptive_journal.py` y `v2_43_governor_evidence.py`: **diff vacío**; `governor.json` sin trackear |
| Flag Adaptive | **OFF** (sin plan, sin lectura, sin encogimiento) |

---

## 2. Lo ya HECHO y verificado (Pasos 0 a 5)

### Paso 0 — Documentar la verificación del CI del tag (solo docs)

- El pack de `v2.57` (§11.7) y este arranque declaran la medición real: `check-runs` de `c5e14ae1` =
  **`37`** y `Release tag CI` run
  [`35968175990`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35968175990) = **`success`**; el
  `statuses: []` que vio el auditor es la API **legacy de Commit Status**, no un check ausente.
- El `downgrade` de `046` se declara **DESTRUCTIVE DATA DOWNGRADE** en su docstring y en el pack.

### Paso 1 — Round-trip cuantitativo en `applied_cost` (P1)

- `applied_cost.py`: `AppliedLeg.quantity` (`:121`), `applied_leg` conserva la cantidad aunque falte el
  mid (`:175`), `_quantity_balanced` (`:222`), notas `APPLIED_COST_UNBALANCED_ROUND_TRIP` (`:75`) y
  `APPLIED_COST_WITHOUT_CYCLE_CLOSURE` (`:79`). El agregado (`:266`/`:267`) exige **lados + balance**.
- `applied_cost_from_fills(..., closed_cycle_ids=...)`: un ciclo pedido fuera del conjunto cerrado declara
  su hueco (`:340`), **nunca** un `0`.
- `auto_self_evaluation_feed.py`: `_cycles_with_risk` (`:246`) calcula `cycles_from_fills` **una sola vez**
  y pasa los `closed_cycle_ids`; informe, confianza y rampa cuelgan del mismo material (`:285`/`:310`/`:404`).

### Paso 2 — `net_r_basis` de extremo a extremo con DOS SERIES

- `auto_self_evaluation.py`: `NetRBasisSeries` (`:689`), campo `net_r_series` en las dos filas
  (`:755`/`:853`), `_net_r_series` (`:1156`), `_basis_of` (`:1180`) y `_pooled_net_expectancy` (`:1192`).
  Con base homogénea el pooled sale **byte a byte** como `v2.57`; con `MIXED` el pooled es **`None`**.
- `auto_adaptive_confidence.py`: `_basis_transition` (`:268`) con `STABLE_ESTIMATED` / `STABLE_APPLIED` /
  `TRANSITION` / `MIXED` / `UNKNOWN`; `_decay` **gated** (`:290`/`:313`); `net_r_basis` + `net_r_series` en
  `RegimeConfidence`/`StrategyConfidence` (`:355`/`:358`, `:403`/`:407`).

### Paso 3 — Protección de poblaciones mixtas en el reparto

- `auto_adaptive.py`: `_net_basis_comparable` (`:967`), nota `ADAPTIVE_CELL_NOTE_BASIS_UNSTABLE` (`:281`,
  uso `:1080`), `StrategyHealth.net_r_basis`/`basis_transition` (`:422`/`:423`), `evidence_for` publicando
  `netRBasis`/`basisTransition`.
- Sello: `ADAPTIVE_POLICY_VERSION = "auto17-v1"` (`:188`). **Aquí SÍ cambia la regla** (la condición del
  eje del R neto), a diferencia de `AUTO-16`, donde solo cambiaba la procedencia de un input.

### Paso 4 — Política de transición histórica

- La dimensión `strategy × regime × basis` se representa con las **dos series**; las celdas decisivas **no**
  se parten (para no romper `min_trades`).
- Sin backfill: pre-2.57 `STABLE_ESTIMATED`, post-2.57 `STABLE_APPLIED`; el periodo con ambos
  `TRANSITION`/`MIXED` y Adaptive **no** interpreta el salto como señal.

### Paso 5 — Cierre: mutaciones, compuertas, delta, docs, bump y sello

- **Mutaciones `M129…M138`** (10 nuevas) + realineos de `M32`, `M122`, `M125`, `M128`.
- Compuertas con el comando de CI, delta simétrico fichero a fichero con los rojos declarados de antemano,
  paquete de docs, bump `1.83.0-beta`, tag `v2.58-beta`, `main` en fast-forward y PR de auditoría.

---

## 3. Anclas de código (verificadas sobre el árbol que se sella)

| Qué | Dónde |
| --- | --- |
| `AppliedLeg.quantity` | `packages/py/application/src/bolsa_application/applied_cost.py:121` |
| `applied_leg` | `.../applied_cost.py:175` |
| `_quantity_balanced` | `.../applied_cost.py:222` |
| Agregado por ciclo (lados + balance) | `.../applied_cost.py:266` / `:267` |
| Autoridad de cierre | `.../applied_cost.py:340` |
| `_cycles_with_risk` (cierre una sola vez) | `.../auto_self_evaluation_feed.py:246` |
| `NetRBasisSeries` | `packages/py/analytics/src/bolsa_analytics/cognitive/auto_self_evaluation.py:689` |
| `_net_r_series` / `_basis_of` / `_pooled_net_expectancy` | `.../auto_self_evaluation.py:1156` / `:1180` / `:1192` |
| `_basis_transition` | `.../auto_adaptive_confidence.py:268` |
| `_decay` gated | `.../auto_adaptive_confidence.py:290` / `:313` |
| `_net_basis_comparable` | `.../auto_adaptive.py:967` |
| Nota `ADAPTIVE_CELL_NOTE_BASIS_UNSTABLE` | `.../auto_adaptive.py:281` (uso `:1080`) |
| Sello del reparto | `.../auto_adaptive.py:188` |
| Guardia de head de Alembic | `apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43` |
| Bloque de la sonda (`M119…M138`) | `apps/api-python/scripts/v2_44_mutation_audit.py` (`MUTATIONS`) |

---

## 4. El método de verificación del repo (no improvisar)

1. **Compuertas con el comando de CI** (no rutas sueltas): `ruff check packages/py apps/api-python
   --config pyproject.toml`, el `mypy` exacto del YAML y `lint-imports --config packages/py/.importlinter`.
2. **pytest con `uv run --no-sync python -m pytest`**: en esta máquina `uv run pytest` lo bloquea la
   directiva de Control de aplicaciones (`os error 4551`).
3. **Sonda de mutaciones**: mide, restaura **byte a byte** y verifica la huella `git status`. Filtro por
   etiqueta para verificar un tramo.
4. **Delta simétrico fichero a fichero**: se corre **la versión de `HEAD`** de cada test modificado contra
   el árbol de la fase (nunca se restan totales).
5. **Los tests PG exigen PostgreSQL real** levantado (compose local); con el puerto cerrado la sonda usa un
   DSN *fast-fail*.

---

## 5. El cierre, hecho y medido

- **Compuertas:** `ruff` **`All checks passed!`**, el `mypy` exacto del YAML **`Success: no issues found in 499 source files`** e `import-linter` **`4 kept, 0 broken`** (pack §7).
- **Batería de CI `quality`** (selección exacta del YAML, sin PG): **`2695 passed, 0 skipped, 0 failed`** en `94.15s`.
- **Tramo de la fase:** `test_applied_cost.py` + `test_auto_self_evaluation_feed.py` +
  `test_auto_self_evaluation.py` + `test_auto_adaptive_confidence.py` + `test_auto_adaptive.py` +
  `test_auto_v57_auto16_applied_cost_seam.py` + `test_auto_v53_auto12_confidence_seam.py` +
  `test_auto_v54_auto13_recovery_seam.py` ⇒ **`245 passed`**, `0` rojos.
- **Delta simétrico:** ver pack §7 (fichero a fichero, con los rojos declarados de antemano y solo ésos).
- **Matriz COMPLETA `M1…M138`:** corrida entera (`138/138` muerden, `0` fragmentos ausentes, restauración
  byte a byte, huella idéntica). **Cuatro realineos declarados** (`M32`, `M122`, `M125`, `M128`).

---

## 6. Límites declarados y freeze

- **El aplicado se completa con la comisión del MODELO** (en SIM no hay comisión realizada): la base lo
  nombra; no se finge un coste completo.
- **Sin backfill y sin migración**: la base es recomputable (`reference_mid` presente/ausente + comisión).
- **La tolerancia del balance de cantidades** (`_QTY`) es declarada; un fill con cantidad ilegible hace que
  el ciclo **no** se declare `COMPLETE`.
- **Freeze:** `auto_adaptive_journal.py` y el gobernador **intactos** (diff vacío); sin UI, sin SHORT, `*.md`
  sin `prettier`; `governor.json` sigue sin trackear.

---

## 7. Punto de entrada para el siguiente agente

El [arranque del agente post `v2.58`](./arranque-agente-post-v2.58-auto-17-2026-09-24.md) trae el prompt
listo, las anclas re-medidas y los candidatos declarados (**no decididos**) para `AUTO-18`. La fase está
**cerrada**: lo que falta es la decisión del propietario, no trabajo pendiente.
