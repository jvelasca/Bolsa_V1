# Audit-pack — `v2.73-beta` · `AUTO-MATERIAL-1`: PAPER MATERIAL READINESS

> **AsOf:** 2026-09-26 · **Versión:** `1.98.0-beta` · **Base auditada (diff):** `v2.72-beta`
> **Alcance:** (A) convertir el bloqueo por material de `v2.72` en un **diagnóstico operativo medido**
> con un gate **read-only** (CLI + JSON) y sondas de linaje A/B/C/D, que se corre **antes** de
> `auto_evidence_run.py` (`AUTO-22`); (B) **no** reparar el productor, **no** tocar el freeze ni el
> reparto y **no** ejecutar el RUN.
> **SIN migración** (head `046_fill_reference_mid`). **El freeze no se toca.** El reparto **no se
> mueve** (`auto18-v1` / `auto15-v1`).

## 1. Tesis a verificar (no a creer)

| # | Tesis | Dónde se sostiene | Test / sonda |
|---|---|---|---|
| 1 | El gate mide el **mismo** material que el instrumento (sin un segundo FIFO ni una segunda aritmética de R) | reutiliza `adaptive_instrument_cycles` | `test_a_strategy_with_enough_measured_cycles_is_ready` (conteos derivados de la fila del instrumento) |
| 2 | Material legacy (sin `cycle_id` ni reservas) ⇒ **BLOCKED** con los motivos nombrados, no un `READY` optimista | `build_paper_material_readiness` (blockers) | `test_legacy_material_is_blocked_and_declares_every_missing_link` |
| 3 | Sin reservas ⇒ **0 R medible** aunque haya cierres (no se sustituye el denominador por capital) | `cycle_risk_from_reservations` | `test_closures_without_reservations_leave_r_unmeasurable` |
| 4 | El gate **no** devuelve `READY` por debajo del mínimo de ciclos con R | guarda de `min_cycles_per_strategy` | `test_below_the_minimum_is_blocked_even_with_measured_cycles` + **M199** |
| 5 | Una reserva de **venta** (`reserved_risk = 0`) no se convierte en denominador de R | extracción de riesgo (solo entrada positiva) | `test_a_sell_reservation_does_not_become_the_denominator` |
| 6 | Lo **no medido** se declara (`None`), nunca un cero de relleno | `lineage.cycle.exitOrders*` | `test_exit_order_lineage_is_declared_and_never_invented` |
| 7 | El CLI sale `0` READY / `2` BLOCKED y emite el sello en el JSON | `scripts/paper_material_readiness.py` | `test_auto_v73_material_readiness_seam.py` (4 tests) |
| 8 | El material real de `v2.72` se reproduce y el gate sale `2` con `BLOCKERS` + `lineage` | medición contra `bolsa-postgres` | evidencia cruda (§5) |
| 9 | El freeze, el reparto y la migración siguen intactos | `git diff` del freeze + Alembic head | verificación git + head |

## 2. Qué cambia (y qué no)

**Cambia.**

- `packages/py/application/src/bolsa_application/paper_material_readiness.py` (**nuevo**): módulo puro
  `build_paper_material_readiness` + `PaperMaterialReadiness` + blockers + linaje. Sello
  `paper_material_readiness_v1`.
- `apps/api-python/scripts/paper_material_readiness.py` (**nuevo**): CLI read-only (tabla + `--json`,
  `0/2/1`) con guarda de venue `BROKER_VENUE=paper`.
- `packages/py/application/tests/test_paper_material_readiness.py` (**nuevo**): 7 tests puros.
- `apps/api-python/tests/test_auto_v73_material_readiness_seam.py` (**nuevo**): 4 tests de costura.
- `apps/api-python/scripts/v2_44_mutation_audit.py`: **`M199`** nueva (matriz **199/199**).
- bump `1.97.0-beta` → **`1.98.0-beta`**.

**No cambia.**

- **El productor**: no se toca el worker ni el pipeline V2; el gate **no repara** material.
- **El `exit 2`** de `paper_cycles_export.py` / `auto_evidence_run.py`: el gate es un **pre-flight
  separado**.
- **Reparto/freeze**: `auto18-v1` / `auto15-v1`; `portfolio_optimizer.py`,
  `portfolio_reservation.py`, `auto_adaptive.py`, `auto_simulation_worker.py`,
  `auto_adaptive_journal.py` intactos. **Sin migración** (`046_fill_reference_mid`).
- **`evidence_runs`/`evidence_validations`** y `governor.json`: intactos (no se escribe nada).
- **La UI**: no hay pantalla en esta fase (el JSON queda listo para una futura).

## 3. Mutación nueva

| Etiqueta | Invariante | Rojo en |
|---|---|---|
| **M199** | El gate **no** puede devolver `READY` sin el mínimo de ciclos cerrados con R por estrategia | `test_below_the_minimum_is_blocked_even_with_measured_cycles`, `test_legacy_material_is_blocked_and_declares_every_missing_link`, `test_closures_without_reservations_leave_r_unmeasurable`, `test_a_sell_reservation_does_not_become_the_denominator` |

**Nota de conteo:** la matriz pasa de `198` a **`199`** (`M1`–`M199` contiguos; el script la
autoreporta con `len(MUTATIONS)`).

## 4. Compuertas medidas

| Compuerta | Comando | Resultado |
|---|---|---|
| `ruff` | `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `import-linter` | `uv run --no-sync lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** |
| `mypy` | `uv run --no-sync mypy <5 paths> --follow-imports=silent` | **Success: 0 issues in 502 source files** |
| `analytics` + `application` | `uv run --no-sync pytest packages/py/analytics packages/py/application -q` | **3222 passed** (incluye los 7 nuevos) |
| costura `api-python` | `uv run --no-sync pytest apps/api-python/tests/test_auto_v73_material_readiness_seam.py -q` | **4 passed** |
| Matriz de mutaciones | `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py` | **199/199**, restauración **byte a byte**, árbol intacto |
| `evidence_runs/` | `Test-Path evidence_runs` | **NO existe** (el gate es read-only) |

> **Evidencia cruda de la matriz**: `evidencia-matriz-mutaciones-v2.73-199-2026-09-26.txt`
> (`199/199`, todas con fragmento presente, restauración byte a byte, `git status` sin cambios).
> **Nota de entorno:** la corrida offline completa de `apps/api-python` incluye 3 tests **DB-gated**
> (`test_tax_report_after_round_trip_trade`, `test_auto_v70_auto23_evidence_validation.py::…real_postgres…`,
> `test_workspaces_crud`) que dependen de PostgreSQL con datos; son **ajenos** a esta fase (no se
> toca ninguno de sus caminos) y no forman parte de la compuerta de esta fase.

## 5. El gate contra el material real (resultado declarado)

Medición contra `bolsa-postgres` (`2026-09-26`). Evidencia cruda en
`evidencia-material-readiness-v2.73-2026-09-26.txt`.

Reconciliación con `v2.72` (tabla completa): **761** fills · **0** con `cycle_id` · **751 `buy` / 10
`sell`** · **53** versiones · **0** reservas · **0** exit orders.

Cuenta del RUN (`181e7e07d27d4cdebc342ff83`, la de `v2.72`): **4** fills · **0** con `cycle_id` ·
**0** reservas · **0** exit orders ⇒ el gate declara **BLOCKED** con **los cinco motivos**
(`no cycle lineage` · `no reservations` · `no closed cycles` · `insufficient measurable cycles per
strategy` · `producer path not exercised`) y `exit 2`.

**Lectura:** el gate **confirma (no supone)** la hipótesis del plan: con el pipeline AUTO 2.0
(`AUTO_ENGINE_SIM_V2`) **OFF**, el worker usa el camino legacy y materializa fills **sin `cycle_id` y
sin reservas** ⇒ sin cierres con R medible. El bloqueo de `v2.72` pasa de "sorpresa tras el intento" a
"diagnóstico antes del intento".

**Declarado como límite:** la cuenta del RUN tiene **4** fills (su universo); los **761** son de toda
la tabla. El gate mide el universo que lee el instrumento (cuenta + versiones pedidas), y por eso su
`fillsTotalForAccount` es **4** — no un total de tabla que no le corresponde.

## 6. Límite declarado

Esta fase **solo mide y declara**. La **reparación de material** (activar el productor V2 y acumular
`≥32` ciclos medibles por estrategia) es la **fase siguiente** y queda fuera de alcance. **`P3-2`**
(correlación por cubos) y **`P3-3`** (`P(R>0)` vs N) siguen **abiertas** hasta el primer dataset real.
No hay UI en esta fase; el JSON queda listo para reutilizarla.

## 7. CI del tag `v2.73-beta` (verificado)

`main == a9166655` == **tag anotado objeto `fd891fcd…` → commit `a9166655`**.

| Workflow (tag `v2.73-beta`, commit `a9166655`) | Run | Resultado |
|---|---|---|
| **Release tag CI** | `36244779500` | **GREEN en la primera pasada** (8m52s; **10 jobs** en success + `certify`; `playwright (integrated E2E, opt-in)` **skipped** por diseño) |
| `Python CI` | `36244779488` | **success** (2m51s) |
| `Frontend CI` | `36244779559` | **success** (3m31s) |
| `Optimize lab` | `36244779562` | **success** (2m8s) |
| `Fase 2 scientific` | `36244779467` | **success** (1m25s) |

Jobs del `Release tag CI` (todos verdes): `decision-spine` (31s) · `python (ruff/imports/mypy/pytest
offline)` (1m54s) · `frontend (typecheck/lint/test/build + contract:check)` (3m11s) · `shared` (34s) ·
`lifecycle-pg (Alembic + auth + golden restart)` (3m44s) · `security (gitleaks)` (7s) · `playwright
(mock E2E)` (8m4s) · `dr-verify` (48s) · `a7-gate` (50s) · `certify (aggregate + artifact)` (3s) —
más `playwright (integrated E2E, opt-in)` **skipped** por diseño.

Sobre el mismo commit, en `main`: `Python CI` `36244778024` · `Frontend CI` `36244778014` ·
`Gitleaks` `36244778017` · `Optimize lab` `36244778000` · `Fase 2 scientific` `36244778040`, todos en
**success**.
