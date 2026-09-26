# Changelog

All notable releases of Bolsa V1.

## [1.96.0-beta] — Corrección de la semántica de `P(R>0)` y cierre de P3 (AUTO-19A/19B) — 2026-09-26

**Fase de corrección del instrumento; SIN migración** (Alembic head sigue en `046_fill_reference_mid`) y
**sin tocar ningún fichero del freeze**. El reparto **no se mueve**: `auto18-v1` / `auto15-v1`. No se
toca `evidence_runs`/`evidence_validations` ni el runbook: el **primer RUN PAPER real** pasa a ser el
**hito siguiente** (paso operativo del propietario).

El nombre `P(R>0)` mezclaba **dos funcionales** y la calibración los comparaba como si fueran lo mismo.
El invariante que instala esta fase: **`P(R>0)` es la fracción de CICLOS positivos (lo medido) y
`P(edge>0)` es la fracción de MEDIAS bootstrap positivas (el edge); la calibración solo compara
magnitudes homogéneas, y lo que no se midió se declara — nunca se cuenta como evidencia negativa ni se
publica con un nivel que no se usó.**

- **Dos probabilidades.** `auto_adaptive_uncertainty.py`: `probability_positive` → **`edge_positive_probability`**
  (`edgePositiveProbability`, `P(edge>0)`) y nueva **`cycle_positive_share`**
  (`cyclePositiveShare`, `P(ciclo>0)` estricta, sobrevive sin bootstrap). Sello
  `ADAPTIVE_UNCERTAINTY_METHOD` `bootstrap_episodes_v2` → **`bootstrap_episodes_v3`**.
- **Calibración homogénea.** `auto_adaptive_calibration.py` (`_question_probability_positive`) compara
  `is_cycle_positive_share` (IS) contra `oos_positive_share` (OOS) e **ignora** la `P(edge>0)`. Sello
  `CALIBRATION_METHOD` `walk_forward_calibration_v3` → **`walk_forward_calibration_v4`**. Se conservan
  las claves y agregados de la UI (`probability_positive_calibration`, `meanDeclaredProbability`,
  `meanRealizedPositiveShare`, `probabilityPositiveOos`).
- **P3 cerradas.**
  - **H2 (cobertura no medida).** `_question_coverage` excluye `dominant_regime_coverage is None` del
    grupo "no cubierta" y lo declara en **`cellsUnmeasured`**: la ausencia de medición no es evidencia.
  - **H3 (nivel clampeado).** `build_replay_report` publica el `interval_level` **efectivo**
    (`resolved_level`, el mismo que usó el bootstrap), como ya hacía `CalibrationReport`.
  - **H4 (colisión de clave).** La celda de replay renombra `regimeCoverage` → **`dominantRegimeCoverage`**
    (campo `dominant_regime_coverage`), fin de la colisión banda/`float` con `StrategyConfidence`.
- **Consumidores.** `auto_adaptive_replay.py`: `is_edge_positive_probability` + `is_cycle_positive_share`;
  `auto_adaptive_regime_evidence.py`: `probabilityPositive = P(ciclo>0)` + `edgePositiveProbability`
  aditiva, sello `current_regime_evidence_v1` → **`current_regime_evidence_v2`**; `auto_evidence_validation.py`:
  `probabilityPositive = cycle_positive_share` + `edgePositiveProbability`, sellos
  `auto23_evidence_validation_v2`, `auto23_sample_size_sweep_v2`, `auto23_regime_stability_v2` y método
  `chronological_prefix_sweep_v2`. La UI **lee**, no recalcula, y mantiene sus claves.
- **Mutaciones.** `M182`–`M184`/`M187` actualizadas y **`M193`–`M197`** nuevas (P(R>0) cuenta ciclos;
  calibración homogénea; cobertura no medida; nivel clampeado; clave sin colisión). Matriz completa
  **197/197** (192 + 5 nuevas; el plan citaba `198` por un desliz aritmético) con restauración
  **byte a byte** (`apps/api-python/scripts/v2_44_mutation_audit.py`).

**Compuertas.** Frontend **1339 passed** (232 ficheros) · `typecheck` OK · `lint` **0 errores** (23
warnings preexistentes) · `build` OK · `contract:check` OK · Python `analytics` **1262 passed** ·
`application` **1945 passed** (5 errores de fixture PG por DSN fast-fail, ajenos) · suites `api-python`
afectadas **13 passed / 1 skipped** · gate offline `api-python` **479 passed / 14 skipped / 0 fallos**
(los 26 tests `*_pg` requieren Postgres real) · `ruff` **All checks passed** · `import-linter`
**4 kept / 0 broken** · `mypy` **0 issues (501 files)** · matriz **197/197** byte a byte.

**CI del tag `v2.71-beta`** (commit `a310fbc5`; feat `0c2f5014` + docs encima): `Release tag CI` run
`36236375738` **GREEN en la primera pasada** (8m13s, `intento=1`, **10 jobs** + `certify (aggregate +
artifact)`, con `playwright (integrated E2E, opt-in)` **skipped** por diseño y **sin flakes ni
re-ejecuciones**); sobre el mismo commit y tag, `Python CI` `36236375798`, `Frontend CI`
`36236375770`, `Optimize lab` `36236375716` y `Fase 2 scientific` `36236375788`, todos en **success**.

**Auditoría externa de `v2.71-beta`: `APROBADA CON OBSERVACIONES` (2026-09-26), 0 bloqueantes.**
El auditor verifica las **15 tesis** contra el tag (objeto `80dbed6c` → `a310fbc5`; `HEAD` `2ace60fb`,
con un diff tag→HEAD **solo de docs**), confirma el **freeze**, el **reparto** y la **ausencia de
migración**, y **re-mide** las compuertas en verde; **14 tesis PASS** y la 15 **PARCIAL** por límite de
mandato (re-ejecutó solo los 7 mutantes autorizados: **7/7 muerden y restauran byte a byte**, `git`
limpio). Levanta **una observación P3 heredada de la clase de H3 y preexistente a la fase**:
`build_current_regime_evidence` publica el `level` **sin clampar** mientras el bootstrap usa el
clampeado; queda registrada como **P3-4** en
[`deuda-p3-post-auditoria-v2.70-2026-09-26.md`](./docs/engineering/deuda-p3-post-auditoria-v2.70-2026-09-26.md)
y **no** se aborda en esta fase (instrumento correcto; la deuda es read-only).

## [1.95.0-beta] — AUTO-23 · Validación de evidencia PAPER real (harness) + procedencia imposible de confundir — 2026-09-25

**Fase de preparación y blindaje; SIN migración** (Alembic head sigue en `046_fill_reference_mid`) y
**sin tocar ningún fichero del freeze**. El reparto **no se mueve**: `auto18-v1` / `auto15-v1`. **La
corrida PAPER real no se ejecuta** (bloqueo por **material**): esta fase deja el RUN (`AUTO-22`) **más**
un **harness de validación** y un **runbook** listos para el primer dataset real.

- **UI (punto 22 de la auditoría de `v2.69`).** `auto-evidence-report.ts` gana `classifyExecutionReality`
  y un bloque `execution` en `EvidenceView`, y `SOURCE` gana un `subtitle` que separa **dato real** de
  **dinero real** («DATOS REALES DE LA CUENTA PAPER · DINERO VIRTUAL · NO ES DINERO REAL»).
  `auto-evidence-section.tsx` renderiza un bloque de cabecera **`EXECUTION REALITY`**
  (`ops-auto-evidence-execution-reality`, `VIRTUAL — NO REAL MONEY`). Reglas duras: `null` ⇒
  `NO MEDIDO`; un origen `desconocido` **jamás** se degrada a `paper_real`; un `realMoneyAtRisk=true`
  **no** se disfraza de virtual. La UI **lee**, no recalcula.
- **Harness puro.** Nuevo `bolsa_analytics/cognitive/auto_evidence_validation.py`
  (`EVIDENCE_VALIDATION_SCHEMA = "auto23_evidence_validation_v1"`, `EvidenceValidationBlockedError`):
  `build_sample_size_sweep` (barrido `P(R>0)` / OOS / WFE / `effective_n` sobre el **prefijo
  cronológico**; `N` > medido ⇒ `NO MEDIDO`), `build_regime_stability` (global vs por régimen +
  divergencias, lectura no gate) y `build_correlation_validation` (matriz de `AUTO-21` por cubo +
  diagnósticos `P3-2`). **Compone** `build_evidence_run_bundle` / `build_adaptive_uncertainty` /
  `build_strategy_correlation_report`: **no** reimplementa ninguna métrica.
- **CLI.** Nuevo `apps/api-python/scripts/auto_evidence_validate.py`: lee PG (o `--cycles FILE`) por el
  **lector único** `read_paper_material` y escribe un **bundle inmutable** en
  `evidence_validations/<UTC>-<huella8>/` (`sweep.json`, `regime_stability.json`,
  `correlation_validation.json`, `validation.json`) con `exist_ok=False`. `exit 2` **BLOQUEADO** sin PG
  / sin material / sin R medible / venue ≠ PAPER / validación ya existente, **sin escribir ningún
  fichero**.
- **Runbook.** `docs/engineering/protocolo-primer-run-paper-real-v2.70-2026-09-25.md`: prerrequisitos,
  paso 1 (1 estrategia, **≥32 ciclos medibles**), paso 2 (2ª estrategia → `correlation(A,B)`), paso 3
  (`P(R>0)` vs N y régimen); **regla dura: no se bajan `min cycles` / `min R` / `folds`**.
- **Mutaciones `M191`** (el barrido recalcula `P(R>0)` en vez de componerla) y **`M192`** (un `N` mayor
  que el material fabrica una fila en vez de `NO MEDIDO`) — **192/192** con restauración byte a byte.
- **Persistencia de la auditoría de `v2.69`** y de su deuda P3 (`auditoria-v2-69-…`, `deuda-p3-post-auditoria-v2.69-…`).

**Compuertas.** Frontend **1339 passed** (232 ficheros) · `typecheck` OK · `lint` **0 errores** (23
warnings preexistentes) · `build` OK · `contract:check` OK · python application+analytics **3203 passed
/ 5 skipped** · CLI **6 passed** (sonda PG opt-in) · `ruff` **All checks passed!** · `import-linter`
**4 kept / 0 broken** · `mypy` **0 issues (501 files)** · matriz completa **192/192** con evidencia cruda
persistida ([`docs/engineering/evidencia-matriz-mutaciones-v2.70-192-2026-09-25.txt`](docs/engineering/evidencia-matriz-mutaciones-v2.70-192-2026-09-25.txt):
`192/192` medidas, `192/192` rojas, árbol intacto).

**Límite declarado:** el **material PAPER real no existe todavía**; la corrida real es **paso operativo
del propietario** y las deudas **P3-2** (correlación por cubos) y **P3-3** (`P(R>0)` vs N) quedan
**abiertas** hasta el primer dataset real.

## [1.94.0-beta] — AUTO-22 · RUN de evidencia PAPER reproducible + UI de evidencia en 3 niveles — 2026-09-25

**Fase de instrumentación de la corrida; SIN migración** (Alembic head sigue en `046_fill_reference_mid`)
y **sin tocar ningún fichero del freeze**. El reparto **no se mueve**: `auto18-v1` / `auto15-v1` — la
evidencia **se publica, no reparte**. El esquema del artefacto **se mantiene**
(`auto20c_evidence_artifact_v1`): el run **no** añade claves. **La corrida PAPER real no se ejecuta**
(bloqueo por **material**): esta fase deja el RUN listo y probado.

- **Lector único PG.** Nuevo `bolsa_application/auto_paper_material.py` (`read_paper_material`,
  `read_all_reservations`, `MaterialIncompleteError`, `NonPaperVenueError`): guarda de **venue PAPER**,
  paginación hasta **completitud**, manifest y **huella**. `paper_cycles_export.py` pasa a **envoltorio
  fino** que lo llama (contrato stdout JSON + `exit 2` intacto, alias `_read_all_reservations`): export y
  run comparten **una sola** ruta de lectura.
- **Composición pura.** Nuevo `bolsa_analytics/cognitive/auto_evidence_run.py`
  (`EVIDENCE_RUN_SCHEMA = "auto22_evidence_run_bundle_v1"`, `EvidenceRunBlockedError`,
  `build_evidence_run_bundle`, `summarize_evidence_levels`): **encadena** `AUTO-19B` + `AUTO-21` +
  `AUTO-20C` sin segunda aritmética; sin ciclos con **R medible** se declara **BLOQUEADO**. El origen por
  defecto es el **fixture declarado**, nunca `paper_real`.
- **Runner.** Nuevo `apps/api-python/scripts/auto_evidence_run.py`: lee PG (o `--cycles FILE`) y escribe
  un **bundle autónomo** por corrida en `evidence_runs/<UTC>-<huella8>/` (`cycles.json`, `artifact.json`,
  `render.txt`, `run.json` con schema, args, **huella** y los tres niveles). `exit 2` **BLOQUEADO** sin PG
  / sin material / sin R medible / venue ≠ PAPER / corrida ya existente, **sin escribir ningún fichero**
  (una corrida es **inmutable**). Publica los **tres niveles** a stderr.
- **UI en 3 niveles.** `auto-evidence-report.ts` (+ test) y `auto-evidence-section.tsx` (+ test):
  **Nivel 1 Material**, **Nivel 2 Global evidence** (`P(R>0)`, `P(R>0) OOS`, `WFE`) + **Calibration**,
  **Nivel 3 Contexto** (régimen actual, evidencia por estrategia con veredicto, correlación entre pares) y
  cierre **ALLOCATION** `none` (congelado). `null` ⇒ `NO MEDIDO`; **jamás `0.0000`** para una correlación
  no medida. La UI **lee**, no recalcula.
- **Mutaciones `M188…M190`** (huella perdida, origen fabricado, bundle vacío en vez de BLOQUEADO) +
  **M169 re-apuntada** al lector único tras el refactor.
- **P3-1 cerrado.** `backtests/core-r-scheduler.test.ts` declara su presupuesto por fichero
  (`vi.setConfig({ testTimeout: 20_000, hookTimeout: 20_000 })`): la suite completa queda verde **sin** el
  flag global `--testTimeout`.

**Compuertas.** Frontend **1331 passed** (232 ficheros; **sin** flag de timeout), `typecheck` OK, `lint`
**0 errores** (23 warnings preexistentes), `build` OK, `contract:check` OK. Python `packages/py/application`
+ `packages/py/analytics` **3196 passed**; runner api-python **8 passed**; `ruff` **All checks passed!**,
`import-linter` **4 kept / 0 broken**. Matriz de mutaciones **190/190** medidas, 0 sin fragmento,
restauración **byte a byte**. **Límite declarado:** el material PAPER real no existe todavía (la corrida
real es paso operativo del propietario).

## [1.93.0-beta] — AUTO-21 · `P(R>0)`, correlación entre estrategias y evidencia del régimen actual — 2026-09-25

**Fase estrictamente de medición/evidencia; SIN migración** (Alembic head sigue en `046_fill_reference_mid`)
y **sin tocar ningún fichero del freeze**. El reparto **no se mueve**: `auto18-v1` / `auto15-v1` — la
probabilidad y el co-movimiento **se publican, no reparten**. El esquema del artefacto **se mantiene**
(`auto20c_evidence_artifact_v1`) con claves **aditivas y opcionales**.

- **`P(R>0)`.** `ExpectancyInterval` gana `probabilityPositive` = fracción de las medias bootstrap
  **estrictamente `> 0`** de la **misma** distribución que ya encuadra el intervalo (un solo productor);
  sin bootstrap el valor es `None` y el hueco se declara (`no_cycles` / `insufficient_episodes`), **nunca un
  `0`**. Sello `ADAPTIVE_UNCERTAINTY_METHOD` → **`bootstrap_episodes_v2`**.
- **Calibración de la probabilidad.** Nueva pregunta `probability_positive_calibration`: compara la
  probabilidad **declarada** sobre el IS con la fracción positiva **realizada** del OOS por el error
  absoluto **medio** frente a tolerancia declarada (`0.20`); sin celdas con ambos términos ⇒
  `inconclusive`. `_aggregate` publica `probabilityPositiveOos` (por **ciclos**). Sello
  `CALIBRATION_METHOD` → **`walk_forward_calibration_v3`**.
- **Correlación entre estrategias** (módulo puro nuevo `auto_adaptive_correlation.py`). Alineación por
  **cubo temporal declarado** (`day` por defecto; `week`/`month`), Pearson sobre las medias de R de los
  cubos **compartidos** (`min_buckets = 4`); sin solape ⇒ `None` + `no_shared_buckets`, pocos cubos ⇒
  `insufficient_buckets`, serie constante ⇒ `constant_series`; orden-invariante. **No** se conecta al
  optimizador ni a la reserva.
- **Evidencia del régimen actual** (módulo puro nuevo `auto_adaptive_regime_evidence.py`). Para el régimen
  actual (flag `--current-regime` o el del ciclo más reciente **con régimen declarable**; `UNKNOWN` no fija
  el actual) publica, por estrategia, la celda `strategy × regime` **reutilizando el bootstrap de
  `AUTO-19A`**, o el hueco declarado (`no_evidence_for_regime`, `measuredN = 0`) — nunca el agregado.
- **Render y UI.** El stub `AUTO-21 (fuera de alcance)` **desaparece**: `Current regime` / `Current
  evidence` y el bloque `correlation (bucket=...)` publican lo medido (o `NO MEDIDO`), con espejo TS que
  **lee** (no recalcula) y bloque de correlación en la sección de evidencia.
- **Mutaciones `M182…M187`** (una por invariante): sello sin subir, probabilidad fabricada, sello de
  calibración sin subir, pregunta sin muestra mínima, correlación sin cubos publicando `0.0` y régimen
  inventado.

**Compuertas.** Frontend **1327 passed** (232 ficheros; con `--testTimeout=30000`), `typecheck` OK, `lint`
**0 errores** (23 warnings preexistentes), `build` OK, `contract:check` OK. Python analytics **1238
passed**, `ruff` **All checks passed!**, `import-linter` **4 kept / 0 broken**. Matriz de mutaciones
**187/187** medidas, 0 sin fragmento, restauración **byte a byte**. **Flake ajeno declarado**:
`backtests/core-r-scheduler.test.ts` agota su timeout de 5 s bajo la carga de la suite completa (fichero
sin tocar; aislado pasa).

## [1.92.0-beta] — AUTO-20F · cierre de las 2 P3 de la auditoría de v2.66 — 2026-09-25

**Frontend + un fichero Python de render; SIN migración** (Alembic head sigue en `046_fill_reference_mid`) y
**sin tocar ningún fichero del freeze**. El reparto **no se mueve**: `auto18-v1` / `auto15-v1`. Fase corta de
**precisión**, no de producto.

- **(P3-1) Corrección documental.** El `plan`/`audit-pack` de `v2.66` afirmaban que la matriz «formaliza como
  **M180**» el contrato TS-vs-Python. **No se sostenía**: M180 mutila el **render**
  (`auto_evidence_report.py`), no el instrumento (`auto_adaptive_calibration.py`); ese contrato es **vitest** y
  no entra en la matriz pytest. Redacción corregida con nota explícita (misma clase de sobre-afirmación que la
  fase anterior decía corregir).
- **(P3-2) Espejo exacto en el perímetro.** `_version_list` trata un valor **que no es lista** (escalar, objeto,
  cadena suelta) como **ausente** (`NO MEDIDO`), en vez de iterarlo — iterar `"orb-a"` producía
  `"o, r, b, -, a"`, que afirmaba haber medido algo que no se midió. Coincide con `asStringArrayOrNull` (TS).
  Tests en **ambos** lados y mutación **M181**.

**Compuertas** (a re-medir y sellar): frontend `test`/`typecheck`/`lint`/`build`/`contract:check`; python
analytics `pytest`/`ruff`/`import-linter`; matriz `M179`/`M180`/`M181`.

## [1.91.0-beta] — AUTO-20E · hardening de procedencia del AUTO EVIDENCE REPORT (deuda P3 de v2.65) — 2026-09-25

**Frontend + un fichero Python de render; SIN migración** (Alembic head sigue en `046_fill_reference_mid`)
y **sin tocar ningún fichero del freeze** (`auto_adaptive.py`, `auto_adaptive_data_gate.py`,
`auto_simulation_worker.py`, `auto_adaptive_journal.py`, `auto_adaptive_replay.py`,
`v2_43_governor_evidence.py`, `governor.json`). El reparto **no se mueve**: `auto18-v1` / `auto15-v1`.

**Cierra las 3 observaciones P3** no bloqueantes de la auditoría de `v2.65-beta` (ver
`docs/engineering/deuda-p3-post-auditoria-v2.65-2026-09-25.md`).

- **P3-1 — el «contrato de claves» ya es real.** El test del frontend deja de comparar la constante TS
  contra un literal propio y **lee el instrumento Python** (`auto_adaptive_calibration.py`), extrayendo las
  seis `CALIBRATION_QUESTION_*`. Se ha verificado que **cae de verdad**: renombrar una clave en Python pone
  el test rojo. Además, `frontend-ci.yml` incorpora ese fichero a sus filtros de ruta (si no, un cambio solo
  de Python no dispararía el workflow) y el render Python gana un test que ata sus filas a las claves
  canónicas.
- **P3-2 — la procedencia no puede contradecirse en silencio.** Si el `materialOrigin` de la raíz y el de
  `material` discrepan, la clasificación pasa a **`PROCEDENCIA DESCONOCIDA`** (nunca `PAPER REAL`) y se
  emite un aviso de integridad.
- **P3-3 — ausente ≠ vacío en el perímetro.** Un listado de versiones **ausente** se muestra `NO MEDIDO`
  (marcado como no concluyente); uno **vacío medido** se muestra `(ninguna)`. Cambiado **a la vez** en el
  módulo TS y en el render Python para no reintroducir divergencia; para artefactos reales (que siempre
  traen las listas) la salida es **byte-idéntica**.

**Tests y compuertas.** Frontend **1323 passed** (232 ficheros; +3), `typecheck` OK, `lint` **0 errores**
(23 warnings preexistentes), `build` OK y `contract:check` OK. Python analytics **1208 passed**, `ruff` OK y
`import-linter` **4 kept / 0 broken**. Matriz de mutaciones ampliada con **M179** (perímetro colapsado) y
**M180** (claves del render desalineadas).

**Alcance del render.** El único cambio de comportamiento en la salida de `render_evidence_report` es el de
las listas de perímetro **ausentes** (antes `(ninguna)`, ahora `NO MEDIDO`); ningún artefacto producido por
la cadena real cambia, porque siempre declara esas listas.

## [1.90.0-beta] — AUTO-20D · UI de procedencia del AUTO EVIDENCE REPORT — 2026-09-25

**Solo frontend, `+3` ficheros de producción y `+3` de test; SIN migración** (Alembic head sigue en
`046_fill_reference_mid`) y **sin tocar `packages/py` ni ningún fichero del freeze**. El reparto **no se
mueve**: `auto18-v1` / `auto15-v1`.

**El hueco que cierra.** `v2.64` selló el artefacto `auto20c_evidence_artifact_v1` y el render, pero el
resultado solo se leía en el JSON, el `.txt` y `stderr`: **no existía superficie de cabina** y un humano
podía mirar `Walk-forward efficiency 0.4213` y asumir que era su cuenta PAPER. Esta fase instala el **badge de
procedencia** del punto 14 de la auditoría de `v2.64`.

**La sección `Evidencia AUTO (AUTO-20D)`** (Consola operacional, primer nivel) muestra un badge SOURCE
imposible de malinterpretar: `PAPER REAL` (verde, única base de decisión), `FIXTURE SINTÉTICO` (ámbar, con
`NO UTILIZAR PARA DECISIONES`), `SIN MATERIAL · NO MEDIDO` (sin artefacto o sin material) y
`PROCEDENCIA DESCONOCIDA` (nunca se asume PAPER real). Separa los tres ejes (punto 11) sin renombrar
`materialOrigin`: origen / ejecución (`virtual / sin dinero real`) / dinero real en riesgo.

**La UI lee, no recalcula.** El módulo puro `auto-evidence-report.ts` valida el esquema (rechaza uno ajeno
con motivo), clasifica la procedencia, arma la vista con el `report` **verbatim** y avisa de una procedencia
incoherente (`realMoneyAtRisk=true`, ejecución no virtual, venue no `paper`, lectura saturada). Dos reglas
duras: **un conteo `null` se muestra `NO MEDIDO`** (nunca un `0` de relleno) y **un veredicto ausente es
`INCONCLUSIVE`**. El artefacto se **importa a mano** (fichero o pegado) y se archiva en local
(`bolsa-auto-evidence-archive-v1`, cap 10, dedupe por huella); sin endpoint ni migración.

**Tests.** 30 nuevos (report 19 · sección 7 · store 4) + el de la Consola actualizado; **1320 passed** (232
ficheros), `typecheck` OK y `lint` 0 errores. El contraste de claves de calibración queda **pinneado**: si
Python cambia la forma del esquema, el test cae.

**Hallazgo declarado.** La **corrida PAPER real (AUTO-20D) NO se ejecuta** en esta fase: el PostgreSQL local
tiene `sim_fill_finance_context` con `cycle_id` NULL en **todos** los fills (628) ⇒ el exportador bloquearía
con `exit 2`. El estado real es **`SIN MATERIAL · NO MEDIDO`**, que la UI declara; el bloqueo es por
**material, no por código**, y la corrida sigue siendo paso operativo del propietario (≥32 ciclos medidos por
estrategia).

## [1.89.0-beta] — AUTO-20C · primera calibración PAPER (virtual) + perímetro + invariante — 2026-09-25

**Frontera declarada, sin nueva arquitectura de motor y SIN migración** (Alembic head sigue en
`046_fill_reference_mid`). El veredicto real (`SUPPORTED` / `NOT_SUPPORTED` / `INCONCLUSIVE`) es un
**resultado**, no un error de software. El reparto **no se mueve**: `auto18-v1` / `auto15-v1`.

**El invariante que se instala: PAPER = dinero VIRTUAL.** Toda la cadena declara que el material y sus
veredictos proceden de una cuenta PAPER con **dinero virtual** y que **ninguna operación se ejecuta jamás
sobre XTB ni ninguna plataforma real** (AUTO permanece SIM-only). La fuente única es el nuevo módulo puro
`auto_evidence_report.py` (`EXECUTION_REALITY_VIRTUAL_PAPER`, `REAL_MONEY_AT_RISK = False`,
`EVIDENCE_ARTIFACT_SCHEMA = "auto20c_evidence_artifact_v1"`), que se propaga al manifest, a la nota del
exportador, al artefacto y al render. El exportador además **se bloquea con `exit 2`** (sin JSON) si
`settings.broker_venue != "paper"` (`NonPaperVenueError`): un artefacto PAPER no se sella con material de
otro carril.

**Perímetro declarado (deudas 21-24), sin tocar el universo medido.** `sim_durable_store.py` gana
`count_by_strategy_version` (agregado **aditivo**: `Protocol` + InMemory + Postgres, el worker intacto). El
manifest declara `observedStrategyVersions`, `versionsRequestedWithoutMaterial`,
`versionsObservedNotRequested`, `fillsTotalForAccount`/`fillsSelected`/`fillsExcludedNoVersion`/
`fillsExcludedOtherVersion`, `regimesPresent` y `materialOrigin` (**obligatorio**: `paper_real` vs
`synthetic_fixture`). La huella `material_fingerprint_v1` **no** incluye excluidos: sigue sellando el
universo medido. `riskReadSaturated = false` se documenta como "la lectura terminó de forma completa",
**no** "todas las reservas existen".

**Artefacto reproducible + render.** `auto_replay_battery.py` gana `--out PATH` y `--render PATH`
**opcionales** (sin ellos, stdout queda **byte-idéntico** al informe auditado). `build_evidence_artifact`
envuelve el informe **verbatim**; `render_evidence_report` imprime la tabla del punto 30 (Material /
Shrinkage / Effective-N / Interval coverage / Edge sign / Confidence / Coverage / Walk-forward efficiency),
declara `Current regime`/`Current evidence` como `AUTO-21 (fuera de alcance)`, `Allocation change = none`, y
recuerda la **regla de oro**: *`INCONCLUSIVE` por muestra insuficiente NO se arregla bajando
`min_is`/`min_oos`/`folds`*.

**Tests y mutaciones.** Puros nuevos `test_auto_evidence_report.py` y `test_auto_v64_auto20c_artifact.py`;
ampliación de `test_auto_v63_auto20b_material_manifest.py` (perímetro) y del E2E PG
`test_auto_v63_auto20b_export_e2e_pg.py` (2 fills sin versión y 2 de otra versión, cuantificados y no
medidos). Mutaciones nuevas **M175–M178** (excluidos falseados, observadas eliminadas, procedencia borrada,
artefacto no escrito).

**Paso operativo del propietario** (no lo fabrica la fase): con ≥32 ciclos medidos por estrategia, correr
export → `--walk-forward --out` sobre la cuenta PAPER **virtual** y conservar
`AUTO20C_REAL_PAPER_REPORT.json` + el render como artefacto reproducible, aceptando honestamente cualquiera
de los tres veredictos.

## [1.88.1-beta] — AUTO-20B.1 · el extra `[asyncio]` de SQLAlchemy se declara (re-sello) — 2026-09-25

**Re-sello de INFRAESTRUCTURA, sin cambios de producto.** El tag **`v2.63-beta` no se mueve**; el sello
vigente pasa a **`v2.63.1-beta`** (mismo árbol de `AUTO-20B` + este arreglo). Sin migración y sin tocar
el reparto (`auto18-v1` / `auto15-v1`).

**El defecto (preexistente, ajeno a `AUTO-20B`).** `packages/py/infrastructure` declaraba
`sqlalchemy>=2.0` **sin el extra `[asyncio]`**, y solo el lock (`uv.lock` → 2.0.51) garantizaba
`greenlet` (el shim que necesita `sqlalchemy.ext.asyncio`). El job **`Optimize lab` instala con pip
crudo, sin lock**: al publicarse **SQLAlchemy 2.1.0** —que movió `greenlet` al extra— la resolución
dejó de traerlo y el import murió con `ModuleNotFoundError: No module named 'greenlet'`. Las corridas
de `v2.62` (2026-09-24 19:52) estaban **verdes** porque aún resolvían 2.0.x: el fallo es del
**entorno**, no del material, y habría tumbado cualquier push de esa superficie.

**El arreglo.** `sqlalchemy[asyncio]>=2.0,<2.1` + `uv lock`: el extra viaja en el **metadato** del
paquete (ya no depende de que el lock lo traiga por suerte) y el techo mantiene la resolución de pip
alineada con la serie que el lock valida (2.1 **no** está evaluada en este repositorio, y se declara).

**Evidencia en frío** (venv limpio, `pip install -e` de los paquetes como hace el workflow):
`sqlalchemy 2.0.54` + `greenlet 3.5.6` + `sqlalchemy.ext.asyncio` importa **OK**; el lock sigue en
2.0.51 con `greenlet` 3.5.4.

**Compuertas re-medidas tras el cambio:** `ruff` ✅ · `lint-imports` 4 kept / 0 broken (626 ficheros) ·
`mypy` 500 ficheros / 0 errores · **3147 puros** ✅ · suites de `AUTO-20B` (E2E PG + completitud +
manifest) **18 passed** con `AUTO20B_EXPORT_PG_REQUIRED=1` ✅.

## [1.88.0-beta] — AUTO-20B Export E2E + oráculo same-material (V2.63) — 2026-09-25

**Sin migración** (Alembic head sigue en `046_fill_reference_mid`). Sin SHORT, sin UI, sin backfill y
**sin clave nueva en el journal durable**. **El sello del reparto NO se mueve: sigue en `auto18-v1`**
(`DATA_GATE_POLICY_VERSION` sigue `auto15-v1`). Fase de **certificación de material**: cierra la deuda
nº 1 de la [auditoría de `v2.62-beta`](./docs/engineering/auditoria-v2-62-auto-20-material-paper-real-2026-09-24.md).
El invariante que instala:

> **Una cadena de material no está certificada hasta que se recorre con PostgreSQL real, y lo que la
> lectura no pudo completar se declara (BLOQUEADO) en vez de publicarse sesgado.** Nada de esta fase
> mueve el reparto, el worker, el plan ni el journal.

1. **Completitud del volcado — el truncamiento silencioso desaparece.** `list_by_cycle_ids` gana
   `offset` (keyword-only) en el `Protocol`, en `InMemoryReservationStore` y en
   `PostgresReservationStore` (`.offset()` tras el `ORDER BY` total ya existente). El exportador recorre
   páginas hasta agotar el material: `--limit` pasa a ser **tamaño de página**. Si una página llena no
   aporta ids nuevos (el `offset` no avanza), **no puede afirmar completitud** y sale **`2`
   (BLOQUEADO)** sin imprimir JSON. El worker de `AUTO-9` no pasa `offset` ⇒ su lectura es
   **byte-idéntica**.
2. **Manifest de material.** El JSON del exportador lleva `material_manifest` (hermano de `note` y
   `cycles`, **nunca dentro**): conteos del MISMO material que mide el instrumento (`closedCycles`,
   `cyclesWithRisk`/`WithoutRisk`, `cyclesWithVersion`/`WithoutVersion`, `cyclesWithoutIdentity`,
   `costAppliedCycles`, `perVersion`, `regimeRead`, `cyclesWithoutRegime`, `reservationsRead`,
   `riskReadSaturated`), la base de riesgo declarada (`reservation_reserved_risk`) y la huella.
3. **Huella `material_fingerprint_v1`** (pura, determinista): sella el **universo medido** para poder
   comparar dos corridas sin abrir el JSON a mano. Normaliza los números por **valor**
   (`Decimal("100.000000")` ≡ `100` ≡ `"100.000000"`, que es lo que trae el JSON) y **no** toca los
   identificadores; el **instante de exportación no entra** a la huella.
4. **Propagación opcional al informe.** `auto_replay_battery.py` pasa el manifest como `material=` y
   `CalibrationReport.as_dict()` publica la clave **solo si se aporta**: sin manifest el informe queda
   **byte-idéntico** al ya auditado y `CALIBRATION_METHOD` sigue `walk_forward_calibration_v2` (es
   metadata de ENTRADA declarada, no cambia ninguna medición).
5. **E2E con PostgreSQL real + oráculo.** Fixture determinista (26 ciclos: A 12/9/3, B 8/8, C 5/0, un
   ciclo con dos versiones, dos regímenes, coste aplicado en 17) → exportador REAL (`main`, sin mocks)
   → JSON → calibración walk-forward, con cardinalidad contra un **oráculo independiente**, caso de
   `--limit` pequeño que demuestra la recuperación completa y test **same-material** (el informe
   durable `AUTO-7` y el material `AUTO-20` describen el MISMO universo, y el informe recalculado
   desde el JSON exportado sale **idéntico** al durable).

### Añadido

- **`auto_material_manifest.py`** (analytics, nuevo, puro) — `material_fingerprint`,
  `MATERIAL_FINGERPRINT_METHOD = "material_fingerprint_v1"`, `FINGERPRINT_FIELDS`.
- **`auto_material_manifest.py`** (application, nuevo) — `build_material_manifest`,
  `MATERIAL_RISK_BASIS = "reservation_reserved_risk"`.
- **`reservation_store.py`** — `offset` keyword-only en el `Protocol` y en los dos stores (aditivo).
- **`paper_cycles_export.py`** — paginación completa, `MaterialIncompleteError` → `exit 2` y
  `material_manifest` en el JSON.
- **`scripts/research/auto_replay_battery.py`** — lee el manifest y lo propaga (`material=`) + nota y
  huella por stderr.
- **`auto_adaptive_calibration.py`** — bloque `material` **opcional** (`as_dict()` solo lo emite si se
  aporta).
- **Tests** — `test_auto_material_manifest.py` (huella), `test_auto_v63_auto20b_material_manifest.py`
  (conteos/particiones), `test_auto_v63_auto20b_export_completeness.py` (fail-closed + battery) y
  `test_auto_v63_auto20b_export_e2e_pg.py` (E2E PG con gate fail-if-skipped), más los casos de
  paginación en `test_auto_v47_cycle_trace.py` y `test_portfolio_reservation_pg.py`.
- **Mutaciones `M169…M174`** — paginación desactivada, `offset` ignorado, `cyclesWithoutRisk` falseado,
  huella ciega al universo, bloque `material` inventado y manifest no propagado.
- **CI** — el E2E `_pg.py` entra en `--ignore` del job offline y se certifica en `auto-v2-durable-pg`
  (y en el paso PG del tag) con `AUTO20B_EXPORT_PG_REQUIRED=1`; los puros entran por los pases de
  directorio (el manifest de aplicación, **explícito**: ese directorio no tiene pase).

### Notas de compatibilidad

- **`AUTO-19A`/`AUTO-19B`/`AUTO-20` intactos**: `auto_adaptive_replay.py` (`statistical_oos_v1`) y el
  sello `walk_forward_calibration_v2` no cambian. Un informe **sin** manifest es byte-idéntico al ya
  auditado; con manifest cambia **solo** la clave `material`.
- `--limit` del exportador cambia de **tope** a **tamaño de página**: un valor pequeño ya **no** trunca
  el universo.
- **Sin migración:** `_ALEMBIC_HEAD` sigue en `046_fill_reference_mid`.

## [1.87.0-beta] — AUTO-20 Material PAPER real + cierre de O1/O2 (V2.62) — 2026-09-24

**Sin migración** (Alembic head sigue en `046_fill_reference_mid`). Sin SHORT, sin UI, sin backfill y
**sin clave nueva en el journal durable**. **El sello del reparto NO se mueve: sigue en `auto18-v1`**
(`DATA_GATE_POLICY_VERSION` sigue `auto15-v1`). Fase de **material + honestidad**: pone el material
PAPER real al alcance del instrumento de calibración y cierra las dos observaciones P3 de la
auditoría de `v2.61-beta`. El invariante que mantiene:

> **El instrumento mide el MISMO material que el informe durable, y lo que no se pudo medir se
> declara.** Nada de esta fase mueve el reparto, el worker, el plan ni el journal.

1. **O1 cerrado — el material no medible se DECLARA.** Una `strategyVersion` cuyos ciclos existen pero
   **ninguno** tiene R medible ya no desaparece en silencio: el informe publica
   `unmeasured_r:<version>`. Las filas **sin versión** (que también se descartaban mudas) salen como
   `unversioned_cycles`. Solo se nombra el hueco: ninguna estrategia entra por declararla.
2. **O2 cerrado — la ratio NO mezcla muestras distintas.** `walkForwardEfficiency` se calcula **solo
   sobre pliegues emparejados** (con IS y OOS a la vez), como exige el espejo de `optimize`. Se
   publican **cuatro conteos** (`foldCount`, `isFoldCount`, `oosFoldCount`, `pairedFoldCount`) para
   que un pliegue que no aporta a la media no se cuente como si aportara.
3. **Sello del instrumento subido.** `CALIBRATION_METHOD` pasa de `walk_forward_calibration_v1` a
   **`walk_forward_calibration_v2`**: la lectura cambió y el sello lo declara (dos informes con el
   mismo aspecto no pueden venir de instrumentos distintos).
4. **Costura pública del material con riesgo.** `adaptive_instrument_cycles` (`auto_self_evaluation_feed`)
   expone el material CON riesgo por la **MISMA** costura que el informe durable
   (`_cycles_with_risk`, `AUTO-16/17`): mismos ciclos, mismo cierre, misma fricción aplicada. Un
   segundo camino habría podido medir ciclos distintos en silencio.
5. **Exportador PAPER real.** `apps/api-python/scripts/paper_cycles_export.py` lee fills durables +
   reservas (`AUTO-9`) + régimen (`AUTO-10`) y vuelca el JSON del instrumento. **Sin PostgreSQL sale
   `2` (BLOQUEADO)**, nunca un JSON vacío leído como "sin edge".

**Por qué importa:** el material que produce `cycles_from_fills` **no trae base de riesgo**; sin
denominador el R no es medible y la calibración sobre ciclos reales saldría **vacía** — y ahí era
justo **O1** el que mordía (la estrategia desaparecía sin explicación).

**Declarado:** el camino durable del exportador está cableado y verificado por trozos, pero **no se
ejercita end-to-end** en esta fase (no hay fixture PG que siembre fills + reservas para él). El
fixture del instrumento sigue siendo **sintético**: la calibración publicada mide el instrumento, no
la estrategia.

### Añadido

- **`auto_adaptive_calibration.py`** — cierre de O1 (`unmeasured_r:<version>`, `unversioned_cycles`) y
  de O2 (`_aggregate` con WFE emparejado y cuatro conteos); `CALIBRATION_METHOD` → `…_v2`.
- **`auto_self_evaluation_feed.py`** — `adaptive_instrument_cycles` (público, aditivo; no cambia
  ninguna salida existente).
- **`apps/api-python/scripts/paper_cycles_export.py`** (nuevo) — exportador del material PAPER real.
- **Mutaciones M165–M168** — matan el silencio de O1, la ratio que mezcla, el conteo inflado y el
  material sin denominador.
- **Tests** — O1 (declarado / parcial no marcado / sin versión), O2 (emparejado y sin par), costura
  pública del material con y sin riesgo.

### Notas de compatibilidad

- **`AUTO-19A` intacto**: `auto_adaptive_replay.py` no se toca; su contrato `statistical_oos_v1`
  sigue igual, incluida su política de notas (el hueco heredado de O1 se **declara en la calibración**,
  no se cambia a escondidas en el replay).
- Un informe de calibración `v2` **no** es comparable campo a campo con uno `v1`.

## [1.86.0-beta] — AUTO-19B Calibración del intervalo y Walk-Forward (V2.61) — 2026-09-24

**Sin migración** (Alembic head sigue en `046_fill_reference_mid`). Sin SHORT, sin UI, sin backfill y
**sin clave nueva en el journal durable**. **El sello del reparto NO se mueve: sigue en `auto18-v1`**
(`DATA_GATE_POLICY_VERSION` sigue `auto15-v1`). Fase **solo medición**: el instrumento es puro y
read-only. El invariante que instala:

> **La incertidumbre no se declara calibrada: se mide.** Toda lectura de calibración viaja con su
> `sample`, su nivel declarado y su tolerancia declarada; sin muestra suficiente el veredicto es
> `inconclusive`, nunca `supported`. Ninguna métrica de calibración mueve el reparto.

`AUTO-19A` construyó el instrumento (intervalo por episodios + confianza de EDGE) y una batería con
**una** partición IS/OOS. Quedaba la pregunta que ahora se responde: **¿está bien calibrada esa
incertidumbre?** `AUTO-19B` añade:

1. **Walk-forward de ventanas CRECIENTES.** En vez de un split, cada estrategia se parte en `n_folds+1`
   segmentos cronológicos y se miden `n_folds` pares IS/OOS: el pliegue `i` entrena con todo lo
   anterior y testea con el segmento inmediatamente posterior (el último absorbe el resto). El IS jamás
   contiene su OOS, y los pliegues que no alcanzan los mínimos declarados **no se forman** (se
   declaran `skipped_strategy` / `insufficient_folds`).
2. **Calibración del intervalo.** `interval_coverage` compara la fracción observada contra el nivel
   declarado (`0.90` por defecto) con tolerancia declarada; publica `meanIntervalWidth` como
   diagnóstico. Una celda **sin** intervalo no cuenta como cubierta ni como descubierta.
3. **Calibración del signo del EDGE.** `edge_sign_calibration` mide el acierto de `edgeConfidence`
   (solo `HIGH`/`LOW`; `MEDIUM`/`UNKNOWN` quedan fuera) sobre el signo realizado, con muestra mínima.
4. **Calibración de la banda de medición.** `confidence_calibration` publica OOS por banda y decide con
   la comparación declarada (menor dispersión OOS en `HIGH`).
5. **Agregados del walk-forward** en R (`meanOosExpectancyR`, `stdOosExpectancyR`,
   `positiveOosFoldShare`, `oosCv`, `walkForwardEfficiency`), espejo de `aggregate_walk_forward_metrics`
   de `optimize`.
6. **Reutilización, no reimplementación.** Las tres preguntas de `AUTO-19A` (shrinkage, `effective_N`,
   cobertura) se reutilizan sobre los pliegues vía `measure_is_oos_row`, extraído de `_build_cell`: una
   sola aritmética de celda para las dos particiones.

### Añadido

- **`auto_adaptive_calibration.py`** (nuevo, puro) — `split_walk_forward_folds`, `CalibrationFold`,
  `CalibrationQuestion`, `CalibrationReport`, las seis preguntas y `aggregate`; config declarada
  (`CALIBRATION_METHOD = "walk_forward_calibration_v1"`, `CALIBRATION_FOLDS_*`,
  `CALIBRATION_COVERAGE_TOLERANCE_DEFAULT`, `CALIBRATION_EDGE_SIGN_FLOOR_DEFAULT`).
- **`auto_adaptive_replay.py`** — extracción aditiva de `measure_is_oos_row` (público) sin renombrar
  `_compare`/`_question_*` ni mover el split de `_build_cell`.
- **`scripts/research/auto_replay_battery.py`** — `--walk-forward` y `--folds`. **Sin el flag la salida
  es byte-idéntica** a la de `AUTO-19A`.
- **Fixture** `auto_calibration_cycles.json` (126 ciclos, 3 estrategias con 3 pliegues + una fina
  declarada como hueco); nota **SYNTHETIC** explícita. No se toca el fixture de `AUTO-19A`.
- **Tests** `test_auto_adaptive_calibration.py` (19): sin muestra, split cronológico/creciente,
  cobertura (cubierto/descubierto/sin intervalo), signo del EDGE, banda de medición, reutilización,
  determinismo/orden-invariancia, fixture medido de punta a punta y no-regresión de `AUTO-19A`.
- **Mutaciones `M159…M164`** (6 nuevas): walk-forward contaminado, cobertura fabricada, cobertura
  invertida, signo del EDGE sin muestra, un pliegue llamado walk-forward y ventana que no crece.
  Matriz completa `M1…M164` corrida con restauración byte a byte y huella `git status` idéntica.
- **CI** — el puro entra por el pase de directorio de `packages/py/analytics/tests` en
  `python-ci.yml` y `release-tag-ci.yml` (no hay costura nueva: el instrumento no se cablea al worker).

### Compatibilidad

- **Sin migración:** `_ALEMBIC_HEAD` sigue en `046_fill_reference_mid`.
- **Read-only:** no se tocan `auto_adaptive.py`, `auto_self_evaluation_feed.py`,
  `auto_simulation_worker.py`, `auto_adaptive_journal.py` (byte a byte), el gobernador ni la tabla
  estado→efecto. Sin UI, sin SHORT, sin backfill.
- La salida de `AUTO-19A` no cambia: sin `--walk-forward`, el CLI emite el mismo `ReplayReport`.

### Límites declarados

El fixture por defecto es **sintético y declarado**: mide el **instrumento**, no la estrategia real.
`P(R > 0)`, la correlación entre estrategias y el current-regime gating quedan **fuera** de v2.61. La
ejecución sobre ciclos PAPER reales es el paso operativo posterior.

## [1.85.0-beta] — AUTO-19A Incertidumbre del edge + Replay OOS (V2.60) — 2026-09-24

**Sin migración** (Alembic head sigue en `046_fill_reference_mid`). Sin SHORT, sin UI nueva y **sin clave
nueva en el journal durable** (la proyección por lista blanca `riskMultipliers` + `evidenceAxis` de
`auto_adaptive_journal.py` queda **byte a byte igual**). El gobernador y su evidencia siguen **intactos**
(diff vacío). **El sello del reparto NO se mueve: sigue en `auto18-v1`** (`DATA_GATE_POLICY_VERSION` sigue
`auto15-v1`). El invariante que instala:

> **Ninguna lectura de edge se publica como certeza ni como permiso.** La expectancy se publica con su
> **intervalo de incertidumbre**; la **confianza de medición** (`confidence`, ya existente) se separa de la
> **confianza de edge** (`edgeConfidence`); y ninguna de las dos mueve el reparto.

`AUTO-18` publicaba **cuánto** se había medido (`confidence`/`coverage`/`effective_N`) y una expectancy
encogida, pero **no** el **intervalo de incertidumbre** del número ni la **confianza de que haya edge**: un
punto sin intervalo es una certeza disfrazada. Esta pasada cierra los dos huecos y añade una batería de
validación:

1. **Intervalo de incertidumbre (`bootstrap_episodes_v1`).** Bootstrap de **percentil** que remuestrea
   **rachas de régimen** (episodios) **con reemplazo**, con **semilla declarada**: la incertidumbre respeta
   la MISMA noción de independencia que `AUTO-18` fijó en la muestra efectiva (100 ciclos de una sola fase
   no son 100 observaciones). El intervalo **contiene siempre a su punto**; sin ciclos medidos se declara
   `no_cycles` y con menos de `min_episodes` rachas **no se fabrica intervalo** (`insufficient_episodes`).
   `dispersion_r` (desviación de las medias bootstrap) da una lectura mínima de estabilidad.
2. **`edgeConfidence` — un eje PROPIO.** `HIGH`/`MEDIUM`/`LOW`/`UNKNOWN` derivados del **signo del
   intervalo frente a cero**, degradados un escalón (con suelo `LOW`) por cobertura baja, deterioro severo
   o base del neto degradada, cada uno con su nota. `UNKNOWN` = no-medición, **nunca** un `LOW` por
   defecto; `measurement=HIGH` con `edge=LOW` significa «sabemos bien que ahora mismo no hay edge».
3. **Replay OOS estadístico (`statistical_oos_v1`).** Instrumento **puro y read-only** que parte cada
   estrategia en tramo IS/OOS **cronológico**, re-aplica las estadísticas de decisión (shrinkage,
   `effective_N`, banda, cobertura) sobre el IS y las compara con la expectancy **realizada** del OOS.
   Responde con números y `sample` a las cuatro preguntas del auditor (**shrinkage**, **`effective_N`**,
   **banda HIGH vs LOW** y **cobertura del régimen**) con veredicto
   `supported`/`not_supported`/`inconclusive`; **nunca** emite veredicto sin muestra.

### Añadido

- **`auto_adaptive_uncertainty.py`** (nuevo, puro) — `ExpectancyInterval` (`bootstrap_episodes_v1`),
  `edgeConfidence`, `AdaptiveUncertainty` por `strategyVersion` **y por celda `strategy × regime`**,
  `percentile` determinista.
- **`auto_adaptive_replay.py`** (nuevo, puro) — split IS/OOS cronológico, `ReplayCell`/`ReplayQuestion`/
  `ReplayReport`, las cuatro preguntas y sus umbrales declarados (`REPLAY_*`).
- **`scripts/research/auto_replay_battery.py`** (nuevo, sin PG) — CLI que emite el `ReplayReport` JSON por
  stdout desde un JSON de ciclos (fixture determinista `auto_replay_cycles.json` por defecto).
- **`auto_adaptive_confidence.py`** — promoción a **público** de `regime_episodes`, `coverage_band`,
  `measured_r`, `regime_of` y `order_cycles_by_instant` (sin cambiar la semántica ni el resultado de
  `AUTO-18`): un solo productor de la semántica de episodios.
- **`auto_adaptive.py`** — `StrategyHealth.expectancy_interval`/`edge_confidence`, frame `uncertainty` en
  el plan y claves nuevas `expectancyInterval`/`edgeConfidence` en `evidence_for` (**aditivas**).
- **`auto_self_evaluation_feed.py`** — `build_adaptive_uncertainty_from_fills` (mismo material que
  `AUTO-18`, sin segundo FIFO) y su consumo en `auto_simulation_worker.py`.
- **Mutaciones `M149…M158`** (10 nuevas) en la sonda, con la matriz completa `M1…M158` corrida.
- **Tests nuevos** `test_auto_adaptive_uncertainty.py` (20) y `test_auto_adaptive_replay.py` (16), más la
  costura `test_auto_v60_auto19_uncertainty_seam.py` (lista explícita en los dos workflows de CI).

### Compatibilidad

- **Sin `uncertainty` el plan es byte-idéntico** a `AUTO-18`: el frame y las dos claves nuevas solo
  aparecen cuando hay lectura, y los campos nuevos tienen defecto `None`.
- La incertidumbre y el replay **no tocan la regla**: `recommend_allocation`/`_confidence_factor` y el
  sello `auto18-v1` quedan intactos. La lectura es **evidencia publicada**, nunca un permiso.
- El fixture del replay es **sintético y declarado**: mide el instrumento, no la estrategia real.

### Sello (v2.60-beta) — CI real medida

- **Tag anotado `v2.60-beta`** sobre el commit de fase **`cbd96bbe`**, `main` en **fast-forward**
  (`9898c51a..cbd96bbe`), tag empujado **de uno en uno** (sin `--follow-tags`). **Sin migración**: la
  guardia `_ALEMBIC_HEAD` sigue en `046_fill_reference_mid`, así que el tag cubre el paquete **a la
  primera**, **sin rojos y sin flakes**.
- **`Release tag CI`**
  [`35999631671`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35999631671) **GREEN a la primera**
  (`10 success` + `1 skipped`, `certify` en `success`); job `python` del tag **`2747 passed / 35 skipped`**
  (**+46** passed y **0** skips nuevos sobre `v2.59`), ruff `All checks passed!`, import-linter
  `4 kept, 0 broken` y mypy `Success: no issues found in 499 source files`.
- **`Python CI` per-commit del tag**
  [`35999631556`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35999631556) **`5/5` jobs verdes**
  (`quality` **`2736 passed / 38 skipped`**; los cuatro de PG incluidos: cierra el límite offline
  declarado). `Python CI` de `main`
  [`35999579254`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35999579254) **`5/5` verdes** con el
  mismo corte. `check-runs` del commit sellado: **`27` success + `1` skipped**.
- **Delta testeado:** **+46** tests sobre `v2.59` en los dos cortes (job `python` `2701` → `2747`; `quality`
  `2690` → `2736`), la cuenta exacta del tramo de la fase.
- **PR de auditoría** [#69](https://github.com/jvelasca/Bolsa_V1/pull/69): `audit-base-v2.59-beta` @
  `9898c51a` → `auto-19a-incertidumbre-edge-replay` @ `7d3c3f23` (**25 ficheros, `+10780/−21`**, 4 commits,
  los tres últimos docs-only), **`10/10` checks `SUCCESS`** (job `quality` **`2736 passed / 38 skipped`**),
  abierto **después** del sello y **no** vehículo de merge (`main` ya recibió la fase en fast-forward).

## [1.84.0-beta] — AUTO-18 Confianza estadística (V2.59) — 2026-09-24

**Sin migración** (Alembic head sigue en `046_fill_reference_mid`). Sin SHORT, sin UI nueva, sin cambio de
contrato de API ni de DTO y **sin clave nueva en el journal durable** (la proyección por lista blanca
`riskMultipliers` + `evidenceAxis` de `auto_adaptive_journal.py` queda **byte a byte igual**). El
gobernador y su evidencia siguen **intactos** (diff vacío). El invariante que instala:

> **Ninguna recomendación Adaptive puede pesar más de lo que su población independiente, homogénea,
> comparable y calibrada sostiene.** La evidencia se mide con `effective_N` **estadístico** (no con el
> bruto), se publica con su **cobertura por régimen** y su **fiabilidad por banda**, y solo compite en un
> eje cuando comparte `(net_r_basis, cost_model_version)`.

`AUTO-12` publicaba una confianza estadística, pero su `effective_n` era **la muestra bruta** (ciclos con R
medido): **100 ciclos dentro de una sola fase de mercado pesaban como 100 observaciones independientes**,
que es precisamente lo que no son. Y el metro con el que se midió el neto **no viajaba**, así que dos
versiones con modelos de coste distintos podían competir en el eje del R neto como si fueran comparables.
Esta pasada cierra los dos huecos:

1. **`effective_N` estadístico por episodios.** `effective_n = min(measured_n, episodes)`, donde
   `episodes` son las **rachas de régimen** de los ciclos medidos ordenados (un ciclo `UNKNOWN` forma su
   **propia** racha). Se publica el descuento declarado (`episode_discount`) y la cobertura por régimen
   como **eje propio** (`HIGH`/`MEDIUM`/`LOW`/`UNCOVERED`). La **calibración es descriptiva**
   (`ConfidenceCalibration`: banda → `n`/`mean_r`/`win_rate`/rango prometido/fiabilidad observada) y **no**
   mueve banda ni reparto; `shrunk_expectancy_r` se publica en cada fila/celda.
2. **El metro del coste viaja** (`costModelVersion` **aditivo** en `TradingCost.to_dict()`, recomputado de
   la firma del modelo) y un cambio de metro **separa series** (`_net_r_series` agrupa por
   `(basis, cost_model_version)`) y **bloquea** `decay`/eje (`COST_MODEL_TRANSITION`), en la misma línea
   que `AUTO-17` hizo con la base del neto.
   El sello del reparto sube a **`auto18-v1`**: aquí **sí** cambia la **regla** (la `n` del encogimiento).

**Deudas P2 cerradas en el mismo sello:** enums cerrados `NetRBasis` / `BasisTransition` con los **mismos
valores** de string (JSON byte-idéntico); invariante de dominio **un neto publicado declara su base**
(`affirms_declared_net_r_basis` + guarda en `_strategy_row`); estado declarado **`DATA_DEGRADED`** para «neto
sin base» (baja la banda, distinto del `UNKNOWN` inocuo); y documentado que **`MIXED` (heterogeneidad
interna) y `TRANSITION` (cambio temporal de base) son dos ejes distintos**.

### Añadido

- **`auto_adaptive_confidence.py`** — `measured_n`/`episodes`/`effective_n` (`_episodes`), cobertura por
  celda (`_coverage_band`), calibración descriptiva (`ConfidenceCalibration`, `_regime_calibration`),
  `shrunk_expectancy_r` (`_shrunk`), `COST_MODEL_TRANSITION` y `DATA_DEGRADED`, enums `NetRBasis`/
  `BasisTransition`.
- **`auto_self_evaluation.py`** — `cost_model_version` en `CycleR`/`NetRBasisSeries`, series por
  `(basis, cost_model_version)` (`_net_r_series`, `_cost_model_key`, `_cost_model_of`), `NetRBasis`,
  `affirms_declared_net_r_basis`.
- **`auto_adaptive.py`** — `_confidence_factor` con `effective_n` estadístico, `shrink_factors` publicado,
  evidencia con `measuredN`/`episodes`/`effectiveN`/`coverage`/`shrunkExpectancyR`/`shrinkFactor`; sello
  `ADAPTIVE_POLICY_VERSION = "auto18-v1"` (`DATA_GATE_POLICY_VERSION` sigue `auto15-v1`).
- **`portfolio_reservation.py`** — `TradingCostModel.cost_model_signature()`, `TradingCost.cost_model_version`
  y su clave aditiva `costModelVersion` en los dos `to_dict()`.
- **Mutaciones `M139…M148`** (10 nuevas) en la sonda, con realineos declarados de `M60`, `M125`, `M128`,
  `M131`, `M134`.
- **Costura nueva** `test_auto_v59_auto18_confidence_seam.py`.

### Compatibilidad

- Sin `confidence` el plan sale **byte a byte** como en `v2.58`; los campos nuevos tienen defecto seguro
  (`measured_n = effective_n` histórico, `cost_model_version=None`, `episodes=0`).
- Sin `costModelVersion` el informe es **byte-idéntico** a `v2.58`: el metro entra como clave **aditiva**.
- Los históricos quedan `None`/`undeclared` (declarado), nunca un metro inventado. **Sin backfill.**

## [1.83.0-beta] — AUTO-17 Integridad de la población de medida (V2.58) — 2026-09-24

**Sin migración** (Alembic head sigue en `046_fill_reference_mid`). Sin SHORT, sin UI nueva, sin cambio de
contrato de API ni de DTO y **sin clave nueva en el journal durable** (la proyección por lista blanca
`riskMultipliers` + `evidenceAxis` de `auto_adaptive_journal.py:58` queda **byte a byte igual**). El
gobernador y su evidencia siguen **intactos** (diff vacío). El invariante que instala:

> **Ningún número con el que Adaptive decide promedia dos bases de coste distintas: la base del R neto
> viaja con la evidencia, y una población mixta se declara y se abstiene, nunca se interpreta como mejora
> o deterioro.**

`AUTO-16` hizo que el R neto **declarara su base** (`estimated` / `applied_friction+modelled_commission`),
pero dejó dos huecos que esta pasada cierra:

1. **El round-trip del coste aplicado no era cuantitativo.** `applied_cost.py` declaraba `COMPLETE` un
   ciclo con solo ver los dos lados; un `BUY 100 / SELL 10` (ciclo abierto) medía la fricción de una
   operación que no terminó. Ahora `COMPLETE` exige **balance de cantidades** (`Σ buy qty == Σ sell qty`,
   tolerancia declarada) y el mapa aplicado se restringe a los ciclos que `cycles_from_fills` declaró
   **cerrados** (autoridad de cierre, sin segundo FIFO ni I/O nuevo).
2. **La base del neto no viajaba de extremo a extremo.** El agregado **declaraba** `mixed` pero seguía
   **promediando** poblaciones de base distinta, y ni la confianza ni el reparto veían la base. Ahora el
   agregado publica **dos series separadas** (`NetRBasisSeries`), con base homogénea el pooled sale **byte
   a byte** como antes y con `MIXED` el pooled **no se publica** (`None`); la confianza gana
   `net_r_basis` + `basis_transition`; el `decay` devuelve `UNKNOWN` si la base cambia entre ventanas (un
   salto de medida no es deterioro ni mejora); y el **reparto solo adopta el eje del R neto si todas las
   versiones que compiten comparten una base estable**, cayendo al eje histórico con nota declarada si no.
   El sello del reparto sube a **`auto17-v1`** (cambia la **regla**, no solo la procedencia).

**Opción A ratificada (dos series separadas):** pre-2.57 = `estimated`, post-2.57 = `applied`; **nunca**
se promedian. El detector puro `basis_transition` (`STABLE_ESTIMATED` / `STABLE_APPLIED` / `TRANSITION` /
`MIXED` / `UNKNOWN`) evita leer el cambio de base como señal. **Sin backfill:** el histórico pre-2.57 queda
`STABLE_ESTIMATED`, el post-2.57 `STABLE_APPLIED` y el periodo con ambos `TRANSITION`/`MIXED`. La base es
**recomputable** (`reference_mid` presente/ausente + comisión), así que no se persiste por ciclo.

### Añadido

- **`applied_cost.py`** — `AppliedLeg.quantity`, `_quantity_balanced`, notas
  `APPLIED_COST_UNBALANCED_ROUND_TRIP` y `APPLIED_COST_WITHOUT_CYCLE_CLOSURE`, y
  `applied_cost_from_fills(..., closed_cycle_ids=...)`.
- **`auto_self_evaluation_feed.py`** — `_cycles_with_risk` calcula el ciclo **una sola vez** (sin segundo
  FIFO) y pasa los `closed_cycle_ids` a `applied_cost_from_fills`.
- **`auto_self_evaluation.py`** — `NetRBasisSeries`, `_net_r_series`, `_basis_of` y
  `_pooled_net_expectancy` (pooled **ausente** si `MIXED`); `net_r_series` en `StrategySelfEvaluation` y
  `StrategyRegimeEvaluation`.
- **`auto_adaptive_confidence.py`** — `net_r_basis` + `net_r_series` en `RegimeConfidence` /
  `StrategyConfidence`, detector `basis_transition` y `decay` **gated** por la transición de base.
- **`auto_adaptive.py`** — `StrategyHealth.net_r_basis` / `basis_transition`, guardia
  `_net_basis_comparable`, nota `ADAPTIVE_CELL_NOTE_BASIS_UNSTABLE` y `evidence_for` publicando
  `netRBasis` / `basisTransition`; sello `ADAPTIVE_POLICY_VERSION = "auto17-v1"`
  (`DATA_GATE_POLICY_VERSION` sigue `auto15-v1`).
- **Mutaciones `M129…M138`** (10 nuevas) en la sonda, con el bloque de `AUTO-16` realineado.

### Compatibilidad

- Con base homogénea, el `net_expectancy_r` pooled y todo lo demás salen **byte a byte** como en `v2.57`.
- El camino sin `reference_mid` sigue publicando **el número de `v2.56`** y lo declara.
- `costEstimate`, `costApplied`, `costBasis` y `netRBasis` **siguen publicándose igual**: esta fase
  **añade** la dimensión `net_r_series` / `basis_transition`, no cambia contratos existentes.
- El flag Adaptive sigue **OFF por defecto**: con OFF el plan, el journal y la API son **byte a byte
  iguales** a `v2.57`.

## [1.82.0-beta] — AUTO-16 Coste REAL por ciclo (V2.57) — 2026-09-24

**Migración nueva** `046_fill_reference_mid`: Alembic head `045_adaptive_gate_state` → **`046_fill_reference_mid`**
(aditiva, **una columna `NULL`able, sin backfill**, `upgrade`/`downgrade` **simétricos e idempotentes**). Sin
SHORT, sin UI nueva, sin cambio de contrato de API ni de DTO y **sin clave nueva en el journal durable** (la
proyección por lista blanca `riskMultipliers` + `evidenceAxis` de `auto_adaptive_journal.py:58` queda **byte a
byte igual**). El gobernador y su evidencia siguen **intactos** (diff vacío). El invariante que instala: **el R
neto declara su BASE** — el coste que descuenta el cociente puede venir del **decisor** (estimado) o del
**simulador** (fricción **APLICADA**, medida contra el mid con el que construyó el precio), y dos netos con el
mismo aspecto y distinta base **no son comparables**:

```
reserva (coste ESTIMADO 25.0) ─┐
fills SIM (fricción APLICADA 2.5, con su mid de referencia) ─┴─► R neto = pnl − ¿cuál de los dos?
```

`AUTO-9` medía el R con el coste que el **decisor supuso**, y el que el **simulador aplicó** no entraba nunca…
y **no era reconstruible**: el mid de referencia vivía en la memoria del tick que construyó el precio y se
tiraba, así que la pata de **entrada** de un ciclo (liquidada en otro tick) habría quedado fuera de cualquier
cálculo en memoria. Si la base no viaja con el número, un cambio de procedencia se lee como un cambio de
rendimiento **justo en el eje con el que `AUTO-12`/`AUTO-13`/`AUTO-14` encogen, rampean y reparten capital**.
Cierra la **octava pregunta del epic**: `AUTO-9` *«¿cuánto vale?»* · `AUTO-10` *«¿de qué ciclo es?»* · `AUTO-11`
*«¿dónde vive su memoria?»* · `AUTO-12` *«¿cuánto puedo creérmelo?»* · `AUTO-13` *«¿están sanos los datos con
los que me lo creo, y cómo vuelvo?»* · `AUTO-14` *«¿el peso que reparto se midió en el régimen en el que voy a
operar?»* · `AUTO-15` *«¿sobrevive esa prueba a un reinicio?»* · **`AUTO-16` *«el coste que descuenta el neto,
¿es el que se pagó o el que se supuso?»***. Adaptive **sigue siendo recomendador read-only** y **el flag sigue
OFF por defecto**: con OFF el plan, el journal y la API son **byte a byte iguales** a `v2.56`.

### Añadido: la referencia cruda del fill (migración `046`) y el lector por ciclo

- **Migración `046_fill_reference_mid`** (`packages/py/infrastructure/alembic/versions/046_fill_reference_mid.py`):
  una columna `reference_mid` `Numeric(18,6)` `NULL`able en `sim_fill_finance_context`, **idempotente** (el
  patrón `_column_exists` de las `028`–`045`) y con `downgrade` **simétrico**. **Sin backfill:** no hay valor
  que inventar para las filas anteriores — la ausencia de referencia **es** el hecho, y un `0` de relleno
  diría «fricción gratis» en todo el histórico.
- **Fila ORM** `SimFillFinanceContextRow.reference_mid` (`tables.py:2248`).
- **Campo en el contexto** `SimFillFinanceContext.reference_mid` (`sim_durable_store.py:106`) con
  **normalización única** (`usable_reference_mid`, `:64`): un valor que no describe un precio (`None`, `NaN`,
  `≤ 0`) se guarda como **ausencia**, **nunca** como un `0`, y uno usable se normaliza a `Decimal` para que el
  mismo hecho no viaje con dos tipos. Y **no** tumba el settlement del fill (el fill es un hecho; su
  referencia puede faltar).
- **Escritura**: `simulated_settlement.py:331` pasa el `base_mid` del schedule y
  `sim_finance_context.persist_fill_finance_context(reference_mid=...)` (`:45`/`:61`/`:78`) lo persiste en la
  **misma** escritura del settlement que ya existía (**cero I/O nuevo**, **cero filas nuevas**).
- **Lector por ciclo** `list_by_cycle_ids` en los dos stores (`sim_durable_store.py:300` memoria, `:581` PG):
  **lector de verificación** del reinicio, **no** del turno (el tick nunca lo llama).
- **Guardia de head**: `_ALEMBIC_HEAD` se bumpea `045` → `046` **en el mismo paso**
  (`apps/api-python/tests/test_discovery_evidence_snapshot_pg.py:43`), que es exactamente el rojo que obligó a
  **re-sellar** `v2.56`.

### Añadido: el módulo puro `applied_cost` (la fricción que el simulador APLICÓ)

- `packages/py/application/src/bolsa_application/applied_cost.py`: `applied_leg` (`:157`) mide la fricción de
  **una** pata desde su precio y su mid de referencia —el signo se **mide** por dirección (comprar por encima
  del mid cuesta; vender por debajo también), el monto es una **magnitud** (un **coste**, nunca una rebaja) y
  una pata favorable se **declara** (`applied_cost_favourable_leg`) en vez de restar—; `_cycle_applied_cost`
  (`:200`) agrega el ciclo **exigiendo ida y vuelta** (media ida y vuelta es un **SUELO**: restarlo
  sobrestimaría el R del ciclo, así que se declara `PARTIAL` y no entra al neto); `applied_cost_from_fills`
  (`:244`) devuelve **una entrada por ciclo pedido**, con sus huecos declarados, y `applied_cost_is_complete`
  (`:274`) es el predicado del `COMPLETE`.
- **Sin `0` fabricado:** una pata sin referencia queda **sin medir** (y su motivo en la nota), jamás con
  fricción cero.

### Añadido: la base declarada (`costApplied`/`costBasis`/`netRBasis`) y el sello `auto16-v1`

- **`cycle_risk.py`**: `CycleRisk.cost_applied` + `cost_applied_measurement` (`:145`/`:157`), publicados por
  `to_cycle_fields` (`:161`, `costApplied` **con su medición**) y el pegador **puro** `attach_applied_cost`
  (`:348`): **solo un aplicado `COMPLETE` se pega**; sin evidencia aplicada el mapa se devuelve **tal cual**
  (la ruta sin productor queda intacta).
- **Un solo punto de cableado, sin I/O nuevo** (`auto_self_evaluation_feed.py:214`,
  `_risk_with_applied_cost`): los fills que el tick **ya** leía llevan su `reference_mid`, así que la fricción
  aplicada se recompone con **aritmética pura**. Por ese punto pasan las tres lecturas que lo consumen
  —informe `AUTO-7`, confianza `AUTO-12` y rampa `AUTO-13`—: un segundo productor podría medir un coste
  distinto en silencio.
- **`auto_self_evaluation.py`**: `CycleR.cost_applied`/`cost_basis` (`:416`/`:420`), `cycle_r` (`:435`) que
  compone el neto **con la comisión del MODELO** (`:195`: el schedule del simulador **no cobra comisión** —en
  SIM la comisión realizada es `0`—, así que restar solo la fricción dejaría el neto **más alto** por un motivo
  que no es una mejor ejecución, sino una parte del coste que se dejó fuera; **sin comisión cuantificada no se
  compone a medias** y el neto vuelve al estimado completo), `_net_r_basis` (`:1124`) y `netRBasis` en las dos
  filas del informe (`:768`/`:839`, con **defecto seguro** `None` = «no declarada»).
- **Sello**: `ADAPTIVE_POLICY_VERSION` → **`auto16-v1`** (`auto_adaptive.py:175`). **No** cambia la regla
  —ninguna condición de `_allocation_weights` se toca— pero **sí la procedencia de un input** del eje del R
  neto. El sello **sí se compara** sobre el journal (las filas históricas quedan declaradas como de otra
  política); el sello del **gate no se toca** (`DATA_GATE_POLICY_VERSION` sigue `auto15-v1`).
- **Desviación declarada respecto al plan** (y más estricta): el plan decía «persistencia… gateado por el
  flag»; la implementación **persiste siempre** —es la MISMA escritura del settlement, sin I/O nuevo— y lo que
  el flag gatea es su **uso**. Gatear la escritura dejaría un hueco **permanente** en el histórico el día que se
  encienda la lectura.

### Verificación y sello

- **Unit nuevos**: `test_applied_cost.py` (**9**) y `test_sim_fill_reference.py` (**9**).
- **Costura nueva con CONTROL** `apps/api-python/tests/test_auto_v57_auto16_applied_cost_seam.py` (**9**): la
  fricción de las **dos** patas llega al neto que lee el plan (`1.16` vs el `1.09` del estimado), **sin
  `reference_mid`** el neto es **el número de `v2.56` byte a byte** y su hueco queda declarado, **sin comisión**
  no se compone a medias, la pata de **otro tick** se compone, el aplicado **mueve los pesos** del reparto
  (la consecuencia que justifica el sello), y **cero I/O nuevo** (una lectura de fills por versión y **cero**
  por ciclo).
- **PG real nuevo** `apps/api-python/tests/test_auto_v57_auto16_applied_cost_pg.py` (**5**, job
  `auto-v2-durable-pg` con `APPLIED_COST_PG_REQUIRED=1`): roundtrip de la `046` (`upgrade`/`downgrade`), la
  `reference_mid` **sobrevive a una sesión nueva**, la fricción **se recompone fuera del proceso** que la midió,
  una fila sin referencia se declara sin fricción (jamás `0`) y la lectura por ciclo **no cruza cuentas**.
- **Tramo de la fase**: **`105 passed`** (`+5` PG), **0** rojos. **Delta simétrico fichero a fichero** contra
  `HEAD`: **9 rojos declarados y solo ésos** — **4** por el **sello** y **5** por la **guardia de head**—, más
  **un defecto medido y corregido dentro de la fase** (el campo `netRBasis` se añadió **sin defecto** y produjo
  **76 rojos** `TypeError`; se corrigió a defecto `None` = «no declarada», el trato de `sinkFailuresDurable`).
- **Mutaciones**: **10 etiquetas nuevas `M119…M128`** y la corrida **COMPLETA** da **`128/128` medidas**, **`0`**
  en `NADA`, **`0`** fragmentos ausentes, restauración **byte a byte** y huella `git status` **idéntica**.
- **Compuertas**: `ruff` **`All checks passed!`**, `mypy` **`0` errores / `499` ficheros** (el módulo puro
  nuevo), `lint-imports` **`4 kept, 0 broken`**.
- **Límites declarados**: la comisión **aplicada** no existe en SIM (el neto se completa con la del modelo y la
  base lo nombra); **sin backfill**; **solo se persiste la referencia**, no la fricción; la referencia se mide
  contra el mid **del simulador**; **sin UI** y **sin SHORT**; `governor.json` sin trackear.
- **Sello**: tag anotado **`v2.57-beta`** sobre el commit del paquete de cierre (`c5e14ae1`), `main` en
  **fast-forward** (`3081ed78..c5e14ae1`); **`Release tag CI`**
  [`35968175990`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35968175990) **GREEN a la primera**
  (`10 success` + `1 skipped`, `certify` en `success`), job `python` del tag **`2649 passed / 35 skipped`**
  (**+41** passed y **0** skips nuevos sobre `v2.56`) y `Python CI` per-commit del tag
  [`35968176009`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35968176009) **`5/5` jobs verdes**
  (los cuatro de PG incluidos: cierra el límite offline declarado); `check-runs` del commit sellado
  **`27 success` + `1 skipped`**. **No hubo re-sello** (la guardia de head se bumpeó en el paso 1, la
  lección de `v2.56`). Cifras en el §11 del
  [audit-pack](./docs/engineering/audit-pack-v2-57-auto-16-coste-real-por-ciclo-2026-09-24.md) y **PR de
  auditoría [#66](https://github.com/jvelasca/Bolsa_V1/pull/66)** abierto post-sello.

## [1.81.0-beta] — AUTO-15 Data Gate persistido (V2.56) — 2026-09-23

**Migración nueva** `045_adaptive_gate_state`: Alembic head `044_auto_cycle_trace` → **`045_adaptive_gate_state`**
(aditiva, **sin backfill**, `upgrade`/`downgrade` **simétricos e idempotentes**). Sin SHORT, sin UI nueva,
sin cambio de contrato de API ni de DTO y **sin clave nueva en el journal durable** (la proyección por
lista blanca `riskMultipliers` + `evidenceAxis` de `auto_adaptive_journal.py:58` queda **byte a byte
igual**). El gobernador y su evidencia siguen **intactos** (diff vacío, script `exit 0`). El invariante que
instala: **«no acusar sin prueba» sobrevive a un reinicio** — la racha de fallos **consecutivos** del sink
del gate de `AUTO-13` vivía **solo en la memoria del proceso**, así que

```
WORKER 1 → 2 fallos del sink (DEGRADED) → CRASH → WORKER 2 → 0 fallos → OK
```

y **no era reconstruible**: un fallo de escritura no dejó fila en `decision_journal_entries` y el ancla de
antigüedad mide *publicación*, no *error*. Cierra la **séptima pregunta del epic**: `AUTO-9` *«¿cuánto
vale?»* · `AUTO-10` *«¿de qué ciclo es?»* · `AUTO-11` *«¿dónde vive su memoria?»* · `AUTO-12` *«¿cuánto
puedo creérmelo?»* · `AUTO-13` *«¿están sanos los datos con los que me lo creo, y cómo vuelvo?»* ·
`AUTO-14` *«¿el peso que reparto se midió en el régimen en el que voy a operar?»* · **`AUTO-15`
*«¿sobrevive esa prueba a un reinicio?»***. Adaptive **sigue siendo recomendador read-only** y **el flag
sigue OFF por defecto**: con OFF esta fase **no ejecuta ni un I/O nuevo** y el runtime publicado es, en
comportamiento, el de `v2.53`.

### Añadido: la tabla del estado durable y su store (`adaptive_gate_state`)

- **Migración `045_adaptive_gate_state`** (`packages/py/infrastructure/alembic/versions/045_adaptive_gate_state.py`):
  tabla `adaptive_gate_state` con **PK `(account_id, engine_id)`** (misma clave con la que se identifica el
  motor Adaptive: con `(account_id)` a secas, dos motores de la misma cuenta compartirían racha y uno
  **curaría** el fallo del otro), `sink_failures` (consecutivos, `server_default='0'`), `last_failure_at`,
  `last_success_at` y `updated_at`, más el índice `adaptive_gate_state_account_failures_idx`
  `(account_id, sink_failures)` («¿qué motores de esta cuenta arrastran racha?»). Idempotente y simétrico
  (helpers `_table_exists`/`_index_exists`; `downgrade` retira el índice y después la tabla).
- **Fila ORM** `AdaptiveGateStateRow` (`tables.py`), espejo de `AutoKillStateRow`.
- **Store nuevo** `packages/py/application/src/bolsa_application/adaptive_gate_store.py`: contrato puro
  (`AdaptiveGateState` + `sink_failures_from_state` con clamp defensivo), **gemelo in-memory** con la misma
  semántica y `PostgresAdaptiveGateStore`. **Dos operaciones, y ninguna guarda la fila entera**:
  - `record_failure` — **incremento atómico** (`INSERT … ON CONFLICT (account_id, engine_id) DO UPDATE SET
    sink_failures = sink_failures + 1`): un `load`+`save` perdería fallos concurrentes, y la racha es justo
    el dato que no puede perderse.
  - `record_success` — **reset sin amplificación** (`UPDATE … WHERE sink_failures > 0`): sin racha viva no
    escribe **nada** (ni crea fila), así que un despliegue sano **no paga una escritura por tick**.
  - `commit` propio (patrón `kill_switch_store.py`) y **`rollback` + `raise`** en el fallo de escritura
    (contrato del sink de `AUTO-10`): el store escribe en la **misma sesión del tick**, así que una
    escritura fallida no puede dejar la sesión envenenada para el siguiente store del turno.
- **Sin backfill:** una fila ausente significa «no hay constancia durable de fallos» (racha `0`
  **declarada**), nunca un cero fabricado.

### Añadido: el contador durable en el worker (siembra, incremento y reset)

- **Siembra al arrancar** (`_v2_recover_adaptive_gate_streak`, `auto_simulation_worker.py`), **una vez por
  proceso** y **antes** del primer plan y de los atajos del lector del journal: el escenario en que más
  importa —journal **roto**, `read_ok = False`— es justo el que se perdía; sembrar después habría
  reiniciado la racha a `0` precisamente cuando hacía falta.
- **Gateado por `adaptive_enabled`**: con el flag OFF no hay lectura ni escritura nuevas (cero I/O).
- **Incremento** al fallar el sink y **reset** al publicar, ambos **fail-open declarados**: sin store o con
  lectura rota, la racha cae al proceso con `sinkFailuresDurable = false` y el motivo en el log — **nunca**
  se finge salud ni fallo.
- La racha durable **manda** cuando el store contesta: el número persistido sustituye al del proceso y se
  publica en el log del tick.

### Modificado: el gate declara la PROCEDENCIA de la racha y sella `auto15-v1`

- `DATA_GATE_POLICY_VERSION` → **`auto15-v1`**: cambia la **procedencia** de uno de los hechos.
- **No** cambia nada sellado del gate: umbrales (`sink_failures_stale = 3`, `journal_gap_blocked = 10`,
  `evaluation_cycle_seconds = 60.0`), tabla estado→efecto y precedencia `BLOCKED > STALE > DEGRADED > OK`
  quedan **byte a byte iguales**; tampoco se toca `ADAPTIVE_POLICY_VERSION` (sigue `auto14-v1`: la regla de
  **reparto** no cambia y subirla sería mentir sobre ella).
- **Hecho nuevo `sinkFailuresDurable`** en `DataGateReading.as_dict()`, **por defecto `false`**: sin
  declaración del llamante **no** se afirma durable, y el gate da el **mismo** estado con la racha durable
  que con la de proceso (la procedencia se **declara**, no graduía).
- **Sin consecuencia de mismatch:** `policy_version_mismatch` que recibe el gate sale del **estado
  Adaptive**, no de `DATA_GATE_POLICY_VERSION`, así que este sello **no** marca un tick `STALE` en filas
  históricas (a diferencia de `auto14-v1`, que sí se compara sobre el journal).

### Verificación

- **Unit del gate** (`test_auto_adaptive_data_gate.py`) **29 → 32** y **unit nuevo del store**
  (`test_adaptive_gate_store.py`, **10 tests**); **costura nueva**
  `apps/api-python/tests/test_auto_v56_auto15_data_gate_durable_seam.py` (**9 tests**) por el camino real
  del worker y **con control negativo** (sin store, el reinicio lee `0` y el gate vuelve a `OK`); **PG real
  nuevo** `apps/api-python/tests/test_auto_v56_auto15_data_gate_pg.py` (**6 tests**, job
  `auto-v2-durable-pg` con `ADAPTIVE_GATE_PG_REQUIRED=1`: roundtrip de la `045`, racha que **sobrevive a la
  sesión nueva**, incremento atómico por clave, reset sin amplificación y sesión del tick **usable** tras
  un fallo de escritura). **Tramo de la fase: `51 passed`** (+ `6` de PG), `0` rojos.
- **Delta simétrico fichero a fichero contra `HEAD`** (nunca restando totales): **`0` rojos**. Un solo
  fichero de test modificado (`test_auto_adaptive_data_gate.py`: su versión de `HEAD` da **`29 passed`**
  contra el código nuevo) y tres **nuevos**. **Desviación medida y declarada:** el plan preveía «rojos
  declarados» (el sello y el campo nuevo) y la medida dice **cero** — el literal `auto13-v1` no estaba
  fijado por ningún test de `HEAD` y `sinkFailuresDurable` es **aditivo** en `as_dict()`. Restauración
  verificada por `sha256`.
- **Matriz de mutaciones ampliada** (`M108…M118`, **11 etiquetas**: racha que se resetea al reiniciar,
  fallo que no persiste, racha durable leída pero ignorada, reset amplificando, store leyendo la fila de
  **otra** cuenta, estado ilegible tratado como **sano** y como **fallo**, sello sin subir,
  `sinkFailuresDurable` afirmado sin store y —añadidas al implementar el contrato de sesión— escritura y
  reset fallidos que **no** limpian la sesión del tick): la corrida **completa** da **`118/118` medidas** y
  **`0` etiquetas en `NADA`**, con restauración **byte a byte** y la huella `git status` **idéntica**
  (`intacto: la sonda no altero el arbol`).
- **Compuertas**: `ruff check packages/py apps/api-python --config pyproject.toml` **`All checks passed!`**,
  `mypy` con el comando de CI **`0` errores en `498` ficheros`** e `import-linter` **`4 kept / 0 broken`**.
  *(Trampa medida: `ruff check <rutas>` **sin** `--config pyproject.toml` resuelve el `pyproject` del
  paquete y devuelve falsos `I001` —también sobre `kill_switch_store.py`, ya certificado—.)*
- **Guardia de head de Alembic bumpeada en el CI del tag** (`test_discovery_evidence_snapshot_pg.py:43`:
  `_ALEMBIC_HEAD` `044_auto_cycle_trace` → `045_adaptive_gate_state`): el primer CI del tag salió **rojo**
  por esa constante (**5** aserciones, solo en los jobs PG) y obligó a un **fix + re-sello** del tag a
  `8ad54416`; se verificó **replicando los dos jobs PG** contra PostgreSQL real: `51 passed` y `21 passed`.
- **Lo que no se pudo medir aquí**: la batería offline **completa** de los jobs `quality`/`python` del tag
  (su recolección incluye suites PG que importan `asyncpg`, ausente, y el teardown de sesión del conftest
  de `apps/api-python` exige PostgreSQL). **Ese límite lo cerró la CI del tag** — y fue justo ahí donde
  apareció la guardia de head sin bumpear (ver arriba), ya corregida: `Release tag CI`
  [`35928080874`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35928080874) **GREEN** (`10 success` +
  `1 skipped`), job `python` del tag **`2608 passed / 35 skipped`** (**+22** passed, **0** skips nuevos
  sobre los `2586 / 35` de `v2.55`) y `check-runs` del commit sellado **`23 success` + `1 skipped`**.
- **Re-sello declarado (no silencioso):** el tag `v2.56-beta` se **borra y se re-crea** en el commit del fix
  (`8ad54416`), no en el del paquete de cierre (`c62ac459`), porque **un CI de tag rojo no certifica nada**;
  `c62ac459` permanece en la historia con su rojo **declarado** y el `1.81.0-beta` **no** cambia (sin `+1`
  de parche). Dos rojos iniciales más, en **tests preexistentes ajenos a la fase**, se declararon y se
  re-ejecutaron: el test PG intermitente de `V2.46` (`test_concurrent_auto_pg.py`, `1` rojo en `5` corridas
  medidas) y el teardown de vitest que envenena el exit code con los **`1290`** tests en verde.

### Límites declarados

- **Solo se persiste la racha**, no el estado del gate ni el plan: el gate sigue siendo una **lectura** del
  tick.
- **Sin TTL ni decadencia:** una racha durable de un proceso muerto mantiene el gate degradado hasta la
  **primera publicación**, que la resetea («se cura en un tick»). Un TTL sería una heurística no declarada;
  una racha vieja es prueba **real** de que hubo fallos.
- **Granularidad `(account_id, engine_id)`**, no por venue ni por sink.
- **Peor caso declarado:** si el **reset** falla tras publicar, la racha durable se queda viva —el proceso
  pierde la memoria de la curación— hasta el siguiente reinicio, que la vuelve a sembrar.
- **Fuera de alcance, sin tocar:** la **UI** de `AUTO-7`…`AUTO-15` y el **coste REAL** por ciclo (hoy
  estimado, así que el R neto cae a `PARTIAL`). Quedan declarados para `AUTO-16`.
- **`governor.json` sigue sin trackear** y **el flag Adaptive sigue OFF por defecto**: esta fase **no se
  ejecuta** en producción hasta un flag explícito.

## [1.80.0-beta] — AUTO-14 Reparto por CELDA de régimen (V2.55) — 2026-09-23

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, sin UI nueva,
sin cambio de contrato de API ni de DTO y **sin clave nueva en el journal durable** (la entrada
`adaptive_recommendation` proyecta por lista blanca `riskMultipliers` + `evidenceAxis`, así que la base de
celda vive en el **plan** y en la **traza del tick**, nunca en la evidencia durable). El gobernador y su
evidencia siguen **intactos**. El invariante que instala: **el reparto no puede mejorar su peso con una
celda que no se ha medido** — una celda sin muestra suficiente, una celda ausente, un R neto no medido,
una celda medida no positiva o un régimen ilegible **no mueven el peso**; esa versión cae al **global** de
su fila y el hueco se **declara**. Cierra la sexta pregunta del epic: `AUTO-9` *«¿cuánto vale?»* · `AUTO-10`
*«¿de qué ciclo es?»* · `AUTO-11` *«¿dónde vive su memoria?»* · `AUTO-12` *«¿cuánto puedo creérmelo?»* ·
`AUTO-13` *«¿están sanos los datos con los que me lo creo, y cómo vuelvo?»* · **`AUTO-14` *«¿el peso que
reparto se midió en el régimen en el que voy a operar?»***. Adaptive **sigue siendo recomendador
read-only** y **el flag sigue OFF por defecto**: con OFF el camino de producción es **byte-idéntico** a
`v2.53`.

### Añadido: la selección de celda, pura y declarativa (`regime_cell_for`)

- **Helper nuevo** en `auto_adaptive.py` (`regime_cell_for`): el **único** sitio donde se elige celda, y
  devuelve **siempre** el par `(celda | None, motivo | None)`. Una celda es **utilizable** solo si existe,
  es `decisive` (su muestra alcanza `min_trades` y tiene el R medido en todos sus ciclos), su **R neto**
  está `COMPLETE` y es **positivo**.
- **Cinco huecos declarados con vocabulario propio** (`ADAPTIVE_CELL_NOTE_*`): `cell_regime_absent`
  (régimen `None`/`""`/`UNKNOWN`), `cell_not_found`, `cell_not_decisive`, `cell_net_unmeasured` y
  `cell_not_positive` — y `cell_axis_without_cell` cuando el eje del grupo es la **moneda**.
- **Normalización declarada y única** (`strip().upper()`): el plan recibe el régimen **canónico** del tick
  (el worker ya lo traduce con `to_market_regime`) y aquí **no** se traduce otra vez, porque un segundo
  mapa de alias podría **divergir** del que usó la rotación. Sin régimen legible no hay juicio de régimen.
- **Nunca se hereda**: no se elige otra celda, ni la de otra versión, ni la de otro ciclo (la lección del
  §20/`M81`).

### Modificado: el reparto pesa con la celda del régimen del tick

- `_allocation_weights` devuelve ahora `_AllocationSources` (eje, pesos y **declaración** de celda) y
  acepta `cells_by_version`/`regime` **keyword-only opcionales**: **sin ellos el reparto es byte-idéntico**
  al de `v2.54` (el patrón de `AUTO-12` con `confidence=None`).
- **La celda afina el PESO, nunca la composición**: el eje y el numerador se siguen decidiendo por la
  **fila** (`decisive` + expectancy positiva; R neto `COMPLETE` cubriendo a **todo** el grupo), y la celda
  se consulta **solo para quien ya competía**. Ni añade ni quita competidores.
- **Con el eje de moneda no se aplica celda alguna** (la celda mide R, no moneda: no se fabrica un
  cociente paralelo) y **todas** las que compiten lo declaran.
- Sigue **suma-preservado**, acotado a `[0, 1]` y **sin ceros**, y la **rampa de `AUTO-13` sigue siendo el
  techo** (`m_final = min(m_reparto, escalón)`), aplicada **después** del reparto.
- **El encogimiento de `AUTO-12` usa la banda de la CELDA** (`StrategyConfidence.by_regime` →
  `RegimeConfidence`): si el peso salió de la celda, se encoge con **su** `effective_n`/`decay`; si salió
  del global, con la de la estrategia. Encoger un peso de celda con la muestra **agregada** (que mezcla
  regímenes que no se parecen) reintroduciría el *winner chasing* que `AUTO-12` cerró.

### Modificado: la base de celda se declara sin tocar nada sellado

- `AllocationPlan` gana `cell_axis`, `cell_used` y `cell_fallback` con lecturas propias (`cell_for`,
  `cell_note_for`) y **su `as_dict()` NO cambia**: sigue publicando `riskMultipliers` + `evidenceAxis`, el
  frame que selló `AUTO-13`.
- La base de celda se publica en el **nivel del plan** (`AdaptivePlan.as_dict()['allocationCells']`), con
  campo propio, junto a `regimeUndetermined` y `shrinkage`; el **tick la declara** en el log
  (`auto_sim v2 adaptive allocation cells`), **sin cambio de firma**.
- **El contrato durable de `AUTO-11` queda byte a byte igual** (`_ALLOCATION_KEYS` proyecta las dos claves
  selladas) y el test de la costura lo fija con una celda **presente**.
- **`ADAPTIVE_POLICY_VERSION` → `auto14-v1`** (cambia la regla de asignación), con el test del sello
  renombrado **con nombre**. **Consecuencia declarada y medida:** el mismatch de política marcará las filas
  históricas `auto13-v1` como `STALE` **un tick**; se cura con la primera escritura, **no** resetea el
  contador (continuidad de política) y **no** se ejecuta con el flag OFF. No se relaja nada de `AUTO-11`.

### Verificación

- **Unit**: `test_auto_adaptive.py` **78 → 90** (**+12**: `regime_cell_for` y sus cinco huecos, celda
  decisiva que **mueve** el peso, celda fina que **no**, régimen ilegible, eje de moneda, composición
  intacta, ejes sin mezclar, shrink con la banda de la celda, rampa como techo, `allocationCells` en campo
  propio y reproducibilidad sin celdas).
- **Costura nueva** `apps/api-python/tests/test_auto_v55_auto14_regime_cell_allocation_seam.py` (**6
  tests**) por el **camino real del worker** y **con control**: una celda **sin muestra** no mueve el peso
  y una **decisiva** sí, la composición no cambia y la rampa sigue topando, el tick **declara** la base de
  celda, la proyección del journal es **byte-idéntica** con una celda presente y el sello declara `STALE`
  **sin resetear** el contador.
- **Tramo de la fase**: **`119 passed`** (`test_auto_adaptive.py` 90 + `..._v53_...` 9 + `..._v54_...` 14 +
  `..._v55_...` 6), `0` rojos.
- **Delta simétrico fichero a fichero contra `HEAD`** (nunca restando totales): **5 rojos** en la versión de
  `HEAD` de los tres ficheros modificados, con **2 causas declaradas** —el contrato de celdas
  (`test_regime_cells_alone_do_not_move_rotation_or_allocation`) y el **sello** `auto13-v1` → `auto14-v1`
  (que aparecía dentro de tres tests distintos)— y **ninguna** regresión de comportamiento. El plan
  declaraba «2 rojos»: se publica la **cifra medida** (5 nodos, 2 causas), no la prevista.
- **Matriz de mutaciones ampliada** (`M99…M107`, **9 etiquetas**: celda fina moviendo peso, fallback sin
  declarar, versión sin celda cayendo a `0`, ejes mezclados por fila, celda de otra versión, régimen
  ilegible eligiendo celda, celda `PARTIAL` tratada como medida, shrink con la banda de la fila y rampa
  `AUTO-13` esquivada con peso de celda): la corrida **completa** da **`107/107` medidas** y **`0`
  etiquetas en `NADA`**, con restauración **byte a byte** y la huella `git status` **idéntica**
  (`intacto: la sonda no altero el arbol`).
- **Compuertas**: `ruff check packages/py apps/api-python --config pyproject.toml` **`All checks passed!`**
  (el primer `ruff` de la fase mordió un `UP035` de la costura nueva y se corrigió), `mypy` con el comando
  de CI (`--follow-imports=silent`) **`0` errores en `497` ficheros** e `import-linter`
  **`4 kept / 0 broken`**.
- **Lo que no se pudo medir aquí**: la batería offline **completa** de los jobs `quality`/`python` del tag
  (su recolección incluye suites PG que importan `asyncpg`, ausente, y el teardown de sesión del conftest
  de `apps/api-python` exige PostgreSQL). **Ese límite lo cierra la CI del tag, medida.**
- **CI del tag `v2.55-beta`** ([run `35889751810`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35889751810)):
  **GREEN** con **`10 success` + `1 skipped`** (`playwright (integrated E2E, opt-in)`) y `certify
  (aggregate + artifact)` en `success`; job `quality` del tag `ruff` **`All checks passed!`** y `pytest`
  **`2575 passed / 38 skipped`** (**+7** passed y **+3** skipped sobre los `2568 / 35` del sello
  `v2.54-beta`; la causa de los `+3` skipped **no se atribuye**: delta medido y declarado), los **4 jobs
  PG** (`grammar-discovery-pg`, `auto-v2-durable-pg`, `lifecycle-pg`, `paper-forward-pg`) **verdes** y
  `check-runs` del commit sellado (`e29e6227`) **`26 success` + `1 skipped`**. `main` en **fast-forward**
  (`6fad572d..e29e6227`) con `Python CI`, `Frontend CI`, `Optimize lab` y `Gitleaks` **verdes**. El tag se
  empujó **suelto** (`git push origin v2.55-beta`, sin `--follow-tags`).

### Límites declarados

- El reparto por celda **solo** actúa sobre el eje del **R neto medido**; con el eje de moneda el reparto es
  global y lo **declara** (`cell_axis_without_cell`): no hay moneda medida por régimen y no se inventa.
- La celda **nunca** cambia quién compite: solo el peso relativo de quien ya competía.
- Una celda medida pero **no positiva** cae al **global** (el reparto **afina**, no castiga): es una
  decisión de producto declarada.
- **Fuera de alcance, sin tocar:** el **Data Gate persistido** (hoy el contador de fallos se pierde al
  reiniciar) y la **UI** de `AUTO-7`…`AUTO-14`. Quedan declarados para `AUTO-15`.
- **`governor.json` sigue sin trackear** y **el flag Adaptive sigue OFF por defecto**: el reparto por celda
  **no se ejecuta** en producción hasta un flag explícito.

## [1.79.0-beta] — AUTO-13 Adaptive Data Gate + recovery gradual (V2.54) — 2026-09-23

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, sin UI nueva,
sin cambio de contrato de API ni de DTO y **sin clave nueva en el journal durable** (la entrada
`adaptive_recommendation` proyecta claves explícitas: el hueco de régimen y el encogimiento viven en el
plan y en la traza del tick, nunca en la evidencia durable). El gobernador y su evidencia siguen
**intactos**. El invariante que instala: **ninguna estrategia puede ser castigada por una deuda de los
datos** — un dato incompleto se **declara** y **limita la adaptación**, nunca se convierte en «esta
estrategia es mala»; una vuelta de pausa se **gana** con evidencia medida, nunca por el paso del tiempo;
y un régimen que no se pudo leer **no** acusa a nadie. Cierra la quinta pregunta del epic: `AUTO-9`
*«¿cuánto vale?»* · `AUTO-10` *«¿de qué ciclo es?»* · `AUTO-11` *«¿dónde vive su memoria?»* · `AUTO-12`
*«¿cuánto puedo creérmelo?»* · **`AUTO-13` *«¿están sanos los datos con los que me lo creo, y cómo
vuelvo?»***. Adaptive **sigue siendo recomendador read-only** y **el flag sigue OFF por defecto**: con
OFF el camino de producción es **byte-idéntico** a `v2.53`.

### Añadido: el Data Gate, puro (`auto_adaptive_data_gate.py`)

- **Módulo nuevo** (`packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_data_gate.py`):
  sin I/O, sin estado y **orden-invariante**. Es un gate de **EVIDENCIA**, no de riesgo: gradúa la salud
  de lo que Adaptive sabe de sí mismo y **nunca** sustituye al gobernador, al kill switch ni a los gates
  duros — solo decide **cuánto puede adaptar** Adaptive con la evidencia que tiene (audit §21).
- **Cuatro estados con su efecto DERIVADO** (`_EFFECT_BY_STATUS`, única fuente: no puede publicarse un
  estado con un efecto incoherente): `OK → ADAPTS`, `DEGRADED → LIMITS`, `STALE → FREEZES`,
  `BLOCKED → NO_ADAPT`. La **precedencia** `BLOCKED > STALE > DEGRADED > OK` hace que el estado grave
  **absorba** los motivos menores (`notes` los acumula y ordena) en vez de esconderlos.
- **Cadencia declarada** y antigüedad en **ciclos**: `DataGatePolicy.evaluation_cycle_seconds = 60.0`
  (validado) y el helper puro `journal_age_cycles(...)`. Un instante ausente, ilegible o **posterior a
  `now`** devuelve `None` («no se pudo medir»), que **no** bloquea: no se supone juventud ni se inventa
  antigüedad.
- **Sin dato no se degrada ni se premia**: que el llamante no aporte un hecho (`None`) se declara
  (`evidence_not_provided`) y **no** cambia el estado — es lo que mantiene **byte-idéntico** el
  comportamiento cuando el gate no se aporta, el mismo patrón que dejó `AUTO-12` con `confidence=None`.
- **Política versionada** (`DATA_GATE_POLICY_VERSION = "auto13-v1"`, `sink_failures_stale = 3`,
  `journal_gap_blocked = 10`): cambiar los umbrales o la tabla estado→efecto **exige** subir la versión.

### Añadido: las dos fuentes de verdad del gate, con su límite declarado (§21)

- **Contador en memoria** de fallos **consecutivos** de `_v2_journal_adaptive_recommendation`: se
  incrementa en el `except` y **un éxito RESETEA** la racha (una publicación sana no arrastra el fallo
  aislado). Detecta el fallo al instante, pero se pierde al reiniciar.
- **Ancla durable**: `AdaptiveStateReading.last_published_at` (el `asOf` de la evidencia **más nueva** del
  journal) alimenta `journal_age_cycles`. **Sobrevive a un reinicio**, pero un journal sano y antiguo no
  prueba que esté roto — de ahí la regla que cierra el diseño:
- **Regla de corroboración**: el ancla **solo bloquea si hay un fallo de escritura propio**
  (`_v2_adaptive_gate_journal_age` devuelve `None` sin fallos). Sin ella, un Adaptive OFF o una pausa larga
  quedarían `BLOCKED` para siempre: `BLOCKED ⇒ adaptive = None ⇒ no se escribe ⇒ journal más viejo`, un
  bloqueo **permanente** que se habría cerrado a sí mismo.

### Modificado: el cableado del gate en el plan Adaptive

`_v2_build_adaptive_plan` acepta `gate: DataGateReading | None = None` (opcional: `None` ⇒ comportamiento
histórico) y lo **compone** con hechos que el tick **ya midió** (`_v2_adaptive_data_gate`): **cero I/O
nuevo**. Los cuatro efectos:

- **`OK` (`ADAPTS`)**: mismos argumentos y plan **byte-idéntico** a `v2.53`.
- **`DEGRADED` (`LIMITS`)**: `shrink=False` — el reparto **deja de usar** la confianza estadística de
  `AUTO-12` y cae a su eje histórico, pero la banda **medida** se sigue publicando en
  `healthByStrategy`/`evidence_for`. La **protección** se conserva entera (pausas vivas, cooldowns y las
  pausas **nuevas** por salud).
- **`STALE` (`FREEZES`)**: además, **ninguna reactivación nueva** (decisión ratificada: **solo en el
  worker**, recortando el contador que **entra** a `recommend_rotation` por debajo de `min_pause_cycles`
  —el contador **real** sigue creciendo y los **umbrales de rotación no se tocan**—, así la pausa se
  mantiene con el motivo mecánicamente cierto `cooldown` mientras el gate se declara en el log).
- **`BLOCKED` (`NO_ADAPT`)**: `adaptive = None` declarado, **sin fila de journal**; el contador de
  cooldown **no avanza** ese tick, así que nada se reactiva por olvido.

Dos decisiones finas medidas: la **completitud del gate son los ejes que Adaptive EXIGE** (resultados y
riesgo), **no** el `measurement_completeness` de la confianza —que combina el net-R **opcional**, cuyo
hueco cae por diseño al eje moneda de `AUTO-9`—, porque con aquel cualquier despliegue sin coste medido
quedaría `DEGRADED` y apagaría `AUTO-12` (**M82**); y **`regime_available` acepta los dos ejes** (canónico
`TREND_UP` y operativo `BULL_TREND`), declarando ausencia solo con `None`, `""`, `UNKNOWN` y `RISK_OFF`
(**M81**).

### Añadido: `RECOVERING` y la rampa de reincorporación por evidencia (§23/§24)

- **Estado operativo derivado** (`ADAPTIVE_STATE_ACTIVE`/`PAUSED`/`RECOVERING`) en
  `AdaptivePlan.operational_states` con `state_for(...)`. **No es un modo de la rotación**: quien pausa y
  reactiva sigue siendo `recommend_rotation` con su hysteresis y su cooldown.
- **Rampa declarada**: `ADAPTIVE_RECOVERY_STEPS_DEFAULT = (0.25, 0.50, 0.75, 1.00)` y
  `ADAPTIVE_RECOVERY_STEP_CYCLES_DEFAULT = 3`, campos de política validados (escalones en `(0, 1]`,
  estrictamente crecientes, paso `>= 1`). `recovery_reading(...)` sube **solo con evidencia medida
  positiva posterior al corte** y vuelve al **suelo** declarándolo con deterioro (`decay == SEVERE` o
  expectancy reciente `<= 0`) o con hueco de fechas.
- **Se aplica como techo**: `m_final = min(m_reparto, escalón)`, después del reparto y antes de publicar,
  así que la evidencia durable lleva el valor **realmente aplicado**. **Solo estrecha**, nunca ensancha y
  **nunca** deja a nadie en `0` (el escalón máximo devuelve la versión a peso pleno = recuperación
  cumplida).
- **Memoria derivada, sin estado propio**: el lector durable **siembra** `reactivated_at` (corte
  **probado**: la fila anterior de la racha tiene que estar **pausada**; un turno ilegible corta la
  búsqueda y **no** se inventa una reincorporación) y el proceso **fecha la transición en el tick en que
  ocurre** (`_v2_adaptive_reactivated_at`), recalculando el plan si la observa con el proceso vivo —sin
  eso, la versión correría un tick a peso pleno antes de que la rampa entrase.
- **Evidencia medida con un solo cociente**: `recovery_evidence_from_fills(...)` reusa los **mismos**
  fills del tick y el **`cycle_r`** del informe (nada de un segundo cociente paralelo); una pausa viva
  **descarta** su escalón (la protección manda sobre la rampa).
- **`ADAPTIVE_POLICY_VERSION` sube a `auto13-v1`**: cambia la regla de asignación ⇒ sello nuevo, con el
  test del sello actualizado **con nombre**.

### Modificado: el fallback declarado del §20 y los tres ejes separados (§29)

- **Un régimen que no se pudo leer no decide nada**: `None`, `""`, `UNKNOWN` y `RISK_OFF` son **huecos
  declarados**, nunca un régimen adverso ni favorable. El tick lo publica como evidencia incompleta
  (`regime_absent` ⇒ `DEGRADED`) y la rama adversa de `recommend_rotation` **no** puede dispararse.
  **Control medido**: el régimen adverso **real** del tick (`market_regime_gate`, p. ej. `BEAR_TREND`, que
  el plan traduce al de mercado `TREND_DOWN`) **sí** la arma — sin ese control, «no se pausa» también
  pasaría con una rotación muerta.
- **El hueco del cruce se declara**: `StrategyHealth.regime_undetermined` conserva el par
  `(régimen, motivo)` que publica `declared_regime` —un `UNKNOWN` legítimo (sin celda decisiva) deja de ser
  indistinguible de un régimen mal medido—; `AdaptivePlan.regime_undetermined` lo publica en **campo
  propio**, **ordenado por versión** (la reproducibilidad no puede depender del orden de las filas) y
  **derivado** de la salud, no recalculado, para que no pueda divergir del cruce que usó la rotación; y el
  tick lo declara (`regimeUndetermined` + `fallback: strategy_evidence`). **Nunca** se asume `RANGE` ni se
  hereda el régimen de otro ciclo: la rotación decide con la evidencia **global** de la estrategia.
- **Medir ≠ usar** (`shrink`/`shrinkage`): `build_adaptive_plan(..., shrink=)` permite que el reparto
  vuelva a su eje histórico **sin** borrar el hecho medido. `ACTIVE` + datos `DEGRADED` + calidad `LOW` es
  un estado **legal** y legible entero, y los tres ejes —operativo, datos y calidad— viajan en campos
  propios: **ninguno se disfraza de otro**.

### Verificación

- **Costura nueva** `apps/api-python/tests/test_auto_v54_auto13_regime_fallback_seam.py` (**7 tests**:
  hueco del tick, `UNKNOWN` explícito, **control adverso real**, fallback declarado sin lector, cruce
  determinado y los tres ejes sin compartir campo) más las de los pasos anteriores
  (`..._data_gate_seam.py` **9**, `..._data_gate_wiring_seam.py` **10**, `..._recovery_seam.py` **14**) y
  ampliación de `test_auto_adaptive.py`, `test_auto_adaptive_data_gate.py`,
  `test_auto_adaptive_recovery.py` y `test_auto_self_evaluation_feed.py`.
- **Delta simétrico**: las versiones de `HEAD` de los ficheros de test tocados dan **1 rojo NOMBRADO**
  (`test_degraded_stops_using_the_confidence_but_keeps_the_protection`, que afirmaba el contrato viejo de
  `DEGRADED` —`confidence=None`—): es **exactamente** el cambio declarado del §29 (la fase entrega la
  confianza como evidencia medida y retira solo su **uso**; el reparto resultante es el mismo).
  **Ninguna otra regresión oculta.**
- **Matriz de mutaciones ampliada** (`M72…M98`, **27 etiquetas**: estado→efecto invertido, `OK` por
  defecto, contador sin reset, ancla sin corroborar, cadencia ignorada, `BLOCKED` adaptando, `STALE`
  reactivando, completitud por el eje opcional, rampa por tiempo, rampa que ensancha, rampa que llega a
  `0`, evidencia anterior al corte, memoria no sembrada, transición sin fechar, régimen ilegible tratado
  como adverso, hueco no publicado, fallback no declarado y encogimiento inapagable, entre otras): la
  corrida **completa** da **`98/98` medidas y `0` etiquetas en `NADA`**, con **98** restauraciones
  **byte a byte** y la huella `git status` de los ficheros tocados **idéntica** antes y después
  (`intacto: la sonda no altero el arbol`).
- **Dos realineos declarados** (una sonda desalineada **afirma** cobertura que no tiene): `M21` se quedó
  sin fragmento cuando el renombrado `weight → share` del paso 4 (exigido por `mypy`) y **vuelve a morder
  en 10 tests**; `M71` quedó **ambigua** al aparecer `confidence=confidence` dos veces en el worker y se
  ancló al par `confidence` + `shrink` de la llamada al plan.
- **Sonda endurecida para Windows**: con ~98 reescrituras seguidas de los mismos ficheros, `open('wb')`
  devolvía `OSError [Errno 22]`; ahora escribe a un temporal y **reemplaza atómicamente** (`os.replace`)
  con reintentos y, si no entra, **aborta sin tocar el fichero** (nunca deja el mutante dentro).
- **Compuertas**: `ruff check packages/py apps/api-python --config pyproject.toml` **`All checks passed!`**,
  `mypy` con el comando de CI (`--follow-imports=silent`) **`0` errores en `497` ficheros** e
  `import-linter` **`4 kept / 0 broken`**. Tramo `AUTO-13` (analytics + application + costuras)
  **`202 passed`** (4 unit: 78 + 29 + 26 + 29; 4 costuras: 9 + 10 + 14 + 7) y el bloque `auto-*` offline de `apps/api-python` (25 ficheros `test_auto_*`, sin los que exigen PostgreSQL) **`288 passed`**.
- **PR de auditoría externa [#63](https://github.com/jvelasca/Bolsa_V1/pull/63)**: la fase entera viaja en
  la rama `auto-13-adaptive-data-gate` con **`28 success` + `1 skipped`** sobre el commit sellado
  (`54a3b86a`), todos en verde (`playwright (integrated E2E, opt-in)` es el skip declarado). La verificación offline
  **completa** de `quality`/`python` **no se pudo reproducir en la máquina** (su recolección incluye suites
  PG que importan `asyncpg`, ausente, y el teardown de sesión del conftest de `apps/api-python` exige
  PostgreSQL); **ese límite lo cierra la CI del tag, medido**.
- **CI del tag `v2.54-beta`** ([run `35857892968`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35857892968)):
  **`10 success` + `1 skipped`** (`playwright (integrated E2E, opt-in)`) con **`certify (aggregate + artifact)`**
  en `success`; job `python` (offline) **`2568 passed / 35 skipped`** (**+109** sobre los `2459 passed / 35 skipped`
  de `v2.53-beta`), `ruff` `All checks passed!`, `import-linter` `4 kept, 0 broken` y `mypy` `0` errores en `497`
  ficheros; los otros cuatro workflows del tag (`Python CI`, `Frontend CI`, `Fase 2 scientific`, `Optimize lab`)
  **GREEN**; `check-runs` del commit sellado **`38 success` + `1 skipped`**; y `main` (`54a3b86a`, en
  **fast-forward** desde `d08e66e5`) con `quality` **`2557 passed / 38 skipped`** y los cuatro jobs PG en verde.
- **Sello:** tag anotado **`v2.54-beta`** sobre **`54a3b86a`** (empujado **de uno en uno**, sin `--follow-tags`).

### Límites declarados

- **El gate no es un permiso**: limita la adaptación; no ejecuta, no pausa dinero y no toca al gobernador
  (audit §21: «Risk Engine continúa funcionando»).
- **El contador de fallos es de proceso** (se pierde al reiniciar); el ancla durable es el journal y su
  antigüedad **solo bloquea corroborada** por un fallo propio.
- **La retención de `STALE` usa el cooldown**: con `min_pause_cycles <= 1` no habría mecanismo y el hueco
  se declararía en el log (inalcanzable con la política de la casa, `= 3`).
- **La rampa nunca ensancha ni inventa**: `min` con el reparto, suelo `0.25`, subida **solo** por evidencia
  medida; sin fechas legibles no sube y lo declara.
- **El gate no se persiste** (es una lectura del tick): persistirlo, junto al reparto por celda de régimen,
  queda declarado para **`AUTO-14`**.
- **Sin UI** para `AUTO-7`…`AUTO-13`, **sin backfill**, **sin migración** (head `044_auto_cycle_trace`) y
  **`governor.json` sin trackear**. **El flag Adaptive sigue OFF por defecto**: el Data Gate y la rampa
  **no se ejecutan** en producción hasta un flag explícito.

## [1.78.0-beta] — AUTO-12 Confidence + calidad estadística (V2.53) — 2026-09-23

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, sin UI nueva,
sin cambio de contrato de API ni de DTO, **sin clave nueva en el nivel superior del payload del journal**
(la confianza añade cuatro campos dentro de las filas de `healthByStrategy`). El gobernador y su
evidencia siguen **intactos**. El invariante que instala: **ninguna recomendación Adaptive pesa más de lo
que su evidencia estadística sostiene** — una muestra fina se **declara** (`confidence`), no se castiga a
ciegas; una mejora reciente que contradice el histórico se **declara** (`decay`), no se convierte en pausa
automática. Adaptive **sigue siendo recomendador read-only**: lo único que cambia es **cuánto pesa** su
recomendación cuando la evidencia es fina.

### Añadido: la lectura de confianza, pura (`auto_adaptive_confidence.py`)

- **Módulo nuevo** (`packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive_confidence.py`):
  sin I/O y sin estado, **orden-invariante**. Reutiliza lo que ya existía en vez de reinventarlo —
  `aggregate_by_regime` (`AUTO-9`) sobre **dos rebanadas** de los ciclos ordenados, `sample_quality_from_n`
  como base de banda y `combine_measurements` para la completitud **compuesta**.
- **`sample_size` frente a `effective_n`**: `trades` cuenta ciclos, pero `expectancy_r` promedia solo los
  ciclos **con R medido**. Publicar la muestra bruta **afirma** una base que el número no tiene; `effective_n`
  es el denominador real. El caso medido: **40 ciclos con 4 medidos ⇒ muestra de 4**, `risk_coverage = 0.1`
  y banda `LOW` con su nota.
- **Completitud compuesta**: `combine(r_measurement, net_r_measurement, pnl_coverage)`. Sin coste medido el
  R neto es `UNKNOWN` y la completitud **no** puede ser `COMPLETE`. `risk_coverage`, `cost_coverage` y
  `regime_coverage` viajan **por separado** porque no medir el denominador de R, no medir el coste y no
  declarar el régimen son tres huecos distintos.
- **`decay` declarado** (`NONE`/`MILD`/`SEVERE`/`UNKNOWN`): `recent ≥ long·0.75` ⇒ `NONE`;
  `recent < long·0.75` y `recent ≥ 0` ⇒ `MILD`; `recent < 0` ⇒ `SEVERE`. Si alguna ventana no está medida,
  la reciente no llega al mínimo o no hay instantes legibles ⇒ `UNKNOWN` (se declara, no castiga por sí
  solo). **No añade motivo de pausa**: la rotación queda `byte-idéntica` con y sin confianza.
- **`confidence` con bandas declaradas** (`LOW`/`MEDIUM`/`HIGH`): base por banda de muestra y tres ajustes
  en orden — completitud no `COMPLETE` baja un nivel, `decay SEVERE` baja un nivel y **`decay UNKNOWN` pone
  TECHO `MEDIUM`**: no se premia lo que no se pudo leer.
- **Lectura vacía declarada**: sin ciclos no hay ceros mudos — `ADAPTIVE_CONFIDENCE_NO_CYCLES` y
  `confidence_for(...)` devuelve `None`.

### Añadido: el eje de recencia honesto (aditivo, sin migración)

- **`SimFillFinanceContext.created_at`** (aditivo; la columna PG ya existía, así que **no hay migración**):
  el store PG lo proyecta en `get`, `get_many` y `list_for_strategy_version`; el doble `InMemory` lo acepta
  y **declara** que su orden es por `execution_id`, en vez de fingir cronología.
- **`closedAt` en el ciclo** (`cycles_from_fills`): el instante del **último** fill del ciclo —la fecha del
  **resultado**, no la de la entrada—. Un **ciclo anónimo** (sin `cycle_id`) no reclama instante; un fill
  sin fecha legible no borra el cierre medible de los demás. **AUTO-7 queda byte-idéntico**: sin
  `created_at`, la tupla de ciclos es exactamente la histórica y ninguna fila lleva `closedAt`.
- **Orden por instante parseado** (patrón de `cycle_risk.py`), con el no-parseable al final y **declarado**
  (`recent_undated`). Sin fechas legibles, la ventana reciente **no se inventa**: `recent_available = False`
  y `decay = UNKNOWN`. La ventana **long** se sigue midiendo, porque no necesita fechas.
- **Costura del feed** `build_adaptive_confidence_from_fills(...)`: confianza e informe salen del **mismo**
  material (los mismos `fills` + `cycle_risk`), sin segundo productor y **sin I/O nuevo**.

### Modificado: el reparto encoge por muestra (protege del *winner chasing*)

- **`recommend_allocation(..., confidence=None)`** y **`build_adaptive_plan(..., confidence=None)`**: sin
  la lectura, el plan es **byte-idéntico** al histórico (mismo patrón que `by_regime` en `AUTO-9`). Con ella,
  el peso de cada estrategia **decisoria positiva** se encoge `w' = w · n/(n + k)` **antes** de normalizar,
  con `k = ADAPTIVE_CONFIDENCE_PRIOR_DEFAULT = 20.0` (campo nuevo de `AdaptivePolicy`); con
  `decay == SEVERE`, un factor adicional declarado (`ADAPTIVE_SEVERE_DECAY_FACTOR_DEFAULT = 0.5`).
  Se normaliza **como siempre** (`(w'/Σw')·count`) y se acota a `[0, 1]`, así que el reparto sigue
  sumando-preservando y **ninguna activa queda en 0**: encoger es **redistribuir**, no eliminar.
- **Una estrategia sin edge decisorio conserva el multiplicador neutral (1.0)**: la confianza fina **solo**
  actúa sobre un edge **medido** — ausencia de dato ≠ dato malo. Es el caso exacto del audit: `+2R/N=12` no
  puede llevarse el peso pleno frente a `+1R/N=180`.
- **`ADAPTIVE_POLICY_VERSION` sube a `auto12-v1`**: la regla de asignación cambió ⇒ sello nuevo, y el test
  del sello se actualiza **con nombre**.
- **`StrategyHealth`** gana `confidence`, `recent_expectancy_r`, `long_expectancy_r` y `decay`, y
  `AdaptivePlan.evidence_for()` los publica ⇒ la confianza viaja en el journal durable de `AUTO-11`
  **dentro de `healthByStrategy`**, sin clave nueva y sin tocar el contrato (que queda **byte a byte
  igual**, igual que `auto_adaptive_recovery.py`).

### Cableado: una lectura por tick, cero I/O nuevo

- `_v2_build_adaptive_plan` construye la confianza desde los `fills` que **ya leyó** para el informe:
  **una** lectura por versión (medido con un store que cuenta llamadas). Si la ventana reciente no está
  disponible, se registra un `warning` con los huecos en vez de fingirla; si la lectura de fills revienta,
  el plan es `None` (**fail-closed declarado**, comportamiento histórico) y el `error` queda con nombre.

### Verificación

- **+50 tests** medidos **fichero a fichero contra `HEAD`**: +21
  `test_auto_adaptive_confidence.py` (nuevo) · +9 `test_auto_v53_auto12_confidence_seam.py` (nuevo) · +11
  `test_auto_adaptive.py` (`HEAD` 44 → 55) · +9 `test_auto_self_evaluation_feed.py` (`HEAD` 13 → 22). Los
  dos ficheros **modificados**, en su versión de `HEAD` contra el código de la fase, dan **56 pasan / 1
  rojo nombrado** (el sello de versión, actualizado con nombre): sin regresiones ocultas.
- **Matriz de mutaciones ampliada** (`M60…M71`, 12 etiquetas por `effective_n`, encogimiento, bandas de
  `decay`, techo por `decay UNKNOWN`, `recent_undated`, orden por instante, cobertura de coste, completitud
  compuesta, cierre por el primer fill y cableado del worker): **12/12 muerden** y la corrida **completa** da
  **`71/71` medidas y `0` etiquetas en `NADA`** con el árbol **intacto** (la trampa de `M39` de `V2.52`,
  usada aquí como gate explícito). La fase **realineó** la sonda heredada `M33` —su fragmento, la llamada
  *inline* al riesgo por ciclo, dejó de existir al medirlo **una sola vez** en una local compartida por
  informe y confianza— sin cambiar su intención: vuelve a morder con **3 rojos**. Se declara porque una
  sonda desalineada **afirma** cobertura que no tiene.
- **Compuertas**: `ruff` con el comando de CI (`All checks passed!`), `mypy` (`--follow-imports=silent`)
  **0 errores en 497 ficheros** e `import-linter` **4 kept / 0 broken**.
  Suites del área con la fase: `analytics` **1011 passed**, `application` **1876 passed** (5 errores
  **pre-existentes** de suites PG por `asyncpg` ausente en la máquina) y el bloque AUTO completo
  **1178 passed / 0 rojos**.
- **CI real del tag** (`v2.53-beta` → `a6655e6e`): `Release tag CI`
  [`35836248169`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35836248169) **GREEN** con **`10
  success` + `1 skipped`** (`playwright` opt-in) y `check-runs` **`27 success` + `1 skipped`** —la misma
  forma que `v2.52-beta`—; job `python` offline **`2459 passed / 35 skipped`** frente a los **`2409`** del
  tag anterior: **+50**, exactamente el delta de tests declarado arriba. `Python CI`, `Frontend CI`,
  `Optimize lab` y `Fase 2 scientific` del tag, también en **verde**. La verificación offline **completa**
  no se pudo reproducir en la máquina (suites PG que importan `asyncpg`); **ese límite lo cierra CI**, que
  es donde se midió.

### Límites declarados

- **`confidence` no es un permiso**: sigue siendo evidencia read-only; la autoridad es el motor determinista
  y el gobernador.
- **Ventanas finitas** (`recent = 30`, `long = 200`): con menos filas el número es un **suelo**
  (`recent_insufficient`), no una medida.
- **Sin fechas legibles no hay `decay`** (`recent_unavailable`): no se inventa cronología.
- **El `decay` se mide sobre `R` bruto**; el neto sigue siendo el eje **alternativo** de `AUTO-9` y exige
  `net_r_measurement == COMPLETE`, que un coste estimado no garantiza.
- **`AUTO-12` no toca la rotación** (el `decay` no genera pausas): el Data Gate
  (`OK/DEGRADED/STALE/BLOCKED`) y el recovery gradual (`RECOVERING`, `0.25→1.0`) son **`AUTO-13`**.
- **Sin UI** para `AUTO-7`…`AUTO-12` (deuda declarada), **sin migración**, **`governor.json` sin trackear**.

## [1.77.0-beta] — AUTO-11 Estado Adaptive durable y recuperación (V2.52) — 2026-09-23

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, sin UI
nueva, sin cambio de contrato de API. El gobernador y su evidencia siguen **intactos**. El invariante
que instala: **el estado Adaptive, o es durable, o se declara** — el **cooldown** (`min_pause_cycles`)
deja de vivir en la lista del proceso y se **reconstruye** del journal durable al arrancar, la
recomendación Adaptive queda **publicada** como evidencia (con el contador que **entró** a decidir) y el
rastro de ciclo se **reconcilia** al arrancar. Adaptive **sigue siendo recomendador read-only**: su
multiplicador sigue en `[0, 1]` y el motor determinista sigue decidiendo; lo único que cambia es **dónde
vive su memoria**.

### Añadido: la recomendación Adaptive, durable

- **`auto_adaptive_journal.py`** (nuevo, contrato puro): evento `adaptive_recommendation` e identidad
  **del turno** `dec-adap-<hash(cuenta, asOf)>` — un reintento del mismo turno **no duplica** evidencia
  y dos cuentas del mismo instante no colisionan; **sin sello de turno** se conserva el fallback
  aleatorio (identidad **única**, nunca compartida por accidente). `cycle_decision_id()` devuelve `None`
  sobre una identidad `dec-adap-*`: las dos historias (`AUTO-10` y `AUTO-11`) **no pueden compartir
  fila**.
- **El payload se proyecta por lista blanca** (`asOf`, `readOnly`, `policyVersion`, `regime`,
  `rotation`, `allocation`, `pausedCycles`, `healthByStrategy`): una clave nueva del plan **no** se cuela
  en la historia sin decidirlo. Cuatro reglas duras con test: **sin plan no hay fila** (`None`, no-op
  declarado, nunca una fila vacía que afirme una evaluación que no hubo); **régimen ausente = declarado**
  (`None`, nunca un `UNKNOWN` de relleno); **salud ausente = declarada** (`healthByStrategy` vacío);
  **`readOnly: true`** viaja en la fila como constancia durable del reparto de autoridad.
- **`pausedCycles` es el contador que ENTRÓ a decidir** (normalizado: `> 0`, sin `bool` s, sin claves en
  blanco, ordenado). Publicar el de salida afirmaría una decisión que el plan no consumió. El worker lo
  copia **antes** de `build_adaptive_plan` (`_v2_adaptive_paused_cycles_entered`).
- **Puerto de escritura**: `build_adaptive_recommendation_sink(session)` commitea él mismo (`append` +
  `commit`, porque la sesión del turno se cierra con `close()`) y hace `rollback` en el fallo —sin él, la
  sesión envenenada tumbaría el compromiso de capital del mismo turno—. La recomendación se publica
  **después** de `plan_v2_tick` y del compromiso de capital: **primero el dinero, después la traza**, así
  que el journal nunca registra una recomendación que el motor no llegó a consumir.

### Añadido: el cooldown, reconstruido del journal

- **`auto_adaptive_recovery.py`** (nuevo, puro sobre las filas): `rebuild_paused_cycles` rehace la racha
  **trailing** por versión con la MISMA regla del proceso vivo (una versión que no está pausada en un
  turno cuenta a 0 y corta su racha; aparece o no en el plan). Recorre las evaluaciones de **nueva a
  vieja** y **satura** en `min_pause_cycles + 1`: el único consumo del contador es `< min_pause_cycles` y
  `<= 0`, así que el valor exacto por encima del umbral da igual.
- **Una evaluación por TURNO**: dos filas con el mismo `decision_id` son la **misma** evaluación escrita
  dos veces (reintento del sink), no dos turnos. Se colapsan antes de contar (`collapsed` lo declara):
  contarlas dos veces **alargaría** el cooldown afirmando un turno que no ocurrió.
- **Cuatro huecos declarados y distintos**: `read_ok=False` (la fuente durable **no se pudo leer**: «no
  leí» nunca se disfraza de «no hay pausas»), `insufficient_history` (la ventana **no** se llenó: la racha
  es un **suelo**), `unreadable` (filas sin el contrato de rotación usable: corta la racha y se cuenta,
  fail-closed) y `policy_version_mismatch` (la historia mezcla versiones; **no se reescribe**, se declara).
- **Continuidad de política**: el contador **se conserva** a través de un cambio de `policyVersion`
  —resetearlo sería exactamente el bug que esta fase cierra— y desde el turno siguiente mandan los
  umbrales de la política en curso, que entra al lector **por parámetro** (`build_adaptive_state_reader`,
  no por copia). `insufficient_history` distingue «leí y no había» de «no pude leer», y la lectura es
  **invariante al orden de las filas** (orden por instante, con el ilegible al final).

### Añadido: reconciliación del rastro de ciclo

- **`auto_cycle_reconciliation.py`** (nuevo, read-only) + **`list_recent_with_cycle`** en
  `reservation_store` (Protocol + `InMemory` + `Postgres`, por la columna `cycle_id` con índice desde
  `044`): cruza los ciclos con **capital comprometido** con los que el lector de `AUTO-10` **confirma** y
  declara **cuatro desajustes que no son el mismo hecho** — `missing` (con motivo: `regime_absent` o
  `regime_unconfirmed`), `unrequested` (un hueco **operativo**, no un journal roto), `not_derivable` (la
  ausencia es estructural) y `orphan` (traza sin reserva). Cierra la ventana
  `RESERVATION COMMITTED → CRASH → NO JOURNAL` que `AUTO-10` aceptó y declaró pero **nadie comprobaba**.
- **El worker lo declara al arrancar**, una vez por proceso y gateado por `adaptive_enabled` (con el flag
  **OFF**, cero I/O y comportamiento byte-idéntico a `V2.51`): `warning` con recuento e ids si hay
  desajustes, `info` si el cruce está limpio, `error` si una lectura revienta (sin afirmar que todo está
  limpio).

### Cambiado: higiene de la auditoría de `v2.51-beta` (los tres hallazgos)

- **`duplicates` vs `extra_rows` en el lector de régimen.** La traza de régimen y la entrada de decisión
  del ciclo **comparten `decision_id` por diseño**, así que en el camino durable el grupo tiene dos filas
  en **todo** ciclo normal: contar todas como «duplicado» daba un **baseline distinto de cero** y ahogaba
  la única señal que interesa vigilar. Ahora `duplicates` cuenta **solo trazas confirmantes** de más
  (`collapsed_rows` su suma) y `extra_rows` cuenta **todas** las filas de más (`discarded_rows` su suma).
- **Orden de `created_at` en `cycle_risk`.** El denominador de `R` se elegía ordenando `created_at` como
  **texto**: correcto solo mientras todo origen use el mismo ancho fijo. Ahora se parsea a **instante** y
  se ordena por `(instante, reservation_id)`, con el no-parseable **al final** y **declarado**
  (`CYCLE_RISK_UNDATED_RESERVATION`, y solo cuando hubo que **desempatar**). El camino de escritura no se
  toca.
- **Régimen releído por ciclo.** `_v2_regime()` y `_v2_instant()` se llamaban **dentro** del bucle de
  reservas, así que un turno con varios ciclos podía publicar regímenes distintos. Se **hojean fuera**:
  todos los ciclos del turno publican el régimen que decidió y el mismo `asOf`.

### Medido, no supuesto

- **Un cuarto hallazgo, de cobertura, y se declaró en vez de esconderse**: `M39` había dejado de morder
  porque la comprobación de `payload['cycleId']` quedó **duplicada e inobservable** en el camino de
  lectura (el filtro por identidad ya la hacía). La identidad de la traza pasa a vivir en **un solo
  sitio** (`_is_trace`, compartida por el recuento de trazas y la lectura del régimen) y `M39` muerde
  otra vez. Es la lección del `33/33` de `V2.51` en su forma pura: la matriz no mentía en lo que medía,
  pero **afirmaba cobertura que no tenía**.
- **Circuitos de crash probados con el módulo real** (no con un valor a mano): la costura usa
  `read_adaptive_state` de verdad, así que el crash durante el cooldown, el cambio de política, el
  arranque que siembra el contador y la recomputación del mismo turno con la misma evidencia e identidad
  se prueban **end-to-end** dentro de la costura.

### Verificación

- **+64 tests, simétricos en los dos bloques offline**: `quality` **2398 passed / 38 skipped** y job
  `python` del tag **2409 passed / 35 skipped**, **0 rojos** en ambos. La base de CI de `v2.51` era
  **2334 / 38 skipped** y `2334 + 64 = 2398`: los `skipped` cuadran uno a uno (la estructura de
  `--ignore` es idéntica), así que la comparación significa algo.
- **El delta se midió fichero a fichero contra `HEAD`** (no restando totales de fases anteriores, cuyos
  targets y entorno no son los mismos): **+13** `test_auto_adaptive_journal.py` (nuevo) **+16**
  `test_auto_adaptive_recovery.py` (nuevo) **+10** `test_auto_cycle_reconciliation.py` (nuevo) **+21**
  `test_auto_v52_auto11_adaptive_state_seam.py` (nuevo) **+3** `test_cycle_risk.py` (`HEAD` 23 → 26)
  **+1** `test_auto_cycle_regime_reader.py` (`HEAD` 17 → 18).
- **Los dos ficheros de test modificados se corrieron en su versión de `HEAD` contra el código de la
  fase**: `test_cycle_risk.py` pasa **23/23** (el orden por instante es **retrocompatible**) y del lector
  de régimen falla **exactamente 1** (`test_the_newest_CONFIRMING_row_wins_over_a_newer_window_entry`),
  que es la expectativa que la fase actualiza: el rojo está **nombrado y justificado**, no es una
  regresión oculta.
- **Mutaciones `M42…M59`** nuevas (identidad sin cuenta, fila sin plan, régimen disfrazado, contador
  normalizado, racha sin corte, saturación sin techo, dedupe caído, historia corta silenciada, hueco
  aprobado, no preguntado disfrazado, trazas contadas como filas, filas de más silenciadas, antigüedad
  por texto, fecha ilegible silenciada, contador de salida, recuperación que no siembra, reconciliación
  muda, flag OFF ignorado): la **matriz completa** da **`59/59` muerden**, **0** `NADA (la mutacion NO se
  detecta)`, 0 fragmentos ausentes, 59 restauraciones byte a byte y huella `git status` **idéntica** antes
  y después. Tres fragmentos derivados por la fase (`M38`, `M40`, `M41`) se reescribieron contra el
  código real: `M38` porque el sink Adaptive es calcado del de `AUTO-10` (el fragmento pasó a aparecer
  **dos** veces y la sonda **abortaba**, que es lo correcto).
- `ruff check` (config de CI) limpio · `mypy` (gate real, `--follow-imports=silent`) **0 errores / 497
  ficheros** · `import-linter` **4/4** contratos `KEPT`.

### Sello y CI real (medido)

- **Tag anotado `v2.52-beta`** (objeto `e2337b7f`) → commit **`71c97880`**, el de los **documentos de
  fase**: el plan (`c8376b1e`) y el código (`b981c980`) van **antes**, así que los cuatro documentos
  viajan **dentro** del tag. `main` en **fast-forward** (`8af3a3ee..71c97880`) y el tag empujado **de
  uno en uno** (lección de `v2.49`: con `--follow-tags` y tags locales antiguos, más de tres tags en
  un push **no** disparan los workflows de tag).
- **`Release tag CI` run `35827266670` → `completed / success`**: los **10 jobs de decisión**
  (`frontend`, `python`, `security`, `a7-gate`, `playwright (mock E2E)`, `decision-spine`, `shared`,
  `lifecycle-pg`, `dr-verify` y el `playwright (integrated E2E)` **`skipped`** opt-in) **+ `certify
  (aggregate + artifact)`** en `success`.
- **Job `python` del tag: `2409 passed, 35 skipped`** (62,04 s), con `ruff` (`All checks passed!`),
  `import-linter` y `mypy` verdes en el mismo job.
- **`Python CI` de `main` run `35827246615` → `success`**: job `quality` **`2398 passed, 38 skipped`**
  (105,88 s) ⇒ **`k = 0`**: la extracción local del §6 cuadra **exacto** con CI (los `38 skipped` son
  las suites PG que ese job ignora por diseño). Y los cuatro jobs PG **por commit** en verde
  (`paper-forward-pg`, `lifecycle-pg`, `auto-v2-durable-pg` con Alembic 040-043 y reinicio real, y
  `grammar-discovery-pg`).
- **`check-runs` del commit del tag: `27 success` + `1 skipped`** — el mismo patrón `27/1` de
  `v2.51-beta`. Y `Frontend CI`, `Optimize lab`, `Fase 2 scientific` y `Gitleaks` en verde.
- **Sin migración**: el head sigue en `044_auto_cycle_trace`.

### Limitado y declarado (no silencioso)

- **La ventana de lectura es finita** (`ADAPTIVE_STATE_WINDOW_DEFAULT = 50`): con menos filas que la
  ventana, `insufficient_history` queda **declarado** y la racha es un **suelo**.
- **`bounded` no es el número exacto**: el contador se satura en `min_pause_cycles + 1`.
- **El pasado no se reescribe**: sin evidencia durable de una pausa anterior, el contador arranca
  **vacío y declarado** (no hay backfill).
- **`confidence` y la ventana recent/long/decay** quedan para `AUTO-12`/`AUTO-13`.
- **La tabla de estado dedicada no existe**: el cooldown vive **derivado** del journal.
- **Sin UI** para `AUTO-7`…`AUTO-11` (deuda heredada). **`governor.json` sigue sin trackear.**

## [1.76.0-beta] — AUTO-10 Journal durable por ciclo (V2.51) — 2026-09-22

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, sin UI nueva,
sin cambio de contrato de API. El gobernador y su evidencia siguen **intactos**. El invariante que
instala: **el hueco que `AUTO-9` declaraba (`regime_not_durable`) deja de existir**, porque el ciclo
abierto publica su régimen en el journal **durable** y el lector lo recupera **confirmándolo** — y lo que
no se pueda confirmar sigue siendo un hueco **declarado**. Instalado en la apertura: lo que se escribe es
el régimen del turno que **decidió**, no el de un instante posterior.

### Añadido: escritura durable del régimen por ciclo

- **`auto_cycle_journal.py`** (nuevo, contrato puro): `cycle_decision_id()` deriva `dec-<x>` de
  `cyc-<x>` por **intercambio de prefijo** (es la misma clave la que acuña ciclo y decisión: no se
  recalcula digest), y `build_auto_cycle_regime_entry()` arma la entrada append-only con `cycleId` +
  `marketRegime` + `regimeMeasurement` + `cycleIdDerived`. Tres reglas duras: **sin `cycle_id` no hay
  entrada** (`None`, no-op declarado, nunca un ciclo vacío); un `cycle_id` sin forma `cyc-` **no finge**
  derivación (`decision_id` propio + `cycleIdDerived = False`, para que el lector sepa que el índice no
  lo alcanza); y **régimen ausente = declarado** (`marketRegime = None` **y** `regimeMeasurement =
  UNKNOWN`, nunca un `UNKNOWN` de relleno que parezca valor).
- **Puerto de escritura en el worker**: el ciclo publica su traza al nacer su reserva de **entrada**
  (`_v2_journal_cycle_regime`), **después** del commit del compromiso de capital: primero el dinero,
  después la traza; si la traza falla, el dinero sigue comprometido y el hueco se declara.
- **`build_cycle_regime_sink(session)`**: cableado real en `run_tick` sobre la sesión del tick, con
  `commit` propio (un `flush` sin commit dejaría la fila sin escribir al cerrar la sesión —el hueco
  volvería a mentir por omisión—) y `rollback` en el fallo para no envenenar la sesión del resto del turno.

### Añadido: lector del journal, con confirmación

- **`auto_cycle_regime_reader.py`** (nuevo, puro sobre el puerto de lectura): pregunta por el
  `decision_id` **derivado** (campo **con índice**, sin migración) y **confirma** el
  `payload['cycleId']` antes de creerse un régimen — la forma no prueba origen: el `decision_id` de un
  ciclo lo comparte su entrada de ventana, y el fallback aleatorio acuña un `cycle_id` con la misma forma.
- **Los tres huecos se declaran por separado**: `unconfirmed` (hay fila con ese `decision_id`, pero no es
  usable: otro evento, otro `cycleId` o régimen declarado `None`), `absent` (no hay fila) y
  `not_derivable` (el `cycle_id` no tiene forma `cyc-`: el índice **no lo alcanza** y no se adivina).
  Tandas acotadas (`DEFAULT_REGIME_CHUNK = 500`).
- **`list_by_decision_ids`** en `SqlAlchemyJournalRepository`, por el índice ya existente
  `decision_journal_entries_decision_id_idx`, ordenado `created_at DESC` (lo que el dedupe necesita).
- **El hueco de `cycle_risk` se parte en dos**: `regime_not_durable` (no se consultó fuente durable, el
  comportamiento de `AUTO-9`) y **`regime_not_found`** (la fuente se consultó y el régimen **no está**).
  Distinguirlos es el punto: «no lo miré» y «no está» no son el mismo hecho.

### Cambiado: dedupe en lectura, declarado

- **`CycleRegimeReading`** gana `duplicates` (por ciclo, las filas **de más**) y `collapsed_rows` (su
  suma), visibles en `as_dict()` y en el log. Frontera medida y probada: **gana la confirmación más
  nueva**, no la fila más nueva (la entrada de ventana comparte `decision_id` y es más nueva que la
  traza; deduplicar por llegada convertiría un ciclo **con** régimen escrito en hueco), y un ciclo **sin**
  confirmación **no** cuenta como duplicado (sin ganadora no hay nada colapsado; llamarlo duplicado
  confundiría el motivo del hueco). El worker lo declara sin gritar: con huecos, dentro del `warning`;
  solo con duplicados, un `info`.

### Medido, no supuesto

- **Coste del lector** (sonda `a9_cycle_regime_read_cost_probe.py`, PostgreSQL 16.14, 1348 filas de
  journal): por **un** `decision_id` el índice se usa (**0,028–0,042 ms** frente a **0,124–0,146 ms** del
  recorrido por `payload->>'cycleId'`), pero la **tanda** del lector (15 ciclos) la resuelve el planner
  recorriendo la tabla a este volumen (**0,082–0,086 ms**, sub-milisegundo). El supuesto «la lectura por
  `decision_id` cae en el índice» es cierto **por id**, no por tanda: se declara en el código, en la
  sonda y en el plan, y **a escala no está medido** (si el spine crece, la decisión es un índice parcial
  o de expresión, nunca cambiar la identidad del ciclo).
- **Circuito escrito → sobrevivido → leído**, con PG real:
  `test_auto_cycle_regime_trace_is_durable_and_readable_from_another_session` lee desde **otra sesión**
  la traza del turno que decidió, con `decision_id` derivado y `payload['cycleId']` confirmado; se
  comprobó que el test **muerde** al desconectar el sink de `run_tick`.

### Verificación

- **+47 tests, simétrico en los dos bloques offline, medido con la MISMA extracción antes y después**
  (apartando el trabajo con `git stash -u` para medir la base en `HEAD`): `quality` **2321 → 2368** y
  job `python` del tag **2329 → 2376**, **0 rojos en ambos**. El delta es la cuenta exacta de la fase:
  **+10** contrato puro (`test_auto_cycle_journal.py`) **+17** lector (`test_auto_cycle_regime_reader.py`)
  **+8** costura de escritura **+10** costura de lectura **+2** `test_cycle_risk.py` (hueco
  `regime_not_found` vs `regime_not_durable`). Las dos costuras entran por el pase de directorio de
  `apps/api-python/tests`; la durabilidad real se certifica en `durable-pg` (**+1**, `3 passed` con
  `AUTO_V2_DURABLE_PG_REQUIRED=1`).
- **Mutaciones `M34…M41`** nuevas (identidad derivada, payload sin `cycleId`, régimen disfrazado, sink sin
  usar, sink sin commit, sin confirmar, dedupe por llegada, duplicado silencioso): **41/41** muerden,
  0 no detectadas, 41 restauraciones byte a byte y huella `git status` idéntica antes y después.
- **Enmienda medida al sello `v2.50`**: al correr la matriz completa se descubrió que **`M25`, `M26` y
  `M33` ya no aplicaban** desde `df2002e7` (fragmentos derivados por el reformateo) y que la sonda
  **seguía** en vez de fallar, así que la afirmación `33/33` de `v2.50` era **sobrestimada**: aplicaban
  **30/33**. En `V2.51` los cuatro fragmentos (`+M30`, roto por el paso 3 de esta fase) se reescribieron
  contra el código real y **la sonda ya no puede perder cobertura en silencio**: un fragmento ausente
  **falla** la corrida, con el mismo criterio con el que ya abortaba si aparecía más de una vez. El
  producto de `v2.50` **no** cambia; se corrige la afirmación (plan, audit-pack, relevo y `PROJECT_STATE`).
- `ruff check` (config de CI) limpio · `mypy` **0 errores / 494 ficheros** · `import-linter` **4/4** ·
  `durable-pg` **3 passed** (con `AUTO_V2_DURABLE_PG_REQUIRED=1`).
- **CI real: 10/10 `success`** sobre el tag (`Release tag CI`
  [`35787648126`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35787648126), `Python CI`
  `35787648092`, `Frontend CI` `35787648145`, `Optimize lab` `35787647996`, `Fase 2 scientific`
  `35787648173`) y 5/5 sobre `main`. En el job `quality` de CI: **2334 passed / 38 skipped** (los
  `skipped` son las suites PG que ese job ignora por diseño: es el mecanismo por el que el rojo local
  declarado no existe en CI). En `auto-v2-durable-pg`: **45 passed**, con el test nuevo de durabilidad
  (lectura desde **otra sesión**) **entre los 45 recolectados** — la certificación PG del tramo corrió de
  verdad.

### Limitado y declarado (no silencioso)

- **Solo ciclos del worker `AUTO`**: ciclos históricos ya cerrados sin entrada durable siguen declarando
  su hueco; `AUTO-10` **no** reescribe el pasado.
- **`netExpectancyR` sigue necesitando su propia cadena**: que el régimen sea durable cierra el eje
  `strategy × regime`, pero la expectativa neta en R depende además de que existan ciclos medidos con
  coste; esta fase no promete que el número aparezca, promete que el **insumo** deja de faltar.
- **Cooldown en memoria** (heredado) y **UI de `AUTO-7`/`AUTO-8`/`AUTO-9`** siguen pendientes.

## [1.75.0-beta] — AUTO-9 Strategy × Regime y net expectancy_R (V2.50) — 2026-09-22

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, sin UI nueva.
El gobernador y su evidencia siguen **intactos** (byte a byte igual y `exit 0`). El invariante que
instala: **el R de un ciclo deja de ser un `None` permanente** — pasa a ser un dato **medido** o un hueco
**declarado con su motivo**, nunca un `0`.

### Añadido: el denominador de R y el coste, por ciclo (read-only)

- **`cycle_risk.py`** (nuevo, `packages/py/application/src/bolsa_application/cycle_risk.py`): adaptador
  read-only que ata por `cycle_id` el **denominador** de R (`portfolio_reservations.reserved_risk`) y el
  **coste estimado** (`cost`). Cuatro reglas duras, cada una con test: el denominador es **uno** (la
  reserva de ENTRADA **más antigua** con riesgo positivo; con varias candidatas se usa la más antigua y
  se declaran — repartir el riesgo sería una media de denominadores, no una razón); las reservas
  **liberadas cuentan** (un ciclo cerrado ya no tiene reserva viva, y filtrar por viva dejaría el
  denominador en `None` justo en los ciclos con resultado); la **ausencia se declara** (`None` + nota,
  nunca un `0` de relleno ni un `inf`); y el **régimen no se inventa** (`None` + `regime_not_durable`, con
  la costura `regime_by_cycle` lista para el productor durable que falta).
- **Cálculo puro `cycle_r` / `CycleR`** en `auto_self_evaluation.py`: `r_multiple = pnl / risk_amount` y
  `net_r_multiple = (pnl − coste) / risk_amount`; coste ausente o incompleto ⇒ neto `None` +
  `cost_unmeasured` (`PARTIAL`), y `pnl = 0` **medido** ⇒ `0.0` (`COMPLETE`).
- **Agregación `strategy × regime`** con `UNKNOWN` como cubo **propio** (no se reparte ni se suma), el
  ciclo repetido contado **una vez** y celdas en orden canónico; `min_trades` es **por celda**.
- **`list_by_cycle_ids`** en `ReservationStore` (Protocol + `InMemory` + `Postgres`, por el índice ya
  existente `portfolio_reservations_cycle_id_idx`), vivas y liberadas.

### Cambiado: Adaptive pesa con el R medido solo cuando puede

- **`StrategyHealth`** gana `net_r_measurement` y su `regime` deja de ser un literal: lo **deriva** del
  cruce `strategy × regime` del **mismo** informe (`declared_regime`). Una celda decisiva con régimen ⇒
  ese régimen; **dos** celdas decisivas, una `UNKNOWN` decisiva o ninguna celda ⇒ `UNKNOWN`. Mapear
  evidencia **no** mueve decisiones: test explícito de que el cruce deja rotación y asignación idénticas.
- **Eje de evidencia por POOL, nunca por fila** en `recommend_allocation`: pesa con `net_expectancy_r`
  (exigiendo `net_r_measurement == COMPLETE` estricto) **solo** si está medido para **todo** el grupo que
  compite; en cualquier otro caso cae a `expectancy_currency`, que es el comportamiento histórico. Un hueco
  de medición no puede sacar a nadie del numerador ni mezclar unidades (R adimensional vs moneda
  absoluta). El eje se declara en `AllocationPlan.evidence_axis` y viaja en `as_dict()`.
- **`adaptivePolicyVersion` sube a `auto9-v1`** (el contrato de evidencia cambió), sellado en
  `AdaptivePlan`, `as_dict()` y journal.

### Limitado y declarado (no silencioso)

- **El régimen por ciclo no es durable hoy**: el payload de la decisión sí lleva `cycleId` y las tres
  dimensiones del gobernador, pero el worker que ejecuta el ciclo escribe su journal **en memoria**, así
  que no hay fila durable con `cycleId`. El productor lo declara (`regime_not_durable`) en vez de inventar
  un `UNKNOWN` que parecería medido; convertir ese journal en el durable es deuda del **worker**, con nombre.
- **Fail-closed por degradación**: una lectura rota devuelve `None` y el informe recupera su forma AUTO-7
  (los ciclos quedan sin R, que es el hueco que ya declaraba); **no** se marca `decisive = False`, para no
  confundir «no pude leer el riesgo» con «la muestra no es decisoria». Una lectura **saturada** tampoco
  veta: los ciclos que no cupieron quedan sin denominador —nunca con el de otro— y se avisa.
- **Cooldown en memoria** (heredado de `v2.49`): se reinicia con el proceso.

### Verificación

- **+69 tests en cada bloque offline**: `quality` **2287/2287** y job `python` del tag **2298/2298**, **0
  rojos en ambos**; el delta es la cuenta exacta de la fase (+4 lector, +8 cálculo, +13 cruce, +8
  `StrategyHealth`, +8 eje de asignación, +21 `cycle_risk`, +7 costura del worker). Con ello queda
  **cerrada** la discontinuidad que §13.8 del plan dejó declarada (2500/2511 eran el artefacto).
- **`test_cycle_risk.py` (21)** y **`test_auto_v50_auto9_cycle_risk_seam.py` (7)** nuevos, registrados en
  CI **de forma simétrica** (el primero explícito en los dos jobs por vivir en
  `packages/py/application/tests`, sin pase de directorio).
- **Mutaciones `M28…M33`** nuevas: **33/33** de la matriz muerden, 0 restauraciones fallidas y huella
  `git status` de los ficheros tocados idéntica antes y después.
- `ruff check` (config de CI) limpio · `mypy` **0 errores / 492 ficheros** · `import-linter` **4/4** ·
  `analytics` **975** · `application` **58** · costura **7**.

### Hallazgos operativos del tooling

- **Una sonda de mutaciones puede dejar el mutante dentro del árbol**: `M16` no pudo restaurar
  `auto_v2_entry.py` (`OSError [Errno 22]` de Windows, reproducible, con el fichero **limpio** y el mismo
  par escritura/restauración funcionando aislado) y dos corridas abortaron con `return best, ()` dentro
  del árbol. La sonda ahora reintenta con pausa, prueba `os.replace` y solo usa `git checkout` **si el
  fichero está limpio** (si tuviera cambios sin commitear, **aborta declarándolo** en vez de descartar
  trabajo ajeno); además admite **filtro por rótulo** para verificar un tramo sin correr la matriz entera.
- **`ruff format` no es un invariante del repo**: la compuerta de CI es `ruff check … --config
pyproject.toml` y `ruff format` no está en ningún job. Formatear en masa con la config de la raíz
  reescribió **608 ficheros ajenos**; se revirtió con criterio exacto (reconstruir `HEAD`, reformatear con
  la misma invocación y comparar ⇒ 610 analizados, 597 restaurados como ruido, 13 conservados). Queda como
  regla: `ruff format` **solo** sobre los ficheros que uno ha tocado.

## [1.74.0-beta] — AUTO-8.1 Adaptive correcto, explícito y reproducible (V2.49) — 2026-09-21

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, sin UI nueva.
El gobernador y su evidencia siguen **intactos** (byte a byte igual y `exit 0`). Cierra los hallazgos de la
auditoría externa de `v2.48-beta` sobre la asignación Adaptive y la frontera de "sin evidencia".

### Corregido: la asignación no puede ensanchar ni castigar al desconocido

- **Gate de decisividad POR FILA** en `recommend_allocation`: solo entran al reparto proporcional las
  estrategias `decisive` con expectancy > 0. Antes, una muestra fina con una racha favorable entraba al
  numerador mientras `decisive` solo se comprobaba a nivel de grupo; una estrategia sin muestra no validada
  movía el presupuesto de las que sí la tenían.
- **Política explícita de "sin evidencia"** (`AdaptivePolicy.unknown_multiplier`, neutral `1.0`): una
  estrategia sin muestra decisoria, o una versión activa sin fila de self-evaluation, recibe una entrada del
  mapa con el multiplicador de la POLÍTICA, nunca un `0.0` derivado de la ausencia de clave. "No medido" deja
  de leerse como "riesgo cero".
- **`0.0` deja de ser un techo inexistente**: `RiskAllocator.compute_allocation` trataba
  `max_risk_per_trade_pct == 0.0` como "sin techo" (el guard `pct > 0` dejaba `max_by_pct = None`) y cedía
  TODO el `risk_budget` de cartera — el multiplicador Adaptive `0.0` ensanchaba el riesgo en vez de vetarlo.
  Ahora `0.0` es un techo CERO explícito, declara `max_risk_per_trade_pct` en `cappedReasons` y veta la
  operación. `None` conserva su único significado histórico.

### Añadido: estabilidad, trazabilidad y reproducibilidad

- **Hysteresis** en la rotación: umbrales de PAUSA y de REACTIVACIÓN distintos (profit factor `1.0` → `1.10`,
  win rate `0.35` → `0.45`). El hueco es una zona muerta: una métrica que oscila alrededor del umbral no
  produce un sistema nervioso pausa/activa/pausa.
- **Cooldown**: `min_pause_cycles` mantiene una pausa un mínimo de ciclos antes de poder reactivarse. El
  estado previo entra como DATO (`paused_cycles`), no como estado interno del módulo puro; el worker lo
  mantiene en memoria (límite declarado: tras un reinicio arranca vacío).
- **`adaptivePolicyVersion`** (`auto8-v2`): viaja en `AdaptivePlan`, en `as_dict()` y en el journal. Dos
  planes con la misma evidencia, régimen y versión de política son idénticos; sin el sello, dos operaciones
  iguales podrían haber sido decididas por reglas distintas sin que se note.
- **Evidencia en el journal**: el estrechamiento y la pausa publican `decisive`, `trades`,
  `expectancyCurrency`, `profitFactor`, `winRate`, `regime` y `netExpectancyR`. "¿Por qué AUTO estrechó (o
  pausó) esta estrategia?" pasa a ser contestable desde el journal.
- **Forma declarada sin datos inventados**: `StrategyHealth.netExpectancyR` (neto) y `regime`
  (`strategy × regime`) se emiten como `None`/`UNKNOWN` declarados. Hoy NO existe productor por ciclo
  (los fills no llevan régimen, coste, riesgo ni R), así que la política ignora el régimen por estrategia y
  no se rellena ningún hueco.

### Verificación

- **29 tests puros** (`test_auto_adaptive.py`) + **9 de integración** (`test_auto_adaptive_entry.py`) + **13 de
  sizing** (`test_risk_allocator.py`), incluidos los nuevos: golden de reproducibilidad (mismo plan con filas en
  orden inverso), gate **ON neutral ≡ OFF** (byte a byte) e invariante "Adaptive solo cambia candidatas y techo de
  riesgo" (gobernador, kill, régimen y decisiones idénticas).
- Matriz de mutaciones extendida con **M22–M27**: 6 de 6 nuevas muerden (M19–M21 actualizadas a los nuevos
  fragmentos y verdes), y el árbol queda intacto.
- `ruff`, `mypy` (491 ficheros, 0 issues), `import-linter` (4 kept / 0 broken) y los dos bloques offline de CI
  (**2218** y **2229** passed, 0 skipped; delta simétrico **+18/+18**) verdes.

### Sello y CI real

- Commit de fase **`2f541fc7`** (14 ficheros, `+1248/−91`) y tag anotado **`v2.49-beta`** → `3d0a139b` → `2f541fc7`,
  empujado a `main` en **fast-forward** (`fae8ec29..2f541fc7`).
- **CI real: 10 runs, 10 `success`, cero rojos** — `Release tag CI`
  [`35694148660`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694148660) y `Python CI`
  [`35694148702`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694148702) en la ref del tag, más los cinco
  de `main` (`Python CI` [`35694063954`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694063954),
  `Frontend CI` [`35694063893`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35694063893), `Optimize lab`,
  `Fase 2 scientific` y `Gitleaks`).
- **Nota operativa medida:** `git push --follow-tags` arrastró 4 tags locales y GitHub **no creó eventos de tag**
  (limitación documentada: _no events for tags when more than three tags are pushed at once_), así que la CI del
  tag no arrancó. Recrear el tag en solitario la disparó. Para el próximo sello: empujar el tag **de uno en uno**.

## [1.73.0-beta] — AUTO-8 Adaptive AUTO · slice 1 (V2.48) — 2026-09-21

**Sin migración** (Alembic head sigue en `044_auto_cycle_trace`). Sin SHORT, sin backfill, `governor.json`
sin trackear. El gobernador y su evidencia (`v2_43_governor_evidence.py`) **no se tocan** (byte a byte igual
y `exit 0`, con `"bump"` todavía en `1.68.0-beta`).

### El invariante del roadmap §10: _Adaptive recomienda, el motor determinista decide_

- **Módulo puro** `packages/py/analytics/src/bolsa_analytics/cognitive/auto_adaptive.py`: deriva de la
  self-evaluation de AUTO-7 (solo fills) una **recomendación** `AdaptivePlan` (rotación + asignación) que el
  motor determinista `plan_v2_tick` consume como **entradas**, nunca como permisos. `AdaptivePlan.read_only`
  es `True` y su `decisive` de origen no es un permiso: **nunca `AI → BUY`**.
- **Rotación** (`recommend_rotation`): pausa una versión de estrategia con motivo
  `adaptive_strategy_unhealthy` (muestra **decisoria** y expectancy ≤ 0 o profit factor < 1) o
  `adaptive_strategy_regime_risk` (régimen adverso `TREND_DOWN`/`HIGH_VOL`, muestra no decisoria y win rate
  por debajo del suelo `0.35`). **Sin dato ⇒ no se rota** (se declara `unknown`, nunca se pausa a ciegas).
- **Asignación** (`recommend_allocation`): reparto proporcional a la expectancy positiva cuando hay al menos
  una decisoria con expectancy > 0, y **uniforme `1/n`** en caso contrario (fail-safe). El multiplicador
  `share * n` se acota a `[0, 1]`: **solo estrecha** el riesgo por operación, nunca lo ensancha.

### Flag OFF ⇒ byte-identidad

- `adaptive_enabled: bool = False` en `V2Tunables` + `AUTO_ENGINE_SIM_V2_ADAPTIVE` (opt-in) y
  `AUTO_ENGINE_SIM_V2_ADAPTIVE_WIN_RATE_FLOOR` (saneado fail-closed en bloque). Con OFF el payload del tick
  es **byte-idéntico** a AUTO-7: `plan_v2_tick(adaptive=None)`, cero I/O nuevo en el worker, ninguna clave
  `adaptive` en el journal.

### Consumo determinista (rotación antes del ranking; asignación estrechando el techo)

- **Rotación**: las candidatas de estrategias pausadas se descartan **antes** del ranking con el no-trade
  observable `adaptive_strategy_paused` (motivo nuevo en `auto_reason_codes.py`) y el motivo de la pausa en el
  detalle del journal.
- **Asignación**: `PortfolioDecisionConfig.adaptive_risk_multiplier` estrecha el `max_risk_per_trade_pct` con
  `min(escalado_del_gobernador, multiplicador_adaptativo)`. El gobernador, los gates y el sizing de
  `RiskAllocator` (camino duro) **siguen intactos**.

### Gates medidos

- `test_auto_adaptive.py` (puro, 17) + `test_auto_adaptive_entry.py` (aplicación, 5: flag OFF byte-idéntico,
  Adaptive no salta el kill switch ni el régimen UNKNOWN, rotación con régimen sintético, estrechamiento del
  risk cap). Registrados en CI con **delta simétrico** y extendidos en la matriz de mutaciones (**M19/M20/M21**).

---

## [1.72.0-beta] — AUTO-6 hardening + trazabilidad de ciclo (V2.47) + AUTO-7 self-evaluation — 2026-09-21

**CON migración** (primera de la línea AUTO desde `043`): Alembic head
`043_exit_identity_and_kill_state` → **`044_auto_cycle_trace`**, con `cycle_id` **nullable e indexado** en
`portfolio_reservations`, `auto_exit_orders` y `sim_fill_finance_context` (**sin backfill**: `NULL` = fila
anterior a `2.47`; desconocido ≠ fabricado). En el mismo sello viajan **dos trabajos que el plan repartía en
dos releases** —lo declara el [pack](./docs/engineering/audit-pack-v2.47-auto-6-hardening-y-trazabilidad-2026-09-21.md)
§7.1—: el **hardening de AUTO-6.x** (economía direccional, parada dura DURABLE, inyección de crash y
multi-proceso) y la **trazabilidad de `V2.47`** (`cycle_id` + identidad formal de señales + primeras fases de
`AUTO-7`). El gobernador y su evidencia (`v2_43_governor_evidence.py`) **no se tocan** (byte a byte igual y
`exit 0`, con `"bump"` todavía en `1.68.0-beta`).

### El defecto real de la auditoría: la economía era LARGO-only

- `expected_value._risk_geometry` y `_target_r` pasan a ser **direccionales** (una corta exige `stop > entry`,
  su distancia es `s − e` y su premio se mide hacia **abajo**) y `build_expected_value` propaga la dirección a
  `estimate_trading_cost`, que cobra la pata de salida sobre **su propio** stop. Una dirección que no se sabe
  leer **degrada** con motivo tipado `EV_DIRECTION_UNSUPPORTED`: **nunca** se asume larga.
- Fuente **única** de la dirección en el motor de entrada: `auto_v2_entry._ENTRY_DIRECTION`
  (`Final[Literal["long","short"]]`) y `entry_direction(signal)` (`BUY → long`). Un `SELL` devuelve `None` y la
  economía lo declara: **no se habilita SHORT por la puerta de atrás** (el dimensionado, el snapshot y la
  economía leen de la misma constante, así que no pueden discrepar).

### Parada dura DURABLE (engage → crash → restart → HALTED → release → RUNNING)

- El worker **adopta** en el arranque tanto el engagement durable como una **liberación** escrita desde fuera
  (si es posterior), **sin reiniciar**: un crash ya no reabre el sistema contra una parada persistida.
- Vía de liberación con **productor real**: `POST /api/v1/risk/kill-switch/durable-release`, con
  `reconciliationId` **obligatorio** (un halt que se levanta "porque sí" no es auditable). `not_engaged` es un
  no-op idempotente. `BROKER_DESYNC` sigue **sin productor**: declarado, no maquillado.

### Exactly-once bajo muerte y concurrencia

- `apps/api-python/tests/test_auto_v46_crash_injection_matrix.py` (NUEVO, 6): `CrashInjected` en las costuras
  (`save_claim`, `start_apply`, `apply_finance` antes de `mark_applied`, primer chunk APPLIED…) con invariante
  **exactly-once** tras el reinicio y convergencia del FSM. Su gemelo PG en las transiciones críticas cierra la
  desviación declarada del Crash Day (el broker SIM liquidaba todas las tranchas en el mismo tick).
- `test_auto_v46_concurrent.py`: **parametrizado** en `N ∈ {2, 3, 5, 10}` (`Σ _order_seq == 1`, una reserva
  viva). `test_auto_v46_multiprocess_pg.py` (NUEVO): **N procesos** `scheduler_worker` reales compitiendo por
  la misma señal, con el invariante medido **en la BD** y convergencia tras matar uno.

### `cycle_id`: una identidad para todo el ciclo financiero

- Acuñado **determinista** por `(cuenta, señal)` (`cyc-<sha256(…)[:12]>`): dos workers duplicados convergen al
  mismo ciclo. Se propaga por **JSONB** donde ya había JSONB (payload del journal con la clave aditiva
  `cycleId`, `V2TickPlan`, `position_state` de la posición —que lo **congela** al nacer—) y por **columna
  indexada** (migración `044`) en reservas, órdenes de salida y contexto financiero del fill. La salida
  **hereda** el ciclo de la posición que cierra.

### Identidad formal de señales (la colisión deja de ser muda)

- El candidato superado por otro se **journaliza** (`signal_superseded_by_candidate`, con ambos `signal_id` y
  `strategy_version`). Opción `allow_distinct_strategies` (default **OFF** = comportamiento actual): dos
  versiones de estrategia sobre la misma cuenta/instrumento/barra compiten como dos oportunidades legítimas
  sujetas al **optimizador de cartera**, no al dedupe ciego. Si no son representables en una sola posición, se
  declara (`signal_distinct_strategy_not_representable`) en vez de emitir dos veces.

### `AUTO-7` slice 1 — self-evaluation puro y read-only

- `packages/py/analytics/src/bolsa_analytics/cognitive/auto_self_evaluation.py` (NUEVO): agrega por
  `strategyVersion` expectancy, win rate, profit factor, MAE/MFE, contribución al drawdown, slippage, coste de
  rechazo y coste de oportunidad, y **reconcilia el embudo** (`seen == traded + rejected + expired + missed`).
- **Declara huecos en vez de rellenarlos**: sin oportunidades el embudo queda **abierto** (`seen = None`), un
  coste sin precios se declara **no medido** (nunca `0.0`), un ciclo repetido se cuenta **una vez** y se
  declara, y un ciclo sin versión **no se reparte** entre estrategias. No toca pesos ni sizing.
- Puente con lo durable: `auto_self_evaluation_feed.py` (reconstruye ciclos desde `SimFillFinanceContext`) y
  endpoint `GET /api/v1/auto/self-evaluation?version=…` (fail-closed sin ámbito de cuenta). **Sin UI** en esta
  fase.

### UI: valor esperado medido (nunca un `0 €`) y primer slice móvil

- El journal de AUTO publica `expectedR`, `netExpectedCurrency`, `expectedMeasurement` y `expectedNotes`
  (aditivos); el DTO del estudio los lleva al cliente (`openapi.json` y `schema.d.ts` regenerados) y la UI los
  pinta con un formateador **propio** (signo y `€`, porque el de dinero de la casa no añade ninguno de los
  dos): fila en `entry-operating-summary` y sección en el panel «¿Por qué?». **Lo no medido no se pinta.**
- Móvil: primer slice responsivo de los seis componentes _cabin_ de más valor con un **único** módulo
  (`use-narrow-cabin.ts`), el hook `use-media-query` **endurecido** (`matchMedia` puede no existir) y stub de
  viewport en test. Cada componente declara `data-cabin-width`, así que el layout es **medible** en test, y al
  estrechar **se apila, no se oculta**.

### Cableado de CI (que nada quede fuera de la red)

- `python-ci.yml` (`quality`): `--ignore` de las **tres** suites PG nuevas y registro **explícito** de los
  cuatro ficheros de test de aplicación de `V2.47` (no entran por pase de directorio). Además se registra
  `test_decision_journal_studies.py`, que **existía desde v2.44 y no estaba en la lista de ningún job** (sus 10
  tests no corrían en CI): hallazgo de cobertura de la pasada, cerrado aquí.
- `release-tag-ci.yml` (`lifecycle-pg`): gates `AUTO_HARDKILL_PG_REQUIRED`, `AUTO_CRASH_INJECT_PG_REQUIRED` y
  `AUTO_MULTIPROCESS_PG_REQUIRED` con **paso dedicado**, `set -o pipefail`, `tee` a log y **guard anti-skip**
  (`grep` de `skipped`).

### Verificación

`ruff` limpio · `mypy` **491** ficheros 0 issues · `lint-imports` **4 kept / 0 broken** · gobernador **exit 0**
con `git diff` **vacío** · bloques offline (targets **extraídos del YAML**) `quality` **2178** y job `python`
del tag **2189** ⇒ **+87 en AMBOS** sobre `2091`/`2102` (77 del trabajo de la fase + 10 del fichero de la
pasada) · suites PG nuevas con sus gates **5 passed, 0 skipped** · **matriz de mutaciones 18/18 muerden**
(sonda `v2_44_mutation_audit.py`, restauración byte a byte y árbol intacto; incluye los tres defectos de la
sonda corregidos: bytecode `.pyc`, `write_text`→LF y stdout UTF-8).

**CI real (sellado).** Commit de fase **`0ce3ab81`** + fix de sonda **`44486fc3`** + commit de sellado
**`2712ce87`**; tag anotado **`v2.47-beta` → `2712ce87`**. En `main`: `Python CI`
[`35619063064`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35619063064) **GREEN** (`quality` **2178
passed, 38 skipped**; `lifecycle-pg`, `auto-v2-durable-pg`, `grammar-discovery-pg`, `paper-forward-pg`
verdes), `Frontend CI` [`35619063046`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35619063046)
**GREEN**. En la ref del tag: `Release tag CI`
[`35623922429`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35623922429) **GREEN** — `python` **2189
passed, 35 skipped**, `shared` **786 + 1 todo**, `frontend` **1290 passed** (contract:check OK), y los **seis**
pasos dedicados de `lifecycle-pg` con sus guards anti-skip: `HardKill recovery` **2 passed**, `crash injection
matrix` **2 passed**, `multiprocess AUTO` **1 passed**, `Concurrent AUTO` **3 passed**, `Crash/Recovery Day`
**1 passed**, `Golden Day 2.0` **1 passed**; `certify` verde y `playwright (integrated E2E)` `skipped` por
opt-in.

**Documentación:** [`plan de fase`](./docs/engineering/plan-v2-47-auto-6-hardening-y-trazabilidad-2026-09-21.md) ·
[`audit-pack`](./docs/engineering/audit-pack-v2.47-auto-6-hardening-y-trazabilidad-2026-09-21.md) ·
[`traspaso de relevo`](./docs/engineering/traspaso-relevo-post-v2-47-auto-6-hardening-y-trazabilidad-2026-09-21.md)

## [1.71.0-beta] — AUTO-6 · Crash/Recovery + Concurrent AUTO: un crash no duplica ni pierde — 2026-09-20

**Sin migración** (el head de Alembic sigue en `043_exit_identity_and_kill_state`; el claim atómico
usa la **PK existente** de `portfolio_reservations` como árbitro). AUTO-6 (roadmap §8) certifica dos
escenarios, cada uno en **dos capas**: el **Crash/Recovery Day** (fill **parcial** → **muerte** del
proceso → **reinicio** → reconciliación → cierre limpio) y el **Concurrent AUTO** (varias instancias
del motor sobre la **misma** cuenta/barra/señal). El invariante: **un crash no duplica nada y no
pierde nada**, y **1 señal ⇒ 1 decisión ⇒ 1 orden ⇒ fills correctos** bajo concurrencia. El
gobernador y su evidencia (`v2_43_governor_evidence.py`) **no se tocan** (byte a byte igual y
`exit 0`, con `"bump"` todavía en `1.68.0-beta`).

### Claim atómico de la reserva (la única costura de producción que cambia)

- `auto_v2_entry.entry_decision_id`: la identidad de la decisión de entrada pasa a ser
  **determinista** por `(cuenta, señal)` (`dec-<sha256(cuenta ␟ signal_id)[:12]>`). Dos
  workers/procesos que evalúan la **misma** señal sobre la **misma** barra producen la **misma**
  identidad. Sin `signal_id` (señal sin barra) se conserva la identidad **aleatoria** histórica: no
  hay clave estable que reclamar (nunca un id compartido por accidente).
- `reservation_store.save_claim` (protocolo + `InMemoryReservationStore` + `PostgresReservationStore`):
  alta/actualización **atómica** del **compromiso vivo** de esa identidad (`INSERT … ON CONFLICT DO
NOTHING … RETURNING` y, si no hay fila nueva, un `UPDATE` **condicional** con `RETURNING`).
  Devuelve `True` sólo si el compromiso vivo pasa a ser del llamante; una identidad ya **liberada**
  se **re-compromete** (re-intento legítimo dentro de la barra). Es la pregunta correcta frente a
  `save`, que responde «¿la fila existía?» (idempotencia de replay): confundirlas veta la re-entrada
  legítima **o** compromete el mismo capital dos veces.
- `auto_simulation_worker._v2_persist_tick_reservations` usa el claim y, si lo **pierde**, veta su
  propia emisión con el motivo ya existente `reservation_already_live` (mismo desenlace, sin inventar
  un motivo nuevo).

### Capa hermética (por commit)

- `apps/api-python/tests/test_auto_v46_crash_recovery.py` (NUEVO): descarta el objeto worker (la RAM
  se pierde) y reinicia sobre los **mismos** espejos durables → reconciliación **convergente**, todo
  `ExecutionEvent` en `APPLIED`, cada fill con su contexto financiero, `POSITION == Σ APPLIED`,
  **sin doble efecto**, libro plano y reservas vivas a 0. Un segundo test aísla la **liberación de
  la cola no llenada** de la reserva parcial; una fase extra prueba que la señal ya consumida **no
  re-abre** la oportunidad de la barra.
- `apps/api-python/tests/test_auto_v46_concurrent.py` (NUEVO): tres workers sobre los mismos stores
  durables compartidos, con `await asyncio.sleep(0)` en los espejos para que el interleaving sea
  **real** (un `gather` sobre stores que no suspenden sería una mentira). Invariantes: una sola
  orden por señal/barra, **un solo** worker abre y los demás **declaran por qué**, una sola fila de
  reserva, `Σ reserved_cash` viva == la cola **no llenada** (nunca × nº de workers), contabilidad
  cerrada y una segunda oleada que **no añade ni una orden**.

### Capa real del tag (`lifecycle-pg`)

- `apps/api-python/tests/test_crash_recovery_day_process_pg.py` (NUEVO): el **proceso real**
  `python -m bolsa_api.workers.scheduler_worker` sobre PostgreSQL real, con id de instrumento
  determinista (`_crash_instrument_id`: BUY parcial con ≥2 tranchas y SELL completo), **muerte
  sucia** (`kill()`/`terminate()`) sobre el fill parcial **durable** que produce el propio proceso
  (sin sembrar nada) → **reinicio** → reconciliación + cierre limpio por el **seam durable**
  (`holdingDeadlineAt` vencido). Gate `AUTO_CRASH_RECOVERY_PG_REQUIRED=1` + guard anti-skip.
- `apps/api-python/tests/test_concurrent_auto_pg.py` (NUEVO): **tres sesiones** concurrentes sobre
  la misma cuenta/engine/instrumento/barra en PG real, conduciendo el tick por la **misma costura de
  producción** (`AutoSimRuntime.run_tick` + stores `Postgres*`). El invariante mide el **INTENT** de
  orden (`Σ _order_seq == 1`), no `count(distinct venue_order_id)`: la identidad de orden del venue
  es determinista y una emisión duplicada **reutilizaría** el mismo id (invisible al `count`). Gate
  `AUTO_CONCURRENT_PG_REQUIRED=1` + guard anti-skip.
- Cableado: los dos herméticos entran por **pase de directorio**; los dos PG se añaden al
  `--ignore` de los **dos** jobs offline y corren en **pasos dedicados** de `lifecycle-pg` con
  `set -o pipefail`, `tee` a log y guard anti-skip.

### Matriz de mutaciones

- `apps/api-python/scripts/v2_46_mutation_audit.py` (NUEVO): seis mutaciones —señal consumida,
  liberación de la reserva por fill, gate de reconciliación, idempotencia de `execution_events`,
  identidad determinista de la decisión y el perdedor del claim—, cada una **medida** contra su
  suite y con restauración **desde memoria**. **6/6 muerden** y la huella `sha256` del raw de los
  ficheros tocados queda **idéntica**. La sonda **sondea el puerto** de PostgreSQL (en Windows un
  puerto cerrado no rechaza al instante: las suites se colgaban) y **aborta** si encuentra un
  `# MUTATION:` sin restaurar.

## [1.70.0-beta] — AUTO-5 · Golden Day 2.0: el día real y su embudo — 2026-09-20

**Sin migración** (la identidad de estrategia entra como clave **aditiva** del `payload` JSONB del
journal; el head de Alembic sigue en `043_exit_identity_and_kill_state`). AUTO-5 cierra el criterio
"Hermetic Golden Path" del roadmap: el día completo se reproduce con **PostgreSQL real** y **proceso
de scheduler real**, y **toda** oportunidad termina en un estado final con motivo
(`seen == traded + rejected + expired + missed`). El gobernador y su evidencia
(`v2_43_governor_evidence.py`) **no se tocan** (byte a byte igual y `exit 0`, con `"bump"` todavía en
`1.68.0-beta`).

### Embudo del día y atribución (`auto_daily_journal.py`, puro)

- `AutoDailyReport` gana campos **aditivos** (defaults que no rompen a ningún llamante): embudo
  (`seen`/`traded`/`rejected`/`expired`/`missed` + `rejection_reasons`), atribución por estrategia
  (`strategy_traded`/`strategy_exits`), MAE/MFE por operación y **coste de oportunidad** de las
  rechazadas.
- **Partición disjunta y exhaustiva:** cada oportunidad cae en **exactamente** un estado. Un estado
  fuera del vocabulario deja el embudo **abierto** (`opportunity_status_unknown`); una rechazada sin
  motivo es una decisión en silencio (`rejection_without_reason`); si el `seen` del productor no cuadra
  con las filas construidas, el día lo declara (`funnel_seen_mismatch`).
- **Disciplina de medición del repo:** lo no medible se declara (`UNKNOWN`/`PARTIAL` + `notes`), jamás
  un `0` que se leería como "coste cero". El coste de oportunidad se mide con el **precio posterior**
  observado; el MAE/MFE se **recoge** del `mfe_mae` del JSONB (`AUTO-7` lo calibrará).

### Identidad de estrategia sin migración

- El worker añade la clave **aditiva** `strategyVersion` al `payload` de las decisiones del journal
  (entradas y propuestas rechazadas) y a la fila del día; el cierre la **hereda** de la posición. Sin
  versión la clave se **omite**: la ausencia es información, nunca se inventa un "unversioned".
- `_strategy_version_from_source` aprende la fuente `auto-2.0:<version>` del pipeline V2 (antes sólo
  entendía `active-strategy:`), de modo que el fill/cierre del camino V2 deja de quedar sin atribuir.

### Capa hermética (por commit)

- `packages/py/application/tests/test_auto_daily_journal.py`: embudo cerrado, motivo en cada rechazo,
  estado desconocido, `seen` descuadrado, coste declarado y MAE/MFE declarado.
- `apps/api-python/tests/test_auto_v2_golden_day_evidence.py`: el día del worker demuestra `time_exit`
  - `thesis_exit`, dos versiones de estrategia atribuidas, MAE/MFE completo y la identidad en el
    `payload` — y el rechazo tipado con su coste (`TOP_N=1`).

### Capa real del tag (`lifecycle-pg`)

- `apps/api-python/tests/test_golden_day_v2_process_pg.py` (NUEVO): el **proceso real**
  `python -m bolsa_api.workers.scheduler_worker` con V2 ON abre ≥3 posiciones (una por instrumento,
  ids **deterministas** que garantizan `fills > orders`) y cierra el libro: se detiene el proceso, se
  lleva el techo de mantenimiento durable (`holdingDeadlineAt`) al pasado y el reinicio lo **rehidrata**
  ⇒ venta por `time_exit`, todo `APPLIED`, cada fill con su transacción y libro canónico plano.
  Gate fail-if-skipped propio (`AUTO_GOLDEN_DAY_V2_PG_REQUIRED`), guard anti-skip dedicado y el fichero
  en `--ignore` de los jobs offline.

### Matriz de mutaciones

- `apps/api-python/scripts/v2_45_mutation_audit.py`: ocho mutaciones (motivo tipificado, estado no
  catalogado, `seen` descuadrado, coste declarado, MAE/MFE declarado, atribución por estrategia,
  identidad aditiva y fuente `auto-2.0`), cada una **medida** contra su suite y con la huella del árbol
  intacta.

## [1.69.0-beta] — AUTO-4 · Portfolio Optimizer: el ranking deja de ser la decisión — 2026-09-20

**Sin migración** (el optimizador es **puro** y el journal es **aditivo**; el head de Alembic sigue en
`043_exit_identity_and_kill_state`). Hasta aquí `plan_v2_tick` recortaba al `TOP_N` y decidía **una a
una** en el orden del ranking: la primera entraba y las siguientes solo si la anterior dejaba hueco, de
modo que el **ranking era la respuesta**. Ahora, con `AUTO_ENGINE_SIM_V2_OPTIMIZER=1`, el `TOP_N` es el
**tamaño del conjunto candidato** y la **cartera elige la combinación** que maximiza valor esperado
**económico** sujeto a riesgo. **Flag OFF por defecto ⇒ byte-identidad con `v2.43.3`.** El gobernador y
su evidencia (`v2_43_governor_evidence.py`) **no se tocan**.

### Valor esperado económico (`expected_value.py`, puro)

- Lo que faltaba: hasta aquí la decisión comparaba **heurísticas** (`OpportunityScore` es una suma
  ponderada de componentes normalizados; el `edge` es una **confianza declarada**, no dinero). Ahora:
  `Expected R = p·avg_win_r + (1−p)·avg_loss_r`, `Expected € = Expected R × risk_amount` y
  `Expected € neto = Expected € − coste de ida y vuelta` (el coste, por `TradingCostModel`, la casa
  única del coste).
- **Disciplina de medición del repo, sin excepciones:** `p_win` fuera de `[0, 1]`, media ausente,
  signo imposible o geometría invertida **degradan** la medición (`UNKNOWN`/`PARTIAL`) **y lo declaran**
  en `notes`; **jamás** se convierten en un `0.0` que se colaría como "una oportunidad más". Un stop del
  lado equivocado **no** es "riesgo 0" (misma lección que `H3` de `v2.43.2`).
- El `avg_win_r` puede **derivarse** del `target` si la estrategia no declara media histórica: es una
  media _declarada como derivada_ (`avg_win_r_derived_from_target`), no una invención.

### Optimizador de cartera (`portfolio_optimizer.py`, puro)

- **Enumeración EXACTA acotada** de subconjuntos (`1..max_positions`), determinista, con **desempate
  declarado**: máximo `Σ net_expected_currency`; a igual valor, **menor riesgo** (`Σ risk_amount`); a
  igual riesgo, combinación **lexicográficamente menor**. El «MIN Portfolio Risk» del roadmap entra como
  **desempate + restricciones duras**, no como optimización multi-objetivo con pesos.
- **Restricciones duras:** capacidad, capital (`Σ notional <= available_cash`), concentración sectorial
  **de la combinación**, correlación y liquidez (**fail-closed**: un límite activo con el dato ausente
  es **infeasible**, no "sin límite"), y permiso de riesgo nuevo. Un límite `None` es **sin límite
  declarado**, nunca "cero".
- **La opción de NO operar compite:** el conjunto vacío vale `0`; si nada factible tiene valor
  positivo, se elige **no operar** (`empty_set_wins`). Un optimizador que siempre encuentra algo que
  comprar no es un optimizador.
- **Tope de combinatoria fail-closed:** si el espacio supera `max_combinations` (default `4096`), el
  optimizador **no optimiza** (`measurement=UNKNOWN` + `optimizer_enumeration_cap_exceeded`) y el tick
  **cae al camino del ranking**. Nada de greedy silencioso.

### Cableado en `plan_v2_tick` (flag OFF por defecto)

- `AUTO_ENGINE_SIM_V2_OPTIMIZER=0` (default) ⇒ no se construye ninguna candidata, no se llama al
  optimizador, `V2TickPlan.optimizer` queda `None` y el **journal no gana ninguna clave**.
- Con **ON**, el TOP del ranking es el **conjunto candidato** y el `ordered` de evaluación pasa a ser la
  **combinación elegida**. Las candidatas del TOP que **no** entran se journalizan con su **motivo REAL**
  (infeasibilidad concreta o `optimizer_not_selected`) y su **score real** — **nunca**
  `edge_below_threshold`, que sería falso.
- **El tamaño lo fija el propio motor:** la candidata se dimensiona con una **sonda**
  `decide_portfolio` contra la foto inicial del tick, con la **misma** caída de ATR que la decisión real
  (no hay una segunda fórmula de stop ni de sizing). Si el motor no la dimensiona, la candidata no es
  medible económicamente y el optimizador lo declara.
- **El gobernador y el kill switch siguen mandando:** la parada dura entra como permiso de cartera; los
  vetos **por candidata** (`EXIT_ONLY`, listón de edge escalado, bandas de volatilidad/liquidez) se
  aplican **sin cambios** en el bucle de decisión. El optimizador solo decide **qué** se evalúa y **en
  qué orden**; toda la maquinaria de reservas, `_working_snapshot` y `RESERVATION_FAILED` queda intacta.
- `V2Signal` gana cuatro campos **aditivos y opcionales** (`target_price`, `p_win`, `avg_win_r`,
  `avg_loss_r`) y `auto_reason_codes` añade `OPTIMIZER_REASONS` (el journal tiene una sola casa).

### Verificación medida (no declarada)

- **33 tests nuevos**: `test_expected_value.py` 12 + `test_portfolio_optimizer.py` 12 +
  `test_auto_v4_optimizer_wiring.py` 8 + 1 en `test_auto_v2_worker_integration.py` (el flag ON está
  cableado en el worker real).
- `quality`: **2042 → 2075 passed**, `0 skipped`; `release-tag-ci` · `python`: **2053 → 2086 passed**,
  `0 skipped` (+33 en **ambos**; el test de aplicación va **explícito** en las dos listas). Los conteos de
  `v2.44` son de **CI real** (runs [35510546044](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510546044)
  y [35510840734](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510840734)): los bloques offline
  completos **no** llegaron a término en la máquina del autor (sin PostgreSQL local el `conftest` paga un
  timeout por test), así que la red de CI es la que mide.
- `ruff` limpio · `mypy` **0 issues** (489 ficheros) · `lint-imports` **4 kept / 0 broken**.
- **Matriz de mutaciones medida** (`v2_44_mutation_audit.py`): **7 de 7 muerden**, huella del árbol
  intacta (objetivo, conjunto vacío, tope, EV no medido, correlación fail-open, motivo honesto en el
  journal y el propio flag).

### Límite declarado

**No hay productor de economía en el camino del tick** (`_v2_signals` no aporta `p_win`/medias: el
productor real es de `AUTO-7`). Con el flag **ON** y sin economía, **todas** las candidatas son
`optimizer_expected_value_unmeasured` y el tick **no opera**: es **fail-closed declarado** y está fijado
en test. Con el flag **OFF por defecto**, el camino de producción no cambia.

### Sello (2026-09-20)

Commit de fase **`f692159d`** (18 ficheros, `+2728/−2`) + tag anotado **`v2.44-beta`** sobre el commit de
sellado docs-only (convención de `v2.43-beta`…`v2.43.3-beta`); `v2.43-beta`/`v2.43.1-beta`/`v2.43.2-beta`/
`v2.43.3-beta` **no se mueven** (ref nueva y aditiva). **CI real del commit de fase**: `Python CI`
**GREEN 5/5** (run [`35510546044`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510546044):
`quality` **2075 passed, 38 skipped** en 89,26 s — el **`+33`** exacto sobre los 2042 de `v2.43.3-beta`,
`auto-v2-durable-pg` **43 passed** — sin cambio, porque no hay migración —, `paper-forward-pg` 2 passed,
`grammar-discovery-pg` 21 passed, `lifecycle-pg` 13 passed), `Gitleaks` **GREEN**
(run [`35510546045`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510546045)), `Optimize lab`
**GREEN** (run [`35510546041`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510546041)) y
`Fase 2 scientific` **GREEN**
(run [`35510546060`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510546060)). El `+33` de `quality`
es la prueba de que el test de aplicación (`test_auto_v4_optimizer_wiring.py`) corre **en CI** y no solo en
local. **CI real de la ref del tag `v2.44-beta`** (`c95819c1`): `Release tag CI` **GREEN** con
`certify (aggregate + artifact)` en `success`
(run [`35510840734`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510840734): job `python` offline
**2086 passed, 35 skipped** — los mismos **+33** sobre los 2053 de `v2.43.3-beta` —, `lifecycle-pg` con PG
real **148 + 45 passed**, `a7-gate` 7 passed, `shared` 778 tests / 94 ficheros, `playwright (mock E2E)`
`success` y `playwright (integrated E2E)` `skipped` por opt-in), `Python CI` **GREEN 5/5**
(run [`35510840771`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510840771): `quality` **2075
passed, 38 skipped**, `auto-v2-durable-pg` **43 passed** — idénticos al commit de fase), `Gitleaks`
**GREEN** (run [`35510839339`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510839339)),
`Optimize lab` **GREEN** (run [`35510840762`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510840762)),
`Frontend CI` **GREEN** (run [`35510840724`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510840724))
y `Fase 2 scientific` **GREEN** (run [`35510840720`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35510840720)).

## [1.68.3-beta] — AUTO-3 reliability closure: kill durable, identidad de salida y orden UTC — 2026-09-20

**Migración 043** (`043_exit_identity_and_kill_state`): nacen `auto_kill_state` y `auto_exit_orders` y la
columna `portfolio_reservations.exit_order_id`. **El head de Alembic pasa de `042` a `043`.** Cierra los
cinco hallazgos P0/P1 de la auditoría de `v2.43.2-beta`: la parada dura y la identidad de una salida
pertenecían a la **memoria del proceso** (un reinicio olvidaba el HALT y podía **reutilizar** una
identidad histórica), el fallo de reserva no tenía política declarada, y el fold del ledger ordenaba por
**cadena** ISO en vez de por instante. **El gobernador no se toca**: `v2_43_governor_evidence.py` sigue
byte a byte igual y **exit 0**.

### P0-1 — El HALT es del SISTEMA, no del proceso

- **`auto_kill_state`** (una fila por `(account_id, engine_id)`): `engaged`, `reason` tipificado,
  `engaged_at`, **`engagement_id`** (identidad de la activación concreta), `reengagements` y el rastro de
  la liberación (`released_at`, `release_actor`, **`release_reconciliation_id`**). Sin fila ⇒ la parada
  nunca se activó: la **ausencia es información**, no un `engaged=false` inventado.
- **Nuevo orden de arranque**: `LOAD KILL STATE` → si `engaged`, latchear y vetar entradas →
  `readopt_positions()` → `_v2_reconcile_reservations(startup=True)`. El arranque **jamás** ignora un HALT
  persistido; una parada durable **liberada** no levanta un halt local (el latch es monótono en el
  proceso y solo una liberación explícita lo quita).
- **`engage_kill_switch_durable` / `release_kill_switch_durable`**: la activación persiste (`save` +
  `commit`) junto al latch y **un fallo de escritura NO levanta la parada** (el latch sigue in-memory y
  se declara; jamás se cree protegido por un HALT que nadie podrá leer tras un crash). La liberación
  **exige `reconciliation_id`**: un halt que se levanta "porque sí" no es auditable, y sin id la
  liberación se rechaza.
- **Productores reales**: un libro de compromiso que **no se pudo medir** con reservas vivas
  (`RECONCILIATION_FAILURE`) deja de ser un veto de aperturas y pasa a ser un **HALT persistido**; un
  **`DUPLICATE_EXECUTION`** detectado al reconciliar hace lo mismo. Antes `engage_kill_switch` no tenía
  productor en producción.

### P0-2 — `exit_order_id`: identidad de salida durable (migración 043)

- Se **retira** `_v2_exit_seq` como fuente de identidad: era un contador de proceso que volvía a 0 en
  cada arranque, así que un reinicio podía **reutilizar** una identidad histórica (y, con
  `ON CONFLICT ... UPDATE`, actualizar una reserva antigua). Ahora se mintea un **ULID** y se persiste el
  **INTENT** (`auto_exit_orders`) **antes** de reservar y de emitir: `INTENT → RESERVED → EMITTED →
PARTIAL/FILLED` (+ `EMERGENCY`/`ABANDONED`), con `filled_qty`/`remaining_qty` explícitas.
- La reserva referencia el intent (`reservation_id = exit:{exit_order_id}` y columna
  `portfolio_reservations.exit_order_id`), y **la identidad viaja a la orden**: `logical_order_id` →
  `venue_order_id` → `execution_id` embeben el id, de modo que cada fill de `execution_events` queda
  **atribuido al intent concreto**.
- La reconciliación de arranque y la liberación por fill **casan por `exit_order_id`** (fallback
  posicional solo para filas legadas por el prefijo `exit:`), y actualizan el intent: un fill parcial lo
  deja `PARTIAL` con su cola viva y una reserva muerta sin fill lo deja `ABANDONED`.

### P1-4 — Política de fallo de reserva (opción B, declarada)

- Si la **reserva** de salida no llega a ser durable, se persiste un **intent de emergencia**
  (`emergency=true`, `EMERGENCY`, motivo `reservation_persist_failed`) y **solo entonces** se emite: una
  salida protectora nunca se bloquea por un fallo de reserva (reducir riesgo no empeora), pero tampoco
  se emite jamás sin identidad durable.
- Si el intent de emergencia **tampoco** es durable ⇒ `engage_kill_switch_durable("SYSTEM_ERROR")` y
  **la orden NO se emite** (fail-closed). El call-site veta con `exit_intent_not_durable`: antes un
  `None` de `_v2_reserve_exit` se ignoraba y el SELL salía igual.

### P1-5 — El ledger ordena por INSTANTE UTC, no por cadena

- `_fold_sort_key` normaliza `applied_at` a **epoch UTC** (`_applied_instant`): ISO con offset y sufijo
  `Z` se parsean, un naive se asume UTC (el espejo durable guarda `timestamptz`) y lo ilegible es "sin
  fecha". Dos hechos con offsets distintos del **mismo** instante comparan igual, y el orden es el real
  (antes `str()` lexicográfico separaba `09:00:00+02:00` de `08:00:00Z`).
- Un hecho **sin fecha** deja de ser "simplemente el último": cuenta como **no valorado** y degrada
  `measurement` a `PARTIAL`/`UNKNOWN` (no se afirma un P&L exacto). Ya no se ordena como el más antiguo.

### P0-3 — Matriz de crash C1–C4, Golden Day y certificación PG

- Nuevo `apps/api-python/tests/test_auto_v44_exit_crash_matrix.py`: cuatro ventanas (C1 decisión→antes de
  reservar, C2 reserva→antes de emitir, C3 emitida→antes de APPLIED, C4 fill parcial), cada una con el
  reinicio modelado como lo que es (**la RAM se pierde, los stores no**): exactly-once del INTENT, sin
  reserva duplicada, sin ejecución duplicada, posición correcta y latch coherente.
- El **Golden Day** dinámico y el **reinicio RISK_EXIT** (`test_auto_v44_exit_governance.py`) se amplían
  con la ventana **crash-antes-de-reservar** (solo posición durable, ni reserva ni intent) y verifican el
  `exit_order_id` del día completo.
- Nuevo `apps/api-python/tests/test_auto_v44_exit_identity_pg.py`: roundtrip de la **043**
  (tablas + índices + columna, `downgrade` a 042 y `upgrade head`), supervivencia del INTENT y del HALT a
  un **reinicio real por segunda sesión**, y el enlace reserva→intent con un fill parcial. Gate
  `AUTO_RESERVATION_PG_REQUIRED=1` fail-if-skipped en el job `auto-v2-durable-pg` (y en `lifecycle-pg` del
  tag); el fichero queda en `--ignore` del job hermético.

### Verificación medida (2026-09-20)

- `ruff check packages/py apps/api-python` → **0**; `mypy` (5 paquetes + api) → **489 ficheros, 0 issues**;
  `lint-imports` → **4 contratos, 0 roto**.
- Bloque offline del job `quality` (extraído del YAML con `offline_ci_run_yaml.py --with-pg-ignores`):
  **2042 passed, 0 skipped, 0 failed**; bloque offline del job `python` del tag (mismo runner, mismo flag):
  **2053 passed, 0 skipped, 0 failed**.
- `test_auto_v44_exit_crash_matrix.py` **8 passed** + `test_auto_v44_exit_governance.py` **9 passed**;
  baterías nombradas (`test_position_ledger.py`, `test_hard_kill_switch.py`,
  `test_portfolio_reservation_ledger.py`, `test_position_manager.py`): el conjunto de las **seis** suites
  del cierre queda en **110 passed**.
- **Matriz de mutaciones** (`apps/api-python/scripts/v2_43_3_mutation_audit.py`): **6 de 6 muerden**
  (M1/M2 kill durable, M3/M4 identidad de salida, M5 política B, M6 orden UTC) y la sonda deja la
  **huella del árbol intacta**.
- **PG real**: no ejecutado en esta máquina (sin PostgreSQL alcanzable), pero **certificado en CI**: el
  job `auto-v2-durable-pg` (gate **fail-if-skipped**) pasó de **39 a 43 passed** — los cuatro tests de la
  043 (roundtrip de la migración, INTENT y HALT que sobreviven a un reinicio real por segunda sesión y el
  enlace reserva→intent con fill parcial) corrieron contra PostgreSQL real, no skipearon.

### Sello (2026-09-20)

Commit de fase **`379b8cc9`** (24 ficheros, `+3688/−42`) + tag anotado **`v2.43.3-beta`** sobre el commit
de sellado docs-only (convención de `v2.43-beta`…`v2.43.2-beta`); `v2.43-beta`/`v2.43.1-beta`/
`v2.43.2-beta` **no se mueven** (ref nueva y aditiva). **CI real del commit de fase**: `Python CI`
**GREEN 5/5** (run [`35507944960`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35507944960):
`quality` **2042 passed, 38 skipped** en 115,73 s, `auto-v2-durable-pg` **43 passed**, `paper-forward-pg`
2 passed, `grammar-discovery-pg` 21 passed, `lifecycle-pg` 13 passed) y `Gitleaks` **GREEN**
(run [`35507944962`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35507944962)). **CI real de la ref del
tag `v2.43.3-beta`** (`52b97126`): `Python CI` **GREEN 5/5**
(run [`35508331525`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35508331525), `auto-v2-durable-pg`
**43 passed**) y `Release tag CI` **GREEN** con `certify (aggregate + artifact)` en `success`
(run [`35508331431`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35508331431): job `python` offline
**2053 passed, 35 skipped**, `lifecycle-pg` con PG real **148 + 45 passed**; `playwright (integrated E2E)`
`skipped` por opt-in), más `Gitleaks` **GREEN**
(run [`35508329936`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35508329936)).

### Deuda diferida (fuera de esta versión, declarada)

API de ledger por `(account_id, instrument_id)`; separación `pending_entry`/`pending_exit` en
`committed_positions`; renombrado de `EXIT_ONLY`; frescura de quote como condición de ejecución;
hysteresis/calibración del gobernador; gobernador ON por defecto; tags firmados / CI attestation;
Portfolio Optimizer.

## [1.68.2-beta] — Hardening de contabilidad de posición + Exit Governance (AUTO-3 slice 2) — 2026-09-19

**Sin migración** (el head de Alembic sigue en `042_portfolio_reservations`). Dos fases en un solo
parche: **hardening** de la contabilidad de posición (6 hallazgos, 2 de ellos P0) y **Exit Governance**
(AUTO-3 slice 2), que hace que el gobernador gobierne también el **ciclo de vida** de la posición, no
solo la entrada. **El gobernador no se toca**: `v2_43_governor_evidence.py` sigue byte a byte igual y
**exit 0** (la escalera de drawdown gobierna igual), y su `"bump": "1.68.0-beta"` se queda como está por
el mismo motivo declarado en `v2.43.1`.

### Fase 1 — Hardening (sin migración, gobernador intacto)

- **H1 · `realized_qty` se inflaba (P0).** El fold de `PositionLedger` sumaba la cantidad de la **venta
  solicitada** (`realized_qty += fact.quantity`) en vez de la que **casó** contra inventario. Una venta
  rechazada o el exceso de un oversell avanzaba la cantidad cerrada sin que existiera inventario que
  cerrar, y como `remaining_qty = quantity - realized_qty`, eso **podía reportar como plana una compra
  real posterior** (una posición viva invisible para la reconciliación). Ahora `realized_qty` avanza solo
  por `matched`, igual que `cost_basis` y `realized_pnl`, y se añaden dos campos explícitos:
  **`sold_qty`** (Σ ventas ejecutadas, el hecho del venue) y **`unmatched_exit_qty`**
  (`sold_qty - realized_qty`, el exceso que no tenía inventario contra el que casar). La relación
  `realized_qty == quantity_closed` vuelve a ser cierta y `sold_qty` deja de ser ambiguo.
- **H2 · El snapshot de trabajo resucitaba R2 (P0).** `_working_snapshot` hacía
  `(snapshot.risk_used or 0.0) + committed_risk`, es decir convertía "alguna posición no declara su
  riesgo" en un **total medido** y el motor dejaba de vetar por medición incompleta. Ahora el riesgo
  reservado solo se suma si la base es **medible** (`snapshot.risk_is_complete`); si `risk_used is None`
  se conserva `None` y se **reenvía `risk_measurement`** al rebuild, porque un `risk_used` explícito se
  leía como una afirmación `COMPLETE` y borraba el `UNKNOWN` de la base.
- **H3 · Un stop del lado equivocado se publicaba como riesgo CERO (P1).** `max(0.0, (entry - stop) * qty)`
  convertía "stop mal puesto" en `0.0` **declarado**, que el sistema leía como riesgo medido. Ahora la
  geometría la valida la **misma casa** que el resto del motor (`stop_distance`): un long con
  `stop >= entry` no tiene stop válido ⇒ `risk_amount = None` (riesgo desconocido) ⇒ degrada la medición
  y **veta**, en vez de publicar 0.
- **H4 · El fold no garantizaba la idempotencia por `execution_id` (P1).** La idempotencia durable ya
  existe (PK + `ON CONFLICT` de `execution_events`), pero el fold no la garantizaba **por sí mismo**: dos
  hechos con el mismo `execution_id` doblaban posición, riesgo, cash y P&L. Ahora `build_position_ledger`
  deduplica (gana la primera aparición tras ordenar) y declara los repetidos como **rechazados**
  (`duplicate_execution_id:<id>`) en vez de ignorarlos en silencio; la medición degrada.
- **H5 · El libro no tenía cuota de cuenta (P1).** `AppliedFillFact` no llevaba `account_id`, así que una
  lectura con `account_id=None` (todas las cuentas) **fundía** dos posiciones del mismo instrumento en
  cuentas distintas en una sola cantidad, y el `quantities()` que alimenta la reconciliación tomaba esa
  fusión por real. Ahora el `account_id` viaja al hecho, el fold agrupa por `(account_id, instrument_id)`
  y una **colisión entre cuentas** del mismo símbolo se **declara** degradando la medición (el mapa
  instrumento → cantidad no puede representar dos posiciones del mismo símbolo sin fundirlas).
- **H6 · Un hecho sin fecha se ordenaba como el más antiguo (P2).** `str(None or "")` precede a cualquier
  ISO real en orden lexicográfico, así que una fila legada sin `applied_at` se doblaba como "la compra
  más antigua" y torcía el coste medio (que depende del orden de compras y ventas). La clave del fold
  pasa a `(tiene_fecha, applied_at, execution_id)`: los hechos sin fecha van **al final**, de forma
  declarada. AUTO-1b ya cerró la causa raíz (un `datetime` de PostgreSQL perdía su fecha al normalizarse);
  esto protege el residuo legado.

### Fase 2 — Exit Governance (AUTO-3 slice 2)

- **Taxonomía de motivos, extendida, no duplicada.** `ExitReason` gana **`KILL_SWITCH`**, **`REGIME_EXIT`**
  y **`RISK_EXIT`**, insertados en la `EXIT_REASON_PRECEDENCE` que ya existía (orden por autoridad de
  deshacer riesgo: `KILL_SWITCH` > `REGIME_EXIT` > `RISK_EXIT` > `MANUAL` > stop estructural > tesis >
  riesgo de cartera > objetivos > trail > tiempo). `REGIME_EXIT` deja de ser un override **post-hoc**
  fuera del `Literal`: nace en el `ExitPlan`. Se añade **`secondary_reasons`** para que el journal deje de
  perder la atribución múltiple (un solo `primary_reason` decisorio + los demás que también dispararon).
- **`portfolio_risk`/`manual` dejan de ser inalcanzables.** `build_exit_plan_from_position` ya los
  aceptaba, pero nadie los pasaba desde AUTO. Ahora se propagan por `build_position_decision` y
  `manage_position_outcome`.
- **El gobernador gobierna el ciclo de vida.** `manage_position_outcome` recibe la lectura del gobernador
  (`risk_regime`, `drawdown_band`, `operational_state`) además del régimen de mercado:
  `RiskRegime == RISK_OFF` (o banda `EXIT_ONLY`) ⇒ **`RISK_EXIT`**; `OperationalState == HALTED` ⇒
  **`KILL_SWITCH`**; régimen exit-only ⇒ `REGIME_EXIT`. Los tres se **reafirman defensivamente** como venta
  **total** para que ningún camino (reconciliación, fracción de T2, ratchet de stop) deje posición abierta
  contra el gobernador. Los coercers canónicos normalizan lo no reconocido a `UNKNOWN` (fail-closed: un
  valor raro no es permisivo). Se añaden `primary_exit_reason`/`secondary_reasons` a
  `PositionManagerResult`, y `RISK_EXIT`/`REGIME_EXIT`/`KILL_SWITCH` entran en el **journal del día**
  (`auto_reason_codes`) y en `_journal_exit_request` para **avanzar el FSM** (`EXIT_REQUESTED`).
- **`HardKillSwitch` latcheado por encima del gobernador** (módulo nuevo
  `bolsa_analytics/cognitive/hard_kill_switch.py`). `resolve_operational_state` aceptaba `halted` desde el
  slice 1, pero **`plan_v2_tick` no lo pasaba nunca**: era un parámetro muerto. Ahora hay un **productor**
  con motivos **tipificados** (`DATA_CORRUPTION`, `BROKER_DESYNC`, `RECONCILIATION_FAILURE`,
  `DUPLICATE_EXECUTION`, `RISK_BREACH`, `STALE_DATA`, `MANUAL_KILL`, `SYSTEM_ERROR`): un motivo no
  canónico **no se puede** activar (`ValueError`), el estado es **latcheado** (no se auto-libera: reavisar
  cuenta el reintento y conserva el motivo original) y liberarlo exige **reconciliación explícita**. Bloquea
  entradas **siempre**; por defecto **permite** las salidas protectoras (el invariante de la casa). La
  parada es **independiente del flag del gobernador**: con la parada activa la tabla se evalúa aunque el
  gobernador esté OFF, porque un kill switch no puede quedar desactivado por un flag de conveniencia.
- **Frescura por dimensión** (módulo nuevo `bolsa_analytics/cognitive/data_freshness.py`). La frescura
  era un único booleano; ahora son **cuatro relojes** (`market_data`, `atr`, `quote`, `volume`) con umbral
  declarado por dimensión. `market_data` no fresca (stale **o sin dato**) ⇒ **no se abre**, pero las
  **salidas protectoras siguen permitidas** (el veredicto se publica como `blocks_new_entry`, nunca como un
  halt que congelaría también las salidas). Un instante no interpretable ⇒ `unknown`, **nunca epoch 0** (que
  fabricaría un stale). `unknown` se publica como `stale` en el snapshot booleano: "no sé" jamás puede
  leerse como fresco.
- **Reservas de SALIDA vivas (F9).** `committed_positions()` **saltaba** las reservas `sell` y la
  reconciliación del worker solo consumía fills `buy`, así que la cola de un `RISK_EXIT` con fill parcial
  era invisible: la exposición comprometida se sobreestimaba y al reiniciar nadie sabía que había una salida
  en vuelo ⇒ la MISMA orden podía re-emitirse. Ahora una reserva de venta viva **se netea** contra la compra
  del mismo instrumento (neto `Σ compras − Σ ventas`, nunca negativo), el worker crea una reserva de salida
  **durable antes de emitir** (`_v2_reserve_exit`) y la libera con los fills de **venta**
  (`_v2_release_reservations_for_fill(side=SIDE_SELL)`), casando por **lado**.

### Verificación medida (árbol final, matriz de mutaciones medida)

| Comprobación             | Comando                                                                                                              | Resultado                                |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Estático (invocación CI) | `uv run ruff check packages/py apps/api-python --config pyproject.toml`                                              | **All checks passed!**                   |
| Tipos                    | `uv run mypy packages/py/{domain,market,infrastructure,application}/src apps/api-python/src --follow-imports=silent` | **487 ficheros, 0 issues**               |
| Fronteras                | `uv run lint-imports --config packages/py/.importlinter`                                                             | **4 kept / 0 broken** (602 ficheros)     |
| Evidencia del gobernador | `uv run python apps/api-python/scripts/v2_43_governor_evidence.py --out governor.json`                               | **exit 0** (la tabla sigue gobernando)   |
| Bloque `quality` de CI   | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/python-ci.yml quality --with-pg-ignores`      | **2031 passed** (`1991 → 2031`, **+40**) |
| Bloque `python` del tag  | `uv run python scripts/verify/offline_ci_run_yaml.py .github/workflows/release-tag-ci.yml python --with-pg-ignores`  | **2042 passed** (`2002 → 2042`, **+40**) |
| Suites de `analytics`    | `uv run pytest packages/py/analytics -q`                                                                             | **862 passed**                           |
| Suites de `application`  | `uv run pytest packages/py/application -q`                                                                           | **1705 passed, 5 skipped**               |

**Nota de método (bloques offline).** En la máquina del autor el lanzador `pytest` del console script
(`uv run pytest`) está **bloqueado por Windows Application Control** (`os error 4551`), así que los dos
bloques del YAML se midieron con la **misma selección extraída del runner** lanzada como `python -m pytest`
(no cambia la selección de tests, solo el lanzador): `2031` y `2042`, los conteos declarados. Son cifras
además corroboradas por la **CI real** (`quality` en el run del commit de fase y `Release tag CI` en la ref
del tag).

El delta `+40/+40` es la comprobación de cobertura: los **40 tests nuevos** entran por las listas
**existentes** de CI en **ambos** bloques, así que ninguno queda fuera de la red (la deuda que `v2.42.2`
tuvo que cerrar a mano para `test_auto_daily_journal.py`). Reparto: 5 en `test_position_ledger.py`,
4 en `test_auto_v2_entry.py`, 8 en `test_position_manager.py`, y **tres ficheros nuevos** —
`test_hard_kill_switch.py` (7), `test_data_freshness.py` (8) y
`apps/api-python/tests/test_auto_v44_exit_governance.py` (8, incluido el **Golden Day dinámico** y el
**reinicio en mitad de un `RISK_EXIT`**).

**Matriz de mutaciones: MEDIDA** (sonda versionada `apps/api-python/scripts/v2_43_2_mutation_audit.py`,
2026-09-20). **9 de las 13** mutaciones muerden (M1–M5, M7–M9, M11) y **4 nacen verdes** (M6, M10, M12,
M13) con su causa declarada en el §10.1 del pack: **tres agujeros reales** (M6, el eje cuenta del libro;
M12, el neteo de reservas de F9; M13, la reconciliación de arranque) quedan **declarados y reproducibles**
— no se añadió test ni se tocó código de producción en el cierre. Tampoco se mide **PG real** en la máquina
del autor (motivo ya declarado en fases anteriores: el `connect` del DSN se cuelga); no hace falta para la
fase 1 (no toca ningún fichero PG) y la certificación de durabilidad de la fase 2 la aporta CI.

**Errata declarada de esta pasada (método):** la primera verificación de `ruff` se hizo **sin** el flag
`--config pyproject.toml` y concluyó «2 avisos, ambos preexistentes». **Con la invocación de la casa** el
resultado era **7 avisos y todos eran míos** (imports desordenados al añadir los imports nuevos): el
ejemplo de que verificar con una copia a mano de la invocación del CI mide otra cosa que el CI. Corregido
con `ruff check --fix` **antes** de sellar; la lección está en el relevo.

**Documentación:** [`audit-pack-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md`](docs/engineering/audit-pack-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md) ·
[`arranque-auditor-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md`](docs/engineering/arranque-auditor-v2.43.2-hardening-y-auto-3-slice-2-2026-09-19.md) ·
[`traspaso-relevo-post-v2-43-2-auto-3-slice-2-2026-09-19.md`](docs/engineering/traspaso-relevo-post-v2-43-2-auto-3-slice-2-2026-09-19.md).

**Sello (`v2.43.2-beta`).** Commit de fase **`ef35e3aa`** (29 ficheros, `+3814/−66`) y tag anotado
**`v2.43.2-beta`** → commit de sellado docs-only **`13b54ceb`**. **CI real medida**: en `main` (`ef35e3aa`)
`Python CI` **GREEN 5/5** ([run 35497681654](https://github.com/jvelasca/Bolsa_V1/actions/runs/35497681654),
con `auto-v2-durable-pg` fail-if-skipped) y `Gitleaks` **GREEN**
([run 35497681645](https://github.com/jvelasca/Bolsa_V1/actions/runs/35497681645)); en la **ref del tag**
(`13b54ceb`) `Release tag CI` **GREEN** (jobs requeridos + `certify`;
[run 35498499879](https://github.com/jvelasca/Bolsa_V1/actions/runs/35498499879)), `Python CI` **GREEN 5/5**
([run 35498499864](https://github.com/jvelasca/Bolsa_V1/actions/runs/35498499864)) y `Gitleaks` **GREEN**
([run 35498498856](https://github.com/jvelasca/Bolsa_V1/actions/runs/35498498856)). Detalle en el §12/§12.1
del pack.

## [1.68.1-beta] — Remediación de la auditoría externa de `v2.43-beta` (5 hallazgos, 2 de ellos de seguridad financiera) — 2026-09-18

**Sin migración** (el head de Alembic sigue en `042_portfolio_reservations`). Parche de remediación, **sin
cambio de arquitectura y sin tocar el gobernador**: no se modifican los ejes, la tabla de decisión, el gate
de entradas ni su evidencia. Los cinco hallazgos viven en las dos piezas que la auditoría declaró **pendientes
de leer línea a línea** (`position_ledger.py` y el resto de `portfolio_reservation.py`), más dos hallazgos de
contabilidad de posición ya reportados sobre `v2.43-beta`.

- **R1 · `reserved_cash` del libro: el comentario contradecía a la propiedad.** El comentario de `release()`
  afirmaba que `reserved_cash` se podía calcular sumando **todas** las reservas "sin tener que filtrar por
  estado", mientras la propiedad filtra por `.live()`. Hoy las dos fórmulas coinciden (una reserva no viva
  tiene sus dimensiones a 0), pero la promesa del comentario invitaba a que un futuro camino de liberación
  **se ahorrase el filtro** y doble-contase. El comentario pasa a declarar el invariante real y el filtro
  como cinturón de seguridad; la propiedad no se toca.
- **R2 · `gross_risk` nunca era `None`: el riesgo de posiciones no medido se leía como 0 (seguridad
  financiera).** En `build_portfolio_risk_state` la guarda `position_total is not None or reserved_risk is
not None` era **siempre verdadera** (`reserved_risk` es un `float` property, nunca `None`), así que el
  `(position_total or 0.0)` convertía "hay posiciones sin `risk_amount`" en 0 y el riesgo de cartera se
  publicaba **por debajo del real**, en silencio, justo en el caso que el sistema declara no poder medir.
  Ahora el total solo se publica si el riesgo de las posiciones está **medido**; si no, `gross_risk` y
  `net_risk` quedan `None` y el `measurement` degrada. Es el mismo patrón `or 0.0` que el bug de
  `total_samples` de `discovery_evidence.py`: "no lo sé" convertido en "es cero" en el cálculo más
  importante del módulo.
- **R3 · Un lado no interpretable se doblaba como VENTA (seguridad financiera).** `AppliedFillFact` solo
  validaba `execution_id`, así que un `side` que no fuese `buy`/`sell` (p. ej. `"hold"`, o `"BUY"` en
  mayúsculas) entraba al fold y caía en su `else`: **reducía la posición, realizaba P&L contra un coste
  ajeno y no declaraba ninguna violación**. Ahora el tipo lo rechaza (la fila ilegible se declara al leer,
  vía `coerce_applied_fill_fact` ⇒ rechazada ⇒ `measurement`), de modo que el `else` del fold es una venta
  **por construcción**.
- **R4 · Una posición PLANA publicaba `averageEntry: 0.0`.** La rama que dividía el residuo de `cost_basis`
  (drift del redondeo a 4 decimales) entre la cantidad total publicaba "compré a 0,0" en una posición
  cerrada, y una entrada histórica rancia en el caso del oversell: tres valores distintos para el mismo
  hecho. Ahora una posición plana no tiene entrada (`average_entry = None`), sin importar por dónde se
  llegó al cierre.
- **R5 · `replay()` podía infradeclarar capital en silencio.** `ReservationEvent` no validaba nada: un
  `kind` desconocido se aplicaba como **liberación** (relajando el libro) y un alta **sin su reserva** se
  perdía sin más, dejando un libro que declara **menos** capital comprometido del real. El evento valida
  ahora su `kind` (con constantes canónicas `RESERVATION_EVENT_RESERVE`/`_RELEASE`) y exige la reserva en el
  alta: lo que no se puede reproducir no se puede representar.

**Cambio observable declarado**: `V2TickPlan.risk_state` es un read-model **en memoria** (sin
serialización: el payload del journal no cambia y la byte-identidad con `AUTO_ENGINE_SIM_V2_GOVERNOR=0`
sigue intacta). Lo único que cambia en él es que `gross_risk` pasa de un **suelo** a `None` cuando hay
posiciones abiertas sin `risk_amount` — que es exactamente el hallazgo R2, no una regresión.

**Matriz de mutaciones medida** (3 mutaciones aplicadas a la vez, 3 rojos): quitar la validación de `side`
⇒ `test_an_uninterpretable_side_cannot_be_represented_as_a_fact` rojo · restaurar la rama del residuo ⇒
`test_flat_position_never_publishes_a_zero_or_stale_average_entry` rojo · quitar la validación de
`ReservationEvent` ⇒ `test_a_non_replayable_event_cannot_be_represented` rojo. El cuarto test correlacionado
(`test_full_exit_flattens_and_is_not_published_as_open`) queda **verde** con la mutación: el sensor del
hallazgo R4 es el test dedicado, no una aserción decorativa.

| #      | Qué                                                                                                                                                                                                       |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R1** | Comentario de `release()` alineado con `reserved_cash`/`reserved_risk` (invariante declarado + filtro `.live()` como cinturón); test de doble vía `Σ all() == Σ live()` por las cuatro vías de liberación |
| **R2** | `build_portfolio_risk_state` fail-closed: `gross_risk`/`net_risk` `None` si el riesgo de posiciones no está medido; traducción explícita "0 medido vs no medido" en `_risk_state_for`; 3 tests            |
| **R3** | `AppliedFillFact.__post_init__` valida `side`; el `else` del fold documentado como "venta por construcción"; test de rechazo y de lectura                                                                 |
| **R4** | `_fold_instrument`: posición plana ⇒ `average_entry = None` (sin residuo de redondeo ni entrada rancia); test con cierre limpio, con drift y con oversell                                                 |
| **R5** | `ReservationEvent` valida `kind` y exige la reserva en el alta; constantes canónicas exportadas; test que prueba lo no-representable y la forma válida                                                    |

### Verificación local medida (árbol final, mutaciones revertidas)

`ruff check` **All checks passed** · `mypy` **487** ficheros, **0** issues · `lint-imports` **4 kept / 0
broken** · evidencia del gobernador `v2_43_governor_evidence.py` **exit 0** (la tabla sigue gobernando: no
se tocó) · bloques offline de CI **extraídos del YAML** ⇒ `quality` **1983 → 1991 passed (+8)** y job
`python` del tag **1994 → 2002 passed (+8)**, **0 failed / 0 skipped**. El delta es **exactamente** el número
de tests nuevos en los **dos** bloques: la comprobación de que lo nuevo **sí** corre en CI y no se queda
fuera de las listas (la deuda que `v2.42.2` tuvo que cerrar a mano para
`test_auto_daily_journal.py`).

**CI real del sello (2026-09-18).** Commit de fase **`48856912`** (11 ficheros, `+721/−12`) + tag anotado
**`v2.43.1-beta`** → commit de sellado `b27280de` (docs-only, que **sí** entra en el tag, convención de
`v2.43-beta`); `v2.43-beta` **no se mueve** (ref nueva y aditiva).

| Ref                         | Workflow       | Resultado                                                                                                                                                                                                                 | Run                                                                            |
| --------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `main` @ `48856912`         | Python CI      | **GREEN 5/5** — `quality` **1991 passed, 38 skipped** (118,90 s), `auto-v2-durable-pg` **39 passed** (5,76 s)                                                                                                             | [`35343011292`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35343011292) |
| `v2.43.1-beta` @ `b27280de` | Python CI      | **GREEN 5/5** — `quality` **1991 passed, 38 skipped** (82,41 s), `auto-v2-durable-pg` **39 passed** (6,54 s)                                                                                                              | [`35344945191`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35344945191) |
| `v2.43.1-beta` @ `b27280de` | Release tag CI | **GREEN** con `certify (aggregate + artifact)` en `success`; job `python` offline **2002 passed, 35 skipped**, `lifecycle-pg` con **PG real** **144 + 45 passed**; `playwright (integrated E2E)` `skipped` por ser opt-in | [`35344945138`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35344945138) |
| `main` @ `48856912`         | Gitleaks       | **GREEN**                                                                                                                                                                                                                 | [`35343011254`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35343011254) |

Los `38 skipped` de `quality` son las suites gated por `DATABASE_URL` / `*_PG_REQUIRED`, que corren en sus
jobs dedicados (y ahí el gate **falla si se saltan**).

## [1.68.0-beta] — V2.43 · AUTO-3 slice 1: `MarketRegime` × `RiskRegime` × `OperationalState` (ejes, tabla y gate de ENTRADAS) — 2026-09-18

**Sin migración** (el head de Alembic sigue en `042_portfolio_reservations`). Primer slice de `AUTO-3`
(§5 del roadmap): instala los **tres ejes** y la **tabla de decisión** con su gate puro, y cablea el
**permiso operativo solo a las ENTRADAS** detrás de un flag **OFF por defecto**. No cambia ninguna
política de salida.

El cambio de fondo es conceptual: hasta ahora "el mercado está bajista" y "AUTO tiene prohibido
abrir" viajaban **mezclados** en un único eje de régimen. Ahora son dos hechos distintos, cada uno
con fuente: `MarketRegime` (hecho de mercado, derivado de barras) y `OperationalState` (permiso
derivado de la tabla), y el veto de permiso tiene **motivo propio** en el journal
(`governor_exit_only` / `governor_halted`), separado de `regime_invalid`.

- **`operational_governor`** (nuevo, `bolsa_analytics.cognitive`, puro y hermético): ejes
  `MarketRegime` / `RiskRegime` / `OperationalState` + bandas de entrada (`DrawdownBand`,
  `VolatilityBand`, `LiquidityBand`), los techos declarados por eje (`_*_CAP`, que **son** la
  política) y `resolve_operational_state(...)` = techo más estricto. La tabla es **total** (todo eje
  tiene default `UNKNOWN`) y **monótona** (más riesgo nunca es más permisivo); un `UNKNOWN` nunca es
  "libre". La severidad es el contrato, y el tamaño se **deriva del estado resuelto**
  (`risk_scale`), con la composición declarada "el más estricto gana" (no producto de factores).
- **`drawdown_pct` medido, por fin, en AUTO V2**: el worker alimenta un `EquityMarkBook` inyectable
  una vez por tick con el equity **marcado a mercado** (base declarada + P&L realizado de las ventas
  aplicadas + no realizado de marcas vs entrada). Antes el snapshot V2 no recibía drawdown (siempre
  `None`), así que el eje de riesgo no podía existir. Sin dato ⇒ `UNKNOWN` ⇒ fail-closed, nunca 0.
- **Bandas de volatilidad y liquidez** con umbral declarado (`HIGH_VOL`/`LOW_VOL` medidos; liquidez
  contra `min_liquidity_notional`), y **`LOW_VOL` deja de ser un valor muerto**: la matemática `v1` de
  `discovery_market_regime` (`AUTO_ENGINE_SIM_V2_REGIME_MATH=v1`, opt-in) añade `low_vol` para el
  tramo "sin dirección y muy calmado". `v0` no cambia ni una etiqueta.
- **Gate en el motor (solo entradas)**: `EXIT_ONLY` ⇒ veto `governor_exit_only`; `HALTED` ⇒ veto
  `governor_halted`; `REDUCED`/`RESTRICTED` escalan el riesgo (0,75 / 0,50) y `RESTRICTED` sube
  además el listón de edge (`min_edge × restricted_edge_factor`, factor ≥ 1 por invariante). El motor
  **lee** el permiso: no reconstruye política, y solo **endurece** (nunca relaja la regla direccional).
- **Las tres dimensiones en el journal** de toda decisión que pasa por el motor
  (`marketRegime` / `riskRegime` / `operationalState`), con el `bindingAxis` declarado dentro de la
  lectura. Con el flag OFF las claves **no se emiten**: el payload es el histórico byte a byte.

| #       | Qué                                                                                                                                                                                                                                                                                                                                                                     |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **C1**  | **`operational_governor`** (módulo nuevo): ejes, bandas, `_STATE_SEVERITY`, `RISK_SCALE_BY_STATE`, techos declarados por eje, `resolve_operational_state` (total, monótona, fail-closed) y `OperationalAssessment` con `risk_scale` / `binding_axis` / `to_dict()`                                                                                                      |
| **C2**  | **`DrawdownPolicy` + `GovernorPolicy`**: cortes declarados y estrictamente crecientes (si no, `ValueError`), `min_liquidity_notional ≥ 0` y `restricted_edge_factor ≥ 1` (un factor que relajaría el listón está prohibido por construcción)                                                                                                                            |
| **C3**  | **Alias aditivos** por colisión de nombre: `MacroRegime` (`weight_rules`), `FinancialIntegrityState` (`reconcile_financial_integrity`) y export `GovernorMarketRegime` (`cognitive/__init__`); ningún eje existente cambia de significado                                                                                                                               |
| **C4**  | **`to_market_regime`** traduce el eje operativo existente al de mercado; `RISK_OFF` macro **no** se traduce (es un hecho de riesgo ⇒ `UNKNOWN`)                                                                                                                                                                                                                         |
| **C5**  | **`MATH_VERSION_MARKET_REGIME_V1`** (`discovery_market_regime`): rama `low_vol` con umbral declarado, `TRIAL_REGIMES_V1` e `is_valid_regime(math_version=...)`; `v0` inmutable y versión desconocida ⇒ `NO_REGIME`. `map_trial_regime` gana `low_vol` y la agregación del universo lo incorpora a su prioridad                                                          |
| **C6**  | **Drawdown cableado al worker**: `EquityMarkBook` inyectable (`equity_marks=`), `_v2_governor_drawdown_pct()` (con el flag OFF devuelve `None`: ni se mide ni se paga el cómputo) y `_sim_realized_pnl` alimentado por las ventas aplicadas, para que una pérdida cerrada no desaparezca de la equity de marca                                                          |
| **C7**  | **`build_worker_snapshot(drawdown_pct=...)`** y **`V2TickPlan.governor_states`** (estado efectivo por candidata, en orden de evaluación): el tick publica el permiso que realmente aplicó                                                                                                                                                                               |
| **C8**  | **`V2Tunables`**: flag `AUTO_ENGINE_SIM_V2_GOVERNOR` (OFF), cortes de drawdown, `governor_min_liquidity_notional`, `governor_restricted_edge_factor` y `regime_math_version`; `governor_policy()` y `decision_config(governor=...)` (escala el riesgo y sube el listón en `RESTRICTED`)                                                                                 |
| **C9**  | **Env saneada como bloque** (`_governor_env_overrides`): un corte no creciente, un número no finito o un factor `< 1` descartan **todos** los umbrales de env y quedan los defaults declarados; una env mal puesta no puede tumbar el tick ni relajar el listón                                                                                                         |
| **C10** | **Gate de permiso en `decide_portfolio`** (paso 3.b, tras el régimen y antes de liquidez) con motivos propios `governor_exit_only` / `governor_halted`, alta en `_NO_TRADE_REASONS` y estado no canónico ⇒ `HALTED` (fail-closed)                                                                                                                                       |
| **C11** | **Journal**: `PortfolioDecision.market_regime` / `risk_regime` / `operational_state` y publicación de `marketRegime` / `riskRegime` / `operationalState` en el payload, **solo** cuando el gobernador se consultó (flag OFF = payload histórico). Un descarte previo al motor no inventa dimensiones                                                                    |
| **C12** | **Tests (48, todos nuevos)**: 25 puros (`test_operational_governor.py`: totalidad sobre 1 728 combinaciones, techo por eje, monotonía por dominancia, `UNKNOWN` nunca libre), 20 de gate (`test_auto_v3_governor_gate.py`: byte-identidad con el flag OFF, vetos, escalado, listón, journal, env y `v1` vs `v0`) y 3 de evidencia (`test_auto_v3_governor_evidence.py`) |
| **C13** | **Evidencia reproducible** (`apps/api-python/scripts/v2_43_governor_evidence.py`): corre la escalera de drawdown por el camino real del worker con su **control con el flag OFF** en cada tramo, emite JSON y **sale ≠ 0** si la tabla no gobierna la decisión. Sin PG, sin red, sin reloj real                                                                         |
| **C14** | **CI**: el gate de aplicación va **explícito** en `python-ci.yml` (job `quality`) y `release-tag-ci.yml` (job `python`); la tabla pura y la evidencia las recogen los pases de directorio de `packages/py/analytics/tests` y `apps/api-python/tests`                                                                                                                    |

### Matriz de mutaciones **medida** (7 mutaciones, 7 rojos)

Sobre las superficies nuevas del slice; se aplica, se corre el target acotado, se **revierte verificando
el contenido exacto** (hash del fichero) y se reporta:

| #   | Mutación                                                                  | Efecto medido                                                                             |
| --- | ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| M1  | Un techo de eje mal mapeado (`HIGH_VOL` deja de reducir)                  | **1 rojo** (el test de techos declarados)                                                 |
| M2  | Se quita `UNKNOWN ⇒ nunca libre` en un eje                                | **3 rojos** (techos, el test por eje de `UNKNOWN`, `assess` extremo a extremo)            |
| M3  | `EXIT_ONLY` deja pasar entradas (solo `HALTED` veta)                      | **4 rojos** (veredicto del permiso, medición ausente, journal, lectura directa del motor) |
| M4  | Se rompe la monotonía (`strictest_state` devuelve el menos severo)        | **11 rojos** (totalidad/máximo, monotonía, `UNKNOWN`, ejes y `bindingAxis`)               |
| M5  | `drawdown_pct` no cableado (el worker publica siempre `0` ⇒ banda `FULL`) | **3 rojos** (escalera medida, pata no realizada y seam de medición)                       |
| M6  | El journal pierde las tres dimensiones                                    | **2 rojos** (journal del gate + evidencia)                                                |
| M7  | `risk_scale` ignorado en el sizing (`scale = 1.0`)                        | **2 rojos** (REDUCED al 75 % y RESTRICTED al 50 %)                                        |

### Verificación medida (árbol final del slice)

- `ruff check packages/py apps/api-python --config pyproject.toml` (invocación exacta de CI): **All checks
  passed**; `mypy` (invocación de CI, `--follow-imports=silent`): **487 ficheros, 0 issues**;
  `lint-imports`: **4 kept / 0 broken**.
- **Tests del slice**: **48 passed** (25 puros + 20 de gate + 3 de evidencia).
- **Evidencia** (salida del script, guardada como JSON, `exit 0`): la escalera de drawdown produce la
  escalera declarada de estados y de efectos — `0 % ENTRY_ALLOWED`, `6 % ENTRY_REDUCED` (cantidad × 0,75
  sobre su control), `12 % ENTRY_RESTRICTED` (tamaño × 0,50 y listón de edge que separa `edge=0.5` de
  `edge=0.9`), `15 % EXIT_ONLY` (`governor_exit_only`), `22 % HALTED` (`governor_halted`) — y **cada
  tramo vetado tiene su control con el flag OFF aprobando**: el freno se atribuye al gobernador, no a
  otro gate. La pata **no realizada** también se mide (posición viva marcada −10 % sobre 60 000 de
  exposición ⇒ 6 % de drawdown con la equity base declarada intacta). Con el flag OFF no hay drawdown,
  ni dimensiones, ni cambio de motivo ni de tamaño.
- **Freeze comprobado**: sin migración (head `042_portfolio_reservations`), `AUTO_ENGINE_SIM_V2=0` intacto
  (el gate vive dentro del pipeline V2) y con `AUTO_ENGINE_SIM_V2_GOVERNOR=0` el camino V2 es
  **byte-idéntico** (test de byte-identidad del journal con y sin drawdown en el snapshot).
- **Bloques offline de CI** (targets y `--ignore` **extraídos del YAML**, con verificación de que cada
  ruta existe): job `quality` de `python-ci.yml` **1983 passed, 0 failed, 0 skipped** (42 rutas, 8
  ficheros PG a `--ignore`) y job `python` de `release-tag-ci.yml` **1994 passed, 0 failed, 0 skipped**
  (51 rutas, 8 ficheros PG a `--ignore`), los dos con `exit 0`. Las cifras incorporan **exactamente** los
  48 tests nuevos (1935 → 1983 y 1946 → 1994), que es la comprobación de que lo nuevo corre en CI.
- **Límites declarados**: el gobernador **solo gobierna entradas** (el camino de salida no cambia);
  `HALTED` no tiene productor propio en este slice (tabla / kill switch); los umbrales de drawdown
  (5/10/15/20 %) son **declarados y calibrables**, no calibrados contra datos; y la evidencia es un día
  **hermético** (stores `InMemory*`, precios y ATR inyectados), no una sesión de mercado real.
- **CI real (sellado)**: commit de fase `7ca4a0e1` (23 ficheros, `+3677/−58`), commit de sellado
  `4fc09f08` y tag anotado **`v2.43-beta` → `4fc09f08`**. `Python CI` **GREEN 5/5** en `main` (run
  [`35322991385`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35322991385): `quality` **1983 passed,
  38 skipped** en 114,94 s; `auto-v2-durable-pg` **39 passed** con el gate fail-if-skipped activo) y
  **GREEN 5/5** en la **ref del tag** (run
  [`35323452519`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35323452519): `quality` **1983 passed,
  38 skipped** en 116,14 s, `auto-v2-durable-pg` **39 passed** en 6,09 s, más los per-commit
  `grammar-discovery-pg`, `paper-forward-pg` y `lifecycle-pg`); `Release tag CI` (run
  [`35323452639`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35323452639)) **GREEN** con el
  **`certify` (aggregate + artifact)** en `success` y los jobs requeridos en verde (job `python` offline:
  **1994 passed, 35 skipped**, `mypy` 487 ficheros 0 issues; job `lifecycle-pg` con **PG real**: **144 +
  45 passed**; `playwright (integrated E2E)` es opt-in y queda `skipped` por diseño), más `Frontend CI`,
  `Optimize lab`, `Fase 2 scientific` y `Gitleaks` en verde. **Desviación declarada del patrón de
  `v2.42.2`**: el tag apunta al **commit de sellado** (docs-only) y no al de fase, para que la ref sellada
  **no cite refs inexistentes**; el código sellado es `7ca4a0e1`. La **petición de auditoría externa** quedó
  publicada en el [issue #62](https://github.com/jvelasca/Bolsa_V1/issues/62), con los puntos de entrada
  fijados a la ref del tag.

## [1.67.2-beta] — V2.42.2 · AUTO-2 slice 2c (cierre): evidencia de un día, ATR medido y cero política legacy — 2026-09-18

**Sin migración** (el head de Alembic sigue en `042_portfolio_reservations`). Cierra el **criterio de
salida de `AUTO-2`** (§4 del roadmap), que exigía dos cosas que no existían:

1. **`ProtectionConfig` sin ninguna lectura en el camino `AUTO_ENGINE_SIM_V2=1`.** Con el motor V2 ON el
   `if` de la política legacy **ya no se evalúa** — antes se evaluaba (y devolvía `None`) en los casos
   `held == 0`/`price <= 0`, así que la afirmación no era estructuralmente cierta. El gate es un **sensor
   que explota** si alguien vuelve a meter la llamada: un test del día completo sustituye las dos funciones
   legacy por un `AssertionError` y el día corre igual.
2. **`TIME_EXIT`/`THESIS_EXIT` con evidencia en el journal de un día completo.** La evidencia era de test
   (hermético + PG), que no responde a "cuántas posiciones cerró el día y por qué". Ahora el **día cuenta sus
   motivos**: la fila `position_close` lleva la etiqueta del motivo **decisorio** y el reporte agrega
   `exit_reasons` (con `undeclared` para un cierre sin motivo declarado: nunca se atribuye lo que no se
   declaró) y la **procedencia del ATR** medida por el worker.

- **`day_exit_reason`** (dueño único en `auto_reason_codes`): traduce el `primary_reason` del plan al
  vocabulario del día (`TIME_STOP → time_exit`, `THESIS_INVALIDATION → thesis_exit`, `STRUCTURAL_STOP →
structural_stop`, ...). Por motivo **decisorio**, así que un stop-out no se cuenta como salida por tesis.
- **`SimJournalRow.reason`** (aditivo, default `""`): el motivo viaja en la propia fila del día. Con V2 ON
  es la etiqueta del día; en el camino legacy, el motivo de protección; un cierre del decider sin motivo de
  protección queda sin declarar ⇒ `undeclared`.
- **`AutoDailyReport.exit_reasons` / `atr_sources`** (tuples deterministas, conteo desc + etiqueta asc) y
  su reflejo en `as_dict()`: el día es comparable entre corridas y la suma de motivos es **exactamente**
  `exits` (ningún cierre sin explicar).
- **`AutoSimulationWorker.atr_source_counts()`**: accessor público de la medición de procedencia del ATR
  (antes contadores privados que solo leían los tests). Es el número con el que D3 decide (o no) flipar el
  veto; sin señales queda a cero (no se asume procedencia).
- **Cero política legacy con V2 ON** (restructure de `auto_turn`): el `else` de la protección legacy solo se
  ejecuta con `AUTO_ENGINE_SIM_V2` **OFF**, y con V2 ON la retirada del T1 parcial legacy queda intacta por
  construcción. Consecuencia declarada: `qty <= 0` en una SELL legacy ya no cae por `hold_no_op` (antes sí).

| #       | Qué                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **C1**  | **`day_exit_reason`** (`auto_reason_codes`, puro): traducción del motivo decisorio al vocabulario del día, con `DAY_EXIT_REASON_UNDECLARED` para el cierre sin motivo declarado; un motivo no catalogado se declara en minúsculas tal cual (nunca se inventa etiqueta)                                                                                                                                                                                                                                         |
| **C2**  | **`SimJournalRow.reason`** (aditivo) + `_emit(..., reason=...)`: el motivo de cierre viaja en la **fila del día** (la que agrega `build_auto_daily_report`), no solo en el journal rico                                                                                                                                                                                                                                                                                                                        |
| **C3**  | **`AutoDailyReport.exit_reasons` + `atr_sources`** (tuples deterministas) y `as_dict()`: el día cuenta **por qué** cerró (`sum(exit_reasons) == exits`, con `undeclared` para lo no declarado) y **de dónde** salió el ATR (`real`/`fallback`/`missing`)                                                                                                                                                                                                                                                       |
| **C4**  | **`build_auto_daily_report(atr_sources=...)`**: la medición del worker entra al reporte tal cual (el build sigue siendo puro; `None`/vacío ⇒ sin medición, jamás inventada)                                                                                                                                                                                                                                                                                                                                    |
| **C5**  | **`AutoSimulationWorker.atr_source_counts()`**: accessor público de la procedencia del ATR del día (antes privado y solo legible desde los tests)                                                                                                                                                                                                                                                                                                                                                              |
| **C6**  | **Cero política legacy con V2 ON** (`auto_turn`): el `else` de `protection_exit_reason` queda detrás de `not self._v2_enabled`, de modo que con V2 ON **no se evalúa** en ningún caso (antes sí en `held == 0`/`price <= 0`, con resultado `None`). La atribución del T1 parcial legacy (`_t1_done`) se preserva en el camino legacy, que es el único donde la política aplica                                                                                                                                 |
| **C7**  | **Tests (21 nuevos)**: 5 puros en `test_auto_daily_journal.py` (conteo de motivos, `undeclared` que no se disfraza, orden determinista, ATR medido, ATR no inventado) y **3 herméticos de día completo** en el fichero nuevo `apps/api-python/tests/test_auto_v2_golden_day_evidence.py` (un día con `time_exit` + `thesis_exit` + `structural_stop`, sano y con `sum(motivos) == exits`; el mismo día con la política legacy sustituida por un sensor que explota; y la medición de ATR cuando el real falta) |
| **C8**  | **Evidencia reproducible** (`apps/api-python/scripts/v2_42_2_golden_day_evidence.py`): corre el día golden y emite JSON con motivos, procedencia del ATR, techo congelado, **lecturas de la política legacy** y estado de cierre; `--out` lo guarda y el script **sale ≠ 0** si el día no cumple el criterio. Sin DB ni red (stores `InMemory*`)                                                                                                                                                               |
| **C9**  | **CI**: el día golden lo cubre el **pase de directorio** de `apps/api-python/tests` en `quality` y va **explícito** en la lista por fichero del job `python` del tag. Además se añade **`packages/py/application/tests/test_auto_daily_journal.py`** a **ambos** jobs: existía desde `v2.24` pero **no estaba en ninguna lista**, así que sus gates no corrían en CI (deuda de cobertura detectada y cerrada aquí)                                                                                             |
| **C10** | **Runner local de CI, versionado en el repo** (`scripts/verify/offline_ci_run_yaml.py`): extrae targets/`--ignore` **del YAML**, **verifica que cada ruta existe** (una ruta inexistente es `exit 4` = job rojo) y mide por **JUnit XML** (bajo `subprocess` en Windows la línea de resumen de pytest se pierde). Se versiona porque vivía fuera del repo y **dos veces** midió otra cosa que CI — ver la errata de abajo                                                                                      |

### Matriz de mutaciones **medida** (7 mutaciones, 7 rojos)

Sobre las superficies nuevas de 2c; se aplica, se corre el target acotado, se **revierte verificando el
contenido exacto** y se reporta:

| #   | Mutación                                                                           | Efecto medido                                        |
| --- | ---------------------------------------------------------------------------------- | ---------------------------------------------------- |
| M1  | `TIME_STOP` se mapea a `thesis_exit` en la etiqueta del día                        | **2 rojos** (`test_auto_daily_journal` + día golden) |
| M2  | La fila `position_close` pierde el motivo (el día vuelve a no saber por qué)       | **1 rojo** (el día golden exige los tres motivos)    |
| M3  | Con V2 ON se vuelve a evaluar la política legacy (`held == 0` entra por el `else`) | **1 rojo** (el sensor del día explota)               |
| M4  | La medición de ATR del día se queda vacía (`atr_source_counts → {}`)               | **2 rojos**                                          |
| M5  | `STRUCTURAL_STOP` se mapea a `thesis_exit` (el stop-out se disfraza)               | **2 rojos**                                          |
| M6  | Un cierre sin motivo declarado se atribuye a `time_exit`                           | **3 rojos**                                          |
| M7  | El reporte del día olvida los motivos (`exit_reasons` vacío)                       | **4 rojos**                                          |

### Verificación medida (árbol final del slice, antes de publicar)

- `ruff check packages/py apps/api-python --config pyproject.toml` (invocación exacta de CI): **All checks
  passed**; `mypy` (invocación de CI, `--follow-imports=silent`): **487 ficheros, 0 issues**;
  `lint-imports`: **4 kept / 0 broken**.
- **Bloques offline de CI** (targets y `--ignore` **extraídos del YAML**, con verificación de que cada ruta
  existe): job `quality` de `python-ci.yml` **1935 passed, 0 failed, 0 skipped** (53,2 s) y job `python` de
  `release-tag-ci.yml` **1946 passed, 0 failed, 0 skipped** (19,3 s). Procedencia: **41 rutas** (50 en el
  job del tag) y **8 ficheros PG** movidos a `--ignore` (en CI saltan rápido porque no hay servidor; aquí el
  `connect` del DSN **se cuelga**: medido), más `--noconftest` para no depender del conftest de la app (que
  también habla con PG). Los 21 tests nuevos de 2c están dentro de esas cifras (+18 del fichero de diario que
  ahora sí se recolecta y +3 del día golden).
- **Evidencia del día** (salida del script, guardada como JSON): `exit_reasons` = `{time_exit: 1,
thesis_exit: 1, structural_stop: 1}`, `exits` 3 de `positions_created` 3, `healthy` **true**,
  `ledger_balance_status` `BALANCED`, `legacy_policy_reads` **0**, `atr` = 15 señales **100 % reales** (0
  fallback, 0 missing) con el veto en `0` (OFF), `holding_deadline_at` `2026-10-30T09:00:00Z` y libro plano
  al cierre. Es la evidencia que el §4 del roadmap pide para `AUTO-2`, con la limitación declarada abajo.
- **Límite declarado de la evidencia**: el día corre **hermético** (stores `InMemory*`, precio y ATR
  inyectados, sin PG). Es un día **completo del motor** (33 ticks, 6 órdenes, 24 fills, 3 posiciones con 3
  desenlaces distintos), **no** una sesión de mercado real con datos de mercado; y la `ProtectionConfig` se
  sigue **construyendo** en el constructor del worker (`_protection_config_from_env()`), porque el camino
  `AUTO_ENGINE_SIM_V2=0` debe conservar el comportamiento `v2.39.x` byte a byte: lo que este slice hace
  estructural es que **con V2 ON no se lee**.
- **Errata de herramienta de esta fase (declarada)**: el runner local declaró colgada una corrida de
  `quality` durante ~15 min. Causa medida: su detección de ficheros PG usaba un patrón que exigía `_pg`
  **pegado al final del nombre**, y se le escapaban dos ficheros de scheduler
  (`test_a9_scheduler_process_pg_zero_human.py` y
  `test_auto_scheduler_real_pg_zero_human_intervention.py`): sin `--ignore`, su `connect` al DSN (que no
  responde ni rechaza) cuelga la corrida. Corregido (`test_*_pg*.py`) y el runner **se versiona en el repo**
  (`scripts/verify/offline_ci_run_yaml.py`) para que la medición local deje de ser una copia a mano: es la
  segunda vez que un runner local mide **otra cosa** que CI, así que la verificación de rutas y la lista
  extraída del YAML pasan a ser una herramienta del repo, no un script suelto.

- **CI real (sellado)**: commit `3e8aa359` + tag anotado **`v2.42.2-beta`**. `Python CI` **GREEN 5/5** en
  `main` (run [`35312788454`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35312788454): `quality`
  **1935 passed, 38 skipped**; `auto-v2-durable-pg` **39 passed, 0 skipped** con el gate; `lifecycle-pg`
  per-commit 13 passed) y **GREEN 5/5** en la ref del tag (run
  [`35312807393`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35312807393)); `Release tag CI`
  (run [`35312807338`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35312807338)) **GREEN** con los
  **10 jobs requeridos** y el **`certify` (aggregate + artifact)** en `success` (`playwright (integrated
E2E)` es opt-in y queda `skipped` por diseño) — job `python`: **1946 passed, 35 skipped** y `mypy` **487
  ficheros 0 issues**; job `lifecycle-pg` (PG real): **144 + 45 passed** —, y `Frontend CI`, `Optimize lab`,
  `Fase 2 scientific` y `Gitleaks` en verde.

## [1.67.1-beta] — V2.42 · AUTO-2 slice 2b: `TIME_EXIT`/`THESIS_EXIT`, ATR real y cierre de los hallazgos H-1..H-7 — 2026-09-17

**Sin migración** (el head de Alembic sigue en `042_portfolio_reservations`): el techo de mantenimiento y
el nivel de invalidación viven en el JSONB `sim_auto_positions.position_state` (migración `040`). Cierra las
tres deudas que el slice 2a declaró y los **siete hallazgos** que la auditoría externa del `v2.42-beta`
dejó por escrito en el §9 de su pack:

- **E1 · `TIME_EXIT` (decisión D1)**: el horizonte de mantenimiento se resuelve por plantilla
  (`resolve_holding_horizon` sobre `trading_policy_templates`), se **congela en el nacimiento** de la
  posición (`holdingDeadlineAt` en el JSONB) y, alcanzado, produce una **salida real** con motivo propio.
  Antes `TIME_STOP` era **inalcanzable por construcción**: la gestión recibía `expires_at=None` y ningún
  camino podía vencer.
- **E3 · `THESIS_EXIT` (decisión D2, firmada por el owner)**: el nivel de invalidación se congela al nacer
  (del plan o del stop estructural) y la invalidación **confirmada vende** (`EXIT` real, no `REVIEW`), con
  la memoria del **peor adverso** (`maeR`) como único testigo — y esa memoria ahora **persiste** en el
  espejo durable en vez de morir dentro de la copia del tick. La atribución del motivo es del **motivo
  decisorio**: un stop-out no se disfraza de salida por tesis.
- **E2 · ATR real (decisión D3)**: se **cablea y se mide** el ATR real de barras (`AtrSource`) con el veto
  fail-closed detrás de `AUTO_ENGINE_SIM_V2_ATR_REQUIRED` (**default OFF**), y la geometría sintética se
  **declara** como tal en el journal (`atr_geometry` + `atrSource`) en vez de disfrazarse de dato real.

| #       | Qué                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **B1**  | **`resolve_holding_horizon`** (`exit_policy.py`, analytics puro): horizonte por plantilla con `DEFAULT_MAX_HOLDING_PERIOD_DAYS`, leído de `trading_policy_templates` con import perezoso (sin ciclo `analytics ↔ application`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **B2**  | **`PositionState.holdingDeadlineAt` / `invalidationPrice`** (aditivos): emitidos en `to_dict()` **solo si existen** (misma doctrina que `lifecycleState`: ausente = "no persistido"), con round-trip y rehidratación, y congelados en `build_position_state_from_fill`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **B3**  | **`TIME_EXIT`/`THESIS_EXIT` en el FSM**: dos eventos de gestión que llevan a `EXIT_PENDING`; `is_thesis_invalidated`/`worst_adverse_price` (analytics, sobre el MAE persistido) como fuente única del juicio                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **B4**  | **D2 (dinero)**: `position_decision` deja de devolver `REVIEW` ante `THESIS_INVALIDATION`/`thesis_invalid` ⇒ **`EXIT`**. Bajo reconciliación `CRITICAL` sigue mandando el veto de la rama de arriba (la invalidación **no** es una salida protectora): el veto queda **declarado**, no silenciado                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **B5**  | **Worker (E1+E3)**: el nacimiento pasa `max_holding_period_days` y el nivel de invalidación; la gestión recibe `now` **y** `expires_at` (sin ambos, `TIME_STOP` no puede dispararse); `_v2_journal_exit_request` journaliza `time_exit`/`thesis_exit` y avanza el FSM con la posición **viva** (no la copia previa al ratchet)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **B6**  | **Worker (E2)**: `_v2_atr_geometry` devuelve `(atr, atrSource)` y sustituye la fabricación del 2 % en el origen (que pisaba la rama de ATR real que `plan_v2_tick` ya prefería); `atrSource` se declara **una vez por (símbolo, origen)** y `matrix` de contadores por origen queda como medición interna                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **B7**  | **`atr_unknown`** (reason code nuevo en `portfolio_decision_engine`): con el veto activo una señal sin ATR real cae por su camino normal de NO ENTRY **con un motivo que no miente** (antes habría caído por R/R con un ATR inventado)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **B8**  | **H-1**: `RECONCILED` exige estado **degradado de origen** + `resolved_state` verificado + **coherencia con el hecho de cantidad**; sin cantidad no se puede verificar y se rechaza (no se sale de una degradación a ciegas)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **B9**  | **H-2**: todo `PROTECT` **con efecto** deja traza (memo `_v2_protect_noop_stop`, una vez por stop) y la **marca del tick** (pico + MFE/MAE) se persiste cuando cambia de verdad (`_mark_observation_changed`) — con dos testigos medidos por separado (MAE y pico en precio)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **B10** | **H-3/H-4/H-5**: `PARTIAL_EXIT` ya no arma el trailing; `compute_trail_stop` **sin pico devuelve `None`** (no cae al precio de entrada); los guardas de finitud usan `math.isfinite` (un `+inf` no pasa por "positivo")                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| **B11** | **H-6/H-7**: `lifecycleState: null` **explícito** degrada en la rehidratación (no se lee como "no persistido"); el FSM es **forward-only** (`_LIFECYCLE_LADDER` + `_forward_target`: una transición cuyo destino nominal ya quedó atrás se queda en el estado actual en vez de retroceder)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| **B12** | **Tests**: **40 nuevos** (+ los **3 PG** de B13 = **43**) y 3 renombrados — **8** en `test_exit_plan.py` (E1/E3: horizonte, congelación del techo, `TIME_STOP` de un techo congelado, nivel de invalidación, invalidación cruzada/recuperada/por dirección), **9** en `test_position_lifecycle.py` (H-1/H-3/H-4/H-5/H-6/H-7 y los eventos `TIME_EXIT`/`THESIS_EXIT`), **3** en `test_position_decision.py` (D2 y `TIME` como `next_event`), **6** en `test_auto_v2_entry.py` (E2: veto, `atr_unknown`, `AtrSource` fail-closed) y **2** en `test_position_manager.py` + **1** en `test_v127_golden_path_fail.py` (D2 en el camino mesa) — **11 de worker** en el fichero nuevo `apps/api-python/tests/test_auto_v2_lifecycle_clock_thesis.py` (nacimiento congelado, `TIME_EXIT` real, invalidación que vende, no-atribución del stop-out, durabilidad de la marca adversarial, ATR real declarado y veto) — más `test_auto_v2_worker_integration.py`, **sin tests nuevos** (adaptado a que el journal ya no empieza por la decisión) |
| **B13** | **PG**: **3** tests nuevos de durabilidad en `test_auto_v2_lifecycle_pg.py` (3 → **6**): techo congelado y superviviente al reinicio, invalidación confirmada durable y geometría con ATR real, con el gate fail-if-skipped `AUTO_V2_LIFECYCLE_PG_REQUIRED` que ya existía (el job `auto-v2-durable-pg` de CI da **39 passed, 0 skipped**)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| **B14** | **CI**: el fichero hermético nuevo entra en la red de los dos jobs offline — en `quality` (`python-ci.yml`) lo **cubre el pase de directorio** `apps/api-python/tests`, y en `python` (`release-tag-ci.yml`) va **explícito** en su lista por fichero — y los ficheros PG siguen en el `--ignore` de los jobs offline (un skip mudo no certifica)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |

### B13 — Matriz de mutaciones **medida** (13 mutaciones, 13 rojos)

Cada mutación se aplicó sobre el árbol de trabajo, se corrió el target acotado y **se revirtió
verificando el contenido exacto** (el fallo de proceso de la auditoría de 2a — medir con el árbol
moviéndose — no puede repetirse aquí):

| #   | Mutación                                                           | Efecto medido                                                          |
| --- | ------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| M1  | La gestión no recibe el techo congelado (`expires_at=None`)        | **1 rojo** (`time_exit` no dispara)                                    |
| M2  | El techo no se congela en el nacimiento                            | **5 rojos** (analytics + worker)                                       |
| M3  | La invalidación no viaja a la decisión (`thesis_invalid=False`)    | **1 rojo** (la posición sobrevive a su tesis)                          |
| M4  | El stop-out se atribuye **además** como salida por tesis           | **1 rojo** (journal mentiroso)                                         |
| M5  | La invalidación confirmada vuelve a `REVIEW` (conducta de 2a)      | **2 rojos** (analytics + camino mesa)                                  |
| M6  | El ATR real se ignora (geometría siempre sintética)                | **2 rojos**                                                            |
| M7  | El veto por ATR real no veta                                       | **1 rojo** (`atr_unknown`)                                             |
| M8  | Sin pico el trailing cae al precio de entrada (H-4)                | **2 rojos**                                                            |
| M9  | `RECONCILED` se acepta desde cualquier estado (H-1)                | **1 rojo**                                                             |
| M10 | La marca no se persiste por el pico favorable (H-2, sensor precio) | **1 rojo** (tras añadir el test que aísla el caso sin memoria en R)    |
| M11 | `lifecycleState: null` explícito no degrada (H-6)                  | **1 rojo**                                                             |
| M12 | La escalera deja retroceder el estado (H-7)                        | **1 rojo**                                                             |
| M13 | La marca no se persiste por el `maeR` (H-2, sensor en R)           | **1 rojo** (tras endurecer el test con un **segundo** extremo adverso) |

Dos mutaciones nacieron **verdes** y **no eran un agujero de cobertura sino una mutación mal puesta**: M5
(«desactivar» la rama dejaba pasar el `full_exit` del plan por la puerta de atrás) y M10/M13 (cada sensor
de la marca tapaba al otro). Las tres se rehicieron para romper **el comportamiento**, no la línea, y los
tests que faltaban se añadieron (el del pico sin memoria en R y el del segundo extremo adverso).

### Verificación medida (árbol final del slice, antes de publicar)

- `ruff check packages/py apps/api-python --config pyproject.toml` (invocación exacta de CI): **All checks
  passed**; `mypy` (invocación de CI, `--follow-imports=silent`): **487 ficheros, 0 issues**;
  `lint-imports`: **4 kept / 0 broken**.
- **Bloques offline de CI** (targets y `--ignore` **extraídos del YAML**, con verificación de que cada
  ruta existe): job `quality` de `python-ci.yml` **1914 passed, 0 failed, 0 skipped** (51,7 s) y job
  `python` de `release-tag-ci.yml` **1925 passed, 0 failed, 0 skipped** (18,4 s). Procedencia declarada:
  se corren **40 rutas** (48 en el job del tag) y los **8 ficheros PG** que en CI saltan rápido por falta
  de servidor aquí se **cuelgan** (el `connect` del DSN no responde ni rechaza: medido), así que van a
  `--ignore`; y se corre con `--noconftest` para no depender del conftest de la app (que también habla con
  PG). Esos ficheros **no** quedan sin certificar: son los que corren con PG real en los jobs dedicados.
- **Errata de esta misma fase (declarada)**: el primer wiring añadió a la lista de `quality` la ruta
  `packages/py/application/tests/test_auto_v2_lifecycle_clock_thesis.py`, que **no existe** (el fichero vive
  en `apps/api-python/tests`, que ese job ya recolecta entero); con la invocación de pytest eso es **exit 4**
  y habría puesto **rojo** el job. Lo detectó el verificador de rutas del runner al re-medir con la lista
  **extraída del YAML** (en vez de una copia a mano, que fue el origen del error). Corregido: la ruta se
  eliminó y en `release-tag-ci.yml` se usa la **correcta** explícita.
- **PG real: NO medido en esta máquina** (mismo motivo, medido y declarado). La certificación de durabilidad
  de 2b la aporta CI en `auto-v2-durable-pg` (`python-ci.yml`) y `lifecycle-pg` (`release-tag-ci.yml`), con
  el gate `AUTO_V2_LIFECYCLE_PG_REQUIRED=1` (un skip es FALLO). Este pack **no** afirma haberlos corrido
  localmente.
- **CI real (sellado)**: `Python CI` **GREEN 5/5** en `main` @ `4ea8c72a` (run
  [`35268151108`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35268151108): `quality` **1914 passed,
  38 skipped**, `auto-v2-durable-pg` **39 passed, 0 skipped** con el gate, `lifecycle-pg` per-commit 13
  passed) y **GREEN 5/5** en la ref del tag (run
  [`35268256591`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35268256591)); tag anotado
  **`v2.42.1-beta` → `4ea8c72a`** y `Release tag CI` (run
  [`35268256718`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35268256718)) **GREEN 10/10 con
  `certify` en `success`** — job `python`: **1925 passed, 35 skipped** y `mypy` **487 ficheros 0 issues**;
  job `lifecycle-pg` (PG real): **144 + 45 passed**, que es donde se certifican los PG de durabilidad de
  2b —, y `Frontend CI`, `Optimize lab`, `Fase 2 scientific` y `Gitleaks` en verde.

## [1.67.0-beta] — V2.42 · AUTO-2 Position Lifecycle FSM & Real Protection — 2026-09-17

**Sin migración** (el head de Alembic sigue en `042_portfolio_reservations`): el ciclo de vida de la
posición vive en `sim_auto_positions.position_state` (JSONB, migración `040`) y en las columnas ya
existentes. Cierra el agujero que dejaron `AUTO-1A`/`AUTO-1`: el **`stop_update` que proponía la gestión se
descartaba** (`position_manager_package` solo leía `order_action`/`order_qty`), así que `current_stop`
quedaba **congelado en el valor de nacimiento** — ni break-even ni trailing existían en AUTO — y un
`PROTECT` colapsaba a `hold → hold_no_op` **mudo**, con una posición de stop rebasado que podía quedarse
sin vender. AUTO-2 instala un **FSM de posición explícito y persistido**, un **ratchet de stop real en R**,
la **degradación fail-closed** de las posiciones adoptadas sin estado verificable y la **política T1/T2
única** (MODERATE 0.3/0.3).

| #       | Qué                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A1**  | **`position_lifecycle.py`** (analytics puro, sin I/O ni reloj): `PositionLifecycleState` (13 estados, incluidos `RECONCILIATION_REQUIRED`/`PROTECTION_MISSING`), `PositionLifecycleEvent` (14 eventos), `ALLOWED_TRANSITIONS` como **tabla explícita** y `apply_lifecycle_event`/`advance_lifecycle` **fail-closed**: una transición no listada **no avanza** (`accepted=False`, motivo `lifecycle_transition_rejected`) y un estado desconocido **degrada**, nunca se interpreta como "sin protección"                                                                                                                                                                                                                             |
| **A2**  | **`PositionState.lifecycle_state`** (aditivo) con `to_dict()` que emite `lifecycleState` **solo si no es `None`** (preserva el canario de igualdad exacta de `test_sim_durable_v2_state.py`), `trailing`/`protection_state` **tipados** (`TrailingStateDict`/`ProtectionStateDict`) y rehidratación que **degrada a `RECONCILIATION_REQUIRED`** cualquier estado desconocido o inconsistente con el hecho de cantidad (p. ej. `CLOSED` con posición viva). `status` sigue siendo el hecho de cantidad/break-even: `derive_position_status` pasa a ser **proyección** del FSM cuando está definido (cero blast radius en los ~30 lectores de `.status`)                                                                              |
| **A3**  | **Trailing en R** (dueño único en analytics): `compute_trail_stop = highWatermark − trail_distance_r × initial_risk` (long) sobre la anchura por plantilla (`TRAIL_DISTANCE_R_BY_WIDTH`: tight 0.75 / medium 1.0 / wide 1.25 — tabla que **preexistía** en `exit_policy.py`; lo nuevo es el cálculo y su anclaje al pico persistido), armado tras T1 (`is_trail_armed`) y con **H2 nunca-empeorar** (`stop_worsens` ⇒ devuelve el stop vigente con override auditado pendiente). `apply_position_mark` pasa a ser el **único writer** del extremo favorable (`trailing.highWatermark`). **Salvedades de la auditoría externa (H-3/H-4)**: `PARTIAL_EXIT` también lo arma (T2 sin T1) y sin pico persistido cae al precio de entrada |
| **A4**  | **Política T1/T2 única**: `position_decision` resuelve **siempre** `resolve_exit_policy(template_id)` (MODERATE 0.3/0.3). Antes `template_id=None ⇒ policy=None ⇒ fallback 0.5/1.0`, así que los dos caminos AUTO cerraban T1 con fracciones **distintas**                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **A5**  | **El stop deja de descartarse**: `position_manager_stop_update(result)` surface el `stop_update` de un `PROTECT` (solo finito y positivo; `None`/NaN/0/negativos = no utilizable); `plan_v2_position_outcome` acepta `trail_hint`/`trail_stop`; `run_auto_cycle` pasa `template_id` y journaliza `stopUpdate`. El spine **no cambia**: `PROTECT` sigue sin emitir orden (`DecisionPackage` solo SELL) pero `suggested_price` deja de estar congelado                                                                                                                                                                                                                                                                                |
| **A6**  | **`protection_compat.py`** (application): dueño único de la política legacy con **dos modos declarados** — `pct` (compat flag-off, reproduce los umbrales `v2.39.x` y sus fracciones) y `r` (V2, delega en `compute_trail_stop`). Incluye la **traducción** del vocabulario legacy al del FSM (`protective_stop`→`EXIT_REQUESTED`, `t1_exit`→`T1_HIT`, `trailing_stop`→`PROTECT_APPLIED`, `session_close`→`EXIT_REQUESTED`); `ProtectionConfig` queda como **value object** (delega su lógica), no como motor                                                                                                                                                                                                                       |
| **A7**  | **Worker — ratchet real**: `_v2_position_package` pasa a **async** y aplica el `stop_update` con `apply_position_current_stop` (H2) → actualiza `self._v2_positions` y **persiste aunque no haya orden** (un ratchet no vende); todo desenlace **con efecto** se journaliza (`stop_ratchet_applied`, `stop_ratchet_rejected`, `protect_requested`) y `trail_hint` solo se declara cuando hay un stop **real** que proponer. **Matiz de la auditoría externa (H-2)**: en el estado estacionario del trailing (mismo stop, mismo `lifecycle_state`) **no** se journaliza nada — el absoluto "ningún `PROTECT` queda mudo" es falso; lo correcto es "todo `PROTECT` **con efecto** deja traza"                                         |
| **A8**  | **FSM en el ciclo de vida**: `_v2_track_entry` emite `ENTRY_FILLED → OPEN`; `_v2_track_reduce` emite `T1_HIT`/`PARTIAL_FILL`/`EXIT_FILLED` y **arma el trailing con el T1** (`mark_trailing`) para que el reinicio no lo re-derive; el JSONB guarda `lifecycleState` y el `trailing.highWatermark` viaja con la posición **marcada** (antes se persistía el pico de nacimiento)                                                                                                                                                                                                                                                                                                                                                     |
| **A9**  | **Adopción degradada (fail-closed)**: sin estado verificable (plan de un tag anterior, o sin plan durable que rehidratar) la adopción se declara `RECONCILIATION_REQUIRED` + `PROTECTION_MISSING` con `source` (`plan`/`reconstructed`), se **journaliza con atención alta** y conserva/reconstruye el **mejor stop conocido**; si ni la geometría de emergencia es construible se declara la ausencia de protección **sin stop sintético**                                                                                                                                                                                                                                                                                         |
| **A10** | **Invariante de oro**: **ninguna salida protectora se veta** por reconciliación degradada (stop rebasado, trailing alcanzado, riesgo de cartera siguen vendiendo con el libro sin cuadrar); el límite queda declarado: **tomar beneficio sí espera** al veredicto                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **A11** | **Reason codes y journal**: `POSITION_LIFECYCLE_REASONS` (`stop_ratchet_applied`, `stop_ratchet_rejected`, `protect_requested`, `protection_missing`, `reconciliation_required`, `lifecycle_transition_rejected` + los motivos del FSM re-exportados desde analytics) y helper único de journal de gestión                                                                                                                                                                                                                                                                                                                                                                                                                          |
| **A12** | **Tests**: 29 herméticos de FSM (producto cartesiano de eventos con transiciones inválidas rechazadas, reinicio por cada estado intermedio, degradación de estados no verificables, ratchet nunca-empeorar, trailing solo tras T1) + 17 herméticos de aplicación (portes **V2=1** de los 5 tests legacy de `A9.1` con semántica R, shim `pct` reproduciendo `v2.39.x`, invariante de no-veto, política única) + 3 de worker (ratchet aplicado/persistido/journalizado, reinicio que sigue ratcheando, `PROTECT` nunca mudo) + 3 **PG reales** (rehidratación por estado y degradación medida en PostgreSQL)                                                                                                                         |
| **A13** | **CI**: entradas **explícitas** para los herméticos nuevos en `python-ci.yml` (`quality`) y `release-tag-ci.yml` (`python`); el fichero PG entra en los jobs con PG real (`auto-v2-durable-pg` / `lifecycle-pg`) con gate **fail-if-skipped** `AUTO_V2_LIFECYCLE_PG_REQUIRED=1` y en el `--ignore` de los jobs offline (un skip mudo no certifica)                                                                                                                                                                                                                                                                                                                                                                                  |
| **A14** | **Dualidad declarada**: `docs/engineering/audit-pack-v2.42-auto-2-position-lifecycle-2026-09-17.md` + `arranque-auditor-...` dejan explícito que la autoridad sigue siendo `sim_auto_positions` (JSONB `position_state`) y que `position_states` (ADR-033) **no se toca** en este slice; la deuda (ATR real, `TIME_EXIT`/`THESIS_EXIT`, horizonte de tiempo) queda asignada a **2b/AUTO-3**                                                                                                                                                                                                                                                                                                                                         |

### A1–A3 — El FSM y el trailing en R

El FSM no sustituye a `status`: lo **complementa** con la única afirmación que el stop no puede hacer
(protección explícita, entrada pendiente, T1 como transición, degradación declarada). `CLOSED` es
terminal, `FLAT` no tiene posición, y la familia degradada **no es un pozo sin salida**: un hecho
observable (un fill, un T1, un ratchet de stop, una salida) la **re-verifica** por la misma tabla de
gestión, y `RECONCILED` necesita un estado resuelto explícito (no se adivina la vuelta). El trailing se
mide en **R sobre `initial_risk`** (no en % del precio): sin riesgo inicial **no hay trailing** y el
llamante debe declararlo, no sustituirlo por un porcentaje inventado.

### A5–A8 — El stop deja de descartarse (el dinero)

El `PROTECT` es la única decisión que **no emite orden** y sí mueve el stop; su `stop_update` viajaba en el
`PositionManagerResult` y **moría en `position_manager_package`**. Ahora se surface, se aplica con la red de
seguridad de `apply_position_current_stop` (nunca empeora sin override) y **se persiste aunque el tick no
venda**: sin esa persistencia el tick siguiente parte del stop viejo y la protección no existe. El
`highWatermark` se escribe desde la posición **marcada** del outcome, así que el trailing tiene memoria
propia en el JSONB y el reinicio continúa el ratchet desde el estado persistido (`trailing.highWatermark`
intacto, medido en PG real).

### A13 — Matriz de mutaciones **medida**

Cada mutación se aplicó sobre el árbol de trabajo, se corrió la suite del slice y se revirtió (ninguna se
declara sin medir):

| #   | Mutación                                                          | Efecto medido                                                                                                                                                                           |
| --- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1  | `apply_lifecycle_event` acepta transiciones no listadas           | **3 rojos** (`test_invalid_transitions_are_rejected_without_advancing`, `test_cartesian_product_is_total_and_fail_closed`, `test_advance_lifecycle_rejected_leaves_position_untouched`) |
| M2  | La rehidratación **no** degrada un estado inconsistente           | **2 rojos** (hermético de analytics **y** el PG real `test_v2_unverifiable_state_degrades_on_rehydration`)                                                                              |
| M3  | `compute_trail_stop` pierde el clamp nunca-empeorar (H2)          | **1 rojo** (`test_trail_stop_never_worsens`: 103 ≠ 107)                                                                                                                                 |
| M4  | El worker descarta el `stop_update`                               | **3 rojos** (ratchet aplicado/persistido, reinicio que sigue ratcheando, `PROTECT` nunca mudo)                                                                                          |
| M5  | La reconciliación `CRITICAL` veta también las salidas protectoras | **2 rojos** (`test_stop_hit_still_sells_with_recon_drift`, `test_ratchet_still_applies_with_recon_drift`)                                                                               |
| M6  | `_v2_track_reduce` no arma el trailing con el T1                  | **1 rojo** (`trailing_status == "armed"` en el ratchet real)                                                                                                                            |
| M7  | La adopción sin estado verificable no se degrada                  | **1 rojo** (`test_v2_adopts_with_reconstructed_geometry_without_durable_plan`)                                                                                                          |
| M8  | Vuelve el fallback 0.5/1.0 sin `template_id`                      | **3 rojos** (`test_t1_reduce_is_moderate_without_template`, `test_v2_t1_reduces_when_no_retracement`, `test_v2_t1_partial_fraction_matches_legacy_shim`: 5.0 ≠ 3.0)                     |
| M9  | El shim legacy evalúa T1 antes que el trailing                    | **2 rojos** (`test_exit_reason_trailing_wins_over_t1`, `test_restart_with_open_position_trailing_uses_persisted_watermark`: `t1_exit` ≠ `trailing_stop`)                                |
| M10 | Un `PROTECT` sin stop utilizable queda mudo                       | **1 rojo** (`protect_requested` ausente en el journal)                                                                                                                                  |
| M11 | El trailing se considera armado antes de T1                       | **3 rojos** (`test_trail_stop_not_armed_before_t1`, `test_trailing_status_of_birth_stub_is_inactive`, `sin T1 no hay trailing`)                                                         |

### Verificación medida (árbol final del slice)

- `ruff check packages/py apps/api-python --config pyproject.toml` (invocación exacta de CI): **All checks
  passed**; `mypy` (invocación de CI, `--follow-imports=silent`): **487 ficheros, 0 issues**;
  `lint-imports`: **4 kept / 0 broken**.
- Job **`quality`** completo (comando **extraído del YAML**, con las listas nuevas y sus `--ignore`):
  **exit 0** en CI (`1869 passed, 38 skipped`, 114,4 s; run `35214904914`, job `quality`). Ojo con la
  procedencia: la medición local de esta misma tabla dio `1903 passed, 0 skipped` porque la sesión tenía
  `DATABASE_URL` y los seis `*_PG_REQUIRED` exportados, de modo que las suites gated corrieron **dentro**
  del job en vez de skipear; la cifra que manda es la de CI.
- Bloque offline del job **`python`** de `release-tag-ci.yml` (extraído del YAML): **exit 0** en CI
  (`1880 passed, 35 skipped`, 60,7 s; run `35214985392`), con la misma salvedad de procedencia (local:
  `1915 passed`).
- Batería completa de paquetes `uv run pytest packages/py -q`: **2825 passed**, 1 skipped (Ollama
  ausente: entorno) y 1 xfailed ⇒ **0 rojos**.
- PG real: batería `auto-v2-durable-pg` **36 passed** (incluye los 3 nuevos de lifecycle durable), bloque
  `lifecycle-pg` de `release-tag-ci.yml` (comando y `env:` extraídos del YAML) **141 passed** — golden,
  auth, outbox, integridad financiera, estado del motor AUTO, finanzas simuladas, **bucle real del
  scheduler con cero intervención humana** y fencing de ejecución — y los 9 tests legacy de protección +
  los 4 portes V2=1 + 35 de integración del worker en verde.
- **CI de GitHub (sellado)**: `Python CI` **GREEN** en `main` @ `35e38c24` (run `35214904914`, 5/5) y en
  la ref del tag (run `35214985401`, 5/5); `Release tag CI` **GREEN** @ `v2.42-beta` → `35e38c24` (run
  `35214985392`, 10 jobs ejecutados + `certify`: **9 requeridos** más el opt-in
  `playwright (integrated E2E)`, `skipped` por diseño). El **primer sellado** del tag (sobre el commit de fase
  `6e53294f`, run `35213906948`) puso **rojo** `auto-v2-durable-pg`: el test durable V2 **sorteaba**
  instrumento (lotería de la cola SIM) y el **mismo commit** había pasado 5/5 minutos antes en `main`
  (run `35213904170`) ⇒ **flaky preexistente, no regresión** del slice; se arregla en `35e38c24`
  (test-only: identidad determinista que llena) y el tag se **re-apunta** a ese commit.

### Deuda declarada (no silenciosa)

1. **`TIME_EXIT`/`THESIS_EXIT`, ATR real y horizonte de tiempo** no entran en este slice: la salida por
   tiempo y la invalidación de tesis siguen fuera del FSM (asignadas a **2b/AUTO-3**).
2. La rehidratación **degrada** un estado no verificable pero **no lo repara**: resolverlo es
   responsabilidad de la reconciliación (el FSM declara, no adivina).
3. `position_states` (ADR-033) **no** se toca: sigue existiendo una segunda superficie de estado de
   posición. La dualidad está **declarada** en el audit-pack, no resuelta.
4. El trailing depende de `trailing.highWatermark`, que sólo se puebla si la posición se marca: una
   posición **sin ticks** (sin mark) no tiene pico y por tanto no puede ratchear.
5. `ProtectionConfig` se conserva como **value object** por compatibilidad del camino flag-off; su lógica
   vive en `protection_compat` (un dueño único), pero la dataclass sigue exportándose desde el worker.

### Auditoría externa post-sellado (2026-09-17)

Tres auditorías independientes de solo lectura sobre `da93cd20` (código idéntico al tag). **Sin P0**;
sello confirmado (5 runs, tag↔commit, sin migración) y **5 mutaciones reproducidas con los rojos
exactos** (M1, M3, M4, M5, M7). **7 hallazgos de código** (afirmación más absoluta que el código) quedan
como **deuda declarada y criterio de aceptación de 2b**, con evidencia en el §9 del audit-pack:
`RECONCILED` sin verificación (H-1), no-op del trailing sin journal (H-2), `PARTIAL_EXIT` arma trailing
sin T1 (H-3), sin pico cae al precio de entrada (H-4), `+inf` no fail-closed (H-5), `lifecycleState:
null` inconsistente sin degradar (H-6) y 7 transiciones que retroceden (H-7). El **owner decide no tocar
el código de 2a**: se corrigen las afirmaciones del documento y se declara la deuda. Errata de mis
cifras (corregidas arriba): "7/28 citas de log" era falso (el fichero aparece 1 vez en el comando y la
sustancia se prueba con el `--collect-only` de 36 tests), "36 ficheros" eran 30, "10 jobs requeridos"
eran 9 + 1 opt-in `skipped`, `TRAIL_DISTANCE_R_BY_WIDTH` **preexistía** y un `mypy` del relevo estaba
rotulado "exacto de CI" sin serlo (incluía `analytics/src`, que CI no compila).

## [1.66.0-beta] — V2.41 · AUTO-1 Portfolio Reservation Engine — 2026-09-17

**Migración aditiva `042_portfolio_reservations`** (Alembic head `041_unique_natural_keys` → `042_portfolio_reservations`).
Sustituye la **reserva artesanal intra-tick** (`committed[]` + `_working_snapshot` dentro de `plan_v2_tick`)
por un **motor de reservas explícito**: cada aprobación produce `Decision + Reservation`, la reserva tiene
**identidad**, **siete dimensiones** comprometidas, **coste real**, **ciclo de vida** (fill / cancelación /
reinicio / rollback) y **`replay`**; y sobrevive al proceso porque tiene espejo durable. Invariante que
instala: **no existe aprobación sin reserva y no existe reserva sin liberación**
(`reserved_cash == Σ reservas vivas`, medido). Deuda declarada de `V2.40.4`/`V2.40.5` cerrada: la
liberación explícita del capital en vuelo y el índice `execution_events(account_id, status)`.

| #       | Qué                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R1**  | **`PortfolioReservation` + `ReservationLedger`** (`bolsa_analytics.cognitive.portfolio_reservation`, puro, sin I/O ni reloj): identidad (`reservation_id`, `account_id`, `tick_id`, instrumento, sector, estrategia, lado) + siete dimensiones (`reserved_cash`, `reserved_risk`, `asset_exposure`, `sector_exposure`, `correlation`, `strategy_capacity`, `liquidity_capacity`) + coste + ciclo de vida. `reserve()` es **idempotente-rechazante**: una segunda reserva con la misma identidad devuelve `None`, nunca sobrescribe |
| **R2**  | **Ciclo de vida explícito**: `OPEN`, `RELEASED_BY_FILL`, `RELEASED_BY_CANCEL`, `RELEASED_BY_RESTART`, `RELEASED_BY_ROLLBACK`. Una liberación **parcial** escala capital/riesgo/exposición a la cantidad viva (lo llenado deja de ser reserva y pasa a ser posición; la cola **sigue** siendo capital comprometido) y una total la deja a 0 dejando el importe original en el evento de alta (historia inmutable). `release` es **idempotente** (segunda llamada = `None`)                                                          |
| **R3**  | **`replay(eventos)`** reproduce el libro exactamente (misma aritmética, orden determinista) ⇒ "¿cuánto riesgo había reservado AUTO antes de lanzar esta orden?" tiene respuesta reproducible                                                                                                                                                                                                                                                                                                                                       |
| **R4**  | **`PortfolioRiskState`**: `gross_risk`, `net_risk`, `reserved_risk`, `pending_risk`, `sector_risk`, `strategy_risk` y `correlation_adjusted_risk` (cota **superior** conservadora: declarar correlación positiva la sube, nunca descuenta diversificación no medida), con `measurement` fail-closed compartido con `PositionLedger`                                                                                                                                                                                                |
| **R5**  | **Coste real de negociación** en el sizing: `estimate_trading_cost` (comisión con el calendario real de `account_settings`, spread/slippage/gap en bps reutilizando los defaults de `cost_model_v2`) deriva `ExpectedLoss` / `WorstCaseLoss` / `GapAdjustedLoss`; `compute_allocation` ajusta la cantidad por `risk_real = stop_loss + comisión + spread + slippage`, publica `risk_real`/`risk_real_pct`/`trading_cost` y declara `cost_unmeasured` (nunca "coste = 0")                                                           |
| **R6**  | `plan_v2_tick` sustituye `committed[]`/`_working_snapshot`/`_committed_position` por el `ReservationLedger` del tick y publica `V2TickPlan.reservations` + `.risk_state` (nuevos); si la reserva no se puede construir, la aprobación se **degrada a veto** (`reservation_failed`) en vez de emitir una orden sin compromiso trazable                                                                                                                                                                                              |
| **R7**  | **Migración `042`**: tabla `portfolio_reservations` (PK `reservation_id`, dimensiones, coste, estado, `lease_generation`) + índices por `(account_id, status)`, `(account_id, sector)` y `(account_id, created_at DESC)` + **el índice que faltaba** `execution_events(account_id, status)` (cierra la deuda de `V2.40.4` §5.1 y `V2.40.5` §5.2). Aditiva, sin backfill, `downgrade()` completo, espejo 1:1 en `tables.py`                                                                                                         |
| **R8**  | **`reservation_store.py`**: `ReservationStore` (Protocol) + `InMemoryReservationStore` + `PostgresReservationStore` (idempotente: `ON CONFLICT DO NOTHING` + `UPDATE`, `commit()` explícito)                                                                                                                                                                                                                                                                                                                                       |
| **R9**  | **Worker**: las reservas vivas pasan a ser la **autoridad** de `reserved_cash`/`pending_risk` (una traza de `execution_events` de un instrumento con reserva viva **no** se suma otra vez: la reserva la cubre) y el productor anterior queda como **reconciliación de arranque**. Liberación por **fill** (parcial o total), por **cancelación** y por **reinicio**; veto `reservation_already_live` si ya hay reserva viva del instrumento y `reservation_unmeasurable` si el libro no es legible                                |
| **R10** | **Bug real corregido en el camino**: `coerce_applied_fill_fact` solo aceptaba `applied_at` como `str`, así que **todo** hecho leído de PostgreSQL quedaba **sin fecha** (el fold del `PositionLedger` perdía su orden canónico y la reconciliación no podía ventanear "¿este fill es posterior al alta de la reserva?"). Normaliza `str` **y** `datetime` → ISO                                                                                                                                                                    |
| **R11** | CI: gate propio **`AUTO_RESERVATION_PG_REQUIRED`** en `auto-v2-durable-pg` (`python-ci.yml`) y `lifecycle-pg` (`release-tag-ci.yml`); el fichero PG entra en el `--ignore` de los jobs offline (un skip mudo no certifica) y el test de snapshot de evidencia sube su head esperado a `042`                                                                                                                                                                                                                                        |

### R1–R3 — La reserva como objeto con ciclo de vida

La reserva es un `frozen` dataclass con identidad: el `reservation_id` deriva de la decisión
(`RES-{decision_id}`), así que **la misma aprobación no puede reservar dos veces** (ni dos candidatas del
mismo tick pueden pisarse) y el alta tiene fecha, cuenta y tick. Las dimensiones **no son decorativas**:
`reserved_cash` es el notional comprometido (lo que el snapshot descuenta de caja/poder de compra) y
`reserved_risk` el presupuesto de riesgo consumido (`riskAmount`), que con coste real es **mayor** que la
pérdida del stop. El `TradingCost` viaja aparte para que el journal pueda mostrar la pérdida esperada
real. Una reserva **sin cuantificar** no se descarta en silencio: cuenta como no medida y degrada el
`measurement` del libro (fail-closed).

`ReservationLedger` no tiene reloj ni I/O: `reserve`/`release`/`release_by_fill`/`release_by_cancel`/
`release_by_restart`/`rollback`/`live`/`reserved_cash`/`reserved_risk`/`by_sector`/`by_strategy`, más
`replay`. El `rollback` libera **solo** las reservas del tick pedido (la reversión de un tick no toca el
resto del libro).

### R4–R5 — Riesgo de cartera y coste real en el tamaño

`PortfolioRiskState` se compone con las posiciones abiertas (su desglose sectorial medido; una posición sin
`risk_amount` **no** aporta 0, cuenta como no medida) y con el libro de reservas. `pending_risk` deja de
ser un suelo: el riesgo de la orden en vuelo entra por la reserva. En el sizing, sin `cost_model` el
comportamiento es el histórico (retrocompatible); con él, la cantidad se recorta para que la **pérdida
esperada real** quepa en el presupuesto, y si algún componente no es medible se declara `cost_unmeasured`
en vez de asumir gratis.

### R9 — Autoridad y liberación (el compromiso de `V2.40.5`)

`reserved_cash` y `pending_risk` del libro pendiente se derivan de las **reservas vivas**; las trazas de
`execution_events` solo entran si su instrumento **no** tiene reserva viva (crash entre la captura del fill
y el alta de la reserva). La cola en `RETRY` sigue siendo **capital reservado** — nunca posición ni
realizado — y ahora tiene sujeto: la reserva que la cubre. Al reiniciar, la reconciliación libera por fill
lo materializado (parcial incluido) y libera entera la reserva de una orden que murió sin llenarse.

### Matriz de mutaciones **medida**

Cada mutación se aplicó sobre el árbol de trabajo, se corrió la suite y se revirtió:

| #   | Mutación                                                                 | Efecto medido                                                                                                                                         |
| --- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1  | `_working_snapshot` devuelve la foto base (muere la autoridad del libro) | **7 rojos** (3 de `test_portfolio_reservation.py`, 3 intra-tick y 1 de sector de `test_auto_v2_entry.py`)                                             |
| M2  | La liberación parcial no escala las dimensiones (`factor = 1`)           | **2 rojos** (`test_release_by_fill_partial_scales_and_keeps_the_tail_reserved`, `test_release_by_fill_of_a_tick_reservation_keeps_the_tail_reserved`) |
| M3  | El libro pendiente suma la traza **y** la reserva (sin `covered`)        | **1 rojo** (`test_retry_trace_keeps_the_reservation_as_reserved_capital`: 20000 ≠ 10000)                                                              |
| M4  | `coerce_applied_fill_fact` vuelve a aceptar `applied_at` solo `str`      | **2 rojos** (el hermético nuevo y `test_reservation_survives_restart_and_is_released_by_the_materialized_fill` en PG)                                 |
| M5  | El allocator asume coste 0 cuando no es medible                          | **1 rojo** (`test_allocator_declares_an_unmeasurable_cost_instead_of_assuming_zero`)                                                                  |

**Sin mutación**: `ruff` limpio, `mypy` 486 ficheros 0 issues, `lint-imports` 4/0, job `quality` completo
(comando extraído del YAML) **exit 0**, `pytest packages/py` **2779 passed**, PG real en verde
(4 reservas durables, 29 durable/contexto/claves, 2 de proceso, bucle ×30 del scheduler **0 fallos**).

### Deuda declarada (no silenciosa)

1. **`correlation`, `strategy_capacity` y `liquidity_capacity`** se reservan cuando el contexto las
   declara; hoy el tick no tiene universo de correlación ni capacidad por estrategia, así que quedan
   `None` (no medidas) y `correlation_adjusted_risk` **no descuenta** diversificación. Poblarlas es
   `AUTO-3`/`AUTO-4`.
2. El **productor desde `execution_events`** no se borra: queda como reconciliación de arranque (es la red
   de seguridad del crash entre fill y alta de reserva).
3. La tabla `portfolio_reservations` **crece con cada aprobación** (es historia: una reserva liberada no se
   borra). No hay job de compactación/purga declarado todavía.
4. `pending_risk` es medible **solo** si la reserva declara riesgo; sin dato el agregado baja de medición y
   el motor **veta** aperturas (las salidas protectoras siguen permitidas).
5. **`lease_generation`** se persiste (espejo 1:1 con la tabla) pero **no** hay lógica de _lease_ para
   reservas: no existe adquisición/robo de propiedad entre procesos. La exclusión es por identidad de
   reserva (`RES-{decision_id}`) y por cuenta, no por fence.
6. El índice de `execution_events` se crea **plano** `(account_id, status)`, no parcial (`WHERE status <>
'APPLIED'` dejaría fuera la lectura de `APPLIED`, la autoridad de posición desde `V2.40.5`); decisión
   documentada en el docstring de la migración.

## [1.65.5-beta] — V2.40.5 · AUTO-1A Position Materialization & Partial-Fill Integrity — 2026-09-17

**Sin migración** (head sigue en `041_unique_natural_keys`). Cierra el **P0** de las auditorías de
`v2.40.4-beta`: `simulated_fill_schedule` puede dejar una orden **parcialmente llena** (la cola queda
en `RETRY`, dinero NO movido), pero el worker contabilizaba la cantidad **pedida**. Resultado: la
posición real (`73,5`) y el exit (`200`) divergían, el hueco viajaba a riesgo, exposición, equity y
protección, los chunks en `RETRY` desaparecían del libro de órdenes pendientes y el invariante de
equity del test de scheduler descuadraba de forma **intermitente** (era el flake que la auditoría
midió, no una casualidad de CI).

| #        | Qué                                                                                                                                                                                                                                                                                                                                      |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P0.1** | La posición pasa a ser **Σ fills `APPLIED`** (`POSITION = Σ APPLIED BUY − Σ APPLIED SELL`). `_settle` deja de descartar los outcomes del apply y devuelve `applied`/`unapplied`/`requested`; `_open`, persistencia, `PositionState` (T1/stop/trailing) y libros usan la cantidad **aplicada**                                            |
| **P0.2** | Nuevo **`PositionLedger`** (read-model puro, `bolsa_analytics.cognitive`) derivado de `execution_events(status='APPLIED')` + `sim_fill_finance_context`. **Sin migración**: la persistencia con rollback/replay es `AUTO-1`                                                                                                              |
| **P0.3** | El exit se dimensiona contra la posición **materializada** con invariante duro `applied_qty <= held`: una venta aplicada de más se declara (`exit_qty_over_position`) y aplana, jamás deja posición negativa                                                                                                                             |
| **P0.4** | Fail-closed del libro: `list_applied` acotado por `limit`, `get_many` batch, `read_applied_fill_facts` devuelve `UNKNOWN` (nunca un libro "vacío y plausible") si no pudo leerlo entero. Tras un crash, una proyección **inflada** se reconstruye (`REBUILT`) desde Σ `APPLIED`; libro ilegible ⇒ aperturas vetadas y salidas permitidas |
| **P0.5** | Observabilidad (Auditoría 2): `manage_position_outcome` con `PositionManagerSkip` + reason codes `no_mark_data`, `mark_rejected`, `decision_unavailable`, `fill_not_materialized`, `fill_partially_materialized`, `exit_qty_over_position`. El `mark is None` deja de ser un `continue` mudo                                             |
| **P0.6** | El helper de equity de las dos suites PG de jornada completa deriva el realizado **solo** de fills `APPLIED` (helper compartido `tests/applied_fill_equity.py`); suma el contexto entero era la causa medida del flake                                                                                                                   |
| **P0.7** | Suite hermética nueva `apps/api-python/tests/test_auto_v2_partial_fills.py` con **seam determinista de settlement** (parcial fijo `50 + 23,5 = 73,5`, cola en `RETRY`) que ejecuta el camino real de liquidación, más bucle 30/30 del test de scheduler con PG real                                                                      |

### P0.1 — `POSITION = Σ APPLIED` (lo pedido ≠ lo llenado ≠ lo materializado)

`_settle` descartaba los outcomes (`result, _out = ...`) y devolvía **todas** las observaciones del
schedule, incluidas las que quedaron en `RETRY`; `_record_applied_event` las daba por aplicadas. Ahora
`_Settlement` distingue `applied` / `unapplied` / `requested_qty` (con modo _structural_ para el camino
sin `finance_applier`, donde no hay dinero que mover) y todo el dimensionado (posición, persistencia,
`PositionState`, `report.fills`, emits) usa la cantidad **aplicada**. El emit `order` conserva la
pedida y el journal declara ambos números: `fill_partially_materialized` cuando parte de los chunks
quedaron pendientes, `fill_not_materialized` cuando no se movió nada y `fill_unapplied` por chunk
pendiente (que sigue siendo **capital reservado**, visible en el libro de órdenes pendientes).

### P0.2 — `PositionLedger`: el libro de posición como read-model

Módulo puro y determinista (sin I/O ni reloj): `AppliedFillFact` (una fila `APPLIED` con contexto
financiero legible), `LedgerPosition` (`quantity`, `realized_qty`, `remaining_qty`, `average_entry`,
`realized_pnl`, `violations`) y `build_position_ledger(facts, rejected=…)` con orden canónico
`(applied_at, execution_id)`. Reglas de honestidad: una **sobreventa** aplicada es violación explícita
(`oversell_above_position`, `oversell_without_position`) y nunca inventa un corto; una fila no
interpretable **no se descarta en silencio** — baja el `measurement` (`COMPLETE`/`PARTIAL`/`UNKNOWN`),
de modo que "no pude leer el libro" jamás se confunde con "el libro está plano".

### P0.3 — Exit dimensionado por posición materializada

El SELL se clampa contra la posición **materializada** y el invariante `applied_qty <= held` es duro:
si un fill de venta excediera la posición, se aplanan las ventas aplicadas y se journaliza
`exit_qty_over_position` (defensa en profundidad medida con un seam que devuelve 1 000 de más).
`report.fills` cuenta **fills aplicados**.

### P0.4 — Autoridad canónica y recuperación

`execution_events.list_applied(account_id, *, limit)` (protocolo + in-memory + PG:
`WHERE status='APPLIED' ORDER BY applied_at, execution_id`) y `SimFillFinanceContextStore.get_many`
(batch, sin N+1). `applied_fills.read_applied_fill_facts` compone el libro y **declara** sus huecos
(sin store, sin `list_applied`, excepción, sin contexto, `limit` agotado, descuadre
evento↔contexto) en vez de devolver un libro plausible. `CanonicalPositions` transporta las trazas
que sustentan cada cantidad (mismo contrato de `dict` que el seam `canonical_positions_reader`), así
que la reconciliación contrasta el canónico en el mismo acto de leerlo: tras un reinicio con la RAM
vacía, una proyección inflada se reescribe a la materializada (`REBUILT`).

### P0.5 — Skips de gestión con rastro (Auditoría 2)

`manage_position_outcome` devuelve `PositionManagerResult` | `PositionManagerSkip` | `None` (los casos
benignos siguen siendo `None`; `manage_position` mantiene el contrato antiguo). `run_auto_cycle`
journaliza `auto_position_skip` con `attention="high"` para `no_mark_data`, `mark_rejected` y
`decision_unavailable`, y el worker propaga el motivo a `_v2_last_exit_reasons[symbol]`. Los literales
viven en un dueño único (`auto_reason_codes.py`).

### P0.6/P0.7 — Flake del scheduler cerrado y certificado

El helper de equity sumaba **todas** las filas de `sim_fill_finance_context`, incluidas las
planificadas que quedaron sin aplicar ⇒ `equity != initial + realized + unrealized` de forma
intermitente. Ahora `realized_notional_from_applied_fills` (helper compartido por
`test_auto_scheduler_real_pg_zero_human_intervention.py` y `test_a9_scheduler_process_pg_zero_human.py`)
usa solo `execution_events.status='APPLIED'` (cantidad del evento, lado/precio del contexto) y
**falla** si un `APPLIED` no tiene contexto o la cantidad diverge. Nuevo instrumento determinista
`test_equity_realized_ignores_unapplied_fill_context` (BUY aplicado + BUY en `RETRY` + SELL aplicado
⇒ el realizado ignora el `RETRY`) y suite hermética nueva con parcial determinista + bucle **30/30**
del scheduler con PG real, sin retries ni `xfail`.

**Deuda declarada:** sin índice parcial `execution_events(account_id, status)` (lectura acotada por
`limit`); la cola no llena queda como capital en `RETRY` y su liberación explícita es `AUTO-1`
(Reservation Engine); el `PositionLedger` es read-model, sin tabla propia.

## [1.65.4-beta] — V2.40.4 · AUTO Safety & Accounting (TOP_N real, measurement status, órdenes pendientes y validación de TradePlan) — 2026-09-16

**Sin migración** (head sigue en `041_unique_natural_keys`). Cierra los cuatro agujeros de
seguridad/contabilidad de AUTO que destapó la auditoría de `v2.40.2-beta`. Ninguno es cosmético: los
cuatro podían hacer que AUTO gastara dinero que ya estaba comprometido, decidiera sobre un número que
era un suelo disfrazado de total, o emitiera un plan que se contradecía a sí mismo.

| #      | Qué                                                                                                                                                                                                                                                                                                                                         |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F1** | `TOP_N` era un tope de **prioridad**, no de **evaluación**: los candidatos fuera del TOP llegaban sin score y el journal los reportaba como `edge_below_threshold` (**un motivo falso**). Ahora es un tope de evaluación y los excluidos se journalizan con `top_n_excluded` y su score/rank **reales** (`approved <= top_n` es invariante) |
| **F2** | `risk_used` y la exposición agregada se publicaban como un número "completo" sumando solo lo que sabían medir (**un suelo**). Nuevo `MeasurementStatus` (`COMPLETE`/`PARTIAL`/`UNKNOWN`): un agregado incompleto **veta** la apertura                                                                                                       |
| **F3** | `open_orders: int` era un contador **muerto** (siempre 0): el sistema podía gastar dos veces el mismo cash. Nuevo libro de órdenes pendientes (`OpenOrder`) con `reserved_cash`/`available_cash`/`pending_risk`/`pending_exposure` y veto `open_orders_unmeasurable`                                                                        |
| **F4** | `TradePlan` **sin validación**: un plan incoherente se serializaba, viajaba por el journal y acababa dimensionando una orden real. Nuevo `validate_trade_plan` + veto `plan_invalid` con las violaciones en el journal                                                                                                                      |

### F1 — `TOP_N` (tope de evaluación) y journal honesto

`plan_v2_tick` rankeaba todo pero **solo puntuaba el top-N**: los de fuera llegaban con `score=None` y
el motor los rechazaba con `edge_below_threshold`. Es decir, el journal afirmaba una causa falsa (su
edge era válido; simplemente no compitieron) y la semántica real era "solo el top-N es operable".

Ahora `TOP_N` es el **máximo de oportunidades evaluadas** (Opción A de la auditoría, lectura literal):
se decide solo contra la cartera el subconjunto del TOP, y las candidatas fuera de él emiten una
entrada de journal `top_n_excluded` que **porta su `OpportunityScore` y su `rank` reales**, así que el
motivo del no-trade es el verdadero y el ranking completo queda auditable. `run_auto_cycle` usa la
misma regla (`build_top_n_excluded_payload`). `top_n = 0` excluye todo (fail-closed).

### F2 — `MeasurementStatus`: un agregado incompleto es un SUELO

Caso de la auditoría: `Position A → risk_amount = 100`, `Position B → risk_amount = UNKNOWN` producía
`risk_used = 100` cuando la verdad es `risk_used >= 100` y el total es **desconocido**. Lo mismo con
`aggregate_exposure` (saltaba las posiciones sin `market_value`).

Módulo puro nuevo `bolsa_analytics.cognitive.measurement` (`MeasurementStatus`, `coerce_measurement`,
`measurement_from_counts`, `is_complete`, `combine_measurements`). `AutoPortfolioSnapshot.risk_measurement`
y `ExposureBreakdown.measurement` derivan el tri-estado del dato real, el motor veta con
`risk_measurement_partial`/`risk_measurement_unknown`/`exposure_measurement_partial`/
`exposure_measurement_unknown` y el gate se puede apagar **explícitamente**
(`require_complete_measurement=False`), nunca por omisión. Un measurement incompleto **no** bloquea
una salida protectora (invariante con test).

### F3 — Órdenes pendientes: capital y riesgo comprometidos (sin migración)

`Cash = 50.000 €` con `BUY pending = 40.000 €` **no** significa 50.000 € disponibles. AUTO SIM liquida
en el mismo tick, así que el productor real de "órdenes en vuelo" son las filas de `execution_events`
que **no** están `APPLIED` (sobreviven a un crash), con su lado/cantidad/precio en
`sim_fill_finance_context`.

- Módulo puro `bolsa_analytics.cognitive.open_order`: `OpenOrder`, `OpenOrderSummary`,
  `build_open_order`, `summarize_open_orders`, `coerce_open_order`. Honestidad: una **venta** no
  reserva cash ni añade riesgo; una **compra** reserva su notional y su riesgo **solo si alguien lo
  declara** (no se inventa).
- `AutoPortfolioSnapshot.open_orders: int → tuple[OpenOrder, ...]` (**breaking declarado en beta**),
  con `order_book_measurement`, `reserved_cash`, `available_cash`, `pending_risk`, `pending_exposure`
  y `risk_remaining = budget − (risk_used + pending_risk)`.
- `ExecutionEventStore.list_unapplied(account_id, *, statuses, limit)` en el protocolo, in-memory y
  PostgreSQL (`WHERE status IN (...) ORDER BY captured_at DESC LIMIT`).
- `auto_simulation_worker._v2_refresh_open_orders()`: lee el libro una vez por tick **antes** de
  construir la foto, descarta lo ya reconocido por el worker (no cuenta dos veces el mismo dinero) y
  declara `UNKNOWN` ante fallo de lectura, `limit` alcanzado o store sin soporte ⇒ **veta aperturas**
  (nunca "no hay pendientes porque no pude leer").
- `RiskAllocator` acepta `reserved_cash` y resta el capital comprometido del poder de compra, con
  motivo propio `CAP_RESERVED_CASH` (distinto de `CAP_BUYING_POWER`: no es "no queda dinero", es
  "el dinero está comprometido"). La reserva intra-tick descuenta también el notional ya aprobado.

**Deuda declarada:** no hay índice parcial `execution_events(account_id, status)`; la lectura queda
acotada con `LIMIT` + orden por captura y la migración se asigna a la fase Reservation Engine.

### F4 — El plan que sale del motor no puede contradecirse

`TradePlan` no tenía `__post_init__` ni `validate()`: solo el factory armaba la máquina de estados, así
que un plan incoherente (qty > 0 sin geometría de riesgo, stop del lado malo, targets cruzados,
`initialRiskR` que no es `|entry − stop|`, `positionValue` que no es `qty × entry`, `status` distinto de
`TRIGGERED` con ejecución) se serializaba y viajaba.

Nuevo `validate_trade_plan(plan) -> tuple[str, ...]` (puro; vacío = válido) con códigos
`PLAN_VIOLATION_*`; `decide_portfolio` valida antes de devolver la decisión aprobada (**`plan_invalid`**
con las violaciones publicadas en el journal: `PortfolioDecision.plan_violations` →
`planViolations`) y `trade_plan_to_decision_package` devuelve `None` si el plan es incoherente
(defensa en profundidad en el seam que consume el worker). Los planes no ejecutables
(`WATCH`/`ARMED`/`BLOCKED`/`EXPIRED`) no se validan contra geometría que no necesitan.

### Certificación y gate CI

- Suites herméticas nuevas en el job `quality` (`python-ci.yml`) y en el job `python` (**`test_auto_v2_lifecycle_stop.py` por nombre; el de analytics entra por directorio**, corregido tras la auditoría)
  del Release-tag CI: `test_trade_plan.py` (validación del plan) y `test_execution_event.py`
  (`list_unapplied`).
- Test nuevo con **PostgreSQL real** en el job `auto-v2-durable-pg`: un fill `CAPTURED` que dejó un
  proceso muerto aparece como **capital reservado** al reiniciar y **veta** la entrada nueva
  (`open_orders_unmeasurable`), en vez de gastar dos veces la caja.
- **Matriz de mutaciones medida** (cada mutación aplicada, suite corrida y revertida): quitar
  `top_n_excluded` ⇒ 3 suites rojas; volver `buying_power` a cash bruto ⇒ 1; desactivar los escalones
  de measurement ⇒ 12; saltarse `validate_trade_plan` ⇒ 1.
- **Límite declarado (pre-existente, NO introducido aquí)**: `test_auto_scheduler_real_pg_zero_human_intervention.py`
  es no determinista. Medido A/B a 30 ejecuciones por lado (revirtiendo en memoria los 9 ficheros de
  código del slice y restaurando byte a byte): **4/30 en el commit base** y **8/30 con el slice**.
  Mecanismo: el entry solo materializa parte de sus chunks y el exit se dimensiona por la **orden** (no
  por la posición materializada), así que los chunks cola quedan en `RETRY` (`apply_ineffective`)
  **conservando fila en `sim_fill_finance_context`**, y la aserción de equity del test las cuenta como
  realizado. Por eso esa puerta puede ponerse roja con el código base **y** con este tip: el criterio es
  re-ejecutar el job. Causa raíz asignada a `AUTO-1`; detalle en §5.6 del audit-pack.
- Plan de implementación y roadmap por fases (`V2.40.4` → Adaptive AUTO) en
  [`docs/engineering/plan-v2-40-4-auto-safety-accounting-2026-09-16.md`](./docs/engineering/plan-v2-40-4-auto-safety-accounting-2026-09-16.md)
  y [`docs/engineering/roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md`](./docs/engineering/roadmap-auto-v2-40-4-a-v2-48-2026-09-16.md),
  con los P1 diferidos mapeados a su fase.
- **Sellado de CI (GitHub, posterior al commit):** tag anotado **`v2.40.4-beta` → `1127d010`**
  (`main` == `1127d010`; el commit docs-only de este sellado es posterior y **no** entra en el tag).
  `Release-tag CI` **GREEN** run [`35155027506`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35155027506)
  (9 jobs requeridos + `certify`) y `Python CI` **GREEN** run
  [`35154788932`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35154788932) (5/5, `quality`
  1734 passed). **Un rojo real, arreglado y declarado:** el primer `Python CI` (run
  [`35150808768`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35150808768)) dejó `quality` en rojo
  con `test_list_unapplied_filters_by_status`, que afirmaba el orden de inserción en vez de
  `captured_at DESC` (en local empataban los sellos de tiempo del reloj y pasaba); se corrigió en
  `1127d010` y el tag apunta al commit verde. Detalle en §7.1 del audit-pack.

## [1.65.3-beta] — V2.40.3 · Hotfix de la clave de idempotencia financiera (colisión por recorte) + invariante del A9 sobre el ledger real — 2026-09-16

**Sin migración** (head sigue en `041_unique_natural_keys`). Tres cambios independientes, y el
primero es un **bug de dinero**, no de cosmética:

| #      | Qué                                                                                                                                                                                                                                           |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **F1** | `simulated_idempotency_key` (SIM) y `recovery_idempotency_key` (recovery LIVE) dejaban de ser inyectivas por el **recorte con pérdida** del `execution_id` ⇒ los N fills de una misma orden colapsaban en **una** clave y el libro no cerraba |
| **F2** | El invariante de equity del test de certificación del día AUTO leía la posición de **`position_states`** (tabla que el camino AUTO SIM **no** escribe) ⇒ el término no realizado era siempre 0                                                |
| **F3** | Gate nuevo: al cerrar el día AUTO, **libro plano** y **ningún fill sin materializar** (`execution_events` todos `APPLIED` y todo `sim_fill_finance_context` con su transacción en el ledger)                                                  |

### La incidencia: el tag `v2.40.2-beta` dejó `lifecycle-pg` en rojo

El Release-tag CI del tag anterior falló en el job `lifecycle-pg`, en el test de certificación del
día AUTO completo (`test_a9_scheduler_process_full_day_pg_zero_human`), con el invariante de equity:

```
AssertionError: equity ... != initial + realized + unrealized ...
```

El mensaje apuntaba al sitio equivocado: el desajuste **no** era de la aritmética del ledger (que
está certificada) sino de **tres fills que nunca llegaron a materializarse**. Ningún test lo decía,
porque no existía un gate que mirara el estado de los `execution_events` al cerrar el día.

### Causa raíz (F1): el recorte se comía justo el `#fill_seq`

La identidad financiera de un fill es `execution_id = f"{venue_order_id}#{fill_seq}"`, y desde
P1-03 el `venue_order_id` del AUTO va **namespaced** (engine + UUID de cuenta + instrumento + lado +
secuencia lógica): medido, el `execution_id` de una orden AUTO realista mide **126-128 caracteres**.
Las dos derivaciones históricas recortaban el slug **por la cola**:

```python
return f"sim-fin-{slug[:120]}"[-128:]          # SIM
return f"recovery-fin-{slug[:100]}"[-128:]     # recovery LIVE
```

y la cola es exactamente donde vive el `#fill_seq`. Medido con la identidad del worker: **4 fills →
1 clave distinta** (en ambos lados y en ambos caminos), cuando el contrato pide 4. Consecuencia
medida en el camino real:

1. La primera trancha se asienta con la clave `sim-fin-…`.
2. La segunda llega a `ExecuteTrade` con la **misma** clave y **otro** payload ⇒
   `IdempotencyKeyReused` (409 en la capa HTTP, excepción en la de aplicación).
3. `apply_execution_financial_once` la captura y la degrada a
   `mark_retry(error="apply_exception")` ⇒ `retry_scheduled`.
4. El worker AUTO absorbe el fallo por símbolo (`auto_sim settle failed` ⇒ "sin fill este tick") y
   esa fila se queda en `RETRY` **para siempre**: la clave es función del mismo `execution_id`, así
   que el reintento vuelve a chocar. El lado vendedor no liquida y el día termina con el libro
   abierto y dinero sin mover.

Es un fallo **permanente y silencioso** (no un 500 transitorio): el sistema parece operar, cierra el
día "sin incidencias" y deja tranchas sin materializar. Detectarlo requería mirar el estado de los
eventos, que es justo lo que añade F3.

### Fix (F1): recorte SIN pérdida en un módulo propio

Nuevo `packages/py/application/src/bolsa_application/idempotency_key.py` con
`bounded_idempotency_key(prefix, execution_id, *, legacy_budget)`:

- `len(slug) <= legacy_budget` ⇒ `f"{prefix}{slug}"`: **byte a byte** la clave histórica (el
  `[-128:]` histórico era inoperante porque el total nunca superaba 128) ⇒ **compatibilidad exacta**:
  un fill en vuelo de un deploy anterior re-deriva LA MISMA clave y no se re-aplica dinero.
- `len(slug) > legacy_budget` ⇒ `f"{prefix}{slug[:head]}~{sha256(execution_id)[:32]}"`, 128 chars
  exactos. El marcador `~` **no puede** aparecer en un slug (`re.sub` manda todo lo que no sea
  `[A-Za-z0-9_]` a `-`), así que ninguna clave "larga" puede coincidir con una "corta"; y el digest
  del `execution_id` **completo** discrimina exactamente lo que el recorte tiraba (el `#fill_seq`).
- Slug degenerado (p.ej. `unknown`) ⇒ se rellena hasta el mínimo de 16 con la **misma** marca.

`simulated_idempotency_key` y `recovery_idempotency_key` pasan a delegar (presupuestos 120 y 100
respectivamente). El contrato R-11 C2 (`16 <= len(key) <= 128`, sin whitespace, estable por
`execution_id`) se mantiene para **todo** el rango.

### Fix (F2): el invariante lee el estado canónico real

El invariante anterior reconstruía la contabilidad desde el ledger, pero tomaba la **posición
abierta** de `SqlAlchemyPositionStateRepository` (`position_states`). El camino AUTO SIM **no escribe
esa tabla** (escribe `sim_auto_positions` y la canónica `positions`), así que `remaining = 0` y el
término no realizado era **siempre 0**: el invariante se degradaba a una identidad de caja y era
**ciego** a una posición a medio liquidar. La versión nueva (`_assert_full_day_closed`) reconstruye
la identidad desde el **estado canónico** (`positions`) y el P&L cerrado desde
`sim_fill_finance_context` (fuente independiente) contra el ledger real.

### Fix (F3): gate nuevo de cierre del día

El mismo test, antes de certificar, exige las tres cosas juntas:

1. Todos los `execution_events` de la cuenta en `APPLIED` (**cero** `RETRY`/`CAPTURED`/`APPLYING`).
2. Todo `sim_fill_finance_context` con su transacción correspondiente en el ledger (**ningún fill sin
   materializar**).
3. Posición final **plana** (libro cerrado) y el invariante de equity del dominio sobre el ledger.

Es el gate que habría nombrado el fallo del tag en una línea: _"el día AUTO deja 3 ExecutionEvents
sin materializar (RETRY/CAPTURED)"_.

### Determinismo del test (y un verde falso retirado)

Con F1 arreglado apareció el siguiente rojo, esta vez en
`test_a9_scheduler_process_restart_with_open_protected_position_pg`:

- **Instrumento aleatorio ⇒ lotería determinista.** El simulador rechaza la orden entera
  (`fills=()`) según un ruido determinista por `(seed, instrument_id, lado)`: medido con la sonda,
  **12,36 %** de los identificadores aleatorios no llenan nunca, así que el test fallaba por sorteo
  (`el proceso debe abrir (BUY durable) antes del restart`). Ahora el instrumento se elige de forma
  **determinista** entre los que sí llenan (`_filling_instrument_id`), y el test del día completo usa
  una identidad fija.
- **Se contaban tranchas en vez de órdenes.** El invariante del restart es "no **re-comprar**", pero
  el test contaba filas de `execution_events` (tranchas de fill) filtradas por lado: materializar
  tras el restart la trancha que quedó en vuelo al matar el proceso es lo **correcto** y se contaba
  como re-compra. Ahora cuenta `count(distinct venue_order_id)` ⇒ una re-compra real es una
  `venue_order_id` **nueva**. El contador anterior solo pasaba porque el bug de F1 lo congelaba en 1.

### Tests

- **Nuevo** `packages/py/application/tests/test_idempotency_key_budget.py` (hermético, sin PG ni
  broker, entra en la batería offline del job `quality`): regresión del colapso (4 fills ⇒ 4 claves,
  ambos lados, con la identidad del worker), comprobación de que el recorte histórico **sí** colapsaba
  (para que el test no pueda "arreglarse" solo), compatibilidad **exacta** con las claves cortas,
  disjunción estructural de las largas (`~`), contrato 16..128 sin whitespace, inyectividad entre
  lados/órdenes/secuencias y caso degenerado.
- `test_a9_scheduler_process_pg_zero_human.py`: invariante sobre el estado canónico, gate de libro
  plano / sin fills pendientes, instrumento determinista que llena y conteo de órdenes en el restart.

### Verificación (local)

- **A/B del bug, sin tocar el código del repo**: restaurando la derivación histórica en runtime (un
  `sitecustomize` por `PYTHONPATH` que también ve el subproceso del scheduler), el día AUTO falla con
  `AssertionError: el día AUTO deja 3 ExecutionEvents sin materializar (RETRY/CAPTURED)` — los 4 fills
  de la orden colapsan en 1 clave, 1 se asienta y 3 quedan en `RETRY` permanente. Con el fix, el
  fichero A9 queda verde (día completo + restart, 2 passed).
- Batería **exacta** del job `lifecycle-pg` sobre PostgreSQL real en una BD scratch recreada y
  **pre-migrada a `head`** (mismos gates fail-if-skipped que CI): **132 passed in 106,55 s**
  (0 failed, 0 errors, 0 skipped). En el tag rojo, el mismo job registró `1 failed, 131 passed`.
- Baterías offline **exactas** de CI (comandos extraídos del propio YAML, para que no se
  desincronicen): job `quality` → **1626 passed**; job `python` del tag (la lista grande sin
  `apps/api-python/tests` completo) → **1634 passed**.
  `ruff check packages/py apps/api-python --config pyproject.toml` → **0** · `lint-imports` →
  **4/4 contratos KEPT**.
- El test hermético nuevo se **cablea** en los dos jobs offline (`quality` y `python` del tag): pasó
  a estar fuera de la red de CI cuando se escribió, y esa es justo la clase de test que debe correr
  en cada push, no solo en el job con PostgreSQL.
- **`mypy` no se pudo ejecutar en la máquina de verificación** (política de control de aplicaciones
  de Windows bloquea el DLL `mypyc` del binario: `ImportError: DLL load failed while importing
…__mypyc`). **No se afirma localmente**: lo cubre el step _Mypy_ del job `quality` y el job `python`
  del tag, ambos verdes en CI (abajo). El cambio de F1 es un módulo nuevo pequeño con firmas
  anotadas y sin dependencias nuevas.

### Sellado de CI (GitHub, posterior al commit)

| Gate                          | Run                                                                                                         | Resultado                                                                                                                                                                                                    |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Python CI del push a `main`   | [`35068139514`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35068139514) (`581067c4`)                 | **success**: `quality`, `lifecycle-pg`, `grammar-discovery-pg`, `paper-forward-pg`, `auto-v2-durable-pg`                                                                                                     |
| Release-tag CI del tag movido | [`35068488972`](https://github.com/jvelasca/Bolsa_V1/actions/runs/35068488972) (`581067c4`, `v2.40.2-beta`) | **success**: `certify` ✓ con `python` (ruff/imports/**mypy**/pytest offline), `lifecycle-pg` (auth + golden restart), `dr-verify`, `a7-gate`, `playwright` (mock), `frontend`, `shared`, `spine`, `security` |

El tag `v2.40.2-beta` se **movió** (borrado + re-tag) desde `11e2cb83`, cuyo CI quedó rojo por el bug
que esta fase corrige, al commit del fix `581067c4`. **Nota declarada:** el tag apunta a un commit
cuya versión es `1.65.3-beta`, así que el nombre del tag no coincide con la versión del código que
señala; es el precio de que "el tag" siga significando "commit certificado".

## [1.65.2-beta] — V2.40.2 · Claves naturales únicas (reconciliación Prisma→Alembic + upsert atómico) — 2026-09-15

Migración nueva **`041_unique_natural_keys`** (head `040` → **`041`**): las **8 claves naturales
que Prisma declaraba y el baseline Alembic nunca creó** pasan a existir como índice único, y los
**tres `upsert` que escriben sobre ellas** resuelven el conflicto dentro de PostgreSQL. El ledger,
el settlement, el `RiskGate`, la reconciliación y el AUTO **no cambian** (cambio aditivo de DDL +
tres escrituras que pasan de `SELECT`+`INSERT` a `INSERT … ON CONFLICT`).

### El incidente que lo motiva (visible en la consola del dev server)

`GET /api/instrument-daily-opinions` quedó en **`MultipleResultsFound` permanente**:

```
instrument_strategy_top_repository.py:60  row = (await self._session.execute(stmt)).scalar_one_or_none()
sqlalchemy.exc.MultipleResultsFound: Multiple rows were found when one or none was required
```

La causa raíz es **doble**, y ninguna de las dos mitades basta sola:

1. **Sin backstop en la BD.** La migración Prisma `20260727160000_instrument_strategy_tops`
   declaró `UNIQUE (instrument_id, timeframe)`, pero el baseline Alembic (003) solo copia columnas
   y constraints de FK/`UniqueConstraint` de `tables.py`: al **no estar declarada en el modelo**,
   el índice nunca se creó. Verificado contra la BD viva: solo existían `_pkey` y la FK.
2. **Escritura no atómica.** `instrument_strategy_top_repository.upsert` era un
   _check-then-insert_ (`get()` → `INSERT`): dos escritores concurrentes ven `None` e insertan
   ambos. Resultado medido: **12 grupos duplicados / 24 filas**, con pares a 7-8 ms de distancia
   (`created_at` 19:32:20.065952 vs 19:32:20.071963), del barrido del **2026-09-14**.

Lo que lo hacía **irrecuperable** (no un 500 transitorio): `get()` usa `scalar_one_or_none()` y el
propio `upsert` empieza llamando a `get()`, así que el instrumento duplicado quedaba envenenado
para siempre.

### Inventario medido antes de tocar nada (BD de desarrollo, 2026-09-15)

De las 10 claves naturales de `schema.prisma`, **8 faltaban** en la BD. Duplicados reales:

| tabla                                                              |  filas | grupos dup | filas implicadas |
| ------------------------------------------------------------------ | -----: | ---------: | ---------------: |
| **`instrument_strategy_tops(instrument_id, timeframe)`**           |     46 |     **12** |           **24** |
| `instruments(symbol, exchange)`                                    |    243 |          0 |                0 |
| `ohlcv_bars(instrument_id, timeframe, timestamp)`                  | 95 224 |          0 |                0 |
| `instrument_daily_opinions(instrument_id, as_of_bar_date, source)` |    160 |          0 |                0 |
| `instrument_list_items(list_id, instrument_id)`                    |    112 |          0 |                0 |
| `positions(portfolio_id, instrument_id)`                           |      0 |          0 |                0 |
| `transactions(portfolio_id, idempotency_key)`                      |      0 |          0 |                0 |
| `data_snapshots(instrument_id, timeframe, data_version)`           |      0 |          0 |                0 |
| `position_policies(account_id, instrument_id)`                     |      0 |          0 |                0 |
| `instrument_narratives(instrument_id, scope)`                      |      0 |          0 |                0 |

Solo `instrument_strategy_tops` tenía duplicados ⇒ las otras 7 claves se pudieron crear **sin
borrar un solo dato**.

### Dedupe conservador (fail-closed: nunca borrar datos financieros en automático)

- **`instrument_strategy_tops`**: se deduplica conservando la fila más reciente
  (`updated_at`, `created_at`, `id`). Es una caché derivada del embudo coach: la más nueva es la
  vigente por construcción. **46 → 34 filas** en la BD de desarrollo.
- **Las otras 7: no se borra nada.** Si alguna tuviera duplicados al aplicar, la migración
  **aborta nombrando tabla, columnas y filas de muestra**. Borrar un `instruments`/`positions`
  duplicado cascadea a datos financieros, y `position_policies`/`instrument_narratives` son
  contenido de usuario: esa decisión no es de una migración. Mejor un bloqueo visible que una
  pérdida silenciosa.

### Escrituras atómicas (las tres que podían duplicar)

| repositorio                                  | clave                                     | antes                   | ahora                            |
| -------------------------------------------- | ----------------------------------------- | ----------------------- | -------------------------------- |
| `instrument_strategy_top_repository.upsert`  | `(instrument_id, timeframe)`              | `get()` → INSERT/UPDATE | `INSERT … ON CONFLICT DO UPDATE` |
| `instrument_narrative_repository.upsert`     | `(instrument_id, scope)`                  | `get()` → INSERT/UPDATE | `INSERT … ON CONFLICT DO UPDATE` |
| `instrument_daily_opinion_repository.upsert` | `(instrument_id, as_of_bar_date, source)` | `get()` → INSERT/UPDATE | `INSERT … ON CONFLICT DO UPDATE` |

Semántica de datos **preservada**: `version` sigue incrementándose en conflicto, el `symbol` de
tops se conserva si el llamante no aporta uno (`coalesce`), y el `idempotency_key` del dictamen no
se reescribe. `instrument_daily_opinion_repository.upsert` mantiene además su `idempotency_key`
único como segunda red.

Las otras 5 tablas **no cambian de writer**: tienen guarda propia y el índice les queda de
backstop (`positions` → lock de cartera + savepoint R-8A; `position_policies` → `ValueError` del
caso de uso; `instruments` → `yahoo_symbol` único + import de usuario; `instrument_list_items` →
dedupe en memoria + delete/insert en una transacción; `data_snapshots` → upsert por `id`).

### Detalle que atrapó PostgreSQL (no el test)

El nombre de índice que declaró Prisma para el dictamen diario
(`instrument_daily_opinions_instrument_id_as_of_bar_date_source_key`) tiene **65 caracteres** y
PostgreSQL **lo habría truncado en silencio** (límite 63): el `CREATE INDEX` falló con
`IdentifierError` en el primer intento de `alembic upgrade head`. Se usa
`instrument_daily_opinions_instrument_id_asof_source_key` (55), explícito y sin truncamiento. Es
la única clave que no converge al nombre de Prisma.

### Cambio de comportamiento observable (a tener en cuenta)

- **Un `INSERT` crudo duplicado sobre cualquiera de las 8 claves ahora falla** con
  `IntegrityError` en vez de crear una fila corrupta. Es el objetivo (fail-closed), y es
  precisamente por eso que las tres escrituras atómicas **tenían que entrar en el mismo cambio**:
  el índice solo, sin arreglar el `upsert`, habría convertido el duplicado silencioso en un 500.
- **Bases con duplicados en las 7 tablas no deduplicadas bloquean el `upgrade`** con un error
  explícito. La BD de desarrollo está limpia (0 grupos en todas); la migración se aplicó sin
  incidencias.

### Tests (job `auto-v2-durable-pg`, gate fail-if-skipped `UNIQUE_NATURAL_KEYS_PG_REQUIRED=1`)

`apps/api-python/tests/test_unique_natural_keys_pg.py` (**7 tests nuevos**):

- guardia **anti-deriva**: las 8 claves existen como índice único en `pg_indexes` (sin ella, la
  reconciliación se vuelve a perder en la siguiente tabla que alguien añada "solo en Prisma");
- **regresión del incidente**: dos `upsert` concurrentes del mismo `(instrument_id, timeframe)`
  ⇒ UNA fila, sin excepción;
- **backstop real**: un `INSERT` crudo duplicado lanza `IntegrityError` (certifica la propiedad
  fail-closed sin pasar por el repositorio);
- semántica de `version`/`symbol` conservada en el upsert de tops;
- concurrencia de narrativas y de dictamen diario ⇒ una fila por clave;
- **roundtrip de la 041 con duplicados preexistentes**: `downgrade` a `040`, se insertan a mano dos
  filas de la misma clave con distinto `updated_at`, `upgrade` a `head` ⇒ queda **la más reciente**
  y el índice vuelve a existir (reproducción exacta de las 24 filas del incidente). El test es
  consciente del **linaje** del nombre —_constraint_ del baseline `003` en una BD nueva, _índice
  plano_ de la 041 en una BD antigua—: comprueba el contrato del `downgrade` en cada caso y retira
  el backstop explícitamente para poder sembrar los duplicados (que es el escenario real: la BD en
  la que la 041 aún no había corrido).

Se actualizó `_ALEMBIC_HEAD` en `test_discovery_evidence_snapshot_pg.py` (`040` → `041`): los tests
de roundtrip existentes ya lo usan como única fuente.

### CI: los comandos plegados ejecutaban menos de lo que declaraban (sellado 2026-09-15)

Tres cosas que la certificación daba por verdes sin serlo, encontradas al revisar por qué el job
`grammar-discovery-pg` se puso rojo tras el push:

1. **`run: >` con comentarios intercalados (comentario de shell = truncación).** En un bloque
   plegado YAML cada línea es _texto del comando_, no un comentario de YAML. Un `#` intercalado en
   medio de la lista de pytest convertía **todo lo que venía después en comentario de shell**:
   - `quality` (`python-ci.yml`) ejecutaba **936 tests** y nunca llegaba a `apps/api-python/tests`;
     los ficheros nuevos de `packages/py/application/tests` (`test_auto_v2_entry.py`,
     `test_auto_investment_system.py`, `test_portfolio_decision_engine.py`,
     `test_position_manager.py`, `test_discovery_evidence.py`, …) estaban **listados pero no
     corrían** en CI. Verde falso.
   - `python` / `Pytest offline` y `lifecycle-pg` de `release-tag-ci.yml` (la certificación de
     release) tenían el mismo corte: el job de release ejecutaba 11 y 10 ficheros respectivamente de
     los ~40 declarados.
2. **`... | tee log` sin `pipefail`.** El step devolvía el exit code de `tee` (**0**): el run
   `35009780076` publicó `6 failed, 22 passed` en el job `auto-v2-durable-pg` **con el job en verde**.
   Ahora los dos steps con `tee` hacen `set -o pipefail` y el guard anti-skip exige que el log exista
   y no esté vacío (antes un log ausente hacía fallar el `grep` en mudo y el guard no guardaba nada).
3. **`downgrade` de la 041 contra índices que respaldan una constraint.** En una BD recién migrada
   el baseline `003` crea los 8 nombres como _constraint_ (copia los `UniqueConstraint` de
   `tables.py`) y `upgrade` los detecta como existentes y los omite; en una BD antigua son _índices
   planos_ creados por la 041. El `downgrade` hacía `DROP INDEX` siempre y PostgreSQL aborta con
   `DependentObjectsStillExist` cuando el índice implementa una constraint: tumbaba los roundtrips
   036→041 en CI. Ahora `downgrade` consulta `pg_constraint.conindid` y solo retira los planos.

Los comentarios de procedencia de las listas de pytest se movieron **encima** del step (donde sí son
YAML) en los tres sitios: `quality` de `python-ci.yml`, y `python`/`lifecycle-pg` de
`release-tag-ci.yml`. Verificado con un parser YAML de verdad (jobs, tokens del comando resultante,
cero tokens `#`) y comprobando que la lista de tests actual es subsecuencia exacta de la anterior
—no se perdió ni se duplicó ningún fichero.

De regalo, el job offline de release gana los `--ignore` de `test_instrument_trade_context_pg.py` y
`test_unique_natural_keys_pg.py` que ya tenía el job equivalente de `python-ci.yml` (los certifica el
job con PG; sin `--ignore` se recolectarían sin BD y skipearían en silencio).

**Lo que destapó el arreglo (y no estaba verde):** con el `pipefail` real, el job
`auto-v2-durable-pg` dejó de mentir y apareció `1 failed, 27 passed` — el roundtrip de la 041
(`assert _index_present(connection) is False` tras bajar a 040). La causa es de linaje, no de
lógica del dedupe: en CI la BD se migra desde cero, así que el baseline `003` (construido desde
`tables.py`) crea las 8 claves como **constraint** y el `downgrade` de la 041 —correctamente— no
las toca (no son suyas; `DROP INDEX` sobre ellas aborta), mientras que en la BD de desarrollo son
**índices planos** de la 041 y sí desaparecen. El test asumía un solo linaje. Ahora comprueba el
contrato en los dos (constraint ⇒ sobrevive; índice plano ⇒ desaparece) y retira el backstop
explícitamente para poder sembrar los duplicados.

Reproducido en local **por el camino de la app** (`ensure_migrated`, no el CLI: el CLI de alembic
construye el engine desde `alembic.ini` e ignora `DATABASE_URL` — en CI coinciden por casualidad),
con una BD vacía migrada a head: las 8 claves quedan como constraint, y el job
(`test_auto_v2_durable_pg` + `test_instrument_trade_context_pg` + `test_unique_natural_keys_pg` +
`test_discovery_evidence_snapshot_pg`) pasa **28 passed** en el linaje de CI y **7 passed** el
roundtrip en el linaje antiguo. También se comprobó que ninguna FK referencia las 8 claves (23 FKs
hacia esas tablas, 0 hacia la clave natural).

### Verificación

- `ruff check packages/py apps/api-python --config pyproject.toml` → **0**
- `ruff format` sobre los ficheros tocados → aplicado
- `mypy domain/market/infrastructure/application/apps-api-python` → **0 errores** (482 ficheros)
- `lint-imports` → **4/4 contratos**
- Batería offline `quality` → **2793 passed**
- `packages/py/infrastructure/tests` → **138 passed, 1 xfailed**
- Job `auto-v2-durable-pg` (4 ficheros, PG real) → **28 passed, 0 skipped**
- Migración aplicada en la BD de desarrollo: head `041`, las 8 claves presentes y
  `instrument_strategy_tops` **46 → 34 filas / 0 grupos duplicados**
- Run Python CI `35018635017` (tras el sellado): `quality` **en verde con la batería completa**
  (2m29s), `lifecycle-pg`, `paper-forward-pg` y `grammar-discovery-pg` en verde; `auto-v2-durable-pg`
  destapó el fallo de linaje del roundtrip (arriba), que el job ocultaba con el `tee` sin `pipefail`
- Run Python CI `35019474204` (tras el fix del linaje): **5/5 jobs en verde** (`quality`, `lifecycle-pg`,
  `paper-forward-pg`, `grammar-discovery-pg`, `auto-v2-durable-pg`). `quality` ejecuta ahora
  **1579 passed, 37 skipped** donde el step truncado corría 936 tests y nunca llegaba a
  `apps/api-python/tests`
- Lista de `release-tag-ci.yml` (la que el `#` truncaba) ejecutada en local con el comando exacto del
  workflow: job `python` / `Pytest offline` → **1624 passed**; job `lifecycle-pg` → **131 passed,
  1 failed**, y el fallo es el flaky **conocido y preexistente**
  `test_a9_scheduler_process_restart_with_open_protected_position_pg` ("el proceso debe abrir (BUY
  durable) antes del restart", con `reconciliation=UNKNOWN`/aperturas vetadas): hasta ahora **no se
  ejecutaba en ningún job de release** porque el `#` cortaba la lista ~30 ficheros antes. Queda
  declarado como deuda (no se toca en este sellado): al etiquetar `v2.40.2-beta` ese test entra por
  primera vez en la certificación de release

## [1.65.1-beta] — V2.40.1 · AUTO Safety Hardening (fail-closed real + fuentes reales) — 2026-09-15

Endurecimiento de **AUTO 2.0** sobre `v2.40-beta`: los siete P0 de la auditoría de esa versión
quedan **cerrados** en el pipeline de decisión, y las fuentes que lo alimentan (sector, liquidez,
edge, régimen) dejan de ser inyecciones de test y pasan a estar **cableadas en producción**. La
regla que gobierna todo el incremento es una sola: **la ausencia de dato no puede aprobar nada**.

Sin migración nueva (Alembic head se queda en **`040_auto_v2_durable_state`**). El ledger, el
settlement, el `RiskGate` y la reconciliación **no cambian**: toda intención sigue pasando por el
mismo _Single Decision Spine_. El flag sigue siendo `AUTO_ENGINE_SIM_V2` (**OFF por defecto**; con
OFF el comportamiento es el de `v2.39.3-beta`).

### Matriz de gates fail-closed (solo el estado explícito permite entrar)

Nuevo módulo puro `bolsa_analytics.cognitive.trade_context` con tri-estados deterministas
(`SectorResolutionStatus`, `LiquidityStatus`, `CorrelationStatus`) y `TradeContext`, que resuelve
sector declarado vs. catálogo, ADV notional y frescura de fundamentales:

| Estado                 | Cuándo                                                      | Efecto en el motor                                                             |
| ---------------------- | ----------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `KNOWN` / `CALCULATED` | Dato presente, coherente y fresco (≤ `sector_max_age_days`) | Único estado que permite **ENTRY**                                             |
| `UNKNOWN`              | No hay dato                                                 | Veto `sector_unknown` / `liquidity_unknown`                                    |
| `CONFLICTING`          | El `memo sector=` y `instruments.sector` difieren           | Veto `sector_conflicting`                                                      |
| `STALE`                | `fetchedAt` de fundamentales supera la edad máxima          | Veto `sector_stale`                                                            |
| `UNAVAILABLE`          | Correlación no calculable con el gate activo                | Veto `correlation_unknown`                                                     |
| Posición abierta opaca | Cualquier posición abierta con sector no-`KNOWN`            | Veto `sector_exposure_unverifiable` (no se sube exposición sobre estado opaco) |

- **P0-1 · Correlación fail-open.** `_correlation_conflict()` devolvía `False` con
  `correlation is None` ⇒ "el dato no existe" se aprobaba como "sin conflicto". Ahora, con el gate
  de correlación activo, solo `CALCULATED` pasa; el resto veta con `correlation_unknown`.
- **P0-2 · Concentración sectorial sobre cajas opacas.** `build_worker_snapshot()` **no
  transmitía el `sector`** de las posiciones abiertas, así que todas caían al sentinel `<unknown>`
  de `portfolio_fit.py` y el sector del candidato se medía **solo contra sí mismo**. Ahora el
  snapshot lleva los sectores **conocidos** y una posición de sector no fiable se publica
  **deliberadamente opaca**: el motor lo detecta y veta `sector_exposure_unverifiable` en vez de
  asumir que la cartera está limpia.
- **P0-3 · Sobre-gasto de riesgo intra-tick.** `_committed_position()` no propagaba
  `risk_amount`, así que `risk_used` no subía dentro del tick y todas las candidatas del mismo tick
  se evaluaban contra la **misma** foto inicial. Ahora cada aprobación reconstruye una **foto de
  trabajo** (`_working_snapshot`) que acumula riesgo y exposición comprometidos: A → reserva → B →
  reserva → C. Invariante: 6 candidatas de riesgo 1 % con presupuesto 6 % ⇒ exactamente 6
  aprobadas, `risk_remaining == 0` y la 7ª veta por `risk_budget_exceeded`.
- **P0-4 · Edge y liquidez inventados.** `V2Tunables.default_edge = 0.9` convertía "la estrategia
  no declara edge" en "oportunidad excelente", y `_score_from_signal()` puntuaba
  `liquidity = 1.0` cuando el notional era `None`. **Breaking (en beta):** se elimina el env
  `AUTO_ENGINE_SIM_V2_DEFAULT_EDGE` y el campo `default_edge`; el edge ausente vale **0** (por
  debajo de `min_edge` ⇒ NO ENTRY) y la liquidez ausente veta. El edge **real** pasa a ser un dato
  persistido y auditable: `EdgeReportRow.edge_score` de la versión de estrategia vía
  `latest_edge_report()` (prioridad `memo edge=` > EdgeReport > nada).
- **P0-5 · Identidad de señal opcional y dedupe dependiente del orden.** `_signal_rejection()` no
  descartaba sin `signal_id` y el dedupe usaba `deduped.setdefault(...)`, de modo que el conjunto
  aprobado dependía del **orden de entrada**. Ahora `signal_id` vacío ⇒
  `SIGNAL_IDENTITY_MISSING` ⇒ NO ENTRY, y la selección usa una clave canónica
  (`canonical_candidate_key`: edge desc → versión → barra → `signal_id` → instrumento) con
  `min(...)` por instrumento: el mismo conjunto de señales produce el mismo veredicto en cualquier
  orden.
- **P0-6 · `EXIT_ONLY` no era absoluto.** `manage_position()` solo forzaba la venta total por
  régimen si `order_action == "hold"`, así que `REDUCE`/`TAKE_PROFIT`/trailing ganaban al
  exit-only. Ahora `EXIT_ONLY` tiene **precedencia absoluta**: liquida el remanente e ignora el
  resto de vías de decisión.
- **P0-7 · AUTO V2 ciego en producción.** `AutoSimRuntime` construía el worker **sin**
  `regime_source` ni `sector_source` (solo los tests los inyectaban) y no existía
  `liquidity_source` ⇒ en producción el régimen era `UNKNOWN` ⇒ exit-only ⇒ **nunca abría nada**.
  Ahora el runtime compone los lectores sobre la sesión viva del tick: régimen con
  `DiscoveryRegimeSource` + `bars_provider` sobre `SqlAlchemyOhlcvRepository`, contexto de cartera
  con `CatalogTradeContextSource` (nueva lectura en una query
  `list_trade_context_by_ids` → `sector`, `advUsd` y `fetchedAt` del catálogo) y edge con
  `EdgeReportSource` sobre `SqlAlchemyCognitiveRepository`. El override
  `AUTO_ENGINE_SIM_V2_REGIME` sigue teniendo prioridad.

**Consecuencia operativa (documentada, no un bug):** AUTO solo entrará si hay **sector + ADV
frescos** (≤ `sector_max_age_days`, 30 días por defecto) y un `EdgeReport` vigente de la versión
ACTIVE. Si los fundamentales están caducados, AUTO queda en **NO ENTRY** (no en "asumir válido").

- **Verificación.** `ruff check` **limpio** (el comando que gatea CI: `E/F/I/UP/B` sobre
  `packages/py` + `apps/api-python`) · `mypy` **0 errores** en 482
  ficheros · _import-linter_ **4/4 contratos KEPT** · batería exacta del job `quality`
  **1616 passed** · `packages/py` (application + analytics + domain) **2347 passed** · job
  `auto-v2-durable-pg` (PG real, `fail-if-skipped`) **21 passed**, incluido el test nuevo
  `test_instrument_trade_context_pg.py` (contrato del contexto de cartera: clave por `id` y por
  `symbol`, dato ausente ⇒ `None` explícito, nunca un default). Tests nuevos de los gates:
  `test_plan_v2_tick_unknown_sector_is_rejected`, `_unknown_liquidity_is_rejected`,
  `_sector_conflict_with_catalog_is_rejected`, `_stale_observation_is_rejected`,
  `_unknown_correlation_blocks_when_gate_on`,
  `_open_position_without_sector_blocks_new_entries`, `_dedupe_is_order_independent`,
  `edge_from_package_has_no_default`, `test_plan_v2_tick_without_identity_is_rejected` y la
  precedencia `EXIT_ONLY` sobre `REDUCE`/`TAKE_PROFIT`; en integración,
  `test_v2_without_trade_sources_is_fail_closed` (sin liquidez/edge/sector el worker real no abre
  nada: cascada `liquidity_unknown` → `edge_below_threshold` → `sector_unknown`).
- **CI:** el test nuevo de PG entra en el job `auto-v2-durable-pg` de `python-ci.yml` (con
  `INSTRUMENT_TRADE_CONTEXT_PG_REQUIRED=1` y el paso _fail-if-skipped_ ya existente) y en el job
  de certificación de `release-tag-ci.yml`; en el job `quality` (sin PostgreSQL) queda
  explícitamente ignorado, como el resto de las suites PG-gated.

## [1.65.0-beta] — V2.40 · AUTO 2.0 — Investment Operating System — 2026-09-15

AUTO deja de ser un _orquestador de investigación + promoción de estrategias_ conectado a un
simulador y pasa a ser un **sistema operativo de inversión**: decide **qué** comprar, **cuándo**,
**cuánto**, **cómo gestionar la posición** y **cuándo salir**. El settlement, el ledger y la
reconciliación **no cambian**: AUTO 2.0 solo decide qué intención emitir, y todo sigue pasando por
el mismo _Single Decision Spine_ (kill switch → Simulation Gate → RiskGate → settlement SIM).

Toda la capa nueva vive detrás de un **flag de entorno**, `AUTO_ENGINE_SIM_V2=1`, **OFF por
defecto**: sin el flag, AUTO se comporta exactamente como en `v2.39.3-beta`.

- **P0 — Espina cognitiva (paquete `bolsa_analytics.cognitive`).**
  `AutoPortfolioSnapshot` (foto canónica e inmutable del libro: posiciones, stops, exposición
  bruta/neta, efectivo, régimen, `as_of`), `OpportunityRanker` (score determinista de cada
  oportunidad: edge, R:R, liquidez y penalización por concentración), `RiskAllocator` (sizing por
  presupuesto de riesgo y SL/TP derivados de ATR) y `SignalIdentity` (identidad estable de señal +
  frescura). Todos **deterministas, puros y sin red** (contrato
  `analytics-market-independence` intacto).
- **P1 — Motor de decisión de cartera.** `PortfolioDecisionEngine`: decide **ENTRY/NO-ENTRY** a nivel
  de cartera, con vetos **fail-closed** y motivo registrado (sin régimen operable, `position_exists`,
  presupuesto de riesgo agotado, correlación, stop inválido, `min_edge`/`min_risk_reward`…). Publica
  un `TradePlan` (el contrato del camino caliente) con stop estructural, objetivos y dirección, y
  propaga el **sector** de la decisión.
- **P2 — Gestión de posición por estado.** `PositionState` + `ExitPlan` + `PositionDecision` vía
  `PositionManager`: stop estructural, T1/T2 (parciales), trailing, exit-only por régimen y cierre
  de sesión — la gestión deja de depender de una `ProtectionConfig` global y pasa a ser **por
  operación**.
- **P3 — Regime gate direccional.** `MarketRegimeGate` veta entradas por régimen y **dirección**
  (un `BULL_TREND` no autoriza cortos). `DiscoveryRegimeSource` conecta el régimen operativo real al
  clasificador determinista de barras (`discovery_market_regime_v0`), con `fail-closed` (régimen
  desconocido ⇒ `UNKNOWN` ⇒ **exit-only**, nunca entradas a ciegas).
- **P4 — Durabilidad del estado V2 (migración nueva, head `040_auto_v2_durable_state`).** Un crash ya
  no degrada la operativa:
  - `sim_auto_positions.position_state` (JSONB): el **plan operativo** de cada posición se persiste
    en cada cambio de cantidad y se **rehidrata exacto** al readoptar (`position_state_from_dict`) —
    mismo stop, mismos objetivos, mismas parciales — en vez de reconstruirlo por ATR. Sin plan
    durable (espejo legado) el fallback reconstruido se marca `adopted` (auditoría explícita).
  - `sim_consumed_signals`: las **señales consumidas por barra** son durables, de modo que tras un
    reinicio el motor no re-emite la MISMA oportunidad sobre la MISMA barra (anti-_churn_: stop-out
    y re-entrada inmediata en la misma vela). La tabla se poda a la barra corriente.
  - `SimDurableUnitOfWork` incorpora el store de señales: el espejo del fill y su dedupe o quedan
    juntos, o no queda ninguno.
- **Cableado en el worker.** `AutoSimulationWorker` incorpora el pipeline (`auto_v2_entry.py`):
  snapshot → ranker → decisión → `TradePlan` → adaptador `trade_plan_to_decision_package` → spine.
  El readopt durable, la marca de señal consumida (solo tras fill confirmado) y la poda de barras
  viejas viven aquí.
- **Verificación.** `ruff` / `ruff format` limpios · `mypy` sin incidencias · `packages/py/application/tests`
  **1546 passed** · `packages/py/analytics` + `infrastructure` **816 passed, 1 xfailed** · suites
  V2/worker/AUTO/PG/migraciones **82 passed** (incluye el roundtrip de la 040 y el reinicio real
  sobre PostgreSQL). Tests nuevos: `test_auto_v2_entry.py`, `test_auto_investment_system.py`,
  `test_portfolio_decision_engine.py`, `test_position_manager.py`,
  `test_active_strategy_runtime_state.py`, `test_sim_durable_v2_state.py`,
  `test_auto_portfolio_snapshot.py`, `test_opportunity_ranker.py`, `test_risk_allocator.py`,
  `test_signal_and_regime.py`, `test_auto_v2_worker_integration.py`, `test_auto_v2_durable_pg.py`.
  Los herméticos entran en la batería offline de CI y el de PG real en el job nuevo
  `auto-v2-durable-pg` con **gate fail-if-skipped**.
- **CI (verificado antes del tag):** `release-tag-ci` **GREEN** — run `34972246205` (10/10 jobs
  requeridos verdes + `certify` aggregate `success`; único skip: `playwright` integrado, opt-in) ·
  `python-ci` **GREEN** — run `34972246101` con el job nuevo `auto-v2-durable-pg` en `success`.

## [1.64.3-beta] — V2.39.3 · Cierre P1/N1 (lock de cuenta) + P2/N2 (secuenciador forzado) + fix `totalSamples` — 2026-09-15

Tercera pasada de la auditoría interna, esta vez sobre `v2.39.2-beta`. Cierra los dos hallazgos
del **secuenciador del ledger** (AUDITORIA 1), el bug de `totalSamples` en `discovery_evidence.py`
(AUDITORIA 2) y confirma un detalle del script de limpieza que **no** es fallo. Alembic head sigue
en **`039_research_trials_regime`** (sin migraciones nuevas).

- **P1/N1 — `next_executed_at` es por cuenta pero el lock que lo protegía era de cartera.**
  `next_executed_at(account_id)` lee `MAX(executed_at)` **por cuenta**, pero el lock era
  `with_for_update` sobre `PortfolioRow` (por `legacy_portfolio_id`). Dos carteras de la **misma
  cuenta** no comparten `legacy_portfolio_id`, así que sus escritores **no se excluyen entre sí** y
  pueden leer el mismo `MAX(executed_at)` antes del commit del otro, emitiendo asientos con
  **idéntico instante** (el desempate por `id`, UUID v4 aleatorio, no rescata el orden real).
  **Fix**: nuevo `SqlAlchemyAccountRepository.lock_account(account_id)` (`SELECT ... FOR UPDATE`
  sobre `investment_accounts`), cableado como lock externo antes del lock de cartera en `trade.py`,
  `cash.py` (deposit + withdraw) y `custody.py` (orden determinista **cuenta → cartera**). El
  docstring de `next_executed_at` pasa a exigir el lock de **cuenta**.
- **P2/N2 — `append_*` aceptaba `executed_at` externo.** `append_trade`, `append_fee`,
  `append_custody_fee` y `append_cash_movement` aceptaban `executed_at: datetime | None = None` con
  fallback `executed_at or now`, permitiendo saltarse el secuenciador. **Fix**: se elimina el
  parámetro y cada método obtiene internamente `await self.next_executed_at(account_id)`; la
  secuencia es ahora obligatoria por infraestructura, no por disciplina del caller. En `trade.py` se
  eliminan `_ledger_ordering`/`_FEE_ORDER_GAP` y la llamada manual al secuenciador (trade → X,
  fee → X+1 µs natural).
- **Auditoría 2 — `totalSamples` inflado.** `compute_lane_weights()` y el payload `"totalSamples"`
  sumaban `sample_sizes.values()` sin filtrar, contando familias descartadas por `min_samples`.
  **Fix**: nuevo `_effective_total_samples(family_weights, sample_sizes)` que suma solo las familias
  con peso, usado en ambos sitios para unificar la puerta de decisión con lo publicado al operador.
- **Test de concurrencia multi-portfolio (N3).** Nuevo
  `packages/py/infrastructure/tests/chaos/test_multi_portfolio_ledger_sequence.py`: dos carteras de
  la misma cuenta, ráfagas concurrentes, `executed_at` estrictamente creciente y cadena
  `balance_after` encadenada. Se valida localmente contra `bolsa_v1_chaos` (los chaos no entran en
  CI, deuda anotada).
- **Detalle del script de limpieza (no es fallo).** `custody_obligation` (005) y
  `custody_obligations` (006) **coexisten** legítimamente: la 006 no borra la 005. La lista
  `ACCOUNT_CHILD_TABLES` es correcta tal cual.
- **Verificación (local)**: `ruff --config pyproject.toml` **All checks passed** · `mypy` full-tree
  **Success (477 ficheros)** · `import-linter` **4 contratos OK** · batería offline del job
  `quality` **en verde** · chaos `test_multi_portfolio_ledger_sequence` **passed** contra PG real.

## [1.64.0-beta] — V2.39 · Régimen de mercado por trial (incremento 4) — 2026-09-11

Cuarto incremento de **Strategy Intelligence**: la evidencia gana la segunda dimensión de
granularidad que V2.38 dejó apuntada, el **régimen de mercado** bajo el que se evaluó cada trial.
Se deriva de las **propias barras del trial** (as-of, determinista y versionado), se persiste en una
columna nueva nullable `research_trials.regime` (migración aditiva) y se publica como dimensión
observable y agregable. **No** entra en el reparto de cupos ni en la clave `familia|region`.

- **Por qué un régimen derivado de barras y no el macro cognitivo.** `bolsa_analytics.cognitive.market_state`
  se alimenta de `fetch_macro_snapshot_dict`, que usa valores _live_ de Yahoo (`date.today()`,
  `closes[-1]`) y **no persiste serie histórica**: no es calculable as-of. Etiquetar un trial pasado
  con el régimen de hoy sería inventar dato — exactamente lo que V2.38 evitó. El régimen de barras, en
  cambio, es derivable en el punto del LAB que ya tiene las barras del trial.
- **Núcleo determinista y puro.** Nuevo módulo `bolsa_application.discovery_market_regime`
  (`math_version=discovery_market_regime_v0`): un solo eje con etiquetas `trend_up` / `trend_down` /
  `range` / `high_vol`. Tendencia por pendiente normalizada por volatilidad; volatilidad por rango
  relativo medio (high-low-close). `high_vol` tiene prioridad (en mercado revuelto la dirección es
  poco fiable). **Fail-closed**: menos de `MIN_REGIME_BARS`, NaN/inf, high-low ausentes o ventana
  degenerada ⇒ sin régimen (`""`); nunca se aproxima. Sin LLM, sin red, sin BD.
- **Persistencia por trial.** Migración aditiva **`039_research_trials_regime`** (columna
  `regime String NULL`, sin backfill, `downgrade()` completo): los trials históricos quedan `NULL`.
  Write-path completo: `OptimizeSmaGridResult.regime` se calcula en los 4 constructores del dataclass
  (con la ventana real de cada camino) y `optimization_runs` lo persiste (entidad + Protocol + repo
  SQL + `_regime_for_trial` fail-closed con fallback a `params`/`blocks`).
- **Agregación y evidencia.** `family_evidence_summary` y `posterior_evidence_summary` amplían su
  `GROUP BY` con `regime`; el snapshot publica el desglose aditivo **`regimeGranularity`** (fuera del
  `snapshot_hash`, dentro del `evidence_fingerprint`) y la evidencia posterior añade `regimeCounts`.
  **La clave de granularidad `familia|region` NO cambia**: el régimen es una **dimensión paralela**;
  meterlo en la clave habría roto `_collapse_regions` y la compatibilidad V2.37/V2.38.
- **Rollout reversible.** Nuevo flag **`AUTO_ORCHESTRATOR_ADAPTIVE_REGIME`** (OFF por defecto). Con
  OFF el LAB **no calcula ni persiste régimen** (`emit_regime=False`, fijado por el composition root,
  no por la candidata): los trials quedan a `NULL` y la evidencia es **idéntica** a la de V2.38.1.
  La lección del P2-01 de V2.38.1 se aplica aquí de raíz: la equivalencia se garantiza por la vía del
  write-path, no por un colapso posterior.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`; LIVE bloqueado; sin LLM en hot path; fail-closed;
  H1/H2; long-only; gates CPCV/PBO/DSR/WFE/OOS sin relajar; anti-explosión `1784` intacto; la clave
  compuesta `familia|region` y `_collapse_regions` **sin modificar**; con el flag OFF, comportamiento
  idéntico a V2.38.1. Alembic head pasa a **`039_research_trials_regime`**.
- **Verificación (local)**: `ruff` con invocación CI exacta (`--config pyproject.toml`) **All checks
  passed** · `mypy` Success en los módulos tocados · suites V2.39 offline **212 passed** · PG
  `test_discovery_evidence_snapshot_pg.py` **18 passed** (migración 039 upgradable/downgradable +
  agregación por régimen + roundtrip).

## [1.64.1-beta] — V2.39.1 · Hotfix de la auditoría interna de V2.39 — 2026-09-13

Hotfix sobre `1.64.0-beta` (auditoría interna previa a la externa). Cierra dos **P2** de Discovery, un
**P1** de arranque, un **P1** de integridad del ledger y la deuda de hermetismo de los tests PG que
hacía el CI no determinista. **Sin cambios de semántica funcional** ni de migraciones (Alembic head
sigue en **`039_research_trials_regime`**).

- **P2-01 — La gramática no consumía su cupo completo (A14).** El orquestador repartía el presupuesto
  entre planes, pero `grammar_variants_for_plan` se invocaba siempre con el mismo eje, así que un plan
  con varios bloques opcionales **no rotaba la variante** y el cupo del allocator quedaba
  subconsumido. **Fix**: `grammar_emission_cap` se calcula sobre el cupo real y la llamada pasa
  `axis_index=emitted_for_grammar`, de modo que cada emisión avanza de eje. Se reordena además la
  enumeración para que el **trigger varíe antes que el exit** (antes el exit agotaba el presupuesto de
  variación y el trigger quedaba con una sola forma).
- **P2 — La evidencia fusionada por clave compuesta perdía y sesgaba datos.** `compute_family_weights`
  agregaba las filas por `familia|region` con un `GROUP BY` que **descartaba en silencio** las filas
  con la misma clave procedentes de regímenes distintos, y ponderaba `avgScore` por número de filas en
  vez de por muestra. **Fix**: nuevo `_merge_aggregates_by_key` que fusiona por clave compuesta con
  semántica explícita — contadores por suma, ratios por **media ponderada por cobertura**,
  `bestScore` por máximo y `kConsumed` por suma. El productor (`family_evidence_summary`) expone
  `is_score_n` para poder ponderar `avgScore` por muestra real. `evidence_fingerprint` sigue
  detectando reescrituras retrospectivas.
- **P1 — El arranque de la API moría con `MultipleResultsFound`.** `_load_default_scope` /
  `_ensure_default_account` filtraban solo por `is_default` con `scalar_one_or_none()`: en cuanto
  existía **otra** cuenta por defecto (otro tenant, o residuo de tests de integración) el bootstrap
  reventaba. **Fix**: ambas consultas filtran por `owner_principal()` (el tenant propietario), que es
  la semántica correcta en un modelo multi-tenant. Regresión:
  `test_migration_survives_foreign_tenant_default_account`.
- **P1 — Perfiles de inversor invisibles (404) al abrir cuenta.** `EnsureDefaultInvestorProfile` /
  `EnsureAccountInvestorProfile` creaban el perfil **sin `user_id`**, así que el control de acceso
  owner-scoped no lo encontraba y la ruta devolvía 404 sobre un recurso propio. **Fix**: se propaga
  `user_id` (el principal de la request) por las tres ramas de creación.
- **P1 — Mandatos con instrumentos huérfanos tumbaban el `PUT`.** Un `instrument_id` inexistente en el
  payload provocaba `ForeignKeyViolation`. **Fix**: `sync_account` valida los `instrument_id` contra el
  catálogo y **descarta** las tenures y links huérfanos en vez de estampar la transacción.
  Regresión: `test_mandate_sync_orphan_instrument.py`.
- **P1 — El worker de custodia abortaba el job entero por una sola cuenta rota.** `RunCustodyJob`
  procesaba las cuentas en serie sin aislar fallos: una cuenta sin cartera legacy (`ValueError`)
  mataba el lote completo. **Fix**: cada cuenta se procesa en su propio `try/except`, con rollback
  best-effort, marcado como `skipped` con motivo en el resumen y continuación del job. Regresión:
  `test_job_cuenta_rota_no_aborta_el_resto`.
- **P2 — El replay idempotente de trade pasaba por el gate de apertura (403 → 200).** `ExecuteTrade`
  evaluaba el gate **antes** de comprobar la `idempotencyKey`: un reenvío legítimo quedaba vetado con
  403 en vez de devolver el 200 original, y un payload divergente daba 403 en vez de 409. **Fix**: la
  comprobación de idempotencia ocurre primero — replay con payload idéntico ⇒ 200; payload divergente
  ⇒ `IdempotencyKeyReused` (409). Regresiones en `test_execute_gated_portfolio_trade.py`.
- **P2 — El ledger perdía el orden real bajo concurrencia.** `append_trade` y `append_fee` tomaban
  cada uno su propio `datetime.now(UTC)`: bajo concurrencia caían en el mismo microsegundo y el
  consumidor que ordena por `(executed_at, id)` desempataba por un **`id` aleatorio**, intercalando la
  fee antes del trade y rompiendo `balance_after[n] == balance_after[n-1] + amount[n]`. El cash era
  correcto, pero el ledger dejaba de ser **reproducible y auditable**. **Fix**: ambos asientos derivan
  del `executed_at` de la transacción (fijado bajo `with_for_update`), con el trade 1 µs antes de la
  fee para que el orden sea el de aplicación real. Verificado por mutación.
- **Hermetismo de tests PG (sin esto el CI era no determinista).** Varias suites dejaban residuos en
  la BD compartida y otras no eran inmunes a ellos: cuentas `AUTO-*`/`lc-*`, barras OHLCV sintéticas y
  filas `live_orders` `UNKNOWN`. Como `claim_unknown_batch` es una barrida **global** (por diseño: un
  worker de recuperación atiende cualquier cuenta), un residuo de una pasada hacía fallar el test de
  concurrencia de otra. **Fix**: fixture `autouse` de limpieza por sesión en `conftest.py`, purga
  explícita en las suites que commitean filas, purga de las `UNKNOWN` de prueba antes de sembrar, y
  limpieza de las suites que crean cuentas. Además se corrigieron 4 hallazgos de `ruff` (orden de
  imports y un `l` ambiguo) que habrían dejado el job `quality` en rojo.
- **Estabilidad de la certificación por proceso del scheduler (A9).** Los dos tests que levantan el
  **proceso real** `scheduler_worker` esperaban actividad con un plazo fijo de 90 s _sin comprobar si
  el subproceso seguía vivo_: bajo un job completo (miles de tests, máquina cargada) el arranque
  —import de la app + `database_bootstrap` con advisory lock + primer tick— podía excederlo, y el
  fallo se reportaba como «0 eventos» sin diagnóstico. **Fix**: la espera es por **progreso real** con
  un margen de arranque explícito (`_STARTUP_GRACE_S`) y **falla al instante con el log del
  subproceso** si el proceso muere, en vez de agotar el plazo a ciegas. Se documenta el hallazgo de que
  `_reconcile_before_trusting` marca `UNKNOWN` (y por tanto **veta aperturas**) cuando el lector
  canónico falla o devuelve `None`, que es la vía por la que el día AUTO podía quedar sin fills.
- **Verificación (local)**: `ruff --config pyproject.toml` **All checks passed** · `import-linter`
  (4 contratos) OK · `mypy` full-tree **Success, 0 errores en 477 ficheros** · job `quality` del CI
  reproducido **2589 passed** · flaky de concurrencia de `live_orders` **10/10** en verde ·
  `test_a9_scheduler_process_pg_zero_human` **6/6** aislado y **3/3** junto al resto de PG.

## [1.64.2-beta] — V2.39.2 · Cierre de flaky: el ledger se secuencia por estado, no por reloj — 2026-09-13

Segunda pasada de la auditoría interna, centrada en los **flaky** que quedaban antes de la auditoría
externa. Tres causas distintas, una de ellas un **bug real de producción** que la primera pasada no
alcanzó a cerrar. Alembic head sigue en **`039_research_trials_regime`** (sin migraciones nuevas).

- **P1 — El `executed_at` del ledger se derivaba del reloj de pared.** La primera pasada (V2.39.1)
  hizo que trade y fee compartieran el instante de la **transacción**, pero ese instante se sigue
  tomando con `datetime.now(UTC)`. Bajo concurrencia eso **no ordena**: dos transacciones serializadas
  por el `with_for_update` de la cartera pueden leer el reloj en orden **invertido** respecto al de
  commit, y el consumidor que ordena por `(executed_at, id)` reconstruye una secuencia falsa (el
  desempate por `id` es un UUID v4 **aleatorio**, no rescata el orden real) → la cadena
  `balance_after[n] == balance_after[n-1] + amount[n]` se rompe de forma intermitente. Capturado con
  instrumentación forense: el salto real entre dos asientos consecutivos **no coincidía con su
  `amount`**, prueba de que el asiento se había aplicado en otra posición del orden.
  **Fix — secuenciador por cuenta:** nuevo `SqlAlchemyLedgerRepository.next_executed_at(account_id)`,
  que devuelve `max(now, último_executed_at_de_la_cuenta + 1 µs)`, leído en la **misma transacción**
  que el llamador (que ya retiene el lock de la cartera). El instante se deriva del **estado
  persistido**, no del reloj, así que es **estrictamente creciente con el orden de aplicación**. Se
  conecta en las cuatro rutas que escriben asientos: trade (`ExecuteTrade`), custodia
  (`ApplyCustodyFees`, que además arrastraba el bug simétrico de calcular `balance_after` desde un
  `get_summary` **pre-lock**) y depósito/retiro (`cash.py`). El paso de 1 µs convierte el desempate
  por `id` en irrelevante: dos asientos nunca comparten instante y el orden es determinista.
- **P1 — `ApplyCustodyFees` calculaba `balance_after` con el cash PRE-lock.** Mismo patrón que
  `ExecuteTrade` ya había corregido (EXEC-B-CONC), pero la custodia nunca lo recibió: leía
  `get_summary().portfolio.cash` **antes** de `deduct_cash` (que es quien toma el `with_for_update`) y
  escribía ese balance desfasado. **Fix**: el `balance_after` se toma del cash **POST-lock** que ya
  devolvía `deduct_cash`, en las dos ramas (liquidación de PENDING y periodo actual).
- **Flaky de entorno — `pool_size=64` agotaba las conexiones del PostgreSQL local.** El escenario de
  estrés abría un pool de 64 conexiones por test; con `max_connections=100` y la convivencia con otros
  engines (otras suites, workers, API) el servidor respondía `FATAL: sorry, too many clients already`
  y los tests fallaban **en ráfaga** con un error de entorno que **enmascaraba el veredicto real**.
  **Fix**: `pool_size=24`. El escenario serializa igual sobre la fila de cartera, así que el pool
  grande no aceleraba nada y sí monopolizaba el servidor. Resultado: **0/10 fallos y ~38 s** por
  pasada (antes ~45 s con fallos intermitentes).
- **Honestidad del test `test_two_workers_claim_disjoint_unknown_batch`.** Hacía `asyncio.gather` de
  dos `claim_unknown_batch` con **rollback inmediato** de cada uno y exigía que fueran disjuntos: eso
  **no certificaba** la exclusión mutua, la refutaba — en PostgreSQL real el segundo `SELECT ... FOR
UPDATE SKIP LOCKED` puede correr **después** del rollback del primero y ver las filas liberadas (el
  resultado dependía del entrelazado del event loop). La propiedad real y determinista que garantiza
  el lease es «**mientras el lease está vivo y no expirado, otro worker no reclama la misma fila**».
  El test ahora retiene las dos transacciones abiertas, afirma que el segundo worker obtiene **vacío**
  y, tras liberar el primero, comprueba el **relevo** cubriendo el lote completo.
- **Certificación por proceso del scheduler (A9): el bucle de vigilancia antirrecompra agotaba el
  presupuesto siempre.** Tras el crash+restart, el test esperaba «a que ocurra una re-compra» para
  fallar; pero el camino **correcto** es que nunca ocurra, así que el bucle agotaba el plazo completo
  en cada pasada (de ahí los ~518 s y, con el margen recortado, fallos intermitentes de «no abrió
  posición»). **Fix**: ese sondeo usa un plazo **corto y acotado** (`_RESTART_WATCH_S = 20 s`) —una
  re-compra aparecería en los primeros ticks, no al final— y los tres bucles comprueban `proc.poll()`
  para **fallar al instante con el log del subproceso** si el worker muere, en vez de esperar a
  ciegas. Pasada: **~28 s** (desde ~518 s) y **8/8 en verde**.
- **Verificación (local)**: `ruff --config pyproject.toml` **All checks passed** · `mypy` sobre las
  fuentes tocadas **Success (272 ficheros)** · `import-linter` **4 contratos OK** · suite de aplicación
  **1468 passed** · infraestructura **137 passed, 1 xfailed** · recovery + idempotencia **8 passed** ·
  chaos de ledger/concurrencia **10/10 pasadas en verde (0 fallos)** · A9 **8/8 (~28 s)** · regresión
  del secuenciador verificada **por mutación** (revertir el fix hace fallar el test nuevo) ·
  `test_two_workers_claim_disjoint_unknown_batch` **5/5** estable.
- **Nota de entorno (no del código).** Los flaky restantes se reprodujeron **solo** bajo ejecuciones
  back-to-back masivas: el PostgreSQL local agotaba conexiones (`FATAL: sorry, too many clients
already`) y los tests que dependen del arranque de un subproceso agotaban su plazo. Con el pool de
  los chaos acotado a 24 y la BD en reposo, **20/20 pasadas del chaos y 8/8 del A9 fueron verdes**. El
  CI (máquina limpia, un job) no reproduce esa saturación, pero se deja anotado para no confundirla
  con una regresión de código.

### Tercera pasada — la gramática de Discovery emitía planes inoperables

Al correr la batería exacta del CI apareció un fallo que **no** era flaky: la certificación A14
(`test_a14_grammar_discovery_pg`) fallaba con _«ningún plan gramatical produjo evidencia CPCV/PBO
real»_. La investigación cerró una cadena de **tres** causas, todas medidas, y una de ellas convertía
el `P2-01` anterior en un colapso silencioso del grid.

- **P1 — El 100 % de los planes gramaticales producía menos de 2 columnas operables.** El PBO CSCV
  exige `len(candidates) >= 2`; con **1 solo trial** (o 0) `build_lab_pbo_summary` devuelve `None` y
  los gates `robustness`/`walk_forward` quedan **sin evidencia** sobre candidatas gramaticales, en
  silencio. Medido sobre los 1784 planes: **1184 con 1 columna y 600 con 0** — ninguno alcanzaba 2.
  El LAB registraba «0 trials» y el orquestador real pasa exactamente la misma ruta, así que el
  defecto era **de producción**, no del test.
- **Causa 1 — el trigger y el filtro de tendencia Donchian eran matemáticamente inalcanzables.** El
  canal `dc:upper` es `max(high)` de la ventana **incluyendo la barra actual**, así que
  `close > upper` es imposible: el máximo de la ventana es siempre `≥ high[i] ≥ close[i]`. Medido:
  **0 disparos incluso en una serie estrictamente creciente**. **Fix**: trigger y trend filter usan la
  banda **media** (`dc:mid`), igual que el preset `donchian_breakout` de producción (que sí opera:
  381/400 barras con `close > mid`). La banda `upper` de la gramática quedaba inerte.
- **Causa 2 — el eje de permutación podía romper el par trigger/exit homónimo.** Al rotar el eje sobre
  el trigger (lo introdujo `P2-01`), el `exit_ema10_cross_ema50` (bajista) seguía mirando las **mismas
  EMAs** que el trigger nuevo: un cruce alcista y otro bajista de las mismas series **no coinciden
  nunca**, así que el trigger quedaba inalcanzable. **Fix**: el exit homónimo se permuta **con** el
  trigger, por par (`_AXIAL_TRIGGER_EXIT_PAIRS`), y el eje rota **preferentemente** sobre los bloques
  opcionales (regime/trend/momentum), cayendo en los axiales solo si el plan no tiene ninguno. Se
  conserva la rotación de ejes que arreglaba el `P2-01`.
- **Causa 3 — incompatibilidad estructural entre bloques, no vetada.** `trigger_ema10_cross_ema50` +
  `trend_ema20_gt_ema50`: el cruce de EMA10 sobre EMA50 es **necesariamente anterior** a que EMA20
  confirme por encima de EMA50, y los gates del plan se exigen **simultáneamente**. Medido: 210 barras
  cumplen ambas condiciones, **0 cruces**. **Fix**: dos vetos de inanición deterministas y fail-closed
  (`_mutually_unreachable_trigger_exit`, `_conjunctive_ema_starvation`) sacan esas combinaciones de la
  enumeración en vez de emitirlas sin evidencia posible. 1684 planes, **0 degenerados**.
- **El test de integración A14 sembraba una serie donde sus propios disparadores no existían.** La
  rampa descendente dejaba `close > sma200` y `close > max(high, n)` en **0 barras**. **Fix**: la serie
  ahora son ciclos con tramo alcista **más largo que el período del canal** (60 > 40) y retrocesos que
  cruzan las EMAs. El test pasa de **fallar a los 146 s** a pasar en **5,8 s**.
- **Regresión**: dos tests nuevos en `test_discovery_grammar.py` exigen **≥2 columnas operables por
  plan** sobre la serie de integración y que el trigger Donchian sea alcanzable.

### Tercera pasada — dos fallos que solo aparecían en la batería completa

- **P1 (producto) — una lista con instrumentos no se podía borrar.** `SqlAlchemyListRepository.delete`
  borraba la fila de `instrument_lists` **sin vaciar antes** `instrument_list_items`; la FK `list_id`
  no es `ON DELETE CASCADE`, así que cualquier lista **con** instrumentos violaba la integridad
  referencial y `DELETE /api/lists/{id}` devolvía **500 en vez de 204**. **Fix**: los items se borran
  en la misma transacción justo antes que la lista. Regresión:
  `test_delete_list_with_items_does_not_violate_fk`.
- **P2 (hermeticidad) — la tabla `lifecycle_outbox` envenenaba suites entre sí.** `claim_batch` es una
  barrida **global** (FIFO por posición, sin filtrar por posición) con sanitizado de huérfanas;
  `test_financial_integrity_pg` dejaba una cabeza FIFO `dead` sin limpieza y otras suites filas
  `pending`/`processing`, de modo que el worker de `test_lifecycle_outbox_worker_pg` reclamaba filas
  **ajenas** y el hook inyectado (`on_before_apply_commit`) consumía su **único** disparo antes de que
  la fila propia pasara a `processing` → _«status=applied expected=processing»_. **Fix**: el test de
  integridad limpia su fila en `finally` y el fichero del worker aísla la tabla (purga
  `pending`/`processing` antes y después de cada test). **Verificado**: `apps/api-python/tests` +
  `packages/py/infrastructure/tests` pasan **521 en dos pasadas consecutivas** (antes 2 failed en cada
  intento de la batería completa).
- **Verificación (local) de la tercera pasada**: `ruff` **All checks passed** · `mypy` **Success (477
  ficheros)** · batería completa del job _quality_ **1306 passed, 0 failed** · gramática + A14
  **40 passed**.

## [1.63.1-beta] — V2.38.1 · Hotfix de los 2 P2 de la auditoría de V2.38 — 2026-09-11

Hotfix de la **auditoría externa de `v2.38-beta`** (commit `41b96a41`, CI GREEN). Cierra dos P2
conceptuales sin cambiar la semántica funcional del incremento 3.

- **P2-01 — La equivalencia "byte-idéntica a V2.37 con el flag OFF" no se cumplía.** El write-path
  etiquetaba `discovery_param_region` **siempre, sin consultar el flag**; con OFF el snapshot contenía
  regiones y `_collapse_regions` colapsaba con `max(peso)` en vez de re-derivar la fuerza sobre el
  agregado familiar (el snapshot solo persiste `family_weights`/`sample_sizes`, así que el colapso no
  puede recomputarla). Divergencia medida: `0.747` (V2.37) vs `0.803` (colapsado) ≈ **7,4 %**.
  **Fix**: el motor recibe la decisión como dependencia inyectada
  (`discover_for_instrument_with_summary(..., emit_param_region: bool = True)`) y el worker pasa
  `adaptive_param_region_enabled()`. Con OFF **no se genera región**, la evidencia es idéntica a la de
  V2.37 y el colapso es un no-op: **equivalencia real, no aproximada**. `_collapse_regions` se
  conserva, pero reencuadrado como puente para **evidencia histórica** ya persistida con región
  (transición ON→OFF), con su docstring corregido para no prometer equivalencia numérica.
- **P2-02 — `evidence_fingerprint` no ordenaba por clave compuesta.** `compute_family_weights` ordenaba
  por `(presetKey, paramRegion)` pero el fingerprint solo por `presetKey`; con varias regiones de una
  misma familia el orden quedaba a merced del orden de entrada (`sorted` estable ⇒ fragilidad latente
  en un valor que es identidad del dataset). **Fix**: orden canónico por clave compuesta + tests de
  orden adverso (familias y regiones barajadas producen el mismo fingerprint).
- **P3 — Versionado de la search policy.** `MATH_VERSION_SEARCH_POLICY_V0` tenía el valor
  `"discovery_search_policy_v1"` (reescrito in-place), de modo que una política histórica no se
  distinguía de la nueva. **Fix**: coexisten `_V0` = `"discovery_search_policy_v0"` y `_V1` =
  `"discovery_search_policy_v1"`, con alias `MATH_VERSION_SEARCH_POLICY` para la vigente.
- **P3 — Test mal nombrado.** `test_granularity_does_not_change_snapshot_hash_vs_plain_family` era
  tautológico; se documenta y se añade la comprobación real (recalcular `snapshot_hash` sobre los
  componentes declarados reproduce el hash almacenado ⇒ el payload/granularidad no participa).
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`; LIVE bloqueado; sin LLM en hot path; fail-closed;
  H1/H2; gates sin relajar; anti-explosión `1784` intacto; Alembic head sigue en
  `038_research_trials_param_region` (el hotfix no añade migración).
- **Verificación (local)**: `ruff` con invocación CI exacta (`--config pyproject.toml`) **All checks
  passed** · `mypy` Success en los módulos tocados · offline **1497 passed** (suites relevantes).

## [1.63.0-beta] — V2.38 · Granularidad por región de parámetros (incremento 3) — 2026-09-11

Tercer incremento de **Strategy Intelligence**: la evidencia adaptativa deja de agregarse solo por
familia H0 (`preset_key`) y pasa a granularidad por **región de parámetros**, con bucket determinista
y versionado, columna nueva nullable en `research_trials` (migración aditiva) y consumo en la search
policy. Régimen e **instrument class quedan explícitamente fuera**: no existen hoy como dato
persistido (ver más abajo).

- **Núcleo determinista y puro.** Nuevo módulo `bolsa_application.discovery_param_region`
  (`math_version=discovery_param_region_v0`): `param_region_for_point` deriva una clave estable del
  punto dentro del grid de su familia (ordinal en el producto cartesiano determinista + hash corto de
  los valores), `compose_granularity_key`/`split_granularity_key` definen la clave compuesta canónica
  `familia` o `familia|region`. **Fail-closed**: un punto fuera del grid no recibe región (`""`), no se
  aproxima. Sin LLM, sin red, sin BD.
- **Persistencia por trial.** Migración aditiva **`038_research_trials_param_region`** (columna
  `param_region String NULL`, sin backfill, `downgrade()` completo): los trials históricos quedan
  `NULL` (no se inventa su región). Write-path completo: el motor etiqueta la candidata
  (`discovery_param_region`), el runner la propaga (`_REGION_KEYS`, antes se descartaba) y
  `optimization_runs` la persiste (`ResearchTrial.param_region`, entidad + Protocol + repo SQL).
- **Agregación por clave compuesta.** `family_evidence_summary` y `posterior_evidence_summary` agrupan
  por `preset_key + param_region` y devuelven `paramRegion`; el job batch mergea por clave compuesta.
  **Retrocompatible**: si todas las regiones son `NULL`, la clave colapsa a la familia y el
  `snapshot_hash` es **idéntico** al de V2.37.
- **Snapshot y fingerprint.** `compute_family_weights` mintea la clave compuesta; `familyGranularity`
  deja de estar vacío y publica `{family, paramRegion}` reales (aditivo, **fuera del `snapshot_hash`**,
  dentro de `evidence_fingerprint`).
- **Search policy y motor.** `SearchPolicy` sube a `discovery_search_policy_v1` e incluye
  `granularityKeyVersion` en su hash (la fórmula de reparto no cambia: ya era agnóstica a la clave).
  El motor resuelve la clave compuesta y **filtra `param_points()` a la región** indicada; clave
  desconocida o región inexistente ⇒ no emite (fail-closed).
- **Rollout** — Flag nuevo `AUTO_ORCHESTRATOR_ADAPTIVE_PARAM_REGION` **OFF por defecto**: con OFF
  el write-path no genera región y el sistema es **equivalente a V2.37** (ver V2.38.1/P2-01: el
  colapso `_collapse_regions` solo normaliza evidencia histórica y no es equivalencia numérica).
  Observabilidad aditiva: `DiscoveryEmissionSummary` gana `adaptive_region_emissions`/
  `adaptive_region_count`; los contadores de ciclo/proceso suman `adaptive_region_emissions` y los
  logs reportan `adaptive_regions=N/M`.
- **Por qué NO régimen ni clase de instrumento.** Régimen solo existe como clasificación en memoria en
  la capa cognitiva (`bolsa_analytics.cognitive.market_state`) y jamás se persiste; `instruments.type`
  es un enum con un único valor (`stock`) y `sector` es texto libre sin poblar. Incorporarlos exige
  primero persistirlos como fuente de verdad; la clave compuesta está diseñada para admitir nuevos
  componentes sin romper el contrato.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`; LIVE bloqueado; sin LLM en hot path; fail-closed;
  long-only; H1 y H2 intactos; gates CPCV/PBO/DSR/WFE/OOS + coach sin relajar; test anti-explosión
  `len(plans) == 1784` intacto (solo se etiqueta, no se añade espacio de búsqueda); con el flag OFF,
  salida equivalente a V2.37 (ver V2.38.1 para la corrección del claim de byte-identidad).
- **Tests**: `test_discovery_param_region.py` (determinismo, estabilidad ante reordenación,
  fail-closed, ida y vuelta de la clave compuesta, anti-explosión intacta),
  `test_discovery_evidence.py` (claves compuestas aíslan regiones, hash estable y sensible a región,
  `familyGranularity` poblado/vacío, coexistencia histórica+regionada),
  `test_discovery_search_policy.py` (claves compuestas + `granularityKeyVersion`, filtrado por región,
  región desconocida fail-closed), worker (flag de región OFF/ON, `_collapse_regions`),
  PG (columna `param_region` + roundtrip, agregación por región, posterior por clave compuesta,
  roundtrip `038`).
- **Alembic head**: `038_research_trials_param_region`.
- **Verificación (local)**: `ruff` OK (ficheros tocados) · `mypy` Success en los módulos tocados ·
  offline **1703 passed** · PG con gates `A14_GRAMMAR_PG_REQUIRED=1` **14 passed** · anti-explosión
  `1784` intacto · `--dry-run` OK · sin región, `snapshot_hash` idéntico a V2.37.

## [1.62.0-beta] — V2.37 · Hardening de V2.36 (P2-01/02/03) + Adaptive Discovery Generation — 2026-09-11

Segundo incremento de **Strategy Intelligence**: cierra los tres P2 de la auditoría externa de
`v2.36-beta` y pasa de "cuánto presupuesto recibe una familia" a **"qué hipótesis merece
explorarse"**, sin relajar ningún gate y manteniendo el aprendizaje **fuera del hot path**.

- **P2-01 — Evidencia estadística rica (LAB + posterior).** La v0 saturaba el score en 1.0
  (`clamp(avgScore,0,1) × success_ratio`) y perdía toda la información por encima de 1. Aplicación:
  nueva señal compuesta `discovery_evidence_v1` con componentes monótonos (`1 - exp(-x)` para el
  `is_score`, `tanh` para el Sharpe, `1 - exp(-(pf-1))` para el profit factor, `exp(-dd/50)` para el
  drawdown y la evidencia posterior ponderada por nivel ADR-012), combinados por media ponderada con
  **_shrinkage_ por cobertura** hacia un ancla neutral 0.5: una métrica ausente **no** puntúa como 0
  (ni premia la ausencia). `family_evidence_summary` agrega ahora Sharpe/PF/drawdown medios con
  `metricCoverage` explícita y nunca inventa ceros; nuevo `posterior_evidence_summary` agrega
  shadow/paper forward por familia vía `research_evidence` (join por `trial_id`). La **v0 se conserva
  reproducible** (`--math-version discovery_evidence_v0`).
- **P2-02 — Política formal exploración/explotación.** `DiscoveryBudgetAllocator` gana
  `exploration_floor_ratio` (default 0.5): fracción mínima del presupuesto de candidatas reservada a
  los carriles exploratorios (catálogo + gramática) que el carril `adaptive` **nunca** puede absorber.
  Materializa el invariante "champion cannot teach itself" en el reparto. Con ratio 0 el reparto es
  el histórico de v2.36 (test de regresión).
- **P2-03 — Freshness y fingerprint del snapshot.** `DiscoveryEvidenceSnapshot` gana
  `evidence_fingerprint` (huella del research dataset agregado, determinista y sin reloj) y
  `is_fresh(now, max_staleness_days)`; la entidad documenta las **tres identidades** (`snapshot_hash`
  = conocimiento, `id` = instancia, `created_at` = persistencia — "más nuevo" ≠ "más reciente en
  conocimiento"). Migración aditiva **`037_discovery_evidence_freshness`** (columna nullable, sin
  backfill, `downgrade()` completo). El worker descarta por **fail-closed** un snapshot `stale`
  (`AUTO_ORCHESTRATOR_ADAPTIVE_MAX_STALENESS_DAYS`, default 30 días): el reparto vuelve al histórico
  en vez de gobernar con aprendizaje viejo. `0` desactiva la validación (compatibilidad v2.36).
- **V2.37 incremento 2 — Adaptive Discovery Generation.** Nuevo módulo de aplicación
  `discovery_search_policy` (`SearchPolicy` determinista y versionado `discovery_search_policy_v0`):
  convierte el prior por familia en **cuotas de emisión por familia**, repartidas en dos tramos
  (explotación top-k por peso + exploración uniforme garantizada, `exploration_ratio` default 0.25).
  El carril `adaptive` con cupo **emite candidatas reales** en `strategy_discovery_engine`
  (prefijo `ADAPTIVE_FAMILY_PREFIX`), reutilizando el catálogo curado — sin añadir espacio de búsqueda
  nuevo. Determinismo: mismo `(instrument_id, snapshot, budget)` ⇒ mismas candidatas en mismo orden;
  el motor sigue sin consultar BD ni reloj. Fail-closed: sin política o sin snapshot ⇒ carril no emite
  (byte-idéntico a v2.36).
- **Rollout** — Flag nuevo `AUTO_ORCHESTRATOR_ADAPTIVE_GENERATION` **OFF por defecto**: con OFF el
  carril solo recibe cupo observable (v2.36). El provider de snapshot se cablea si **cualquiera** de
  los dos flags está ON. Observabilidad aditiva: `DiscoveryEmissionSummary` gana
  `adaptive_candidates`/`adaptive_policy_hash`/`adaptive_exploration_quota`/`adaptive_families` y los
  contadores de ciclo/proceso suman `adaptive_candidates`/`adaptive_discoveries`.
- **Granularidad progresiva (P2-03 del audit)** — El payload del snapshot publica un desglose
  aditivo `familyGranularity` (régimen / región de parámetros / clase de instrumento) cuando el repo
  los aporte, sin romper el esquema ni participar en el hash.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`; LIVE bloqueado; sin LLM en hot path; fail-closed;
  long-only; H1 y H2 intactos; gates CPCV/PBO/DSR/WFE/OOS + coach sin relajar; test anti-explosión
  `len(plans) == 1784` intacto; con los flags OFF, salida **byte-idéntica a v2.36**.
- **Tests**: `test_discovery_evidence.py` (v1 sin saturación, cobertura neutral, drawdown/PF/posterior,
  fingerprint, suelo de exploración, cota adaptive), `test_discovery_search_policy.py` (determinismo,
  fail-closed, exploración garantizada, emisión adaptativa dentro del presupuesto global y
  determinista), worker (freshness fail-closed, staleness 0, flag de generación), PG (métrica rica +
  cobertura, posterior por familia, fingerprint persistida, roundtrip `037`).
- **Alembic head**: `037_discovery_evidence_freshness`.
- **Verificación (local)**: `ruff` OK · `lint-imports` 4/4 · `mypy` **475 files** Success · offline
  **1547 passed** · PG discovery/snapshot **12 passed** + snapshot detallado **10 passed** +
  lifecycle **6 passed**.

## [1.61.0-beta] — V2.36 · Strategy Intelligence adaptativa (incremento 1: carril `adaptive`) — 2026-09-11

Primer incremento de la **V2.36 Strategy Intelligence adaptativa**: cerrar el bucle
`evidence → aprender → ajustar búsqueda` activando el carril `adaptive` del
`DiscoveryBudgetAllocator` (hoy peso `0.0`, un hueco semántico) con pesos derivados de
**evidencia real ya persistida del LAB**. El aprendizaje NO ocurre dentro del motor: se
materializa en un **snapshot determinista, versionado y persistido**, calculado fuera del
hot path por un job batch/CLI, e **inyectado** como dependencia. El discovery sigue siendo
una **función pura dada la tupla `(instrument_id, snapshot)`**.

- **Dominio** — entidad `DiscoveryEvidenceSnapshot` (dominio puro, `frozen`/`slots`) con
  `snapshot_hash`, `math_version`, ventana temporal, `family_weights` (familia H0 →
  peso), `lane_weights` (catálogo/gramática/adaptive), `sample_sizes` y `payload`; más el
  contrato `DiscoveryEvidenceSnapshotRepository` (`save`/`get_latest`/`get_by_hash`/
  `list_recent`). Método de lectura agregada nuevo `family_evidence_summary` (por
  `preset_key`, orden canónico) en el protocolo de trials.
- **Aplicación** — `bolsa_application.discovery_evidence` (nuevo): builder determinista
  `build_discovery_evidence_snapshot` + `compute_family_weights`/`compute_lane_weights` +
  `snapshot_hash`. Aritmética con redondeo fijo, orden canónico por familia y hash estable
  (`sort_keys`+separadores compactos, patrón `definition_hash`). `math_version`
  `discovery_evidence_v0` audita la fórmula. **Fail-closed**: sin muestra mínima por
  familia (`min_samples`) ni total (`min_total_samples`) el peso adaptativo es `0.0`
  explícito — nunca un peso inventado. Peso acotado a `[0, max_adaptive_weight]` (0.5 por
  defecto) contra overfitting a familias con suerte (multiple testing documentado).
- **Persistencia** — migración aditiva **`036_discovery_evidence_snapshots`**
  (`down_revision=035_paper_forward_evidence`), tabla nueva con `snapshot_hash` único,
  `math_version`, ventana y `payload` JSONB; sin backfill, `downgrade()` completo.
  Repositorio `SqlAlchemyDiscoveryEvidenceSnapshotRepository` inmutable por hash
  (`save` idempotente).
- **Job batch/CLI** — `apps/api-python/scripts/build_discovery_evidence_snapshot.py`:
  lee evidencia → construye snapshot → persiste. **Idempotente de verdad** por
  `snapshot_hash`: el corte `window_to` por defecto es el `created_at` del trial más
  reciente (dato-dependiente, no reloj), de modo que dos ejecuciones sobre la misma
  evidencia dan el mismo hash y la segunda no reescribe. `--dry-run` para auditar la
  fórmula sin tocar la BD. No se ejecuta desde el worker ni el request path.
- **Worker (inyección, sin tocar el hot path)** — flag nuevo
  `AUTO_ORCHESTRATOR_ADAPTIVE_ALLOCATOR` **OFF por defecto**: con OFF no se lee la BD y
  todo es **byte-idéntico a v2.35.1**. Con ON, el bucle lee el snapshot vigente **una vez
  por ciclo** (`_refresh_adaptive_snapshot` + `_make_adaptive_snapshot_provider`, una
  sesión por operación) y lo inyecta en el allocator de todos los instrumentos del ciclo.
  `_discovery_allocator(snapshot)` toma el peso del snapshot (fail-closed: sin snapshot o
  sin evidencia ⇒ `0.0`, nunca el env por accidente).
- **Alcance del incremento 1 (explícito)** — se asigna **cupo real y observable** al
  carril `adaptive`; NO se añade espacio de búsqueda nuevo ni emisión adaptativa (eso es el
  incremento 2). No confundir "peso asignado" con "capacidad de búsqueda": debe quedar
  escrito. Catálogo, gramática simple y gramática compuesta quedan intactos.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`; LIVE bloqueado; sin LLM en hot path;
  fail-closed; long-only; H1 (`require_holdout=True` inviolable) y H2 (identidad de
  dataset) intactos; gates CPCV/PBO/DSR/WFE/OOS + coach sin relajar. Test anti-explosión
  `len(plans) == 1784` intacto.
- **Tests**: `test_discovery_evidence.py` (determinismo, orden-insensibilidad del hash,
  fail-closed, cotas, reproducibilidad por hash, cupo adaptativo sin romper el global);
  worker (flag OFF por defecto, peso del snapshot vs env, fail-closed),
  lectura única por ciclo, no-op sin provider); PG (tabla/índices a head, `save`
  idempotente por hash, `get_latest`/`get_by_hash`, agregación por familia, roundtrip
  `up/down` de la migración `036`).
- **Verificación (tres bloques, local)**: `ruff` + `lint-imports` (4/4) + `mypy` (474
  ficheros) verdes; offline `1518 passed` (domain + application + worker); PG con gates
  `A14_GRAMMAR_PG_REQUIRED`/`LIFECYCLE_PG_REQUIRED`/`AUTO_ORCHESTRATOR_PG_REQUIRED`
  `10 passed` + snapshot PG `6 passed` + lifecycle `57 passed` (incluye anti-explosión).
- **Alembic head**: `036_discovery_evidence_snapshots`.
- **Elevación**: `main == cb147d89` == tag **`v2.36-beta`**. Release-tag CI **GREEN
  verificado** (run [`34604803938`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34604803938),
  conclusión `success`, 2026-09-11): `python`, `lifecycle-pg`, `dr-verify`, `a7-gate`,
  `security`, `decision-spine`, `shared`, `frontend`, `playwright (mock E2E)` y `certify`
  en verde; `playwright (integrated E2E, opt-in)` correctamente skipped.

## [1.60.1-beta] — V2.35.1 · ESTUDIO hard gate (P1-01) — 2026-09-11

Cierra el único hallazgo P1 de la auditoría externa de v2.35-beta: el AUTO podía
**abandonar ESTUDIO** y operar la allowlist CSV como universo cuando ESTUDIO fallaba
o estaba vacío. El contrato pasa a ser literal: **ESTUDIO es obligatorio para AUTO;
la allowlist solo intersecta; nunca lo sustituye.**

- **Hard gate en `_instruments_for_cycle`**: los cinco caminos que antes devolvían la
  allowlist (`resolver` ausente, excepción del resolver, `resolution is None`,
  `status != "ok"` —cubre `unavailable`/`empty`/desconocido— e `instrument_ids` vacío)
  ahora devuelven `()` ⇒ **no se opera**. El worker no muere: reintenta el ciclo
  siguiente (fail-closed, no fail-stop).
- **Allowlist como intersección pura**: con ESTUDIO `ok` y CSV configurado, el cálculo
  sigue siendo `ESTUDIO ∩ allowlist`; nunca `ESTUDIO falla → CSV se convierte en
universo`.
- **Sin vía de escape hermética**: el gate es estricto también cuando el orquestador no
  expone `resolve_universe` (antes los tests/dobles caían a la allowlist). Los dobles de
  test migran a un universo ESTUDIO real.
- **Documentación coherente**: se corrige la contradicción entre el docstring del worker
  ("`empty`/`unavailable` nunca inventa candidatas") y su comportamiento previo, y el
  comentario de `orchestrator_universe.py` deja de llamar a la allowlist "fallback".
- **Tests**: nuevos `test_unavailable_estudio_never_falls_back_to_allowlist`,
  `test_estudio_empty_never_falls_back_to_allowlist`,
  `test_estudio_error_never_falls_back_to_allowlist` y
  `test_loop_does_not_operate_when_estudio_unavailable_with_allowlist` (no se ejecuta
  ningún ciclo); se retiran los que certificaban el fallback.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`, LIVE bloqueado, sin LLM en hot path,
  fail-closed, long-only y gates CPCV/PBO/DSR/WFE/OOS + coach sin cambios. Sin
  migración (head Alembic sigue en `035_paper_forward_evidence`).
- **Elevación**: `main == 5348bee0` == tag **`v2.35.1-beta`**. Release-tag CI **GREEN
  verificado** (run [`34599471123`](https://github.com/jvelasca/Bolsa_V1/actions/runs/34599471123),
  conclusión `success`, 2026-09-11): `python` (ruff/imports/mypy/pytest offline),
  `lifecycle-pg`, `dr-verify`, `a7-gate`, `security`, `decision-spine`, `shared`,
  `frontend` y `playwright (mock E2E)` en verde.

### Deuda P2 de la auditoría v2.35-beta, resuelta en la misma versión

- **P2-01 — Promotion Gate automática separada de la admin/manual.** El override humano
  `shadow_validated` sale del API genérico: `decide_promotion`/`evaluate_promotion` son la
  vía **automática** (solo evidencia shadow ejecutada, sin parámetro de override) y
  `decide_admin_promotion`/`evaluate_admin_promotion` la **única** vía admin con override.
  Se elimina `OrchestratorDeps.shadow_override` y el parámetro `shadow_validated` de
  `run_cycle`. H1 intacto (`require_holdout=True` inviolable, sin escape hatch; sin
  `lab_end` no hay replay). El AUTO productivo nunca podía usar el override; ahora la
  frontera es explícita también en el tipo. Sin migración.
- **P2-02 — Contadores de ciclo separados de los de proceso.** Nuevo
  `CycleGrammarCounters` efímero (reiniciado al inicio de cada iteración) para que
  `cycle_summary` reporte **solo** el ciclo vigente; se añade `process_summary` con los
  acumulados desde el arranque del worker. `grammar_counters()` sigue devolviendo el
  acumulador de proceso (compatibilidad). Observabilidad pura: no altera ninguna decisión.
- **P2-03 — Allocator explícito de presupuesto del Discovery.** Nuevo
  `DiscoveryBudgetAllocator` (pesos por carril: catálogo / gramática simple / gramática
  compuesta / adaptive-placeholder) con reparto determinista por **resto mayor** y suelos
  por carril, que sustituye la reserva secuencial `_grammar_reserve` y elimina el sesgo de
  orden catálogo→gramática (el catálogo ya no puede dejar sin presupuesto a la gramática, ni
  al revés). Con gramática OFF la salida sigue siendo byte-idéntica a A13 (test de
  regresión). `adaptive` queda a peso 0 (placeholder; **no** implementa aprendizaje). Pesos
  configurables por env `AUTO_ORCHESTRATOR_ALLOCATOR_*`. Sin migración.
- **Integración**: el bump de P2-03 da cupo real a la gramática y destapó que
  `RunSmaGridOptimizeAndSave.execute` no reenviaba `grammar_variants` (A14 lo añadió al
  optimizador y a `_GRID_KEYS`, pero no al wrapper de persistencia) ⇒ corregido. Los tests
  A14 PG admiten además el corte honesto `sin_evidencia_top3` (fail-closed previo al gate
  shadow) ahora que la gramática ya no queda muerta.

## [1.60.0-beta] — V2.35 / A15 · Observabilidad y gobernanza de la gramática de Discovery — 2026-09-11

Hace **gobernable el rollout** de la gramática controlada de A14 (`AUTO_ORCHESTRATOR_GRAMMAR`,
OFF por defecto) sin cambiar ninguna semántica de decisión: ahora se mide cuánto aporta la
gramática frente al catálogo curado y cuántos planes llegan de verdad al LAB y al shadow.
Todo es **observabilidad de solo lectura** — no altera presupuestos, gates ni el reparto
catálogo↔gramática, y **no hay migración** (head Alembic sigue en
`035_paper_forward_evidence`).

- **Resumen determinista de emisión (`DiscoveryEmissionSummary`)**: nueva API aditiva
  `discover_for_instrument_with_summary(...)` en `strategy_discovery_engine.py` que devuelve
  `(candidatas, resumen)`. El resumen cuenta `catalog_candidates`, `grammar_candidates`,
  `total_candidates`, `trials_used`, los cupos reservados (`catalog_cap`/`grammar_cap`), el
  flag `grammar_enabled` y el warm-up (`bar_count_ok`). Se calcula sobre lo ya emitido (el
  prefijo `grammar:` es la fuente de verdad); **no añade estado al motor**.
- **API estable intacta**: `discover_for_instrument(...)` delega en la nueva función y
  descarta el resumen, de modo que con `grammar_budget=None` la salida es **byte-idéntica**
  a la de A13 (test de regresión explícito).
- **Procedencia en el orquestador**: `OrchestratorResult` gana campos aditivos de conteo
  (`catalog_candidates`, `grammar_candidates`, `lab_grammar_evaluated`, `shadow_started`,
  `shadow_grammar_started`) derivados de la evidencia real del ciclo (evaluaciones del LAB y
  replay shadow ejecutado). Sin provider de barras, `shadow_started` es 0 (fail-closed
  honesto: no se inventa evidencia).
- **Logs estructurados en el worker AUTO**: una línea de observabilidad por instrumento
  (procedencia, presupuesto y cupos) y un `cycle_summary` agregado por ciclo, más
  `GrammarObservabilityCounters` acumulados por proceso (`grammar_counters()` para
  inspección/tests). Solo `logging`: sin persistencia en DB.
- **Invariantes intactas**: `AUTO ⇒ SIMULATED`, LIVE bloqueado, sin LLM en hot path,
  fail-closed (ausencia de evidencia ≠ aprobación), long-only y gates CPCV/PBO/DSR/WFE/OOS
  - coach sin cambios.
- **Tests**: herméticos de resumen OFF/ON, cuadre catálogo+gramática=total, determinismo,
  warm-up y regresión A13 (`test_discovery_grammar.py`); contadores y `cycle_summary` del
  worker (`test_auto_orchestrator_worker.py`); procedencia LAB/shadow del orquestador
  (`test_auto_orchestrator.py`).

> Verificación: `ruff`, `lint-imports` (4/0), `mypy` (470 ficheros) verdes; job `quality`
> offline (1243 passed) y E2E PG de certificación (`grammar-discovery-pg`,
> `paper-forward-pg`, `lifecycle-pg`) sin skips.
>
> **Deuda preexistente que NO se toca aquí**: `packages/py/infrastructure/tests/chaos/
test_load_concurrency_flow.py` (fallos de carga preexistentes) y el flake ambiental de
> `test_a9_scheduler_process_pg_zero_human` sobre BD local sucia (documentado en el audit-pack
> de V2.32.1).

## [1.59.0-beta] — V2.34 / A14 · Strategy Intelligence (gramática controlada de Discovery) — 2026-09-11

Discovery deja de ser un catálogo de familias técnicas fijas y pasa a ser una **gramática
controlada**: una estrategia se compone de bloques funcionales (`REGIME` + `TREND FILTER`

- `MOMENTUM` + `ENTRY TRIGGER` + `EXIT`, con `TRIGGER`/`EXIT` obligatorios y máx. 2–3
  opcionales), acotada por un presupuesto determinista. **Sin segundo motor de trading ni
  segundo FSM**, **sin migración** (head Alembic sigue en `035_paper_forward_evidence`) y sin
  tocar las barreras LIVE.

* **Gramática controlada (`discovery_grammar.py`)**: vocabulario de bloques, variantes
  declaradas, vetos de redundancia y materialización a `StrategyDefinitionV1` con los
  helpers existentes. La composición es la **conjunción plana** de reglas
  (`operator="all"`), exactamente lo que el motor declarativo ya evalúa; no se añade
  sintaxis ni nesting al motor.
* **`GrammarBudget`**: envuelve `DiscoveryBudget` (un único presupuesto global por
  instrumento), acota `max_components ∈ [1, 3]` y `max_per_component_variant`, con
  enumeración determinista (cero azar, cero IA). El techo exacto queda fijado por test
  anti-explosión (1784 planes con el presupuesto por defecto).
* **Cierre del gap bloqueante de promoción**: la vía declarativa del LAB
  (`_run_cpcv`/`_run_walk_forward`) gana una rama que reutiliza `split_cpcv_paths` y
  `_simulate_rules_strategy`, produciendo **CPCV/PBO/DSR/WFE reales**. Antes de A14,
  `robustness`/`walk_forward` quedaban `NOT_EVALUATED` para toda familia declarativa y
  **ninguna candidata de Discovery podía promocionar**.
* **Grid gramatical**: cada candidata gramatical lleva variantes hermanas
  (`grammar_variants`) para que el LAB re-optimice de verdad y el PBO CSCV tenga columnas
  que rankear; la reserva de presupuesto garantiza que el catálogo no deja a la gramática
  sin candidatas.
* **Sanación de familias inertes**: se cablean en `_series_for_spec` los ids causales que
  faltaban (`roc`, `srsi`, `mom`, `wma`, `sd`, `obv`, `mfi`, `aroon`, `bears`, `bulls`,
  `sar` vía `compute_psar` con `maxAf`). Las plantillas `roc_momentum`,
  `stoch_rsi_reversion` y `sar_flip` del catálogo, que referenciaban ids no cableados
  (reglas silenciosamente inertes), ahora producen señales reales.
* **Propagación del campeón**: el `executable` promocionado se **re-materializa con los
  parámetros ganadores** del campeón (no con el punto plantilla de la candidata), evitando
  que shadow/forward repliquen parámetros obsoletos.
* **Rollout reversible**: la gramática está tras `AUTO_ORCHESTRATOR_GRAMMAR` (OFF por
  defecto); con OFF el Discovery es idéntico al de A13 (test de regresión).
* **Invariantes intactas**: H1 (`require_holdout=True` inviolable; fail-closed sin
  `lab_end`), H2 (identidad `instrument_id/timeframe/source/adjusted` en `bars_hash`) y las
  barreras LIVE (`AUTO ⇒ SIMULATED`; cero publicaciones al bridge real).
* **Tests**: herméticos de gramática/determinismo/techo/vetos/wiring/gates declarativos
  (entran en el job `quality`) y E2E PG `grammar-discovery-pg` (gate
  `A14_GRAMMAR_PG_REQUIRED=1`, fail-if-skipped; negativo fail-closed e invariante LIVE=0).

> Verificación: `ruff`, `lint-imports`, `mypy` verdes; job `quality` offline
> (`apps/api-python` 201/201, `packages/py` 2276/2278) y E2E PG de certificación
> (`grammar-discovery-pg`, `paper-forward-pg`, `lifecycle-pg`) sin skips.
>
> **Deuda preexistente que NO se toca aquí**: `packages/py/infrastructure/tests/chaos/
test_load_concurrency_flow.py` (2 fallos de carga preexistentes).

## [1.58.1-beta] — V2.32.1 · Hardening H1+H2 (hold-out inviolable + identidad de dataset) — 2026-09-11

Cierra los dos contratos que la auditoría V2.32.1 dejó pendientes y que se acordó **no**
mezclar con A13. Cambio de contrato, **sin migración** y sin tocar las barreras LIVE
(siguen doblemente bloqueadas).

- **H1 — `require_holdout=True` inviolable en la ruta de promoción**: el orquestador
  fuerza el hold-out estricto al construir el `ShadowReplayConfig` del shadow. El flag
  `OrchestratorDeps.shadow_require_holdout` **se elimina** (ya no existe vía de escape).
  Sin `lab_end` demostrable no se construye el replay (fail-closed en el orquestador,
  antes de invocar la fase). Ya no existe ninguna ruta de promoción que replique sin
  hold-out estricto ni sin frontera LAB.
- **H2 — identidad de dataset en el `bars_hash`**: `ShadowReplayConfig` y
  `PaperForwardConfig` ganan `instrument_id`/`timeframe`/`source`/`adjusted`, que se
  incorporan a la cabecera del hash en shadow y forward. Dos series con el mismo OHLCV
  pero distinto instrumento o marco temporal ya **no** comparten identidad de evidencia.
  Si el config no fija `instrument_id`, se cae al del finalista/ACTIVE (compatibilidad).
  Se mantiene la semántica «mismo dataset ⇒ mismo hash».
- **Wiring AUTO**: el worker puebla `instrument_id`/`timeframe`/`source` en la evidencia
  shadow y forward desde la lectura diaria del instrumento; `adjusted` no se inventa.
- **Tests**: orquestador (fuerza del hold-out, fail-closed sin `lab_end`) y fases shadow/
  forward (mismo OHLCV con distinta identidad ⇒ hash distinto; identidad estable).
- **Correcciones de arranque del CI (deuda preexistente saldada en esta release)**:
  - `alembic/env.py`: `fileConfig(..., disable_existing_loggers=False)`. Al correr Alembic
    **en proceso** (`ensure_migrated` en el bootstrap de workers y en tests PG), el default
    de `fileConfig` deshabilitaba los loggers de la app ya creados — silenciando el logging
    del proceso y rompiendo por orden `test_queue_poll_worker::test_run_con_arq_es_noop`.
  - `test_scheduler_worker`: el set esperado no incluía `start_auto_orchestrator` (A10).
  - `test_auto_scheduler_real_pg_zero_human_intervention`: la reconstrucción de equity
    llamaba a `reconstruct_accounting_from_state` sin `closed_pnl`, provocando un descuadre
    cuando el día cerraba con pérdida realizada (`cash` ya la incorporaba). Ahora deriva el
    P&L cerrado del libro de fills (`sim_fill_finance_context`) — fuente independiente del
    `cash`, invariante no tautológica.

> Verificación: `ruff`, `lint-imports`, `mypy` verdes; job `quality` offline
> (`apps/api-python` 201/201, `packages/py` 2276/2278) y E2E PG de certificación
> (`paper-forward-pg` / `lifecycle-pg`) en verde.
>
> **Deuda preexistente que NO se toca aquí** (ajena al hardening; falla igual en el baseline
> `5fcd0224`): `packages/py/infrastructure/tests/chaos/test_load_concurrency_flow.py` (2
> tests de carga 500+500; el invariante de orden por `(executed_at, id)` se rompe por empates
> de timestamp a alta concurrencia — el invariante contable Σ ledger == cash sí es correcto).
>
> **Compatibilidad de evidencia**: el `bars_hash` cambia de semántica (incluye identidad). La
> evidencia _shadow/forward_ persistida **antes** de este commit conserva su hash almacenado,
> pero no coincide con un recálculo bajo la nueva cabecera. No hay migración ni backfill (la
> evidencia histórica no se reescribe); el cambio afecta a la reproducibilidad de aquí en
> adelante.

## [1.58.0-beta] — V2.33 / A13 · Paper Forward (ACTIVE → forward P&L → vigilancia) — 2026-09-11

Cierra el salto que V2.32/A12 deja abierto: la evidencia de una estrategia deja de ser
solo **histórica** (shadow sobre un hold-out del LAB) y pasa a incluir **forward** real
sobre mercado nuevo posterior a la promoción. Sin dinero real, sin cambios en las
barreras LIVE (siguen doblemente bloqueadas) y sin tocar la ruta SIM-only.

- **Forward paper determinista**: nuevo `paper_forward_phase.run_paper_forward` que
  reutiliza el **mismo** motor declarativo de reglas que el LAB/shadow (causalidad
  `index-1 → open(index)`, sin look-ahead) pero sobre barras con timestamp
  **estrictamente posterior** a la promoción de la ACTIVE. No hay un segundo motor de
  trading: la definición ejecutable de la ACTIVE es la única fuente de señal.
- **Frontera temporal fail-closed**: sin barras nuevas post-promoción no hay evidencia
  (`forward_sin_barras`, `passed=False`); nunca se inventa un P&L forward.
- **Fingerprint reproducible**: dominio `PaperForwardResult` + `PaperForwardPolicy`
  (guarda de muestra en `min_closed_round_trips`, DD fail-closed) con
  `forward_start`/`forward_end`/`bars_hash`/`strategy_definition_hash`/`engine_version`/
  `config_hash`/`data_snapshot_id`/`promoted_at`.
- **Persistencia**: migración **035** (`paper_forward_results`, aditiva y nullable, sin
  backfill) + `save_forward_result`/`list_forward_results` en el store (InMemory y
  Postgres). La evidencia queda atribuida a la `version_id` de la ACTIVE.
- **Wiring AUTO (default OFF)**: `AUTO_ORCHESTRATOR_FORWARD=1` activa el forward tras
  cada ciclo y antes de la vigilancia (`AUTO_ORCHESTRATOR_FORWARD_WINDOW_BARS`, default
  400). Con OFF el comportamiento es idéntico a V2.32.1 (rollout reversible).
- **Certificación PG por commit**: nuevo job `paper-forward-pg` en `python-ci.yml` que
  aplica `alembic upgrade head` (hasta 035) y ejecuta el E2E A13 con
  `PAPER_FORWARD_PG_REQUIRED=1` (un skip es fallo duro). El E2E certifica
  ACTIVE → barras nuevas → señal → fills/round-trips → P&L → evidencia persistida →
  vigilancia, y el caso negativo sin barras nuevas.

> Cierre: `docs/engineering/cierre-v2.33-a13-paper-forward-2026-09-11.md`.

## [1.57.0-beta] — V2.32.1 / A12.1 · Audit Remediation (P1 + promotion-hardening P2) — 2026-09-11

Remedia los hallazgos verificados de la auditoría V2.32 contra HEAD `854dc86`, sin
cambios de arquitectura ni en las barreras LIVE (siguen doblemente bloqueadas) y sin
tocar la ruta SIM-only. Endurece la honestidad estadística y la certificación continua.

- **P1-01 — Hold-out estricto LAB/shadow**: la ventana del shadow ya no se solapa con la
  del LAB. El orquestador resuelve el corte (`lab_end`), lo inyecta en las candidatas
  (`date_to`) y el replay parte las barras en LAB vs hold-out estricto
  (`split_holdout`), con _fail-closed_ (`shadow_solape_lab` /
  `shadow_barras_holdout_insuficientes`). El worker lee `bar_limit + shadow_window`
  barras para que exista un hold-out real posterior.
- **P1-02 — E2E PG por commit**: nuevo job `lifecycle-pg` en `python-ci.yml` que arranca
  `postgres:16`, aplica `alembic upgrade head` (032/033/034) y ejecuta la suite A12
  crítica con gates `*_PG_REQUIRED=1` (un skip es fallo duro). El E2E
  `test_a11_discovery_to_auto_sim_pg.py` deja de estar `--ignore` d en la certificación.
- **P1-02 — E2E determinista (sin SKIPPED)**: dataset sembrado que produce un cruce SMA
  real en la última barra ⇒ `ACTIVE → SIGNAL → SIM BUY → FILL` certificado como
  aserción dura. Se corrige además un fallo preexistente de lectura de gates
  (`walkForwardEfficiency`/`dsr` anidados en `edge_report["suite"]`) que dejaba
  `robustness`/`walk_forward`/`dsr` en `NOT_EVALUATED` e impedía promocionar.
- **P2-01 — Drawdown fail-closed**: `ShadowPolicy.evaluate` falla cerrado si
  `max_drawdown_pct` está configurado y la métrica es `None` (`shadow_drawdown_ausente`).
- **P2-02 — Sin override en AUTO**: se elimina `shadow_validated`/`shadow_override` de la
  ruta AUTO real; la promoción en AUTO es solo por evidencia. El parámetro se mantiene
  para llamadas manuales/admin/test.
- **P2-03 — Fingerprint del dataset shadow**: migración **034**
  (`round_trips`, `data_snapshot_id`, `shadow_start`, `shadow_end`, `bars_hash`,
  `strategy_definition_hash`, `engine_version`, `config_hash`, `lab_end`), todas
  nullable y sin backfill (la ausencia de evidencia no se inventa).
- **P2-04 — Semántica de round-trips**: la guarda de muestra es `min_closed_round_trips`
  (operaciones cerradas), no piernas ejecutadas.
- **P2-05 — Identidad por ciclo**: `run_id` por ciclo (`orchestrator:{instrument}:{ts}-{rnd}`)
  en vez de constante, para distinguir retries/re-LAB/shadow.
- **Auditoría 2a — `can_transition` fail-closed**: transicionar sin gates evaluados se
  bloquea (`gates_no_evaluados`) en vez de permitirse.
- **Auditoría 2b — `HealthThresholds` predictivos**: `min_edge`/`min_wfe`/`min_dsr`/
  `min_credibility` pasan a `None` por defecto (sin fabricar un `0.0`); la vigilancia
  solo degrada con umbrales calibrados.

> Cierre: `docs/engineering/cierre-v2.32.1-a12.1-remediacion-auditoria-2026-09-11.md`.

## [1.56.0-beta] — V2.32 / A12 · Shadow Validation & Autonomous Attribution — 2026-09-11

Cierra los **dos P2 diferidos a V2.32** por la auditoría V2.31. Sin cambios en las
barreras LIVE (siguen doblemente bloqueadas) ni en la ruta SIM-only.

- **Shadow real (evidencia ejecutada, no flag)**: nuevo `strategy_shadow_phase.py`
  (`run_shadow_replay`) que ejecuta la definición del finalista con el motor real de
  reglas sobre una ventana separada del LAB. Dominio: `ShadowValidationResult` +
  `ShadowPolicy`; `evaluate_promotion` pasa a exigir evidencia (`shadow=...`) y la
  ACTIVE queda enlazada a `shadow_validation_id`. `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`
  deja de ser autoridad y pasa a **override explícito** del operador.
- **Persistencia**: migración **032** `strategy_shadow_validations` +
  `strategy_promotions.shadow_validation_id`; `save_shadow_result`/`list_shadow_results`.
  El marcador engañoso de `save_active` (escribía `shadow_validated=True` sin evidencia)
  queda corregido.
- **Atribución post-crash**: migración **033** (`sim_auto_positions.strategy_version_id` +
  `ledger_entries.strategy_version_id`). `readopt_positions` restaura la versión ⇒ los
  cierres readoptados vuelven a atribuirse; el ledger recibe la versión por
  `ExecuteTrade.execute(..., strategy_version_id=...)` (aditivo, sin tocar importes).
- **E2E A11 en PG**: nuevo `test_a11_discovery_to_auto_sim_pg.py`
  (DISCOVERY → SHADOW → PROMOTION → ACTIVE → SIM → LEDGER → VIGILANCIA + caso negativo
  sin evidencia + readopt con atribución), en el job `lifecycle-pg`.
- **CI simétrico**: discovery + shadow añadidos también a `python-ci.yml` (el job diario
  no los listaba).

> Cierre: `docs/engineering/cierre-v2.32-a12-shadow-attribution-2026-09-11.md`.

## [1.55.0-beta] — V2.31 / A11 · Intelligent Strategy Discovery — 2026-09-10

Cierra los **dos P1** de la auditoría V2.30. Sin cambios en las barreras LIVE (siguen
doblemente bloqueadas) ni en la ruta SIM-only.

- **P1-01 — `StrategyDiscoveryEngine`**: nuevo search space **curado y acotado** sobre los
  33 `definitionId` reales de `bolsa_analytics.indicators` (antes solo 3 familias fijas:
  SMA/RSI/MACD). `discovery_catalog.py` declara 14 plantillas en tres ramas
  (trend / momentum / volatility) con parámetros pequeños; `strategy_discovery_engine.py`
  emite candidatas **deterministas** con presupuesto global (`DiscoveryBudget`).
- **LAB declarativo**: `run_rules_grid_search` evalúa las plantillas con el motor real de
  reglas (`evaluate_rules_signals`, gated, sin look-ahead); `RunSmaGridOptimize.execute`
  acepta `definition=` y despacha a `rules_grid_h0` sin colapsar la familia a SMA/RSI/MACD.
  `LabOptimizeRunner` propaga la definición.
- **Orquestación**: `OrchestratorDeps.discovery` + flag `AUTO_ORCHESTRATOR_DISCOVERY`
  (default OFF) con presupuesto por env. Discovery vacío ⇒
  `status="sin_candidatas_discovery"` (fail-closed: no se inventa la candidata única).
- **P1-02 — ACTIVE fail-closed (NO TRADE)**: se elimina el fallback al spine en
  `active_strategy_signal_evaluator.py`. Sin señal evaluable (sin `executable`, sin barras,
  fuera de `watch`, error) ⇒ `HOLD`; el único camino a BUY/SELL es la señal propia de la
  estrategia promocionada. La procedencia real deja de ser invisible.
- **Sin migraciones nuevas**: catálogo y motor son puros; el discovery reutiliza
  `strategy_candidates`.

> Cierre: `docs/engineering/cierre-v2.31-a11-discovery-engine-2026-09-10.md`.

> **Diferido a V2.32 (deuda de producto):** shadow real (evidencia ejecutada en vez del
> flag `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`) y atribución de versión tras crash en
> posiciones readoptadas.

## [1.54.0-beta] — V2.30 / A10 · Higiene auditable (CI que ejecuta lo que certifica) — 2026-09-10

Cierra la **deuda de higiene** que impedía una auditoría limpia en GitHub. Sin cambios
de comportamiento de producto: el núcleo de decisión A10 y el LIVE real quedan igual.

- **Guardias de head de Alembic derivadas** (causa raíz): nuevo `alembic_head()` en
  `bolsa_infrastructure.database.migrations`, que lee la head del filesystem de
  migraciones (no se hardcodea). Sustituye las guardias que había que parchear a mano
  en cada migración (`029→030`, `030→031`, ...).
- **Drift de 27 migraciones corregido**: `test_f3b_alembic_data_epoch` y
  `test_ledger_entries_reference_unique` seguían anclados a `004_ledger_reference_unique`
  y **no se ejecutaban en ningún job** — el CI daba verde sobre tests que no corrían.
- **Test de concurrencia PG hermético**: `test_live_order_recovery_concurrency_pg`
  commiteaba filas y no limpiaba, envenenando la suite entre pasadas. Ahora purga por
  `account_id` en `finally`.
- **Hueco de CI cerrado**: 7 tests PG que estaban fuera de todos los jobs se incorporan
  al job `lifecycle-pg` con gates fail-if-skipped (`LIVE_PG_REQUIRED`, `E2_PG_REQUIRED`,
  `EXECUTION_FENCE_PG_REQUIRED`); el job `python` los ignora explícitamente.
- **Marcador shadow documentado**: `shadow_validated=True` en `save_active` es un
  localizador de la activa, no evidencia de validación (aclarado en código).

> Cierre: `docs/engineering/cierre-v2.30-higiene-auditable-2026-09-10.md`.

> **Diferido a V2.31 (deuda de producto):** `StrategyDiscoveryEngine` (selector sobre
> los 30+ indicadores), shadow automático (evidencia ejecutada en vez del flag
> `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`) y atribución de versión tras crash en posiciones
> readoptadas.

## [1.53.0-beta] — V2.27 + V2.28 + V2.29 / A10 · Cierre del núcleo de decisión — 2026-09-10

Cierra los P2 del A10 que tocaban el **núcleo de decisión**, acumulados desde V2.26:

- **V2.27 — Wiring real**: el universo ESTUDIO y el LAB (`RunSmaGridOptimizeAndSave`) se
  cablean en la composición real (`_default_orchestrator`), sin inyectar dependencias.
- **V2.28 — Vigilancia real**: `sim_fill_finance_context` gana `strategy_version_id`
  (Alembic `031_sim_fill_strategy_attr`) y la vigilancia calcula métricas observadas
  (PnL, drawdown, win rate, profit factor) desde fills SIM atribuidos a la versión.
- **V2.29 — COACH comparativo + SignalEvaluator real**: el COACH dictamina el TOP3 entero
  (eligiendo el primer candidato sin veto, sin reordenar la evidencia); la versión
  promocionada persiste los **parámetros del campeón** y su **definición ejecutable**; y
  la estrategia ACTIVE puede evaluar **su propia señal** sobre barras reales
  (`AUTO_ENGINE_SIM_ACTIVE_STRATEGY_SIGNAL`, default OFF ⇒ se conserva el spine).

AUTO sigue **estrictamente SIMULATED**; **LIVE real intacto**. La vigilancia observada
está separada de las métricas predictivas (`edge`/`wfe`/`dsr`) y usa una guarda de
muestra mínima para no degradar por ruido.

> Cierres: `docs/engineering/cierre-v2.27-a10-real-wiring-2026-09-10.md`,
> `cierre-v2.28-vigilancia-real-2026-09-10.md`,
> `cierre-v2.29-coach-comparativo-signal-real-2026-09-10.md`.

> **Diferido a V2.30:** `StrategyDiscoveryEngine` (selector sobre los 30+ indicadores),
> shadow automático (evidencia ejecutada en vez del flag `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`)
> y atribución de versión tras crash en posiciones readoptadas.

## [1.52.0-beta] — V2.25 + V2.26 / A10 · Strategy Lifecycle + Auto Orchestrator — 2026-09-10

Construye el **ciclo de vida autónomo de estrategia (A10)** sobre la infraestructura
LAB/optimización/OOS ya existente y lo cablea al AUTO **exclusivamente** por el seam
`DecisionProvider`. Núcleo financiero LIVE congelado; **LIVE real sigue doblemente
bloqueado** y AUTO es **estrictamente SIMULATED**.

> **Nota de reciclaje de nombres:** los identificadores **V2.25** y **V2.26** se usaron
> el 4-sep-2026 para _polish_ de UI (docs de `docs/engineering/`). Aquí se **reutilizan**
> con el significado canónico del plan A10: **V2.25 = Strategy Lifecycle** y
> **V2.26 = Auto Orchestrator**. Las referencias antiguas a V2.25/V2.26 de UI quedan
> superadas por esta entrada.

### V2.25 — Strategy Lifecycle (A10)

- **Dominio** (`bolsa_domain/entities/strategy_lifecycle.py`): `StrategyCandidate`,
  `StrategyEvaluation`, `StrategyFinalist`/`StrategyVersion` (inmutable, hash de
  definición), `StrategyPromotion`, `ActiveStrategy`, `StrategyHealth` y la máquina de
  estados `StrategyLifecycleState` con transiciones fail-closed (un gate previo debe
  PASS; el COACH **solo veta/degrada**, nunca aprueba por encima de los gates).
- **Persistencia** (Alembic **`030_strategy_lifecycle`**, head pasa de `029`): tablas
  `strategy_candidates`, `strategy_versions`, `strategy_evaluations`,
  `strategy_promotions`, `strategy_health_snapshots`. Reutiliza `strategy_definitions`,
  `research_trials`, `research_evidence` y `edge_reports` como evidencia enlazada (no
  duplica). Store: `InMemoryStrategyLifecycleStore` (hermético) y
  `PostgresStrategyLifecycleStore` (PG).
- **Fases** (módulos de aplicación, reutilizando el LAB existente):
  - **ESTUDIO/LABORATORIO** (`strategy_lab_phase.py`): universo reproducible con
    `data_snapshot_id` sellado; `evaluate_optimize_result` traduce
    `RunSmaGridOptimize` (holdout/WF/CPCV/PBO) a `StrategyEvaluation` con gates.
  - **TOP 3 / COACH** (`strategy_top3_coach_phase.py`): selección por evidencia (score +
    gates + PBO) y `assess_with_coach` determinista y _advisory_ (veta, no promociona).
  - **FINALISTA + Promotion Gate** (`strategy_promotion_phase.py`): `StrategyVersion`
    inmutable y `decide_promotion` con los seis gates (`backtest`, `robustness`,
    `walk_forward`, `oos`, `risk`, `coach`) + coach + **shadow validation**; reglas
    anti-strategy-chasing (el LAB no sustituye la activa sin promoción).
  - **Vigilancia** (`strategy_vigilance_phase.py`): `evaluate_active_health` compara
    edge/WFE/DSR/credibilidad con umbrales; la degradación ⇒ **re-LAB** (nunca swap).
- **API**: `GET /research/strategy/{version_id}/health` expone estado e histórico de
  salud de la estrategia activa (DTOs en `schemas/research.py`).

### V2.26 — Auto Orchestrator (A10)

- **`auto_orchestrator.py`**: ciclo completo
  ESTUDIO→LAB→TOP3→COACH→FINALISTA→VALIDACIÓN→PROMOCIÓN→ACTIVE→vigilancia, determinista
  e inyectable. Sin shadow no promociona; sin evidencia, no hay TOP3; el COACH puede
  vetar.
- **Worker** (`background/auto_orchestrator_worker.py`, registrado en
  `scheduler_worker.py`): bucle env-gated **default OFF** —
  `AUTO_ORCHESTRATOR_ENABLED`, `AUTO_ORCHESTRATOR_INSTRUMENTS`,
  `AUTO_ORCHESTRATOR_INTERVAL_SECONDS`, `AUTO_ORCHESTRATOR_SHADOW_VALIDATED`.
- **Seam ACTIVE→AUTO**: `active_strategy_decider` traduce la estrategia activa a un
  `DecisionProvider`. El worker AUTO lo instala vía `AutoSimRuntime.set_decider` cuando
  `AUTO_ENGINE_SIM_ACTIVE_STRATEGY=1` (**default OFF**). No se toca RiskGate ni
  SimulationGate y **no se abre LIVE**; sin activa fiable se conserva el spine
  determinista.

### Gates CI

- `python-ci.yml` / `release-tag-ci.yml`: entran al pytest offline los tests herméticos
  de las fases A10 + orquestador (`test_strategy_*_phase.py`, `test_auto_orchestrator.py`,
  `test_sim_durable_unit_of_work.py`).
- `release-tag-ci.yml > lifecycle-pg`: nuevo **`AUTO_ORCHESTRATOR_PG_REQUIRED=1`** y el
  test `test_auto_orchestrator_full_cycle_pg` sobre el store Postgres real (promoción con
  shadow y degradación→re-LAB). Un skip silencioso es fallo duro.

## [1.51.1-beta] — V2.24.2 / A9.1-hardening — P2 residuales (equity real, UoW, recon global, restart) — 2026-09-10

Endurecimiento de la certificación V2.24/A9.1 (run `34470214388`, GREEN) cerrando los
**P2 residuales** señalados por la auditoría externa. Sin features de trading nuevas;
núcleo financiero LIVE congelado y **LIVE real sigue doblemente bloqueado**.

### Qué cambia

- **P2-A — equity invariant REAL:** `reconstruct_accounting_from_state` reconstruye el
  `LifecycleAccounting` desde las filas reales del ledger (depósitos/compras/ventas/fees),
  coste medio y precio actual. El test de la Reina por proceso ya no pasa
  `last_price=0`/`realized_pnl=0` (invariante tautológica): ahora `total_equity ==
initial + realized + unrealized` es una afirmación financiera no degenerada.
- **P2-B — unidad-de-trabajo proyección + finance:** `SimDurableUnitOfWork` y el flag
  `autocommit=False` en `PostgresSimFillFinanceContextStore`/`PostgresSimAutoPositionStore`
  permiten componer ambos espejos en UNA transacción. El commit autónomo sigue siendo
  el default (durabilidad-e-idempotencia intacta); la proyección no cambia de naturaleza
  (sigue siendo reconstruible, P1-01).
- **P2-C — reconciliación GLOBAL de cuenta:** `reconcile_sim_account` agrega todos los
  símbolos (unión eventos/canónico/proyección) y detecta posiciones fantasma solo en la
  proyección; cualquier `DIVERGENT`/`UNKNOWN` bloquea aperturas en toda la cuenta
  (fail-closed). El worker expone `reconciliation_status` y
  `reconciliation_blocks_openings`.
- **P2-D — restart con posición/protección abierta:** nuevo test PG-gated que arranca el
  proceso real `scheduler_worker`, lo mata con la posición abierta y lo reinicia sobre la
  misma BD: el proceso readopta la posición durable y **NO re-compra** (los BUY no se
  doblan). Retén del spine parametrizable por `AUTO_ENGINE_SIM_EXIT_AFTER_TICKS` para
  poder certificar el escenario.

### Gates CI

- `lifecycle-pg` añade `AUTO_SCHEDULER_RESTART_PG_REQUIRED=1`; el test de restart corre en
  `apps/api-python/tests/test_a9_scheduler_process_pg_zero_human.py` (un skip sin PG sigue
  siendo fallo duro con los gates activos).

## [1.51.0-beta] — V2.24-beta / A9.1 · Durable Autonomous Simulation Integrity — 2026-09-10

Cierre de los **4 P1 de durabilidad/aislamiento** que la auditoría V2.23 detectó en
el AUTO SIM-ONLY, más el endurecimiento de los P2 de integridad y la primera
**Reina real** (proceso scheduler, no `run_turn` manual). El núcleo financiero sigue
congelado y **LIVE real continúa doblemente bloqueado** (`LIVE_EXECUTION_AUTHORIZED`

- `LIVE_EXECUTION_UNLOCKED`, false por defecto e independientes).

### ¿Qué cambia?

- **P1-01 — proyección, no autoridad:** `sim_auto_positions` pasa a ser un espejo de
  recuperación **reconstruible** desde el estado financiero canónico. Una proyección
  no puede autorizar por sí sola una compra; ante divergencia se reconstruye y, si no
  hay datos, se vetan aperturas (fail-closed).
- **P1-02 — aislamiento por cuenta:** migración `029_sim_auto_positions_account_scope`
  añade `account_id` a `sim_auto_positions` y rehace la PK a
  `(account_id, engine_id, symbol)`. Dos cuentas con el mismo engine/símbolo ya no
  colisionan en la misma fila.
- **P1-03 — identidad de ejecución namespaceada:** `venue_order_id` incorpora
  `engine_id` + `account_id` + `logical_order_id` único por intención
  (`auto_venue_order_id`). Dos cuentas no pueden compartir `execution_id`. La
  aleatoriedad del book deja de depender de la identidad del order (solo del contexto
  de mercado).
- **P1-04 — cuenta obligatoria:** sin `AUTO_ENGINE_SIM_ACCOUNT_ID` inequívoco el
  motor AUTO **no arranca** (fail-closed) y `auto_turn` veta con
  `account_id_required`; nunca una traza con `account_id=None`.
- **P2-01 — estado de protección durable:** la proyección persiste
  `entry_price`/`high_watermark`/`stop_price`/`t1_state`/`trailing_state`; tras un
  crash el worker readoptado no olvida el máximo (trailing correcto).
- **P2-02 — reconciliación SIM:** nuevo `sim_reconciliation.reconcile_sim_position`
  exige `ExecutionEvents == posición canónica == proyección`
  (`OK`/`REBUILT`/`DIVERGENT`/`UNKNOWN`).
- **P2-03 — batería de crash:** escenarios C3-F/G/H/I sobre las nuevas ventanas
  (finance/sim_position/journal/contexto/readopt).
- **P2-04 — Reina real:** test que arranca `python -m bolsa_api.workers.scheduler_worker`
  como proceso real con el spine determinista (sin `run_tick()` manual ni decider
  scripteado) e intervalo parametrizable por `AUTO_ENGINE_SIM_INTERVAL_SECONDS`.
- **P2-05 — invariante de equity:** el día AUTO se certifica con
  `assert_equity_invariant` sobre el ledger real (nuevo gate CI
  `AUTO_EQUITY_INVARIANT_PG_REQUIRED`).
- **P2-06 — honestidad de etiquetas:** `ProtectionConfig.exit_reason` evalúa el
  trailing antes que T1 cuando el máximo rebasó T1 (no etiqueta un trailing real como
  toma en T1); T1 **parcial** (`AUTO_ENGINE_SIM_T1_FRACTION`); `AutoDecisionEngine`
  lleva la edad **por símbolo** (no un contador compartido), de modo que
  `exit_after_ticks` es comparable entre watches de distinto tamaño.

### Estado

AUTO SIM-ONLY end-to-end con durabilidad/aislamiento cerrados. La siguiente capa
(ESTUDIO→LAB→COACH autónomo) es A10.

## [1.50.0-beta] — V2.23-beta / A9 · AUTO SIM-ONLY end-to-end — 2026-09-09

Composición real scheduler → `AutoSimRuntime` (stores PG + finanzas SIM por sesión),
Decision Spine determinista, RiskGate/SimulationGate en el camino AUTO, kill switch
fail-closed, posición durable básica (migración 028), protección SL/T1/trailing
inicial, journal tri-estado (`NOT_CHECKED` ≠ PASS) y gates PG fail-if-skipped.

## [1.49.0-beta] — V2.20-beta / A7 Iter-3 · hardening — 2026-09-09

Elevación de **hardening (Iter-3 de LIVE Certification / A7)** que cierra la
verificación **P1-01 — CAS no atómico** en `PostgresExecutionEventStore`
(`start_apply` no era un Compare-And-Swap real) y los huecos de concurrency /
recuperación que abría (dos-worker, C3-E, reaper de `APPLYING` stale,
contrato de cantidad en parciales, identidad de release). Núcleo financiero
congelado **intacto**: no añade features de trading.

### ¿Qué cambia?

- **P1-01 — CAS real atómico:** `PostgresExecutionEventStore.start_apply` /
  `mark_*` / `reclaim_stale_apply` pasan a un ÚNICO `UPDATE ... WHERE
execution_id AND status IN (orígenes-legales)` atómico con `rowcount`, sin la
  secuencia `SELECT → check-in-memory → ORM-mutate → commit`. `start_apply`
  incrementa `attempt_count` solo cuando gana y **NO acepta** el auto-origen
  `APPLYING` (`_cas_sources_of`), de modo que dos workers sobre el MISMO
  `CAPTURED` → exactamente uno `True` (`winner=1`) y otro `False` (`loser=0`).
- **Diseño single-owner por lease (1b):** migrate `025_execution_events_lease`
  añade `lease_owner` + `updated_at` a `execution_events` y un índice
  `(status, updated_at)`; un `APPLYING` huérfano (dueño caído, lease vencida)
  solo se retoma vía `reclaim_stale_apply` / `reclaim_stale_applying_batch`
  (reaper).
- **C3-E — crash tras commit financiero:** nueva escenario de la batería
  `live_a7` (worker SIGKILLeado tras `ExecuteTrade COMMIT` pero antes de
  `mark_applied`) → la traza queda `APPLYING` con dinero durable y la
  recuperación lo retoma por lease **sin segundo efecto** (`APPLIED`, no doble
  `ledger/position`).
- **Two-worker real-PG test:** `test_v220_two_workers_cas_exactly_one_owner`
  en `live_a7` demuestra sobre Postgres real que una sola de dos pasadas
  simultáneas de `start_apply` gana (`winner=1, loser=0`).
- **P2-02 — reaper de `APPLYING` stale (mecanismo + orquestador):**
  `reclaim_stale_applying_batch` (barrido atómico por lease vencido / dueño
  muerto) + orquestador `reap_stale_applying`: sobre un dueño garantizado-muerto
  lleva `APPLYING → APPLIED` (apply idempotente, UNA materialización) o a
  `RETRY` honesto cuando el candidato no es aún re-derivable, sin robar un
  `APPLYING` de lease VIVA. **Decisión safe-by-default (V2.20):** el substrato de
  lease + escenario real-PG se entregan verificados, pero **NO** se auto-enciende
  un sweep de fondo en el worker — reclamar por mera edad a un apply en curso
  (que no hace heartbeat entre `start_apply` y su `mark_applied`) podría robarle
  el APPLYING a un dueño vivo (lost-/double-apply). Cerrar la gestión automática
  plena requiere lease-renewal/heartbeat per-apply (Iter-4).
- **P2-03 — contrato de cantidad en parciales:** `filled_quantity` documentado
  y testeado como **delta por `fill_seq`** (no cumulativo): `40+30+30=100` son
  3 trazas idempotentes y suman el total. Sin cambio de comportamiento en
  espera del ruling del broker (puente XTB cumulativo-vs-delta sin confirmar).
- **P2-04 — identidad de release:** package `1.48.0-beta → 1.49.0-beta`.

### Verificación

- **Live (Postgres real dedicado):** la batería `apps/api-python/tests/chaos/live_a7`
  validada de nuevo con las semánticas de lease — **7 escenarios passed**:
  C3-A/B/C/D/E + `test_v220_two_workers_cas_exactly_one_owner`
  - `test_v220_stale_reaper_converges_orphaned_apply` (reaper real-PG).
- Ruff `apps/api-python packages/py` → limpio en los ficheros tocados. Suita
  unitaria de dominio (`test_execution_event.py` incl. los 2 nuevos de reaper,
  `test_recovery_apply.py` con el contrato `40+30+30`) → sin regresiones.

## [1.48.0-beta] — V2.18 / A7 Iter-1 · C3 — 2026-09-09

Elevación (completada: **Release-tag CI `#34341628713` GREEN** sobre `v2.18-beta` `conclusion: success`,
certify ✓, tag remoto en `bd2bd163`) de la **Iter-1 de LIVE Certification / A7**, **gated exclusivamente
al gap C3** (crash-injection): una batería **real-PG** de crash de **proceso real** sobre el worker de
recovery/scheduler que cierra el hueco que la Iter-0 (V2.17) dejó mapeado como 🔴.
Núcleo financiero congelado **intacto** (Alembic head `023_ohlcv_bars_unique_reconcile`, sin migración).
Como se decidió en V2.18 (`fsm_only`), C3 valida invariantes de **order-state/FSM** (≈ una resolución exacta,
sin doble transición ni doble materialización) y **NO** cash/position: la vertiente financiera del crash queda
reservada a Iter-2 bajo el roadmap XL-3 (A3/B2/P2-01 son los puentes hacia ella).

### ¿Qué cambia?

- **Home real-PG C3:** `apps/api-python/tests/chaos/live_a7/` con `test_c3_crash_injection_recovery_worker.py`
  (escenarios A/B) y harness de proceso `_crash_recovery_probe.py`. La batería lanza un **subproceso Python
  real** que reclama y resuelve UNKNOWN sobre `PostgresLiveOrderStore` + `live_order_recovery_worker.resolve_one_unknown`
  (el núcleo no se toca): en C3-A el proceso A es **SIGKILLeado con el claim FOR UPDATE en vivo** y un segundo
  proceso reaparece y resuelve **exactamente una vez**; en C3-B relanzar la recuperación tras un resolve durable
  no duplica (idempotencia del `put` + terminal-not-UNKNOWN). Falla-quieto → `financial_apply_count=0` en ambos.
- **CI:** job **`a7-gate`** en `.github/workflows/release-tag-ci.yml` — Postgres service + BD dedicada
  `bolsa_v1_a7` (drop+create, esquema a head por `ensure_migrated` idempotente en la propia batería) + pytest
  `chaos/live_a7` con `LIVE_A7_PG_REQUIRED=1` (fail duro si skip). `a7-gate` se suma a `needs` de `certify` y al
  resumen del artefacto.
- El job offline `python` (tag y `python-ci.yml`) y `lifecycle-pg`/iso quedan intactos; se añade
  `--ignore=.../chaos/live_a7` al pytest offline para mantenerlo hermético (A7 corre en `a7-gate`).

### Verificación

- **Elevación en GitHub:** **Release-tag CI `#34341628713` GREEN** sobre el tag remoto `v2.18-beta`
  (`conclusion: success`; `origin/main` en `bd2bd163`, sin ahead/behind). Jobs: `security (gitleaks)` ✓ ·
  `shared` ✓ · `decision-spine` ✓ · `python (ruff/imports/mypy/pytest offline)` ✓ · `frontend` ✓ ·
  `playwright (mock E2E)` ✓ · `dr-verify` ✓ · `lifecycle-pg` ✓ · [`a7-gate` (dedicated real-PG)] ✓ ·
  `certify (aggregate + artifact)` ✓. `playwright (integrated E2E)` skipped (opt-in, correcto para GREEN).
- Live (Postgres real dedicado): `apps/api-python/tests/chaos/live_a7` → **2 passed** (C3-A y C3-B) tanto en
  primera ejecución (migrando de cero) como en repetición.
- Ruff `apps/api-python packages/py` → limpio. Suites unitarias de worker:
  `test_live_order_recovery_worker.py` + `test_scheduler_worker.py` → **12 passed**.
- Relevo del ciclo (nuevo): `docs/engineering/traspaso-relevo-a7-iter1-c3-v2-18-beta-2026-09-09.md`;
  estado C3 actualizado en `docs/engineering/plan-a7-live-certification-gap-map-2026-09-09.md` (§1-ter/§3/§4/§5).

## [1.47.0-beta] — 2026-09-09

Elevación a `main` de la **Iter-0 de LIVE Certification / A7** (ciclo `v2.17-beta`), de acuerdo con el
veredicto de la **auditoría externa de V2.16.1**: P0=0 / P1=0 / Global 9.3 → abrir A7 y **no añadir
features**. Esta iteración es **SÓLO marco y mapa de gaps documental** (sin código ni tests nuevos):
mapea los 16 escenarios de certificación del auditor contra la cobertura ya existente y registra el home
futuro de la batería. Núcleo financiero congelado **intacto**. Alembic head `023_ohlcv_bars_unique_reconcile`.
Package **`1.47.0-beta`** (bump desde `1.46.1-beta`).

### Iter-0 A7 — entregable documental

- **Marco + gap-map:** [`docs/engineering/plan-a7-live-certification-gap-map-2026-09-09.md`](./docs/engineering/plan-a7-live-certification-gap-map-2026-09-09.md)
  — escenario a escenario (`🟢/🟡/🔴`) con evidencia ruta:línea y dobles a reutilizar.
- **Hallazgo P2-05 cerrado:** la incoherencia documental que marcó la auditoría (doc de relevo aún decía
  "sin push") ya fue resuelta por `b8858c2f` (SHA `1596f4ad`, tag `v2.16.1-beta`, CI `#34331846887` GREEN).
- **Home de la batería (Iter-1):** `packages/py/infrastructure/tests/chaos/live_a7/` (PG-real) con gate en
  el job `lifecycle-pg` del release-tag CI.
- **Backlog A7 (Iter-1+):** C3 crash-injection sobre `scheduler_worker` 🔴; A3 broker timeout/network
  real; B2 partial-fill → materialización; P2-01 Applied durable (APPLYING/APPLIED/FAILED).
- Deuda P3 C2 del núcleo sigue ACCEPTED sin tocar; la deuda pos-p3 `[runtime/aislamiento] LIVE A7` pasa a
  "Iter-0 en curso → Iter-1 backlog" (actualizado en `deuda-p3-nucleo-aceptada-c2-2026-09-09.md`).

### Verificación

Sin cambios de código: **Release-tag CI `#34334824584` GREEN** sobre `v2.17-beta` (`conclusion: success`,
certify ✓), tag remoto apuntando a `79df594c`. Relevo del ciclo:
[`docs/engineering/traspaso-relevo-a7-iter0-v2-17-beta-2026-09-09.md`](./docs/engineering/traspaso-relevo-a7-iter0-v2-17-beta-2026-09-09.md).

## [1.46.1-beta] — 2026-09-09

Elevación a `main` (tag **`v2.16.1-beta`**, commit `1596f4ad`, push a `origin/main`) del ciclo de
cierre de hallazgos residuales de la auditoría sobre `v2.16-beta`: owner-scoping de cuenta por
defecto (**P1-02/03**), **Auditoría 2** (fill_unseen tapado por cancel en el incidente `live_drift`) y
**Auditoría 3** (consentimiento del operador de ExecutionEvent en dos fases, sin salida).
Núcleo financiero congelado **intacto** (deuda P3 C2 aceptada como riesgo medido, ver
[`docs/engineering/deuda-p3-nucleo-aceptada-c2-2026-09-09.md`](./docs/engineering/deuda-p3-nucleo-aceptada-c2-2026-09-09.md)).
Package **`1.46.1-beta`** (bump desde `1.46.0-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**
(sin migración nueva).

### P1-02/P1-03 — owner-scoping del account default (`set_default_account`/`delete_simulated_account`)

- `set_default_account` y `delete_simulated_account` ya no tratan el `is_default` y la promoción
  de siguiente default de forma global-cuenta: se ciñen al **owner** que hace la operación
  (`owner_user_id` desde el principal autenticado en rutas), evitando sobrescribir el default de
  otro tenant o promover una cuenta activa ajena tras borrar un default.
- Rutas `accounts.py` pasan `owner_user_id` resuelto del principal; el purge administrativo
  del ciclo de vida usa `for_purge=True` (scope de sistema) pero la promoción de default sigue
  siendo owner-local (P1-03).
- CI iso: gate `account-isolation` real-PG **43 passed**.

### Auditoría 2 — el incidente `live_drift` ya no tapa un `fill_unseen` posterior

- Cuando una cuenta ya tiene un `live_drift` activo (abierto p. ej. por `cancel_broker_side`) y
  en un tick posterior el recovery entregar un drift de **firma nueva** (order/venue/subtipo,
  p. ej. `fill_unseen`), el snapshot del incidente vigente se **amplía** de forma idempotente
  por firma (`publish_order_live_drifts`, campo `merged`) en lugar de descartarlo con un
  `already_active` silencioso. Un drift ya registrado sigue siendo replay no-op. Nunca se crea
  un 2º OPEN ni se auto-heal.

### Auditoría 3 — consentimiento del operador de ExecutionEvent con salida real (dos fases)

- `apply_fill_idempotent` captura con idempotencia (1ª fase, `permit=False` no materializa).
  Nueva `apply_pending_execution(execution_id, apply_finance)` (2ª fase) retoma la traza ya
  capturada cuando llega el "go" y materializa Position/Ledger sin chocar con
  `duplicate_skipped`; `event_not_found` si la traza no existe (fail-closed) y
  `captured_not_applied` si el apply no fue efectivo (reintentable).

### Verificación

Unit (18 drift + execution) + regresión (60) verdes; e2 PG real en scratch `bolsa_c1_scratch`
(head 023, dedicated) **5/5**, incluido el merge `fill_unseen`; ruff CI-parity 0; mypy src 0.
Shared `bolsa_v1` intacta en 023.

**Release-tag CI `#34331846887` GREEN** sobre `v2.16.1-beta` (`conclusion: success`, certify ✓):
security · shared · decision-spine · lifecycle-pg · dr-verify · python (ruff/mypy/pytest) ·
frontend (+contract) · playwright (mock E2E). Integrated E2E opt-in skipped (no requisito de
GREEN). Repo dispuesto para **auditoría externa** sobre el tag `v2.16.1-beta`.

## [1.46.0-beta] — 2026-09-09

Elevación a `main` de `V2.15.4` (aislamiento account-less) + `V2.15.5` (DR industrial OHLCV/backup 3-2-1) en **un solo tag `v2.16-beta`**; núcleo financiero congelado intacto; sin migración nueva. Producto **BETA / no producción**.
Package **`1.46.0-beta`** (**bump** desde `1.45.3-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**.
Tip: **`302a3220`** (V2.15.5) == código elevado; este commit es el bump/elevación.

### V2.15.4 — aislamiento account-less fiable (P1 C2-06)

Reads/writes **account-less no degradan a global**; sin cuenta propia quedan fail-closed, nunca asumen tenant del owner ajeno:

- `account_repository.resolve_default_account_for_owner`: el default activo visible al owner F7c (evita colapso `is_default` entre tenants).
- `resolve_account_scope_or_default`: `account_id` ajeno → 404; ausente → default del principal; sin cuenta propia → `None` (fail-closed).
- `ai_governance` reads (effectiveness, decision-sessions, learning-summary) y writes (decision-memory, trials, edge-reports, propose): account-less → default del principal; filas huérfanas `NULL` excluidas de listados.
- `investor_profiles` refresh-observed: valida el owner del account; account-less → default.
- CI: gate `account-isolation` real-PG en `lifecycle-pg` (fail-closed vía `certify`).
- Tests: 4 account-less 2-owners (23 ISO + ai_authoring 26 verdes real-PG).

### V2.15.5 — DR industrial: snapshot atómico + digest por bloques + OHLCV + C2-01 + backup 3-2-1/RPO-RTO

Alcance SOLO infraestructura DR (`scripts/`), núcleo financiero congelado:

- **Snapshot atómico `REPEATABLE READ`**: TODAS las tablas (financieras + mercado) se leen en **UNA** transacción `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; … COMMIT;` → imagen consistente. Parser arreglado (psql `-A` emite `|`, no tab) → el digest de tablas no vacías ya reporta cuenta real (antes 0/vacío y el cheque pasaba en vacío).
- **Digest por BLOQUES** (`CHUNK_SIZE=5000`, md5 por bloque ordenado + concat) en vez de `md5(string_agg total)` → memoria acotada y determinista; añade `MARKET_ENTITIES`: `ohlcv_bars` (167k, fuente de verdad), `instruments`, `data_sync_log`.
- **RTO** medido del restore + cobertura volcada a `logs/agent/db-dr-verify.json`.
- **C2-01** (`db-restore`): `--target-db` validado (`^[A-Za-z0-9_.-]+$`) **ANTES** del DDL destructivo.
- **Backup 3-2-1 + RPO/RTO**: espejo a dir env `DB_BACKUP_MIRROR_DIR` (2º medio/árbol) + manifest registra `mirror`; `db-backup-list` muestra RPO y estado espejo. (3er medio off-site: guía MVP de set-up, ver [`docs/engineering/guia-off-site-3er-medio-2026-09-09.md`](./docs/engineering/guia-off-site-3er-medio-2026-09-09.md).)
- `db-backup-cron-win`: tarea programada de **restore-test DR diario** (`db:dr:test` con volumen real) junto al backup diario.

### Verificación real

Batería DR local con volumen real (dump → checksum → restore a scratch → integridad md5 por bloques financiero+mercado) **verde** + aislamiento **43 passed** real-PG + `node --check` OK + C2-01 rechaza inyección antes del DDL (`bolsa_v1` intacta). Gate industrial del tag: job `dr-verify` del Release-tag CI (TCP, fail-closed vía `certify`).

## [1.45.3-beta] — 2026-09-08

Hardening de la auditoría **V2.15.1 C2** (delta en **scripts DR + CI del tag**; núcleo financiero congelado sin tocar; sin migración nueva). Producto **BETA / no producción**.
Package **`1.45.3-beta`** (**bump** desde `1.45.2-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**.
Cierra tres hallazgos de la pasada anterior:

- **C2-02 (P2-alto)** — `scripts/db-dr-verify.mjs` extiende la batería DR con **invariantes financieras de datos**: inventario canónico de 18 tablas (`FINANCIAL_ENTITIES`, fuente `tables.py`), snapshot `COUNT(*)` + digest md5 del contenido canónico ordenado **BEFORE** sobre la principal y comparación **AFTER** sobre la scratch; checks `dr-snapshot-financiero-leido` y `dr-datos-financieros-integridad`. El restore deja de ser solo "estructural ↔ head" y pasa a ser **financieramente verificable**. (md5 en vez de sha256: `sha256()/encode` viven en `pgcrypto`, no en PostgreSQL 16 core por defecto al restaurar la scratch; md5 built-in basta como guard no-adversarial.)
- **C2-12 / C2-13 (P2/P3)** — la faena DR y el readiness schema-aware se elevan al **release-tag CI** para que certifiquen en el runner, no solo en local:
  - transport layer TCP opt-in `BOLSA_DR_TCP=1` (psql/pg*dump de host por `PGHOST/PGPORT/PGUSER/PGPASSWORD`/`DB*\*`) en `docker.mjs`/`backup.mjs`/`db-restore.mjs`/`db-dr-verify.mjs`, con **default Docker intacto** para dev.
  - job nuevo **`dr-verify`** en `release-tag-ci.yml` (`services: postgres:16-alpine` + `postgresql-client` + `alembic upgrade head` + batería DR por TCP), incorporado a `needs:`/fail-if/summary de `certify` → **un DR rojo rompe el tag**.
  - `apps/api-python/tests/test_health.py` (readiness `/health/ready` 200/503 schema-aware) entra en el pytest PG de `lifecycle-pg`.
    Validación local: `pnpm db:dr:test` (Docker) → **8/8 PASS**, incluidas las 2 checks nuevas C2-02. Certificación final del path TCP (runner) vía **Release-tag CI** de este tag.

## [1.45.2-beta] — 2026-09-08

Auditoría externa **V2.15.1 C2** (delta exclusivamente **documental/audit**; núcleo financiero sin tocar). Producto **BETA / no producción**.
Package **`1.45.2-beta`** (**bump** desde `1.45.0-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`** (sin migración nueva).
V2.15.1 C2 re-certificada ≈ **9.1/10 Beta** (ver [`auditoria-v2-15-1-c2`](./docs/engineering/auditoria-v2-15-1-c2-2026-09-08.md)): los tres P1 de V2.15 cerrados; deudas P2/C2-12+13 (DR+readiness no corren en tag-CI) y C2-02 (invariantes financieras en batería DR) decididas antes del "OK final"; account isolation **P2-latente** (no P1-activo, single-owner). Cierres de esta pasada: C2-08 (cash paper/ledger idempotente real-PG, no P1 de doble-abono), C2-06 (sin path de creación por JWT; ops-self-eval cerrado), contrato FE↔BE núcleo **limpio**.

## [1.45.0-beta] — 2026-09-08

V2.15 **C2 · cierre de certificación** a `main` (restore seguro + readiness schema-aware + batería DR). Producto **BETA / no producción**.
Package **`1.45.0-beta`** (**bump** desde `1.44.0-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`** (sin migración nueva).
Núcleo financiero (FSM/live_orders/ExecutionEvent/ledger/outbox/reconciliation) **congelado e intacto**. Relevo [`traspaso-relevo-tag-v2-15-1-c2-cierre-certificacion-2026-09-08.md`](./docs/engineering/traspaso-relevo-tag-v2-15-1-c2-cierre-certificacion-2026-09-08.md).

### Cierre certificación — restore 100 % seguro (P1 V2.15-01/02)

- **`db:restore`**: psql con `-v ON_ERROR_STOP=1` (cualquier error SQL ⇒ failed). Alembic tras el restore se dirige **siempre a `--target-db`** (reescritura de `DATABASE_URL` vía `redirectDatabaseUrlTo`), nunca a `bolsa_v1`. Aborta si el sidecar `.sha256` no coincide.
- `scripts/lib/db.mjs`: `runAlembicUpgrade({ databaseUrl })` + `redirectDatabaseUrlTo(db)`.

### Cierre certificación — readiness schema-aware (P1 V2.15-03)

- **`/api/health/ready`** exige `READY = PostgreSQL AND alembic_version == expected_head` (Alembic): 200/ready solo si ambos; 503 si la BD responde pero el esquema no está al head (fail-closed, nunca "ready" contra una BD vieja). Campo nuevo `schema_status`.
- `session.py::read_db_schema_current` (lee `alembic_version`, mensajes redactados).

### Batería DR y hardening de backups (P2)

- **`pnpm db:dr:test`** (`scripts/db-dr-verify.mjs`): vuelca, verifica checksum, restaura a scratch vía `db-restore --target-db`, comprueba head/esquema consultable y que `bolsa_v1` no cambia; limpia la scratch. GREEN en local.
- `backup.mjs`: sello con ms + escritura exclusiva (O_EXCL), sidecar `<file>.sha256`, `backups-manifest.json`, `DB_BACKUP_KEEP` mínimo ≥1.

### Tests y contrato

- `test_health.py`: ready 200-at-head + 503 schema-mismatch + 503 unmigrated. Contrato `openapi.json`/`schema.d.ts` regenerados (solo `schema_status` + descripciones).

## [1.44.0-beta] — 2026-09-08

V2.15 **1er ciclo de hardening** a `main` (PREVENCIÓN backups + provenance/readiness). Producto **BETA / no producción**.
Package **`1.44.0-beta`** (**bump** desde `1.43.2-beta`). Alembic head **`023_ohlcv_bars_unique_reconcile`**.
**≠** Accept LIVE · **≠** thaw · **≠** settlement · éxodo LIVE no certificado. Relevo [`traspaso-relevo-v2-15-backups-prevencion-2026-09-08.md`](./docs/engineering/traspaso-relevo-v2-15-backups-prevencion-2026-09-08.md).

### Prevention — backups de `bolsa_v1` (faena 1)

- **`pnpm db:dump` / `db:backup`**: volcado local `db-backups/bolsa_v1-<stamp>.sql[.gz]` vía `docker exec pg_dump`
  (por fuera del contenedor) + poda por retención (`DB_BACKUP_KEEP`, default 14). `db:backup:list` lista.
- **`pnpm db:restore --file … --yes`**: recrea la BD destino y aplica el dump por stdin, re-aplicando Alembic head `023`.
  `--target-db` y `--no-alembic` para pruebas seguras. `db:backup:cron:win` genera tarea `schtasks` diaria.
- `.gitignore db-backups/` (no versiona), `.env.example DB_BACKUP_KEEP`, doc en `docs/DEV_STARTUP.md`.
  Motivo: [incidente pérdida de listas](./docs/engineering/traspaso-incidente-perdida-list-2026-09-08.md).
  Helpers [`scripts/lib/backup.mjs`](./scripts/lib/backup.mjs) · scripts `db-dump/db-restore/db-backup-list/db-backup-cron-win`.

### Hardening V2.15 — first cycle (provenance + readiness)

- **Readiness operacional**: nuevo `GET /api/health/live` (liveness sin BD) y `GET /api/health/ready`
  (readiness, PostgreSQL requerido → 200/ready o 503/not_ready). `/api/health` agregado compatible.
- **Provenance obligatoria en producción**: `require_release_identity_env()` eleva en `create_app` cuando
  `PRODUCT_VERSION`/`API_CONTRACT_VERSION` faltan en `ENVIRONMENT=production` (allowlist dev/test/staging
  las mantiene opcionales para no romper CI/local).
- Tests offline `test_provenance_gate.py` + tests `live/ready` en `test_health.py`; `openapi.json`/`schema.d.ts`
  regenerados (solo aditivo). Rama `stage/v2.15-backups-prevencion-2026-09-08` → merge PR **#59**.
  Núcleo congelado (FSM/live_orders/ExecutionEvent/ledger/outbox/recon) intacto.

## [1.43.2-beta] — 2026-09-08

V2.14.2 **elevation** (cierre A1: account-isolation ampliada a rutas de LECTURA/estudio) a `main`. Producto **BETA / no producción**. Package **`1.43.2-beta`** (**bump** desde `1.43.1-beta`). **≠** Accept LIVE · **≠** thaw · **≠** settlement · éxodo LIVE no certificado.

### Close — A1 account-isolation extendida a rutas de LECTURA/estudio (2026-09-08)

- **Cierre A1 residual (deuda del cierre V2.14.1).** Además de los gates de EJECUCIÓN ya aplicados
  (confirm/evaluate-exits/execute-auto/paper-desk-cycle), quedó la deuda de que los endpoints de
  **lectura/estudio/acount-scope** operaban sin `require_account_access` (solo explotable con ≥2.º
  owner real; hoy single-owner bootstrap). Al añadirse `require_owned_account_if_present`
  (`dependencies.py`), se bloquea (404) toda lectura/estudio que declare una `account_id` que no
  pertenezca al principal del request; `account_id` ausente (demo/global) se preserva para la UI.
- **Rutas gateadas con cuenta visible:**
  - `ai_governance.py`: `GET /ai/effectiveness`, `POST /ai/decision-memory`, `GET /ai/decision-sessions`,
    `GET /ai/decision-sessions/learning-summary`, `GET /ai/decision-sessions/{id}` + `/replay`,
    `POST /ai/decision-sessions/{id}/outcome`, `POST /ai/trials`, `POST /ai/edge-reports`,
    `POST /ai/recommendations/propose`.
  - `instrument_daily_opinions.py`: `POST /instrument-daily-opinions/query`,
    `GET /instrument-daily-opinions/auto-telemetry`, `POST /instrument-daily-opinions/auto-propose`,
    `POST /instrument-daily-opinions/eod-batch`.
  - `paper_desk.py`: `GET /paper-desk/daily-report`.
  - `risk.py`: `GET /risk/ops-self-eval`.
- Tests de aislamiento por cuenta añadidos en `apps/api-python/tests/test_account_isolation.py`
  (effectiveness/decision-sessions/ops-self-eval/daily-report → 404 cuenta ajena). En el informe de
  lectura A1 (`audit-interno-lectura-v2-14-2026-09-08.md`) el hallazgo A1 pasa de **[cerrado parcial]**
  a **[cerrado]** (la nota cross-account multi-owner sigue `[runtime-aislamiento]`: hoy único owner real).

## [1.43.1-beta] — 2026-09-08

V2.14.1 **hotfix elevation** (`provenance self-reported + contract G12/G13` · `A1 account-isolation` · `schema 023 reconcile`) a `main`. Producto **BETA / no producción**. Tip vigente **`main` → [`da181b76`](https://github.com/jvelasca/Bolsa_V1/commit/da181b76)** (cierre auditoría V2.14 · +hotfixes 2026-09-08). Package **`1.43.1-beta`** (**bump** desde `1.43.0-beta`). **≠** Accept LIVE · **≠** thaw · **≠** settlement · éxodo LIVE no certificado.

### Hotfix interno — reconciliación upsert OHLCV → schema `023_ohlcv_bars_unique_reconcile` (2026-09-08)

- **Schema-drift (auditoría interna V2.14):** `ohlcv_repository.upsert_bars` (`ON CONFLICT (instrument_id,timeframe,timestamp)`, cd451fea) exigía un índice único que las migraciones Alembic no creaban (solo PK id) → todo el sync de mercado abortaba (500, `InvalidColumnReference`), la BD quedaba sin barras y la UI mostraba listas vacías e "histórico no disponible". Añadida migración **`023_ohlcv_bars_unique_reconcile`** (+índice único declarado en `OhlcvBarRow`) y repoblado el histórico (44.7k barras 1d, 2021→hoy, para los 35 activos IBEX; freshness `current`). Guards tests real-PG/provenance actualizados a head `023`.

### Hotfix interno — provenance self-reported + contract gate G12/G13 (2026-09-08)

- `GET /api/health → provenance` (PRODUCT/PACKAGE/GIT_SHA/DB_SCHEMA/API_CONTRACT desde fuentes únicas, sin DB) · `bolsa_api.provenance` · `contract-check.ts` **G12** `OperationalIncidentV1` + **G13** `SubmitIntentListItemV1` · openapi.json/schema.d.ts regenerados y sincronizados.

### Hotfix interno — A1 account-isolation en rutas de EJECUCIÓN (2026-09-08)

- `require_account_access` en `POST /ai/intents/confirm`, `/position-policies/evaluate-exits`, `/position-automation/execute-auto`, `/paper-desk/cycle`. Rutas de LECTURA/estudio quedan sin gate (deuda residual A1, explotable solo con ≥2º owner real).

## [1.43.0-beta] — 2026-09-08

V2.14 **Financial Execution Core** elevation a `main`. Producto **BETA / no producción**. Tip vigente **`main` → [`e76a1942`](https://github.com/jvelasca/Bolsa_V1/commit/e76a1942)** (V2.14 elevation · 08/09 09:23 UTC). Package **`1.43.0-beta`** (**bump** desde `1.42.0-beta`). Tip previo **`v2.13-beta` → `da5c4b2a`** / `1.42.0-beta`. Alembic head **`022_live_orders_exec`**. `LIVE_EXECUTION_UNLOCKED` default **off** (sandbox · cero POST bridge). **No** LIVE capital · cancel XTB real **PARKED** (honest-boundary, cero POST en cancel). Capacidad técnica ≠ permiso operativo (separación deliberada). Provenance auto-reportada vía `GET /api/health → provenance`.

### V2.14 — Financial Execution Core

- **D0 foundation** [`b54c92d8`](https://github.com/jvelasca/Bolsa_V1/commit/b54c92d8): decree Financial Execution & Full Reconciliation.
- **B1** [`462a30cb`](https://github.com/jvelasca/Bolsa_V1/commit/462a30cb): `Decimal` al boundary financiero (order/cash/position query + drift) — P1-03/P2-02/P2-03.
- **B2** [`67867a04`](https://github.com/jvelasca/Bolsa_V1/commit/67867a04): lease configurable por env (P2-04) + cancel XTB **PARKED** (P2-05).
- **E1** [`f29e452c`](https://github.com/jvelasca/Bolsa_V1/commit/f29e452c): `ExecutionEvent` scaffold idempotente **GATED** (P1-01) + migración **`022_live_orders_exec`** + observabilidad `live_orders` (`attempt_count`/`last_error`/`claim_expires_at`).
- **E2 P2-2** [`2942fec1`](https://github.com/jvelasca/Bolsa_V1/commit/2942fec1): dedup **OPEN** multi-worker en `OperationalIncidentStore` PG (1 incidente, no 2).
- **E2 P2-01** [`0a44764b`](https://github.com/jvelasca/Bolsa_V1/commit/0a44764b): durable order-drift → `OperationalIncident` `live_drift` (gated).
- **E2 P1-02** [`660fbd83`](https://github.com/jvelasca/Bolsa_V1/commit/660fbd83): reconcile **POSICIÓN continuo** (LR-1) en tick recovery, gated.
- **E2 C1 real-PG** [`96778854`](https://github.com/jvelasca/Bolsa_V1/commit/96778854): batería REAL-PG dedup OPEN/drift frente a PostgreSQL.
- **C1 Release-tag CI** [`095a5ab1`](https://github.com/jvelasca/Bolsa_V1/commit/095a5ab1) → [`78dd3f9a`](https://github.com/jvelasca/Bolsa_V1/commit/78dd3f9a): head real-PG `022` + ruff-I001 whole-tree + fix mypy gate (3 errores) hallados por Release-tag CI real.
- **Elevation** [`e76a1942`](https://github.com/jvelasca/Bolsa_V1/commit/e76a1942): V2.14 + bump `1.43.0-beta` — tip auditable desde GitHub.
- Docs: arranque auditor externo [`08cada82`](https://github.com/jvelasca/Bolsa_V1/commit/08cada82) (veredicto V2.13 sin P0/P1) · deuda hallazgos P2/P3 del audit ampliado V2.13 [`0a217468`](https://github.com/jvelasca/Bolsa_V1/commit/0a217468) · relevo de cierre [`c24bbb67`](https://github.com/jvelasca/Bolsa_V1/commit/c24bbb67).

## [1.42.0-beta] — 2026-09-07

V2.13 **live execution gates** + tip formal `v2.13-beta`. Producto **BETA / no producción**. Tip **`v2.13-beta` → `da5c4b2a`**. Package **`1.42.0-beta`** (**bump** desde `1.41.0-beta`). Alembic head **`021_live_orders_fin`**. Release-tag CI tip según último run sobre este tag. Confirm = firma. `LIVE_EXECUTION_UNLOCKED` default **off** (sandbox · cero POST bridge). **No** LIVE capital. **≠** Accept estricto · **≠** thaw venue · **≠** settlement.

### V2.13 — live execution gates (concurrency + financial invariants + honest cancel + reconcile)

- **Baseline** [`34285584`](https://github.com/jvelasca/Bolsa_V1/commit/34285584): live execution gates — XL-3 concurrency + financial invariants + honest cancel + reconcile.
- **V2.13.1 rc** [`0dce2fa9`](https://github.com/jvelasca/Bolsa_V1/commit/0dce2fa9): honesty remediation (audit H1/H2/H4/H5) post-baseline.
- **V2.13.2 rc** [`656c8b37`](https://github.com/jvelasca/Bolsa_V1/commit/656c8b37): broker-query real (H6) + reconcile máquina `live_orders` (H7); docs cierre H3 [`0983391c`](https://github.com/jvelasca/Bolsa_V1/commit/0983391c).
- **Tip formal** [`da5c4b2a`](https://github.com/jvelasca/Bolsa_V1/commit/da5c4b2a): release `v2.13-beta` (`1.42.0-beta`) — broker-query real H6 + reconcile live_orders H7.
- **V2.13.3 rc CI fix** [`4039087f`](https://github.com/jvelasca/Bolsa_V1/commit/4039087f) · [`4c5dee57`](https://github.com/jvelasca/Bolsa_V1/commit/4c5dee57) · [`e4cfbabd`](https://github.com/jvelasca/Bolsa_V1/commit/e4cfbabd) · [`6e279e2d`](https://github.com/jvelasca/Bolsa_V1/commit/6e279e2d): lifecycle-pg fixtures head-guard a `021_live_orders_fin` (set-membership, no prefijo) + mock E2E live-virtual confirm seed a TRIGGERED tradePlan (CTA sandbox cero POST bridge) + revision corta `varchar32`.

## [1.41.0-beta] — 2026-09-07

V2.12 **XL-3 durable core** + scope-out `list_open_orders` / `cancel_order`. Producto **BETA / no producción**. Tip **`v2.12-beta`** → commit de release de esta entrada. Package **`1.41.0-beta`** (**bump** desde `1.40.0-beta`). Tip previo **`v2.11-beta` → `80e891c4`** / `1.40.0-beta` (**inmutable**). Release-tag CI tip según último run sobre este tag. Confirm = firma. `LIVE_EXECUTION_UNLOCKED` default **off** (sandbox · cero POST bridge). **No** LIVE capital. **≠** Accept estricto · **≠** thaw venue · **≠** settlement.

### V2.12 — XL-3 durable core (live_orders PG + UNKNOWN recovery)

- **Tabla `live_orders`** (PK `order_id` · account_id · indicadores 8×) · migración **`020_live_orders`** idempotente (guards table/index; down `019_outbox_position_fifo`).
- **`PostgresLiveOrderStore`** durable cross-PID: put (insert/update) / get / delete / `list_unknown` / `list_open_orders` / `cancel_order`. Mapeo dominio↔fila 1:1 con `account_id`.
- **Worker `live_order_recovery_worker`** (por defecto ON · `LIVE_RECOVERY_WORKER_ENABLED`): cada tick relee `UNKNOWN` y resuelve vía `query_broker` (no re-POST). Fail-closed: sin cliente / `unavailable` / intraducible → la fila queda `UNKNOWN` (refresca `updated_at`). **Nunca** sintetiza `execute_trade`/ledger.
- **Scope-out V2.12:** `list_open_orders` (no terminales via `NON_TERMINAL_LIVE_STATUSES`, ordena `updated_at`, limita) y `cancel_order` (`CANCELLED` solo si el grafo lo permite; idempotente; `reason` documental). Real cancel round-trip XTB **PARKED** (honest-boundary; cero POST en cancel).
- Wiring: `scheduler_worker` arranca el worker; `dependencies.get_confirm_intent_use_case` inyecta `PostgresLiveOrderStore(session)`.
- Dominio `LiveOrder` (PY+TS) UNKNOWN first-class · no re-POST · PARTIAL qty · `account_id` en PY+TS.
- OR-6 fail-closed: live recon no medido → `LIVE_BLOCKED` / `live_unavailable`; adapter `None` → `live_adapter_not_wired` (vocab LR-1 `clean`).
- OE-1 cablea LR-1 + `liveAdapterWired` (bridge URL) en OR-6.
- Sandbox VIRTUAL: `XtbBrokerAdapter` sin unlock → `live_virtual_sandbox` (cero POST bridge); kill switch reconsultado en adapter.
- **Confirm wiring persist-only:** `LiveOrderCoordinator` registra la máquina tras submit LIVE `submitted`/`unknown` y la expone en `result["liveOrder"]`; PAPER/sandbox/rejected/executed(XL-2) no la tocan. Confirm orquestador sigue `<1100` líneas.
- Docs: [roadmap LIVE Execution](./docs/engineering/roadmap-live-execution-core-2026-09-07.md) · [honesty bridge](./docs/engineering/honesty-pack-xtb-bridge-external-2026-09-07.md) · relevo durable core [`traspaso-relevo-xl3-durable-core-2026-09-07.md`](./docs/engineering/traspaso-relevo-xl3-durable-core-2026-09-07.md) · relevo tag [`traspaso-relevo-tag-v2-12-beta-2026-09-07.md`](./docs/engineering/traspaso-relevo-tag-v2-12-beta-2026-09-07.md).

## [1.40.0-beta] — 2026-09-07

V2.11 Confirm LIVE VIRTUAL (UI honesty). Producto **BETA / no producción**. Tip **`v2.11-beta` → `80e891c4`**. Package **`1.40.0-beta`**. Tip previo **`v2.10.1-beta` → `a060af37`** / `1.39.1-beta` (inmutable). Release-tag CI tip **CERTIFICABLE** — [run 34027601775](https://github.com/jvelasca/Bolsa_V1/actions/runs/34027601775) `conclusion=success`. Confirm = firma. CTA live = **Firmar · Ejecutar en LIVE VIRTUAL (simulado)**. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE capital. **NO MÁS PANELES** (híbrido dentro de Confirm · excepción owner). **≠** Accept estricto · **≠** thaw venue · **≠** settlement.

### V2.11 — Confirm LIVE VIRTUAL

- Pasarela híbrida telegrama + por qué + banner **LIVE VIRTUAL · SIMULADO** en Confirm (`live-virtual-*`).
- CTA TS+PY honesty; badge manual ticket alineado.
- E2E mock `gp-e2e-live-virtual-confirm-mock`.
- Pack [`audit-pack-v2-11-live-virtual-confirm-2026-09-07.md`](./docs/engineering/audit-pack-v2-11-live-virtual-confirm-2026-09-07.md) · relevo tag [`traspaso-relevo-tag-v2-11-beta-2026-09-07.md`](./docs/engineering/traspaso-relevo-tag-v2-11-beta-2026-09-07.md) · arranque auditor [`arranque-auditor-v2-11-live-virtual-2026-09-07.md`](./docs/engineering/arranque-auditor-v2-11-live-virtual-2026-09-07.md).

## [1.39.1-beta] — 2026-09-05

V2.10.1 CI certification hotfix + tip de provenance. Producto **BETA / no producción**. Tip **`v2.10.1-beta` → `a060af37`**. Hotfix código **`7156169f`** (tests/selectores; **no** motor). Package **`1.39.1-beta`**. Tip previo **`v2.10-beta` → `6495dd5f`** (inmutable; Release-tag CI [33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `failure`). Código hotfix CI [33981998373](https://github.com/jvelasca/Bolsa_V1/actions/runs/33981998373) `success`. Release-tag CI tip **CERTIFICABLE** — [run 33983574346](https://github.com/jvelasca/Bolsa_V1/actions/runs/33983574346) `conclusion=success`. Confirm = firma. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE. **NO MÁS PANELES**. **PRODUCT FREEZE** en V2.10.1.

### V2.10.1 — CI GREEN / Certification Fix

- **Cluster A:** expand Daily Desk `no_operar` antes de assert deny stale.
- **Cluster B:** `sr-only` `position-decision-stop` / t1 / t2 con Journey HUD.
- Vitest copy alineado a cabina actual.
- Relevo [`traspaso-relevo-v2-10-1-ci-green-2026-09-05.md`](./docs/engineering/traspaso-relevo-v2-10-1-ci-green-2026-09-05.md) · relevo tag [`traspaso-relevo-tag-v2-10-1-beta-2026-09-05.md`](./docs/engineering/traspaso-relevo-tag-v2-10-1-beta-2026-09-05.md).

## [1.39.0-beta] — 2026-09-05

V2.9 Visual and Operational Certification + V2.10 Seed Ops. Producto **BETA / no producción**. Tip **`v2.10-beta`** (sin tip `v2.9-beta` aparte). Partida **`v2.8-beta` → `a9ec6424`**. Package **`1.39.0-beta`**. Confirm = firma. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE. **NO MÁS PANELES**. Release-tag CI **NO CERTIFICABLE** — [run 33980277268](https://github.com/jvelasca/Bolsa_V1/actions/runs/33980277268) `conclusion=failure`.

### V2.9 — Visual and Operational Certification (2026-09-05)

- **V2.46–V2.51:** ARM chrome `autoActive` · `orphan_recovery_failed` visible · touch 44px · layout zoom 100/125/150 · snapshots/contraste `gp-e2e-v29` (pixel skip CI linux) · teclado cabina.
- Relevo [`traspaso-relevo-v2-9-visual-operational-certification-2026-09-05.md`](./docs/engineering/traspaso-relevo-v2-9-visual-operational-certification-2026-09-05.md).

### V2.10 — Seed Ops (2026-09-05)

- **V2.52–V2.53:** seed birth Confirm + `signedStop` estructural → `PROTECTED` / Planificado · Journal `runtime.mfeMae` · `scripts/ops_seed_cabin_smoke`.
- Relevo [`traspaso-relevo-v2-10-seed-ops-2026-09-05.md`](./docs/engineering/traspaso-relevo-v2-10-seed-ops-2026-09-05.md) · runbook [`runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md`](./docs/engineering/runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md).
- Relevo tag [`traspaso-relevo-tag-v2-10-beta-2026-09-05.md`](./docs/engineering/traspaso-relevo-tag-v2-10-beta-2026-09-05.md).

## [Unreleased]

### V1.60 — UX Mercado (tarjeta estrella DECISIÓN) (2026-09-02)

- **GP-V160-01..04:** tarjeta estrella `PositionOperationalStarCard` + `usePositionOperationalView` — POV canónico en panel DECISIÓN; T2_READY/T2_EXECUTED · RECONCILIATION_DRIFT · stopHistory colapsable · vitest + testids.
- Wire: `operativa-cockpit-card` · `mercadoCockpitPosicionPhaseLabel` · recon chip POV-aware.
- Spec [`spec-v160-ux-mercado-2026-09-02.md`](./docs/engineering/spec-v160-ux-mercado-2026-09-02.md) · relevo [`traspaso-relevo-v1-60-ux-mercado-2026-09-02.md`](./docs/engineering/traspaso-relevo-v1-60-ux-mercado-2026-09-02.md) · arranque auditor [`arranque-auditor-v1-60-ux-mercado-2026-09-02.md`](./docs/engineering/arranque-auditor-v1-60-ux-mercado-2026-09-02.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.60-beta` → `7ac8ad9b`**.

### V1.59 — E2E Integrated (FastAPI + PostgreSQL) (2026-09-02)

- **GP-V159-01..07:** suite integration pytest + `httpx.AsyncClient` + PG real (`@pytest.mark.integration`): trade/portfolio operational · paper-desk dry-run/gate · ops-self-eval recon · decision-journal · incident resolve/clear HTTP · execute-auto dry_run.
- **Harness:** `v159_harness.py` + skip sin PostgreSQL; complementa Golden Session pytest (no sustituye).
- **Fix colateral:** `opening_gate_seed` siembra serie plana 120d (elimina veto sanity split/dividendo en DS-05).
- Spec [`spec-v159-e2e-integrated-2026-09-02.md`](./docs/engineering/spec-v159-e2e-integrated-2026-09-02.md) · relevo [`traspaso-relevo-v1-59-e2e-integrated-2026-09-02.md`](./docs/engineering/traspaso-relevo-v1-59-e2e-integrated-2026-09-02.md) · arranque auditor [`arranque-auditor-v1-59-e2e-integrated-2026-09-02.md`](./docs/engineering/arranque-auditor-v1-59-e2e-integrated-2026-09-02.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.59-beta` → `b5c5c6ab`**.

### V1.58 — Adversarial Execution (2026-09-01)

- **GP-GOLDEN-DAY-ADV-01:** día PAPER encadenado (BUY → dup fill → T1 → crash replay → TRAIL → T2 network skip → retry → dup event → EXIT → recon clean) en `test_paper_desk_golden_day_adversarial.py`.
- **AdversarialSell:** `fail_next(n)` → `skipped`/`network_failure` sin consumir fill id; retry ejecuta.
- **P0b:** `execute_position_policy_auto` marca leg `failed` solo en `blocked`/`rejected`, no en transport skip.
- **GP-V158-STOP-CLOSED:** STRUCTURAL_STOP + `session=CLOSED` vende; T1 + CLOSED → `queue_next_session`. Hallazgo 22 rondas cerrado como contrato PAPER (sin encolar stop a apertura).
- Spec [`spec-v158-adversarial-execution-2026-09-01.md`](./docs/engineering/spec-v158-adversarial-execution-2026-09-01.md) · relevo [`traspaso-relevo-v1-58-adversarial-execution-2026-09-01.md`](./docs/engineering/traspaso-relevo-v1-58-adversarial-execution-2026-09-01.md) · arranque auditor [`arranque-auditor-v1-58-adversarial-execution-2026-09-01.md`](./docs/engineering/arranque-auditor-v1-58-adversarial-execution-2026-09-01.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.58-beta`**.

### V1.57 — Operational Truth (2026-09-01)

- **GP-V157-01:** `T2_EXECUTED` distinto de `T2_READY`; eventos T2 simétricos a T1; desk map `T2_*` → reduced.
- **GP-V157-02:** `buildStopHistory` incluye `protect` / `trail` / `reduce` / `override` / `stop`.
- **GP-V157-03:** `reconStatus === "drift"` → `RECONCILIATION_DRIFT` (TS + Python); cubo Mesa `requiere_accion`.
- **INV-01..10:** batería `test_inv_operational_truth.py`. Exhaustividad `assertNever` en proyección cognitiva.
- Spec [`spec-v157-operational-truth-2026-09-01.md`](./docs/engineering/spec-v157-operational-truth-2026-09-01.md) · relevo [`traspaso-relevo-v1-57-operational-truth-2026-09-01.md`](./docs/engineering/traspaso-relevo-v1-57-operational-truth-2026-09-01.md) · arranque auditor [`arranque-auditor-v1-57-operational-truth-2026-09-01.md`](./docs/engineering/arranque-auditor-v1-57-operational-truth-2026-09-01.md). Freeze intacto: **no** LIVE · `PAPER_D_EXECUTE` OFF · package `1.35.0-beta`. Tag **`v1.57-beta`**.

## [1.56-beta] — 2026-09-01

Hardening Residuals post-V1.55. Producto **BETA / no producción**. Tag **`v1.56-beta`**. Partida **`v1.55-beta` → `c23091d9`**. Package congelado **`1.35.0-beta`**. Confirm/DEX/SubmitIntent **intactos**. `PAPER_D_EXECUTE` default **OFF**. **No** LIVE.

### V1.56 — Hardening Residuals (2026-09-01)

- **GP-SESSION-07e:** assert estricto `target2Leg.status == executed`; fix `apply_position_reduce` promueve T2 `triggered`→`executed` en cierre.
- **GP-SESSION-10r:** pytest drift → human `resolve` → `clear` solo recon clean; sin auto-heal.
- **GP-E2E-01..02:** Playwright smoke Journal (`/decision-journal`) + Consola (`/operational-console`); script `pnpm --filter @bolsa/web e2e`; skip default · `E2E_RUN=1` → 2/2.
- Relevo [`traspaso-relevo-tag-v1-56-beta-2026-09-01.md`](./docs/engineering/traspaso-relevo-tag-v1-56-beta-2026-09-01.md) · arranque auditor [`arranque-auditor-v1-56-beta-2026-09-01.md`](./docs/engineering/arranque-auditor-v1-56-beta-2026-09-01.md).
- Pre-flight: pytest GP **26** · shared **34** · web **29** · ruff OK · tsc OK.

## [1.16-beta] — 2026-08-26

Mesa desk V1.16–V1.19 (ADR-037 extensiones) + backend paralelo auditoría V1.15. Producto sigue **BETA / no producción**. Tag **`v1.16-beta` → `f16119b`**. Partida: **`v1.15-beta` → `fc2ed753`**. Spine **`pnpm test:decision-spine` = 485**. Pack: [`audit-pack-estado-global-2026-08-26-v116.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v116.md). Confirm/DEX/SubmitIntent **intactos**. Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. AUTO **off**.

### Docs — Pack auditor v116 Mesa desk (2026-08-26)

- Pack [`audit-pack-estado-global-2026-08-26-v116.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v116.md): stamp global · scorecard MD-1…5 · limitaciones P1/P2.
- Relevo tag [`traspaso-relevo-tag-v1-16-beta-2026-08-26.md`](./docs/engineering/traspaso-relevo-tag-v1-16-beta-2026-08-26.md) — tag `v1.16-beta` → `f16119b`.
- Spine verificado **485**. Limitaciones: chip DS-05 P1 · sanity E2E P1 · what-if sin gates · Libro showRoute post-tag.

### MD-1 — V1.16 Mesa desk cierre (Operational UX II)

- Cabecera operativa · matriz semántica 10 estados · FeatureErrorBoundary Mesa/Confirm/F3.
- Tests shared + web GREEN · smoke browser 5/5 documentado.
- Pendiente P1: chip DS-05 honesto (F1-H).
- Relevo [`traspaso-relevo-mesa-desk-v116-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v116-2026-08-26.md).

### MD-2 — V1.17 Posición + ticket Confirm

- `showRoute` cableado en `/mesa` · invalidación qty/precio F3 · ticket riesgo primero.
- Libro (`/operaciones`) fuera scope — post-tag.
- Relevo [`traspaso-relevo-mesa-desk-v117-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v117-2026-08-26.md).

### MD-3 — V1.18 Evolución + alertas

- Deltas Journal relevantes · panel alertas decisión · orden ADR-037 en `/mesa`.
- Relevo [`traspaso-relevo-mesa-desk-v118-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v118-2026-08-26.md).

### MD-4 — V1.19 What-if + ranking operable

- `sortMesaCandidatesOperable` · `projectMesaWhatIf` read-only · tests ranking.
- Gates reales what-if **fuera** tag (documentado).
- Relevo [`traspaso-relevo-mesa-desk-v119-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-v119-2026-08-26.md).

### MD-5 — Backend paralelo (auditoría V1.15)

- Pickle SHA256 · prod allowlist · `PAPER_D_EXECUTE` Router gate · sanity→DS-05 API · EdgeReport · `require_role` doc.
- pytest **72** passed. `sanity_warnings` E2E runtime **P1 post-tag**.
- Relevo [`traspaso-relevo-mesa-desk-backend-2026-08-26.md`](./docs/engineering/traspaso-relevo-mesa-desk-backend-2026-08-26.md).

## [1.15-beta] — 2026-08-26

Operational UX — **Mesa · Hoy** (ADR-037). Home diaria `/mesa` compone Decision Board, portfolio, studies e incidentes sin endpoints nuevos. Nav: Mesa · Hoy → Trading → … · Consola ops → Herramientas. Journal: vista tabla simplificada + status 3 dimensiones. **BETA / no producción.** Sin cambios en Confirm, TradePlan, SubmitIntent ni DEX.

### Mesa · Hoy (V1.15 Operational UX)

- Ruta `/mesa` · redirect `/` → `/mesa` · ADR [`037-mesa-hoy-operational-ux.md`](./docs/adr/037-mesa-hoy-operational-ux.md).
- Compositor shared `mesa-hoy-model` · `mapMesaStatusDimensions` · tests.
- Secciones: incidentes → sesión → KPIs → atención → posiciones → candidatos → salud ops.
- Deep-links Journal ficha · Hoy strip adelgazado (top-3 + link Mesa).
- Plan [`plan-mesa-hoy-v115-2026-08-26.md`](./docs/engineering/plan-mesa-hoy-v115-2026-08-26.md).

## [1.13-beta] — 2026-08-26

Durable Execution v1.13 (D0 + DEX-1…DEX-5). Producto sigue **BETA / no producción**. Tag anotado **`v1.13-beta` → `c8d5800`** (Release tag CI GREEN). Partida: **`v1.12-beta` → `369b5d1`**. Spine **`pnpm test:decision-spine` = 483**. Pack: [`audit-pack-estado-global-2026-08-26-v113.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v113.md). OR-2 cerrado vía DEX-1+DEX-2. Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. Confirm = única firma. Mesa default **paper**. LIVE **experimental**. AUTO **off**.

### Docs — Pack auditor v113 Durable Execution (2026-08-26)

- Pack [`audit-pack-estado-global-2026-08-26-v113.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v113.md): stamp global · scorecard DEX-1…5 · candidatas post-v1.13.
- Relevo tag [`traspaso-relevo-tag-v1-13-beta-2026-08-26.md`](./docs/engineering/traspaso-relevo-tag-v1-13-beta-2026-08-26.md) — tag `v1.13-beta` al stamp.
- Spine verificado **483**. Cero thaw · cero UI Mesa · cero AUTO · cero broker.

### DEX-5 — Operational invariants (V1.13 Durable Execution)

- Kernel `paper_order`: qty > 0 en build · FILLED rechaza filled < 0 o filled > ordered.
- Predicados `operational_invariants.py` (qty · filled≤ordered · terminal · adverse_exposure).
- Property suite spine `test_dex5_operational_invariants.py` (6 invariantes; sin `hypothesis`).
- Spine **`pnpm test:decision-spine` = 483** (465 → 483).
- Pack v113 stampado en Unreleased Docs · sin UI Mesa incidente · sin thaw.
- Plan [`plan-dex5-operational-invariants-2026-08-26.md`](./docs/engineering/plan-dex5-operational-invariants-2026-08-26.md) · relevo [`traspaso-relevo-dex5-operational-invariants-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex5-operational-invariants-2026-08-26.md).

### DEX-4 — Confirm = orquestador (V1.13 Durable Execution)

- Paquete `bolsa_application/confirm/`: Identity · RiskGate · OpeningGate · ExitGate · Execution · SubmitIntent · PositionSync.
- `ConfirmRecommendationIntent` = orquestador fino (~922 líneas; pre ~1531). API pública y semántica OR-1…OR-4 / DEX-1…3 intactas.
- Tests spine `test_dex4_confirm_orchestrator.py` (2). Spine **`pnpm test:decision-spine` = 465**.
- Sin property suite (DEX-5) · sin pack v113 · sin UI Mesa incidente · sin thaw.
- Plan [`plan-dex4-confirm-orchestrator-2026-08-26.md`](./docs/engineering/plan-dex4-confirm-orchestrator-2026-08-26.md) · relevo [`traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex4-confirm-orchestrator-2026-08-26.md).

### DEX-3 — OperationalIncident / resolución recon (V1.13 Durable Execution)

- Kernel `OperationalIncident`: open → in_review → resolved → cleared. Resolve exige nota; clear solo si recon `clean`. Sin auto-heal.
- Alembic `014_operational_incidents` + `PostgresOperationalIncidentStore`. Un activo por `(account, kind)`.
- Opening veto `incident:unresolved` (incluso si el drift ya se fue). Exits ALLOW. Confirm / Fill / HTTP / Router cableados.
- Tests spine `test_dex3_operational_incident.py` + kernel analytics. Spine **`pnpm test:decision-spine` = 463**.
- Sin Confirm split · sin UI Mesa · sin pack v113.
- Plan [`plan-dex3-operational-incident-2026-08-26.md`](./docs/engineering/plan-dex3-operational-incident-2026-08-26.md) · relevo [`traspaso-relevo-dex3-operational-incident-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex3-operational-incident-2026-08-26.md).

### DEX-2 — Crash/restart cross-PID (V1.13 Durable Execution)

- Certificación: store/sesión A persiste → kill → store B fresco → Confirm `UNKNOWN` · 0 re-POST · mismos ids / mapeo venue.
- Tests spine `test_dex2_crash_restart_cross_pid.py` (5). Spine **`pnpm test:decision-spine` = 440**.
- Sin Incident UI · sin Confirm split · sin pack v113.
- Plan [`plan-dex2-crash-restart-cross-pid-2026-08-26.md`](./docs/engineering/plan-dex2-crash-restart-cross-pid-2026-08-26.md) · relevo [`traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex2-crash-restart-cross-pid-2026-08-26.md).

### DEX-1 — PostgreSQL SubmitIntent (V1.13 Durable Execution)

- Alembic `013_submit_intents` + `SubmitIntentRow` + `PostgresSubmitIntentStore` (commit en put/delete).
- Fases `recorded` → `send_attempted` → `venue_bound`/`filled` + `send_attempted_at`; espejo TS.
- Confirm: put recorded → mark send_attempted → `adapter.submit`; fila durable ⇒ no re-POST.
- DI Confirm → store PG; InMemory en unit tests. Sin DEX-2 kill · sin Incident · sin Confirm split.
- Plan [`plan-dex1-pg-submit-intents-2026-08-26.md`](./docs/engineering/plan-dex1-pg-submit-intents-2026-08-26.md) · relevo [`traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md`](./docs/engineering/traspaso-relevo-dex1-pg-submit-intents-2026-08-26.md).

### Docs — Auditoría v1.12 → V1.13 Durable Execution (2026-08-26)

- Triage externo post-`v1.12-beta`: OR-2 **PARTIAL** (InMemory ≠ cross-PID). Tag `v1.12-beta` intacto.
- Roadmap V1.13 DEX-1…DEX-5 · plan DEX-1 PG `submit_intents` · relevo apertura.
- ADR-035 §8 post-audit · `CURRENT_SYSTEM` next = DEX-1 (cerrado en Unreleased DEX-1; DEX-2 cerrado → next DEX-3).

## [1.12-beta] — 2026-08-26

Operational Reliability v1.12 (D0 + OR-1…OR-6). Producto sigue **BETA / no producción**. Tag anotado **`v1.12-beta` → `369b5d1`** (Release tag CI GREEN). Partida: **`v1.11-beta` → `76d0f951`**. Spine **`pnpm test:decision-spine` = 433**. Pack: [`audit-pack-estado-global-2026-08-26-v112.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v112.md). Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. Confirm = única firma. Mesa default **paper**. LIVE **experimental**.

### OR-6 — SEMI operational certification (v1.12)

- Readiness discreto `PAPER_READY` / `PAPER_DEGRADED` / `LIVE_EXPERIMENTAL` / `LIVE_BLOCKED` (un FAIL crítico no se promedia; AUTO no entra).
- CTA firma `Ejecutar en PAPER|LIVE` + badge LIVE; chip mesa aparte del Autoeval OE-1.
- UI preferencia Paper|Live por cuenta (PA-1 API).
- Spine **`pnpm test:decision-spine` = 433** (post-OR-5 = 418).
- ADR-035 · plan [`plan-or6-semi-operational-certification-2026-08-26.md`](./docs/engineering/plan-or6-semi-operational-certification-2026-08-26.md) · relevo [`traspaso-relevo-or6-semi-operational-certification-2026-08-26.md`](./docs/engineering/traspaso-relevo-or6-semi-operational-certification-2026-08-26.md).
- **No** thaw estricto · **no** AUTO on · **no** Alembic · **no** `contract:gen`.

### OR-5 — Broker execution scenario suite (v1.12)

- Certificación spine A–L + retry (OR-1) + crash (OR-2) en `test_or5_broker_execution_scenarios.py`.
- Ancla en `pnpm test:decision-spine`. Paper/mock; sin live accepted; sin mass sim.
- Spine **`pnpm test:decision-spine` = 418** (post-OR-4 = 403).
- ADR-035 · plan [`plan-or5-broker-execution-scenario-suite-2026-08-26.md`](./docs/engineering/plan-or5-broker-execution-scenario-suite-2026-08-26.md) · relevo [`traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md`](./docs/engineering/traspaso-relevo-or5-broker-execution-scenario-suite-2026-08-26.md).
- **No** CTA LIVE (OR-6) · **no** Alembic · **no** `contract:gen` · **no** simulación 1k–10k.

### OR-4 — Reconciliation → opening veto (v1.12)

- `check_opening`: OI-6 `drift` → DENY aperturas; LR-1 `drift`/`unavailable` → DENY solo venue **live**; exits (`exit`/`exit_hint`/`reduce`) ALLOW.
- Confirm / Fill / HTTP gated / Router cablean puertos recon; fail-closed si lookup lanza. Sin auto-heal · sin UI resolución.
- OE-1: OI-6 status honesto (`ok`/`drift`/`error`/`unavailable`; ya no `not_wired` fijo).
- Spine **`pnpm test:decision-spine` = 403** (post-OR-3 = 387).
- ADR-035 · plan [`plan-or4-recon-opening-veto-2026-08-26.md`](./docs/engineering/plan-or4-recon-opening-veto-2026-08-26.md) · relevo [`traspaso-relevo-or4-recon-opening-veto-2026-08-26.md`](./docs/engineering/traspaso-relevo-or4-recon-opening-veto-2026-08-26.md).
- **No** suite A–L (OR-5) · **no** CTA LIVE (OR-6) · **no** Alembic · **no** `contract:gen`.

### OR-3 — Full order state machine (v1.12)

- `PaperOrderStatus`: `CREATED` | `SUBMITTED` | `ACK` | `PARTIAL` | `FILLED` | `REJECTED` | `CANCELLED` | `EXPIRED` | `UNKNOWN` + grafo `ALLOWED_TRANSITIONS` (PY/TS).
- PaperBroker: `CREATED` → `SUBMITTED` pre-send → `FILLED` ok; boom → `UNKNOWN` (no deja CREATED «como si no enviada»).
- Crash recovery OR-2: `paperOrder.status = UNKNOWN`. Campo opcional `filledQuantity` para PARTIAL.
- Spine **`pnpm test:decision-spine` = 387** (post-OR-2 = 382).
- ADR-035 · plan [`plan-or3-order-state-machine-2026-08-26.md`](./docs/engineering/plan-or3-order-state-machine-2026-08-26.md) · relevo [`traspaso-relevo-or3-order-state-machine-2026-08-26.md`](./docs/engineering/traspaso-relevo-or3-order-state-machine-2026-08-26.md).
- **No** veto recon (OR-4) · **no** suite A–L (OR-5) · **no** OCO · **no** `contract:gen`.

### OR-2 — Crash/restart recovery (v1.12)

- Confirm: `DurableSubmitIntent` persistido **antes** de `adapter.submit` (fail-closed si `put` falla).
- Sin fill local y con intento durable → `ExecutionRecord unknown` reconstruido (`crashRecovery`); **no** segundo `adapter.submit`.
- Mapeo `intent_id` ↔ `venue_order_id` (retry live `submitted` = 1 send). Fill local (OR-1) sigue ganando.
- Store = puerto + InMemory de proceso (sin Alembic). Tabla PG / Redis multi-worker parked en v1.12.
- **Post-audit `v1.12-beta`:** estado **PARTIAL** — no sobrevive al PID; PG = DEX-1 (V1.13).
- Spine **`pnpm test:decision-spine` = 382** (post-OR-1 = 372).
- ADR-035 · plan [`plan-or2-crash-restart-2026-08-26.md`](./docs/engineering/plan-or2-crash-restart-2026-08-26.md) · relevo [`traspaso-relevo-or2-crash-restart-2026-08-26.md`](./docs/engineering/traspaso-relevo-or2-crash-restart-2026-08-26.md).
- **No** OR-3 state machine · **no** veto recon (OR-4) · **no** `contract:gen`.

### OR-1 — End-to-end idempotency (v1.12)

- Confirm paper: clave canónica = `decision_id` (sin fallback `confirm-{uuid}`); sin `decision_id` → `error` / `decision_id_required` pre-send.
- `intent_id` / `PaperOrder.order_id` estables (`INT-{slug}` / `ORD-{slug}`) derivados de `decision_id`.
- Short-circuit pre-`adapter.submit` si ya hay fill local (`ExecuteTrade.find_existing_by_idempotency`); replay sin segundo submit ni journal `executed` duplicado.
- Spine **`pnpm test:decision-spine` = 372** (partida v1.11 = 367).
- ADR-035 · plan [`plan-or1-e2e-idempotency-2026-08-26.md`](./docs/engineering/plan-or1-e2e-idempotency-2026-08-26.md) · relevo [`traspaso-relevo-or1-e2e-idempotency-2026-08-26.md`](./docs/engineering/traspaso-relevo-or1-e2e-idempotency-2026-08-26.md).
- **No** Alembic · **no** `contract:gen` · **no** OR-2/OR-3/OR-4 en esta rebanada.

## [1.11-beta] — 2026-08-26

Operational Integrity v1.11 (OI-1…OE-1). Producto sigue **BETA / no producción**. Tag anotado **`v1.11-beta` → `76d0f951`** (Release tag CI GREEN). Partida: **`v1.10-beta` → `047ddb6`**. Spine **`pnpm test:decision-spine` = 367**. Pack: [`audit-pack-estado-global-2026-08-26-v111.md`](./docs/engineering/audit-pack-estado-global-2026-08-26-v111.md). Accept estricto **NO**. `PAPER_D_EXECUTE` default **OFF**. Confirm = única firma. Mesa default **paper**.

### OI-1 — Continuidad operativa (v1.11)

- **Manual trade:** `POST /portfolio/trade` y pending sin plan nacen PositionState con override `human_manual`.
- **Pending SELL / manual sell:** cierran o reducen Position persistida vía `post_fill_position_sync`.
- **Confirm honesty:** fill ejecutado no se reporta como error si falla persist/journal posterior (`positionPersist`).
- **Proteger:** Confirm persiste stop operativo (H2); botón «Confirmar protección»; cero ledger.
- **Lab:** `evaluate-exits` con `executeTrades` persiste exit si `trade_executed` (Lab ≠ mesa).
- ADR-034 · plan [`plan-oi1-continuity-2026-08-26.md`](./docs/engineering/plan-oi1-continuity-2026-08-26.md) · spine **273**.

### OI-2 — Risk signature honesty (v1.11)

- **SEMI opening:** `risk_signature` con `require_triggered_plan` — sin TradePlan TRIGGERED → `rejected_by_gate` / `no_tradeplan`.
- **Manual HTTP:** sin cambio (no pasa por `risk_signature`).
- **UI:** copy `no_tradeplan` en F3 risk block y supervised panel.
- Plan [`plan-oi2-risk-signature-honesty-2026-08-26.md`](./docs/engineering/plan-oi2-risk-signature-honesty-2026-08-26.md) · spine **274**.

### OI-3 — ExecutionRecord UNKNOWN ≠ ERROR (v1.11)

- **Confirm:** excepción de `execute_trade` → `trade.status=unknown` + `executionRecord.outcome=unknown` (nunca `error`, nunca `rejected_by_gate`).
- **Gate/skip** antes de enviar → `not_executed`. Fill OK + persist falla → `executed` (OI-1).
- **UI/HELP:** copy «no asumir que no se ejecutó».
- Plan [`plan-oi3-execution-record-2026-08-26.md`](./docs/engineering/plan-oi3-execution-record-2026-08-26.md) · spine **283**.

### OI-4 — PaperOrder CREATED→FILLED (v1.11)

- **Confirm / FillPending:** al enviar nace `paperOrder` CREATED; fill → FILLED. Gate/skip → no hay orden. Excepción de envío → CREATED (fill no confirmado).
- **UI/HELP:** CREATED ≠ FILLED; orden creada no es fill. Venue PAPER ≠ broker.
- Plan [`plan-oi4-order-lifecycle-2026-08-26.md`](./docs/engineering/plan-oi4-order-lifecycle-2026-08-26.md) · spine **291**.

### OI-5 — Position revisions (v1.11)

- **PositionRevision:** historia append-only de stop/status en `PositionState.revisions` (JSON snapshot).
- **applyCurrentStop / applyReduce:** append solo si hay cambio real; mark no; protect → `origin=protect`.
- **UI/HELP:** stop/status con historia auditada; Proteger deja huella.
- Plan [`plan-oi5-position-revisions-2026-08-26.md`](./docs/engineering/plan-oi5-position-revisions-2026-08-26.md) · spine **306**.

### OI-6 — Portfolio reconciliation (v1.11)

- **PortfolioReconciliation:** detect/report cash ↔ ledger ↔ holdings ↔ PositionState (OPEN). Add-on / holding sin OPEN → `expected`.
- **No** auto-heal · **no** broker · **no** Alembic · ≠ ADR-021 DÍA D.
- Use-case `ReconcilePortfolioIntegrity` + spine tests.
- Plan [`plan-oi6-reconciliation-2026-08-26.md`](./docs/engineering/plan-oi6-reconciliation-2026-08-26.md) · spine **317**.

### PaperBroker — venue PAPER (v1.11)

- **PaperBroker.submit:** CREATED → ledger fill → FILLED; excepción → CREATED + `unknown`.
- Confirm / FillPending adjuntan `paperOrder` + `paperBroker` (`venue: PAPER`, ≠ broker live).
- **No** `IBrokerAdapter` · **no** broker live · **no** thaw `PAPER_D_EXECUTE`.
- Plan [`plan-paperbroker-2026-08-26.md`](./docs/engineering/plan-paperbroker-2026-08-26.md) · spine **322**.

### BrokerAdapter — puerto Paper | Live (v1.11)

- **IBrokerAdapter:** Confirm / FillPending envían por el puerto (default paper = PaperBroker).
- **Mock LIVE:** `not_wired` — nunca llama `execute_trade` (≠ broker live / XTB).
- Receipt `brokerAdapter` (`venue: PAPER|LIVE`). Gate/skip → sin receipt.
- **No** live · **no** thaw `PAPER_D_EXECUTE`.
- Plan [`plan-brokeradapter-2026-08-26.md`](./docs/engineering/plan-brokeradapter-2026-08-26.md) · spine **331**.

### PH-1 — Confirm protect honesty (v1.11)

- **Proteger:** si H2/`persist` → `None` (o excepción), Confirm no dice `protect_applied`. `skipped` / `stop_not_applied`. Cero ledger: el éxito es persistir.
- **UI:** log «stop no aplicado»; no saca de cola ni graba mandato.
- Plan [`plan-confirm-protect-honesty-2026-08-26.md`](./docs/engineering/plan-confirm-protect-honesty-2026-08-26.md) · spine **334**.

### XL-1 — Broker live XTB (v1.11)

- **XtbBrokerAdapter:** `venue: LIVE`, `adapter: xtb`; POST bridge `/orders`.
- Fail-closed: mock `live_orders_disabled`; `submitted` ≠ fill.
- Confirm/FillPending: rejected→skipped; submitted→unknown `live_submitted_no_fill`; pending intacta.
- **No** thaw `PAPER_D_EXECUTE` · mesa default paper.
- Plan [`plan-broker-live-xtb-2026-08-26.md`](./docs/engineering/plan-broker-live-xtb-2026-08-26.md) · spine **341**.

### LR-1 — Live reconciliation (v1.11)

- **LiveLedgerReconciliation:** live cash/positions ↔ ledger; `clean`/`drift`/`unavailable`.
- Detect/report only · **no** heal · **no** trade · bridge `GET /account/cash|positions`.
- Plan [`plan-lr1-live-reconciliation-2026-08-26.md`](./docs/engineering/plan-lr1-live-reconciliation-2026-08-26.md).

### XL-2 — XTB fill → ledger (v1.11)

- Bridge `filled` (opt-in FILL) → `execute_trade` → Confirm/FillPending `executed`.
- `submitted` sigue ≠ fill · boom → `unknown` (OI-3).
- Plan [`plan-xl2-xtb-fill-ledger-2026-08-26.md`](./docs/engineering/plan-xl2-xtb-fill-ledger-2026-08-26.md).

### VS-1 — Venue selector Paper | Live (v1.11)

- `BROKER_VENUE` + runtime · DI Confirm/FillPending · mesa toggle Paper|Live.
- Live → Xtb (sin URL → `not_wired`) · default paper · ≠ thaw `PAPER_D_EXECUTE`.
- Plan [`plan-vs1-venue-selector-2026-08-26.md`](./docs/engineering/plan-vs1-venue-selector-2026-08-26.md) · spine **362**.

### RV-1 — Redis persist broker venue (v1.11)

- Key `bolsa:risk:broker_venue` · coalesce `memory ?? redis ?? env ?? paper` · DI async.
- Per-account venue **parked**. Plan [`plan-rv1-redis-venue-2026-08-26.md`](./docs/engineering/plan-rv1-redis-venue-2026-08-26.md).

### JP-1 — PositionState JSONB → columnas hot (v1.11)

- Alembic `012`: `direction` · `current_stop` · `remaining_quantity` · `quantity` · `initial_stop` · `actual_entry`.
- Dual-write + backfill; JSONB `position_state` sigue SoT. Plan [`plan-jp1-position-jsonb-columns-2026-08-26.md`](./docs/engineering/plan-jp1-position-jsonb-columns-2026-08-26.md).

### Thaw stamp — `PAPER_D_EXECUTE` DEMO opt-in (v1.11)

- Docs/ops: DEMO opt-in **autorizado**; repo default **OFF**; ≠ venue Live · ≠ thaw estricto P1–P5.
- Plan [`plan-thaw-paper-d-execute-stamp-2026-08-26.md`](./docs/engineering/plan-thaw-paper-d-execute-stamp-2026-08-26.md).

### PA-1 — Preferencia venue por cuenta (v1.11)

- `settings_json.brokerVenue` (`paper`|`live`); coalesce `memory ?? redis ?? account ?? env ?? paper`.
- Lazy Confirm/Fill; mesa/API risk = override **global**. UI preferencia cuenta **opcional**.
- Plan [`plan-pa1-per-account-venue-2026-08-26.md`](./docs/engineering/plan-pa1-per-account-venue-2026-08-26.md).

### OE-1 — Ops Autoeval SEMI·AUTO (v1.11)

- `GET /api/risk/ops-self-eval` + `scripts/ops_operativa_self_eval.mjs` + chip mesa. Measure ≠ Accept.
- Recon OI-6 en informe `not_wired`. Plan [`plan-oe1-ops-autoeval-2026-08-26.md`](./docs/engineering/plan-oe1-ops-autoeval-2026-08-26.md).

## [1.10-beta] — 2026-08-25

Operational Authority v1.10 (H1→P4 Consola de Mesa P4.1+P4.2). Producto sigue **BETA / no producción**. Tag anotado **`v1.10-beta` → `047ddb6`** (Release tag CI GREEN). Partida: **`v1.9-beta` → `7d90d965`**. Spine **`pnpm test:decision-spine` = 260**. Shared **156**. Pack: [`audit-pack-estado-global-2026-08-25-v110.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v110.md). **No** broker · **No** auto-exit CTA producto · thin 5.x/8.x congelados · Confirm = única firma.

### P4 — Consola de Mesa (P4.1 + P4.2)

- Operaciones enriquecido (R, stop, T1/T2, salida advisory); CTAs Revisar/Reducir/Salir → cola Confirm; barra operativa; cola entradas read-only; «No operar hoy» → Journal; barra estado global; filtros cola; Proteger + preview stop en Confirm.
- Plan: [`plan-p4-consola-mesa-2026-08-25.md`](./docs/engineering/plan-p4-consola-mesa-2026-08-25.md) · ADR-033 §7.

### P3 — Una cadena de salida

- Confirm SEMI `exit_hint`/`reduce`: ExitPlan (`manual`) → ExitPermission → fill. Motivo `exit_permission`. Persist `applyReduce`. Operaciones: columna Salida advisory (sin CTA). Lab `evaluate-exits` intacto.
- Plan: [`plan-p3-cadena-salida-2026-08-25.md`](./docs/engineering/plan-p3-cadena-salida-2026-08-25.md) · ADR-033 §4.

### P2 — Riesgo al firmar

- Ticket F3: qty/stop/pérdida €/R del TradePlan TRIGGERED. % caja deja de ser SoT. Override con motivo. Gate Confirm `risk_signature`.
- Plan: [`plan-p2-riesgo-al-firmar-2026-08-25.md`](./docs/engineering/plan-p2-riesgo-al-firmar-2026-08-25.md) · ADR-033 §6.

### P1 — Position durable + wire fill

- Alembic `011`: tabla `position_states` (snapshot TradePlan + PositionState + `open_transaction_id`). Ledger `positions` intacto.
- Wire: Confirm SEMI apertura y FillPendingOrder (si hay snapshot) → `from_fill` (H2). Operaciones muestra stop / T1 / T2.
- Plan: [`plan-p1-position-durable-2026-08-25.md`](./docs/engineering/plan-p1-position-durable-2026-08-25.md) · ADR-033 §2.

### H2 — Invariantes factories

- Guards ADR-033 §5 en factories TS+Py: `from_fill` exige TRIGGERED (o override); stop no empeora; T2 no ataja T1; short close=`buy`; kill switch asimétrico.
- Cero Alembic · cero wire Confirm · cero UI mesa.
- Plan: [`plan-h2-invariantes-factories-2026-08-25.md`](./docs/engineering/plan-h2-invariantes-factories-2026-08-25.md) · ADR-033.

### H1 — Honesty pending ≠ stop

- UI/HELP: «Orden pendiente a precio» (antes Stop/Limitada). Solo `limitPrice`; no es stop de posición.
- Plan: [`plan-h1-honesty-pending-2026-08-25.md`](./docs/engineering/plan-h1-honesty-pending-2026-08-25.md) · ADR-033.

### Docs — Operational Authority v1.10 (D0)

- Triage auditoría de discontinuidad decisión→posición: factories F1–F4 ≠ autoridad viva; ADR-033 + roadmap v1.10.
- [ADR-033](./docs/adr/033-operational-authority-position-persistence.md) docs-only · [roadmap v1.10](./docs/engineering/roadmap-v110-operational-authority-2026-08-25.md) · fase v1.10 cerrada en tag.

## [1.9-beta] — 2026-08-25

Operational Core v1.9 (modelo post-entrada) + INFRA CI-by-tag. Producto sigue **BETA / no producción**. Tag anotado **`v1.9-beta` → `7d90d965`**. Partida: **`v1.8.1-beta` → `e78fbb9`**. Spine **`pnpm test:decision-spine` = 217**. Shared **134**. Pack: [`audit-pack-estado-global-2026-08-25-v19.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v19.md). **No** broker · **No** auto-exit producto · thin 5.x/8.x congelados.

### ExitPermission (Operational Core)

- Gate puro `checkExitPermission` / `check_exit_permission` (TS + Py): ALLOW/DENY post-ExitPlan.
- Reasons: `not_actionable` · `position_closed` · `kill_switch` · `broker_not_allowed` · `paper_auto_env_blocked` · `execution_blocked` · `missing_exit_plan`.
- **≠** `check_opening` · **≠** auto-exit · **≠** ExecuteTrade · sin wire Confirm / EvaluatePositionExits.
- Plan: [`plan-exit-permission-2026-08-25.md`](./docs/engineering/plan-exit-permission-2026-08-25.md).

### INFRA — CI reproducible por tag

- Workflow [`.github/workflows/release-tag-ci.yml`](./.github/workflows/release-tag-ci.yml): `on: push tags v*` **sin** path-filter + `workflow_dispatch`.
- Gates: gitleaks · shared · `test:decision-spine` · frontend · python offline · job `certify` + artefacto summary.
- Path-filters diarios (`frontend-ci` / `python-ci`) **intactos**.
- Plan: [`plan-infra-ci-by-tag-2026-08-25.md`](./docs/engineering/plan-infra-ci-by-tag-2026-08-25.md).

### F4 — ExecutionPlan → PAPER (Operational Core)

- Objeto nuevo `ExecutionPlan` (TS + Py): factory `buildExecutionPlanFromExitPlan` / `build_execution_plan_from_exit_plan`.
- `venue: PAPER` · status `DRAFT`/`PAPER_READY`→`JOURNALED`→`REPLAYED`→`VALIDATED` · broker → `BLOCKED`.
- Stages puros (refs opcionales, sin I/O). **No** ExecuteTrade · **No** `PAPER_D_EXECUTE` on · **No** OCO.
- Plan: [`plan-f4-execution-plan-paper-2026-08-25.md`](./docs/engineering/plan-f4-execution-plan-paper-2026-08-25.md).

### F3 — ExitPlan (Operational Core)

- Objeto nuevo `ExitPlan` (TS + Py): factory `buildExitPlanFromPosition` / `build_exit_plan_from_position`.
- Razones canónicas · status `IDLE`/`HINT`/`ARMED`/`TRIGGERED`/`DONE` · `suggestedAction` advisory.
- Plan: [`plan-f3-exit-plan-2026-08-25.md`](./docs/engineering/plan-f3-exit-plan-2026-08-25.md).

### F2.1 — PositionState transitions

- API pura `applyMark` / `applyReduce` / `applyCurrentStop` (TS + Py).
- Plan: [`plan-f2-1-position-state-transitions-2026-08-25.md`](./docs/engineering/plan-f2-1-position-state-transitions-2026-08-25.md).

### F2 — PositionState (Operational Core)

- Factory `build_position_state_from_fill` / `buildPositionStateFromFill` → `OPEN`.
- Plan: [`plan-f2-position-state-2026-08-25.md`](./docs/engineering/plan-f2-position-state-2026-08-25.md).

### F1 — TradePlan v1 (Operational Core)

- Campos gap ADR-032 §1 **dentro** de TradePlan.
- Plan: [`plan-f1-tradeplan-v1-2026-08-25.md`](./docs/engineering/plan-f1-tradeplan-v1-2026-08-25.md).

### Docs — auditoría externa v1.8.1 + diseño v1.9

- Consolidación v1.8.1 **cerrada** por auditoría externa. Triage: [`audit-ext-v181-triage-2026-08-25.md`](./docs/engineering/audit-ext-v181-triage-2026-08-25.md).
- ADR-032 + gap + roadmap v1.9. **F1–F4 + ExitPermission + INFRA** en este tag; broker adapter sigue no.

## [1.8.1-beta] — 2026-08-25

Operational Consolidation post-`v1.8.0-beta`. Producto sigue **BETA / no producción**. Tag anotado **`v1.8.1-beta` → `e78fbb9`**. Partida: **`v1.8.0-beta` → `8c8b789`**. Spine battery **`pnpm test:decision-spine` = 161**. Pack: [`audit-pack-estado-global-2026-08-25-v181.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v181.md). **No** módulos thin nuevos. **No** PositionState/ExecutionPlan (ADR-032 docs-only).

### Ciclo C4 — TradePlan shape canónico

- Hoy `readCanonicalTradePlan`: canónico sesiones = `session.tradePlan`; F3 = `extra.payload.tradePlan`. Fallbacks (`extra.tradePlan`, payload top-level) marcados `legacy`, no borrados.
- `HoyQueueItem.planSource`: `live` (objeto TradePlan en canónico o fallback permitido) | `projection` (sin plan → C1 WATCH, nunca BUY/ARMED).
- **No** Pydantic DTO · **no** OpenAPI · **no** `contract:gen` (contrato fuerte = ADR-032 / v1.9). Confirm/propose/spine/`check_opening` intactos. C1/C3/C5 intactos.

### Ciclo C5 — MFE/Expectancy honesty

- `MfeMae.source`: `bars` | `close_proxy` | `none`. Hoy Excursión añade sufijo `proxy` si close_proxy. Proxy no se presenta como peak de barras.
- Expectancy `sampleQuality`: insufficient (n<20) / preliminary (20–49) / developing (50–99) / useful (n≥100). `status: ready` (READY_MIN_N=5) no significa estadísticamente útil.
- UI Expectativa: «muestra insuficiente (n=…)» antes de E±R si insufficient. Sigue `≠ permiso`. Parsers `asMfeMae` / `asExpectancy` fail-soft.
- Advisory ≠ permiso. **No** mezclar proxy y bars en agregados futuros. Sin journal histórica.

### Ciclo C3 — ActionQueue

- `buildActionQueue(board)` devuelve la cola completa ordenada (prioridad D2 + `actionability` del plan vivo; dedup por símbolo post-sort).
- Hoy (`mapDecisionBoardToHoyQueue`, default 8) es un **slice** de esa cola, no una agregación que corta a 8 antes de ordenar. C1 intacto: sin TradePlan vivo → WATCH (nunca BUY/ARMED inventados). Sin HTTP ActionQueue.

### Ciclo C2 — Alembic única autoridad

- Públicos `pnpm db:push` / `db:migrate` / `db:migrate:deploy` fail-closed (`Prisma schema is not authoritative. Use Alembic.`).
- Bootstrap (`setup` / `db-ensure` / `db-check`) aplica schema vía `ensure_migrated`. Prisma queda seed + `db:generate`. ADR-025 enmendado.

### Docs

- ADR-032 Operational Core (v1.9 contrato, **docs-only**, no implementado): TradePlan / PositionState / ExecutionPlan. Thin congelados. NO TRADE first-class.

### Ciclo C1 — Hoy honesty + HELP (v1.8.1 P0)

- Hoy: F3/sesión **sin** TradePlan vivo → `WATCH` (nunca BUY/ARMED heurístico). BLOCKED/WATCH de proyección → `whyNot: legacy_projection` (no `fit` ficticio).
- Ayuda: `HELP_CONTENT_AS_OF = 2026-08-25` — AUTO BETA-D (`ACTIVAR AUTO` + `PAPER_D_EXECUTE` opt-in), Decision Spine, TradePlan, Hoy proyección.
- Roadmap consolidación: [`roadmap-v181-operational-consolidation-2026-08-25.md`](./docs/engineering/roadmap-v181-operational-consolidation-2026-08-25.md). **No** módulos thin nuevos.

## [1.8.0-beta] — 2026-08-25

Post-`v1.7.0-beta` spine growth + integrity + Camino D thaw parcial. Producto sigue **BETA / no producción**. Tag anotado **`v1.8.0-beta` → `8c8b789`**. Partida: **`v1.7.0-beta` → `e3b943a`**. Spine battery **`pnpm test:decision-spine` = 159**.

### Decision Spine — TradePlan / mesa / journal

- TradePlan v0 + Ciclos **4.0–4.9** (stop ATR/swing, EntrySetup, ARMED, Wyckoff formal→effort, Board echo).
- Ciclos **5.0–5.3** thin: Thesis Health · Protect/T1 · Exit Radar · MFE/MAE (advisory; ≠ permiso).
- Ciclo **6** Attribution journal thin · Ciclo **7** Spine honesty.
- Ciclos **8.0–8.2** thin: Expectancy · Trail · Bracket (advisory; sin OCO/broker). **Línea crecimiento thin CERRADA.**

### Integridad execute / honesty

- **I1** ExecuteTrade converge (`check_opening` en buy HTTP).
- **I2** Actionability / Indice Operativo server.
- **I3** Shadow honesty — HTTP `paper_auto` exige `PAPER_D_EXECUTE`.
- **RX1** exits `full_auto` honesty — mismo env gate antes del Router. **No** auto-exit producto.

### Thaw Camino D (ADR-023)

- Medición estricta P1–P5 **FAIL** · perfil **BETA-D Accepted** (P1'–P5' + W2–W4).
- UI Libro AUTO on · execute **opt-in** `PAPER_D_EXECUTE=1` (default repo off).
- **A3-wire** (`d704263`): frase exacta `ACTIVAR AUTO` obligatoria antes de `mode:auto`; disarm al salir. Arm ≠ execute.
- Deuda estricto tracking: runbook + `scripts/thaw_estricto_snapshot.mjs` (W2–W4 vigentes).

### Ops / docs

- `TRUSTED_PROXIES` runbook exact-string · valor prod **OWNER**.
- Pack auditoría: [`audit-pack-estado-global-2026-08-25-v180.md`](./docs/engineering/audit-pack-estado-global-2026-08-25-v180.md).

## [1.7.0-beta] — 2026-08-24

Ciclo post-`v1.6.0-beta` (Decision Spine + mesa U0–U6 + gates DS-05/DS-03 + ops + copy Research→Radar). Producto sigue **BETA**. Tag anotado **`v1.7.0-beta`** (pendiente de crear por coordinador sobre commit de stamp). Partida: **`c3964fc`**. Tags `v1.6.0-beta` / `v1.5.0-beta` / `v1.3.0` intactos.

### Track B — split backtests + nav Señales (heredado post-R-13)

- **F4′–F6′** (`240c846`): copy nav **Señales** (`/screeners`); tests href B0; herencia R-13 Track B desbloqueado.
- **B1–B12**: extracción incremental de `backtests-page.tsx` (~4698→321 LOC shell) — constantes/tipos, queries, mutations, derivados, URL sync, navegación, Lista AUTO, play cycle, Lab handlers, tabs run/jobs, `useBacktestPageModel`. Sin cambio de comportamiento; smoke manual backtests sigue recomendado.

### Fase 0 Decision Spine (código + docs)

- **F0.5b** (`3670a09`): PortfolioFit v1 — concentración cesta activo+sector, VETO fail-closed; `MaxSectorExposure` cableada.
- **F0.6b + F0.6-UI** (`8df8a65`, `672e88f`): Decision Board v1 backend + UI solo lectura (`/decision-board`).
- **D1/D2/D3**: risk cesta SEMI=AUTO (`7530556`); DecisionPackage contrato en confirm SEMI (`f7b1f6c`); Lab/Radar **fuera** del spine (`ea0c93f`, ADR-019).
- **Confirm SEMI deuda** (`2281903`): `wait` sin sesión ya no ejecuta sell default; side de `exit_hint`/`reduce` desde package.
- **Prove Spine** (`5e81350`): S0–S3, tests `pnpm test:decision-spine`, golden scenario.
- **H5** (`f56af2f`): perfil inversor SEMI → `check_opening` (mismo SoT AUTO).

### UX mesa U0–U6

- **U0–U4** (`6f26f9d`): tips Ayuda, presets S/R, Confirm drawer, chips Fit.
- **U5** (`04e441e`): proyección orden F3 en chart (post-SEMI preview).
- **U6** (`9e9a346`): preview ticket en Confirm/drawer — notional, comisión, margen (UI-only; sin bypass execute).

### Spine residual — gates en `check_opening`

- **DS-05** (`15e86a4`): Data Freshness Gate fail-closed (umbral 5×24h; SEMI ohlcv + AUTO `signal.timestamp`; exits fuera).
- **DS-03** (`41adb8e`): Account Mandate Gate fail-closed (tenure BD `mandate_tenures`; mismatch estrategia AUTO; exits fuera). Batería `pnpm test:decision-spine` **53**.

### Ops (ejecutable + propietario)

- **Ops residual** (`3c53f4e`…`7363ec6`): saneo símbolos `/` en import índices; fix 404 recurrente `BP.L`; re-sync `idx-ftse100` verificado; backup corrupt drop.
- **Ops propietario** (`5100d23`): secret scanning + push protection enabled vía API; runbook `TRUSTED_PROXIES` prod (valor real sigue en propietario).
- **Higiene dev** (`ea9a985`, dato local `bolsa_v1`): script `cleanup_dev_test_residues.py`; 3 cuentas huérfanas R8C eliminadas; `verify_ledger_balance_chain.py` **EXIT 0**.

### Research→Radar copy (UI)

- CTAs y cross-links **Asesor** (`/research`) vs **Señales** (`/screeners`); helpers `asesorHistoryHref`; sin fusión de páginas ni rutas API. Hereda F4′–F6′. Batería: `daily-nav.test.ts` 8/8.

## [1.6.0-beta] — 2026-08-22

Consolidación BETA post-R-12 (ciclo R-13). Producto sigue **BETA**. Tag anotado **`v1.6.0-beta` → `c3964fc`**. Tags `v1.5.0-beta` / `v1.3.0` intactos. Plan: `docs/engineering/plan-r13-consolidacion-beta-2026-08-22.md`.

### R-13 consolidación (docs + E8 micro)

- Cierre de R-12 como ciclo de reparación. Firma de partida R-13: `origin/main` **`5edbcb5`** (histórica) → **`c3964fc`** (A0–A3). README alineado a **v1.6.0-beta**. Track B producto (god-page / Research→Radar) **bloqueado**.
- A2: tests de contrato/ausencia en `chart-new-tab-setup.test.ts`; **purge** de `normalizeChartNewTabSeed` (0 callers). `extractChartNewTabSeed` / `applyChartNewTabSeed` intactos. Pending-delete alto **sin purge**.

### Auth D4 / JWT (incluido en release; commits post-`v1.5.0-beta`, ya en `main`)

- **R12-ACCOUNTS** (`3c958f1`) paquete `bolsa_application/accounts/`
- **R12-AUTH F1–F3** stamp owner + 404 cuenta ajena + cash/trade scoped
- **F4** ADR-027 Opción C **Aceptado** · **F5–F7a** tabla `users` + JWT + list/get scoped · **F8–F8e** perfiles, trackers, policies, events, workspaces, list-for-list
- **F9** FE login campo `login` opcional · **F10** `session_version` + `/auth/refresh` + rate-limit user
- **F7b** script + apply **local** (103→0 NULL; no prod) · **JWT-only** (`tokens.py` eliminado; SHA-256/HMAC → 401)
- **F7c** match estricto `user_id == principal` · `scan.completed` `ownerUserId` · cron stamp `tracker.user_id`
- Pending-delete E8 tests (`851b545`) · purge V2 métricas T+0 19/19 (**E8 N, sin purge**)

## [1.5.0-beta] — 2026-08-22

R-12 Track C (mesa SEMI frontend) + copy E8 residual + leftover CORE-R + tres gates de contrato/ejecución/workers. Producto sigue **BETA**. Tag anotado **`v1.5.0-beta` → `5e52bd6`**. Tag `v1.3.0` → `b778292` intacto. Plan: `docs/engineering/plan-r12-auditoria-ux-2026-08-21.md`.

### Track C + higiene copy

- Track C **C1** (`5bc51ff`): ruta `/confirm`, nav Confirmar con badge de cola, `openHelpAiPlatform({ panel: "supervised-f3" })` navega SPA (no Ayuda)
- Track C **C2** (`01af9ff`): nav diaria Trading · Señales · Confirmar vs Laboratorio / Asesor; hub Señales; copy Universo en vigilancia
- Track C **C3** (`97e20ab`): AUTO de cuenta «No disponible (BETA)»; copy de mesa sin `PAPER_D_EXECUTE`; execute sigue congelado
- Track C **C4** (`154fcd1`): nav **Libro** (Operaciones + Historial); cabeceras «Libro · …»; sin fusionar páginas
- Track C **C5** (`0eb8976`): HELP + Ayuda sync Confirm `/confirm` · Señales/Libro · AUTO BETA · frase SEMI
- Copy E8 residual (`ce601c9`) + leftover CORE-R (`8dd3caf`): CTAs de firma → `/confirm` dejan de decir Ayuda; atajos list-hub `/screeners` = Señales (Laboratorio); leftover CORE-R Proponer F3 ya en Confirmar

### Gates cerrados

- **R12-409 B1** (`eb24608`): declarar HTTP 409 en OpenAPI para conflictos de `idempotency_key` en deposit/withdraw/trade (`{detail: str}`); regen acotada `openapi.json` + `schema.d.ts`; runtime handler sin cambio
- **EXEC-B-CONC** (`ca60d0a`): `ExecuteTrade` deriva `balance_after` trade/fee desde cash post-lock (`result.summary.portfolio.cash`); elimina lectura pre-lock `get_summary`; chaos refuerza invariante B estricta bajo concurrencia
- **R12-SCHED / R-8C.2** (`5e52bd6`): scheduler = crons only; poll no-ARQ → `bolsa-queue-poll-worker`; ARQ → `bolsa-arq-worker` (queue_poll no-op); `run-dev.mjs` spawnea el proceso correcto según `SCAN_QUEUE_BACKEND`

### Contexto R-12 previo (Track A+B)

- Firma de estado: **GitHub `origin/main`**; implementación Track A+B `48cc255`; partida R-12 `f7a86cc`; premisas esenciales del ciclo R-12
- Alineación documental: README `v1.3.0 BETA`; tag `v1.3.0` → **`b778292`**
- Tests/scripts de verificación residuales (DEFAULT_PORTFOLIO, invariantes C–E, retry HTTP)
- Inventario `pending-delete` (sin purge) + higiene E8 + estudio UX comparativo (Track B **aprobado**, mesa 5 puertas)

## [1.3.0] — 2026-08-21

Endurecimiento del núcleo financiero y del gate CI apuntado por la **auditoría externa sobre v1.2.1** (R-11: C1–C5, C6, D1, D2 — todas cerradas) + deuda de datos/código residual cerrada tras el cierre de R-11. Documenta la política de cargo de custodia (C6) y deja `verify_ledger_balance_chain.py` en **EXIT 0 global**. Tag: `v1.3.0` sobre **`b778292`** (cierre documental; padre `deafa27` = fix test + verify EXIT 0). DEMO / paper; sin broker live.

### Post-R-11 (deuda §3 del traspaso, cierre de release)

- **Test** (`deafa27`) `test_execute_trade_con_fees_reconcilia` corregido: `ExecuteTrade.execute(...)` pide `idempotency_key` (R-10 F1 / R-11 C2); se añade `f"trade-{uuid4().hex[:8]}"` (deuda ajena a R-11, no regresión de gate). Batería coordinador: `test_m2` 7 passed 1 xfailed
- **Dato dev** (fuera de repo) cuenta de simulación huérfana `acc_broken_72ab7c2aa881` ("R8C broken", única de 111 que fallaba la cadena `balance_after` por +0.01 float legacy) **eliminada por path canónico** `close_account`→`delete_simulated_account` (coherente con R-10 F3-sim; **D6 prohíbe backfill** por eso no se reescribió `balance_after`) → `verify_ledger_balance_chain.py` **EXIT 0**

### R-11 — Endurecimiento post-v1.2.1 (C1–C6 + D1 + D2 cerradas a `main`)

- **C1** (`c3327c1`) Custodia **multi-periodo** (R-10.6): tabla `custody_obligations` PK `id` autoincremento + `UNIQUE(account_id, period)` + `created_at`/`updated_at`; migración Alembic `006_custody_obligations_period` (encadena sobre `005`); `upsert` reparado para **no sobrescribir** + `get_pending_by_account`/`get_by_account_period`; `ApplyCustodyFees`/`RunCustodyJob` liquidan primero el PENDING más antiguo antes del periodo nuevo
- **C2** (`17a1107`) **Idempotency_key end-to-end** (R-10.7): DTOs `DepositCashDto`/`WithdrawCashDto`/`TradeRequestDto` con `str_strip_whitespace=True`, `min_length=16`, `max_length=128`; repo `execute_trade` con `idempotency_key: str` obligatoria + rechazo de `""`/whitespace; guard en `ConfirmRecommendationIntent` (uuid4 fallback)
- **C3** (`cda26e9`) **Precisión Decimal end-to-end** (R-10.8): en `ExecuteTrade.execute` `notional`/`cash_before`/`amount`/`trade_balance`/`fee_balance` en `Decimal`, `float` solo en el borde al invocar repo/ledger; invariante secuencial exacta
- **C4** (`157bb45`) `contract:check` **EXIT 0** (R-10.9, Opción A): regen acotada de `apps/web/api/openapi.json` — `idempotencyKey` con `minLength/maxLength` + `TaxProfileDto` con `minimum:0.0`; `schema.d.ts` sin cambio; el 409 sigue solo en runtime (handler global), no en OpenAPI (decisión Opción A)
- **C5** (`6762614`) **`mypy` == 0 en gate CI** (R-10.9): añadida `packages/py/application/src` al step Mypy de `.github/workflows/python-ci.yml`; limpiados **105 errores en 33 ficheros** de la capa application; semántica mínima en `ledger_repository` (`limit: int|None=50`), `market_indices`, `fetch_core_r_pnl_extra_rows` (guard numérico) y `scans.py` (fix de `TypeError` latente: `expected_last_daily_bar()` sin el `exchange` obligatorio; ahora por instrumento)
- **C6** (docs, 2026-08-21) Política de cargo de custodia **`custody_charge_source = DEFAULT_PORTFOLIO`** documentada en ADR 026: la custodia es obligación de cuenta (importe sobre **equity agregado**) pero se cobra **exclusivamente desde la cartera seleccionada/default** (`scope.portfolio`, fallback `is_default`); sin transferencia implícita entre carteras — **solo documenta la regla, sin cambio de comportamiento**
- **Batería global R-11** (verificada por el coordinador): mypy gate `344 files` EXIT 0 · mypy application `95 files` EXIT 0 · ruff 0 · pytest application+market `388` · pytest api-python offline `84`
- **D2** (`db95709`, con C6) **Cierre documental**: docstrings aditivos en `ApplyCustodyFees.execute`/`ExecuteTrade.execute` (accounts.py, 14 ins, 0 lógica) · estado documental en PROJECT_STATE/backlog/index/plan/ADR 026/CHANGELOG
- **D1** (`870fb21`) **Limpieza transversal E8**: `custody_obligation_repository.get_by_account` + `get_by_account_period` (0 callers producción; el segundo nunca se cableó a `ApplyCustodyFees`/`RunCustodyJob`) quitados del repo y de fakes de test · se mantienen `get_pending_by_account`/`upsert` · **sin tocar ítems RIESGO ALTO** · batería D1: ruff 0 · mypy repo gate 0 · pytest custodia 7 · pytest application 279

## [1.2.1] — 2026-08-21

Correcciones de la **auditoría externa post‑v1.2.0** (R-10, F1–F5). Refuerza el núcleo financiero detectado en la pasada: `balance_after` secuencial, custodia con obligación pendiente y fuera del GET, DTOs estrictos, idempotencia exacta y `idempotency_key` obligatoria. DEMO / paper; sin broker live.

### R-10 — Correcciones de la auditoría externa (cerrada, F1–F5)

- **F1** `idempotency_key` **obligatoria** en deposit/withdraw/trade (422 si falta) + contrato/regen OpenAPI y ajuste de consumidores web
- **F2a** `TaxProfileDto` estricto (Pydantic fail-fast 422): `ge=0`, `allow_inf_nan=False`, `fiscal_year_start_month ∈ [1,12]`
- **F2b** Comparación idempotente **exacta normalizada a `Numeric(18,6)`** (eliminada la tolerancia de `0.01`)
- **F3** `balance_after` de trade+fee **secuencial por fila** (cash FINAL ya no en ambas), sin backfill (forward-only)
- **F4a** Custodia **Opción B con obligación pendiente** (tabla `custody_obligation`, `PENDING`/`APPLIED`, ADR 026, migración `005`): si `cash < fee` no descuenta ni marca DONE — registra `PENDING` y cobra el total cuando haya saldo
- **F4b** Custodia **fuera del GET** → job periódico `RunCustodyJob` (scheduler/worker); `GetAccountSummary`/`GetTaxReport` quedan **100% de solo lectura** (desfase de saldo pre‑custodia aceptado mientras corre el job). **Reabre `M-4/T-M4`** (job de custodia dedicado)
- **F5** Cierre: docs de estado (backlog, PROJECT_STATE, engineering-index, plan-r10) + CHANGELOG `[1.2.1]` + limpieza E8 inventariada

### Pendientes de decisión (no bloquean cierre)

- Contrato F2/F4: exponer el 409 + DTOs estrictos en OpenAPI (`contract:gen`) — pendiente
- `pending-delete` riesgo alto (no tocar hasta `purge storage`) · **R-8C.2 scheduler-vs-worker** · gobernanza IA
- **`M-4/T-M4` REACTIVADO y CERRADO por R-10 F4b** (`e12a125`) — la custodia ya es un job dedicado, no muta en GET

### Operativo (FUERA de repo)

- GitHub secret scanning · `TRUSTED_PROXIES` prod · registro BD `BP/.L`→`BP.L` · limpiar `logs/dev`

## [1.2.0] — 2026-08-20

Refactorización y corrección R-7 / R-8 / R-9 completadas (hardening financiero + limpieza + contrato). DEMO / paper; sin broker live.

### R-9 — Núcleo financiero determinista (cerrada, F1–F8)

- **F1** Idempotencia deposit/withdraw aislada por cuenta + `type` (align lookup ↔ UNIQUE por-cuenta)
- **F2** 409 `IDEMPOTENCY_KEY_REUSED` ante `idempotency_key` reutilizada con payload distinto (sin migración)
- **F3** Carrera de custodia idempotente → nunca 500 en contienda (UNIQUE + savepoint + detección de violación)
- **F4** DTOs financieros estrictos (Pydantic fail-fast 422): `ge/gt` + `allow_inf_nan=False` en `CommissionProfileDto` / `CreateInvestmentAccountDto`
- **F5** Sesión con **epoch UTC** (`time.time()`) en vez de `time.monotonic()` (portable multi-host)
- **F6** `balance_after` documentado como **postcondición de app** (no constraint DB) + corrección de docs
- **F7** Suite de **concurrencia/invariantes** en PG real (`test_concurrency_scenarios.py`) + verifiers `scripts/verify/`
- **F8** Limpieza transversal E8: código/aliases muertos en Python + web + shared (pending-delete riesgo alto intacto)
- **F9 (V2)** — arquitectura Python + puente `legacy_portfolio_id`: **DIFERIDA** (requiere ADR + decisión explícita)

### R-7 — Deuda de dinero real (cerrada)

- Doble cargo de custodia en GET concurrentes · deposit/withdraw idempotentes · claim AUTO no quemado
- Ledger con UNIQUE `(account_id, reference_type, reference_id, type)` · reconciliación cash↔ledger · cost-basis FIFO/avg con fee · margen real · max drawdown high-water-mark · `transfer_cash` muerto eliminado · trade+fee idempotente en AUTO execute/confirm · guard FIFO qty==0 + observabilidad PnL CORE-R · `total_unrealized_gain` fail-closed

### R-8 — Prevención de riesgo + contrato (cerrada; incluida en v1.1.0)

- Sesión HttpOnly firmada + logout · rate-limit login/status · invariante `balance_after` por grupo atómico · limpieza transversal baja (R-8D) · fidelidad wire DTOs shared (R-8B.3) · CONTRACT-STALE resuelto (`openapi.json`+`schema.d.ts` regenerados)

### Pendientes de decisión (no bloquean cierre)

- Contrato F2/F4: exponer el 409 + DTOs estrictos en OpenAPI (`contract:gen`) — pendiente
- `pending-delete` riesgo alto (no tocar hasta `purge storage`) · R-8C.2 scheduler-vs-worker · M-4/T-M4 (job dedicado custodia) · gobernanza IA

### Operativo (FUERA de repo)

- GitHub secret scanning · `TRUSTED_PROXIES` prod · registro BD `BP/.L`→`BP.L` · limpiar `logs/dev`

## [1.1.0] — 2026-08-20

Integridad R-7/R-8 y fidelidad de contrato. DEMO / paper; sin broker live.

### Seguridad / sesión (R-8B)

- Cookie de sesión **HttpOnly firmada** + logout + endpoint `authenticated`
- Rate-limit en login/status (R-8B.1)
- Sesión vulnerable a reutilización multi-host corregida (preludio de epoch en R-9.5)

### Robustez financiera (R-7)

- `A-1/A-3` custodia: mutex `claim_custody_charge` + release · `A-2` deposit/withdraw idempotentes por `idempotency_key`
- `L-M3/M-5` ledger UNIQUE por-cuenta+type · `M-1` fallback mark-to-cost · `M-2` `sum_cash_amounts` rest con ledger · `M-3` cost-basis con fee · `M-6` margen real · `M-4/T-M5` fees de custodia fuera de `fees_paid_total` · `M-7` dedup verificación por UNIQUE · `B-1` max drawdown high-water-mark · `B-3` `transfer_cash` eliminado · `B-4` trade+fee idempotente AUTO/confirm · `B-5` guard FIFO qty==0 + obs. PnL CORE-R · `B-2` `total_unrealized_gain` fail-closed
- Invariante `balance_after` por grupo atómico (R-8C) · bootstrap advisory-lock · fidelidad wire DTOs (R-8B.3, fases A–D) · CONTRACT-STALE resuelto

## [Unreleased] — stage 2026-08-06

### Listas / Visualizados

- **Visualizados** = espejo de pestañas abiertas (separado de **Estudio** API)
- Quitar selección cierra tabs (sin resucitar por autosave) · **Por IO** ordena por Índice Operativo
- Columnas opcionales IO/TA/FA/★/Postura · sort por columna (tabs siguen el orden)
- Foco buscar/pestaña: lista **Cartera → Estudio → resto** + scroll bajo cabecera sticky
- Docs: `visualizados-list-ux-2026-08-06.md` · handoff `session-handoff-2026-08-06-visualizados-list-ux.md`

### Arranque (perf)

- Windows: liberar puertos con `netstat` (sin PowerShell Get-NetTCPConnection)
- `GET /api/lists/memberships` batch · sync catálogo con TTL 60s en `GET /lists`
- Monitor / CORE-R: batch `instrument-strategy-tops/query` (menos N+1 al pintar Trading)
- CORE-R shell: primer tick + hydrate diferidos (~1.5–4 s / idle) tras el paint

### Estudio / Operativa (ADR-024 + UI procesos)

- Universo **Estudio** API · Supervisión ON · cadencias Vigilia / Frescura / Redescubrimiento
- UI: subtítulo procesos bajo el nombre · botones **Actualizar** / **Redescubrir** (barra inferior) · chips cadencia V·F·R en banner · sellos locales
- Manual/SEMI/AUTO en barra de estado (`OPERATIVA: …`) → Cuentas · Config (fuera del panel por valor)
- Docs: `docs/engineering/estudio-process-status-ui-2026-08-06.md` · handoff `session-handoff-2026-08-06-estudio-process-ui.md` · HELP sync
- GitHub: [jvelasca/Bolsa_V1](https://github.com/jvelasca/Bolsa_V1) · PR stage [#29](https://github.com/jvelasca/Bolsa_V1/pull/29)

## [1.0.0] — 2026-08-01

Primera release empaquetada (**BETA1 → GitHub V1**). DEMO / paper; sin broker live.

### Producto

- Embudo Backtesting: Coach ★ local · Lab AT · Lista AUTO (frescura v1.3) · Finalistas
- **CORE-P** perfil ↔ Coach/Lab (gate, techo DD, soft-bias espacio, E2E smoke/ASGI)
- **CORE-B** v0.2 memoria Lab (meseta → espacio · `resolveDefaultLabFamily`)
- **CORE-R** v1.8 reevaluación (Monitor, cola, narración; cron local)
- **DÍA D** v0.11 simulación as-of + Evidence (fullBleed no se persiste)
- Análisis del valor / FA·FIE · Tarjeta CAPM footnote · Composite liquidez v1.1
- Trading supervisado F3 (Decision Engine); paper auto dry-run (execute off-by-default)
- Ayuda / trackers sincronizados (`HELP_CONTENT_AS_OF` 2026-08-01)

### Calidad

- `pnpm test:coach` · `test:coach:smoke` · `test:coach:api`
- `pnpm test:operativa` · `test:operativa:smoke`
- `pnpm test:fa`

### Congelado (no en V1)

- Belief UI · Lab Discovery P3–P9 · `PAPER_D_EXECUTE` · CORE-R multi-dispositivo · broker live

### Notas

- Stack: React/Vite + FastAPI + PostgreSQL
- Requiere Node ≥20, pnpm ≥10, Python ≥3.11, Docker Desktop
