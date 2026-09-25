# Audit-pack — `v2.64-beta` (`AUTO-20C` · Primera calibración PAPER (virtual) + perímetro + invariante)

**Versión:** `1.89.0-beta` · **Rótulo:** `AUTO-20C` / `V2.64` · **Fecha:** 2026-09-25 · **Base de
auditoría:** cierre de `v2.63.1-beta`.

**Plan:** [plan-v2-64](./plan-v2-64-auto-20c-paper-virtual-2026-09-25.md) ·
**Invariante:** [invariante-paper-virtual](./invariante-paper-virtual-2026-09-25.md) ·
**Origen:** auditoría de `v2.63.1-beta` (puntos 17-30) · **Pack previo:**
[audit-pack v2.63](./audit-pack-v2-63-auto-20b-export-e2e-2026-09-25.md).

## §1 — Qué se construyó (afirmación → código → test)

| # | Afirmación | Código | Test que la sostiene |
|---|---|---|---|
| 1 | El artefacto declara la realidad **PAPER VIRTUAL** (`realMoneyAtRisk=false`) | `auto_evidence_report.py` | `test_the_artifact_declares_the_virtual_paper_reality`, `test_the_artifact_declares_virtual_paper_and_no_real_money` |
| 2 | El informe viaja **verbatim** en el artefacto (no se reinterpreta) | `build_evidence_artifact` | `test_the_artifact_publishes_the_report_verbatim` |
| 3 | Cada pregunta se imprime con su veredicto (sin invertirlo) | `render_evidence_report` | `test_the_render_labels_every_calibration_question` |
| 4 | Un `walkForwardEfficiency` ausente ⇒ `INCONCLUSIVE`, nunca un número inventado | idem | `test_the_render_marks_missing_evidence_inconclusive`, `test_the_render_shows_the_walk_forward_efficiency_when_it_exists` |
| 5 | El render declara perímetro y reparto congelado (`none`) | idem | `test_the_render_declares_the_perimeter_and_the_frozen_allocation` |
| 6 | El manifest declara **observadas vs pedidas** y los **fills excluidos** | `auto_material_manifest.py` (application) | `test_the_manifest_declares_the_perimeter_of_the_dump` |
| 7 | Una versión pedida sin material se **nombra** | idem | `test_the_manifest_names_a_requested_version_without_material` |
| 8 | Sin agregado del store el perímetro es **`None`** ("no medido"), no `0` | idem | `test_the_manifest_does_not_invent_the_perimeter_without_the_aggregate` |
| 9 | La lectura agregada por versión es **aditiva** (worker/`list_by_cycle_ids` intactos) | `sim_durable_store.py` | suites de la costura AUTO-9/AUTO-16 sin cambio |
| 10 | `--out`/`--render` **no cambian** stdout (byte-idéntico) | `auto_replay_battery.py` | `test_the_battery_writes_the_artifact_and_render_without_changing_stdout` |
| 11 | Un carril no-PAPER **bloquea** el sellado (`exit 2`, sin JSON) | `paper_cycles_export.py` → `NonPaperVenueError` | `test_the_exporter_blocks_a_venue_that_is_not_paper` |
| 12 | E2E PG: los fills sin versión / de otra versión se **cuantifican** sin entrar al universo | fixture + exportador real | `test_the_export_is_certified_end_to_end_against_real_postgres` (asertos 2b) |

Cada afirmación tiene su **mutación** (§4) que la mata.

## §2 — Superficie medida (compuertas)

| Compuerta | Comando | Resultado |
|---|---|---|
| Lint | `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| Capas | `uv run --no-sync lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** (627 ficheros) |
| Tipos | `uv run mypy … --follow-imports=silent` | **500 ficheros, 0 errores** |
| Puros | `uv run --no-sync pytest packages/py/analytics/tests packages/py/application/tests -q` | **3156 passed** |
| E2E + puros AUTO-20B/20C | `AUTO20B_EXPORT_PG_REQUIRED=1 uv run pytest test_auto_v63_auto20b_export_e2e_pg.py test_auto_v64_auto20c_artifact.py test_auto_v63_auto20b_export_completeness.py -q -rs` | **10 passed** (sin skips) |
| Mutaciones (nuevas) | `v2_44_mutation_audit.py M175 M176 M177 M178` | **4/4** muerden |
| Mutaciones (matriz) | `v2_44_mutation_audit.py` | **178/178**, `0` sin fragmento, restauración byte a byte |
| Línea base | la del propio runner (sin mutación) | **`ninguno`** en cada selección de tests del tramo |

## §3 — Superficie de cambio

`9 ficheros` **de código/CI/tests** modificados (**+436 / −18**) más **4 ficheros nuevos** (sin contar este
pack ni la documentación/sello):

- `packages/py/analytics/src/bolsa_analytics/cognitive/auto_evidence_report.py` (**nuevo**, puro) — realidad
  virtual, artefacto y render.
- `packages/py/application/src/bolsa_application/sim_durable_store.py` (**+42**) — `count_by_strategy_version`
  aditivo (Protocol + InMemory + Postgres).
- `packages/py/application/src/bolsa_application/auto_material_manifest.py` (**+84/−…**) — perímetro,
  `observedStrategyVersions`, `regimesPresent`, `materialOrigin` (obligatorio), procedencia.
- `apps/api-python/scripts/paper_cycles_export.py` (**+67/−…**) — nota virtual, guard `NonPaperVenueError`,
  lectura agregada del perímetro.
- `scripts/research/auto_replay_battery.py` (**+56/−…**) — `--out`/`--render`, envelope + render.
- `apps/api-python/scripts/v2_44_mutation_audit.py` (**+42**) — M175–M178 y sus constantes.
- `.github/workflows/python-ci.yml` (**+10**) y `release-tag-ci.yml` (**+10**) — comentario de la fase.
- `test_auto_evidence_report.py` (**nuevo**), `test_auto_v64_auto20c_artifact.py` (**nuevo**),
  `test_auto_v63_auto20b_material_manifest.py` (**+93**), `test_auto_v63_auto20b_export_e2e_pg.py` (**+50**).
- `CHANGELOG.md`, `PROJECT_STATE.md`, `engineering-index`, `package.json` (`1.88.1-beta`→`1.89.0-beta`).

## §4 — Mutaciones de la fase

| Id | Qué rompe | Rojo en |
|---|---|---|
| **M175** | El perímetro declara que no hay fills sin versión | `test_the_manifest_declares_the_perimeter_of_the_dump` |
| **M176** | El manifest deja de declarar las versiones observadas | idem |
| **M177** | El artefacto deja de declarar la realidad PAPER virtual | `test_the_artifact_declares_the_virtual_paper_reality` (+2) |
| **M178** | El battery no vuelca el artefacto reproducible | `test_the_battery_writes_the_artifact_and_render_without_changing_stdout` (+1) |

## §5 — Render del punto 30 (forma)

```text
AUTO EVIDENCE REPORT
====================
Material
  origin:               paper_real
  cycles:               26
  measured (with R):    17
  without R:            9
  regimes:              RANGE, TREND_UP (2)
  fingerprint:          sha256:…

Calibration
  Shrinkage                 INCONCLUSIVE
  Effective-N               INCONCLUSIVE
  Interval coverage         INCONCLUSIVE
  Edge sign                 NOT_SUPPORTED
  Confidence calibration    NOT_SUPPORTED
  Coverage (regime)         SUPPORTED
  Walk-forward efficiency   0.4213

Declared
  Current regime            AUTO-21 (fuera de alcance)
  Current evidence          AUTO-21 (fuera de alcance)
  Allocation change         none (auto18-v1 congelado: la evidencia no mueve el reparto)

perimeter
  requested versions:   orb-a
  observed versions:    orb-a
  fills total:          500
  fills selected:       420
  excluded (no version):80
  excluded (other):     0
  reservations read:    17
  risk read saturated:  False (false = la lectura terminó; NO = 'todas las reservas existen')

execution reality:    virtual_paper_only (realMoneyAtRisk=False, venue=paper)
golden rule:          INCONCLUSIVE por muestra insuficiente NO se arregla bajando min_is/min_oos/folds: se declara y se conserva como resultado.
```

(Forma ilustrativa: los valores son los del fixture de test, no una corrida real.)

## §6 — Freeze

No se tocan: `auto_adaptive.py` (`auto18-v1`), `auto_adaptive_data_gate.py` (`auto15-v1`),
`auto_simulation_worker.py`, `auto_adaptive_journal.py`, `auto_adaptive_replay.py`
(`statistical_oos_v1`), `v2_43_governor_evidence.py`, `governor.json`. **Sin migración** (todo es código).

## §7 — Límites declarados

- Sin material PAPER real suficiente, el entregable es el **instrumento** + el invariante; la corrida real
  es paso **operativo** del propietario (`export` → `--walk-forward --out` sobre ≥32 ciclos medidos por
  estrategia).
- El material sigue sin demostrar edge; la huella no prueba procedencia criptográfica.
- `P(R>0)`, correlación entre estrategias y current-regime gating siguen fuera (AUTO-21).
