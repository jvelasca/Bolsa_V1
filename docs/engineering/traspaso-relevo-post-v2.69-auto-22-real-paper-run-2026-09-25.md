# Traspaso / relevo — cierre de `v2.69-beta` (`AUTO-22`)

> **AsOf:** 2026-09-25 · **Versión:** `1.94.0-beta` · **Fase:** RUN de evidencia PAPER reproducible +
> UI de evidencia en 3 niveles.
> **SIN migración.** **Freeze intacto.** Sello del reparto **`auto18-v1` congelado**.

## Qué se ha hecho

Fase de **instrumentación de la corrida real**, no de decisión. El invariante que instala:

> **La corrida de evidencia es UN comando reproducible que se guarda con su huella; o se ejecuta
> completa o se declara BLOQUEADA — nunca un bundle parcial, recálculo manual ni número copiado.**

1. **Lector único PG.** `packages/py/application/src/bolsa_application/auto_paper_material.py` (nuevo)
   concentra la lectura del material PAPER: guarda de **venue PAPER** (`NonPaperVenueError`), paginación
   hasta **completitud** (`MaterialIncompleteError`), manifest y **huella**. `paper_cycles_export.py`
   pasa a **envoltorio fino** que lo llama: **una sola ruta de lectura**, sin divergencia posible entre
   el export y el run. Su contrato (stdout JSON, `exit 2`) queda intacto y los E2E PG siguen verdes.
2. **Composición pura.** `packages/py/analytics/src/bolsa_analytics/cognitive/auto_evidence_run.py`
   (nuevo) con `EVIDENCE_RUN_SCHEMA = "auto22_evidence_run_bundle_v1"`, `EvidenceRunBlockedError` y
   `build_evidence_run_bundle(...)`: **encadena** `build_calibration_report` (`AUTO-19B`),
   `build_strategy_correlation_report` + `build_current_regime_evidence` (`AUTO-21`) y
   `build_evidence_artifact` / `render_evidence_report` (`AUTO-20C`). **No** hay una segunda aritmética
   de `P(R>0)` ni una correlación paralela. Sin ciclos con R medible ⇒ **lanza** (fail-closed).
   `summarize_evidence_levels` deriva los **tres niveles** del artefacto sin recalcular.
3. **Runner.** `apps/api-python/scripts/auto_evidence_run.py` (nuevo): `--account-id`,
   `--strategy-version` (repetible), `--bucket`, `--current-regime`, `--folds`, `--seed`, `--level`,
   `--resamples`, `--limit`, `--out-root` y `--cycles FILE` (fixture declarado). Escribe un **bundle
   autónomo** por corrida en `evidence_runs/<UTC>-<huella8>/`: `cycles.json`, `artifact.json`,
   `render.txt`, `run.json` (schema, timestamp, args, **huella**, origen, versiones, niveles). Imprime
   los tres niveles a stderr. `exit 2` **BLOQUEADO** sin PG / sin material / sin R medible / venue ≠
   PAPER / corrida ya existente (una corrida es **inmutable**), **sin escribir ningún fichero**.
4. **UI de 3 niveles.** `auto-evidence-report.ts` + `auto-evidence-section.tsx`: **Nivel 1 Material**
   (universo, huecos, huella), **Nivel 2 Global evidence** (`P(R>0)`, `P(R>0) OOS`, `WFE`) **+
   Calibration**, **Nivel 3 Contexto** (régimen actual, evidencia por estrategia con veredicto,
   correlación entre pares) y cierre **ALLOCATION** `none` (congelado). `null` ⇒ `NO MEDIDO`; veredicto
   ausente ⇒ `INCONCLUSIVE`; **jamás `0.0000`** para una correlación no medida. La UI **lee**, no
   recalcula.
5. **Mutaciones.** **M188** (huella perdida), **M189** (origen `paper_real` fabricado sin material),
   **M190** (bundle vacío en vez de BLOQUEADO).
6. **P3-1 cerrado.** `backtests/core-r-scheduler.test.ts` declara su presupuesto por fichero
   (`vi.setConfig({ testTimeout: 20_000, hookTimeout: 20_000 })`); la suite completa queda verde **sin**
   el flag global `--testTimeout`.

## Estado del sello

- **Tag:** `v2.69-beta` → **`0457827a`** (commit del paquete de fase; `80860ebf` es el `feat` del
  código y el `docs` va encima) = `origin/main`; ver `arranque-auditor`.
- **CI del tag:** `Release tag CI` run `36174421860` **GREEN** en la **primera** pasada (7m59s;
  **11/11 jobs** en success —`lifecycle-pg`, `frontend`, `python`, `a7-gate`, `dr-verify`,
  `decision-spine`, `playwright (mock E2E)`, `shared`, `security (gitleaks)`,
  `certify (aggregate + artifact)`— más `playwright (integrated E2E, opt-in)` **skipped** por diseño;
  **sin flakes** ni re-ejecuciones). Sobre el mismo commit y tag: `Python CI` `36174421886`,
  `Frontend CI` `36174421903`, `Optimize lab` `36174421864` y `Fase 2 scientific` `36174421895` en
  **success**.
- **Base del diff:** `v2.68-beta`.
- **`v2.68-beta` permanece intacta** (tag inmutable).

## Compuertas (medidas)

| Compuerta | Resultado |
|---|---|
| `pnpm --filter @bolsa/web test` | **1331 passed** (232 ficheros), **sin** flag de timeout |
| `pnpm --filter @bolsa/web typecheck` | OK |
| `pnpm --filter @bolsa/web lint` | **0 errores** (23 warnings preexistentes) |
| `pnpm --filter @bolsa/web build` | OK |
| `pnpm --filter @bolsa/web contract:check` | OK |
| `uv run pytest packages/py/application packages/py/analytics -q` | **3196 passed** |
| `uv run pytest apps/api-python/tests/test_auto_v69_auto22_evidence_run.py -q` | **8 passed** |
| `uv run ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src packages/py/application/src apps/api-python/src --follow-imports=silent` | **Success: no issues found in 501 source files** |
| `uv run lint-imports --config packages/py/.importlinter` | **4 kept / 0 broken** |
| Mutaciones | **M188…M190** muerden; matriz completa **190/190** |

## Invariantes que NO se tocan

- PAPER = 100 % VIRTUAL; el reparto `auto18-v1`/`auto15-v1`; el freeze; **sin migración**
  (head `046_fill_reference_mid`).
- La UI **lee y presenta**: `null` ⇒ `NO MEDIDO`; veredicto ausente ⇒ `INCONCLUSIVE`; no-lista ⇒
  `NO MEDIDO`; correlación no medida ⇒ `NO MEDIDO`, nunca `0.0000`.
- **La evidencia no reparte**: `P(R>0)`, la correlación y el régimen viajan como evidencia publicada y
  **no** mueven el sizing, el plan, la reserva ni la rotación.
- El bundle es **autónomo e inmutable**: no se sobrescribe una medición.

## Pendiente / fuera de alcance

- **La corrida PAPER real**: paso operativo del propietario (bloqueo por **material**, no por código).
  Con material: `auto_evidence_run.py --account-id <uuid> --strategy-version <v>` e importar
  `artifact.json` en la cabina.
- **P3-2** (validación empírica de la correlación por cubos) y **P3-3** (`P(R>0)` vs tamaño muestral):
  requieren el primer dataset real.
- LIVE, allocation dinámica y current-regime gating operativo.

## Cómo continuar

Ver [`arranque-agente-post-v2.69-auto-22-real-paper-run-2026-09-25.md`](./arranque-agente-post-v2.69-auto-22-real-paper-run-2026-09-25.md).
Para auditar, [`arranque-auditor-v2.69-auto-22-real-paper-run-2026-09-25.md`](./arranque-auditor-v2.69-auto-22-real-paper-run-2026-09-25.md).
