# Audit pack — `v2.88.128-beta` (auditable desde GitHub)

> **AsOf:** 2026-10-14 · **Repo:** [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) (**público**) · **Tag:** `v2.88.128-beta`
> **Propósito:** reunir en un solo sitio **todo lo necesario para auditar esta versión desde GitHub sin credenciales**: identidad inmutable, cómo obtenerla, dónde está la evidencia, qué **certifica**, qué **NO**, y cómo **falsarlo**.
> **Naturaleza:** documento de **evidencia/enlace**, no de producto. **`Δ producto = 0` · `Δ decisión = 0` · `Δ motor = 0`** (solo **tests + docs**). Tag **unsigned** (anotado, sin firma GPG).

---

## 0. TL;DR — auditar en dos comandos

```bash
git clone --branch v2.88.128-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git
```

O, más estricto (fija el **commit** exacto, no el tag):

```bash
git clone https://github.com/jvelasca/Bolsa_V1.git && cd Bolsa_V1 && git checkout 0d0a8c153831cba79fe06c89196d115a90ada656
```

---

## 1. Identidad inmutable del sello

| Elemento | Valor |
| --- | --- |
| **Tag (anotado)** | `v2.88.128-beta` |
| **Objeto de tag** | `b347d76ab5b20073b7eed714aacce9d24cdc82e8` |
| **Commit apuntado** | `0d0a8c153831cba79fe06c89196d115a90ada656` (contenido del sello: cierre `G2`/`G3`/`G5` + runbook de la ventana PAPER) |
| **Padre del commit** | `9f3d9b5d` (POST-TAG de `v2.88.127-beta`: cita del `Release tag CI` `38554913743` + audit pack de `v2.88.127`) |
| **Base (tag anterior)** | `v2.88.127-beta` → `38c26ae9` (objeto `f14049f2`) |
| **Versión monorepo** | `2.11.128-beta` ([`package.json`](../../package.json)) |
| **Alembic head** | `053_dia_d_cycle_verifications` (**sin migración**) |
| **Firma** | **unsigned** (anotado, sin GPG) |

> **Nota:** el tag anotado sella el **contenido** del sello (`0d0a8c15`). Este audit pack es un artefacto **POST-TAG** que vive en `main`, **por delante** del tag (mismo patrón que `v2.88.125`/`v2.88.127`). Se escribe **después** de que exista el run de CI, para **no** dejar placeholders en ningún árbol.

---

## 2. Cómo obtener la versión

| Forma | Comando / enlace |
| --- | --- |
| Clonar el tag (recomendado) | `git clone --branch v2.88.128-beta --depth 1 https://github.com/jvelasca/Bolsa_V1.git` |
| Fijar el commit SHA | `git checkout 0d0a8c15` |
| Ver el árbol en la web | [tree/v2.88.128-beta](https://github.com/jvelasca/Bolsa_V1/tree/v2.88.128-beta) |
| Ver el commit del sello | [commit/0d0a8c15](https://github.com/jvelasca/Bolsa_V1/commit/0d0a8c15) |

---

## 3. Evidencia — qué leer, en orden

| # | Documento | Qué responde |
| --- | --- | --- |
| 1 | [`evidence/v2.88.128/README.md`](./evidence/v2.88.128/README.md) | Evidencia del sello: qué cierra cada cambio, verificación y **límites declarados** |
| 2 | [`CHANGELOG.md` §`2.11.128-beta`](../../CHANGELOG.md) | Nota de release: alcance, deltas, límites, verificación local |
| 3 | [`PROJECT_STATE.md`](./PROJECT_STATE.md) (AsOf `V2.88.128-beta`) | Estado vivo + **agenda funcional** (qué sigue abierto) |
| 4 | [`auditoria-aislamiento-ejecucion-xtb-2026-10-14.md`](./auditoria-aislamiento-ejecucion-xtb-2026-10-14.md) | Auditoría de aislamiento XTB: barreras y huecos `G1`…`G6` (**`G2`/`G3`/`G5` cerrados aquí**) |
| 5 | [`plan-ventana-paper-arranque-operativo-2026-10-14.md`](./plan-ventana-paper-arranque-operativo-2026-10-14.md) | Runbook de la ventana PAPER (ADR-046): criterios, bloqueadores (OPERACIÓN) y §G con el **preflight real** |

---

## 4. CI público (citable)

**`Release tag CI` del tag (VERDE):** [run **38560567905**](https://github.com/jvelasca/Bolsa_V1/actions/runs/38560567905) — `success` en **~11m56s** (2026-10-14T12:00:07Z → 12:12:03Z).

| Job | Conclusión |
| --- | --- |
| `python (ruff/imports/mypy/pytest offline)` | success |
| `lifecycle-pg (Alembic + auth + golden restart)` | success |
| `frontend (typecheck/lint/test/build + contract:check)` | success |
| `shared (build/typecheck/test)` | success |
| `decision-spine` | success |
| `dr-verify (battery DB_DR / TCP CI)` | success |
| `replay-repro (regenera el artefacto del sello desde el fixture)` | success |
| `a7-gate (A7 C3 chaos live_a7 · dedicated real-PG)` | success |
| `playwright (mock E2E)` | success |
| `playwright (integrated AUTO S5)` | success |
| `security (gitleaks)` | success |
| `certify (aggregate + artifact)` | success |
| `playwright (integrated E2E, opt-in)` | **skipped** (opt-in por diseño) |

**Lo decisivo:** `replay-repro` = `success` ⇒ el artefacto congelado **se reproduce** (coherente con **`Δ decisión = 0`**); `lifecycle-pg` = `success` ⇒ el nuevo test `apps/api-python/tests/test_risk_control_auth.py` (auth de las rutas de control) pasa contra el stack real; `python` (offline) recoge el invariante AST ampliado (`G2`/`G3`) **por commit**.

**Artefactos descargables** (pestaña *Artifacts* del run):

| Artefacto | Tamaño | Id | Qué es |
| --- | --- | --- | --- |
| `release-tag-ci-summary` | 429 B | `11893430893` | Resumen agregado de la certificación |
| `replay-oos-durable-v2.88.7` | 306 720 B | `11891634452` | **Sello congelado** del replay OOS (reproducible) |

---

## 5. Qué **certifica** esta versión

Publica los **tests + docs** que cierran tres de los cinco huecos `P3` de la auditoría de aislamiento XTB, y entrega el runbook operativo de la ventana PAPER:

- **`G2` CERRADO — el invariante AST cubre TODO el monorepo.** [`test_a8_m0_auto_live_invariant.py`](../../packages/py/application/tests/test_a8_m0_auto_live_invariant.py) añade `test_no_other_package_references_live_money_path`, que censa `packages/py/{analytics,infrastructure,market,domain,ai}/src` con **allowlist invertida VACÍA** (`_OTHER_PACKAGE_ROOTS`) ⇒ un módulo de otro paquete que cablee el broker rompe en CI. El barrido ampliado **no** encontró referencias reales fuera de la allowlist (docstring-only en `bolsa_analytics/.../broker_adapter.py`).
- **`G3` CERRADO (con residual) — el invariante deja de ser un punto ciego ante el dispatch dinámico.** `_dynamic_dispatch_symbols` marca `getattr(obj, "<nombre prohibido>")`, `importlib.import_module(...)`, `__import__(...)`, `eval(...)`/`exec(...)` y **literales string IGUALES** a `_FORBIDDEN_DYNAMIC_NAMES` (`resolve_broker_adapter`, `XtbBrokerAdapter`, `IBrokerAdapter`, `broker_adapter`, `bolsa_application.broker_adapter`). **Residual declarado:** los nombres **no literales** (`getattr(mod, var)`, `importlib.import_module(build)`, strings concatenados) siguen fuera del alcance del análisis estático.
- **`G5` CERRADO — la auth de las rutas de control de riesgo se fija por test.** Nuevo [`test_risk_control_auth.py`](../../apps/api-python/tests/test_risk_control_auth.py): con `APP_PASSWORD` puesto, `POST /api/risk/kill-switch`, `/api/risk/broker-venue` y `/api/risk/kill-switch/durable-release` exigen JWT (**401** sin credencial) porque **ninguna** vive en `PUBLIC_PREFIXES`; con JWT válido pasan (**200**); en dev sin `APP_PASSWORD` la auth está **OFF por diseño** (prod **fail-closed**).
- **Runbook de la ventana PAPER (ADR-046).** [`plan-ventana-paper-arranque-operativo-2026-10-14.md`](./plan-ventana-paper-arranque-operativo-2026-10-14.md): veredicto **verificado por lectura de código** de que los **tres** ejes (días/regímenes/ciclos medibles) son falta de **OPERACIÓN**, no hueco de software; incluye el **preflight real** (§G) y el diagnóstico del pin (`TREE_MOVED`).

**Deltas:** `Δ producto = 0` · `Δ decisión = 0` · `Δ motor = 0` · **sin migración** (`053`) · **`Δ contrato = 0`** · **`Δ CI = 0`** (ficheros de CI sin cambios; el nuevo test entra por el pase de **directorio**, censo `620 → 621`).

---

## 6. Límites / huecos **declarados** (lo que NO certifica)

1. **Ventana PAPER longitudinal (`P3-2`/`P3-3`, ADR-046)** — sigue **`NO MEDIDO` / `INCONCLUSIVE`**. Criterios de fuente única `operability_window.py:88-90` (≥4 días de **calendario** / ≥2 **regímenes** distintos / ≥32 **ciclos medibles** con R). Con el runbook se **descarta** el hueco de software (la cadena AUTO sí sella `cycle_id`; el régimen AUTO-10 está cableado), pero el **runtime contra PostgreSQL NO se probó** en esta pasada; la falsación está en §D del runbook. El **pin de la ventana está desfasado** ⇒ `TREE_MOVED` hasta re-anclar (procedimiento en §G.1).
2. **Aislamiento XTB — residuos `P3`:** **`G4`** (el recovery worker nace ON; **read-only**, apply financiero fail-closed OFF) y **`G6`** (sin fugas de credenciales; el bridge XTB es frontera de confianza **fuera** del repo) quedan **CONFIRMADOS/declarados** (verificados hoy, **readonly**, **no** cerrados). **`G3` residual** (nombres no literales) declarado.
3. **El eslabón externo** (bridge XTB, `XTB_BRIDGE_FILL_ORDERS`) queda **fuera** de lo verificable dentro del repo.
4. **P&L** — el DÍA-D certifica **identidad de fuentes y motivos**, **no** rentabilidad ni magnitud.
5. **Habilitación real** — `AUTO_ORCHESTRATOR_ENABLED`/`AUTO_SIMULATION_WORKER_ENABLED` nacen **OFF** (SIM-only).
6. **Deuda UI preexistente** — `heading-order` (11 rutas L1) y `axe` (solo con mocks) siguen como deuda declarada.

---

## 7. Falsabilidad — cómo un auditor **rompe** cada afirmación

| # | Afirmación | Cómo se rompe |
| --- | --- | --- |
| 1 | El tag `v2.88.128-beta` apunta al commit del sello y este desciende de `v2.88.127-beta` (`38c26ae9`). | `git rev-parse` / `git cat-file -p` del tag da otro commit o linaje. |
| 2 | `2.11.128-beta` es la versión del árbol. | `package.json` muestra otra versión. |
| 3 | El invariante AST censa **todos** los paquetes: un módulo fuera de `bolsa_application` que importe/use la vía real rompe el test. | Un `import`/atributo/`.submit` a la vía real en `analytics`/`infrastructure`/`market`/`domain`/`ai` **no** hace fallar `test_no_other_package_references_live_money_path`. |
| 4 | El invariante caza el dispatch **dinámico** por nombre literal. | `getattr(mod, "resolve_broker_adapter")`, `importlib.import_module("bolsa_application.broker_adapter")` o el literal `"XtbBrokerAdapter"` en un módulo barrido **no** rompen el invariante. |
| 5 | Las rutas de control de riesgo exigen auth con `APP_PASSWORD`. | Con `APP_PASSWORD` puesto y **sin** JWT, `POST /api/risk/kill-switch` (o `broker-venue`) **no** responde `401`; o alguna ruta empieza por un `PUBLIC_PREFIXES`. |
| 6 | El certificador PAPER **no fabrica** (ventana no alcanzada ⇒ `INCONCLUSIVE`, no `READY`). | `certify_paper_window` devuelve `READY` con criterios faltantes, o `0` donde no midió. |
| 7 | El censo de tests no tiene ficheros invisibles (el nuevo test entra por directorio). | `uv run python scripts/ci/test_selection.py --report` muestra `SIN DECLARAR > 0` o `test_risk_control_auth.py` fuera del universo. |
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

# Tests del sello (invariante AST ampliado + auth de control)
uv run --no-sync python -m pytest packages/py/application/tests/test_a8_m0_auto_live_invariant.py -q
uv run --no-sync python -m pytest apps/api-python/tests/test_risk_control_auth.py -q
uv run --no-sync python -m pytest apps/api-python/tests/test_dia_d_bump_guard.py -q
uv run --no-sync python -m pytest apps/api-python/tests/test_ci_test_selection_census.py -q

# Censo de selección + ventana PAPER (read-only)
uv run --no-sync python scripts/ci/test_selection.py --report
uv run --no-sync python apps/api-python/scripts/v2_98_paper_window_certification.py --help
```

**Resultados medidos de referencia (local):** invariante AST ampliado **41 passed** · auth de control **8 passed** · guardián de bump **1 passed** (`2.11.128-beta`) · guarda de censo **5 passed** · censo **621/621 ejecutados, 0 sin declarar, 0 obsoletas** · `ruff` sobre el test AST **All checks passed**.

> **Nota de alcance:** esta pasada no re-ejecutó las suites completas de `ruff`/`mypy`/`pytest` ni `pnpm --filter @bolsa/web test` (trabajo de sellado de tests + docs, sin cambio de lógica de producto); las cubre el `Release tag CI` del tag, y el `CHANGELOG`, el `PROJECT_STATE` y la evidencia lo **declaran** de forma explícita.
