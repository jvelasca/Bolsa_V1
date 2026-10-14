# Audit pack — `v2.88.127-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-14 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.127-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, dónde está la evidencia, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** documento de **evidencia/enlace**, no de producto. **`Δ motor = 0` · `Δ decisión = 0`** (no toca la lógica de decisión). Tag **unsigned** (anotado, sin firma GPG).

---

## 0. TL;DR — auditar en dos comandos

```bash
git clone --branch v2.88.127-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

O, más estricto (fija el **commit** exacto, no el tag):

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1 && git checkout __TAG_COMMIT__
```

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag (anotado)** | `v2.88.127-beta` |
| **Objeto de tag** | `__TAG_OBJECT__` |
| **Commit apuntado** | `__TAG_COMMIT__` |
| **Commit del contenido del sello** | `38c26ae940bc3e8de5f78859d13329dbff1088c1` (ola 6 + `H3` + auditoría de aislamiento XTB) |
| **Base (tag anterior)** | `v2.88.126-beta` → `7801474c` |
| **Versión monorepo** | `2.11.127-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `053_dia_d_cycle_verifications` (**sin migración**) |
| **Firma** | **unsigned** (anotado, sin GPG) |

> **Nota:** la fila `Objeto de tag` / `Commit apuntado` se completa en el commit **POST-TAG** (que cita el `Release tag CI`), igual que en el audit pack de `v2.88.125`. El commit `38c26ae9` es el contenido del sello; el tag anotado apunta al commit que lo publica.

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.127-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | `git checkout __TAG_COMMIT__` |
| Ver el árbol en la web | [tree/v2.88.127-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.127-beta) |
| Ver el commit del sello | [commit/38c26ae9](https://github.com/jvelasca/Bolsa_V1/commit/38c26ae9) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`evidence/v2.88.127/README.md`](./evidence/v2.88.127/README.md) | Evidencia del sello: qué cierra cada commit, verificación y **límites declarados** |
| 2 | [`CHANGELOG.md` §`2.11.127-beta`](../../CHANGELOG.md) | Nota de release: alcance, deltas, límites, verificación local |
| 3 | [`PROJECT_STATE.md`](./PROJECT_STATE.md) (AsOf `V2.88.127-beta`) | Estado vivo + **agenda funcional** (qué sigue abierto) |
| 4 | [`auditoria-aislamiento-ejecucion-xtb-2026-10-14.md`](./auditoria-aislamiento-ejecucion-xtb-2026-10-14.md) | Auditoría de aislamiento XTB: barreras, huecos `G1`…`G6` y **falsabilidad** |
| 5 | [`auditoria-ui-olas-2-6-2026-10-13.md`](./auditoria-ui-olas-2-6-2026-10-13.md) | Auditoría de olas UI 2..6 (veredicto por ola) |
| 6 | [`spec-auto-ui-semantic-model-1-2026-10-05.md`](./spec-auto-ui-semantic-model-1-2026-10-05.md) | Modelo semántico del relato DÍA-D **ratificado a 14 conceptos** (`H3`) |

---

## 4. CI público (citable)

**`Release tag CI` del tag:** __CI_SECTION__

---

## 5. Qué **certifica** esta versión

Publica los **3 commits** que quedaban sobre `v2.88.126-beta`, cerrando la **ola 6 (UI)** y la deuda **`H3`**, y entrega la **auditoría de aislamiento de ejecución XTB** con su único `P2` **cerrado**:

- **Ola 6 `DONE` (y con ella las olas 2..6 `DONE`) — invariante `UNKNOWN ≠ 0` (`O6-06`).** Nuevo primitivo `SurfaceLevelDeclaration`/`SURFACE_LEVEL_ATTR` (`data-surface-level`) y helper `absentDataLabel()`; el gate falsable `first-level-gate.ts` gana `findFirstLevelFalseZeros` (detecta el relleno `?? 0`) y refuerza la detección del comodín `—` ⇒ una **ausencia nunca** se pinta como `0` (ni como SLA verde) en el primer nivel.
- **Ola 6 `DONE` — nivel 3 explícito (`O6-01/02/03`).** La consola declara su nivel (`<SurfaceLevelDeclaration level={3} data-testid="ops-surface-level" />`) y la evidencia AUTO (`OpsAutoEvidenceSection`) **sale del primer nivel** al entrar en `<TechnicalDetail testId="ops-technical-detail">`; el copy de cabecera se humaniza conservando el prefijo `/Resolver excepciones/i`.
- **`H3` CERRADO — la etapa `EXIT` es fila propia.** `auto-operation-story.ts`: `EXIT` pasa a `foldedInto: null` y publica el **motivo durable** `SETTLEMENT.facts.exitReason` (o declara el hueco con `measurement: "UNKNOWN"`); **no** duplica los hechos financieros de `SETTLEMENT` (`closedQty`/`pnl`). El **modelo semántico queda ratificado a 14 conceptos** (no se añade un 15º id).
- **Auditoría de aislamiento de ejecución XTB — `AISLADO` en código, sin hallazgos `P1`.** Doble barrera de entorno fail-closed, sandbox sin HTTP, `broker_venue` por defecto `paper`, permiso SIM-only sellado, dry-run que nunca envía, kill switch e invariante AST. **`G1` `P2` se cierra en este mismo sello** (los dos tests de aislamiento del broker pasan a correr **por commit**; `W-G2/2` 34 → 32).

**Deltas:** `Δ decisión = 0` · **sin migración** (`053`) · **`Δ contrato = 0`** (sin cambio de contrato HTTP) · **`Δ CI = 1`** (cableado de los dos tests de broker al pase por commit).

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **Ventana PAPER longitudinal (`P3-2`/`P3-3`, ADR-046)** — sigue **`NO MEDIDO` / `INCONCLUSIVE`**. Criterios de fuente única `operability_window.py:88-90` (≥4 días de **calendario** / ≥2 **regímenes** distintos / ≥32 **ciclos medibles** con R). Medido hoy: 451 cuentas con fills y **todas** con `distinct_days = 1`; **0** fills en la cuenta PAPER declarada; regímenes distintos = **1** (`BULL_TREND`); fills con `cycle_id` = **0**; snapshots = **0**; salida literal `dias=42/4 episodios=0/2 ciclos=0/32 => INCONCLUSIVE`. **No** se emite `CONFIRMED`.
2. **Aislamiento XTB — residuos `P3` abiertos (`G2`..`G6`).** `G2` alcance del invariante AST acotado a `bolsa_application` + `apps/*/src`; `G3` el invariante no ve dispatch dinámico (`getattr`/`importlib`); `G4` el recovery worker nace ON (read-only, apply financiero OFF); `G5` `POST /api/risk/broker-venue` y `/kill-switch` no abren dinero por sí solos (auth no verificada en la firma); `G6` sin fugas de credenciales (el bridge XTB es frontera de confianza **fuera** del repo).
3. **`G2`..`G6`** y el **eslabón externo** (bridge XTB, `XTB_BRIDGE_FILL_ORDERS`) quedan **fuera** de lo verificable dentro del repo.
4. **P&L** — el DÍA-D certifica **identidad de fuentes y motivos**, **no** rentabilidad ni magnitud.
5. **Habilitación real** — `AUTO_ORCHESTRATOR_ENABLED`/`AUTO_SIMULATION_WORKER_ENABLED` nacen **OFF** (SIM-only).
6. **Deuda UI preexistente** — `heading-order` (11 rutas L1) y `axe` (solo con mocks) siguen como deuda declarada.

---

## 7. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | El tag `v2.88.127-beta` apunta al commit del sello y este desciende de `v2.88.126-beta` (`7801474c`). | `git rev-parse` / `git cat-file -p` del tag da otro commit o linaje. |
| 2 | `2.11.127-beta` es la versión del árbol. | `package.json` muestra otra versión. |
| 3 | El invariante `UNKNOWN ≠ 0` se sostiene: el gate detecta relleno `?? 0`/comodín `—` de primer nivel y **no** marca ceros legítimos ni tokens dentro de un `TechnicalDetail`. | El gate de primer nivel deja pasar un `?? 0` o un `—` de primer nivel en la consola. |
| 4 | `EXIT` es fila propia que lee el motivo durable y declara el hueco cuando falta. | Con `SETTLEMENT.facts.exitReason` presente `EXIT` no es `REACHED`/`COMPLETE`, o sin él no declara `UNKNOWN` con nota de hueco. |
| 5 | `EXIT` no republica los hechos financieros de `SETTLEMENT` (`closedQty`/`pnl`). | `EXIT` expone `closedQty` o `pnl`. |
| 6 | El certificador PAPER **no fabrica** (ventana no alcanzada ⇒ `INCONCLUSIVE`, no `READY`). | `certify_paper_window` devuelve `READY` con criterios faltantes, o `0` donde no midió. |
| 7 | El censo de tests no tiene ficheros invisibles y los dos tests de broker corren **por commit**. | `uv run python scripts/ci/test_selection.py --report` muestra `SIN DECLARAR > 0`, o `test_broker_adapter`/`test_broker_venue_per_account` vuelven al `--ignore` del job por commit. |
| 8 | El `Release tag CI` del tag es **verde**. | El run citado tiene algún job en `failure`. |
| 9 | Sin migración: head `053_dia_d_cycle_verifications`. | `alembic heads` (desde `packages/py/infrastructure`) da otro head. |

---

## 8. Reproducir la verificación (local, opcional)

```bash
# Lint / tipos / contratos / import-linter (comando de CI)
uv run ruff check packages/py apps/api-python --config pyproject.toml
uv run mypy packages/py/domain/src packages/py/market/src packages/py/infrastructure/src \
            packages/py/application/src apps/api-python/src --follow-imports=silent
uv run lint-imports --config packages/py/.importlinter

# Tests del sello
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
uv run --no-sync python -m pytest apps/api-python/tests/test_ci_test_selection_census.py -q
pnpm --filter @bolsa/shared test
pnpm --filter @bolsa/web test

# Censo de selección (agujero declarado) + ventana PAPER (read-only)
uv run --no-sync python scripts/ci/test_selection.py --report
uv run --no-sync python apps/api-python/scripts/v2_98_paper_window_certification.py --help
```

**Resultados medidos de referencia (local):** guardián de bump **1 passed** (`2.11.127-beta`) · guarda de censo **5 passed** · censo **620/620 ejecutados, 0 sin declarar, 0 obsoletas** · los dos tests de broker movidos al pase por commit **29 passed** (idéntico con BD alcanzable y con `DATABASE_URL` a host/puerto inexistentes ⇒ **herméticos**).

> **Nota de alcance:** esta pasada no re-ejecutó las suites completas de `ruff`/`mypy`/`pytest` ni `pnpm --filter @bolsa/web test` (trabajo de sellado/cableado de CI, sin cambio de lógica de producto); el `CHANGELOG`, el `PROJECT_STATE` y la evidencia lo **declaran** de forma explícita.
