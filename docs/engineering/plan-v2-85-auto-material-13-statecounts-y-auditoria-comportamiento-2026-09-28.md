# Plan — `V2.85` / `AUTO-MATERIAL-13`: cierre de `OBS-10` y auditoría de COMPORTAMIENTO

> **AsOf:** 2026-09-28 · **Estado:** **PLANIFICADA** (no ejecutada) · **Base:** `v2.84-beta`
> (`2.09.0-beta`, commit `fd3859e3`) · **Bump previsto:** `2.09.0-beta → 2.10.0-beta` ·
> **Alembic head:** `046_fill_reference_mid` (**SIN migración**).

## 0. Por qué existe y cuándo se ejecuta

La auditoría externa de `v2.84-beta` emite **APROBADO** (0 bloqueantes) y deja una observación **`OBS-10`**
(LOW) más dos recomendaciones operativas. Su conclusión estratégica es que el siguiente salto de calidad
debe venir de **datos reales**, no de más infraestructura, así que esta fase es **corta y de cierre**: no
añade capas de observabilidad, corrige una inconsistencia de semántica y endurece un script de operación.

**Cuándo:** **después** de cerrar la ventana PAPER (`P3-2`/`P3-3`), porque una ventana en curso exige que
el árbol de **código** no se mueva (`git rev-parse "HEAD:apps" "HEAD:packages"`) y esta fase **sí** toca
`packages/`. Ejecutarla antes invalidaría D1..D4 en curso.

## 1. Alcance (4 entregables)

### 1.1 `OBS-10` — `stateCounts` debe respetar `measured_rows` (INSTRUMENTO)

- `packages/py/application/src/bolsa_application/operability_audit.py`: el bloque `stateCounts` de
  `window_totals` itera **`measured_rows`** (hoy itera `rows`), coherente con `counts`, `coverage`,
  `rSum` y `funnel`. Los días no medidos siguen declarados como `daysTotal - daysMeasured`.
- **Docstring de `window_totals`**: añadir que `stateCounts` **también** respeta `measured_rows`.
- **Test**: `test_window_totals_state_counts_ignores_unmeasured_rows` en
  `packages/py/application/tests/test_operability_audit.py` (una fila `measured=False` con `state`
  poblado **no** cuenta; una fila medida **sí**).
- **Mutación `M233`** en `apps/api-python/scripts/v2_44_mutation_audit.py` (matriz **232 → 233**) que
  muerda exactamente contra ese test.

**Criterio de aceptación.** Con una fila `measured=False` + `state="unresolved"`, `stateCounts` **no**
la cuenta; `daysMeasured` no cambia; el TOTAL sigue cuadrando con `counts`/`funnel`.

### 1.2 Etiquetado de `unresolvedRate` (lectura, sin renombrar la clave)

- `operability_audit.py`: aclarar en el docstring de `window_rates` y en el render
  (`_rate_lines`) que `unresolvedRate` es **días** en estado `unresolved` sobre **días medidos**, no una
  tasa de propuestas. **No** se renombra la clave (compatibilidad con informes anteriores).

### 1.3 Endurecimiento de `ops_seed_window_pair.py` (anexo operativo)

- `apps/api-python/scripts/ops_seed_window_pair.py`: **no** permitir la creación silenciosa de una cuenta
  nueva. Opciones a decidir en ejecución: (a) exigir `--account-id`; (b) mantener el valor por defecto
  pero exigir un `--allow-create` explícito para acuñar cuenta. **Motivo (auditor):** sin cuenta fija la
  continuidad de la muestra se rompe (`D1 → account 101`, `D2 → account 102`). Se documentará la decisión
  y su código de salida.

### 1.4 Auditoría de COMPORTAMIENTO sobre el material real

- Ejecutar el [protocolo de comportamiento](./protocolo-auditoria-comportamiento-auto-2026-09-28.md) sobre
  el bundle **real** de la ventana y publicar el **funnel localizado** + las tasas + el veredicto honesto
  (`READY`/`INCONCLUSIVE`/`NO MEDIDO`) en un informe de fase con las cifras **observadas**.

## 2. Fuera de alcance (prohibido)

- Motor (`auto_simulation_worker.py`), gobernador (`aggregate_trial_regime`), `operability_window.py`,
  `v2_80_market_window.py`, `TOP_N`, umbrales, allocation, pesos A/B, UI y **migraciones**.
- **No** se renombra `unresolvedRate` ni ninguna otra clave publicada.
- **No** se cierra ninguna deuda por documentación: `P3-2`/`P3-3`/`H-4`/`OBS-9`/`P3-5`/`OBS-5` sólo se
  cierran con datos o con barrido explícito.
- **No** se añade ninguna capa nueva de observabilidad.

## 3. Compuertas a ejecutar (idénticas a `v2.84`)

```powershell
uv run --no-sync pytest packages/py/application/tests/test_operability_audit.py -q   # 19 passed (18 + 1)
uv run --no-sync pytest packages/py/application/tests -q                             # 2090 passed (2089 + 1)
uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml      # All checks passed!
uv run --no-sync lint-imports --config packages/py/.importlinter                     # 4 kept, 0 broken
uv run --no-sync mypy packages/py/domain/src packages/py/market/src \
    packages/py/infrastructure/src packages/py/application/src apps/api-python/src \
    --follow-imports=silent                                                          # 0 issues
uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py              # medidas: 233/233
```

**Freeze check (obligatorio antes y después):** `git rev-parse "HEAD:apps" "HEAD:packages"` debe ser
**estable** durante toda la fase (no hay ventana en curso en ese momento).

## 4. Entregables documentales

- `docs/engineering/plan-v2-85-…` (este documento).
- `docs/engineering/audit-pack-v2-85-…` + `arranque-auditor-v2-85-…` + `arranque-agente-…` +
  `traspaso-relevo-post-v2-85-…` + evidencia de matriz (**233**) + evidencia del CI del tag.
- Actualización de `CHANGELOG.md`, `PROJECT_STATE.md`, `engineering-index`, y cierre de `OBS-10` en la
  [deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md).
- `package.json`: `2.09.0-beta → 2.10.0-beta`; tag anotado **`v2.85-beta`**.

## 5. Riesgos declarados

| Riesgo | Mitigación |
|---|---|
| Corregir `stateCounts` cambia una cifra publicada | Es un **bloque del TOTAL** que hoy sólo se contamina en el bucket `unknown` (los productores son fail-closed): impacto medido **nulo** sobre el material real; se mide antes/después en la fase |
| Tocar `packages` durante la ventana | **Prohibido**: la fase se ejecuta **después** del cierre de la ventana (freeze check obligatorio) |
| Endurecer el script OPS rompe el arranque ya hecho | La cuenta de la ventana **ya** está fijada en `.env`; el cambio sólo afecta a futuras siembras |

## 6. Referencias

- [Protocolo de auditoría de COMPORTAMIENTO](./protocolo-auditoria-comportamiento-auto-2026-09-28.md).
- [Deuda P3](./deuda-p3-post-auditoria-v2.70-2026-09-26.md) (`OBS-10`).
- [Audit-pack `v2.84`](./audit-pack-v2-84-auto-material-12-instrument-funnel-contract-2026-09-27.md).
- [Runbook de la ventana](./runbook-ventana-forward-v2.78-2026-09-27.md).
