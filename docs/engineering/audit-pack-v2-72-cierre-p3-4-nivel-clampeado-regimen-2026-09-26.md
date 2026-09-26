# Audit-pack — `v2.72-beta` · cierre de `P3-4` (nivel clampeado en la lectura del régimen)

> **AsOf:** 2026-09-26 · **Versión:** `1.97.0-beta` · **Base auditada (diff):** `v2.71-beta`
> **Alcance:** (A) cerrar **`P3-4`**, la **única** observación de la auditoría externa de `v2.71-beta`
> —la lectura del régimen publicaba un `level` **crudo** mientras el bootstrap medía con el
> **clampeado**—; (B) declarar el resultado del **primer intento del RUN PAPER real**.
> **SIN migración** (head `046_fill_reference_mid`). **El freeze no se toca.** El reparto **no se
> mueve** (`auto18-v1` / `auto15-v1`).

## 1. Tesis a verificar (no a creer)

| # | Tesis | Dónde se sostiene | Test / sonda |
|---|---|---|---|
| 1 | El `level` que **publica** la lectura del régimen es el **clampeado** (`[0.5, 0.99]`), no el crudo | `build_current_regime_evidence` (`resolved_level`) | `test_the_interval_level_is_clamped_and_published` + **M198** |
| 2 | La celda publicada con `level` fuera de rango es la **MISMA** que con el nivel clampeado explícito (no hay segunda aritmética) | ídem | ídem (compara `evidence_for(...)` con la baseline del clamp) |
| 3 | El hueco declarado (sin ciclos) también publica el nivel clampeado | rama `not rows` | `test_the_clamped_level_travels_even_without_cycles` |
| 4 | El sello sube a `current_regime_evidence_v3` y ningún consumidor queda desalineado | constante de módulo | `test_the_regime_evidence_seal_is_v3` (fija el literal) |
| 5 | Con el `level` default (`0.90`) el payload es **byte-idéntico** al de `v2.71` | el clamp es idempotente dentro del rango | `test_the_regime_cell_reuses_the_bootstrap_and_publishes_probability_positive` (sin cambio) |
| 6 | El freeze, el reparto y la migración siguen intactos | `git diff v2.71-beta..v2.72-beta` del freeze; Alembic head | verificación git + head |
| 7 | El RUN PAPER se ejecuta **completo o se declara BLOQUEADO**; sin material **no** se baja ningún umbral | `paper_cycles_export.py` / `auto_evidence_run.py` | salidas `exit 2` medidas (ver §5) |

## 2. Qué cambia (y qué no)

**Cambia.**

- `.../auto_adaptive_regime_evidence.py`: `resolved_level` **clampeado** antes de publicarlo; sello
  `current_regime_evidence_v2` → **`v3`**; docstring del productor actualizada.
- `.../tests/test_auto_adaptive_regime_evidence.py`: **+3** tests (clamp, clamp sin ciclos, sello).
- `apps/api-python/scripts/v2_44_mutation_audit.py`: **`M198`** nueva (matriz **198/198**).
- bump `1.96.0-beta` → **`1.97.0-beta`**.

**No cambia.**

- **La aritmética**: el bootstrap, la `P(R>0)` por ciclos, la `P(edge>0)`, el `byStrategy`, los
  `notes` y la selección del régimen actual quedan **congelados**. Solo cambia **qué nivel se
  publica** cuando el llamante pasa uno fuera de rango.
- **Reparto/freeze**: `auto18-v1` / `auto15-v1`, `portfolio_optimizer.py`,
  `portfolio_reservation.py` intactos. **Sin migración** (`046_fill_reference_mid`).
- **`evidence_runs`/`evidence_validations`** y el runbook del primer RUN: intactos (el RUN bloqueado
  **no crea** carpeta).

## 3. Mutación nueva

| Etiqueta | Invariante | Rojo en |
|---|---|---|
| **M198** | El `level` publicado por la lectura del régimen es el **clampeado** (el que usó el bootstrap) | `test_the_interval_level_is_clamped_and_published` |

**Nota de conteo:** la matriz pasa de `197` a **`198`** (`M1`–`M198` contiguos; el script la
autoreporta con `len(MUTATIONS)`).

## 4. Compuertas medidas

| Compuerta | Comando | Resultado |
|---|---|---|
| `ruff` | `uv run --no-sync ruff check packages/py apps/api-python --config pyproject.toml` | **All checks passed!** |
| `import-linter` | `uv run --no-sync lint-imports --config packages/py/.importlinter` | **4 kept, 0 broken** |
| `mypy` | `uv run --no-sync mypy <5 paths> --follow-imports=silent` | **Success: 0 issues in 501 source files** |
| `analytics` | `uv run --no-sync pytest packages/py/analytics -q` | **1265 passed** (1262 + 3 nuevos) |
| costuras `api-python` | `test_auto_v60_…_seam` · `test_auto_v64_…_artifact` · `test_auto_v70_…_evidence_validation` | **13 passed, 1 skipped** (PG por DSN fast-fail, ajeno) |
| Matriz de mutaciones | `uv run --no-sync python apps/api-python/scripts/v2_44_mutation_audit.py` | **198/198**, restauración **byte a byte**, árbol intacto |

> **Evidencia cruda de la matriz**: `evidencia-matriz-mutaciones-v2.72-198-2026-09-26.txt`.
> La medición se hizo **contra el árbol ya commiteado** (`git status` de los ficheros mutados:
> `limpio` antes y después).

## 5. El primer RUN PAPER: BLOQUEADO por material (resultado declarado)

El RUN se **intentó** de verdad contra PostgreSQL y se declaró **BLOQUEADO** con el propio
instrumento. **No se relajó ningún umbral.** Evidencia cruda en
`evidencia-run-paper-bloqueado-v2.72-2026-09-26.txt`.

Hechos medidos en `bolsa-postgres` (`2026-09-26`):

| Hecho | Valor | Por qué bloquea |
|---|---|---|
| Fills durables | **761** | hay actividad, luego el lector llega a leer |
| Fills con `cycle_id` | **0** | ningún ciclo identificado (migración `044` sin poblar en este material) |
| Lados | **751 `buy` / 10 `sell`** | sin salida no hay **ciclo cerrado** ni resultado que medir |
| `portfolio_reservations` | **0 filas** | sin `reserved_risk` ⇒ **sin R medible** aunque hubiera cierre |
| Fills por versión (máx.) | **4** | muy por debajo de los **≥32 ciclos medidos** por estrategia |

Salidas medidas (código de bloqueo `2` en ambas, `fail-closed`):

- `paper_cycles_export.py --account-id <cuenta> --strategy-version <v>` →
  `# BLOQUEADO: no hay ciclos cerrados con fill durable para esas versiones/cuenta`.
- `auto_evidence_run.py --account-id <cuenta> --strategy-version <v> --bucket day --folds 3` →
  `# BLOQUEADO: sin ciclos con R medible: no se publica un bundle vacío como si fuera una medición`,
  y `evidence_runs/` **no existe** al terminar (`exist_ok=False` verificado).

**Lectura:** el instrumento está listo y se comporta como debe; lo que falta es **material**, con
**dos causas independientes** (faltan **cierres** y faltan **reservas**), cada una suficiente para
bloquear. Es **paso operativo del propietario**; no se convierte en una corrida a medias.

## 6. Límite declarado

Esta fase **corrige un nivel publicado**; **no** produce estadística nueva ni ejecuta el RUN. Las
deudas **P3-2** (correlación por cubos) y **P3-3** (`P(R>0)` vs N) siguen **abiertas** hasta el
primer dataset real, que sigue **BLOQUEADO por material**. **`P3-4` queda cerrada** por esta fase
(§1–§3).
