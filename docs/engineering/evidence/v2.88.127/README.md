# Evidencia `v2.88.127-beta` — cierre de la ola 6 (UI) y de `H3`: los huecos no se colapsan a `0`/verde y la etapa `EXIT` del relato DÍA-D es fila propia con su motivo durable

> **Bump:** `2.11.126-beta` → **`2.11.127-beta`** (`package.json` + `meta.bump` del CLI OOS `v2_87`, de los 9 CLIs `v2_89`…`v2_97` y del certificador `v2_98`; guardián [`test_dia_d_bump_guard`](../../../../apps/api-python/tests/test_dia_d_bump_guard.py) verde).
>
> **Naturaleza:** incremento **mixto UI/shared** — **UI** (ola 6: nivel 3 explícito + invariante `UNKNOWN ≠ 0`) y **presentación del relato** (`packages/shared`, etapa `EXIT`). **`Δ decisión = 0`** (sin umbrales/reparto/`TOP_N`/régimen/selección/protección/ejecución) · **`Δ motor de decisión = 0`** (se toca la **capa de presentación** del relato y **primitivos UI**, no el motor) · **SIN migración** (head `053_dia_d_cycle_verifications`) · **SIN cambio de contrato HTTP** (`Δ contrato = 0`: el read-model Python ya publicaba `exitReason`). Tag **unsigned**.
>
> **Base:** `v2.88.126-beta`. Cubre los **3 commits** que hoy están sobre `v2.88.126-beta`: `0fa81a9c` (ola 6, `O6-06`), `5693971b` (ola 6, `O6-01/02/03`) y `90bfce05` (`H3`).

---

## 1. Ola 6 CERRADA — los huecos NO se colapsan a `0`/verde (`O6-06`, commit `0fa81a9c`)

**Antes:** un dato **ausente** podía leerse como `0` (o como SLA verde) en el primer nivel de la consola: la fuga **simétrica** del comodín `—` (el guion admite que falta el dato; el `0` lo **niega**).

**Ahora:**

- **Primitivo nuevo.** [`surface-level.tsx`](../../../../apps/web/src/components/surface-level.tsx): `SurfaceLevelDeclaration` + `SURFACE_LEVEL_ATTR` (`data-surface-level`) materializan en el primer nivel la **declaración de nivel** de una superficie (nivel 1/2/3), sin introducir un mecanismo de profundidad nuevo (el disclosure sigue siendo `TechnicalDetail`).
- **Gate falsable endurecido.** [`first-level-gate.ts`](../../../../apps/web/src/components/first-level-gate.ts) gana `findFirstLevelFalseZeros` (detecta el relleno `?? 0` pegado a un `0` literal) y refuerza la detección del comodín `—` (literal entrecomillado, guion embebido junto a delimitador y nodo JSX de solo-guion). Ambos operan **fuera** de los bloques `TechnicalDetail`/`AutoTechnicalDetail`.
- **Helper de etiqueta de ausencia.** `absentDataLabel()` nombra el hueco en vez de colapsarlo.
- **Consola.** [`operational-console-sections.tsx`](../../../../apps/web/src/features/operational-console/operational-console-sections.tsx) **deja de colapsar** los huecos a `0`/verde en el primer nivel.

**Invariante (falsable):** **`UNKNOWN ≠ 0`** — una ausencia **nunca** se pinta como `0` ni como SLA verde en el primer nivel. Un cero **legítimo** (recuento real ya materializado) o un valor dentro de un `TechnicalDetail` **no** se marcan.

**Criterio de aceptación FALSABLE (cumplido):** el gate detecta un `?? 0` de primer nivel y un comodín `—` de primer nivel, y **no** marca ni el cero legítimo ni el guion de prosa ni los mismos tokens dentro de un `TechnicalDetail`.

---

## 2. Ola 6 CERRADA — la consola declara su nivel 3 y la evidencia AUTO sale del primer nivel (`O6-01/02/03`, commit `5693971b`)

**Ahora:**

- **Nivel 3 explícito.** [`operational-console-page.tsx`](../../../../apps/web/src/features/operational-console/operational-console-page.tsx): `<SurfaceLevelDeclaration level={3} data-testid="ops-surface-level" />` declara que la consola es superficie de **diagnóstico** (nivel 3), para que no se confunda con la vista de operación diaria.
- **La evidencia AUTO sale del primer nivel.** `OpsAutoEvidenceSection` se **mueve dentro** de `<TechnicalDetail testId="ops-technical-detail">` ⇒ la jerga de ingeniería de la evidencia AUTO queda **detrás del disclosure**, no en el primer nivel.
- **Copy humanizado.** La cabecera se reescribe en lenguaje llano conservando el prefijo `/Resolver excepciones/i` (ancla del censo de primer nivel).

**Con esto la ola 6 queda `DONE` y las olas 2..6 quedan `DONE`** ([`auditoria-ui-olas-2-6-2026-10-13.md`](../../auditoria-ui-olas-2-6-2026-10-13.md)).

**Mapeo criterio → test (evidencia):** [`surface-level.test.tsx`](../../../../apps/web/src/components/surface-level.test.tsx) (el atributo `data-surface-level` declara el nivel) y [`operational-console-page.test.tsx`](../../../../apps/web/src/features/operational-console/operational-console-page.test.tsx) (nivel 3 declarado + evidencia AUTO fuera del primer nivel).

---

## 3. `H3` CERRADO — la etapa `EXIT` es fila propia con el motivo durable (`90bfce05`)

**Antes:** la «señal de SALIDA» estaba **plegada** en `SETTLEMENT` (no había etapa `EXIT` propia).

**Ahora** ([`auto-operation-story.ts`](../../../../packages/shared/src/cognitive/auto-operation-story.ts)):

- `EXIT` pasa a `foldedInto: null` (fila propia) y lee el **motivo durable** `SETTLEMENT.facts.exitReason` (o `reason` si existe un paso `EXIT` explícito).
- **Con motivo** ⇒ `facts: [{ label: "reason", value, measurement: "COMPLETE" }]` y `state: "REACHED"`.
- **Sin motivo** ⇒ `value: null`, `measurement: "UNKNOWN"` **con nota de hueco** (política `UNKNOWN ≠ 0`; nunca un motivo de relleno).
- **No duplica** los hechos financieros de `SETTLEMENT` (`closedQty`, `pnl`): `EXIT` publica el **motivo**, no el dinero.
- El **modelo semántico queda ratificado a 14 conceptos** (no se añade un 15º id).

**`Δ motor = 0` / `Δ contrato = 0`.** El read-model Python **ya** publicaba `exitReason`; este cambio solo mueve la etapa en la **capa de presentación** del relato.

**Criterio de aceptación FALSABLE (cumplido):** con `SETTLEMENT.facts.exitReason` presente, `EXIT` es `REACHED` con el motivo `COMPLETE`; sin él, `EXIT` declara `UNKNOWN` con nota de hueco (nunca `0`/motivo inventado); `EXIT` no republica `closedQty`/`pnl`.

**Mapeo criterio → test (evidencia):** [`auto-operation-story.test.ts`](../../../../packages/shared/src/cognitive/auto-operation-story.test.ts) (fila propia, motivo durable vs hueco declarado, no duplicación) y [`auto-operation-story-panel.test.tsx`](../../../../apps/web/src/features/auto-monitor/auto-operation-story-panel.test.tsx).

---

## 4. Verificación (local)

| Comprobación | Resultado |
|--------------|-----------|
| Guardián de bump (`uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q`) | **1 passed** (`2.11.127-beta`) |
| Guarda de censo (`... python -m pytest apps/api-python/tests/test_ci_test_selection_census.py -q`) | **5 passed** |
| Censo de selección (`uv run --no-sync python scripts/ci/test_selection.py --report`) | **620/620 ejecutados · 0 sin declarar · 0 obsoletas** |
| Los **dos** tests de broker movidos al pase por commit (`test_broker_adapter` + `test_broker_venue_per_account`) | **29 passed** (idéntico con la BD alcanzable y con `DATABASE_URL` a host/puerto inexistentes ⇒ **herméticos**) |
| `grep` de `2.11.126-beta` tras el bump | **solo** en documentos **históricos** (entrada `CHANGELOG` de `2.11.126-beta`, `PROJECT_STATE` de `v2.88.126`, `deuda-cierre-dia-d-h3-h5-h6` y `evidence/v2.88.126`), **ninguno** ligado al bump |
| `ruff` / `mypy` / `pytest` completos, `pnpm --filter @bolsa/web test`, `contract:gen`/`contract:check` | **NO ejecutado localmente** en esta pasada (sellado + cableado de CI); **sí** los cubre el `Release tag CI` del tag (ver §6) |
| **`Release tag CI` del tag** ([run 38554913743](https://github.com/jvelasca/Bolsa_V1/actions/runs/38554913743)) | **`success` en 10m26s** — **12/12** jobs `success` + `certify` (`python`, `lifecycle-pg`, `frontend` incl. `contract:check`, `shared`, `decision-spine`, `dr-verify`, `replay-repro`, `a7-gate`, `playwright (mock E2E)`, `playwright (integrated AUTO S5)`, `security`, `certify`); `playwright (integrated E2E, opt-in)` = `skipped` por diseño |
| Prettier | El `format` del repo cubre `**/*.{ts,tsx,js,json}` (**no** markdown) y `.prettierignore` excluye `docs/engineering/evidence/` ⇒ los `.md` de este sello viajan **sin reformatear** |

---

## 5. Límites declarados (sin fabricar) + falsabilidad

### 5.1 Ventana PAPER longitudinal (ADR-046) — **NO MEDIDO / `INCONCLUSIVE`**

**Criterios** (fuente única [`operability_window.py:88-90`](../../../../packages/py/application/src/bolsa_application/operability_window.py)): **≥4 días de CALENDARIO**, **≥2 regímenes/episodios DISTINTOS**, **≥32 ciclos MEDIBLES** (con R).

**Medido hoy** sobre la BD local real con el CLI read-only [`v2_98_paper_window_certification.py`](../../../../apps/api-python/scripts/v2_98_paper_window_certification.py):

| Hecho medido | Valor |
|--------------|-------|
| Cuentas con fills | **451**, y **TODAS** con `distinct_days = 1` |
| Cuenta PAPER declarada (`PAPER_D_ACCOUNT_ID = 1484e253d2d54645945a6b1d7`) | **0 fills** |
| Máximo de días (`40787fbdb2354f70a3aec5256`) | **42** — pero **solo-journal** (sus **504** fills son de un **único** día) |
| Regímenes distintos en todo el journal | **1** (`BULL_TREND`) |
| Fills con `cycle_id` | **0** |
| Reservas | **38 filas / 19 `cycle_id` / 13 cuentas** (≤4 por cuenta) |
| Filas de `auto_paper_evidence_snapshot` | **0** |
| Salida literal del CLI | `dias=42/4 episodios=0/2 ciclos=0/32 => INCONCLUSIVE` |

**Falta** `episodes` y `measurable_cycles`. Conclusión: **no certificable**; lo que falta es **OPERACIÓN real** (≥4 días de calendario sellando hechos durables, ≥2 regímenes, ≥32 ciclos medibles con `cycle_id`). **No** se emite `CONFIRMED`.

### 5.2 Auditoría de aislamiento de ejecución XTB — **AISLADO en código, sin hallazgos P1**

Informe completo: [`auditoria-aislamiento-ejecucion-xtb-2026-10-14.md`](../../auditoria-aislamiento-ejecucion-xtb-2026-10-14.md). Resumen: ninguna ruta AUTO alcanza dinero real con los defaults; doble barrera de entorno fail-closed, sandbox sin HTTP, `broker_venue` default `paper`, permiso SIM-only sellado, dry-run que nunca envía, kill switch e invariante AST. **Residuos:** **`G1` `P2` se cierra en este mismo sello** (`v2.88.127-beta`): los dos tests de aislamiento del broker ([`test_broker_adapter.py`](../../../../packages/py/application/tests/test_broker_adapter.py) y [`test_broker_venue_per_account.py`](../../../../packages/py/application/tests/test_broker_venue_per_account.py), herméticos sin PG) pasan a correr **por commit** en [`python-ci.yml`](../../../../.github/workflows/python-ci.yml) y salen del lote `W-G2/2` del sello (34 → 32 ficheros) y del `--ignore` del job offline. **`G2`..`G6` `P3` siguen declarados abiertos.**

### 5.3 Falsabilidad

- **Ola 6:** re-ejecutar el gate de primer nivel ([`first-level-gate.ts`](../../../../apps/web/src/components/first-level-gate.ts)) sobre `operational-console-sections.tsx`; si aparece un `?? 0` o un comodín `—` de primer nivel, la afirmación `DONE` se **rompe**.
- **`H3`:** si con `SETTLEMENT.facts.exitReason` presente `EXIT` no es `REACHED`/`COMPLETE`, o si sin él no declara `UNKNOWN` con hueco, la afirmación se **rompe**.
- **PAPER:** re-ejecutar el CLI `v2_98` sobre la BD real; en cuanto cualquier cuenta acumule **≥4 días de calendario** con **≥2 regímenes** y **≥32 ciclos con `cycle_id`**, el certificado **deja** de ser `INCONCLUSIVE`.

---

## 6. `Release tag CI` del sello — **VERDE**

Sello **publicado**: `main` empujado y tag anotado **`v2.88.127-beta`** (objeto `f14049f22eaf2c2a22444b8e11891cbbc4072874` → commit `38c26ae940bc3e8de5f78859d13329dbff1088c1`, el contenido del sello).

**`Release tag CI` [run 38554913743](https://github.com/jvelasca/Bolsa_V1/actions/runs/38554913743)** — `success` en **10m26s** (2026-10-14T11:12:12Z → 11:22:38Z): **12/12 jobs `success`** (`python`, `lifecycle-pg`, `frontend`, `shared`, `decision-spine`, `dr-verify`, `replay-repro`, `a7-gate`, `playwright (mock E2E)`, `playwright (integrated AUTO S5)`, `security`, `certify`) + `playwright (integrated E2E, opt-in)` = `skipped` por diseño. Los dos tests de aislamiento del broker (`G1`) corren ya en el job `python` **por commit**.

**Identidad:** tag anotado `v2.88.127-beta` (**unsigned**; objeto `f14049f22eaf2c2a22444b8e11891cbbc4072874` → commit `38c26ae940bc3e8de5f78859d13329dbff1088c1`), `package.json` = `2.11.127-beta`, Alembic head `053_dia_d_cycle_verifications` (**sin migración**).

**Audit pack (auditoría externa desde GitHub):** [`audit-pack-v2.88.127-beta-2026-10-14.md`](../../audit-pack-v2.88.127-beta-2026-10-14.md).
