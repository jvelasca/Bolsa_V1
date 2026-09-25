# Traspaso / relevo — post `v2.64-beta` (`AUTO-20C` · Primera calibración PAPER (virtual) + perímetro + invariante)

**Para el siguiente agente.** Lee esto antes de tocar nada. Fuente de verdad de la fase:
[plan](./plan-v2-64-auto-20c-paper-virtual-2026-09-25.md) ·
[audit-pack](./audit-pack-v2-64-auto-20c-paper-virtual-2026-09-25.md) ·
[invariante](./invariante-paper-virtual-2026-09-25.md) ·
[arranque del auditor](./arranque-auditor-v2.64-auto-20c-paper-virtual-2026-09-25.md).

## 1. Dónde estamos

- **`v2.64-beta` (`1.89.0-beta`)** sellada. Base de auditoría: el cierre de `v2.63.1-beta`.
- `AUTO-20C` cierra el **perímetro declarado** (puntos 21-24 de la auditoría) y **instala el invariante
  PAPER VIRTUAL** en toda la cadena, además de producir el **artefacto reproducible** y el **render**
  (`AUTO EVIDENCE REPORT`, punto 30) sobre la calibración ya auditada.
- El **reparto no se movió**: `auto18-v1` / `auto15-v1`; **sin migración** (head en `046_fill_reference_mid`).

## 2. Qué se hizo (y por qué)

| Pieza | Qué cambia |
|---|---|
| **Invariante virtual** | Nuevo `auto_evidence_report.py` (analytics, puro): `EXECUTION_REALITY_VIRTUAL_PAPER`, `REAL_MONEY_AT_RISK=False`, `EVIDENCE_ARTIFACT_SCHEMA`. Se propaga a manifest, nota del exportador, artefacto y render. **Ninguna operación se ejecuta sobre XTB ni plataforma real.** |
| **Guard de venue** | El exportador **se bloquea con `2`** (sin JSON) si `settings.broker_venue != "paper"` (`NonPaperVenueError`): un artefacto PAPER no se sella con material de otro carril. |
| **Perímetro** | `sim_durable_store.py` gana `count_by_strategy_version` (agregado aditivo: Protocol + InMemory + Postgres). El manifest declara `observedStrategyVersions`, `versionsRequestedWithoutMaterial`, `versionsObservedNotRequested`, `fillsTotalForAccount`/`fillsSelected`/`fillsExcludedNoVersion`/`fillsExcludedOtherVersion`, `regimesPresent` y `materialOrigin` (**obligatorio**). |
| **Artefacto + render** | `auto_replay_battery.py` gana `--out`/`--render` **opcionales** (sin ellos stdout es **byte-idéntico**). `build_evidence_artifact` envuelve el informe verbatim; `render_evidence_report` imprime la tabla del punto 30 + los huecos declarados (`AUTO-21`) + la **regla de oro**. |
| **E2E** | Fixture PG ampliado con 2 fills sin versión y 2 de otra versión: el exportador **no** los lee, el manifest los **cuantifica**. Asertos de perímetro y de que el universo medido no cambia. |
| **Mutaciones** | **M175–M178** (excluidos falseados, observadas eliminadas, procedencia borrada, artefacto no escrito). |

**Por qué el perímetro va separado del universo medido**: la huella `material_fingerprint_v1` sella el
universo **medido**; los excluidos son **metadata del contorno**. Mezclarlos habría cambiado la huella de
corridas ya auditadas. `riskReadSaturated=false` sigue significando "la lectura terminó", **no** "todas las
reservas existen".

## 3. Estado medido (compuertas)

* `ruff check packages/py apps/api-python --config pyproject.toml` — **All checks passed!**
* `lint-imports --config packages/py/.importlinter` — **4 kept / 0 broken** (627 ficheros).
* `mypy … --follow-imports=silent` — **500 ficheros, 0 errores**.
* Puros `packages/py/analytics/tests` + `packages/py/application/tests` — **3156 passed**.
* E2E + puros AUTO-20B/20C con `AUTO20B_EXPORT_PG_REQUIRED=1` — **10 passed** (postgreSQL real, sin skips).
* Mutaciones nuevas **M175–M178** — muerden y restauran byte a byte; matriz completa **M1–M178**.

## 4. Huecos declarados (lo que ESTA fase NO cierra)

1. **El walk-forward real sigue sin ejecutarse.** Los umbrales por defecto (`folds=3`, `min_is=8`,
   `min_oos=4`) exigen ≥32 ciclos medidos por estrategia: el fixture del E2E es **sintético** y mide la
   cadena de material, no el edge. Es un **paso operativo del propietario** (ver §6).
2. **La huella no es una prueba de procedencia criptográfica**: sella igualdad de universo, no la fuente.
3. **`P(R > 0)`, correlación entre estrategias y current-regime gating** siguen fuera (AUTO-21); por eso el
   render imprime `Current regime`/`Current evidence` como `AUTO-21 (fuera de alcance)`.

## 5. Ficheros clave

* `packages/py/analytics/src/bolsa_analytics/cognitive/auto_evidence_report.py` — **nuevo**: invariante + artefacto + render.
* `packages/py/application/src/bolsa_application/sim_durable_store.py` — `count_by_strategy_version` aditivo.
* `packages/py/application/src/bolsa_application/auto_material_manifest.py` — perímetro + procedencia.
* `apps/api-python/scripts/paper_cycles_export.py` — nota virtual + guard de venue + perímetro.
* `scripts/research/auto_replay_battery.py` — `--out`/`--render`.
* `packages/py/analytics/tests/test_auto_evidence_report.py`, `apps/api-python/tests/test_auto_v64_auto20c_artifact.py` — **nuevos**.
* `apps/api-python/tests/test_auto_v63_auto20b_export_e2e_pg.py` — E2E ampliado (job `auto-v2-durable-pg`).
* `apps/api-python/scripts/v2_44_mutation_audit.py` — M175–M178.

## 6. Paso operativo del propietario (no lo fabrica la fase)

Con **≥32 ciclos medidos por estrategia** en una cuenta PAPER (**virtual**):

```powershell
uv run --no-sync python apps/api-python/scripts/paper_cycles_export.py --account-id <uuid> --strategy-version <v> > ciclos.json
uv run --no-sync python scripts/research/auto_replay_battery.py --walk-forward --cycles ciclos.json --out AUTO20C_REAL_PAPER_REPORT.json --render AUTO20C_REAL_PAPER_REPORT.txt
```

Conservar `AUTO20C_REAL_PAPER_REPORT.json` + el render como artefacto reproducible y aceptar honestamente
cualquiera de los tres veredictos (`SUPPORTED` / `NOT_SUPPORTED` / `INCONCLUSIVE`) **sin tocar umbrales**.

## 7. Cómo re-verificar en frío

```powershell
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml
uv run --no-sync lint-imports --config packages/py/.importlinter
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent
uv run --no-sync pytest packages/py/analytics/tests packages/py/application/tests -q
$env:AUTO20B_EXPORT_PG_REQUIRED="1"; uv run --no-sync pytest apps/api-python/tests/test_auto_v63_auto20b_export_e2e_pg.py apps/api-python/tests/test_auto_v64_auto20c_artifact.py apps/api-python/tests/test_auto_v63_auto20b_export_completeness.py -q -rs
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py M175 M176 M177 M178
```

## 8. Reglas de la casa que siguen vigentes

* **PAPER = dinero VIRTUAL** — ninguna operación se ejecuta sobre XTB ni plataforma real; toda la cadena lo
  declara y el exportador lo bloquea si la venue no es `paper`.
* **Lo que no se midió se declara** — nunca un veredicto, un conteo ni un cero inventados.
* **Un solo productor por medida** — la realidad virtual se importa, no se re-declara.
* **Nada de evidencia mueve el reparto** — `auto18-v1` no se toca sin fase propia.
* **`INCONCLUSIVE` es un resultado**, no un error: no se "arregla" bajando `min_is`/`min_oos`/`folds`.
